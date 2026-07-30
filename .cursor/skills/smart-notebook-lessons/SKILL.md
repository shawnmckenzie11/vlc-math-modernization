---
name: smart-notebook-lessons
description: >-
  Inventories and organizes MCF3M SMART Notebook (.notebook) live Zoom lessons,
  maps files to modules, and prepares for future .notebook ZIP extraction and
  curriculum alignment. Use when working with live lessons, SMART Notebook,
  sync class materials, module lesson files, or courses/MCF3M/live-lessons/.
---

# SMART Notebook live lessons

## Instructions

1. Read `courses/MCF3M/live-lessons/README.md` for provenance and storage layout.
2. Prefer the inventory over ad-hoc finds:
   - `courses/MCF3M/live-lessons/inventory.json`
   - `courses/MCF3M/live-lessons/inventory.md`
3. Refresh inventory after adding/removing files:
   `python3 scripts/inventory_smart_notebook.py`
4. Answer module questions from folder names (`Module N - …`) and inferred lesson codes (`M1L2`, etc.).
5. Distinguish **teacher** vs **student** `.notebook` variants (`(student)` in the filename).
6. For curriculum links, query expectations — do not invent codes:
   `python3 scripts/query_expectations.py search "keyword"`
7. Phase 2 (only when asked): treat `.notebook` as a ZIP; extract to a temp/scratch path; summarize; do not commit raw internals unless Shawn requests it.

## Key files

- `agents/smart-notebook-lessons.md`
- `scripts/inventory_smart_notebook.py`
- `courses/MCF3M/live-lessons/`
- `courses/MCF3M/curriculum/mcf3m.sqlite`

## Delivery context

Live materials are for **2×75 min Zoom** classes (SMART Notebook). Friday office hours are flexible support. Canvas async modules stay separate under `courses/MCF3M/modules/`.
