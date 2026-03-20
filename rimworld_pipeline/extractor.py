from __future__ import annotations

from pathlib import Path
from typing import BinaryIO
import fnmatch
import json
import xml.etree.ElementTree as ET
import zipfile

from rimworld_pipeline.resolver import EntityResolver, ResolvedEntityRef
from rimworld_pipeline.sanitizer import sanitize_rimworld_markup
from rimworld_pipeline.snapshots import (
    SaveSnapshot,
    SaveSource,
    WORLD_SAVE_MEMBER_PATH,
    load_map_snapshots,
)


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


def normalize_abs_tick(tick_abs: int, game_start_abs_tick: int) -> int:
    tick_game = tick_abs - game_start_abs_tick
    if tick_game < 0:
        return tick_abs
    return tick_game


def parse_bool_value(xml_element: ET.Element | None) -> bool | None:
    raw_value = clean_text(xml_element)
    if raw_value is None:
        return None
    if raw_value == "True":
        return True
    if raw_value == "False":
        return False
    return None


def parse_body_part_reference(part_element: ET.Element | None) -> dict[str, object] | None:
    if part_element is None:
        return None

    body_definition = clean_text(part_element.find("body"))
    part_index = parse_int_value(part_element.find("index"))
    if body_definition is None and part_index is None:
        return None

    payload: dict[str, object] = {}
    if body_definition is not None:
        payload["body"] = body_definition
    if part_index is not None:
        payload["index"] = part_index
    return payload


def parse_body_part_list(parts_element: ET.Element | None) -> list[dict[str, object]]:
    if parts_element is None:
        return []

    body_parts: list[dict[str, object]] = []
    for part_element in parts_element.findall("li"):
        parsed_part = parse_body_part_reference(part_element)
        if parsed_part is not None:
            body_parts.append(parsed_part)
    return body_parts


def enrich_event_with_resolved_entity(
    event_payload: dict[str, object],
    prefix: str,
    resolved_entity: ResolvedEntityRef,
    display_override: str | None = None,
) -> None:
    display_label = display_override or resolved_entity.display_label or resolved_entity.raw_id
    if display_label is not None:
        event_payload[prefix] = display_label
    if resolved_entity.raw_id is not None:
        event_payload[f"{prefix}_id"] = resolved_entity.raw_id
    if resolved_entity.entity_id is not None:
        event_payload[f"{prefix}_entity_id"] = resolved_entity.entity_id
    if resolved_entity.kind_def is not None:
        event_payload[f"{prefix}_kindDef"] = resolved_entity.kind_def
    if resolved_entity.thing_def is not None:
        event_payload[f"{prefix}_thingDef"] = resolved_entity.thing_def
    if resolved_entity.faction_id is not None:
        event_payload[f"{prefix}_faction_id"] = resolved_entity.faction_id
    if resolved_entity.faction_name is not None:
        event_payload[f"{prefix}_faction"] = resolved_entity.faction_name
    if resolved_entity.role_hint is not None:
        event_payload[f"{prefix}_role"] = resolved_entity.role_hint


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
    game_start_abs_tick: int,
    last_seen_tick_abs: int,
    resolver: EntityResolver,
) -> tuple[list[dict[str, object]], int]:
    """Extracts tale records newer than the dedup boundary."""
    tale_events: list[dict[str, object]] = []
    highest_tale_tick_abs = last_seen_tick_abs

    for tale_element in world_root.findall("./game/taleManager/tales/li"):
        tale_tick_abs = parse_int_value(tale_element.find("date"))
        if tale_tick_abs is None or tale_tick_abs <= last_seen_tick_abs:
            continue

        highest_tale_tick_abs = max(highest_tale_tick_abs, tale_tick_abs)
        tale_tick_game = normalize_abs_tick(tale_tick_abs, game_start_abs_tick)

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

        resolved_pawn = resolver.resolve_reference(tale_pawn_id or raw_tale_id)
        tale_event = {
            "type": "tale",
            "source": "taleManager.tales",
            "tick": tale_tick_game,
            "tickAbs": tale_tick_abs,
            "human_date": ticks_to_date(tale_tick_game),
            "class": tale_element.get("Class"),
            "def": clean_text(tale_element.find("def")),
            "customLabel": clean_text(tale_element.find("customLabel")),
        }
        enrich_event_with_resolved_entity(
            tale_event,
            prefix="pawn",
            resolved_entity=resolved_pawn,
            display_override=tale_pawn_name,
        )
        tale_events.append(tale_event)

    return tale_events, highest_tale_tick_abs


