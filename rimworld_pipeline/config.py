from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    save_directory: Path
    file_pattern: str
    timeline_json_output_path: Path
    timeline_text_output_path: Path


@dataclass(frozen=True)
class RuntimeConfig:
    pipeline: PipelineConfig


def load_runtime_config(config_path: Path) -> RuntimeConfig:
    # Keeping configuration outside code is reducing edit risk during routine runs.
    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    pipeline_section = config_payload["pipeline"]

    return RuntimeConfig(
        pipeline=PipelineConfig(
            save_directory=Path(pipeline_section["save_directory"]).expanduser(),
            file_pattern=pipeline_section["file_pattern"],
            timeline_json_output_path=Path(
                pipeline_section["timeline_json_output_path"]
            ).expanduser(),
            timeline_text_output_path=Path(
                pipeline_section["timeline_text_output_path"]
            ).expanduser(),
        )
    )
