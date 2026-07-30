# Canvas LMS constraints

## Role of Canvas

Canvas is the **system of record** for:

- Module / lesson pages (async content)
- Assignments, quizzes, and gradebook
- Course navigation and student pacing cues

Zoom handles live interaction; Canvas should still tell students *when* live sessions happen and *what* to complete before/after.

## Content conventions

- Prefer Canvas Pages and Module items over long detached PDFs when possible
- One clear learning goal per page or short page sequence
- Link curriculum expectation codes (e.g. `A2.5`) where useful for teacher/agent alignment; student language can stay plain
- Existing course structure: IMSCC archive in `courses/MCF3M/sources/mcf3m-canvas-export.imscc`
- Working unpack: `courses/MCF3M/canvas/unpacked/` (gitignored)
- Committed inventory: `courses/MCF3M/canvas/INVENTORY.md` + `inventory.json`
- Structural edits: [`agents/canvas-course-updater.md`](../agents/canvas-course-updater.md)

## Agent rules

- Do not assume in-person handouts or whiteboard-only activities without a Canvas equivalent
- When drafting lessons, produce Canvas-ready structure (title, outcomes, instructions, practice, submit)
- Keep file paths and media portable for Canvas upload
- Large binary course exports stay in `courses/<CODE>/sources/`; do not commit unpacked IMSCC trees — commit inventory instead
- Use `scripts/canvas_*.py` for unpack / inventory / module scaffold / re-pack
- Note: `canvas_add_module.py` rewrites `module_meta.xml` / `imsmanifest.xml` via ElementTree (may reformat whitespace); smoke-test import before student-facing use
