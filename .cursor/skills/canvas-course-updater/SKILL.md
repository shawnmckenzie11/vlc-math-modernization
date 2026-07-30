---
name: canvas-course-updater
description: >-
  Unpacks, inventories, and structurally updates the MCF3M Canvas Common
  Cartridge (.imscc) course — modules, pages, assignments, quizzes, reorder,
  and re-pack for import. Use when editing Canvas modules/pages, IMSCC/
  imsmanifest/wiki_content, or when the user mentions Canvas course updates,
  Common Cartridge, or mcf3m-canvas-export.
---

# Canvas course updater

## Instructions

1. Read `courses/MCF3M/canvas/INVENTORY.md` (or `inventory.json`) before editing.
2. Load ELC Canvas constraints from `frameworks/canvas-lms.md` and course notes in `courses/MCF3M/AGENTS.md`.
3. Work in `courses/MCF3M/canvas/unpacked/` (gitignored). Source archive: `courses/MCF3M/sources/mcf3m-canvas-export.imscc`.
4. Prefer scripts for scaffold/inventory; do not invent curriculum expectation codes — query `courses/MCF3M/curriculum/mcf3m.sqlite`.
5. After structural changes, regenerate inventory with `python3 scripts/canvas_inventory.py`.
6. Follow the full brief in `agents/canvas-course-updater.md`.

## Commands

```bash
python3 scripts/canvas_unpack.py --clean
python3 scripts/canvas_inventory.py
python3 scripts/canvas_add_module.py --title "Module N: Title" --pages "Learning Goals" "Lesson 1"
python3 scripts/canvas_pack.py
```

## Key paths

- `agents/canvas-course-updater.md`
- `courses/MCF3M/canvas/`
- `scripts/canvas_unpack.py`
- `scripts/canvas_inventory.py`
- `scripts/canvas_add_module.py`
- `scripts/canvas_pack.py`
