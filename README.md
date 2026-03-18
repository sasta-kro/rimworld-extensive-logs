# Extensive Logs

## Overview

Extensive Logs is a data extraction tool designed for RimWorld. The game engine generates a massive amount of rich data, including minor social interactions, major historical events, and UI notifications. However, to save memory, the game aggressively deletes temporary messages and unrecorded conversations as time passes.

This project solves that data loss by parsing frequent backup save files, capturing those temporary logs before they disappear, and stitching them together into a single, perfectly chronological timeline. It translates raw XML game data into readable text, providing a complete historical record of a colony.

## The End Goal

The immediate purpose of this extracted timeline is for use with Large Language Models. By feeding the highly compressed, token-efficient text logs into an LLM, users can generate detailed, narratively accurate stories based on the actual events of their playthrough.

Currently, the project exists as a standalone Python pipeline. The long-term goal is to translate this logic into a lightweight, non-intrusive C# RimWorld mod. The mod version will bypass the need for external scripts and frequent zipped backups, quietly exporting the timeline directly from the game without altering core gameplay logic.

## Current Functionality

The Python script operates as an ETL (Extract, Transform, Load) pipeline. Its current capabilities include:

- **In-Memory Processing:** Reads raw XML data directly from sequential `.zip` backup files without requiring manual extraction to the disk.
- **Comprehensive Data Extraction:** Targets and pulls data from the Tale Manager (major events), the PlayLog (social interactions), the Archive (UI letters and messages), and the Story Watcher (colony statistics).
- **Time Normalization:** Synchronizes absolute game ticks and relative game ticks, mathematically converting them into a unified in-game calendar (Year, Quadrum, Day) and a 24-hour clock.
- **Identity Resolution:** Scans the world pawn lists to translate raw internal identifiers into actual character names, tracking renames across different save files.
- **Smart Deduplication:** Uses distinct tracking variables and signature hashing to identify overlapping timeframes between save files, ensuring that no event or notification is printed twice.
- **Dual Output Formats:** Generates a structured JSON file for programmatic filtering and a compacted text file grouped by daily headers for easy reading and LLM ingestion.

## Setup and Usage

The pipeline requires a target directory containing sequential RimWorld save files.

Configuration is managed via a `pipeline_config.json` file located in the root directory. Users must specify the path to their save directory and a file pattern to match the target colony saves.

Example configuration:

```json
{
  "pipeline": {
    "save_directory": "./_tests/2saves",
    "file_pattern": "*Dilunasol*",
    "timeline_json_output_path": "./outputs/rimworld_timeline.json",
    "timeline_text_output_path": "./outputs/rimworld_timeline.txt"
  }
}

```

Execution is handled by running the main entry point from the terminal:

```bash
python run_pipeline.py --config pipeline_config.json

```

## Known Limitations and Active Development

This project is in active development. Features and extraction logic are subject to change. Current known behaviors include:

- **Backup Dependency:** Because the script relies on capturing data before the game's internal garbage collector deletes it, users must create frequent save backups (approximately every 15 to 30 minutes) to capture a rich history of transient UI notifications.
- **Unresolved Pawn IDs:** Temporary entities like enemy raiders, traders, or wild animals are often not saved to the global pawn dictionary by the game. These entities may appear in the final logs as raw identifiers (e.g., Thing_Human116478) rather than standard names.
- **Event Clumping:** Certain minor UI messages lack internal timestamps. The script attempts to place them chronologically based on the save file's master timestamp, which can occasionally result in minor events clumping at specific hours.