# Save Snapshot Model

Phase 2 introduces a structured per-save snapshot layer for the pipeline.

## Purpose

The extractor previously parsed:

- one world XML root per save
- zero or more map XML roots per zip archive

but only preserved the world root and discarded map roots after pawn-name enrichment. That made later map-scoped extraction and snapshot diffing harder than necessary.

The new snapshot layer keeps the parsed XML for one processed save together in a small typed container, while preserving current runtime behavior.

## Types

Defined in [`rimworld_pipeline/snapshots.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/snapshots.py):

- `SaveSource`
  - existing lightweight discovery record
  - contains `source_type` and filesystem `path`
- `MapSnapshot`
  - `member_path`
  - `map_id`
  - parsed XML `root`
- `SaveSnapshot`
  - `source_path`
  - `source_type`
  - parsed `world_root`
  - `map_snapshots`
  - `ticks_game`
  - `game_start_abs_tick`

## Current Usage

[`load_save_snapshot`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L139) is now responsible for loading one save into a `SaveSnapshot`.

[`build_master_timeline`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L410) now:

1. discovers sources
2. sorts them chronologically by parsed `ticksGame`
3. loads each source into a `SaveSnapshot`
4. updates pawn resolution from world plus map snapshots
5. extracts the same world-scoped event types as before

## Intended Phase 3+ Usage

Later phases should prefer extending `SaveSnapshot` or consuming it directly rather than reparsing zip members ad hoc.

Likely next uses:

- map-scoped extractors can iterate `save_snapshot.map_snapshots`
- richer entity resolution can incorporate map-level and world-level identities together
- snapshot diffing can compare adjacent `SaveSnapshot` objects without changing the current world event extractors

This layer is intentionally small. It is meant to preserve parsed state, not to become a framework on its own.
