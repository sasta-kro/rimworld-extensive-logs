from __future__ import annotations

from rimworld_pipeline.rendering.text_display import (
    clean_actor_label,
    clean_display_text,
    format_change,
    format_key_value_stats,
    format_text_value,
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

    if event_type == "inferred_health_event":
        pawn_name = clean_actor_label(event_payload.get("pawn")) or "Unknown pawn"
        hediff_def = clean_display_text(event_payload.get("hediffDef"))
        subcategory = clean_display_text(event_payload.get("subcategory")) or ""
        if subcategory == "pawn_died":
            return f"HEALTH: {pawn_name} died between saves."
        if subcategory == "hediff_started" and hediff_def:
            return f"HEALTH: {pawn_name} developed {hediff_def}."
        if subcategory == "hediff_removed" and hediff_def:
            return f"HEALTH: {pawn_name} no longer has {hediff_def}."
        if subcategory == "hediff_severity_changed" and hediff_def:
            severity_change = format_change(
                event_payload.get("severity_before"),
                event_payload.get("severity_after"),
            )
            if severity_change is None:
                return f"HEALTH: {pawn_name}'s {hediff_def} changed."
            return (
                f"HEALTH: {pawn_name}'s {hediff_def} changed "
                f"({severity_change})."
            )
        return None

    if event_type == "inferred_research_event":
        owner = clean_display_text(event_payload.get("owner")) or "Unknown owner"
        subcategory = clean_display_text(event_payload.get("subcategory")) or ""
        project_def = clean_display_text(event_payload.get("projectDef"))
        if subcategory == "research_completed" and project_def:
            return f"RESEARCH: {owner} completed {project_def}."
        if subcategory == "research_started" and project_def:
            return f"RESEARCH: {owner} started {project_def}."
        if subcategory == "research_switched":
            before = clean_display_text(event_payload.get("project_before")) or "unknown project"
            after = clean_display_text(event_payload.get("project_after")) or "unknown project"
            return f"RESEARCH: {owner} switched {before} -> {after}."
        if subcategory == "research_progressed" and project_def:
            progress_change = format_change(
                event_payload.get("progress_before"),
                event_payload.get("progress_after"),
            )
            if progress_change is None:
                return f"RESEARCH: {owner} progressed {project_def}."
            return (
                f"RESEARCH: {owner} progressed {project_def} "
                f"({progress_change})."
            )
        return None

    if event_type == "inferred_faction_relation_event":
        faction = clean_display_text(event_payload.get("faction")) or "Unknown faction"
        subcategory = clean_display_text(event_payload.get("subcategory")) or ""
        if subcategory == "goodwill_changed":
            before = event_payload.get("goodwill_before")
            after = event_payload.get("goodwill_after")
            before_text = format_text_value(before)
            after_text = format_text_value(after)
            if before_text is None and after_text is not None:
                return f"FACTION: Relations with {faction} changed to {after_text}."
            if before_text is not None and after_text is not None:
                if before is not None and after is not None and after > before:
                    return f"FACTION: Relations with {faction} improved {before_text} -> {after_text}."
                if before is not None and after is not None and after < before:
                    return f"FACTION: Relations with {faction} worsened {before_text} -> {after_text}."
                return f"FACTION: Relations with {faction} changed {before_text} -> {after_text}."
            return f"FACTION: Relations with {faction} changed."
        if subcategory == "relation_kind_changed":
            relation_change = format_change(
                event_payload.get("relation_kind_before"),
                event_payload.get("relation_kind_after"),
            )
            if relation_change is None:
                return f"FACTION: {faction} relation changed."
            return (
                f"FACTION: {faction} relation changed "
                f"{relation_change}."
            )
        return None

    return f"RAW: {event_payload}"
