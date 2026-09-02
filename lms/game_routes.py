"""Staff-only Math Game Show APIs mounted on the LLOVES Flask app."""

from __future__ import annotations

import re
import sys
from datetime import date
from typing import Any, Callable

from flask import Flask, jsonify, request

from lms.paths import GAME_SHOW

if str(GAME_SHOW) not in sys.path:
    sys.path.insert(0, str(GAME_SHOW))

from db import GameShowDB  # noqa: E402


def _optional_date(value: Any) -> date | None:
    """Parse YYYY-MM-DD from a JSON field, or None if blank."""
    if value is None or value == "":
        return None
    return date.fromisoformat(str(value)[:10])


def _error_response(exc: BaseException):
    """Map domain exceptions to JSON HTTP errors."""
    if isinstance(exc, KeyError):
        return jsonify({"ok": False, "error": f"Not found: {exc.args[0]}"}), 404
    if isinstance(exc, FileNotFoundError):
        return jsonify({"ok": False, "error": str(exc)}), 404
    if isinstance(exc, ValueError):
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": False, "error": str(exc)}), 500


def register_game_routes(
    app: Flask,
    get_db: Callable[[], GameShowDB],
    staff_required,
) -> None:
    """Attach game-show JSON APIs used by the Grades tab and live game.

    Args:
        app: Flask application.
        get_db: Returns the process GameShowDB.
        staff_required: Decorator requiring a staff/IT session.
    """

    @app.get("/api/classes/<int:class_id>/dashboard")
    @staff_required
    def api_dashboard(class_id: int):
        """Return the class spreadsheet payload."""
        sort = request.args.get("sort") or "last"
        try:
            return jsonify({"ok": True, **get_db().dashboard(class_id, sort)})
        except Exception as exc:  # noqa: BLE001
            return _error_response(exc)

    @app.get("/api/classes/<int:class_id>")
    @staff_required
    def api_get_class(class_id: int):
        """Return one class record."""
        try:
            return jsonify({"ok": True, "class": get_db().get_class(class_id)})
        except Exception as exc:  # noqa: BLE001
            return _error_response(exc)

    @app.get("/api/classes/<int:class_id>/game")
    @staff_required
    def api_game_state(class_id: int):
        """Return live setup/game state."""
        try:
            return jsonify({"ok": True, **get_db().game_state(class_id)})
        except Exception as exc:  # noqa: BLE001
            return _error_response(exc)

    @app.get("/api/scoreboard")
    def api_scoreboard_current():
        """Public-to-session scoreboard JSON (staff or student-code)."""
        if not (
            request.environ.get("lloves_staff") or request.environ.get("lloves_student")
        ):
            return jsonify({"ok": False, "error": "Authentication required."}), 401
        try:
            return jsonify(get_db().scoreboard())
        except Exception as exc:  # noqa: BLE001
            return _error_response(exc)

    @app.get("/api/classes/<int:class_id>/scoreboard")
    def api_scoreboard_class(class_id: int):
        """Scoreboard JSON for a class (staff or matching student offering)."""
        if not (
            request.environ.get("lloves_staff") or request.environ.get("lloves_student")
        ):
            return jsonify({"ok": False, "error": "Authentication required."}), 401
        try:
            return jsonify(get_db().scoreboard())
        except Exception as exc:  # noqa: BLE001
            return _error_response(exc)

    @app.post("/api/classes/<int:class_id>/<path:action>")
    @staff_required
    def api_class_post(class_id: int, action: str):
        """Dispatch class mutation APIs."""
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "Invalid JSON"}), 400
        path = f"/api/classes/{class_id}/{action}"
        try:
            return _dispatch_post(get_db(), path, body)
        except Exception as exc:  # noqa: BLE001
            return _error_response(exc)


