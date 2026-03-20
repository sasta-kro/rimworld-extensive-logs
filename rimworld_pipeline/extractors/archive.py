from __future__ import annotations

import xml.etree.ElementTree as ET

from rimworld_pipeline.extractors.common import clean_text, parse_int_value
from rimworld_pipeline.sanitizer import sanitize_rimworld_markup


def extract_archive_messages(
    world_root: ET.Element,
    ticks_game: int,
    last_seen_archive_tick: int,
    historical_message_signatures: set[str],
    seen_message_signatures: set[str],
    ticks_to_date: callable,
) -> tuple[list[dict[str, object]], int]:
    archive_events: list[dict[str, object]] = []
    highest_archive_tick = last_seen_archive_tick

    for archive_item_element in world_root.findall("./game/history/archive/archivables/li"):
        archive_class = archive_item_element.get("Class") or ""
        archive_label = sanitize_rimworld_markup(clean_text(archive_item_element.find("label")))
        archive_text = sanitize_rimworld_markup(clean_text(archive_item_element.find("text")))
        arrival_tick = parse_int_value(archive_item_element.find("arrivalTick"))

        if arrival_tick is None:
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

