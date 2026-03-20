from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

from rimworld_pipeline.diffing.common import (
    DiffContext,
    RESEARCH_PROGRESS_DELTA_THRESHOLD,
    build_inferred_event_metadata,
)


@dataclass(frozen=True)
class ResearchState:
    owner_id: str
    owner_label: str
    current_project: str | None
    progress_by_project: dict[str, float]


def parse_research_progress(research_manager: ET.Element | None) -> dict[str, float]:
    if research_manager is None:
        return {}

    keys = [(li.text or "").strip() for li in research_manager.findall("./progress/keys/li")]
    values = [(li.text or "").strip() for li in research_manager.findall("./progress/values/li")]
    progress_by_project: dict[str, float] = {}
    for key, value in zip(keys, values):
        if not key:
            continue
        try:
            progress_by_project[key] = float(value)
        except ValueError:
            continue
    return progress_by_project


def extract_snapshot_research_states(save_snapshot, resolver) -> list[ResearchState]:
    research_states: list[ResearchState] = []

    main_research_manager = save_snapshot.world_root.find("./game/researchManager")
    if main_research_manager is not None:
        research_states.append(
            ResearchState(
                owner_id="global",
                owner_label="Global",
                current_project=(main_research_manager.findtext("currentProj") or "").strip() or None,
                progress_by_project=parse_research_progress(main_research_manager),
            )
        )

    for faction_data in save_snapshot.world_root.findall("./game/world/mpWorldComp/factionData/values/li"):
        faction_id = (faction_data.findtext("factionId") or "").strip()
        if not faction_id:
            continue
        research_manager = faction_data.find("researchManager")
        if research_manager is None:
            continue

        resolved_faction = resolver.resolve_reference(f"Faction_{faction_id}")
        research_states.append(
            ResearchState(
                owner_id=f"Faction_{faction_id}",
                owner_label=resolved_faction.display_label or f"Faction_{faction_id}",
                current_project=(research_manager.findtext("currentProj") or "").strip() or None,
                progress_by_project=parse_research_progress(research_manager),
            )
        )

    return research_states


def build_research_event(
    diff_context: DiffContext,
    subcategory: str,
    owner_state: ResearchState,
    ticks_to_date: callable,
    confidence: str = "medium",
) -> dict[str, object]:
    event_payload = build_inferred_event_metadata(
        diff_context=diff_context,
        event_type="inferred_research_event",
        subcategory=subcategory,
        confidence=confidence,
    )
    event_payload["human_date"] = ticks_to_date(diff_context.current_snapshot.ticks_game)
    event_payload["owner_id"] = owner_state.owner_id
    event_payload["owner"] = owner_state.owner_label
    return event_payload


def diff_research_states(
    diff_context: DiffContext,
    ticks_to_date: callable,
) -> list[dict[str, object]]:
    previous_states = {
        state.owner_id: state
        for state in extract_snapshot_research_states(
            diff_context.previous_snapshot, diff_context.previous_resolver
        )
    }
    current_states = {
        state.owner_id: state
        for state in extract_snapshot_research_states(
            diff_context.current_snapshot, diff_context.current_resolver
        )
    }

    inferred_events: list[dict[str, object]] = []

    for owner_id in sorted(set(previous_states) | set(current_states)):
        previous_state = previous_states.get(owner_id)
        current_state = current_states.get(owner_id)
        if current_state is None:
            continue

        if previous_state is None:
            if current_state.current_project:
                event_payload = build_research_event(
                    diff_context=diff_context,
                    subcategory="research_started",
                    owner_state=current_state,
                    ticks_to_date=ticks_to_date,
                )
                event_payload["projectDef"] = current_state.current_project
                inferred_events.append(event_payload)
            continue

        if previous_state.current_project != current_state.current_project:
            if previous_state.current_project and current_state.current_project:
                event_payload = build_research_event(
                    diff_context=diff_context,
                    subcategory="research_switched",
                    owner_state=current_state,
                    ticks_to_date=ticks_to_date,
                )
                event_payload["project_before"] = previous_state.current_project
                event_payload["project_after"] = current_state.current_project
                inferred_events.append(event_payload)
            elif previous_state.current_project is None and current_state.current_project:
                event_payload = build_research_event(
                    diff_context=diff_context,
                    subcategory="research_started",
                    owner_state=current_state,
                    ticks_to_date=ticks_to_date,
                )
                event_payload["projectDef"] = current_state.current_project
                inferred_events.append(event_payload)
            elif previous_state.current_project and current_state.current_project is None:
                event_payload = build_research_event(
                    diff_context=diff_context,
                    subcategory="research_completed",
                    owner_state=current_state,
                    ticks_to_date=ticks_to_date,
                    confidence="high",
                )
                event_payload["projectDef"] = previous_state.current_project
                event_payload["completion_inference"] = "current_project_cleared"
                inferred_events.append(event_payload)

        tracked_projects = sorted(set(previous_state.progress_by_project) | set(current_state.progress_by_project))
        for project_def in tracked_projects:
            previous_progress = previous_state.progress_by_project.get(project_def, 0.0)
            current_progress = current_state.progress_by_project.get(project_def, 0.0)
            if current_progress <= previous_progress:
                continue

            if (
                current_progress - previous_progress >= RESEARCH_PROGRESS_DELTA_THRESHOLD
                and current_state.current_project == project_def
            ):
                event_payload = build_research_event(
                    diff_context=diff_context,
                    subcategory="research_progressed",
                    owner_state=current_state,
                    ticks_to_date=ticks_to_date,
                )
                event_payload["projectDef"] = project_def
                event_payload["progress_before"] = previous_progress
                event_payload["progress_after"] = current_progress
                inferred_events.append(event_payload)

        for project_def in sorted(previous_state.progress_by_project):
            if project_def in current_state.progress_by_project:
                continue
            event_payload = build_research_event(
                diff_context=diff_context,
                subcategory="research_completed",
                owner_state=current_state,
                ticks_to_date=ticks_to_date,
                confidence="high",
            )
            event_payload["projectDef"] = project_def
            event_payload["progress_before"] = previous_state.progress_by_project.get(project_def)
            event_payload["completion_inference"] = "progress_removed"
            inferred_events.append(event_payload)

    return inferred_events
