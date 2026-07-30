# Async module lessons (agent brief)

When authoring or regenerating Canvas async modules under `courses/*/modules/`, follow:

- Cursor rule: [`.cursor/rules/async-module-lessons.mdc`](../.cursor/rules/async-module-lessons.mdc)
- Project skill (if present): `.cursor/skills/async-module-lessons/SKILL.md`

## Shawn shorthand (agents only)

- **QU** (Quick Update): one-off module tweak for the current task. Do **not** promote into `.cursor/rules/` or lasting agent rules.
- **AU** (Always Update): onboard into the async-module-lessons rule / skill / this brief, and implement for the active module **and** all future modules.

## Module 1 (MCF3M) reference implementation

- Package: `courses/MCF3M/modules/01-change-and-transformation/`
- Build: `python3 scripts/m1_build_async.py`
- Outputs: `async/index.html` (lesson), `async/questions.html` (ID browser), `questions/m1_questions.sqlite`
- Seed: `questions/seed_data.py` + `questions/schema.sql`
- Local media: `async/assets/` (relative paths from HTML)

Do not hand-edit generated HTML as source of truth. Prefer mining legacy Canvas / Notebook banks, then rewrite in student voice with correct sequencing.

## Rendering conventions (AU — all modules)

- **In-repo assets** — module images live under `async/assets/` (or `media/`) with relative refs for Canvas porting; not remote-only.
- **Solution toggles** — example/practice solution `<details>` summaries use **“Show solution”** (not “Show worked solution,” “Reveal full solution,” or similar).
- **Practice accordion** — similar-topic practice cards in a collapsed accordion for space + natural progression.
- **Formative accordion** — all formative groups collapsed by default, including the first (no `open` on first).
- **Khan / Sweeney instructions** — one-line modality ask (“Watch and complete activities here” / “Watch the following video”) + open-resource link; not verbose title+notes chrome.
- **Desmos** — overall activity ask up front; calculator how-to steps in expandable `<details>` from seed `interaction_steps_html`. Never a bare iframe/link. Desmos-referencing question stems should include steps too.
- **Type hierarchy** — use the CSS scale: page title > section `h2` > explore/block `h3` > card titles.
- **Expectation footnotes** — quiet (hover/`title` OK) but Canvas-portable via `data-expectations` + subtle visible codes.
