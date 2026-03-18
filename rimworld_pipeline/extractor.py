from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
import fnmatch
import json
import xml.etree.ElementTree as ET
import zipfile

from rimworld_pipeline.sanitizer import sanitize_rimworld_markup


WORLD_SAVE_MEMBER_PATH = "world/000_save"


@dataclass(frozen=True)
class SaveSource:
    source_type: str
    path: Path


def clean_text(xml_element: ET.Element | None) -> str | None:
    if xml_element is None or xml_element.text is None:
        return None

    normalized_text = xml_element.text.strip()
    return normalized_text if normalized_text else None


def parse_int_value(xml_element: ET.Element | None) -> int | None:
    raw_value = clean_text(xml_element)
    if raw_value is None:
        return None

    try:
        return int(raw_value)
    except ValueError:
        return None


def build_name_from_name_triple(name_element: ET.Element | None) -> str | None:
    if name_element is None:
        return None

    nick_name = clean_text(name_element.find("nick"))
    first_name = clean_text(name_element.find("first"))
    last_name = clean_text(name_element.find("last"))

    if nick_name:
        return nick_name
    if first_name and last_name:
        return f"{first_name} {last_name}"
    return first_name or last_name


def translate_pawn_id(raw_pawn_id: str | None, pawn_id_to_name: dict[str, str]) -> str | None:
    if raw_pawn_id is None:
        return None
    return pawn_id_to_name.get(raw_pawn_id, raw_pawn_id)


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
    """Reads only ticksGame so archives can be sorted without full XML parsing."""
    # Stopping the pre-pass parser early is reducing IO and memory churn on large saves.
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
    """Sorts sources by in-game time instead of filesystem metadata."""
    save_source_and_tick_pairs = [
        (save_source, read_source_ticks(save_source)) for save_source in save_sources
    ]
    save_source_and_tick_pairs.sort(key=lambda source_and_tick: source_and_tick[1])
    return [save_source for save_source, _ in save_source_and_tick_pairs]


def parse_world_root(save_source: SaveSource) -> ET.Element:
    if save_source.source_type == "zip":
        with zipfile.ZipFile(save_source.path, "r") as archive_file:
            with archive_file.open(WORLD_SAVE_MEMBER_PATH, "r") as world_xml_stream:
                return ET.parse(world_xml_stream).getroot()

    return ET.parse(save_source.path).getroot()


def map_save_member_paths(archive_file: zipfile.ZipFile) -> list[str]:
    return [
        archive_member_name
        for archive_member_name in archive_file.namelist()
        if archive_member_name.startswith("maps/")
        and archive_member_name.endswith("_save")
        and archive_member_name != "maps/000_save"
    ]


def parse_map_roots(save_source: SaveSource) -> list[ET.Element]:
    if save_source.source_type != "zip":
        return []

    map_roots: list[ET.Element] = []
    with zipfile.ZipFile(save_source.path, "r") as archive_file:
        for map_member_path in map_save_member_paths(archive_file):
            with archive_file.open(map_member_path, "r") as map_xml_stream:
                map_roots.append(ET.parse(map_xml_stream).getroot())

    return map_roots


def update_pawn_dictionary_from_world(
    world_root: ET.Element, pawn_id_to_name: dict[str, str]
) -> None:
    """Refreshes pawn name mappings so later event translation stays current after renames."""
    world_pawn_paths = [
        "./game/world/worldPawns/pawnsAlive/li",
        "./game/world/worldPawns/pawnsDead/li",
    ]

    for world_pawn_path in world_pawn_paths:
        for pawn_element in world_root.findall(world_pawn_path):
            pawn_id = clean_text(pawn_element.find("id"))
            pawn_name = build_name_from_name_triple(pawn_element.find("name"))
            if pawn_id and pawn_name:
                pawn_id_to_name[pawn_id] = pawn_name

    # Reading tale pawnData is catching names that might not exist under worldPawns yet.
    for tale_pawn_data_element in world_root.findall("./game/taleManager/tales/li/pawnData"):
        pawn_id = clean_text(tale_pawn_data_element.find("pawn"))
        pawn_name = build_name_from_name_triple(tale_pawn_data_element.find("name"))
        if pawn_id and pawn_name:
            pawn_id_to_name[pawn_id] = pawn_name


