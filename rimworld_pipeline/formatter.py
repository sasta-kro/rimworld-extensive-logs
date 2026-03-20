from __future__ import annotations

from pathlib import Path
import json
import re

from rimworld_pipeline.rendering.event_text import render_event_as_text


def format_hour_for_event(event_payload: dict[str, object]) -> str:
    raw_tick = event_payload.get("tick", 0)
    tick_value = int(raw_tick) if isinstance(raw_tick, int | str) and str(raw_tick).isdigit() else 0
    hour_24_value = (tick_value % 60000) // 2500
    meridiem = "AM" if hour_24_value < 12 else "PM"
    hour_12_value = hour_24_value % 12
    if hour_12_value == 0:
        hour_12_value = 12
    return f"{hour_12_value}{meridiem}"


def compact_text_log_line(raw_line: str) -> str:
    return re.sub(r"\n{2,}", "\n", raw_line)


def append_aggregated_line(
    output_lines: list[str], previous_line: str | None, previous_count: int
) -> None:
    if previous_line is None:
        return
    if previous_count > 1:
        output_lines.append(f"{previous_line} (x{previous_count})")
        return
    output_lines.append(previous_line)


def convert_timeline_to_text_lines(timeline_events: list[dict[str, object]]) -> list[str]:
    output_lines: list[str] = []
    current_human_date: str | None = None
    previous_event_line: str | None = None
    previous_event_count = 0

    for event_payload in timeline_events:
        event_body = render_event_as_text(event_payload)
        if event_body is None:
            continue

        human_date = str(event_payload.get("human_date", "Unknown date"))
        if human_date != current_human_date:
            append_aggregated_line(output_lines, previous_event_line, previous_event_count)
            previous_event_line = None
            previous_event_count = 0

            if output_lines:
                output_lines.append("")
            output_lines.append(f"### {human_date}")
            current_human_date = human_date

        event_hour = format_hour_for_event(event_payload)
        formatted_event_line = compact_text_log_line(f"[{event_hour}] {event_body}")

        if formatted_event_line == previous_event_line:
            previous_event_count += 1
            continue

        append_aggregated_line(output_lines, previous_event_line, previous_event_count)
        previous_event_line = formatted_event_line
        previous_event_count = 1

    append_aggregated_line(output_lines, previous_event_line, previous_event_count)
    return output_lines


def write_text_timeline(text_lines: list[str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(text_lines) + "\n", encoding="utf-8")


def convert_json_file_to_text_file(
    timeline_json_path: Path,
    timeline_text_output_path: Path,
) -> None:
    timeline_events = json.loads(timeline_json_path.read_text(encoding="utf-8"))
    text_lines = convert_timeline_to_text_lines(timeline_events)
    write_text_timeline(text_lines=text_lines, output_path=timeline_text_output_path)
