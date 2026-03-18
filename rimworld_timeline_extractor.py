from __future__ import annotations

import argparse
import os
from pathlib import Path

from rimworld_pipeline.extractor import build_master_timeline, write_timeline_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract RimWorld timeline events into structured JSON."
    )
    parser.add_argument(
        "--dir",
        default=os.environ.get("RW_SAVE_DIR"),
        help="Directory containing save backups. Defaults to RW_SAVE_DIR.",
    )
    parser.add_argument(
        "--pattern",
        default=os.environ.get("RW_FILE_PATTERN", "*.zip"),
        help="Filename match pattern. Defaults to RW_FILE_PATTERN or *.zip.",
    )
    parser.add_argument(
        "--output",
        default="rimworld_timeline.json",
        help="Output JSON path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dir:
        raise ValueError("--dir was not provided and RW_SAVE_DIR is not set.")

    timeline_events = build_master_timeline(
        save_directory=Path(args.dir).expanduser().resolve(),
        file_pattern=args.pattern,
    )

    output_path = Path(args.output).expanduser().resolve()
    write_timeline_json(timeline_events=timeline_events, output_path=output_path)

    print(f"Extracted {len(timeline_events)} events to {output_path}")


if __name__ == "__main__":
    main()