def update_pawn_dictionary_from_map(
    map_root: ET.Element, pawn_id_to_name: dict[str, str]
) -> None:
    map_pawn_paths = [
        "./mapPawns/AllPawnsSpawned/li",
        "./mapPawns/AllPawnsUnspawned/li",
        "./mapPawns/FreeColonistsSpawned/li",
        "./mapPawns/PrisonersOfColonySpawned/li",
    ]

    for map_pawn_path in map_pawn_paths:
        for pawn_element in map_root.findall(map_pawn_path):
            pawn_id = clean_text(pawn_element.find("id"))
            pawn_name = build_name_from_name_triple(pawn_element.find("name"))
            if pawn_id and pawn_name:
                pawn_id_to_name[pawn_id] = pawn_name


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


def extract_tale_events(
    world_root: ET.Element,
    last_seen_tick: int,
    pawn_id_to_name: dict[str, str],
) -> tuple[list[dict[str, object]], int]:
    """Extracts tale records newer than the dedup boundary."""
    tale_events: list[dict[str, object]] = []
    highest_tale_tick = last_seen_tick

    for tale_element in world_root.findall("./game/taleManager/tales/li"):
        tale_tick = parse_int_value(tale_element.find("date"))
        if tale_tick is None or tale_tick <= last_seen_tick:
            continue

        highest_tale_tick = max(highest_tale_tick, tale_tick)

        raw_tale_id = clean_text(tale_element.find("id"))
        pawn_data_element = tale_element.find("pawnData")
        tale_pawn_id = (
            clean_text(pawn_data_element.find("pawn"))
            if pawn_data_element is not None
            else None
        )
        tale_pawn_name = (
            build_name_from_name_triple(pawn_data_element.find("name"))
            if pawn_data_element is not None
            else None
        )

        resolved_pawn_name_or_id = (
            tale_pawn_name
            or translate_pawn_id(tale_pawn_id, pawn_id_to_name)
            or translate_pawn_id(raw_tale_id, pawn_id_to_name)
        )

        tale_events.append(
            {
                "type": "tale",
                "source": "taleManager.tales",
                "tick": tale_tick,
                "human_date": ticks_to_date(tale_tick),
                "class": tale_element.get("Class"),
                "def": clean_text(tale_element.find("def")),
                "customLabel": clean_text(tale_element.find("customLabel")),
                "pawn": resolved_pawn_name_or_id,
                "pawn_id": tale_pawn_id or raw_tale_id,
            }
        )

    return tale_events, highest_tale_tick


def extract_playlog_interactions(
    world_root: ET.Element,
    last_seen_tick: int,
    pawn_id_to_name: dict[str, str],
) -> tuple[list[dict[str, object]], int]:
    """Extracts social interactions newer than the dedup boundary."""
    playlog_events: list[dict[str, object]] = []
    highest_playlog_tick = last_seen_tick

    for playlog_element in world_root.findall("./game/playLog/entries/li"):
        playlog_tick = parse_int_value(playlog_element.find("ticksAbs"))
        if playlog_tick is None or playlog_tick <= last_seen_tick:
            continue

        highest_playlog_tick = max(highest_playlog_tick, playlog_tick)

        initiator_id = clean_text(playlog_element.find("initiator"))
        recipient_id = clean_text(playlog_element.find("recipient"))

        playlog_events.append(
            {
                "type": "playlog_interaction",
                "source": "playLog.entries",
                "tick": playlog_tick,
                "human_date": ticks_to_date(playlog_tick),
                "class": playlog_element.get("Class"),
                "interactionDef": clean_text(playlog_element.find("intDef")),
                "logID": clean_text(playlog_element.find("logID")),
                "initiator": translate_pawn_id(initiator_id, pawn_id_to_name),
                "recipient": translate_pawn_id(recipient_id, pawn_id_to_name),
                "initiator_id": initiator_id,
                "recipient_id": recipient_id,
            }
        )

    return playlog_events, highest_playlog_tick


def extract_archive_messages(
    world_root: ET.Element,
    ticks_game: int,
    last_seen_archive_tick: int,
    historical_message_signatures: set[str],
    seen_message_signatures: set[str],
) -> tuple[list[dict[str, object]], int]:
    """Extracts archived letters/messages and applies the same global dedup gate."""
    archive_events: list[dict[str, object]] = []
    highest_archive_tick = last_seen_archive_tick

    for archive_item_element in world_root.findall("./game/history/archive/archivables/li"):
        archive_class = archive_item_element.get("Class") or ""
        archive_label = sanitize_rimworld_markup(clean_text(archive_item_element.find("label")))
        archive_text = sanitize_rimworld_markup(clean_text(archive_item_element.find("text")))
        arrival_tick = parse_int_value(archive_item_element.find("arrivalTick"))

        if arrival_tick is None:
            # Deduplicating no-timestamp message rows by content is preventing repeated UI spam
            # while still allowing chronological placement in the output timeline.
            message_signature = f"{archive_class}_{archive_label or ''}_{archive_text or ''}"
            if message_signature in historical_message_signatures:
                continue
            seen_message_signatures.add(message_signature)
            resolved_tick = ticks_game
        else:
            resolved_tick = arrival_tick
            if resolved_tick <= last_seen_archive_tick:
                continue

        highest_archive_tick = max(highest_archive_tick, resolved_tick)
        archive_events.append(
            {
                "type": "archive_message",
                "source": "history.archive.archivables",
                "tick": resolved_tick,
                "human_date": ticks_to_date(resolved_tick),
                "class": archive_class,
                "label": archive_label,
                "text": archive_text,
            }
        )

    return archive_events, highest_archive_tick


