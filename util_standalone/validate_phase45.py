from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rimworld_pipeline.diffing.common import DiffContext
from rimworld_pipeline.diffing.health import diff_health_states, parse_float_value
from rimworld_pipeline.resolver import EntityResolver
from rimworld_pipeline.snapshots import SaveSnapshot


def build_snapshot(xml_text: str, tick: int) -> SaveSnapshot:
    return SaveSnapshot(
        source_path=f"inline_{tick}.xml",
        source_type="raw",
        world_root=ET.fromstring(xml_text),
        map_snapshots=[],
        ticks_game=tick,
        game_start_abs_tick=0,
    )


def assert_health_severity_diff_emits() -> None:
    previous_xml = """
    <savegame>
      <game>
        <world>
          <worldPawns>
            <pawnsAlive>
              <li>
                <id>Human1</id>
                <def>Human</def>
                <name><first>Ada</first></name>
                <healthTracker>
                  <hediffSet>
                    <hediffs>
                      <li>
                        <def>BloodLoss</def>
                        <severity>0.10</severity>
                      </li>
                    </hediffs>
                  </hediffSet>
                </healthTracker>
              </li>
            </pawnsAlive>
            <pawnsMothballed />
            <pawnsDead />
          </worldPawns>
          <factionManager><allFactions /></factionManager>
        </world>
      </game>
    </savegame>
    """
    current_xml = previous_xml.replace("<severity>0.10</severity>", "<severity>0.30</severity>")
    previous_snapshot = build_snapshot(previous_xml, tick=1000)
    current_snapshot = build_snapshot(current_xml, tick=2000)
    diff_context = DiffContext(
        previous_snapshot=previous_snapshot,
        current_snapshot=current_snapshot,
        previous_resolver=EntityResolver.from_snapshot(previous_snapshot),
        current_resolver=EntityResolver.from_snapshot(current_snapshot),
    )
    events = diff_health_states(diff_context, ticks_to_date=lambda tick: f"Tick {tick}")
    if not any(event.get("subcategory") == "hediff_severity_changed" for event in events):
        raise AssertionError("Expected a synthetic hediff_severity_changed event.")


def assert_output_contracts(
    json_path: str,
    text_path: str,
    expected_explicit_count: int,
) -> None:
    with open(json_path, encoding="utf-8") as handle:
        timeline = json.load(handle)
    explicit_count = sum(
        1 for event in timeline if not str(event.get("type", "")).startswith("inferred_")
    )
    if explicit_count != expected_explicit_count:
        raise AssertionError(
            f"Explicit event count changed for {json_path}: {explicit_count} != {expected_explicit_count}"
        )

    with open(text_path, encoding="utf-8") as handle:
        inferred_lines = [
            line.strip()
            for line in handle
            if line.strip().startswith("[")
            and any(prefix in line for prefix in ("HEALTH:", "RESEARCH:", "FACTION:"))
        ]
    leaking_lines = [line for line in inferred_lines if "None" in line]
    if leaking_lines:
        raise AssertionError(f"Found raw None in inferred TXT output: {leaking_lines[:5]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 4.5 validation checks.")
    parser.add_argument("--json", dest="json_path", required=True)
    parser.add_argument("--text", dest="text_path", required=True)
    parser.add_argument("--expected-explicit-count", type=int, required=True)
    args = parser.parse_args()

    if parse_float_value("0.25") != 0.25:
        raise AssertionError("parse_float_value failed to parse a valid float.")
    if parse_float_value(" null ") is not None:
        raise AssertionError("parse_float_value should ignore placeholder values.")

    assert_health_severity_diff_emits()
    assert_output_contracts(
        json_path=args.json_path,
        text_path=args.text_path,
        expected_explicit_count=args.expected_explicit_count,
    )


if __name__ == "__main__":
    main()
