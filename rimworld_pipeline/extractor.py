from __future__ import annotations

from pathlib import Path
from typing import BinaryIO
import fnmatch
import json
import xml.etree.ElementTree as ET
import zipfile

from rimworld_pipeline.extractors.archive import extract_archive_messages
from rimworld_pipeline.extractors.battle import extract_battle_log_events
from rimworld_pipeline.extractors.common import clean_text, parse_int_value
from rimworld_pipeline.extractors.playlog import extract_playlog_interactions
from rimworld_pipeline.extractors.tales import extract_tale_events
from rimworld_pipeline.resolver import EntityResolver
from rimworld_pipeline.snapshots import (
    SaveSnapshot,
    SaveSource,
    WORLD_SAVE_MEMBER_PATH,
    load_map_snapshots,
)


def ticks_to_date(ticks: int) -> str:
    ticks_per_day = 60000
    ticks_per_year = 3600000
    days_per_quadrum = 15

    year_index = ticks // ticks_per_year
    day_within_year = (ticks % ticks_per_year) // ticks_per_day
    quadrum_index = day_within_year // days_per_quadrum
    day_within_quadrum = day_within_year % days_per_quadrum

    quadrum_names = ["Aprimay", "Jugust", "Septober", "Decembary"]
    quadrum_name = (
        quadrum_names[quadrum_index]
        if quadrum_index < len(quadrum_names)
        else f"Quadrum {quadrum_index + 1}"
    )

    return f"Year {year_index + 1}, {quadrum_name}, Day {day_within_quadrum + 1}"


def discover_save_sources(save_directory: Path, file_pattern: str) -> list[SaveSource]:
    zip_sources = [
        SaveSource(source_type="zip", path=file_path)
        for file_path in sorted(save_directory.iterdir())
        if file_path.is_file()
        and file_path.suffix.lower() == ".zip"
        and fnmatch.fnmatch(file_path.name, file_pattern)
    ]
    if zip_sources:
        return zip_sources

    raw_world_save_path = save_directory / WORLD_SAVE_MEMBER_PATH
    if raw_world_save_path.is_file():
        return [SaveSource(source_type="raw", path=raw_world_save_path)]

    return []


def extract_master_ticks_from_stream(xml_stream: BinaryIO) -> int:
    active_path_stack: list[str] = []

    for event_name, current_element in ET.iterparse(xml_stream, events=("start", "end")):
        if event_name == "start":
            active_path_stack.append(current_element.tag)
            continue

        if event_name == "end" and active_path_stack == [
            "savegame",
            "game",
            "tickManager",
            "ticksGame",
        ]:
            ticks_game_value = parse_int_value(current_element)
            if ticks_game_value is None:
                raise ValueError("Missing or invalid game/tickManager/ticksGame value.")
            return ticks_game_value

        if active_path_stack:
            active_path_stack.pop()

    raise ValueError("Unable to find game/tickManager/ticksGame in XML stream.")


def read_source_ticks(save_source: SaveSource) -> int:
    if save_source.source_type == "zip":
        with zipfile.ZipFile(save_source.path, "r") as archive_file:
            with archive_file.open(WORLD_SAVE_MEMBER_PATH, "r") as world_xml_stream:
                return extract_master_ticks_from_stream(world_xml_stream)

    with save_source.path.open("rb") as world_xml_stream:
        return extract_master_ticks_from_stream(world_xml_stream)


def get_chronological_sources(save_sources: list[SaveSource]) -> list[SaveSource]:
    save_source_and_tick_pairs = [
        (save_source, read_source_ticks(save_source)) for save_source in save_sources
    ]
    save_source_and_tick_pairs.sort(key=lambda source_and_tick: source_and_tick[1])
    return [save_source for save_source, _ in save_source_and_tick_pairs]


def load_save_snapshot(save_source: SaveSource) -> SaveSnapshot | None:
    if save_source.source_type == "zip":
        with zipfile.ZipFile(save_source.path, "r") as archive_file:
            with archive_file.open(WORLD_SAVE_MEMBER_PATH, "r") as world_xml_stream:
                world_root = ET.parse(world_xml_stream).getroot()
            map_snapshots = load_map_snapshots(archive_file)
    else:
        world_root = ET.parse(save_source.path).getroot()
        map_snapshots = []

    ticks_game = parse_int_value(world_root.find("./game/tickManager/ticksGame"))
    game_start_abs_tick = parse_int_value(world_root.find("./game/tickManager/gameStartAbsTick"))
    if ticks_game is None or game_start_abs_tick is None:
        return None

    return SaveSnapshot(
        source_path=save_source.path,
        source_type=save_source.source_type,
        world_root=world_root,
        map_snapshots=map_snapshots,
        ticks_game=ticks_game,
        game_start_abs_tick=game_start_abs_tick,
    )


