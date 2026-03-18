from __future__ import annotations

import argparse
import fnmatch
import json
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET
import zipfile


WORLD_SAVE_MEMBER = "world/000_save"


@dataclass(frozen=True)
class SaveSource:
    source_type: str
    path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract RimWorld timeline events from multiplayer backup saves."
    )
    parser.add_argument(
        "--dir",
        default=os.environ.get("RW_SAVE_DIR"),
        help="Directory containing backup zip files. Defaults to RW_SAVE_DIR.",
    )
    parser.add_argument(
        "--pattern",
        default=os.environ.get("RW_FILE_PATTERN", "*.zip"),
        help="Filename pattern to match backup files. Defaults to RW_FILE_PATTERN or *.zip.",
    )
    parser.add_argument(
        "--output",
        default="rimworld_timeline.json",
        help="Output JSON file path. Defaults to rimworld_timeline.json.",
    )
    return parser.parse_args()


def clean_text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    stripped_text = element.text.strip()
    return stripped_text if stripped_text else None


def parse_int_value(element: ET.Element | None) -> int | None:
    cleaned_text = clean_text(element)
    if cleaned_text is None:
        return None
    try:
        return int(cleaned_text)
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


def translate_id(raw_id: str | None, pawn_dictionary: dict[str, str]) -> str | None:
    if raw_id is None:
        return None
    return pawn_dictionary.get(raw_id, raw_id)


def ticks_to_date(ticks: int) -> str:
    ticks_per_day = 60000
    ticks_per_year = 3600000
    days_per_quadrum = 15

    year_index = ticks // ticks_per_year
    day_within_year = (ticks % ticks_per_year) // ticks_per_day
    quadrum_index = day_within_year // days_per_quadrum
    day_within_quadrum = day_within_year % days_per_quadrum

    quadrum_names = ["Aprimay", "Jugust", "Septober", "Decembary"]
    quadrum_name = quadrum_names[quadrum_index] if quadrum_index < 4 else f"Quadrum {quadrum_index + 1}"

    return f"Year {year_index + 1}, {quadrum_name}, Day {day_within_quadrum + 1}"


def discover_sources(target_directory: Path, filename_pattern: str) -> list[SaveSource]:
    zip_sources = [
        SaveSource(source_type="zip", path=file_path)
        for file_path in sorted(target_directory.iterdir())
        if file_path.is_file()
        and file_path.suffix.lower() == ".zip"
        and fnmatch.fnmatch(file_path.name, filename_pattern)
    ]
    if zip_sources:
        return zip_sources

    raw_world_save = target_directory / WORLD_SAVE_MEMBER
    if raw_world_save.is_file():
        return [SaveSource(source_type="raw", path=raw_world_save)]

    return []


def extract_master_ticks_from_stream(xml_stream: BytesIO | Iterable[bytes] | object) -> int:
    # Stopping early once game/tickManager/ticksGame is seen to avoid full XML parse.
    active_path_stack: list[str] = []

    for event_name, element in ET.iterparse(xml_stream, events=("start", "end")):
        if event_name == "start":
            active_path_stack.append(element.tag)
            continue

        if event_name == "end" and active_path_stack == ["savegame", "game", "tickManager", "ticksGame"]:
            master_ticks = parse_int_value(element)
            if master_ticks is None:
                raise ValueError("Missing or invalid game/tickManager/ticksGame value.")
            return master_ticks

        if active_path_stack:
            active_path_stack.pop()

    raise ValueError("Unable to find game/tickManager/ticksGame in XML stream.")


def read_source_ticks(source: SaveSource) -> int:
    if source.source_type == "zip":
        with zipfile.ZipFile(source.path, "r") as archive:
            with archive.open(WORLD_SAVE_MEMBER, "r") as world_stream:
                return extract_master_ticks_from_stream(world_stream)

    with source.path.open("rb") as world_stream:
        return extract_master_ticks_from_stream(world_stream)


def get_chronological_order(sources: list[SaveSource]) -> list[SaveSource]:
    source_tick_pairs: list[tuple[SaveSource, int]] = []
    for source in sources:
        source_tick_pairs.append((source, read_source_ticks(source)))

    source_tick_pairs.sort(key=lambda pair: pair[1])
    return [source for source, _ in source_tick_pairs]


