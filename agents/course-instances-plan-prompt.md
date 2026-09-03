# Plan prompt — LLOVES course instances

Copy everything below the line into Cursor **Plan** mode.

---

Plan how LLOVES should store **staff course instances** as tuples `(ontario_code, school_year, semester, teacher)` with a single instance folder tree that all build off course-code templates. Produce an implementation plan only (no code yet). Read the repo before proposing; do not invent a second school or rewrite ELC docs.

## Product

LLOVES is a **new** school LMS (`lms/`, live at https://alc.mckenzian.com, Fly app `lloves-lms`). It is **not** a rename of ELC. Do **not** rewrite `frameworks/school.md`. Shared calendar / class-shape constants stay in `frameworks/` (`semester.json`, `class-structure.md`).

Portals: staff, student (8-char course key), IT (`solutions@mckenzian.com`). Canonical app: `lms/app.py` `create_app(...)`.

## Goal

When IT assigns a course to staff:

1. IT selects an **Ontario course code** (catalog).
2. That selection fills a field below with **previous instances of that code** (this semester or earlier semesters, any teacher) to use as an optional **base layer**.
3. The new assignment is wrapped in the **current active year + semester calendar** (`frameworks/semester.json`) plus **teacher identity**, and becomes an **instance** on that teacher’s dashboard.

Instance identity: **(course code, school year, semester, teacher)**.

## Current state (do not ignore)

Three layers are conflated today:

| Layer | Reality |
|--------|---------|
| Template / authoring | Only `courses/MCF3M/` exists. Other Ontario codes are sqlite `ontario_courses` rows; most have `content_root` NULL. |
| Assignment | `course_offerings`: `UNIQUE(semester_id, ontario_code, teacher_user_id)` in `lms/school_db.py`. IT form is staff + code only (`lms/templates/it/dashboard.html` → `POST /it/offerings`). No previous-instance picker. |
| Live section | `tools/math-game-show` `classes` (days/time/roster) with `offering_id`. Engine only — **no** `tools/math-game-show/MCF3M/` folder. |
| Packs | MCF3M is hard-coded in `lms/paths.py` (`MCF3M_IMSCC`, `MCF3M_UNPACKED`) and `assign_course` (if code == MCF3M, point at repo IMSCC). Other codes: staff upload → `/data/module_packs/<offering_id>/` (`lms/modules.py`). |

`ontario_courses.content_root` already exists (`courses/MCF3M` for MCF3M only). Student live-access code is shared per `(semester, ontario_code)`, not per teacher.

## Target file architecture

Keep **three layers**. Do not clone the authoring tree per teacher.

```
frameworks/                         # school calendar wrap (unchanged)
courses/<CODE>/                     # TEMPLATE — git; create only when we author that code
  AGENTS.md, sources/, curriculum/, modules/, canvas/, live-lessons/

data/instances/<CODE>/<YEAR>/<TERM>/<teacher-slug>/   # RUNTIME — volume, not git
  manifest.json
  pack/                             # IMSCC + unpacked + inventory
  syllabus/                         # placements for THIS semester’s dates
```

Production: `/data/instances/...` on the Fly volume (same place sqlite already lives). Local: `lms/data/instances/...`.

`manifest.json` should record at least: `ontario_code`, `year`, `term`, `teacher_user_id`, `teacher_name`, `offering_id`, `base_offering_id` (nullable), calendar source.

Use **teacher user id or email slug** in the path (display names change). Sqlite remains source of truth; folders are a readable address for the tuple.

**Do not** put instances under `courses/MCF3M/`. That folder is a curriculum product (Nelson, course-plan, SMART Notebook). Agents must keep treating it as the shared template.

**Do not** create empty `courses/<CODE>/` folders for every catalog code. Catalog row is enough until we author content.

**Do not** move `tools/math-game-show/` or treat its `classes.year` / `semester` / `course_code` as a second instance tree. Sections stay children of one offering.

## IT + copy rules

- Select code → query all `course_offerings` with that `ontario_code` (any semester) → show as base choices (year, term, teacher, whether a pack exists).
- Optional “no base” / “use course-code template” (MCF3M repo IMSCC is the default template, not a live write target).
- Assign creates a **new** offering for the **active** semester + chosen teacher (existing uniqueness).
- **Copy as base:** module pack (IMSCC/unpacked/inventory) and syllabus **structure**.
- **Re-wrap dates** from current `frameworks/semester.json` (20-week shape, first 2 instructional days = intro, last week before exams = review, due dates only on school days). Do not reuse last semester’s calendar dates.
- **Do not copy:** roster, scores, live games. Student code policy stays: one key per `(semester, course)` shared across teachers unless you explicitly call out a change.
- Two teachers must not share a writable `courses/MCF3M/canvas/unpacked/`. Template is read-only; instances get their own pack copy.

## Implementation constraints

- Backwards compatible: existing offerings, `POST /api/staff/classes`, module-pack upload, MCF3M dashboard, student codes must keep working. Migrate `module_packs/<offering_id>/` into the instance tree (or resolve both during transition).
- Replace MCF3M hardcodes (`lms/paths.py`, `assign_course`, `resolve_module_pack`) with `content_root` + instance paths.
- Add `copied_from_offering_id` (or equivalent) on offerings.
- Staff dashboard lists **active-semester instances** assigned to that teacher (today’s `list_offerings`).
- Tests: extend `lms/test_it.py` / `lms/test_module_pack.py` / roster tests; no commit unless I ask.
- Do not invent Ontario expectation codes; query the curriculum DB.
- Prefer teaching-content conventions; docstrings on new functions.

## Plan output

1. Target data model (sqlite columns + manifest) vs folders.
2. Exact repo files to change (`lms/school_db.py`, `lms/modules.py`, `lms/paths.py`, IT templates/JS, syllabus paths).
3. IT UX flow (code → previous instances → assign → dashboard card).
4. Migration of existing MCF3M offerings and `module_packs/<id>/`.
5. What stays git vs volume.
6. Risks (shared live-access code, two teachers, Fly volume, large `courses/` Docker context).
7. Phased build order (schema + paths first, then IT picker, then copy/re-wrap, then retire hardcodes).

Ask me only if a product choice is blocking (e.g. whether a second teacher in the same semester should share one pack or always fork).
