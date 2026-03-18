from __future__ import annotations

import argparse
from pathlib import Path

from rimworld_pipeline.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RimWorld timeline extraction and text conversion pipeline."
    )
    parser.add_argument(
        "--config",
        default="pipeline_config.json",
        help="Path to pipeline config JSON file. Defaults to pipeline_config.json.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()

    json_output_path, text_output_path, event_count = run_pipeline(config_path)

    print(f"Pipeline completed. Extracted {event_count} events.")
    print(f"Structured timeline: {json_output_path}")
    print(f"Token-efficient text timeline: {text_output_path}")


if __name__ == "__main__":
    main()
