from __future__ import annotations

from rimworld_pipeline.rendering.text_display import (
    clean_actor_label,
    clean_display_text,
    format_key_value_stats,
)


def render_event_as_text(event_payload: dict[str, object]) -> str | None:
    event_type = event_payload.get("type")

    if event_type == "tale":
        pawn_name = clean_actor_label(event_payload.get("pawn")) or "Unknown pawn"
        tale_definition = clean_display_text(event_payload.get("def")) or "Unknown tale"
        custom_label = clean_display_text(event_payload.get("customLabel"))
        if custom_label:
            return f"EVENT: {pawn_name} triggered {tale_definition} ({custom_label})."
        return f"EVENT: {pawn_name} triggered {tale_definition}."

    if event_type == "playlog_interaction":
        initiator = clean_actor_label(event_payload.get("initiator")) or "Unknown initiator"
        recipient = clean_actor_label(event_payload.get("recipient")) or "Unknown recipient"
        interaction_definition = clean_display_text(event_payload.get("interactionDef")) or "Unknown interaction"
        return f"SOCIAL: {initiator} did {interaction_definition} with {recipient}."

    if event_type == "snapshot":
        formatted_stats = format_key_value_stats(event_payload.get("stats"))
        if formatted_stats is None:
            return None
        return f"SNAPSHOT: {formatted_stats}."

    if event_type == "archive_message":
        archive_label = clean_display_text(event_payload.get("label"))
        archive_text = clean_display_text(event_payload.get("text")) or ""
        if archive_label:
            return f"NOTIFICATION: {archive_label} - {archive_text}"
        return f"MESSAGE: {archive_text}"

    if event_type == "battle_state_transition":
        subject = clean_actor_label(event_payload.get("subject")) or "Unknown subject"
        transition_def = clean_display_text(event_payload.get("transitionDef")) or "Unknown transition"
        initiator = clean_actor_label(event_payload.get("initiator"))
        if initiator:
            return f"BATTLE: {subject} had {transition_def} caused by {initiator}."
        return f"BATTLE: {subject} had {transition_def}."

    if event_type == "battle_melee":
        initiator = clean_actor_label(event_payload.get("initiator")) or "Unknown attacker"
        recipient = clean_actor_label(event_payload.get("recipient"))
        tool_label = clean_display_text(event_payload.get("toolLabel"))
        if recipient and tool_label:
            return f"BATTLE: {initiator} hit {recipient} in melee with {tool_label}."
        if recipient:
            return f"BATTLE: {initiator} hit {recipient} in melee."
        if tool_label:
            return f"BATTLE: {initiator} struck an unknown target in melee with {tool_label}."
        return f"BATTLE: {initiator} struck an unknown target in melee."

    if event_type == "battle_ranged_impact":
        initiator = clean_actor_label(event_payload.get("initiator")) or "Unknown attacker"
        recipient = clean_actor_label(event_payload.get("recipient"))
        original_target = clean_actor_label(event_payload.get("originalTarget"))
        weapon_def = clean_display_text(event_payload.get("weaponDef")) or "unknown weapon"
        if recipient:
            return f"BATTLE: {initiator} hit {recipient} with {weapon_def}."
        if original_target:
            return f"BATTLE: {initiator} fired {weapon_def} at {original_target}."
        return f"BATTLE: {initiator} fired {weapon_def} at an unknown target."

    if event_type == "battle_event":
        subject = clean_actor_label(event_payload.get("subject")) or "Unknown subject"
        event_def = clean_display_text(event_payload.get("eventDef")) or "Unknown battle event"
        initiator = clean_actor_label(event_payload.get("initiator"))
        if initiator:
            return f"BATTLE: {subject} had {event_def} from {initiator}."
        return f"BATTLE: {subject} had {event_def}."

    return f"RAW: {event_payload}"