def parse_world_root(source: SaveSource) -> ET.Element:
    if source.source_type == "zip":
        with zipfile.ZipFile(source.path, "r") as archive:
            with archive.open(WORLD_SAVE_MEMBER, "r") as world_stream:
                return ET.parse(world_stream).getroot()

    return ET.parse(source.path).getroot()


def map_member_paths(archive: zipfile.ZipFile) -> list[str]:
    return [
        member_name
        for member_name in archive.namelist()
        if member_name.startswith("maps/")
        and member_name.endswith("_save")
        and not member_name.endswith("000_save")
    ]


def parse_map_roots(source: SaveSource) -> list[ET.Element]:
    if source.source_type != "zip":
        return []

    map_roots: list[ET.Element] = []
    with zipfile.ZipFile(source.path, "r") as archive:
        for map_member_path in map_member_paths(archive):
            with archive.open(map_member_path, "r") as map_stream:
                map_roots.append(ET.parse(map_stream).getroot())
    return map_roots


def update_pawn_dictionary_from_world(xml_root: ET.Element, pawn_dictionary: dict[str, str]) -> None:
    pawn_collections = [
        "./game/world/worldPawns/pawnsAlive/li",
        "./game/world/worldPawns/pawnsDead/li",
    ]

    for pawn_path in pawn_collections:
        for pawn_element in xml_root.findall(pawn_path):
            pawn_id = clean_text(pawn_element.find("id"))
            pawn_name = build_name_from_name_triple(pawn_element.find("name"))
            if pawn_id and pawn_name:
                pawn_dictionary[pawn_id] = pawn_name

    for tale_pawn_data in xml_root.findall("./game/taleManager/tales/li/pawnData"):
        tale_pawn_id = clean_text(tale_pawn_data.find("pawn"))
        tale_pawn_name = build_name_from_name_triple(tale_pawn_data.find("name"))
        if tale_pawn_id and tale_pawn_name:
            pawn_dictionary[tale_pawn_id] = tale_pawn_name


def update_pawn_dictionary_from_map(map_root: ET.Element, pawn_dictionary: dict[str, str]) -> None:
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
                pawn_dictionary[pawn_id] = pawn_name


def extract_snapshot_event(xml_root: ET.Element, ticks_game: int) -> dict[str, object] | None:
    stats_record = xml_root.find("./game/storyWatcher/statsRecord")
    if stats_record is None:
        return None

    snapshot_metrics: dict[str, int] = {}
    for metric_tag in ["numRaidsEnemy", "numThreatsQueued", "greatestPopulation"]:
        metric_value = parse_int_value(stats_record.find(metric_tag))
        if metric_value is not None:
            snapshot_metrics[metric_tag] = metric_value

    return {
        "type": "snapshot",
        "source": "storyWatcher.statsRecord",
        "tick": ticks_game,
        "human_date": ticks_to_date(ticks_game),
        "stats": snapshot_metrics,
    }


def extract_tales(
    xml_root: ET.Element,
    last_seen_tick: int,
    pawn_dictionary: dict[str, str],
) -> tuple[list[dict[str, object]], int]:
    extracted_tales: list[dict[str, object]] = []
    highest_tale_tick = last_seen_tick

    for tale_element in xml_root.findall("./game/taleManager/tales/li"):
        tale_tick = parse_int_value(tale_element.find("date"))
        if tale_tick is None or tale_tick <= last_seen_tick:
            continue

        highest_tale_tick = max(highest_tale_tick, tale_tick)
        raw_tale_id = clean_text(tale_element.find("id"))

        pawn_data_element = tale_element.find("pawnData")
        pawn_data_id = clean_text(pawn_data_element.find("pawn")) if pawn_data_element is not None else None
        pawn_data_name = (
            build_name_from_name_triple(pawn_data_element.find("name"))
            if pawn_data_element is not None
            else None
        )
        translated_tale_id = (
            pawn_data_name
            or translate_id(pawn_data_id, pawn_dictionary)
            or translate_id(raw_tale_id, pawn_dictionary)
        )

        extracted_tales.append(
            {
                "type": "tale",
                "source": "taleManager.tales",
                "tick": tale_tick,
                "human_date": ticks_to_date(tale_tick),
                "class": tale_element.get("Class"),
                "def": clean_text(tale_element.find("def")),
                "customLabel": clean_text(tale_element.find("customLabel")),
                "pawn": translated_tale_id,
                "pawn_id": pawn_data_id or raw_tale_id,
            }
        )

    return extracted_tales, highest_tale_tick


