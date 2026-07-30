# SMART Notebook live-lessons agent

## Purpose

Inventory, organize, and (later) extract **SMART Notebook** synchronous live-lesson files for ELC math courses—starting with **MCF3M**. Delivery medium for live Zoom classes is SMART Notebook (`.notebook`).

## Always load first

1. [`frameworks/school.md`](../frameworks/school.md) — online ELC model  
2. [`frameworks/class-structure.md`](../frameworks/class-structure.md) — 2×75 live Zoom + Friday office hours  
3. Course notes: [`courses/MCF3M/AGENTS.md`](../courses/MCF3M/AGENTS.md)  
4. Live-lessons README: [`courses/MCF3M/live-lessons/README.md`](../courses/MCF3M/live-lessons/README.md)


## Rebuild posture

Module folders and `.notebook` files under `live-lessons/modules/` are a **baseline archive**, not frozen course IA. Rebuilds may reorganize, merge, or retire lessons. Preserve `live-lessons/archives/MCF3M.zip`; restructure working copies deliberately and refresh inventory. Align with Canvas modules by learning intent, not legacy numbers alone.

## Sources (MCF3M)

| Artifact | Path |
|----------|------|
| Original zip | `courses/MCF3M/live-lessons/archives/MCF3M.zip` |
| Extracted tree | `courses/MCF3M/live-lessons/modules/` |
| Inventory | `courses/MCF3M/live-lessons/inventory.json` (+ `.md`) |

Do **not** modify or delete `~/Downloads/MCF3M.zip`; the repo holds a copy.

## Phase 1 — store & inventory (current)

1. Confirm files under `courses/MCF3M/live-lessons/modules/`.
2. Refresh catalog: `python3 scripts/inventory_smart_notebook.py`
3. Answer “what lessons exist for module X?” from `inventory.json` / `inventory.md`.
4. Prefer inferred codes (`M1L2`, `M6L1`, …) and teacher vs student variants.
5. Map folders to Canvas module titles when known; do not invent curriculum expectation codes—query `courses/MCF3M/curriculum/mcf3m.sqlite` via `scripts/query_expectations.py` when linking.

### Naming / organization conventions

- Keep source folder names (including the Module 6 `Sinusodial` spelling).
- Teacher file = no `(student)` suffix; student file = `(student)` / `(student 2)`.
- Special folders: `Exam Outline`, `Learning Skills` (not numbered modules).

## Phase 2 — extract & align (future)

`.notebook` files are ZIP archives. Future work (do not run unless Shawn asks):

1. Unzip a single `.notebook` into a scratch dir (never commit extracted internals by default).
2. Inventory internal pages / media / text XML.
3. Produce lesson summaries suitable for 75-min Zoom planning.
4. Suggest links to MCF3M expectations (query DB; never invent codes).
5. Relate live lessons to Canvas async modules under `courses/MCF3M/modules/` when those exist.

## Constraints

- Live lessons support sync Zoom; Canvas async pages remain the standalone student path.
- Do not invent Ontario curriculum expectations.
- Docstrings on any new script functions.
- Do not commit unless Shawn asks.

## Related skill

`.cursor/skills/smart-notebook-lessons/SKILL.md`
