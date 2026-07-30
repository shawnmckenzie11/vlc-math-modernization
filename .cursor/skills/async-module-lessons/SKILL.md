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

Student-facing only · life-understanding motivation · Khan-like clarity · no ahead-of-schedule notation · DB → cards + quiet expectation footnotes (`data-expectations`) · stable smart IDs · questions browse page · Explore tabs only for same-content media · first/second differences as HTML tables · KA → Sweeney → Desmos priority · practice in accordion · formatives all collapsed (incl. first) · solution toggles labeled “Show solution” · Khan/Sweeney one-line modality instructions · Desmos activity ask + expandable how-to · in-repo `async/assets/` with relative paths · differentiated title type scale · regenerate HTML from DB

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

## Typography (AU)

- Follow the module CSS type scale: page `h1` > section `h2` > explore/block `h3` > card `h4` / accordion summaries.
