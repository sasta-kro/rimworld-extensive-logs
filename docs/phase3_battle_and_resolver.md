# Phase 3: Battle Extraction and Entity Resolver

Phase 3 adds two linked capabilities:

- richer entity resolution built on `SaveSnapshot`
- explicit battle-log extraction from `game/battleLog/battles`

Snapshot diffing is still intentionally deferred to Phase 4.

## Resolver Architecture

Defined in [`rimworld_pipeline/resolver.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/resolver.py).

### Main types

- `FactionInfo`
- `EntityInfo`
- `ResolvedEntityRef`
- `EntityResolver`

### Current resolver inputs

The resolver builds one per-save entity index from:

- world factions under `./game/world/factionManager/allFactions/li`
- world pawns under:
  - `pawnsAlive`
  - `pawnsMothballed`
  - `pawnsDead`
- map pawn collections when present in map saves
- all tale pawn-data records that contain both `pawn` and `name`

This matters because many actors referenced in playlog or battle log are not still present in `worldPawns`, but they may still be named in tale records.

### Resolver behavior

For each entity, the resolver now tries to preserve:

- raw source ID
- normalized entity ID
- best display label
- `kindDef`
- thing `def`
- `faction_id`
- `faction`
- `role`

Identity is anchored on raw/normalized ID, not display name, so two different pawns with the same name do not collapse together.

When a full lookup is unavailable, fallback remains graceful:

1. named entity from indexed save data
2. label derived from the raw ID, such as `Snowhare` from `Thing_Snowhare19274`
3. raw ID when nothing better is available

## Battle Event Types

Defined in [`rimworld_pipeline/extractor.py`](/Users/saiaikeshwetunaung/Developer/PythonProjects/rimworld-log-extractor/rimworld_pipeline/extractor.py).

Phase 3 now emits these explicit JSON event types from `./game/battleLog/battles/li/entries/li`:

- `battle_state_transition`
- `battle_melee`
- `battle_ranged_impact`
- `battle_event`

All battle events include at minimum:

- `type`
- `source`
- `class`
- `battle_id` when available
- `logID` when available
- `tick`
- `tickAbs`
- `human_date`
- `source_file`

### Battle entity fields

Battle events preserve both resolved display fields and raw IDs where available, for example:

- `initiator`, `initiator_id`
- `recipient`, `recipient_id`
- `subject`, `subject_id`
- `originalTarget`, `originalTarget_id`

And additive metadata from the resolver:

- `*_entity_id`
- `*_kindDef`
- `*_thingDef`
- `*_faction_id`
- `*_faction`
- `*_role`

### Battle-specific fields

- `battle_state_transition`
  - `transitionDef`
  - `culpritHediffDef`
  - `culpritTargetPart`
  - `culpritHediffTargetPart`
- `battle_melee`
  - `combatDef`
  - `ruleDef`
  - `implementType`
  - `toolLabel`
  - `ownerDef`
  - `alwaysShowInCompact`
  - `deflected`
  - `damagedParts`
  - `damagedPartsDestroyed`
  - `recipientThing`
- `battle_ranged_impact`
  - `weaponDef`
  - `projectileDef`
  - `coverDef`
  - `originalTargetMobile`
  - `damagedParts`
  - `damagedPartsDestroyed`
  - `recipientThing`
  - `originalTargetThing`
- `battle_event`
  - `eventDef`

## Existing Event Schema Additions

Existing `tale` and `playlog_interaction` events now keep their prior primary fields, but also gain resolver-derived metadata when available:

- `*_entity_id`
- `*_kindDef`
- `*_thingDef`
- `*_faction_id`
- `*_faction`
- `*_role`

This keeps JSON as the high-retention canonical store without requiring a major text-format redesign.

## Dedupe and Time Handling

- chronological save ordering still uses parsed `ticksGame`
- battle entries normalize `ticksAbs` to game-relative `tick` using the same absolute-to-relative logic as other absolute-tick sources
- battle extraction uses its own dedupe tracker via battle-entry signatures and does not reuse tale/playlog/archive trackers

## Still Deferred To Phase 4

- snapshot differencing
- inferred health/research/faction deltas
- map-state diff inference
- broader text formatter redesign
