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
.cursor/skills/ Project skills (semester, curriculum)
```

## Non-negotiables

- Online ELC delivery (Canvas async + Zoom sync); not in-person defaults
- Ontario curriculum adherence; query expectations DB before inventing outcomes
- Semester-aware pacing from `frameworks/semester.json`
- Do **not** invent curriculum expectations; extract/query from sources
- Include docstrings on any new functions/methods
- Prefer teaching-content conventions over generic app-code patterns
- Do not commit unless Shawn asks

## Active course

**MCF3M** — see [`courses/MCF3M/AGENTS.md`](courses/MCF3M/AGENTS.md)

## Agent entry points

| Agent | Path | Use when |
|-------|------|----------|
| Semester context | [`agents/semester-context.md`](agents/semester-context.md) | Pacing, calendars, “what week” |
| Curriculum extractor | [`agents/curriculum-extractor.md`](agents/curriculum-extractor.md) | Extract/update/query expectations |
