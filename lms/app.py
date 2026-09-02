#!/usr/bin/env python3
"""LLOVES LMS — Flask entry point.

Usage:
    python3 lms/app.py
    # http://127.0.0.1:8787
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

LMS_DIR = Path(__file__).resolve().parent
REPO_ROOT = LMS_DIR.parent
MGS_DIR = REPO_ROOT / "tools" / "math-game-show"
if str(LMS_DIR) not in sys.path:
    sys.path.insert(0, str(LMS_DIR))
for path in (str(REPO_ROOT), str(MGS_DIR)):
    if path not in sys.path:
        sys.path.append(path)

from dotenv import load_dotenv

load_dotenv(LMS_DIR / ".env")
load_dotenv(REPO_ROOT / ".env")

from flask import (  # noqa: E402
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

from auth import (  # noqa: E402
    current_user,
    google_oauth_ready,
    it_required,
    landing_kwargs,
    login_required,
    register_auth_routes,
    staff_or_student_scoreboard,
    staff_required,
    student_required,
)
from curriculum import seed_curriculum  # noqa: E402
from school_db import SchoolDB  # noqa: E402
from modules import (  # noqa: E402
    ensure_unpacked,
    imscc_path_for_code,
    inventory_path_for_code,
    load_inventory,
    module_nav,
    placeholder_html,
    rewrite_wiki_html,
    safe_unpacked_file,
    unpacked_dir_for_code,
    wrap_page,
)
from paths import (  # noqa: E402
    DATA_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_IT_EMAIL,
    MGS_DIR as MGS_PATH,
    SCHOOL_NAME,
    SCHOOL_SHORT,
)
import syllabus as syllabus_mod  # noqa: E402
from schedule import TIME_OPTIONS, wizard_defaults  # noqa: E402

MGS_TEMPLATES = MGS_PATH / "templates"
MGS_STATIC = MGS_PATH / "static"


def _optional_date(value: Any) -> date | None:
    """Parse YYYY-MM-DD from a JSON field, or None if blank."""
    if value is None or value == "":
        return None
    return date.fromisoformat(str(value)[:10])


def _json_error(exc: BaseException):
    """Map domain exceptions to JSON API errors."""
    if isinstance(exc, KeyError):
        return jsonify({"ok": False, "error": f"Not found: {exc.args[0]}"}), 404
    if isinstance(exc, FileNotFoundError):
        return jsonify({"ok": False, "error": str(exc)}), 404
    if isinstance(exc, ValueError):
        return jsonify({"ok": False, "error": str(exc)}), 400
    return jsonify({"ok": False, "error": str(exc)}), 500


def create_app(
    *,
    db_path: Path | None = None,
    data_dir: Path | None = None,
    testing: bool = False,
) -> Flask:
    """Build the LLOVES Flask application.

    Args:
        db_path: Override sqlite path (tests).
        data_dir: Override game-show uploads/logs directory.
        testing: Disable CSRF-adjacent secure cookies; used by tests.
    """
    app = Flask(
        __name__,
        template_folder=str(LMS_DIR / "templates"),
        static_folder=None,
    )
    secret = os.getenv("FLASK_SECRET_KEY", "lloves-dev-secret-change-me")
    app.secret_key = secret
    app.config["TESTING"] = testing
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=31)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    secure = (os.getenv("FLASK_ENV") or "").lower() == "production"
    app.config["SESSION_COOKIE_SECURE"] = secure and not testing
    if secure:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
        app.config["PREFERRED_URL_SCHEME"] = "https"

    db_file = Path(db_path or os.getenv("LLOVES_DB") or DEFAULT_DB_PATH)
    store = Path(data_dir or os.getenv("LLOVES_DATA_DIR") or db_file.parent)
    it_email = (os.getenv("IT_EMAILS") or DEFAULT_IT_EMAIL).split(",")[0].strip()
    school = SchoolDB(
        db_file,
        store,
        it_email=it_email or DEFAULT_IT_EMAIL,
    )
    app.config["SCHOOL_DB"] = school
    seed_curriculum(school)

    register_auth_routes(app)
    _register_pages(app, school)
    _register_game_api(app, school)
    return app


def _register_pages(app: Flask, school: SchoolDB) -> None:
    """Landing, IT, staff, student, static, and module/syllabus routes."""

    @app.route("/static/<path:filename>")
    def static_files(filename: str):
        """Serve LLOVES assets first, then Math Game Show static files."""
        lms_file = LMS_DIR / "static" / filename
        if lms_file.is_file():
            return send_from_directory(LMS_DIR / "static", filename)
        return send_from_directory(MGS_STATIC, filename)

    @app.route("/")
    def landing():
        """Public landing: Staff Login, IT Login, Student Code."""
        returning = request.cookies.get("lloves_seen") == "1"
        return render_template(
            "landing.html",
            **landing_kwargs(one_tap_auto=returning),
        )

    @app.route("/health")
    def health():
        """Fly / DNS liveness — no auth."""
        return jsonify({"ok": True, "school": SCHOOL_SHORT})

    @app.route("/it")
    @it_required
    def it_dashboard():
        """IT: activate semester, register staff, assign Ontario courses."""
        user = current_user()
        semesters = school.list_semesters()
        active = school.get_active_semester()
        offerings = school.list_offerings(semester_id=active["id"] if active else None)
        from flask import make_response

        html = render_template(
            "it/dashboard.html",
            user=user,
            semesters=semesters,
            active=active,
            staff=school.list_staff(),
            offerings=offerings,
            courses=school.search_ontario_courses("", limit=80),
            school_name=SCHOOL_NAME,
        )
        resp = make_response(html)
        resp.set_cookie("lloves_seen", "1", max_age=86400 * 400, samesite="Lax")
        return resp

    @app.route("/it/semesters/activate", methods=["POST"])
    @it_required
    def it_activate_semester():
        """Clone ``frameworks/semester.json`` (or switch an existing row)."""
        existing_id = request.form.get("semester_id")
        if existing_id:
            school.set_active_semester(int(existing_id))
        else:
            school.activate_from_semester_json()
        return redirect(url_for("it_dashboard"))

    @app.route("/it/staff", methods=["POST"])
    @it_required
    def it_register_staff():
        """Allowlist a personal Google email as staff."""
        try:
            school.register_staff(
                request.form.get("email") or "",
                request.form.get("display_name") or None,
            )
        except ValueError as exc:
            return render_template(
                "forbidden.html", message=str(exc)
            ), 400
        return redirect(url_for("it_dashboard"))

    @app.route("/it/courses")
    @it_required
    def it_search_courses():
        """JSON autocomplete for Ontario course codes."""
        q = request.args.get("q") or ""
        return jsonify({"ok": True, "courses": school.search_ontario_courses(q)})

    @app.route("/it/offerings", methods=["POST"])
    @it_required
    def it_assign_course():
        """Assign a catalog course to a teacher; mint/reuse the 8-char key."""
        teacher_id = int(request.form.get("teacher_user_id") or 0)
        code = (request.form.get("ontario_code") or "").strip().upper()
        try:
            school.assign_course(teacher_user_id=teacher_id, ontario_code=code)
        except (ValueError, KeyError) as exc:
            return render_template("forbidden.html", message=str(exc)), 400
        return redirect(url_for("it_dashboard"))

    @app.route("/it/offerings/<int:offering_id>/rotate", methods=["POST"])
    @it_required
    def it_rotate_code(offering_id: int):
        """Rotate the shared student key for a (semester, course) pair."""
        school.rotate_live_access_code(offering_id)
        return redirect(url_for("it_dashboard"))

    @app.route("/staff")
    @staff_required
    def staff_home():
        """Populate Class / Start Existing Class."""
        user = current_user()
        assert user is not None
        active = school.get_active_semester()
        offerings = []
        classes = []
        if active:
            offerings = school.list_offerings(
                teacher_user_id=int(user["id"]), semester_id=int(active["id"])
            )
            classes = school.list_staff_classes(int(user["id"]), int(active["id"]))
        from flask import make_response

        html = render_template(
            "staff/home.html",
            user=user,
            active=active,
            offerings=offerings,
            classes=classes,
            time_options=list(TIME_OPTIONS),
            school_name=SCHOOL_NAME,
        )
        resp = make_response(html)
        resp.set_cookie("lloves_seen", "1", max_age=86400 * 400, samesite="Lax")
        return resp

    @app.route("/api/staff/defaults")
    @staff_required
    def staff_defaults():
        """Wizard defaults: inherited semester, assigned offerings, times."""
        user = current_user()
        assert user is not None
        active = school.get_active_semester()
        offerings = []
        if active:
            offerings = school.list_offerings(
                teacher_user_id=int(user["id"]), semester_id=int(active["id"])
            )
        return jsonify(
            {
                "ok": True,
                "semester": active,
                "offerings": offerings,
                "time_options": list(TIME_OPTIONS),
                "day_options": wizard_defaults()["day_options"],
            }
        )

    @app.route("/api/staff/classes", methods=["GET", "POST"])
    @staff_required
    def staff_classes():
        """List or populate a class (Codenames only — no Canvas CSV)."""
        user = current_user()
        assert user is not None
        if request.method == "GET":
            active = school.get_active_semester()
            classes = (
                school.list_staff_classes(int(user["id"]), int(active["id"]))
                if active
                else []
            )
            return jsonify({"ok": True, "classes": classes, "semester": active})
        body = request.get_json(silent=True) or {}
        if body.get("csv_text"):
            return jsonify(
                {"ok": False, "error": "Canvas CSV import is not available in LLOVES."}
            ), 400
        try:
            offering_id = int(body.get("offering_id") or 0)
            offering = school.get_offering(offering_id)
        except (TypeError, ValueError, KeyError):
            return jsonify(
                {"ok": False, "error": "No course assignment. Ask IT to assign a course."}
            ), 403
        if int(offering["teacher_user_id"]) != int(user["id"]):
            if user["role"] != "it":
                return jsonify(
                    {"ok": False, "error": "No course assignment. Ask IT to assign a course."}
                ), 403
        semester = school.get_semester(int(offering["semester_id"]))
        if not semester:
            return jsonify({"ok": False, "error": "Semester is missing."}), 400
        names = body.get("codenames") or []
        if not isinstance(names, list):
            return jsonify({"ok": False, "error": "codenames must be a list"}), 400
        try:
            created = school.game.create_class(
                year=str(semester["year_display"]),
                semester=str(semester["term"]),
                course_code=str(offering["ontario_code"]),
                days_preset=str(body.get("days") or ""),
                time_label=str(body.get("time") or ""),
                codenames=[str(n) for n in names],
                offering_id=int(offering["id"]),
                teacher_user_id=int(user["id"]),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        created = school.enrich_class(created)
        return jsonify({"ok": True, "class": created})

    @app.route("/staff/class/<int:class_id>")
    @staff_required
    def staff_course(class_id: int):
        """Course dashboard shell: Modules / Syllabus / Grades."""
        user = current_user()
        assert user is not None
        if not school.teacher_owns_class(int(user["id"]), class_id):
            abort(403)
        cls = school.enrich_class(school.game.get_class(class_id))
        offering = school.get_offering(int(cls["offering_id"])) if cls.get("offering_id") else None
        expectations = []
        if offering:
            expectations = school.list_expectations(str(offering["ontario_code"]))
        tab = request.args.get("tab") or "modules"
        return render_template(
            "staff/course.html",
            user=user,
            cls=cls,
            offering=offering,
            expectations=expectations,
            tab=tab,
            school_name=SCHOOL_NAME,
        )

    @app.route("/api/staff/class/<int:class_id>/modules")
    @staff_required
    def staff_modules_nav(class_id: int):
        """JSON module tree for the Modules tab."""
        user = current_user()
        assert user is not None
        if not school.teacher_owns_class(int(user["id"]), class_id):
            return jsonify({"ok": False, "error": "Forbidden"}), 403
        cls = school.enrich_class(school.game.get_class(class_id))
        code = str(cls.get("ontario_code") or cls.get("course_code") or "")
        imscc = imscc_path_for_code(code, cls.get("imscc_path"))
        unpacked = unpacked_dir_for_code(code)
        status = {"ok": True, "unpacked": False, "error": None}
        if imscc:
            status = ensure_unpacked(imscc, unpacked)
        inventory = load_inventory(code)
        if not inventory:
            return jsonify(
                {
                    "ok": True,
                    "empty": True,
                    "message": status.get("error")
                    or "No module pack for this course yet.",
                    "modules": [],
                }
            )
        if not (unpacked / "wiki_content").is_dir():
            return jsonify(
                {
                    "ok": True,
                    "empty": True,
                    "message": status.get("error")
                    or "Module files are not unpacked on this machine.",
                    "modules": module_nav(inventory),
                }
            )
        return jsonify(
            {"ok": True, "empty": False, "modules": module_nav(inventory), "code": code}
        )

    @app.route("/lms/modules/<code>/item")
    @staff_required
    def module_item(code: str):
        """Serve a wiki page, file, or titled placeholder."""
        kind = request.args.get("kind") or "page"
        title = request.args.get("title") or "Item"
        href = request.args.get("href") or ""
        content_type = request.args.get("type") or ""
        if kind == "placeholder" or content_type in {
            "Quizzes::Quiz",
            "Assignment",
            "DiscussionTopic",
        }:
            return placeholder_html(title, content_type)
        if kind == "header":
            return wrap_page(title, f"<h1>{title}</h1>")
        unpacked = unpacked_dir_for_code(code)
        if href.startswith("web_resources/") or kind == "file":
            target = safe_unpacked_file(unpacked, href)
            if not target:
                abort(404)
            return send_from_directory(target.parent, target.name)
        rel = href if href.startswith("wiki_content/") else f"wiki_content/{href}"
        target = safe_unpacked_file(unpacked, rel)
        if not target:
            return wrap_page(
                title,
                f"<h1>{title}</h1><p>This page is not in the unpacked module pack.</p>",
            ), 404
        raw = target.read_text(encoding="utf-8", errors="replace")
        return wrap_page(title, rewrite_wiki_html(raw, code))

    @app.route("/lms/modules/<code>/files/<path:rel>")
    @staff_required
    def module_file(code: str, rel: str):
        """Serve a rewritten IMSCC asset from the unpacked tree."""
        unpacked = unpacked_dir_for_code(code)
        target = safe_unpacked_file(unpacked, rel)
        if not target:
            abort(404)
        return send_from_directory(target.parent, target.name)

    @app.route("/staff/class/<int:class_id>/syllabus")
    @staff_required
    def staff_syllabus(class_id: int):
        """Saved month-grid or a prompt to open the click-to-place editor."""
        user = current_user()
        assert user is not None
        if not school.teacher_owns_class(int(user["id"]), class_id):
            abort(403)
        cls = school.enrich_class(school.game.get_class(class_id))
        label = str(cls.get("semester_label") or "")
        code = str(cls.get("ontario_code") or cls.get("course_code") or "")
        saved = syllabus_mod.saved_html_path(label, code) if label else None
        if saved and request.args.get("view") != "edit":
            return saved.read_text(encoding="utf-8")
        return redirect(url_for("staff_syllabus_editor", class_id=class_id))

    @app.route("/staff/class/<int:class_id>/syllabus/editor")
    @staff_required
    def staff_syllabus_editor(class_id: int):
        """Embedded click-to-place editor; calendar locked from IT semester."""
        user = current_user()
        assert user is not None
        if not school.teacher_owns_class(int(user["id"]), class_id):
            abort(403)
        cls = school.enrich_class(school.game.get_class(class_id))
        semester = school.get_active_semester()
        if cls.get("offering_id"):
            offering = school.get_offering(int(cls["offering_id"]))
            if offering:
                semester = school.get_semester(int(offering["semester_id"]))
        if not semester:
            return wrap_page(
                "Syllabus",
                "<h1>Syllabus</h1><p>Ask IT to activate a semester first.</p>",
            )
        calendar = syllabus_mod.calendar_from_semester_row(semester)
        slots = syllabus_mod.slots_from_class(str(cls["days"]), str(cls["time"]))
        imscc = imscc_path_for_code(
            str(cls.get("ontario_code") or cls["course_code"]),
            cls.get("imscc_path"),
        )
        try:
            modules = syllabus_mod.load_editor_modules(imscc)
        except ValueError as exc:
            return wrap_page("Syllabus", f"<h1>Syllabus</h1><p>{exc}</p>")
        if not modules:
            return wrap_page(
                "Syllabus",
                "<h1>Syllabus</h1><p>No module pack for this course yet. "
                "The click-to-place editor needs an IMSCC cartridge.</p>",
            )
        save_url = url_for("staff_syllabus_save", class_id=class_id)
        html_out = syllabus_mod.build_editor_page(
            course=str(cls.get("ontario_code") or cls["course_code"]),
            calendar=calendar,
            slots=slots,
            modules=modules,
            save_url=save_url,
        )
        return html_out

    @app.route("/staff/class/<int:class_id>/syllabus/save", methods=["POST"])
    @staff_required
    def staff_syllabus_save(class_id: int):
        """Write CSV + HTML + answers JSON per offering. No sequential packer."""
        user = current_user()
        assert user is not None
        if not school.teacher_owns_class(int(user["id"]), class_id):
            return jsonify({"ok": False, "error": "Forbidden"}), 403
        cls = school.enrich_class(school.game.get_class(class_id))
        semester = school.get_active_semester()
        if cls.get("offering_id"):
            offering = school.get_offering(int(cls["offering_id"]))
            if offering:
                semester = school.get_semester(int(offering["semester_id"]))
        if not semester:
            return jsonify({"ok": False, "error": "No active semester"}), 400
        calendar = syllabus_mod.calendar_from_semester_row(semester)
        slots = syllabus_mod.slots_from_class(str(cls["days"]), str(cls["time"]))
        imscc = imscc_path_for_code(
            str(cls.get("ontario_code") or cls["course_code"]),
            cls.get("imscc_path"),
        )
        try:
            modules = syllabus_mod.load_editor_modules(imscc)
            payload = request.get_json(force=True, silent=False) or {}
            paths = syllabus_mod.save_placements(
                payload=payload,
                course=str(cls.get("ontario_code") or cls["course_code"]),
                semester_label=str(semester["label"]),
                calendar=calendar,
                slots=slots,
                modules=modules,
            )
        except (ValueError, json.JSONDecodeError, OSError, KeyError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify({"ok": True, **paths})

    @app.route("/class/<int:class_id>")
    @staff_required
    def class_redirect(class_id: int):
        """Send the old game-show class URL to the course dashboard."""
        return redirect(url_for("staff_course", class_id=class_id, tab="grades"))

    @app.route("/class/<int:class_id>/setup")
    @staff_required
    def class_setup(class_id: int):
        """Teacher game setup (attendance / teams)."""
        user = current_user()
        assert user is not None
        if not school.teacher_owns_class(int(user["id"]), class_id):
            abort(403)
        return send_from_directory(MGS_TEMPLATES, "setup.html")

    @app.route("/class/<int:class_id>/game")
    @staff_required
    def class_game(class_id: int):
        """Teacher scoring dashboard — students never get this route."""
        user = current_user()
        assert user is not None
        if not school.teacher_owns_class(int(user["id"]), class_id):
            abort(403)
        return send_from_directory(MGS_TEMPLATES, "game.html")

    @app.route("/scoreboard")
    @app.route("/scoreboard/<int:class_id>")
    @staff_or_student_scoreboard
    def scoreboard_page(class_id: int | None = None):
        """ESPN board: staff overlay or student join."""
        return send_from_directory(MGS_TEMPLATES, "scoreboard.html")

    @app.route("/student/waiting")
    @student_required
    def student_waiting():
        """Waiting room when the teacher has not started a live game."""
        offering = school.get_offering(int(session["student_offering_id"]))
        return render_template(
            "student/waiting.html",
            offering=offering,
            school_name=SCHOOL_NAME,
        )

    @app.route("/student/game")
    @student_required
    def student_game():
        """Student scoreboard-first live game (no scoring controls)."""
        if not session.get("student_class_id"):
            return redirect(url_for("student_waiting"))
        return send_from_directory(MGS_TEMPLATES, "scoreboard.html")

    @app.route("/student/pick", methods=["GET", "POST"])
    @student_required
    def student_pick():
        """Disambiguate overlapping live sections by Codename or days/time."""
        code = session.get("student_live_code") or ""
        live = school.live_games_for_access_code(code)
        error = None
        if request.method == "POST":
            class_id = request.form.get("class_id")
            codename = request.form.get("codename") or ""
            if class_id:
                chosen = next((g for g in live if str(g["class_id"]) == str(class_id)), None)
                if chosen:
                    session["student_class_id"] = int(chosen["class_id"])
                    return redirect(url_for("student_game"))
                error = "That section is not live."
            elif codename.strip():
                try:
                    match = school.find_class_by_codename(code, codename)
                except ValueError as exc:
                    match = None
                    error = str(exc)
                if match:
                    session["student_class_id"] = int(match["id"])
                    return redirect(url_for("student_game"))
                error = error or "No live section matched that Codename."
        return render_template(
            "student/pick.html",
            live=live,
            classes=school.classes_for_access_code(code),
            error=error,
            school_name=SCHOOL_NAME,
        )

    @app.route("/api/student/state")
    @student_required
    def student_state():
        """Waiting-room poll: join when a live game appears."""
        code = session.get("student_live_code") or ""
        live = school.live_games_for_access_code(code)
        if session.get("student_class_id"):
            still = [g for g in live if int(g["class_id"]) == int(session["student_class_id"])]
            if still:
                return jsonify({"ok": True, "status": "live", "redirect": url_for("student_game")})
        if len(live) == 1:
            session["student_class_id"] = int(live[0]["class_id"])
            return jsonify({"ok": True, "status": "live", "redirect": url_for("student_game")})
        if len(live) > 1:
            return jsonify({"ok": True, "status": "pick", "redirect": url_for("student_pick")})
        return jsonify({"ok": True, "status": "waiting"})


def _register_game_api(app: Flask, school: SchoolDB) -> None:
    """Mount Math Game Show JSON APIs with staff (or student scoreboard) auth."""

    def _require_class_staff(class_id: int) -> tuple[Any, int] | None:
        """Return a JSON 403/401 tuple if the current user cannot score this class."""
        user = current_user()
        if user is None:
            return jsonify({"ok": False, "error": "Authentication required."}), 401
        if not school.teacher_owns_class(int(user["id"]), class_id):
            return jsonify({"ok": False, "error": "Forbidden"}), 403
        return None

    def _dashboard_payload(class_id: int, sort: str) -> dict[str, Any]:
        """Spreadsheet JSON with offering metadata attached."""
        payload = school.game.dashboard(class_id, sort)
        payload["class"] = school.enrich_class(payload["class"])
        return payload

    @app.route("/api/classes/<int:class_id>/dashboard")
    @login_required
    def api_dashboard(class_id: int):
        """Grades spreadsheet payload."""
        denied = _require_class_staff(class_id)
        if denied:
            return denied
        sort = request.args.get("sort") or "az"
        try:
            return jsonify({"ok": True, **_dashboard_payload(class_id, sort)})
        except Exception as exc:  # noqa: BLE001
            return _json_error(exc)

    @app.route("/api/classes/<int:class_id>")
    @login_required
    def api_class(class_id: int):
        """One class row."""
        denied = _require_class_staff(class_id)
        if denied:
            return denied
        try:
            cls = school.enrich_class(school.game.get_class(class_id))
            return jsonify({"ok": True, "class": cls})
        except Exception as exc:  # noqa: BLE001
            return _json_error(exc)

    @app.route("/api/classes/<int:class_id>/game")
    @login_required
    def api_game_state(class_id: int):
        """Teacher game state."""
        denied = _require_class_staff(class_id)
        if denied:
            return denied
        try:
            return jsonify({"ok": True, **school.game.game_state(class_id)})
        except Exception as exc:  # noqa: BLE001
            return _json_error(exc)

    @app.route("/api/scoreboard")
    @app.route("/api/classes/<int:class_id>/scoreboard")
    @staff_or_student_scoreboard
    def api_scoreboard(class_id: int | None = None):
        """Public board: staff uses current class; students are scoped."""
        scoped = class_id
        if session.get("student_class_id") and current_user() is None:
            scoped = int(session["student_class_id"])
        try:
            return jsonify(school.game.scoreboard(scoped))
        except Exception as exc:  # noqa: BLE001
            return _json_error(exc)

    @app.route("/api/sessions/<int:session_id>/log")
    @login_required
    def api_session_log(session_id: int):
        """Plain-text game log."""
        try:
            path = school.game.session_log_path(session_id)
            return path.read_text(encoding="utf-8"), 200, {"Content-Type": "text/plain; charset=utf-8"}
        except Exception as exc:  # noqa: BLE001
            return _json_error(exc)

    @app.route("/api/classes/<int:class_id>/begin", methods=["POST"])
    @login_required
    def api_begin(class_id: int):
        """Start a new game (staff only)."""
        denied = _require_class_staff(class_id)
        if denied:
            return denied
        body = request.get_json(silent=True) or {}
        try:
            meeting = _optional_date(body.get("meeting_date"))
            state = school.game.begin_game(class_id, meeting_date=meeting)
            return jsonify({"ok": True, **state})
        except Exception as exc:  # noqa: BLE001
            return _json_error(exc)

    def _staff_post(class_id: int, handler):
        """Run a GameShowDB mutation for a staff-owned class."""
        denied = _require_class_staff(class_id)
        if denied:
            return denied
        body = request.get_json(silent=True) or {}
        try:
            return jsonify({"ok": True, **handler(body)})
        except Exception as exc:  # noqa: BLE001
            return _json_error(exc)

    @app.route("/api/classes/<int:class_id>/game/meeting", methods=["POST"])
    @login_required
    def api_meeting(class_id: int):
        """Set the live-game meeting date."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            chosen = _optional_date(body.get("meeting_date"))
            if chosen is None:
                raise ValueError("meeting_date is required (YYYY-MM-DD)")
            time_label = body.get("time")
            return school.game.set_meeting_date(
                class_id,
                chosen,
                time_label=str(time_label) if time_label else None,
            )

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/game/cancel", methods=["POST"])
    @login_required
    def api_cancel(class_id: int):
        """Quit setup without starting."""
        return _staff_post(class_id, lambda _b: school.game.cancel_setup(class_id))

    @app.route("/api/classes/<int:class_id>/game/attendance", methods=["POST"])
    @login_required
    def api_attendance(class_id: int):
        """Save who is present."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            ids = [int(x) for x in (body.get("present_ids") or [])]
            return school.game.save_attendance(class_id, ids)

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/game/step", methods=["POST"])
    @login_required
    def api_step(class_id: int):
        """Advance setup status."""
        return _staff_post(
            class_id,
            lambda body: school.game.set_setup_step(class_id, str(body.get("status") or "")),
        )

    @app.route("/api/classes/<int:class_id>/game/assign", methods=["POST"])
    @login_required
    def api_assign(class_id: int):
        """Assign teams."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            raw_assignments = body.get("assignments")
            if raw_assignments is not None and not isinstance(raw_assignments, list):
                raise ValueError("assignments must be a list")
            return school.game.assign_teams(
                class_id,
                int(body.get("n_teams") or 0),
                str(body.get("mode") or ""),
                assignments=raw_assignments,
            )

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/game/rename", methods=["POST"])
    @login_required
    def api_rename(class_id: int):
        """Rename teams."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            names = body.get("teams") or []
            if not isinstance(names, list):
                raise ValueError("teams must be a list")
            return school.game.rename_teams(class_id, names)

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/game/round", methods=["POST"])
    @login_required
    def api_round(class_id: int):
        """Start a scoring round."""
        return _staff_post(
            class_id,
            lambda body: school.game.start_round(class_id, int(body.get("round") or 0)),
        )

    @app.route("/api/classes/<int:class_id>/game/score", methods=["POST"])
    @login_required
    def api_score(class_id: int):
        """Award points — staff only."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            return school.game.award_points(
                class_id,
                kind=str(body.get("kind") or ""),
                target_id=int(body.get("id") or 0),
                amount=int(body.get("amount") or 0),
                team_rule=(str(body["team_rule"]) if body.get("team_rule") else None),
            )

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/game/add-student", methods=["POST"])
    @login_required
    def api_late(class_id: int):
        """Add a late student to a live game."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            return school.game.add_late_student(
                class_id,
                int(body.get("student_id") or 0),
                int(body.get("team_id") or 0),
            )

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/game/end", methods=["POST"])
    @login_required
    def api_end(class_id: int):
        """End the live game."""
        return _staff_post(class_id, lambda _b: school.game.end_game(class_id))

    @app.route("/api/classes/<int:class_id>/students", methods=["POST"])
    @login_required
    def api_add_student(class_id: int):
        """Add a Codename (LLOVES) or last/first (legacy)."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            return _dashboard_payload_from_add(class_id, body)

        return _staff_post(class_id, run)

    def _dashboard_payload_from_add(class_id: int, body: dict[str, Any]) -> dict[str, Any]:
        """Insert a roster row and return an enriched dashboard."""
        dash = school.game.add_student(
            class_id,
            first_name=str(body.get("first_name") or ""),
            last_display=str(body.get("last_display") or ""),
            sort=str(body.get("sort") or "az"),
            codename=body.get("codename"),
        )
        dash["class"] = school.enrich_class(dash["class"])
        return dash

    @app.route("/api/classes/<int:class_id>/students/delete", methods=["POST"])
    @login_required
    def api_del_student(class_id: int):
        """Remove a roster row."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            dash = school.game.delete_student(
                class_id,
                int(body.get("student_id") or 0),
                sort=str(body.get("sort") or "az"),
            )
            dash["class"] = school.enrich_class(dash["class"])
            return dash

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/sessions", methods=["POST"])
    @login_required
    def api_add_session(class_id: int):
        """Append a session column."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            chosen = _optional_date(body.get("meeting_date"))
            if chosen is None:
                raise ValueError("meeting_date is required (YYYY-MM-DD)")
            dash = school.game.add_session_column(
                class_id,
                chosen,
                time_label=str(body["time"]) if body.get("time") else None,
                sort=str(body.get("sort") or "az"),
            )
            dash["class"] = school.enrich_class(dash["class"])
            return dash

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/sessions/delete", methods=["POST"])
    @login_required
    def api_del_session(class_id: int):
        """Delete a session column."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            dash = school.game.delete_session_column(
                class_id,
                int(body.get("session_id") or 0),
                sort=str(body.get("sort") or "az"),
            )
            dash["class"] = school.enrich_class(dash["class"])
            return dash

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/subtotals", methods=["POST"])
    @login_required
    def api_freeze(class_id: int):
        """Freeze a SUBTOTAL column."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            dash = school.game.freeze_subtotal(
                class_id,
                name=str(body["name"]) if body.get("name") else None,
                sort=str(body.get("sort") or "az"),
            )
            dash["class"] = school.enrich_class(dash["class"])
            return dash

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/subtotals/rename", methods=["POST"])
    @login_required
    def api_rename_sub(class_id: int):
        """Rename a frozen subtotal."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            dash = school.game.rename_subtotal(
                class_id,
                int(body.get("id") or 0),
                str(body.get("name") or ""),
                sort=str(body.get("sort") or "az"),
            )
            dash["class"] = school.enrich_class(dash["class"])
            return dash

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/subtotals/delete", methods=["POST"])
    @login_required
    def api_del_sub(class_id: int):
        """Delete a frozen subtotal."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            dash = school.game.delete_subtotal(
                class_id,
                int(body.get("id") or 0),
                sort=str(body.get("sort") or "az"),
            )
            dash["class"] = school.enrich_class(dash["class"])
            return dash

        return _staff_post(class_id, run)

    @app.route("/api/classes/<int:class_id>/stat-window", methods=["POST"])
    @login_required
    def api_stat_window(class_id: int):
        """Set scoreboard stats period."""

        def run(body):
            """Apply one staff JSON mutation for this class."""
            dash = school.game.set_stat_window(
                class_id,
                str(body.get("window") or ""),
                sort=str(body.get("sort") or "az"),
            )
            dash["class"] = school.enrich_class(dash["class"])
            return dash

        return _staff_post(class_id, run)


if __name__ == "__main__":
    port = int(os.getenv("PORT") or "8787")
    host = os.getenv("HOST") or "127.0.0.1"
    application = create_app()
    print(f"LLOVES LMS: http://{host}:{port}/")
    print(f"Database: {application.config['SCHOOL_DB'].db_path}")
    application.run(host=host, port=port, debug=os.getenv("FLASK_DEBUG") == "1")
