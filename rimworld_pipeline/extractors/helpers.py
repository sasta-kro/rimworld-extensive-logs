from __future__ import annotations

from rimworld_pipeline.resolver import ResolvedEntityRef


def enrich_event_with_resolved_entity(
    event_payload: dict[str, object],
    prefix: str,
    resolved_entity: ResolvedEntityRef,
    display_override: str | None = None,
) -> None:
    display_label = display_override or resolved_entity.display_label or resolved_entity.raw_id
    if display_label is not None:
        event_payload[prefix] = display_label
    if resolved_entity.raw_id is not None:
        event_payload[f"{prefix}_id"] = resolved_entity.raw_id
    if resolved_entity.entity_id is not None:
        event_payload[f"{prefix}_entity_id"] = resolved_entity.entity_id
    if resolved_entity.kind_def is not None:
        event_payload[f"{prefix}_kindDef"] = resolved_entity.kind_def
    if resolved_entity.thing_def is not None:
        event_payload[f"{prefix}_thingDef"] = resolved_entity.thing_def
    if resolved_entity.faction_id is not None:
        event_payload[f"{prefix}_faction_id"] = resolved_entity.faction_id
    if resolved_entity.faction_name is not None:
        event_payload[f"{prefix}_faction"] = resolved_entity.faction_name
    if resolved_entity.role_hint is not None:
        event_payload[f"{prefix}_role"] = resolved_entity.role_hint

