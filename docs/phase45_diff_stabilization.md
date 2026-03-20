# Phase 4.5 Diff Stabilization

This pass hardens the Phase 4 snapshot-diff layer without adding new inferred families.

## What Changed

- Fixed the health severity parser so `severity` values are actually parsed as floats.
- Re-enabled `hediff_severity_changed` emission when the existing materiality threshold is crossed.
- Suppressed low-value `MissingBodyPart` hediff delta rows to reduce health spam.
- Extended health diff sourcing to include map-local pawn records stored under map thing containers when they are not already present in world pawn sections.
- Extended the resolver to load those same map-local pawns so inferred health events get better labels.
- Cleaned inferred TXT rendering so faction, research, and health lines do not print raw `None`.

## Noise Controls

- Health severity change threshold remains `0.05`.
- `MissingBodyPart` hediff starts, removals, and severity changes are suppressed.
  These rows were high-volume and low-value in the provided fixtures.
- World pawn sections remain authoritative.
  Map-local pawn health is used as fallback coverage for map-only pawns.

## Validation

- `util_standalone/validate_phase45.py` checks:
  - float severity parsing
  - synthetic `hediff_severity_changed` emission
  - explicit event counts staying fixed for fixture outputs
  - absence of raw `None` in inferred TXT lines

## Still Deferred

- quest diffing
- inventory/resource diffing
- broader inferred-event summarization
- Phase 5 work
