# ELC Math Modernization

Ontario Grade 11–12 math course materials for **ELC** (online), built for Canvas + Zoom.

## Current focus

- **Course:** MCF3M — Functions and Applications (Grade 11, University/College Preparation)
- **Semester:** 2026–2027 S1 (Sept 2026 – Jan 2027), currently in **prep** (summer 2026)

## Quick start for agents / humans

1. Read [`AGENTS.md`](AGENTS.md)
2. Check [`frameworks/semester.json`](frameworks/semester.json) for phase and key dates
3. For MCF3M expectations: `courses/MCF3M/curriculum/` (+ SQLite DB)

## Layout

| Path | Purpose |
|------|---------|
| `frameworks/` | Shared ELC school, class, semester, Canvas guidance |
| `courses/MCF3M/` | Course sources, curriculum DB, modules |
| `agents/` | Agent workflow definitions |
| `scripts/` | PDF extraction & expectation queries |
| `.cursor/rules/` | Always-on agent rules |

## Preserved sources

- Ontario curriculum PDF → `courses/MCF3M/sources/ontario-math-curriculum-gr-11-12.pdf`
- Canvas IMSCC export → `courses/MCF3M/sources/mcf3m-canvas-export.imscc`
- TLDSB calendar PDF → `frameworks/sources/tldsb-2026-27-school-year-calendar.pdf`

## Tooling

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Rebuild MCF3M expectations DB + markdown mirrors
python scripts/extract_mcf3m_expectations.py

# Query
python scripts/query_expectations.py search "quadratic"
python scripts/query_expectations.py search "sine" --kind specific
python scripts/query_expectations.py show A2.5
```
