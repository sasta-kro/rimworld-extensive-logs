# Phase 4: Snapshot Differencing

Phase 4 adds inferred events by comparing consecutive `SaveSnapshot` objects.

It currently covers only:

- health / hediff deltas
- research deltas
- faction relation / goodwill deltas

It does not add quest diffing or broad world-state differencing yet.

## Where Diffing Attaches

The orchestration point remains [`rimworld_pipeline/extractor.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py).

Current flow:

1. load current `SaveSnapshot`
2. build current resolver
3. extract explicit persisted-log events
4. compare previous snapshot vs current snapshot
5. emit inferred events
6. merge and sort all events into canonical JSON

The diff orchestration lives in [`rimworld_pipeline/diffing/pipeline.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/diffing/pipeline.py).

## Inferred Event Families

### `inferred_health_event`

Implemented in [`diffing/health.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/diffing/health.py).

Current subcategories:

- `hediff_started`
- `hediff_removed`
- `hediff_severity_changed`
- `pawn_died`

Current behavior:

- detailed hediff diffing only runs for pawns present in both snapshots
- this avoids dumping entire health states for pawns that exist on only one side
- death transitions are inferred when a pawn is present in both snapshots and moves from non-dead to dead

Noise control:

- severity changes require an absolute delta of at least `0.05`
- hediff identity is based on semantic fields such as def, part, and combat-log linkage rather than save-local `loadID`

### `inferred_research_event`

Implemented in [`diffing/research.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/diffing/research.py).

Current subcategories:

- `research_started`
- `research_progressed`
- `research_completed`
- `research_switched`

Current sources:

- `./game/researchManager`
- `./game/world/mpWorldComp/factionData/values/li/researchManager`

Noise control:

- progress rows emit only when progress increases by at least `250.0`
- completion rows emit when a tracked project disappears from progress or the active project clears

### `inferred_faction_relation_event`

Implemented in [`diffing/factions.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/diffing/factions.py).

Current subcategories:

- `goodwill_changed`
- `relation_kind_changed`

Current behavior:

- compares each faction’s relation toward the detected `PlayerColony` faction
- emits only when goodwill or relation kind actually changes

## Provenance

All inferred events currently include:

- `inference_source`
- `derived_from`
- `confidence`
- `previous_source_file`
- `previous_tick`
- `current_tick`
- `derived_between_ticks`

This keeps inferred rows clearly separate from explicit persisted-log rows.

## Still Deferred

- quest diffing
- broader map/world structural differencing
- inventory/resource diffing
- automatic dedupe between explicit and inferred signals beyond basic source separation
