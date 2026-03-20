from __future__ import annotations

import xml.etree.ElementTree as ET

from rimworld_pipeline.extractors.common import clean_text, normalize_abs_tick, parse_int_value
from rimworld_pipeline.extractors.helpers import enrich_event_with_resolved_entity
from rimworld_pipeline.resolver import EntityResolver


def extract_playlog_interactions(
    world_root: ET.Element,
    game_start_abs_tick: int,
    last_seen_tick_abs: int,
    resolver: EntityResolver,
    ticks_to_date: callable,
) -> tuple[list[dict[str, object]], int]:
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

