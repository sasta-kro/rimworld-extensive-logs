from __future__ import annotations

import re


ANGLE_TAG_PATTERN = re.compile(r"<[^>]+>")
RIMWORLD_OPEN_TOKEN_PATTERN = re.compile(r"\(\*[A-Za-z]+(?:=[^)]*)?\)")
RIMWORLD_CLOSE_TOKEN_PATTERN = re.compile(r"\(/[^)]+\)")


def sanitize_rimworld_markup(raw_text: str | None) -> str | None:
    if raw_text is None:
        return None

    cleaned_text = ANGLE_TAG_PATTERN.sub("", raw_text)
    cleaned_text = RIMWORLD_OPEN_TOKEN_PATTERN.sub("", cleaned_text)
    cleaned_text = RIMWORLD_CLOSE_TOKEN_PATTERN.sub("", cleaned_text)

    # Trimming each line is removing stray spaces left behind by token removal.
    normalized_lines = [line.strip() for line in cleaned_text.splitlines()]
    normalized_text = "\n".join(normalized_lines)

    return normalized_text.strip()
