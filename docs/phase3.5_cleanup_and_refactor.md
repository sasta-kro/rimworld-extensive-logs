# Phase 3.5: Cleanup and Refactor

This phase is a cleanup/prep pass after Phase 3.

It does not add snapshot differencing or new inferred event families.

## Correctness Fixes

- TXT rendering no longer emits literal placeholder strings such as `null`.
- Tale rows no longer treat numeric tale record IDs as if they were actor names.
- Snapshot rows in TXT no longer dump raw Python dict repr output.
- Battle TXT phrasing now degrades more carefully when a recipient or initiator is missing.
- Resolver lookups now treat placeholder raw IDs like `null` as missing instead of preserving them as display values.

## Modular Refactor

### Extraction split

Source-specific extraction logic now lives under [`rimworld_pipeline/extractors/`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractors):

- `common.py`
- `tales.py`
- `playlog.py`
- `archive.py`
- `battle.py`
- `helpers.py`

[`rimworld_pipeline/extractor.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py) is now primarily:

- save discovery
- chronological ordering
- snapshot loading
- orchestrating per-save extraction
- maintaining dedupe state
- writing canonical JSON

### Rendering split

TXT presentation helpers now live under [`rimworld_pipeline/rendering/`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/rendering):

- `text_display.py`
- `event_text.py`

This keeps display cleanup separate from extraction logic and makes future TXT changes safer.

## JSON-First Policy In This Phase

- JSON still retains raw IDs and structured battle metadata.
- TXT simplifies or suppresses low-value raw presentation.
- A small additive JSON field was added for tales:
  - `taleID`

## Phase 4 Attachment Points

Snapshot differencing should attach next at the orchestration layer in [`extractor.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py), alongside existing per-save extractors, rather than being mixed into battle or TXT rendering code.

The intended flow remains:

1. load `SaveSnapshot`
2. build resolver
3. extract explicit persisted-log events
4. later add diff-based inferred events
5. merge and sort into canonical JSON

## Still Deferred

- snapshot differencing
- health/research/faction delta inference
- quest diffing
- large narrative formatter redesign
