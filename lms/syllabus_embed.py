"""Embed the click-to-place syllabus editor in the staff Syllabus tab."""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from lms.paths import ROOT, SEMESTER_JSON

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from syllabus_calendar import (  # noqa: E402
    LIVE_CLASS_TITLE,
    LiveSlot,
    build_table_rows_from_placements,
    load_modules_from_imscc_file,
    load_semester_calendar,
    parse_editor_placements,
    render_editor_html,
    write_calendar_outputs,
)

WEEKDAY = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
}

STORED_DAYS = {
    "Mon/Wed/Fri": (0, 2),
    "Tue/Thu/Fri": (1, 3),
    "M/W/F": (0, 2),
    "T/Th/F": (1, 3),
}


def live_slots_from_class(days: str, time_label: str) -> list[LiveSlot]:
    """Build syllabus live slots from a populated class meeting pattern.

    Friday office hours stay off the calendar. Only the two 75-minute live
    days from the class preset are stamped as live-class candidates.

    Args:
        days: Stored days such as ``Mon/Wed/Fri``.
        time_label: Wizard time such as ``2:00pm``.
    """
    weekdays = STORED_DAYS.get(days) or STORED_DAYS.get(days.replace(" ", ""))
    if not weekdays:
        weekdays = (0, 2)
    start, end = _window_for_label(time_label)
    return [LiveSlot(weekday=d, start=start, end=end) for d in weekdays]


def _window_for_label(time_label: str) -> tuple[str, str]:
    """Return 24h start–end strings for a 75-minute live class.

    Args:
        time_label: ``2:00pm``-style wizard value.
    """
    text = (time_label or "2:00pm").strip().lower().replace(" ", "")
    match = __import__("re").match(r"^(\d{1,2}):(\d{2})(am|pm)$", text)
    if not match:
        return "14:00", "15:15"
    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = match.group(3)
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    start_t = time(hour, minute)
    end_dt = datetime.combine(date.today(), start_t) + timedelta(minutes=75)
    return start_t.strftime("%H:%M"), end_dt.strftime("%H:%M")


def editor_html_for_offering(
    *,
    course: str,
    imscc_path: Path,
    days: str,
    time_label: str,
    save_url: str,
    semester_json: Path | None = None,
) -> str:
    """Render the click-to-place editor with IMSCC already loaded.

    Args:
        course: Ontario course code.
        imscc_path: Course cartridge.
        days: Class live-day preset.
        time_label: Class start time.
        save_url: Flask POST path that replaces ``/save``.
        semester_json: Override calendar JSON.

    Returns:
        Full editor HTML document.
    """
    calendar = load_semester_calendar(semester_json or SEMESTER_JSON)
    slots = live_slots_from_class(days, time_label)
    modules = load_modules_from_imscc_file(imscc_path)
    included = {module.number: list(module.lessons) for module in modules}
    empty_rows = build_table_rows_from_placements(
        calendar, slots, {}, blank_calendar=True
    )
    html = render_editor_html(
        empty_rows,
        course=course,
        calendar=calendar,
        live_slots=slots,
        modules=modules,
        included=included,
    )
    return html.replace('fetch("/save"', f'fetch("{save_url}"')


def save_placements(
    *,
    raw: dict[str, Any],
    course: str,
    imscc_path: Path,
    days: str,
    time_label: str,
    out_dir: Path,
    slug: str,
    semester_json: Path | None = None,
) -> dict[str, str]:
    """Write CSV/HTML/answers from editor placement JSON.

    Args:
        raw: Editor POST body.
        course: Course code.
        imscc_path: Cartridge used to load remaining items.
        days: Class days.
        time_label: Class time.
        out_dir: Output folder.
        slug: Filename slug.
        semester_json: Calendar JSON.

    Returns:
        Relative path strings for csv/html/answers.
    """
    calendar = load_semester_calendar(semester_json or SEMESTER_JSON)
    slots = live_slots_from_class(days, time_label)
    modules = load_modules_from_imscc_file(imscc_path)
    included = {module.number: list(module.lessons) for module in modules}
    pool = set(calendar.instructional_days)
    placements = parse_editor_placements(raw, pool, modules)
    rows = build_table_rows_from_placements(
        calendar, slots, placements, blank_calendar=True
    )
    out_dir.mkdir(parents=True, exist_ok=True)
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
    return {
        "csv": str(csv_path),
        "html": str(html_path),
        "answers": str(answers_path),
    }
