# Agent guide — ELC Math Modernization

This repository builds **Ontario high school math courses for ELC** (online), starting with **MCF3M**.

## Always load first

1. [`frameworks/school.md`](frameworks/school.md) — ELC identity & online model  
2. [`frameworks/class-structure.md`](frameworks/class-structure.md) — 2×75 live + Friday office hours + async Canvas  
3. [`frameworks/semester.json`](frameworks/semester.json) — current semester phase & dates  
4. [`frameworks/canvas-lms.md`](frameworks/canvas-lms.md) — LMS constraints  

Course work also reads that course’s `courses/<CODE>/AGENTS.md`.

## Repo map

```
frameworks/     Shared school / class / semester / Canvas constants
courses/        Per-course content (MCF3M first)
agents/         Agent prompts & workflows
scripts/        Extraction & query tooling
.cursor/rules/  Always-on Cursor rules
.cursor/skills/ Project skills (semester, curriculum, canvas, smart-notebook)
```

## Non-negotiables

- Online ELC delivery (Canvas async + Zoom sync); not in-person defaults
- Ontario curriculum adherence; query expectations DB before inventing outcomes
- Semester-aware pacing from `frameworks/semester.json`
- Do **not** invent curriculum expectations; extract/query from sources
- Include docstrings on any new functions/methods
- Prefer teaching-content conventions over generic app-code patterns
- Do not commit unless Shawn asks


## Course inheritance & agent harness

Every course inherits shared ELC constants under `frameworks/` (school, class structure, semester, Canvas LMS). New courses copy the `courses/MCF3M/` shape: `AGENTS.md`, `sources/`, `curriculum/`, `canvas/`, `live-lessons/`, `modules/`.

For trickle-down work, **harness the specialized agents** rather than reinventing workflows:

| Concern | Agent / tooling |
|---------|-----------------|
| Curriculum expectations | [`agents/curriculum-extractor.md`](agents/curriculum-extractor.md) · `scripts/query_expectations.py` |
| Semester / pacing | [`agents/semester-context.md`](agents/semester-context.md) · `frameworks/semester.json` |
| Canvas structure (IMSCC) | [`agents/canvas-course-updater.md`](agents/canvas-course-updater.md) · `scripts/canvas_*.py` |
| Sync Zoom lessons (Notebook) | [`agents/smart-notebook-lessons.md`](agents/smart-notebook-lessons.md) · `live-lessons/` inventory |
| Async module lessons (DB → HTML) | [`agents/async-module-lessons.md`](agents/async-module-lessons.md) · `.cursor/rules/async-module-lessons.mdc` · `courses/*/modules/` |

## Rebuild posture (MCF3M and later courses)

Current Canvas modules/pages and SMART Notebook lesson trees are a **baseline archive**, not a frozen information architecture. Rebuilds may remove, add, or merge modules and lessons. Do **not** treat inventory titles or order as immutable requirements.

- **MCF3M target IA:** [`courses/MCF3M/course-plan.md`](courses/MCF3M/course-plan.md) (Module 0 + five themed 3-week modules + culminating/buffer). Legacy 8-module Canvas/Notebook structure maps into that plan.
- Preserve source archives (`.imscc` under `sources/`, `live-lessons/archives/`) when restructuring; edit working copies / produce new structures deliberately.
- After structural changes, regenerate inventories; link new/changed content to curriculum expectations where relevant.
- Keep sync (Notebook) and async (Canvas) aligned by **module intent**, not by old numbering alone.

## Active course

**MCF3M** — see [`courses/MCF3M/AGENTS.md`](courses/MCF3M/AGENTS.md)

## Agent entry points

| Agent | Path | Use when |
|-------|------|----------|
| Semester context | [`agents/semester-context.md`](agents/semester-context.md) | Pacing, calendars, “what week” |
| Curriculum extractor | [`agents/curriculum-extractor.md`](agents/curriculum-extractor.md) | Extract/update/query expectations |
| Canvas course updater | [`agents/canvas-course-updater.md`](agents/canvas-course-updater.md) | Modules/pages/IMSCC edits, Canvas re-pack |
| SMART Notebook live lessons | [`agents/smart-notebook-lessons.md`](agents/smart-notebook-lessons.md) | Sync Zoom `.notebook` inventory, module mapping, future extraction |
| Async module lessons | [`agents/async-module-lessons.md`](agents/async-module-lessons.md) | Student async pages from question DB; smart IDs; Explore UX |
