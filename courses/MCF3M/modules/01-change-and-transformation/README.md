# Module 1 — Change & Transformation

Async lesson package for MCF3M Module 1. Content is **DB-backed**; HTML is **regenerated**.

Authoring rules (all future modules): [`.cursor/rules/async-module-lessons.mdc`](../../../.cursor/rules/async-module-lessons.mdc) · [`agents/async-module-lessons.md`](../../../agents/async-module-lessons.md)

## Preview (Shawn)

```bash
cd courses/MCF3M/modules/01-change-and-transformation/async
python3 -m http.server 8765
```

| Page | URL |
|------|-----|
| Lesson (single Canvas-like page) | http://127.0.0.1:8765/ |
| Question bank by smart ID | http://127.0.0.1:8765/questions.html |

Files: `async/index.html`, `async/questions.html`

`file://` often blocks YouTube/Desmos iframes — prefer the local server.

## Khan Academy embeds vs link-out

Khan Academy lesson pages **cannot be iframed** (site framing / CSP). Module 1 Explore therefore uses **in-page link-out cards**: title, one-line why it helps, and a prominent “Open on Khan Academy” button. YouTube (Steve Sweeney) and Desmos keep on-page iframes when `embed_url` is set.

Seed URLs are current Algebra 1 paths under `x2f8bb11595b61c86:…`. Re-verify after KA curriculum renames; do not invent slugs.

## Smart ID scheme

`M1-S{n}-{E|F|P}{nn}` e.g. `M1-S1-E01`, `M1-S5-P12`

- Stored in sqlite `items.smart_id` (seeded explicitly; stable across regenerations)
- Shown as a muted badge on every question card
- Anchors: `index.html#M1-S2-E01`

## Regenerate

```bash
python3 scripts/m1_build_async.py
```

## Paths

| Piece | Path |
|-------|------|
| Lesson HTML | `async/index.html` |
| Question bank HTML | `async/questions.html` |
| CSS / JS | `async/styles.css`, `async/module.js`, `async/questions.js` |
| Schema / seed / DB | `questions/schema.sql`, `questions/seed_data.py`, `questions/m1_questions.sqlite` |
| Build | `scripts/m1_build_async.py` |

## Explore media rule

- Same idea, alternate modality → **tabs** (`content_group` shared)
- Different / sequential ideas → **separate Explore blocks** (no tabs)
- **Desmos** → always include patient calculator interaction steps (`interaction_steps_html`); never a bare iframe

## Counts

120 items (targets met): S1 2/1/3 · S2 4/2/6 · S3 4/2/6 · S4 8/4/12 · S5 12/6/18 · S6 10/5/15