def extract_events_for_world_save(
    world_root: ET.Element,
    ticks_game: int,
    last_seen_tale_tick: int,
    last_seen_playlog_tick: int,
    last_seen_archive_tick: int,
    historical_message_signatures: set[str],
    seen_message_signatures: set[str],
    pawn_id_to_name: dict[str, str],
) -> tuple[list[dict[str, object]], int, int, int]:
    """Builds one save's event slice and advances the global dedup boundary."""
    extracted_events: list[dict[str, object]] = []

    snapshot_event = extract_snapshot_event(world_root, ticks_game)
    if snapshot_event is not None:
        extracted_events.append(snapshot_event)

    tale_events, highest_tale_tick = extract_tale_events(
        world_root=world_root,
        last_seen_tick=last_seen_tale_tick,
        pawn_id_to_name=pawn_id_to_name,
    )
    extracted_events.extend(tale_events)

    playlog_events, highest_playlog_tick = extract_playlog_interactions(
        world_root=world_root,
        last_seen_tick=last_seen_playlog_tick,
        pawn_id_to_name=pawn_id_to_name,
    )
    extracted_events.extend(playlog_events)

    archive_events, highest_archive_tick = extract_archive_messages(
        world_root=world_root,
        ticks_game=ticks_game,
        last_seen_archive_tick=last_seen_archive_tick,
        historical_message_signatures=historical_message_signatures,
        seen_message_signatures=seen_message_signatures,
    )
    extracted_events.extend(archive_events)

    return extracted_events, highest_tale_tick, highest_playlog_tick, highest_archive_tick


def build_master_timeline(save_directory: Path, file_pattern: str) -> list[dict[str, object]]:
    """Builds one merged chronology across all matching save sources."""
    save_sources = discover_save_sources(save_directory=save_directory, file_pattern=file_pattern)
    if not save_sources:
        raise FileNotFoundError(
            f"No save sources found in '{save_directory}' for pattern '{file_pattern}'."
        )

    chronological_sources = get_chronological_sources(save_sources)

    master_timeline: list[dict[str, object]] = []
    pawn_id_to_name: dict[str, str] = {}
    last_seen_tale_tick = 0
    last_seen_playlog_tick = 0
    last_seen_archive_tick = 0
    seen_message_signatures: set[str] = set()

    for save_source in chronological_sources:
        world_root = parse_world_root(save_source)
        ticks_game = parse_int_value(world_root.find("./game/tickManager/ticksGame"))
        if ticks_game is None:
            continue

        historical_message_signatures = set(seen_message_signatures)

        update_pawn_dictionary_from_world(world_root, pawn_id_to_name)

        # Merging map pawns is improving name resolution for world-level references.
        for map_root in parse_map_roots(save_source):
            update_pawn_dictionary_from_map(map_root, pawn_id_to_name)

        (
            new_events,
            last_seen_tale_tick,
            last_seen_playlog_tick,
            last_seen_archive_tick,
        ) = extract_events_for_world_save(
            world_root=world_root,
            ticks_game=ticks_game,
            last_seen_tale_tick=last_seen_tale_tick,
            last_seen_playlog_tick=last_seen_playlog_tick,
            last_seen_archive_tick=last_seen_archive_tick,
            historical_message_signatures=historical_message_signatures,
            seen_message_signatures=seen_message_signatures,
            pawn_id_to_name=pawn_id_to_name,
        )

        for event_payload in new_events:
            event_payload["source_file"] = str(save_source.path)

        master_timeline.extend(new_events)

    master_timeline.sort(key=lambda event_payload: int(event_payload.get("tick", 0)))
    return master_timeline


def write_timeline_json(timeline_events: list[dict[str, object]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(timeline_events, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
