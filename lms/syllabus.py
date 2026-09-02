"""Flask helpers for the click-to-place syllabus editor (no sequential packer)."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date, datetime, timedelta, time
from pathlib import Path
from typing import Any

from paths import REPO_ROOT, SCRIPTS_DIR, SEMESTER_JSON, SYLLABUS_DATA_DIR

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "syllabus_calendar", SCRIPTS_DIR / "syllabus_calendar.py"
)
if _spec is None or _spec.loader is None:
    raise ImportError("scripts/syllabus_calendar.py is missing")
_cal = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("syllabus_calendar", _cal)
_spec.loader.exec_module(_cal)

LiveSlot = _cal.LiveSlot
SemesterCalendar = _cal.SemesterCalendar
load_semester_calendar = _cal.load_semester_calendar
load_modules_from_imscc_file = _cal.load_modules_from_imscc_file
render_editor_html = _cal.render_editor_html
parse_editor_placements = _cal.parse_editor_placements
build_table_rows_from_placements = _cal.build_table_rows_from_placements
write_calendar_outputs = _cal.write_calendar_outputs
render_html = _cal.render_html


def calendar_from_semester_row(row: dict[str, Any]) -> Any:
    """Build a ``SemesterCalendar`` from an IT-activated semester row.

    Prefers the cloned ``raw_json`` (same fields as ``semester.json``). Falls
    back to reconstructing a payload from the row columns.

    Args:
        row: ``semesters`` dict.
    """
    raw = row.get("raw_json")
    if raw:
        payload = json.loads(raw) if isinstance(raw, str) else raw
        tmp = SYLLABUS_DATA_DIR / "_active_semester.json"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        return load_semester_calendar(tmp)
    payload = {
        "semester": row.get("label"),
        "instructional": {
            "first_day_of_school": row.get("instructional_first"),
            "last_instructional_day_before_exams": row.get("instructional_last"),
        },
        "pd_days": json.loads(row.get("pd_days_json") or "[]"),
        "holidays": json.loads(row.get("holidays_json") or "[]"),
        "exam_window": {
            "secondary_exam_days": json.loads(row.get("exam_window_json") or "[]")
        },
    }
    tmp = SYLLABUS_DATA_DIR / "_active_semester.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    return load_semester_calendar(tmp)


def slots_from_class(days_stored: str, time_label: str) -> list[Any]:
    """Live-class slots from Populate Class days/time (75-minute meetings).

    Args:
        days_stored: ``Mon/Wed/Fri`` or ``Tue/Thu/Fri``.
        time_label: Wizard time such as ``2:00pm``.
    """
    from schedule import STORED_DAYS_TO_WEEKDAYS, parse_time_label

    weekdays = STORED_DAYS_TO_WEEKDAYS.get(days_stored)
    if not weekdays:
        raise ValueError(f"Unknown class days: {days_stored}")
    clock = parse_time_label(time_label)
    end_dt = datetime.combine(date.today(), clock) + timedelta(minutes=75)
    end: time = end_dt.time()
    start_s = f"{clock.hour:02d}:{clock.minute:02d}"
    end_s = f"{end.hour:02d}:{end.minute:02d}"
    return [
        LiveSlot(weekday=w, start=start_s, end=end_s) for w in sorted(weekdays)
    ]


def offering_output_dir(semester_label: str, ontario_code: str) -> Path:
    """Per-offering syllabus output folder (does not clobber course archives).

    Args:
        semester_label: e.g. ``2026-2027 S1``.
        ontario_code: Course code.
    """
    slug = semester_label.replace(" ", "-")
    path = SYLLABUS_DATA_DIR / slug / ontario_code.upper()
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_editor_modules(imscc_path: Path | None) -> list[Any]:
    """Parse IMSCC modules for the editor, or return an empty list.

    Args:
        imscc_path: Cartridge file, or None.
    """
    if imscc_path is None or not imscc_path.is_file():
        return []
    return load_modules_from_imscc_file(imscc_path)


def build_editor_page(
    *,
    course: str,
    calendar: Any,
    slots: list[Any],
    modules: list[Any],
    save_url: str,
) -> str:
    """Render click-to-place HTML and point Save at the Flask route.

    Args:
        course: Ontario course code.
        calendar: Locked IT semester calendar.
        slots: Live meetings from the class.
        modules: IMSCC modules (may be empty).
        save_url: POST target for placements JSON.
    """
    included = {module.number: list(module.lessons) for module in modules}
    empty_rows = build_table_rows_from_placements(
        calendar, slots, {}, blank_calendar=True
    )
    page = render_editor_html(
        empty_rows,
        course=course,
        calendar=calendar,
        live_slots=slots,
        modules=modules,
        included=included,
    )
    return page.replace('fetch("/save"', f'fetch("{save_url}"')


def save_placements(
    *,
    payload: dict[str, Any],
    course: str,
    semester_label: str,
    calendar: Any,
    slots: list[Any],
    modules: list[Any],
) -> dict[str, str]:
    """Write CSV, Canvas-RCE-safe HTML, and answers JSON under ``lms/data/syllabus``.

    Does **not** call ``pack_modules()``.

    Args:
        payload: Editor POST JSON.
        course: Course code.
        semester_label: Semester id used as the filename slug.
        calendar: Locked calendar.
        slots: Live-class slots.
        modules: IMSCC modules.

    Returns:
        Relative paths for csv/html/answers.
    """
    if not modules:
        raise ValueError("No module pack for this course yet")
    pool = set(calendar.instructional_days)
    placements = parse_editor_placements(payload, pool, modules)
    rows = build_table_rows_from_placements(
        calendar, slots, placements, blank_calendar=True
    )
    included = {module.number: list(module.lessons) for module in modules}
    out_dir = offering_output_dir(semester_label, course)
    slug = semester_label.replace(" ", "-")
    csv_path, html_path, answers_path = write_calendar_outputs(
        out_dir,
        slug,
        rows,
        course=course,
        calendar=calendar,
        slots=slots,
        warnings=[],
        content=modules,
        included=included,
    )

    def _rel(path: Path) -> str:
        """Repo-relative POSIX path when possible."""
        try:
            return path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return str(path)

    return {
        "csv": _rel(csv_path),
        "html": _rel(html_path),
        "answers": _rel(answers_path),
        "html_abs": str(html_path),
    }


def saved_html_path(semester_label: str, ontario_code: str) -> Path | None:
    """Return the saved month-grid HTML if it exists."""
    slug = semester_label.replace(" ", "-")
    path = offering_output_dir(semester_label, ontario_code) / f"{slug}.html"
    return path if path.is_file() else None
