# Textbook / Nelson question bank (agent brief)

When extracting, curating, browsing, or deleting **textbook reference** questions (Nelson Functions 11 for MCF3M today; same process for later modules and other courses), follow:

1. Framework: [`frameworks/textbook-question-bank.md`](../frameworks/textbook-question-bank.md)
2. Cursor rule: [`.cursor/rules/nelson-question-bank.mdc`](../.cursor/rules/nelson-question-bank.mdc)
3. Skill: [`.cursor/skills/nelson-question-bank/SKILL.md`](../.cursor/skills/nelson-question-bank/SKILL.md)
4. Course `AGENTS.md` + active module `questions/*_README.md`

## Purpose

Build a **verified reference corpus** from the course textbook PDF so agents/teachers can shortlist items into live Canvas lesson banks. This is **not** the student-facing async DB.

## Shawn shorthand

- **QU:** one-off bank fix for the current task only.
- **AU:** stem/figure/verification rules → update the rule + framework + this brief; apply to all future textbook banks.

## Non-negotiables

- Two DBs: reference (`nelson_*.sqlite` / textbook bank) ≠ live (`m*_questions.sqlite`)
- Do not re-run raw extract over a curated bank without a curation pass afterward
- `verified_inclusion=1` only after PDF stem + answers check (or intentional open task)
- Browse deletes require `python3 scripts/nelson_browse_server.py` (not plain `http.server`)
- Prefer `questions/curation/*.json` patches for reproducible deep-curate work
- Do not commit unless Shawn asks

## MCF3M Module 1 (reference implementation)

| Item | Path |
|------|------|
| PDF | `courses/MCF3M/sources/nelson-functions-11.pdf` (printed ≈ PDF − 10) |
| Answers | `courses/MCF3M/sources/nelson/answers_ch1_3.sqlite` |
| Glossary | `courses/MCF3M/sources/nelson/glossary.sqlite` |
| Bank + assets | `courses/MCF3M/modules/01-change-and-transformation/questions/` |
| Status README | `…/questions/NELSON_README.md` |
| Enrichment → live | `…/questions/M1_ENRICHMENT_MAP.md` |

### Standard commands

```bash
# Assemble / refresh Chapter 1 bank from curated pieces + patches
python3 scripts/build_nelson_ch1_bank.py
python3 scripts/apply_nelson_curation_patches.py \
  courses/MCF3M/modules/01-change-and-transformation/questions/curation/*.json

# Regenerate browse UI
python3 scripts/m1_build_nelson_browse.py

# Preview with delete-from-DB (+ chapter hub /ch4 /ch5 /ch6)
python3 scripts/nelson_browse_server.py
# → http://127.0.0.1:8765/nelson-browse.html
# → http://127.0.0.1:8765/ch1/nelson-questions.html
```

### Deep-curate loop (per section)

1. Filter browse to **Needs review** (or target section).
2. Reconstruct stems from PDF; fix figures (inline, labeled crops).
3. Check `answers_*.sqlite` (or work the math for open tasks).
4. Set `verified_inclusion=1`; write/update `curation/<section>.json`.
5. Rebuild browse; leave intentional stubs (e.g. duplicate fragments) unverified or delete via UI.

## Later MCF3M modules

- Map textbook chapters to [`courses/MCF3M/sources/nelson/CHAPTER_MODULE_MAP.md`](../courses/MCF3M/sources/nelson/CHAPTER_MODULE_MAP.md) (aligned with [`course-plan.md`](../courses/MCF3M/course-plan.md)).
- Extract: `python3 scripts/extract_nelson_chapter.py --chapter N` (Ch1 refused unless `--force`).
- Answers Ch4–8: `extract_nelson_answers_ch1_3.py --printed-start 645 --printed-end 685 --max-chapter 8 --db …/answers_ch4_8.sqlite`.
- Browse: `python3 scripts/build_nelson_browse.py --module <slug>` · `nelson_browse_server.py` (hub + `/ch4` `/ch5` `/ch6` `/ch7` `/ch8`).
- Multi-chapter modules (Finance): separate banks `nelson_ch7.sqlite` / `nelson_ch8.sqlite` with mounts `--mount ch7` / `--mount ch8` (async under `async/ch7/`, `async/ch8/`). Optional archive merge via `merge_nelson_chapter_banks.py` is not used by browse.
- Promote via a new `M*_ENRICHMENT_MAP.md` into that module’s live seed after deep-curate.

## Other courses

1. Copy `courses/MCF3M/` shape; add textbook PDF under `sources/`.
2. Extract answers/glossary into `sources/<slug>/`.
3. Reuse AU rules and schema pattern; rename files to the textbook slug.
4. Generalize scripts with flags when the one-off `m1_*` / `nelson_*` names become painful — keep behavior identical.

## Handoff to live Canvas lessons

After verification, use async-module-lessons:

- Rewrite stems into student/life voice and correct sequencing
- Assign live smart IDs + curriculum expectations
- Build with the module’s `m*_build_async.py` (or successor)

Do **not** ship raw Nelson HTML into Canvas pages as the lesson bank.
