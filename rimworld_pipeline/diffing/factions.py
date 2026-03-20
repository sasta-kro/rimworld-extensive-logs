from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

from rimworld_pipeline.diffing.common import DiffContext, build_inferred_event_metadata
from rimworld_pipeline.resolver import normalize_entity_id


@dataclass(frozen=True)
class FactionRelationState:
    faction_id: str
    faction_name: str
    relation_kind: str | None
    goodwill: int | None


def parse_int(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def extract_faction_relation_states(world_root: ET.Element) -> dict[str, FactionRelationState]:
    faction_states: dict[str, FactionRelationState] = {}
    player_faction_id: str | None = None

    for faction_element in world_root.findall("./game/world/factionManager/allFactions/li"):
        faction_load_id = (faction_element.findtext("loadID") or "").strip()
        faction_def = (faction_element.findtext("def") or "").strip()
        if faction_load_id and faction_def == "PlayerColony":
            player_faction_id = f"Faction_{faction_load_id}"
            break

    if player_faction_id is None:
        return faction_states

    for faction_element in world_root.findall("./game/world/factionManager/allFactions/li"):
        faction_id = normalize_entity_id((faction_element.findtext("loadID") or "").strip())
        if faction_id is None:
            continue

        faction_name = (faction_element.findtext("name") or "").strip() or faction_id
        player_relation = None
        for relation_element in faction_element.findall("./relations/li"):
            other_faction = normalize_entity_id((relation_element.findtext("other") or "").strip())
            if other_faction == player_faction_id:
                player_relation = relation_element
                break

        if player_relation is None:
            continue

        faction_states[faction_id] = FactionRelationState(
            faction_id=faction_id,
            faction_name=faction_name,
            relation_kind=(player_relation.findtext("kind") or "").strip() or None,
            goodwill=parse_int((player_relation.findtext("goodwill") or "").strip()),
        )

    return faction_states


def build_faction_event(
    diff_context: DiffContext,
    subcategory: str,
    faction_state: FactionRelationState,
    ticks_to_date: callable,
) -> dict[str, object]:
    event_payload = build_inferred_event_metadata(
        diff_context=diff_context,
        event_type="inferred_faction_relation_event",
        subcategory=subcategory,
        confidence="high",
    )
    event_payload["human_date"] = ticks_to_date(diff_context.current_snapshot.ticks_game)
    event_payload["faction_id"] = faction_state.faction_id
    event_payload["faction"] = faction_state.faction_name
    return event_payload


def diff_faction_relation_states(diff_context: DiffContext, ticks_to_date: callable) -> list[dict[str, object]]:
    previous_states = extract_faction_relation_states(diff_context.previous_snapshot.world_root)
    current_states = extract_faction_relation_states(diff_context.current_snapshot.world_root)
    inferred_events: list[dict[str, object]] = []

    for faction_id in sorted(set(previous_states) & set(current_states)):
        previous_state = previous_states[faction_id]
        current_state = current_states[faction_id]

        if previous_state.goodwill != current_state.goodwill:
            event_payload = build_faction_event(
                diff_context=diff_context,
                subcategory="goodwill_changed",
                faction_state=current_state,
                ticks_to_date=ticks_to_date,
            )
            event_payload["goodwill_before"] = previous_state.goodwill
            event_payload["goodwill_after"] = current_state.goodwill
            event_payload["relation_kind"] = current_state.relation_kind
            inferred_events.append(event_payload)

        if previous_state.relation_kind != current_state.relation_kind:
            event_payload = build_faction_event(
                diff_context=diff_context,
                subcategory="relation_kind_changed",
                faction_state=current_state,
                ticks_to_date=ticks_to_date,
            )
            event_payload["relation_kind_before"] = previous_state.relation_kind
            event_payload["relation_kind_after"] = current_state.relation_kind
            event_payload["goodwill_before"] = previous_state.goodwill
            event_payload["goodwill_after"] = current_state.goodwill
            inferred_events.append(event_payload)

    return inferred_events
