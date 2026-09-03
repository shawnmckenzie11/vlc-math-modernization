---
name: async-module-lessons
description: >-
  Author and regenerate ELC Canvas async module lesson pages from a sqlite
  question bank (student voice, smart IDs, Explore media rules, difference
  tables). Use when drafting modules under courses/*/modules/, Module async
  HTML, question DBs, or regenerating index.html / questions.html.
---

# Async module lessons

## Load first

1. Read [`.cursor/rules/async-module-lessons.mdc`](../../rules/async-module-lessons.mdc)
2. Read course `AGENTS.md`, `course-plan.md`, and `frameworks/` as needed
3. Query curriculum expectations — do not invent codes
4. If the task is textbook PDF extract/curate/browse (Nelson), switch to the **nelson-question-bank** skill — that bank is not the live lesson DB

## Reference build (MCF3M Module 1)

```bash
python3 scripts/m1_build_async.py
```

Preview:

```bash
cd courses/MCF3M/modules/01-change-and-transformation/async
python3 -m http.server 8765
```

- Lesson: http://127.0.0.1:8765/
- Question bank: http://127.0.0.1:8765/questions.html

## Non-negotiables (summary)

Student-facing only · life-understanding motivation · Khan-like clarity · no ahead-of-schedule notation · DB → cards + quiet expectation footnotes (`data-expectations`) · first-use glossary inline `<span class="gterm">` (allowlist + glossary DB; not mid-paragraph `<details>`) · end-of-section **Section Glossary** · solution media thrift · Canvas export inlines CSS/JS (`m1_export_canvas_page.py`) · canvasify inlines process-block + card-title styles · stable smart IDs · questions browse page · Explore tabs only for same-content media · first/second differences as HTML tables · KA → Sweeney → Desmos priority · practice in accordion · formatives all collapsed (incl. first) · solution toggles labeled “Show solution” · Khan/Sweeney one-line modality instructions · Desmos activity ask + expandable how-to · in-repo `async/assets/` with relative paths · card thumbnail titles (not PROCESS/etc.) · section titles `{m}.{n}` Title Case (Shawn: **S1.1**) · mandatory spine Minds-On → Explore → Examples → Formative → Practice → Summary: Need to Know · elevated coloured process headers (incl. Minds-On + Summary) · regenerate HTML from DB

## In-context glossary (AU)

- Build-time first-use links from `questions/glossary_allowlist.py` + `sources/nelson/glossary.sqlite`.
- Markup: inline `<span class="gterm">` + checkbox/label + popover def (keeps sentence flow).
- End-of-section collapsed review label: **“Section Glossary”**.
- Before IMSCC / for import preview: `python3 scripts/m1_export_canvas_page.py` → `courses/MCF3M/canvas/exports/m1-change-and-transformation/`.

## Media assets (AU)

- Save images under the module’s `async/assets/` (or `media/`); reference with relative paths for Canvas porting.

## Learning-modality instructions (AU)

- Khan: “Watch and complete activities here” + Open on Khan Academy CTA.
- Sweeney/YouTube: “Watch the following video” + Open resource link.
- Do not render verbose `Kind · Title · long notes` chrome for these modalities.

## Desmos (AU)

- Overall activity ask/expectations up front (`notes` or activity-ask field).
- Concrete calculator steps in expandable `<details>` via seed `interaction_steps_html`.
- Renderer must require + display steps for Desmos cards; tailor to the activity.
- Question stems that send students to Desmos also need steps.

## Formatives (AU)

- All formative groups use collapsed `<details class="formative-accordion">` — including the first (never auto-`open`).

## Solution toggles (AU)

- Example/practice solution `<details>` summaries: **“Show solution”** (not “Show worked solution,” “Reveal full solution,” or similar).

## Solution media thrift (AU)

- Solutions must **not** re-show an unmodified stem table/figure/image.
- Only keep solution media when it was added to or changed vs the stem (filled cells, annotations, etc.).
- Implemented in the module build renderer (`thrift_solution_media`); do not hand-paste duplicate media into generated HTML.

## Section Glossary (AU)

- End-of-section collapsed review label: **“Section Glossary”** (not “Words from this section”).
- Keep CSS/class names (`section-words*`) stable; rename is student-facing summary text (+ canvasify if it hardcodes the old label).

## Section titles (AU)

- Title Case + `{moduleNumber}.{sectionNumber}` prefix (e.g. `1.1 Relationships We Can Trust`).
- Shawn shorthand **S1.1** / **S1.2** = module.section from `sort_order`.
- Do not renumber stable smart IDs to match display indices; document mapping in the module README.

## Mandatory section sequence (AU)

Every section: **Minds-On** (lightbulb; intro + brainstorm before Explore) → **Explore** → **Examples** → **Formative** → **Practice** → **Summary: Need to Know** (always render; placeholder OK). Section Glossary after Summary when present.

## Nelson Summary provenance (AU note for QU)

Nelson **In Summary** boxes mix **Key Ideas** and **Need to Know**. When filling module Summaries from Nelson, use **Need to Know bullets only** — do not adapt Key Ideas. Index as `{lesson}.{n}` (Module 1 gap report: `questions/NELSON_SUMMARY_GAP.md`).

## Typography (AU)

- Follow the module CSS type scale: page `h1` > section `h2` > process-block `h3` (Minds-On / Explore / Examples / Formative / Practice / Summary) > card titles / accordion summaries.

## Question card titles (AU)

- Render seed `title` at the top of each question card (with smart-id); do **not** show PROCESS / CONCEPTUAL / APPLICATION subtype labels on student pages.

## Process block headers (AU)

- Elevate Minds-On / Explore / Examples / Formative checks / Practice / Summary: Need to Know with coloured `process-heading-*` headers + light container backgrounds.
- Keep `styles.css` and `scripts/m1_canvasify_html.py` CLASS_STYLES / heading inlining in sync for Canvas import.
