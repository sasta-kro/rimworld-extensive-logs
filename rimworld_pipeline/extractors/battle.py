from __future__ import annotations

import xml.etree.ElementTree as ET

from rimworld_pipeline.extractors.common import (
    clean_text,
    normalize_abs_tick,
    parse_body_part_list,
    parse_body_part_reference,
    parse_bool_value,
    parse_int_value,
)
from rimworld_pipeline.extractors.helpers import enrich_event_with_resolved_entity
from rimworld_pipeline.resolver import EntityResolver
from rimworld_pipeline.snapshots import SaveSnapshot


SUPPORTED_BATTLE_ENTRY_CLASSES = {
    "BattleLogEntry_StateTransition",
    "BattleLogEntry_MeleeCombat",
    "BattleLogEntry_RangedImpact",
    "BattleLogEntry_Event",
}


def build_battle_entry_signature(battle_id: str | None, battle_entry: ET.Element) -> str:
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
    ticks_to_date: callable,
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
    ticks_to_date: callable,
) -> list[dict[str, object]]:
    battle_events: list[dict[str, object]] = []

    for battle_element in save_snapshot.world_root.findall("./game/battleLog/battles/li"):
        battle_id = clean_text(battle_element.find("loadID"))

        for battle_entry in battle_element.findall("./entries/li"):
            entry_class = battle_entry.get("Class")
            if entry_class not in SUPPORTED_BATTLE_ENTRY_CLASSES:
                continue

            battle_signature = build_battle_entry_signature(battle_id, battle_entry)
            if battle_signature in historical_battle_signatures or battle_signature in seen_battle_signatures:
                continue
            seen_battle_signatures.add(battle_signature)

            battle_tick_abs = parse_int_value(battle_entry.find("ticksAbs"))
            if battle_tick_abs is None:
                continue

            battle_tick_game = normalize_abs_tick(battle_tick_abs, save_snapshot.game_start_abs_tick)
            event_payload = build_base_battle_event(
                battle_entry=battle_entry,
                battle_id=battle_id,
                battle_tick_abs=battle_tick_abs,
                battle_tick_game=battle_tick_game,
                ticks_to_date=ticks_to_date,
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

