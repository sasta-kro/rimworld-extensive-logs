from __future__ import annotations

from rimworld_pipeline.diffing.common import DiffContext
from rimworld_pipeline.diffing.factions import diff_faction_relation_states
from rimworld_pipeline.diffing.health import diff_health_states
from rimworld_pipeline.diffing.research import diff_research_states
from rimworld_pipeline.resolver import EntityResolver
from rimworld_pipeline.snapshots import SaveSnapshot


def build_inferred_events(
    previous_snapshot: SaveSnapshot,
    current_snapshot: SaveSnapshot,
    previous_resolver: EntityResolver,
    current_resolver: EntityResolver,
    ticks_to_date: callable,
) -> list[dict[str, object]]:
    diff_context = DiffContext(
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        previous_resolver=previous_resolver,
        current_resolver=current_resolver,
    )

    inferred_events: list[dict[str, object]] = []
    inferred_events.extend(diff_health_states(diff_context=diff_context, ticks_to_date=ticks_to_date))
    inferred_events.extend(diff_research_states(diff_context=diff_context, ticks_to_date=ticks_to_date))
    inferred_events.extend(
        diff_faction_relation_states(diff_context=diff_context, ticks_to_date=ticks_to_date)
    )
    return inferred_events

