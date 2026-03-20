from __future__ import annotations

import xml.etree.ElementTree as ET


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

