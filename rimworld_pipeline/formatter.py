from __future__ import annotations

from pathlib import Path
import json


def render_event_as_text(event_payload: dict[str, object]) -> str:
    human_date = str(event_payload.get("human_date", "Unknown date"))
    event_type = event_payload.get("type")

    if event_type == "tale":
        pawn_name_or_id = event_payload.get("pawn") or "Unknown pawn"
        tale_definition = event_payload.get("def") or "Unknown tale"
        custom_label = event_payload.get("customLabel")

        if custom_label:
            return f"[{human_date}] EVENT: {pawn_name_or_id} triggered {tale_definition} ({custom_label})."
        return f"[{human_date}] EVENT: {pawn_name_or_id} triggered {tale_definition}."

    if event_type == "playlog_interaction":
        initiator_name_or_id = event_payload.get("initiator") or "Unknown initiator"
        recipient_name_or_id = event_payload.get("recipient") or "Unknown recipient"
        interaction_definition = event_payload.get("interactionDef") or "Unknown interaction"
        return (
            f"[{human_date}] SOCIAL: {initiator_name_or_id} did "
            f"{interaction_definition} with {recipient_name_or_id}."
        )

    if event_type == "snapshot":
        snapshot_stats = event_payload.get("stats")
        return f"[{human_date}] SNAPSHOT: {snapshot_stats}."

    if event_type == "archive_message":
        archive_label = event_payload.get("label")
        archive_text = event_payload.get("text") or ""
        if archive_label:
            return f"[{human_date}] NOTIFICATION: {archive_label} - {archive_text}"
        return f"[{human_date}] MESSAGE: {archive_text}"

    # Keeping unknown records in output is preserving potentially important context.
    return f"[{human_date}] RAW: {event_payload}"


def convert_timeline_to_text_lines(timeline_events: list[dict[str, object]]) -> list[str]:
    return [render_event_as_text(event_payload) for event_payload in timeline_events]


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
