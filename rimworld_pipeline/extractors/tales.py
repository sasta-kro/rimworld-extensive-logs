from __future__ import annotations

import xml.etree.ElementTree as ET

from rimworld_pipeline.extractors.common import (
    build_name_from_name_triple,
    clean_text,
    normalize_abs_tick,
    parse_int_value,
)
from rimworld_pipeline.extractors.helpers import enrich_event_with_resolved_entity
from rimworld_pipeline.resolver import EntityResolver, normalize_entity_id


def extract_tale_events(
    world_root: ET.Element,
    game_start_abs_tick: int,
    last_seen_tick_abs: int,
    resolver: EntityResolver,
    ticks_to_date: callable,
) -> tuple[list[dict[str, object]], int]:
    tale_events: list[dict[str, object]] = []
    highest_tale_tick_abs = last_seen_tick_abs

    for tale_element in world_root.findall("./game/taleManager/tales/li"):
        tale_tick_abs = parse_int_value(tale_element.find("date"))
        if tale_tick_abs is None or tale_tick_abs <= last_seen_tick_abs:
            continue

        highest_tale_tick_abs = max(highest_tale_tick_abs, tale_tick_abs)
        tale_tick_game = normalize_abs_tick(tale_tick_abs, game_start_abs_tick)

        tale_record_id = clean_text(tale_element.find("id"))
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

        tale_event = {
            "type": "tale",
            "source": "taleManager.tales",
            "tick": tale_tick_game,
            "tickAbs": tale_tick_abs,
            "human_date": ticks_to_date(tale_tick_game),
            "class": tale_element.get("Class"),
            "def": clean_text(tale_element.find("def")),
            "customLabel": clean_text(tale_element.find("customLabel")),
            "taleID": tale_record_id,
        }

        if normalize_entity_id(tale_pawn_id) is not None:
            enrich_event_with_resolved_entity(
                tale_event,
                prefix="pawn",
                resolved_entity=resolver.resolve_reference(tale_pawn_id),
                display_override=tale_pawn_name,
            )

        tale_events.append(tale_event)

    return tale_events, highest_tale_tick_abs

