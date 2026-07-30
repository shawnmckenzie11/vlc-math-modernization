# Canvas course updater agent (MCF3M)

## Purpose

Be the **interface for structural Canvas course changes** to the MCF3M Common Cartridge export: modules, pages, quizzes, assignments, reordering, and safe unpack → edit → validate → (optional) re-pack workflows.

Never invent Ontario curriculum expectation codes or wording — query `courses/MCF3M/curriculum/mcf3m.sqlite` when tagging content.

## Always load first

1. [`frameworks/school.md`](../frameworks/school.md)
2. [`frameworks/class-structure.md`](../frameworks/class-structure.md)
3. [`frameworks/canvas-lms.md`](../frameworks/canvas-lms.md)
4. [`frameworks/semester.json`](../frameworks/semester.json)
5. [`courses/MCF3M/AGENTS.md`](../courses/MCF3M/AGENTS.md)
6. [`courses/MCF3M/canvas/INVENTORY.md`](../courses/MCF3M/canvas/INVENTORY.md) (or `inventory.json`)


## Rebuild posture

Inventoried modules and pages are a **baseline**, not a required permanent structure. Rebuilds may remove, add, or merge modules/lessons. Preserve the `.imscc` archive under `sources/`; edit `canvas/unpacked/` (or pack a new cartridge) deliberately. After structural change, regenerate inventory. Align with `live-lessons/` by module intent, not old numbering alone. Query curriculum expectations when tagging outcomes.

## Path convention

| Role | Path |
|------|------|
| Source-of-truth archive | `courses/MCF3M/sources/mcf3m-canvas-export.imscc` |
| Working unpack (gitignored) | `courses/MCF3M/canvas/unpacked/` |
| Committed inventory | `courses/MCF3M/canvas/INVENTORY.md`, `inventory.json` |
| Layout notes | `courses/MCF3M/canvas/README.md` |

Do **not** commit the unpacked tree (media-heavy). Do commit regenerated inventory after structural edits.

## IMSCC / Common Cartridge map

Canvas exports are ZIP files with a `.imscc` extension:

| Path | Role |
|------|------|
| `imsmanifest.xml` | Resource index + module organization tree |
| `course_settings/module_meta.xml` | Module metadata, item order, content types |
| `course_settings/course_settings.xml` | Course title/code/tabs |
| `wiki_content/*.html` | Canvas Pages (title + `meta name="identifier"`) |
| `g<hex>/assignment_settings.xml` + `*.html` | Assignments |
| `g<hex>/assessment_meta.xml` + `assessment_qti.xml` | Quizzes |
| `non_cc_assessments/*.xml.qti` | Full QTI bodies for some quizzes |
| `web_resources/` | Uploaded files / media |
| `lti_resource_links/` | External tool links |

Module item `content_type` values commonly seen: `WikiPage`, `Assignment`, `Quizzes::Quiz`, `Attachment`, `ContextModuleSubHeader`, `ExternalUrl`, `ContextExternalTool`.

## Safe workflow

```
Task Progress:
- [ ] 1. Read inventory (+ semester / curriculum if tagging outcomes)
- [ ] 2. Ensure unpacked tree exists (unpack if missing)
- [ ] 3. Make structural edits (prefer scripts for scaffolds)
- [ ] 4. Spot-check XML + HTML identifiers still match
- [ ] 5. Regenerate inventory
- [ ] 6. (Optional) Pack .imscc for Canvas re-import
```

### Commands

```bash
# Unpack (~189MB archive → working tree)
python3 scripts/canvas_unpack.py --clean

# Inventory (from unpacked if present, else directly from .imscc)
python3 scripts/canvas_inventory.py

# Scaffold a module + pages into the unpacked tree
python3 scripts/canvas_add_module.py \
  --title "Module 9: Example Topic" \
  --pages "Learning Goals" "Lesson 1" "Practice" "Checkpoint intro"

# Re-pack for Canvas import (writes a NEW archive; does not overwrite source)
python3 scripts/canvas_pack.py
```

### Re-import to Canvas

1. Run `python scripts/canvas_pack.py` → e.g. `courses/MCF3M/sources/mcf3m-canvas-edited.imscc`
2. In Canvas: **Settings → Import Course Content → Common Cartridge 1.x**
3. Prefer importing into a **sandbox / copy** course first
4. Review modules, unpublished items, and media before publishing to students

## How to add a module (agent procedure)

1. Confirm desired title, page list, and placement (end vs specific `--position`).
2. Query curriculum DB if the module should cite expectations:
   `python3 scripts/query_expectations.py search "<topic>"`
3. Ensure unpack exists: `python3 scripts/canvas_unpack.py` if `canvas/unpacked/imsmanifest.xml` is missing.
4. Run `canvas_add_module.py` with `--title` and `--pages`.
5. Edit the new `wiki_content/*.html` stubs (Canvas-ready: goal, instructions, practice, submit cues).
6. Run `python3 scripts/canvas_inventory.py` and confirm the module appears in `INVENTORY.md`.
7. Do not invent expectation codes in page HTML; omit or query first.
8. Note: `canvas_add_module.py` may reformat XML whitespace — sandbox re-import before production use.

## Editing / reordering

- **Reorder items within a module**: edit `position` values under that module in `module_meta.xml`, and keep the matching organization subtree in `imsmanifest.xml` in the same order.
- **Reorder modules**: change module `position` in `module_meta.xml` and reorder organization children under `LearningModules` in `imsmanifest.xml`.
- **Edit a page**: open the HTML under `wiki_content/`; keep the `meta name="identifier"` unchanged.
- **Add a page to an existing module**: prefer extending via careful XML edits mirroring an existing `WikiPage` item (identifier links across `module_meta.xml`, `imsmanifest.xml` resource, and HTML meta). Use `canvas_add_module.py` only for **new** modules.

## Assignments & quizzes

- Structure-aware only unless Shawn asks for full QTI authoring.
- New assignments need a `g…/` folder with `assignment_settings.xml` + HTML body, a manifest `resource`, and a module item (`content_type` = `Assignment`).
- Quizzes additionally need QTI (`assessment_qti.xml` / `non_cc_assessments/`) — treat as advanced; copy an existing simple practice quiz as a template rather than inventing QTI from scratch.

## Non-negotiables

- Inherit ELC online model (Canvas async + 2×75 Zoom + Friday office hours)
- Never invent curriculum expectations; link codes only after DB/PDF verification
- Keep the original `.imscc` archive intact; pack edits to a separate file
- Docstrings on any new script functions
- Do not commit unless Shawn asks

## Related skill

`.cursor/skills/canvas-course-updater/SKILL.md`
