# MCF3M live lessons (SMART Notebook)

Synchronous Zoom live-class materials for **MCF3M**, authored in **SMART Notebook** (`.notebook` files). Used for the two 75-minute live classes each week; not a substitute for Canvas async module pages.

## Provenance

| Field | Value |
|-------|--------|
| Imported | 2026-07-30 |
| Source | User Downloads: `~/Downloads/MCF3M.zip` (copy only; original left untouched) |
| Medium | SMART Notebook for all math live lessons |
| Course | MCF3M — Functions and Applications |

## Storage decision

| Artifact | Path | Tracked? | Why |
|----------|------|----------|-----|
| Original zip | [`archives/MCF3M.zip`](archives/MCF3M.zip) (~65 MB) | Yes | Canonical restore / re-import |
| Extracted tree | [`modules/`](modules/) (~66 MB, 93 files) | Yes | Fast listing & module queries without unzip |
| Inventory | [`inventory.json`](inventory.json), [`inventory.md`](inventory.md) | Yes | Agent-readable catalog |

**Rationale:** The repo already tracks a large Canvas IMSCC under `courses/MCF3M/sources/` (~189 MB). An additional ~130 MB for zip + extract is acceptable and keeps both restore-from-archive and browse-by-module workflows easy. macOS junk (`__MACOSX`, `.DS_Store`) was stripped on extract.

If git size becomes painful later: keep the zip + inventories, gitignore `modules/**/*.notebook` (and large PDFs), and re-extract with:

```bash
unzip -o courses/MCF3M/live-lessons/archives/MCF3M.zip -d /tmp/mcf3m-nb
# then rsync MCF3M/ into modules/ excluding __MACOSX / .DS_Store
python3 scripts/inventory_smart_notebook.py
```

## Layout

```
live-lessons/
  README.md                 # this file
  archives/MCF3M.zip        # original import
  modules/                  # cleaned extract
    Module 1 - Intro to the Quadratic Function/
    Module 2 - Algebra of Quadratic Expressions/
    ...
    Module 8 - Finance/
    Exam Outline/
    Learning Skills/
  inventory.json
  inventory.md
```

## Module folders (as imported)

| Folder | Notes |
|--------|--------|
| Module 1 – Intro to the Quadratic Function | Includes course intro (M1L0) |
| Module 2 – Algebra of Quadratic Expressions | |
| Module 3 – Standard and Factored Form | |
| Module 4 – Standard and Vertex Form | |
| Module 5 – Trigonometry | |
| Module 6 – Sinusodial Functions | Source spelling preserved |
| Module 7 – Exponential Functions | |
| Module 8 – Finance | |
| Exam Outline | Exam review notebooks |
| Learning Skills | Non-strand live materials |

## Naming

Typical patterns:

- Teacher: `3M M2L1 - Multiplying Polynomials.notebook`
- Student: `3M M2L1 - Multiplying Polynomials (student).notebook`
- Alternate: `3M Module 6 Lesson 2 - The Sine Function & Transformations.notebook`

Companion `.pdf` / `.png` assets appear beside some lessons.

Quirk preserved from source: one Module 3 duplicate is named `3M M3L3 - Solving Application Problems.notebook(1)` (macOS-style collision suffix).

## Tooling

```bash
python3 scripts/inventory_smart_notebook.py
```

Agent / skill: [`agents/smart-notebook-lessons.md`](../../../agents/smart-notebook-lessons.md), [`.cursor/skills/smart-notebook-lessons/SKILL.md`](../../../.cursor/skills/smart-notebook-lessons/SKILL.md)

## Phase status

- **Phase 1 (now):** store, inventory, module mapping, answer “what lessons exist for module X?”
- **Phase 2 (later):** open `.notebook` as ZIP, extract slides/text/images, summarize, align to curriculum expectations, draft 75-min Zoom session plans
