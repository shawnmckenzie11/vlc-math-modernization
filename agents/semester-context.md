# Semester context agent

## Purpose

Keep all planning **semester-aware**: phase, instructional dates, PD days, holidays, and exam windows for the semester Shawn is preparing for or teaching.

## Always do first

1. Read [`frameworks/semester.json`](../frameworks/semester.json)
2. Skim [`frameworks/semester.md`](../frameworks/semester.md) if human context helps
3. State the active semester, `current_phase`, and any date conflicts with the user’s request

## Phase meanings

| Phase | Meaning |
|-------|---------|
| `preparing` | Pre-term / summer build; no live classes yet |
| `in_session` | Instructional days in progress |
| `exam` | Secondary exam window |
| `break` | Board/stat multi-day break (e.g. winter break) |

## Pacing rules

- Do not schedule required student work on holidays/PD days listed in `semester.json`
- Leave buffer before the exam window for review
- In `preparing`, prioritize course structure, modules, and Canvas readiness over “this week’s homework”
- Live-class count must fit remaining instructional weeks (2×75 min/week)

## Updating semester state

When Shawn changes semester or the board publishes a final calendar:

1. Download/update PDF under `frameworks/sources/`
2. Parse key dates (or update manually from the PDF grid)
3. Update `frameworks/semester.json` (`as_of`, `current_phase`, date arrays)
4. Sync narrative in `frameworks/semester.md`
5. Optionally move the previous JSON to `frameworks/archive/`

## Related skill

`.cursor/skills/semester-context/SKILL.md`
