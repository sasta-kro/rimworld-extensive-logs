from __future__ import annotations

import argparse
from pathlib import Path

from rimworld_pipeline.formatter import convert_json_file_to_text_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert structured timeline JSON into compact narrative text lines."
    )
    parser.add_argument(
        "--input",
        default="your_output.json",
        help="Input timeline JSON file.",
    )
    parser.add_argument(
        "--output",
        default="timeline_text.txt",
        help="Output text timeline file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()

    convert_json_file_to_text_file(
        timeline_json_path=input_path,
        timeline_text_output_path=output_path,
    )

    print(f"Wrote text timeline to {output_path}")


if __name__ == "__main__":
    main()