def extract_playlog_interactions(
    world_root: ET.Element,
    game_start_abs_tick: int,
    last_seen_tick_abs: int,
    resolver: EntityResolver,
) -> tuple[list[dict[str, object]], int]:
    """Extracts social interactions newer than the dedup boundary."""
    playlog_events: list[dict[str, object]] = []
    highest_playlog_tick_abs = last_seen_tick_abs

    for playlog_element in world_root.findall("./game/playLog/entries/li"):
        playlog_tick_abs = parse_int_value(playlog_element.find("ticksAbs"))
        if playlog_tick_abs is None or playlog_tick_abs <= last_seen_tick_abs:
            continue

        highest_playlog_tick_abs = max(highest_playlog_tick_abs, playlog_tick_abs)
        playlog_tick_game = normalize_abs_tick(playlog_tick_abs, game_start_abs_tick)

        initiator_id = clean_text(playlog_element.find("initiator"))
        recipient_id = clean_text(playlog_element.find("recipient"))

        playlog_event = {
            "type": "playlog_interaction",
            "source": "playLog.entries",
            "tick": playlog_tick_game,
            "tickAbs": playlog_tick_abs,
            "human_date": ticks_to_date(playlog_tick_game),
            "class": playlog_element.get("Class"),
            "interactionDef": clean_text(playlog_element.find("intDef")),
            "logID": clean_text(playlog_element.find("logID")),
        }
        enrich_event_with_resolved_entity(
            playlog_event,
            prefix="initiator",
            resolved_entity=resolver.resolve_reference(initiator_id),
        )
        enrich_event_with_resolved_entity(
            playlog_event,
            prefix="recipient",
            resolved_entity=resolver.resolve_reference(recipient_id),
        )
        playlog_events.append(playlog_event)

    return playlog_events, highest_playlog_tick_abs


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


def build_battle_entry_signature(
    battle_id: str | None,
    battle_entry: ET.Element,
) -> str:
    signature_parts = [
        battle_id or "",
        battle_entry.get("Class") or "",
        clean_text(battle_entry.find("logID")) or "",
        clean_text(battle_entry.find("ticksAbs")) or "",
        clean_text(battle_entry.find("subjectPawn")) or "",
        clean_text(battle_entry.find("initiator")) or clean_text(battle_entry.find("initiatorPawn")) or "",
        clean_text(battle_entry.find("recipientPawn")) or "",
    ]
    return "|".join(signature_parts)


def build_base_battle_event(
    battle_entry: ET.Element,
    battle_id: str | None,
    battle_tick_abs: int,
    battle_tick_game: int,
) -> dict[str, object]:
    return {
        "source": "battleLog.battles",
        "class": battle_entry.get("Class"),
        "battle_id": battle_id,
        "logID": clean_text(battle_entry.find("logID")),
        "tick": battle_tick_game,
        "tickAbs": battle_tick_abs,
        "human_date": ticks_to_date(battle_tick_game),
    }


