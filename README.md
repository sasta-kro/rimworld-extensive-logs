# Extensive Logs

## What is Extensive Logs?

RimWorld generates incredible stories, but the game engine gradually forgets the details over time. Characters have deep conversations, form rivalries, and experience major life events. To save computer memory, the game deletes these detailed text logs after a short period.

Extensive Logs is a tool designed to permanently capture and save every single detail of a colony's history. By scanning frequent save files, it catches those temporary logs before they disappear and stitches them together into one perfect, chronological timeline.

This provides a massive, highly detailed text document of everything that happened during a playthrough. This extracted history is exceptionally helpful for creative projects. Writers can use the timeline as a strict reference guide for storytelling. Animators and artists can pull exact quotes and event sequences for videos. Additionally, creators can feed these rich, token-efficient text logs directly into artificial intelligence tools to automatically generate narratively accurate, novelized versions of their colony.

## The Data Extraction Problem

The RimWorld engine generates a massive amount of rich data, including minor social interactions, major historical events, and user interface notifications. This project solves the aggressive data loss caused by the game's internal garbage collector. It translates raw XML game data into readable text, providing a complete historical record without altering the original save files.

## Current Functionality

The Python script operates as a data pipeline. Its current capabilities include:

- **In-Memory Processing:** Reads raw XML data directly from sequential zip backup files without requiring manual extraction to the disk.
- **Comprehensive Data Extraction:** Targets and pulls data from the Tale Manager (major events), the PlayLog (social interactions), the Archive (UI letters and messages), and the Story Watcher (colony statistics).
- **Time Normalization:** Synchronizes absolute game ticks and relative game ticks, mathematically converting them into a unified in-game calendar (Year, Quadrum, Day) and a 24-hour clock.
- **Identity Resolution:** Scans the world pawn lists to translate raw internal identifiers into actual character names, tracking renames across different save files.
- **Smart Deduplication:** Uses distinct tracking variables and signature hashing to identify overlapping timeframes between save files, ensuring that no event or notification is printed twice.
- **Dual Output Formats:** Generates a structured JSON file for programmatic filtering and a compacted text file grouped by daily headers for easy reading and AI ingestion.

## Setup and Usage

**Preparation Checklist:**

- [ ] Ensure a Python environment is installed on the local machine.
- [ ] Gather sequential RimWorld save files (frequent backups are required for rich data).
- [ ] Place all target save files into a single, dedicated target directory.
- [ ] Update the configuration file to point to the correct folder.

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

## The End Goal and Roadmap

Currently, the project exists as a standalone Python pipeline. The long-term goal is to translate this logic into a lightweight, non-intrusive C# RimWorld mod. The mod version will bypass the need for external scripts and frequent zipped backups, quietly exporting the timeline directly from the game without altering core gameplay logic.

**Development Roadmap:**

- [x] Establish Python pipeline for raw XML parsing.
- [x] Implement time normalization and timeline sorting.
- [x] Implement identity resolution for standard pawns.
- [ ] Resolve temporary and non-standard pawn IDs.
- [ ] Port extraction logic into a C# RimWorld mod.
- [ ] Implement automated background text exporting.