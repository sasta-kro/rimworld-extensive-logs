# Current Pipeline Audit

## Scope

This note documents the current RimWorld extraction pipeline as implemented in this repository on 2026-03-20. It is intended as the Phase 1 audit deliverable from `.prompt/rimworld_codex_implementation_plan.md`.

The goal here is to describe what the code does today, where the current extension points are, and where later phases should attach new logic with minimal churn.

## Runtime Entry Points

- [`run_pipeline.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/run_pipeline.py#L9) parses `--config`, resolves the config path, and calls `rimworld_pipeline.pipeline.run_pipeline`.
- [`rimworld_pipeline/pipeline.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/pipeline.py#L10) orchestrates the three top-level stages:
  1. load config
  2. build the JSON timeline
  3. render the compact text timeline
- [`rimworld_pipeline/config.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/config.py#L19) currently supports only one config section, `pipeline`, with:
  - `save_directory`
  - `file_pattern`
  - `timeline_json_output_path`
  - `timeline_text_output_path`

## End-to-End Data Flow

The current pipeline is linear:

1. Discover save sources in a directory.
2. Read only `game/tickManager/ticksGame` from each source to sort saves by in-game chronology.
3. Parse the full `world/000_save` XML for each save.
4. Optionally parse `maps/*_save` XML files from zip archives, but only to enrich pawn names.
5. Update a shared pawn ID -> display name dictionary.
6. Extract world-level events from a small set of XML subtrees.
7. Deduplicate overlapping content across sequential saves using per-source trackers.
8. Add `source_file` metadata.
9. Sort the merged timeline by `tick`.
10. Write JSON.
11. Convert the same event list into grouped text lines and write text output.

The heavy lifting is concentrated in [`rimworld_pipeline/extractor.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py).

## Current Input Model

### Save discovery

[`discover_save_sources`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L83) supports two source types:

- `zip`: matching `.zip` files in the configured save directory
- `raw`: a fallback direct file at `world/000_save`

If any matching zip files exist, raw-file fallback is not used.

### Chronological ordering

[`extract_master_ticks_from_stream`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L101) uses `xml.etree.ElementTree.iterparse` to stop as soon as it reaches `savegame/game/tickManager/ticksGame`.

[`get_chronological_sources`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L138) sorts by those parsed ticks, not by filename or filesystem timestamps.

This matches the plan’s non-negotiable requirement and should remain the primary ordering mechanism.

### World XML parsing

[`parse_world_root`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L147) parses exactly one XML document per save source:

- zip input: `world/000_save`
- raw input: the raw file path itself

### Map XML parsing

[`map_save_member_paths`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L156) enumerates archive members under `maps/` ending in `_save`, excluding `maps/000_save`.

[`parse_map_roots`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L166) parses each map save into an `ElementTree` root, but those roots are not kept in a structured snapshot model. They are consumed immediately in `build_master_timeline` only for pawn-dictionary updates.

This means the repository already has low-level map enumeration and parsing, but not map-scoped event extraction.

## Current Extraction Sources

All emitted events come from the world save. There are four event types today.

### 1. Snapshot stats

Source path:
- `./game/storyWatcher/statsRecord`

Implementation:
- [`extract_snapshot_event`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L221)

Fields extracted:
- `numRaidsEnemy`
- `numThreatsQueued`
- `greatestPopulation`

Emission characteristics:
- one `snapshot` event per save, if `statsRecord` exists
- tick source is the save’s `ticksGame`

Assessment:
- already extracted
- very limited and coarse
- currently a per-save summary, not a diff

### 2. Tales

Source path:
- `./game/taleManager/tales/li`

Implementation:
- [`extract_tale_events`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L241)

Fields extracted:
- `Class`
- `def`
- `customLabel`
- `date` as `tickAbs`
- pawn identity from `pawnData/pawn` and `pawnData/name` when available

Emission characteristics:
- emits `tale` events only when the tale’s absolute date is greater than the last seen tale tick
- converts absolute tale time to game-relative `tick` using `gameStartAbsTick`

Assessment:
- already extracted
- one of the strongest current explicit-log sources
- still shallow because most tale-specific payload is not decoded beyond generic fields

### 3. PlayLog social interactions

Source path:
- `./game/playLog/entries/li`

Implementation:
- [`extract_playlog_interactions`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L298)

Fields extracted:
- `Class`
- `intDef` as `interactionDef`
- `logID`
- `initiator`
- `recipient`
- `ticksAbs` as `tickAbs`

Emission characteristics:
- emits `playlog_interaction` events only when `ticksAbs` exceeds the last seen playlog tick
- converts absolute time to game-relative `tick` using `gameStartAbsTick`

Assessment:
- partially extracted
- only the initiator/recipient interaction case is currently modeled
- other playlog entry classes, combat details, and richer semantics are not expanded

### 4. Archive letters/messages

Source path:
- `./game/history/archive/archivables/li`

Implementation:
- [`extract_archive_messages`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L341)

Fields extracted:
- `Class`
- `label`
- `text`
- `arrivalTick` when present

Emission characteristics:
- emits `archive_message` events
- timestamped rows use `arrivalTick` directly
- untimestamped rows fall back to the save’s `ticksGame`
- markup is sanitized before storage

Assessment:
- already extracted
- useful for letters and notifications
- partially constrained because untimestamped rows get clumped at save time and content is not classified further

## What Is Already Extracted

- World-level tale records
- World-level playlog interaction records
- World-level historical archive messages/letters
- World-level story watcher snapshot counters
- Source file path for every emitted event
- Human-readable RimWorld calendar date for every emitted event
- Hour-of-day formatting for text output
- Pawn display names when the current pawn dictionary can resolve them

## What Is Partially Extracted

- `maps/*_save` is parsed, but only for pawn-name enrichment, not event emission
- PlayLog is only represented through `playlog_interaction`; there is no broad playlog class expansion
- Battle-related information may appear indirectly in tales, playlog, or archive messages, but there is no dedicated battle-log extractor
- Pawn resolution covers some world and map pawns, but not a rich role/faction-aware identity system
- Snapshot handling exists only as per-save stats output, not as inferred state-diff events

## What Is Not Extracted At All

Based on the current code, the following categories have no direct extractor yet:

- Map-local events from `maps/*_save`
- Snapshot diffs between saves
- Explicit building, stockpile, room, biome, weather, or settlement state changes
- Health/injury/recovery progression inferred from save state
- Detailed combat participation and outcomes from battle log structures
- Rich faction resolution beyond raw pawn name fallback
- Non-pawn entity resolution for settlements, caravans, traders, animals, corpses, raids, prisoners, or guests as first-class entities
- Any structured per-save snapshot object that combines world and map scope for downstream diffing

## Time Normalization Logic

There are two time models in current use.

### Relative game time

- `ticksGame` is read from `./game/tickManager/ticksGame`
- it is used to:
  - sort saves
  - timestamp snapshot events
  - timestamp archive rows that do not have `arrivalTick`

### Absolute world time

- `gameStartAbsTick` is read from `./game/tickManager/gameStartAbsTick`
- tale `date` and playlog `ticksAbs` are treated as absolute ticks
- current normalization logic computes:
  - `tick = tickAbs - gameStartAbsTick`
- if that result is negative, the code falls back to the absolute value

### Human date conversion

[`ticks_to_date`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L63) converts relative ticks into:

- year
- quadrum
- day

The formatter separately derives hour labels from `tick` using 60,000 ticks per day and 2,500 ticks per hour.

Important nuance:
- archive rows with `arrivalTick` are treated as already compatible with `ticks_to_date`
- there is no explicit marker distinguishing whether a given event’s `tick` came from relative time or an archive-specific direct tick

## Current Deduplication Logic

Deduplication is source-specific and stateful across the full chronological run.

### Tale dedupe

- tracker: `last_seen_tale_tick`
- logic: only emit tales whose absolute `date` is strictly greater than the last seen value

### PlayLog dedupe

- tracker: `last_seen_playlog_tick`
- logic: only emit playlog rows whose absolute `ticksAbs` is strictly greater than the last seen value

### Archive dedupe

- tracker: `last_seen_archive_tick`
- logic for timestamped rows: only emit when `arrivalTick` is strictly greater than the last seen archive tick
- logic for untimestamped rows: dedupe by a content signature of `Class`, `label`, and `text`
- supporting state:
  - `seen_message_signatures`
  - `historical_message_signatures` copied per save before processing

### Snapshot dedupe

- none
- one snapshot event is emitted for each processed save

This matches the implementation-plan constraint that dedupe trackers should remain separate per source. Future sources should likely continue that pattern.

## Current Entity Resolution Logic

The repository does not yet have a dedicated resolver module. Entity resolution is currently a small shared dictionary that maps pawn IDs to names.

### Reusable helpers that already exist

In [`rimworld_pipeline/extractor.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py):

- `clean_text`
- `parse_int_value`
- `build_name_from_name_triple`
- `translate_pawn_id`

These are useful building blocks, but they are not yet a generalized resolution layer.

### World-derived pawn dictionary inputs

[`update_pawn_dictionary_from_world`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L179) populates the dictionary from:

- `./game/world/worldPawns/pawnsAlive/li`
- `./game/world/worldPawns/pawnsDead/li`
- `./game/taleManager/tales/li/pawnData`

Notably absent:
- mothballed world pawns
- faction manager data
- settlement/world object identities
- role hints
- species or kind definitions

### Map-derived pawn dictionary inputs

[`update_pawn_dictionary_from_map`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L203) populates the dictionary from:

- `./mapPawns/AllPawnsSpawned/li`
- `./mapPawns/AllPawnsUnspawned/li`
- `./mapPawns/FreeColonistsSpawned/li`
- `./mapPawns/PrisonersOfColonySpawned/li`

This improves name resolution for world-emitted events, but map-origin metadata is discarded.

### Resolution behavior in emitted events

- tales prefer:
  - embedded `pawnData/name`
  - mapped `pawnData/pawn`
  - mapped raw tale `id`
- playlog entries map `initiator` and `recipient` through the dictionary
- unresolved IDs are passed through unchanged

Assessment:
- good minimal fallback behavior
- not yet a true entity model
- not enough for raiders, traders, animals, prisoners, faction-aware labeling, or dead/non-standard pawns beyond basic names

## Current Output Schema

Every emitted event currently contains:

- `type`
- `source`
- `tick`
- `human_date`
- `source_file`

Additional fields are event-type specific.

### `tale`

- `class`
- `def`
- `customLabel`
- `tickAbs`
- `pawn`
- `pawn_id`

### `playlog_interaction`

- `class`
- `interactionDef`
- `logID`
- `tickAbs`
- `initiator`
- `initiator_id`
- `recipient`
- `recipient_id`

### `archive_message`

- `class`
- `label`
- `text`

### `snapshot`

- `stats`

The text formatter in [`rimworld_pipeline/formatter.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/formatter.py#L10):

- renders by `type`
- groups lines by `human_date`
- computes hour from `tick`
- collapses repeated consecutive identical lines as `(xN)`

## Where `maps/*_save` Should Plug In

The cleanest insertion point for later phases is immediately after world parsing and before event extraction in [`build_master_timeline`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L433).

Today, that function does this:

1. parse world root
2. read `ticksGame` and `gameStartAbsTick`
3. update world pawn dictionary
4. parse map roots and update pawn dictionary
5. extract world events

For Phase 2 and later, this should likely evolve into a per-save snapshot object containing:

- source file path
- world root
- map roots plus their member paths
- master ticks metadata

That would let downstream code:

- keep current world extractors unchanged
- add map-scoped extractors without reparsing archives
- attach source metadata such as `save_scope`, `map_file`, and inferred `map_id`
- support snapshot diffing between consecutive saves

## Best Insertion Points For Later Phases

### Multiplayer map parsing

Best insertion point:
- replace the loose `parse_world_root` plus `parse_map_roots` pattern with a structured per-save snapshot loader inside [`build_master_timeline`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py#L450)

Why:
- map enumeration already exists
- world and map XML currently share lifecycle only inside `build_master_timeline`
- this avoids introducing a parallel framework

### Battle log expansion

Best insertion point:
- add a new world extractor adjacent to:
  - `extract_tale_events`
  - `extract_playlog_interactions`
  - `extract_archive_messages`

Why:
- current extractor organization is source-by-source
- existing dedupe model is already per source
- a battle-log source will likely need its own dedupe tracker

Secondary likely requirement:
- a richer resolver module so combatants can be named consistently

### Snapshot diffing

Best insertion point:
- after a structured per-save snapshot model exists, add a diffing stage between consecutive snapshots before final timeline merge

Why:
- diffing is inherently pairwise across saves
- the current extractor functions are single-save readers, not previous-vs-current comparisons
- forcing diff logic into `extract_events_for_world_save` would overload a function that currently assumes one-save world-scope extraction

Recommended shape:
- keep explicit log extraction separate
- add a dedicated diffing module later, then merge inferred events into the same event list before final sort

## Reusable Helpers Present Today

Already reusable:

- simple XML text/int helpers in `extractor.py`
- name construction helper in `extractor.py`
- RimWorld markup sanitization in [`rimworld_pipeline/sanitizer.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/sanitizer.py#L11)
- timeline text rendering and aggregation in `formatter.py`

Not present yet:

- generic XML traversal utilities
- typed event models
- typed snapshot models
- dedicated resolver module
- generic event-emission helper
- diffing helper module

## Architectural Observations

- The repo is intentionally small and centralized. Most future work can still fit the current organization if responsibilities are split carefully.
- `extractor.py` currently mixes:
  - source discovery
  - XML parsing
  - pawn dictionary maintenance
  - source extraction
  - dedupe state
  - JSON writing
- That is workable for now, but later phases will likely benefit from extracting:
  - snapshot loading
  - entity resolution
  - diffing
  into separate modules while keeping `build_master_timeline` as the orchestrator.
- The current code already honors the most important architectural constraints:
  - in-memory zip processing
  - chronological sorting by parsed ticks
  - separate dedupe trackers by source

## Validation Performed For This Audit

The pipeline was run without code-path changes on both fixture sets using the repo virtualenv interpreter:

- `./.venv/bin/python run_pipeline.py --config pipeline_config.json`
  - dataset: `_tests/p4_to_p5`
  - result: 2400 events
- `./.venv/bin/python run_pipeline.py --config /tmp/rimworld_phase1_2saves_config.json`
  - dataset: `_tests/2saves`
  - result: 1001 events

This Phase 1 audit intentionally makes no extractor behavior changes.