def extract_snapshot_event(world_root: ET.Element, ticks_game: int) -> dict[str, object] | None:
    stats_record_element = world_root.find("./game/storyWatcher/statsRecord")
    if stats_record_element is None:
        return None

    snapshot_stats: dict[str, int] = {}
    for metric_tag in ["numRaidsEnemy", "numThreatsQueued", "greatestPopulation"]:
        metric_value = parse_int_value(stats_record_element.find(metric_tag))
        if metric_value is not None:
            snapshot_stats[metric_tag] = metric_value

    return {
        "type": "snapshot",
        "source": "storyWatcher.statsRecord",
        "tick": ticks_game,
        "human_date": ticks_to_date(ticks_game),
        "stats": snapshot_stats,
    }


def extract_events_for_snapshot(
    save_snapshot: SaveSnapshot,
    resolver: EntityResolver,
    last_seen_tale_tick: int,
    last_seen_playlog_tick: int,
    last_seen_archive_tick: int,
    historical_message_signatures: set[str],
    seen_message_signatures: set[str],
    historical_battle_signatures: set[str],
    seen_battle_signatures: set[str],
) -> tuple[list[dict[str, object]], int, int, int]:
    extracted_events: list[dict[str, object]] = []
    world_root = save_snapshot.world_root

    snapshot_event = extract_snapshot_event(world_root, save_snapshot.ticks_game)
    if snapshot_event is not None:
        extracted_events.append(snapshot_event)

    tale_events, highest_tale_tick = extract_tale_events(
        world_root=world_root,
        game_start_abs_tick=save_snapshot.game_start_abs_tick,
        last_seen_tick_abs=last_seen_tale_tick,
        resolver=resolver,
        ticks_to_date=ticks_to_date,
    )
    extracted_events.extend(tale_events)

    playlog_events, highest_playlog_tick = extract_playlog_interactions(
        world_root=world_root,
        game_start_abs_tick=save_snapshot.game_start_abs_tick,
        last_seen_tick_abs=last_seen_playlog_tick,
        resolver=resolver,
        ticks_to_date=ticks_to_date,
    )
    extracted_events.extend(playlog_events)

    archive_events, highest_archive_tick = extract_archive_messages(
        world_root=world_root,
        ticks_game=save_snapshot.ticks_game,
        last_seen_archive_tick=last_seen_archive_tick,
        historical_message_signatures=historical_message_signatures,
        seen_message_signatures=seen_message_signatures,
        ticks_to_date=ticks_to_date,
    )
    extracted_events.extend(archive_events)

    extracted_events.extend(
        extract_battle_log_events(
            save_snapshot=save_snapshot,
            resolver=resolver,
            historical_battle_signatures=historical_battle_signatures,
            seen_battle_signatures=seen_battle_signatures,
            ticks_to_date=ticks_to_date,
        )
    )

    return extracted_events, highest_tale_tick, highest_playlog_tick, highest_archive_tick


def build_master_timeline(save_directory: Path, file_pattern: str) -> list[dict[str, object]]:
    save_sources = discover_save_sources(save_directory=save_directory, file_pattern=file_pattern)
    if not save_sources:
        raise FileNotFoundError(
            f"No save sources found in '{save_directory}' for pattern '{file_pattern}'."
        )

    chronological_sources = get_chronological_sources(save_sources)

    master_timeline: list[dict[str, object]] = []
    last_seen_tale_tick = 0
    last_seen_playlog_tick = 0
    last_seen_archive_tick = 0
    seen_message_signatures: set[str] = set()
    seen_battle_signatures: set[str] = set()

    for save_source in chronological_sources:
        save_snapshot = load_save_snapshot(save_source)
        if save_snapshot is None:
            continue

        historical_message_signatures = set(seen_message_signatures)
        historical_battle_signatures = set(seen_battle_signatures)
        resolver = EntityResolver.from_snapshot(save_snapshot)

        (
            new_events,
            last_seen_tale_tick,
            last_seen_playlog_tick,
            last_seen_archive_tick,
        ) = extract_events_for_snapshot(
            save_snapshot=save_snapshot,
            resolver=resolver,
            last_seen_tale_tick=last_seen_tale_tick,
            last_seen_playlog_tick=last_seen_playlog_tick,
            last_seen_archive_tick=last_seen_archive_tick,
            historical_message_signatures=historical_message_signatures,
            seen_message_signatures=seen_message_signatures,
            historical_battle_signatures=historical_battle_signatures,
            seen_battle_signatures=seen_battle_signatures,
        )

        for event_payload in new_events:
            event_payload["source_file"] = str(save_snapshot.source_path)

        master_timeline.extend(new_events)

    master_timeline.sort(key=lambda event_payload: int(event_payload.get("tick", 0)))
    return master_timeline


def write_timeline_json(timeline_events: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(timeline_events, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