def extract_battle_log_events(
    save_snapshot: SaveSnapshot,
    resolver: EntityResolver,
    historical_battle_signatures: set[str],
    seen_battle_signatures: set[str],
) -> list[dict[str, object]]:
    battle_events: list[dict[str, object]] = []

    for battle_element in save_snapshot.world_root.findall("./game/battleLog/battles/li"):
        battle_id = clean_text(battle_element.find("loadID"))

        for battle_entry in battle_element.findall("./entries/li"):
            entry_class = battle_entry.get("Class")
            if entry_class not in {
                "BattleLogEntry_StateTransition",
                "BattleLogEntry_MeleeCombat",
                "BattleLogEntry_RangedImpact",
                "BattleLogEntry_Event",
            }:
                continue

            battle_signature = build_battle_entry_signature(battle_id, battle_entry)
            if battle_signature in historical_battle_signatures or battle_signature in seen_battle_signatures:
                continue
            seen_battle_signatures.add(battle_signature)

            battle_tick_abs = parse_int_value(battle_entry.find("ticksAbs"))
            if battle_tick_abs is None:
                continue

            battle_tick_game = normalize_abs_tick(
                battle_tick_abs,
                save_snapshot.game_start_abs_tick,
            )
            event_payload = build_base_battle_event(
                battle_entry=battle_entry,
                battle_id=battle_id,
                battle_tick_abs=battle_tick_abs,
                battle_tick_game=battle_tick_game,
            )

            if entry_class == "BattleLogEntry_StateTransition":
                event_payload["type"] = "battle_state_transition"
                event_payload["transitionDef"] = clean_text(battle_entry.find("transitionDef"))
                event_payload["culpritHediffDef"] = clean_text(battle_entry.find("culpritHediffDef"))
                culprit_target_part = parse_body_part_reference(battle_entry.find("culpritTargetPart"))
                if culprit_target_part is not None:
                    event_payload["culpritTargetPart"] = culprit_target_part
                culprit_hediff_target_part = parse_body_part_reference(
                    battle_entry.find("culpritHediffTargetPart")
                )
                if culprit_hediff_target_part is not None:
                    event_payload["culpritHediffTargetPart"] = culprit_hediff_target_part
                enrich_event_with_resolved_entity(
                    event_payload,
                    prefix="subject",
                    resolved_entity=resolver.resolve_reference(clean_text(battle_entry.find("subjectPawn"))),
                )
                enrich_event_with_resolved_entity(
                    event_payload,
                    prefix="initiator",
                    resolved_entity=resolver.resolve_reference(clean_text(battle_entry.find("initiator"))),
                )
                battle_events.append(event_payload)
                continue

            if entry_class == "BattleLogEntry_MeleeCombat":
                event_payload["type"] = "battle_melee"
                event_payload["combatDef"] = clean_text(battle_entry.find("def"))
                event_payload["ruleDef"] = clean_text(battle_entry.find("ruleDef"))
                event_payload["implementType"] = clean_text(battle_entry.find("implementType"))
                event_payload["toolLabel"] = clean_text(battle_entry.find("toolLabel"))
                event_payload["ownerDef"] = clean_text(battle_entry.find("ownerDef"))
                deflected = parse_bool_value(battle_entry.find("deflected"))
                if deflected is not None:
                    event_payload["deflected"] = deflected
                always_show = parse_bool_value(battle_entry.find("alwaysShowInCompact"))
                if always_show is not None:
                    event_payload["alwaysShowInCompact"] = always_show
                damaged_parts = parse_body_part_list(battle_entry.find("damagedParts"))
                if damaged_parts:
                    event_payload["damagedParts"] = damaged_parts
                destroyed_parts = parse_body_part_list(battle_entry.find("damagedPartsDestroyed"))
                if destroyed_parts:
                    event_payload["damagedPartsDestroyed"] = destroyed_parts
                enrich_event_with_resolved_entity(
                    event_payload,
                    prefix="initiator",
                    resolved_entity=resolver.resolve_reference(clean_text(battle_entry.find("initiator"))),
                )
                enrich_event_with_resolved_entity(
                    event_payload,
                    prefix="recipient",
                    resolved_entity=resolver.resolve_reference(clean_text(battle_entry.find("recipientPawn"))),
                )
                recipient_thing = clean_text(battle_entry.find("recipientThing"))
                if recipient_thing is not None:
                    event_payload["recipientThing"] = recipient_thing
                battle_events.append(event_payload)
                continue

            if entry_class == "BattleLogEntry_RangedImpact":
                event_payload["type"] = "battle_ranged_impact"
                event_payload["weaponDef"] = clean_text(battle_entry.find("weaponDef"))
                event_payload["projectileDef"] = clean_text(battle_entry.find("projectileDef"))
                event_payload["coverDef"] = clean_text(battle_entry.find("coverDef"))
                original_target_mobile = parse_bool_value(battle_entry.find("originalTargetMobile"))
                if original_target_mobile is not None:
                    event_payload["originalTargetMobile"] = original_target_mobile
                damaged_parts = parse_body_part_list(battle_entry.find("damagedParts"))
                if damaged_parts:
                    event_payload["damagedParts"] = damaged_parts
                destroyed_parts = parse_body_part_list(battle_entry.find("damagedPartsDestroyed"))
                if destroyed_parts:
                    event_payload["damagedPartsDestroyed"] = destroyed_parts
                enrich_event_with_resolved_entity(
                    event_payload,
                    prefix="initiator",
                    resolved_entity=resolver.resolve_reference(clean_text(battle_entry.find("initiatorPawn"))),
                )
                enrich_event_with_resolved_entity(
                    event_payload,
                    prefix="recipient",
                    resolved_entity=resolver.resolve_reference(clean_text(battle_entry.find("recipientPawn"))),
                )
                enrich_event_with_resolved_entity(
                    event_payload,
                    prefix="originalTarget",
                    resolved_entity=resolver.resolve_reference(clean_text(battle_entry.find("originalTargetPawn"))),
                )
                recipient_thing = clean_text(battle_entry.find("recipientThing"))
                if recipient_thing is not None:
                    event_payload["recipientThing"] = recipient_thing
                original_target_thing = clean_text(battle_entry.find("originalTargetThing"))
                if original_target_thing is not None:
                    event_payload["originalTargetThing"] = original_target_thing
                battle_events.append(event_payload)
                continue

            if entry_class == "BattleLogEntry_Event":
                event_payload["type"] = "battle_event"
                event_payload["eventDef"] = clean_text(battle_entry.find("eventDef"))
                enrich_event_with_resolved_entity(
                    event_payload,
                    prefix="subject",
                    resolved_entity=resolver.resolve_reference(clean_text(battle_entry.find("subjectPawn"))),
                )
                enrich_event_with_resolved_entity(
                    event_payload,
                    prefix="initiator",
                    resolved_entity=resolver.resolve_reference(clean_text(battle_entry.find("initiatorPawn"))),
                )
                battle_events.append(event_payload)

    return battle_events


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
    """Builds one save's event slice and advances the global dedup boundary."""
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
    )
    extracted_events.extend(tale_events)

    playlog_events, highest_playlog_tick = extract_playlog_interactions(
        world_root=world_root,
        game_start_abs_tick=save_snapshot.game_start_abs_tick,
        last_seen_tick_abs=last_seen_playlog_tick,
        resolver=resolver,
    )
    extracted_events.extend(playlog_events)

    archive_events, highest_archive_tick = extract_archive_messages(
        world_root=world_root,
        ticks_game=save_snapshot.ticks_game,
        last_seen_archive_tick=last_seen_archive_tick,
        historical_message_signatures=historical_message_signatures,
        seen_message_signatures=seen_message_signatures,
    )
    extracted_events.extend(archive_events)

    extracted_events.extend(
        extract_battle_log_events(
            save_snapshot=save_snapshot,
            resolver=resolver,
            historical_battle_signatures=historical_battle_signatures,
            seen_battle_signatures=seen_battle_signatures,
        )
    )

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