def extract_playlog_entries(
    xml_root: ET.Element,
    last_seen_tick: int,
    pawn_dictionary: dict[str, str],
) -> tuple[list[dict[str, object]], int]:
    extracted_playlogs: list[dict[str, object]] = []
    highest_playlog_tick = last_seen_tick

    for entry_element in xml_root.findall("./game/playLog/entries/li"):
        entry_tick = parse_int_value(entry_element.find("ticksAbs"))
        if entry_tick is None or entry_tick <= last_seen_tick:
            continue

        highest_playlog_tick = max(highest_playlog_tick, entry_tick)

        raw_initiator = clean_text(entry_element.find("initiator"))
        raw_recipient = clean_text(entry_element.find("recipient"))

        extracted_playlogs.append(
            {
                "type": "playlog_interaction",
                "source": "playLog.entries",
                "tick": entry_tick,
                "human_date": ticks_to_date(entry_tick),
                "class": entry_element.get("Class"),
                "interactionDef": clean_text(entry_element.find("intDef")),
                "logID": clean_text(entry_element.find("logID")),
                "initiator": translate_id(raw_initiator, pawn_dictionary),
                "recipient": translate_id(raw_recipient, pawn_dictionary),
                "initiator_id": raw_initiator,
                "recipient_id": raw_recipient,
            }
        )

    return extracted_playlogs, highest_playlog_tick


def extract_events(
    xml_root: ET.Element,
    ticks_game: int,
    last_seen_tick: int,
    pawn_dictionary: dict[str, str],
) -> tuple[list[dict[str, object]], int]:
    new_events: list[dict[str, object]] = []

    snapshot_event = extract_snapshot_event(xml_root, ticks_game)
    if snapshot_event is not None:
        new_events.append(snapshot_event)

    tales, highest_tale_tick = extract_tales(xml_root, last_seen_tick, pawn_dictionary)
    playlogs, highest_playlog_tick = extract_playlog_entries(
        xml_root, last_seen_tick, pawn_dictionary
    )

    new_events.extend(tales)
    new_events.extend(playlogs)

    return new_events, max(last_seen_tick, highest_tale_tick, highest_playlog_tick)


def run_extraction(target_directory: Path, filename_pattern: str) -> list[dict[str, object]]:
    source_files = discover_sources(target_directory, filename_pattern)
    if not source_files:
        raise FileNotFoundError(
            f"No save sources found in '{target_directory}' for pattern '{filename_pattern}'."
        )

    ordered_sources = get_chronological_order(source_files)

    master_timeline: list[dict[str, object]] = []
    pawn_dictionary: dict[str, str] = {}
    last_seen_tick = 0

    for source in ordered_sources:
        world_root = parse_world_root(source)
        ticks_game = parse_int_value(world_root.find("./game/tickManager/ticksGame"))
        if ticks_game is None:
            continue

        update_pawn_dictionary_from_world(world_root, pawn_dictionary)

        for map_root in parse_map_roots(source):
            update_pawn_dictionary_from_map(map_root, pawn_dictionary)

        new_events, last_seen_tick = extract_events(
            xml_root=world_root,
            ticks_game=ticks_game,
            last_seen_tick=last_seen_tick,
            pawn_dictionary=pawn_dictionary,
        )

        for event in new_events:
            event["source_file"] = str(source.path)

        master_timeline.extend(new_events)

    master_timeline.sort(key=lambda event: int(event.get("tick", 0)))
    return master_timeline


def main() -> None:
    args = parse_args()

    if not args.dir:
        raise ValueError("--dir was not provided and RW_SAVE_DIR is not set.")

    target_directory = Path(args.dir).expanduser().resolve()
    timeline = run_extraction(target_directory, args.pattern)

    output_path = Path(args.output).expanduser().resolve()
    output_path.write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Extracted {len(timeline)} events to {output_path}")


if __name__ == "__main__":
    main()
