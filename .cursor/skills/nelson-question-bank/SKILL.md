---
name: nelson-question-bank
description: >-
  Extract, deep-curate, browse, and delete textbook reference questions (Nelson
  Functions 11 for MCF3M; same pipeline for later modules and other courses).
  Use when working on nelson_*.sqlite, curation patches, nelson-questions browse
  UI, verified_inclusion, answers DB checks, or promoting textbook items toward
  live Canvas lesson seeds.
---

# Textbook / Nelson question bank

## Load first

1. [`frameworks/textbook-question-bank.md`](../../../frameworks/textbook-question-bank.md)
2. [`.cursor/rules/nelson-question-bank.mdc`](../../rules/nelson-question-bank.mdc)
3. [`agents/nelson-question-bank.md`](../../../agents/nelson-question-bank.md)
4. Active module `questions/*_README.md` (MCF3M M1: `NELSON_README.md`)
5. Course `AGENTS.md` + `course-plan.md` when choosing chapters for a module

## Separate from live lessons

- Reference bank ≠ `m*_questions.sqlite` / `seed_data.py`
- For student async HTML, use the **async-module-lessons** skill after enrichment mapping

## MCF3M Module 1 commands

```bash
python3 scripts/m1_build_nelson_browse.py
python3 scripts/nelson_browse_server.py
# Hub: http://127.0.0.1:8765/nelson-browse.html
# Ch1: http://127.0.0.1:8765/ch1/nelson-questions.html
# (compat root still serves Module 1: /nelson-questions.html)
```

Deep-curate: PDF → stem (AU rules) → answers check → `verified_inclusion` → `questions/curation/*.json`.

Delete: only via browse server API (or sqlite), not by editing generated JSON alone.

## MCF3M Modules 2–5 (raw extract scaffolding)

Map: `courses/MCF3M/sources/nelson/CHAPTER_MODULE_MAP.md`

```bash
python3 scripts/extract_nelson_chapter.py --chapter 5   # etc. 4–8
python3 scripts/build_nelson_browse.py --module 03-trigonometry
python3 scripts/nelson_browse_server.py   # hub + /ch4 /ch5 /ch6 /ch7 /ch8
# Ch5: http://127.0.0.1:8765/ch5/nelson-questions.html
# Ch7: http://127.0.0.1:8765/ch7/nelson-questions.html
# Ch8: http://127.0.0.1:8765/ch8/nelson-questions.html
```

Finance (Module 5) uses separate banks/mounts: `build_nelson_browse.py --mount ch7` / `--mount ch8`.

All new rows start `verified_inclusion=0` until a Module-1-quality deep-curate pass.

## Do not

- Re-extract over curated rows without re-curating
- Set `verified_inclusion=1` on garbled OCR stems
- Treat enrichment-map candidates as already live lesson items
- Commit unless Shawn asks

## Multi-module / multi-course

Follow path layout and generalization notes in `frameworks/textbook-question-bank.md`. Prefer `--db` / `--module` flags over forked one-off scripts.
