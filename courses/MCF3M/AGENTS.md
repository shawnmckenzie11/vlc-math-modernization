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
- Async authoring rule: [`../../.cursor/rules/async-module-lessons.mdc`](../../.cursor/rules/async-module-lessons.mdc) · brief [`../../agents/async-module-lessons.md`](../../agents/async-module-lessons.md)
- Module 1 package: [`modules/01-change-and-transformation/`](modules/01-change-and-transformation/) (`python3 scripts/m1_build_async.py`)

## Canvas course structure

- Inventory (committed): [`canvas/INVENTORY.md`](canvas/INVENTORY.md), [`canvas/inventory.json`](canvas/inventory.json)
- Unpacked edit tree (gitignored): `canvas/unpacked/`
- Agent: [`agents/canvas-course-updater.md`](../../agents/canvas-course-updater.md)
- Skill: `.cursor/skills/canvas-course-updater/SKILL.md`

## Live lessons

Synchronous Zoom materials are **SMART Notebook** files under [`live-lessons/`](live-lessons/). Inventory with `python3 scripts/inventory_smart_notebook.py`. Agent brief: [`agents/smart-notebook-lessons.md`](../../agents/smart-notebook-lessons.md).


## Syllabus (draft)

Student-facing syllabus reflecting the rebuild ethos and mark breakdown: [`syllabus.md`](syllabus.md).  
Module 1 assessment source: [`sources/assessments/Change_and_Transformation_Assessment.docx`](sources/assessments/Change_and_Transformation_Assessment.docx).  
Canvas LMS syllabus stub (pending approval sync): `canvas/unpacked/course_settings/syllabus.html`.

## Target course plan (rebuild)

**Authoritative target IA:** [`course-plan.md`](course-plan.md) · [`course-plan.json`](course-plan.json)

| # | Title | Weeks | Legacy |
|--:|-------|------:|--------|
| 0 | Intro / housekeeping | 1 | Existing Module 0 |
| 1 | Change & Transformation | 3 | Merge old modules 1–4 (quadratic) |
| 2 | Trigonometry | 3 | Old module 5 |
| 3 | Waves | 3 | Old module 6 (periodic/sinusoidal) |
| 4 | Explosions | 3 | Old module 7 (exponential) |
| 5 | Finance | 3 | Old module 8 |
| — | Culminating / review + buffer | ~1 + ~1 | Before exams |

## Rebuild posture

Canvas modules/pages (`canvas/` inventory + unpacked working tree) and SMART Notebook files under `live-lessons/` are the **legacy baseline/archive**, not the target IA. Rebuilds remove/add/merge toward `course-plan.md`. Prefer regenerating inventories after structural edits; align sync ↔ async by **new module intent**, not legacy M1–M8 numbers. Preserve `sources/mcf3m-canvas-export.imscc` and `live-lessons/archives/MCF3M.zip` as archives.

## Agent checklist for MCF3M work

1. Load semester state (`frameworks/semester.json`)
2. Load target IA (`course-plan.md` / `course-plan.json`) — not legacy inventory order
3. Query expectations before writing lesson outcomes
4. Design for Canvas async + 2×75 Zoom + Friday office hours
5. Prefer expectation-aligned key questions and practice over generic worksheets
6. For sync class materials, consult `live-lessons/` inventory as legacy source (do not invent missing lessons)
7. For Canvas structural changes, use the Canvas course updater — read `canvas/INVENTORY.md` as baseline, build toward `course-plan.md`
8. When rebuilding, harness curriculum / semester / Canvas / Notebook agents; do not treat old module order as required
