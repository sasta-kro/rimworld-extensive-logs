from __future__ import annotations

from dataclasses import dataclass

from rimworld_pipeline.resolver import EntityResolver, ResolvedEntityRef
from rimworld_pipeline.snapshots import SaveSnapshot


HEDIFF_SEVERITY_DELTA_THRESHOLD = 0.05
RESEARCH_PROGRESS_DELTA_THRESHOLD = 250.0


@dataclass(frozen=True)
class DiffContext:
    previous_snapshot: SaveSnapshot
    current_snapshot: SaveSnapshot
    previous_resolver: EntityResolver
    current_resolver: EntityResolver


def resolve_entity_for_diff(diff_context: DiffContext, raw_id: str | None) -> ResolvedEntityRef:
    current_resolved = diff_context.current_resolver.resolve_reference(raw_id)
    if current_resolved.display_label not in {None, current_resolved.entity_id}:
        return current_resolved

    previous_resolved = diff_context.previous_resolver.resolve_reference(raw_id)
    if previous_resolved.display_label is not None:
        return previous_resolved
    return current_resolved


def build_inferred_event_metadata(
    diff_context: DiffContext,
    event_type: str,
    subcategory: str,
    confidence: str = "medium",
) -> dict[str, object]:
    return {
        "type": event_type,
        "subcategory": subcategory,
        "tick": diff_context.current_snapshot.ticks_game,
        "human_date": "",  # caller fills via ticks_to_date to avoid circular deps
        "source": "snapshot_diff",
        "inference_source": "snapshot_diff",
        "derived_from": "consecutive_save_snapshots",
        "confidence": confidence,
        "previous_source_file": str(diff_context.previous_snapshot.source_path),
        "previous_tick": diff_context.previous_snapshot.ticks_game,
        "current_tick": diff_context.current_snapshot.ticks_game,
        "derived_between_ticks": [
            diff_context.previous_snapshot.ticks_game,
            diff_context.current_snapshot.ticks_game,
        ],
    }

