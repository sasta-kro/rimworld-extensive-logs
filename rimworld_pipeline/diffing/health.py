from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

from rimworld_pipeline.diffing.common import (
    DiffContext,
    HEDIFF_SEVERITY_DELTA_THRESHOLD,
    build_inferred_event_metadata,
    resolve_entity_for_diff,
)
from rimworld_pipeline.extractors.common import clean_text, parse_body_part_reference
from rimworld_pipeline.extractors.helpers import enrich_event_with_resolved_entity
from rimworld_pipeline.snapshots import SaveSnapshot


SUPPRESSED_HEDIFF_DEFS = {"MissingBodyPart"}
MAP_LOCAL_PAWN_PATH = "./things/thing/innerContainer/innerList/li"


@dataclass(frozen=True)
class HediffState:
    key: str
    hediff_def: str | None
    severity: float | None
    part: dict[str, object] | None
    combat_log_entry: str | None


@dataclass(frozen=True)
class PawnHealthState:
    pawn_id: str
    is_dead: bool
    hediffs: dict[str, HediffState]


def parse_float_value(raw_value: str | None) -> float | None:
    normalized_value = normalize_optional_value(raw_value)
    if normalized_value is None:
        return None
    try:
        return float(normalized_value)
    except ValueError:
        return None


def normalize_optional_value(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    normalized_value = raw_value.strip()
    if not normalized_value or normalized_value.lower() in {"null", "none"}:
        return None
    return normalized_value


def should_emit_hediff_event(hediff_def: str | None) -> bool:
    normalized_def = normalize_optional_value(hediff_def)
    if normalized_def is None:
        return True
    return normalized_def not in SUPPRESSED_HEDIFF_DEFS


def is_map_local_pawn_element(candidate_element: ET.Element) -> bool:
    return candidate_element.find("id") is not None and candidate_element.find("healthTracker") is not None


def extract_pawn_state_from_element(pawn_element: ET.Element, is_dead: bool) -> PawnHealthState | None:
    raw_id = clean_text(pawn_element.find("id"))
    if raw_id is None:
        return None

    pawn_id = raw_id if raw_id.startswith("Thing_") else f"Thing_{raw_id}"
    hediffs: dict[str, HediffState] = {}
    for hediff_element in pawn_element.findall("./healthTracker/hediffSet/hediffs/li"):
        hediff_state = HediffState(
            key=build_hediff_key(hediff_element),
            hediff_def=clean_text(hediff_element.find("def")),
            severity=parse_float_value(clean_text(hediff_element.find("severity"))),
            part=parse_body_part_reference(hediff_element.find("part")),
            combat_log_entry=normalize_optional_value(clean_text(hediff_element.find("combatLogEntry"))),
        )
        hediffs[hediff_state.key] = hediff_state
    return PawnHealthState(pawn_id=pawn_id, is_dead=is_dead, hediffs=hediffs)


def merge_health_state(
    pawn_states: dict[str, PawnHealthState],
    candidate_state: PawnHealthState | None,
    prefer_existing: bool,
) -> None:
    if candidate_state is None:
        return
    if prefer_existing and candidate_state.pawn_id in pawn_states:
        return
    pawn_states[candidate_state.pawn_id] = candidate_state


def build_hediff_key(hediff_element: ET.Element) -> str:
    hediff_def = clean_text(hediff_element.find("def")) or "unknown"
    part = parse_body_part_reference(hediff_element.find("part"))
    combat_log_entry = clean_text(hediff_element.find("combatLogEntry"))
    key_parts = [hediff_def]
    if part is not None:
        key_parts.append(str(part.get("body") or ""))
        key_parts.append(str(part.get("index") or ""))
    if combat_log_entry is not None:
        key_parts.append(combat_log_entry)
    return "|".join(key_parts)


def extract_pawn_health_states(save_snapshot: SaveSnapshot) -> dict[str, PawnHealthState]:
    pawn_states: dict[str, PawnHealthState] = {}
    sections = {
        "./game/world/worldPawns/pawnsAlive/li": False,
        "./game/world/worldPawns/pawnsMothballed/li": False,
        "./game/world/worldPawns/pawnsDead/li": True,
    }

    for path, is_dead in sections.items():
        for pawn_element in save_snapshot.world_root.findall(path):
            merge_health_state(
                pawn_states,
                extract_pawn_state_from_element(pawn_element, is_dead=is_dead),
                prefer_existing=False,
            )

    # Map saves in the provided fixtures keep extra pawn state under thing containers rather than mapPawns/*.
    # Use these only as a fallback source so world sections remain authoritative when both exist.
    for map_snapshot in save_snapshot.map_snapshots:
        for pawn_element in map_snapshot.root.findall(MAP_LOCAL_PAWN_PATH):
            if not is_map_local_pawn_element(pawn_element):
                continue
            merge_health_state(
                pawn_states,
                extract_pawn_state_from_element(pawn_element, is_dead=False),
                prefer_existing=True,
            )

    return pawn_states


def build_health_event(
    diff_context: DiffContext,
    subcategory: str,
    pawn_id: str,
    ticks_to_date: callable,
    confidence: str = "medium",
) -> dict[str, object]:
    event_payload = build_inferred_event_metadata(
        diff_context=diff_context,
        event_type="inferred_health_event",
        subcategory=subcategory,
        confidence=confidence,
    )
    event_payload["human_date"] = ticks_to_date(diff_context.current_snapshot.ticks_game)
    enrich_event_with_resolved_entity(
        event_payload,
        prefix="pawn",
        resolved_entity=resolve_entity_for_diff(diff_context, pawn_id),
    )
    return event_payload


def diff_health_states(diff_context: DiffContext, ticks_to_date: callable) -> list[dict[str, object]]:
    previous_states = extract_pawn_health_states(diff_context.previous_snapshot)
    current_states = extract_pawn_health_states(diff_context.current_snapshot)
    inferred_events: list[dict[str, object]] = []

    for pawn_id in sorted(set(previous_states) | set(current_states)):
        previous_state = previous_states.get(pawn_id)
        current_state = current_states.get(pawn_id)

        if previous_state is None or current_state is None:
            continue

        if not previous_state.is_dead and current_state.is_dead:
            event_payload = build_health_event(
                diff_context=diff_context,
                subcategory="pawn_died",
                pawn_id=pawn_id,
                ticks_to_date=ticks_to_date,
                confidence="high",
            )
            inferred_events.append(event_payload)

        previous_hediffs = previous_state.hediffs
        current_hediffs = current_state.hediffs

        for hediff_key in sorted(set(previous_hediffs) | set(current_hediffs)):
            previous_hediff = previous_hediffs.get(hediff_key)
            current_hediff = current_hediffs.get(hediff_key)

            if previous_hediff is None and current_hediff is not None:
                if not should_emit_hediff_event(current_hediff.hediff_def):
                    continue
                event_payload = build_health_event(
                    diff_context=diff_context,
                    subcategory="hediff_started",
                    pawn_id=pawn_id,
                    ticks_to_date=ticks_to_date,
                    confidence="medium",
                )
                event_payload["hediffDef"] = current_hediff.hediff_def
                event_payload["severity_after"] = current_hediff.severity
                if current_hediff.part is not None:
                    event_payload["part"] = current_hediff.part
                if current_hediff.combat_log_entry is not None:
                    event_payload["combatLogEntry"] = current_hediff.combat_log_entry
                inferred_events.append(event_payload)
                continue

            if previous_hediff is not None and current_hediff is None:
                if not should_emit_hediff_event(previous_hediff.hediff_def):
                    continue
                event_payload = build_health_event(
                    diff_context=diff_context,
                    subcategory="hediff_removed",
                    pawn_id=pawn_id,
                    ticks_to_date=ticks_to_date,
                    confidence="medium",
                )
                event_payload["hediffDef"] = previous_hediff.hediff_def
                event_payload["severity_before"] = previous_hediff.severity
                if previous_hediff.part is not None:
                    event_payload["part"] = previous_hediff.part
                if previous_hediff.combat_log_entry is not None:
                    event_payload["combatLogEntry"] = previous_hediff.combat_log_entry
                inferred_events.append(event_payload)
                continue

            if previous_hediff is None or current_hediff is None:
                continue

            if previous_hediff.severity is None or current_hediff.severity is None:
                continue

            if abs(current_hediff.severity - previous_hediff.severity) < HEDIFF_SEVERITY_DELTA_THRESHOLD:
                continue
            if not should_emit_hediff_event(current_hediff.hediff_def or previous_hediff.hediff_def):
                continue

            event_payload = build_health_event(
                diff_context=diff_context,
                subcategory="hediff_severity_changed",
                pawn_id=pawn_id,
                ticks_to_date=ticks_to_date,
                confidence="medium",
            )
            event_payload["hediffDef"] = current_hediff.hediff_def or previous_hediff.hediff_def
            event_payload["severity_before"] = previous_hediff.severity
            event_payload["severity_after"] = current_hediff.severity
            if current_hediff.part is not None or previous_hediff.part is not None:
                event_payload["part"] = current_hediff.part or previous_hediff.part
            if current_hediff.combat_log_entry is not None or previous_hediff.combat_log_entry is not None:
                event_payload["combatLogEntry"] = (
                    current_hediff.combat_log_entry or previous_hediff.combat_log_entry
                )
            inferred_events.append(event_payload)

    return inferred_events
