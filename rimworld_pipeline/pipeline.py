from __future__ import annotations

from pathlib import Path

from rimworld_pipeline.config import load_runtime_config
from rimworld_pipeline.extractor import build_master_timeline, write_timeline_json
from rimworld_pipeline.formatter import write_text_timeline, convert_timeline_to_text_lines


def run_pipeline(config_path: Path) -> tuple[Path, Path, int]:
    runtime_config = load_runtime_config(config_path)

    timeline_events = build_master_timeline(
        save_directory=runtime_config.pipeline.save_directory,
        file_pattern=runtime_config.pipeline.file_pattern,
    )

    write_timeline_json(
        timeline_events=timeline_events,
        output_path=runtime_config.pipeline.timeline_json_output_path,
    )

    text_lines = convert_timeline_to_text_lines(timeline_events)
    write_text_timeline(
        text_lines=text_lines,
        output_path=runtime_config.pipeline.timeline_text_output_path,
    )

    return (
        runtime_config.pipeline.timeline_json_output_path,
        runtime_config.pipeline.timeline_text_output_path,
        len(timeline_events),
    )
