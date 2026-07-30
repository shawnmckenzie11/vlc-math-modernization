# MCF3M — agent notes

Inherits all root [`AGENTS.md`](../../AGENTS.md) and [`frameworks/`](../../frameworks/) constants.

## Course

| Field | Value |
|-------|--------|
| Code | MCF3M |
| Title | Functions and Applications |
| Grade / pathway | 11 University/College Preparation |
| Prerequisites | MPM2D or MFM2P |

## Strands

- **A** — Quadratic Functions  
- **B** — Exponential Functions  
- **C** — Trigonometric Functions  

Plus mathematical process expectations (integrated across the course).

## Local paths

- Sources: [`sources/`](sources/) (includes `mcf3m-canvas-export.imscc`)
- Curriculum DB / mirrors: [`curriculum/`](curriculum/)
- Canvas working tree + inventory: [`canvas/`](canvas/)
- Live lessons (SMART Notebook): [`live-lessons/`](live-lessons/)
- Modules (Canvas async drafts): [`modules/`](modules/)

## Canvas course structure

- Inventory (committed): [`canvas/INVENTORY.md`](canvas/INVENTORY.md), [`canvas/inventory.json`](canvas/inventory.json)
- Unpacked edit tree (gitignored): `canvas/unpacked/`
- Agent: [`agents/canvas-course-updater.md`](../../agents/canvas-course-updater.md)
- Skill: `.cursor/skills/canvas-course-updater/SKILL.md`

## Live lessons

Synchronous Zoom materials are **SMART Notebook** files under [`live-lessons/`](live-lessons/). Inventory with `python3 scripts/inventory_smart_notebook.py`. Agent brief: [`agents/smart-notebook-lessons.md`](../../agents/smart-notebook-lessons.md).


## Rebuild posture

Canvas modules/pages (`canvas/` inventory + unpacked working tree) and SMART Notebook files under `live-lessons/` are the **current baseline/archive**, not a permanent IA. Upcoming MCF3M rebuilds will remove, add, and merge modules and lessons. Prefer regenerating inventories after structural edits; align sync ↔ async by learning intent, not legacy module numbers. Preserve `sources/mcf3m-canvas-export.imscc` and `live-lessons/archives/MCF3M.zip` as archives.

## Agent checklist for MCF3M work

1. Load semester state (`frameworks/semester.json`)
2. Query expectations before writing lesson outcomes
3. Design for Canvas async + 2×75 Zoom + Friday office hours
4. Prefer expectation-aligned key questions and practice over generic worksheets
5. For sync class materials, consult `live-lessons/` inventory (do not invent missing lessons)
6. For Canvas structural changes, use the Canvas course updater — read `canvas/INVENTORY.md` first (baseline, not frozen)
7. When rebuilding, harness curriculum / semester / Canvas / Notebook agents; do not treat old module order as required
