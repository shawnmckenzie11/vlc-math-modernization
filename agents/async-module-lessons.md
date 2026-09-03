# Async module lessons (agent brief)

When authoring or regenerating Canvas async modules under `courses/*/modules/`, follow:

- Cursor rule: [`.cursor/rules/async-module-lessons.mdc`](../.cursor/rules/async-module-lessons.mdc)
- Project skill (if present): `.cursor/skills/async-module-lessons/SKILL.md`

## Shawn shorthand (agents only)

- **QU** (Quick Update): one-off module tweak for the current task. Do **not** promote into `.cursor/rules/` or lasting agent rules.
- **AU** (Always Update): onboard into the async-module-lessons rule / skill / this brief, and implement for the active module **and** all future modules.

## Textbook / Nelson reference bank (AU)

Reference extraction is a **separate pipeline** from this live lesson DB.

- Framework: [`frameworks/textbook-question-bank.md`](../frameworks/textbook-question-bank.md)
- Agent / skill: [`agents/nelson-question-bank.md`](nelson-question-bank.md) · `.cursor/skills/nelson-question-bank/SKILL.md`
- Stem/figure rule: [`.cursor/rules/nelson-question-bank.mdc`](../.cursor/rules/nelson-question-bank.mdc)
- MCF3M Module 1 status: `courses/MCF3M/modules/01-change-and-transformation/questions/NELSON_README.md`

Key stem rules: no leading Q#; figures inlined with parts; no redundant table+crop; stand-alone follow-ups; currency/prose out of `$…$` KaTeX. Promote verified items via enrichment maps into **rewritten** live seeds — do not paste textbook stems into student pages unchanged.

## Module 1 (MCF3M) reference implementation

- Package: `courses/MCF3M/modules/01-change-and-transformation/`
- Build: `python3 scripts/m1_build_async.py`
- Outputs: `async/index.html` (lesson), `async/questions.html` (ID browser), `questions/m1_questions.sqlite`
- Seed: `questions/seed_data.py` + `questions/schema.sql`
- Local media: `async/assets/` (relative paths from HTML)

Do not hand-edit generated HTML as source of truth. Prefer mining legacy Canvas / Notebook banks, then rewrite in student voice with correct sequencing.

## Rendering conventions (AU — all modules)

- **In-repo assets** — module images live under `async/assets/` (or `media/`) with relative refs for Canvas porting; not remote-only.
- **Section titles (AU)** — Title Case with `{module}.{section}` prefix (`1.1 Relationships We Can Trust`). Shawn shorthand: **S1.1**, **S1.2**, … from `sort_order`. Keep smart IDs stable; map display index ↔ `section_key` in the module README.
- **Mandatory section sequence (AU)** — every section: **Minds-On** (lightbulb; intro + brainstorm) → **Explore** → **Examples** → **Formative** → **Practice** → **Summary: Need to Know** (always present; placeholder OK). Section Glossary after Summary. Textbook fill of Summary bullets is QU; the slot is AU.
- **Nelson Summary provenance (AU note for QU)** — Nelson In Summary = Key Ideas + Need to Know; module Summaries must use **Need to Know only** (`{lesson}.{n}` indices). Module 1: `questions/NELSON_SUMMARY_GAP.md`.
- **Solution toggles** — example/practice solution `<details>` summaries use **“Show solution”** (not “Show worked solution,” “Reveal full solution,” or similar).
- **Solution media thrift** — when pulling bank items onto lesson pages, solutions show a table/image **only if** it was added to or modified vs the stem (annotations, filled values). Strip unmodified duplicates in the build renderer (`thrift_solution_media`).
- **Practice accordion** — similar-topic practice cards in a collapsed accordion for space + natural progression.
- **Formative accordion** — all formative groups collapsed by default, including the first (no `open` on first).
- **Khan / Sweeney instructions** — one-line modality ask (“Watch and complete activities here” / “Watch the following video”) + open-resource link; not verbose title+notes chrome.
- **Desmos** — overall activity ask up front; calculator how-to steps in expandable `<details>` from seed `interaction_steps_html`. Never a bare iframe/link. Desmos-referencing question stems should include steps too.
- **Type hierarchy** — use the CSS scale: page title > section `h2` > process-block headers (Minds-On / Explore / Examples / Formative / Practice / Summary) > card titles.
- **Question card titles (AU)** — thumbnail title (`title`) at the top of each card; never PROCESS / CONCEPTUAL / APPLICATION subtype labels on student HTML.
- **Process block headers (AU)** — Elevate Minds-On / Explore / Examples / Formative checks / Practice / Summary: Need to Know with distinctive colour + light container backgrounds (`process-heading-*` + block classes). Canvasify must inline the same styles (`m1_canvasify_html.py`) because Canvas strips `<style>`.
- **Expectation footnotes** — quiet (hover/`title` OK) but Canvas-portable via `data-expectations` + subtle visible codes.
- **In-context glossary** — first-use inline `<span class="gterm">` (not mid-paragraph `<details>`) with definition HTML embedded at build time from the course glossary DB + per-section allowlist; end-of-section **“Section Glossary”** accordion (not “Words from this section”).
- **Canvas export packs (AU)** — `python3 scripts/m1_export_canvas_page.py` → folder preview; `python3 scripts/m1_pack_canvas_imscc.py` → `courses/MCF3M/canvas/exports/m1-change-and-transformation.imscc` for Canvas **All Content** import.
