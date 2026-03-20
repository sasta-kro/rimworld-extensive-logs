from __future__ import annotations

import re

from rimworld_pipeline.sanitizer import sanitize_rimworld_markup


PLACEHOLDER_DISPLAY_VALUES = {"null", "none", "unknown", "n/a"}
NUMERIC_ONLY_PATTERN = re.compile(r"^\d+$")


def clean_display_text(raw_value: object) -> str | None:
    if raw_value is None:
        return None

    sanitized_text = sanitize_rimworld_markup(str(raw_value))
    if sanitized_text is None:
        return None

    normalized_text = sanitized_text.strip()
    if not normalized_text:
        return None
    if normalized_text.lower() in PLACEHOLDER_DISPLAY_VALUES:
        return None
    return normalized_text


def clean_actor_label(raw_value: object) -> str | None:
    cleaned_text = clean_display_text(raw_value)
    if cleaned_text is None:
        return None
    if NUMERIC_ONLY_PATTERN.match(cleaned_text):
        return None
    return cleaned_text


def format_text_value(raw_value: object) -> str | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, int):
        return str(raw_value)
    if isinstance(raw_value, float):
        return f"{raw_value:.2f}".rstrip("0").rstrip(".")
    return clean_display_text(raw_value)


def format_change(before_value: object, after_value: object) -> str | None:
    before_text = format_text_value(before_value)
    after_text = format_text_value(after_value)
    if before_text is None and after_text is None:
        return None
    if before_text is None:
        return f"to {after_text}"
    if after_text is None:
        return f"from {before_text}"
    if before_text == after_text:
        return before_text
    return f"{before_text} -> {after_text}"


def format_key_value_stats(stats_payload: object) -> str | None:
    if not isinstance(stats_payload, dict) or not stats_payload:
        return None

    parts: list[str] = []
    for key in sorted(stats_payload):
        parts.append(f"{key}={stats_payload[key]}")
    return ", ".join(parts)