def _dispatch_post(db: GameShowDB, path: str, body: dict[str, Any]):
    """Handle a parsed POST body the same way as the standalone server.

    Args:
        db: Game-show database.
        path: URL path.
        body: JSON object.
    """
    begin = re.match(r"^/api/classes/(\d+)/begin$", path)
    if begin:
        meeting = _optional_date(body.get("meeting_date"))
        state = db.begin_game(int(begin.group(1)), meeting_date=meeting)
        return jsonify({"ok": True, **state})
    meeting_post = re.match(r"^/api/classes/(\d+)/game/meeting$", path)
    if meeting_post:
        chosen = _optional_date(body.get("meeting_date"))
        if chosen is None:
            raise ValueError("meeting_date is required (YYYY-MM-DD)")
        time_label = body.get("time")
        state = db.set_meeting_date(
            int(meeting_post.group(1)),
            chosen,
            time_label=str(time_label) if time_label else None,
        )
        return jsonify({"ok": True, **state})
    cancel = re.match(r"^/api/classes/(\d+)/game/cancel$", path)
    if cancel:
        return jsonify(db.cancel_setup(int(cancel.group(1))))
    attendance = re.match(r"^/api/classes/(\d+)/game/attendance$", path)
    if attendance:
        ids = [int(x) for x in (body.get("present_ids") or [])]
        state = db.save_attendance(int(attendance.group(1)), ids)
        return jsonify({"ok": True, **state})
    step = re.match(r"^/api/classes/(\d+)/game/step$", path)
    if step:
        state = db.set_setup_step(int(step.group(1)), str(body.get("status") or ""))
        return jsonify({"ok": True, **state})
    assign = re.match(r"^/api/classes/(\d+)/game/assign$", path)
    if assign:
        raw_assignments = body.get("assignments")
        if raw_assignments is not None and not isinstance(raw_assignments, list):
            raise ValueError("assignments must be a list")
        state = db.assign_teams(
            int(assign.group(1)),
            int(body.get("n_teams") or 0),
            str(body.get("mode") or ""),
            assignments=raw_assignments,
        )
        return jsonify({"ok": True, **state})
    rename = re.match(r"^/api/classes/(\d+)/game/rename$", path)
    if rename:
        names = body.get("teams") or []
        if not isinstance(names, list):
            raise ValueError("teams must be a list")
        state = db.rename_teams(int(rename.group(1)), names)
        return jsonify({"ok": True, **state})
    round_post = re.match(r"^/api/classes/(\d+)/game/round$", path)
    if round_post:
        state = db.start_round(int(round_post.group(1)), int(body.get("round") or 0))
        return jsonify({"ok": True, **state})
    score = re.match(r"^/api/classes/(\d+)/game/score$", path)
    if score:
        state = db.award_points(
            int(score.group(1)),
            kind=str(body.get("kind") or ""),
            target_id=int(body.get("id") or 0),
            amount=int(body.get("amount") or 0),
            team_rule=(str(body["team_rule"]) if body.get("team_rule") else None),
        )
        return jsonify({"ok": True, **state})
    late = re.match(r"^/api/classes/(\d+)/game/add-student$", path)
    if late:
        state = db.add_late_student(
            int(late.group(1)),
            int(body.get("student_id") or 0),
            int(body.get("team_id") or 0),
        )
        return jsonify({"ok": True, **state})
    end = re.match(r"^/api/classes/(\d+)/game/end$", path)
    if end:
        return jsonify(db.end_game(int(end.group(1))))
    add_student = re.match(r"^/api/classes/(\d+)/students$", path)
    if add_student:
        dash = db.add_student(
            int(add_student.group(1)),
            first_name=str(body.get("first_name") or ""),
            last_display=str(body.get("last_display") or ""),
            sort=str(body.get("sort") or "last"),
            codename=str(body["codename"]) if body.get("codename") else None,
        )
        return jsonify({"ok": True, **dash})
    del_student = re.match(r"^/api/classes/(\d+)/students/delete$", path)
    if del_student:
        dash = db.delete_student(
            int(del_student.group(1)),
            int(body.get("student_id") or 0),
            sort=str(body.get("sort") or "last"),
        )
        return jsonify({"ok": True, **dash})
    add_session = re.match(r"^/api/classes/(\d+)/sessions$", path)
    if add_session:
        chosen = _optional_date(body.get("meeting_date"))
        if chosen is None:
            raise ValueError("meeting_date is required (YYYY-MM-DD)")
        dash = db.add_session_column(
            int(add_session.group(1)),
            chosen,
            time_label=str(body["time"]) if body.get("time") else None,
            sort=str(body.get("sort") or "last"),
        )
        return jsonify({"ok": True, **dash})
    del_session = re.match(r"^/api/classes/(\d+)/sessions/delete$", path)
    if del_session:
        dash = db.delete_session_column(
            int(del_session.group(1)),
            int(body.get("session_id") or 0),
            sort=str(body.get("sort") or "last"),
        )
        return jsonify({"ok": True, **dash})
    freeze = re.match(r"^/api/classes/(\d+)/subtotals$", path)
    if freeze:
        dash = db.freeze_subtotal(
            int(freeze.group(1)),
            name=str(body["name"]) if body.get("name") else None,
            sort=str(body.get("sort") or "last"),
        )
        return jsonify({"ok": True, **dash})
    rename_sub = re.match(r"^/api/classes/(\d+)/subtotals/rename$", path)
    if rename_sub:
        dash = db.rename_subtotal(
            int(rename_sub.group(1)),
            int(body.get("id") or 0),
            str(body.get("name") or ""),
            sort=str(body.get("sort") or "last"),
        )
        return jsonify({"ok": True, **dash})
    del_sub = re.match(r"^/api/classes/(\d+)/subtotals/delete$", path)
    if del_sub:
        dash = db.delete_subtotal(
            int(del_sub.group(1)),
            int(body.get("id") or 0),
            sort=str(body.get("sort") or "last"),
        )
        return jsonify({"ok": True, **dash})
    stat_window = re.match(r"^/api/classes/(\d+)/stat-window$", path)
    if stat_window:
        dash = db.set_stat_window(
            int(stat_window.group(1)),
            str(body.get("window") or ""),
            sort=str(body.get("sort") or "last"),
        )
        return jsonify({"ok": True, **dash})
    return jsonify({"ok": False, "error": "Unknown API path"}), 404
