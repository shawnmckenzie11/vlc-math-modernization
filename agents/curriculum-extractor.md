# Curriculum extractor agent (MCF3M)

## Purpose

Extract, store, and query **Ontario MCF3M** overall/specific expectations and linked examples. Never invent expectations.

## Sources

- Curriculum PDF: `courses/MCF3M/sources/ontario-math-curriculum-gr-11-12.pdf` (MCF3M section ~pp. 59–68)
- Canvas IMSCC (course structure, not expectation wording): `courses/MCF3M/sources/mcf3m-canvas-export.imscc`

## Outputs

| Artifact | Path |
|----------|------|
| SQLite DB | `courses/MCF3M/curriculum/mcf3m.sqlite` |
| Markdown mirrors | `courses/MCF3M/curriculum/*.md` |
| Verified seed data | `courses/MCF3M/curriculum/expectations_seed.json` |

## Workflow

1. Confirm PDF path and MCF3M page range (stop at MBF3C / Foundations for College).
2. Run: `python scripts/extract_mcf3m_expectations.py`
3. Spot-check codes against the PDF (overall vs specific; sample problems linked).
4. Query: `python scripts/query_expectations.py search "<topic>"`
5. If PDF parsing fails for a fragment, keep prior verified seed text and mark `verification_status` accordingly — **do not fabricate**.

## Schema (SQLite)

- `overall_expectations` — strand, code, statement, topics
- `specific_expectations` — FK to overall, code, statement, topics
- `examples` — FK to specific (or overall), example text
- FTS / LIKE search via topics + statement text (see query script)

## Related skill

`.cursor/skills/curriculum-extractor/SKILL.md`
