from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


WORLD_SAVE_MEMBER_PATH = "world/000_save"


@dataclass(frozen=True)
class SaveSource:
    source_type: str
    path: Path


@dataclass(frozen=True)
class MapSnapshot:
    member_path: str
    map_id: str
    root: ET.Element


@dataclass(frozen=True)
class SaveSnapshot:
    source_path: Path
    source_type: str
    world_root: ET.Element
    map_snapshots: list[MapSnapshot]
    ticks_game: int
    game_start_abs_tick: int


def map_save_member_paths(archive_file: zipfile.ZipFile) -> list[str]:
    return [
        archive_member_name
        for archive_member_name in archive_file.namelist()
        if archive_member_name.startswith("maps/")
        and archive_member_name.endswith("_save")
        and archive_member_name != "maps/000_save"
    ]


def infer_map_id_from_member_path(member_path: str) -> str:
    member_name = Path(member_path).name
    return member_name.removesuffix("_save")


def load_map_snapshots(archive_file: zipfile.ZipFile) -> list[MapSnapshot]:
    map_snapshots: list[MapSnapshot] = []

    for map_member_path in map_save_member_paths(archive_file):
        with archive_file.open(map_member_path, "r") as map_xml_stream:
            map_snapshots.append(
                MapSnapshot(
                    member_path=map_member_path,
                    map_id=infer_map_id_from_member_path(map_member_path),
                    root=ET.parse(map_xml_stream).getroot(),
                )
            )

    return map_snapshots

