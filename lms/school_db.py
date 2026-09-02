"""School sqlite for LLOVES users, semesters, catalog, and course offerings."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from codes import generate_live_access_code
    from paths import GAME_SHOW, SEMESTER_JSON
except ImportError:  # ``python3 lms/app.py`` package import
    from lms.codes import generate_live_access_code
    from lms.paths import GAME_SHOW, SEMESTER_JSON

IT_EMAIL_DEFAULT = "solutions@mckenzian.com"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    google_sub TEXT UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL,
    verified_at TEXT,
    verification_code TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS semesters (
    id INTEGER PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,
    year_display TEXT NOT NULL,
    term TEXT NOT NULL,
    source_pdf TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS curriculum_documents (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    grades TEXT,
    subject TEXT,
    source_url TEXT,
    local_path TEXT
);

CREATE TABLE IF NOT EXISTS ontario_courses (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    grade INTEGER,
    pathway TEXT,
    document_id INTEGER REFERENCES curriculum_documents(id),
    content_root TEXT,
    verification_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS expectations (
    id INTEGER PRIMARY KEY,
    course_code TEXT NOT NULL,
    kind TEXT NOT NULL,
    code TEXT NOT NULL,
    parent_code TEXT,
    strand TEXT,
    statement TEXT NOT NULL,
    verification_status TEXT,
    UNIQUE(course_code, code)
);

CREATE TABLE IF NOT EXISTS course_offerings (
    id INTEGER PRIMARY KEY,
    semester_id INTEGER NOT NULL REFERENCES semesters(id),
    ontario_code TEXT NOT NULL REFERENCES ontario_courses(code),
    teacher_user_id INTEGER NOT NULL REFERENCES users(id),
    live_access_code TEXT NOT NULL,
    imscc_path TEXT,
    expectations_status TEXT NOT NULL DEFAULT 'unverified',
    student_options_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    UNIQUE(semester_id, ontario_code, teacher_user_id)
);

CREATE INDEX IF NOT EXISTS idx_live_access_code
    ON course_offerings(live_access_code);

CREATE TABLE IF NOT EXISTS student_code_attempts (
    id INTEGER PRIMARY KEY,
    ip TEXT NOT NULL,
    ts TEXT NOT NULL
);
"""


def _now() -> str:
    """Return a local ISO timestamp without microseconds."""
    return datetime.now().replace(microsecond=0).isoformat()


def parse_semester_label(semester: str) -> tuple[str, str]:
    """Turn ``2026-2027 S1`` into ``(2026/27, Semester 1)``.

    Args:
        semester: Value of ``semester.json``'s ``semester`` field.

    Returns:
        ``(year_display, term_name)``.
    """
    text = (semester or "").strip()
    parts = text.split()
    year_raw = parts[0] if parts else ""
    term = parts[1] if len(parts) > 1 else ""
    years = year_raw.split("-")
    if len(years) == 2 and years[0].isdigit() and years[1].isdigit():
        year_display = f"{years[0]}/{years[1][-2:]}"
    else:
        year_display = year_raw or "2026/27"
    if "S2" in term.upper():
        return year_display, "Semester 2"
    return year_display, "Semester 1"


class LovesDB:
    """School-level sqlite (users, semesters, offerings) on the shared LMS file."""

    def __init__(self, db_path: Path, *, it_email: str = IT_EMAIL_DEFAULT) -> None:
        """Open the school database and seed catalog + IT user.

        Args:
            db_path: Shared sqlite path (same file as Math Game Show).
            it_email: Bootstrap IT Google email.
        """
        self.db_path = db_path
        self.it_email = it_email.lower().strip()
        self._lock = threading.RLock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self._seed()
        self.conn.commit()

    def close(self) -> None:
        """Close the sqlite connection."""
        with self._lock:
            self.conn.close()

    def _seed(self) -> None:
        """Insert IT user, curriculum catalog, MCF3M expectations, default semester."""
        with self._lock:
            row = self.conn.execute(
                "SELECT id FROM users WHERE email = ?", (self.it_email,)
            ).fetchone()
            if row is None:
                self.conn.execute(
                    """
                    INSERT INTO users (email, display_name, role, created_at)
                    VALUES (?, ?, 'it', ?)
                    """,
                    (self.it_email, "IT", _now()),
                )
            if SEMESTER_JSON.is_file() and self.conn.execute(
                "SELECT COUNT(*) AS n FROM semesters"
            ).fetchone()["n"] == 0:
                self.activate_from_semester_json(SEMESTER_JSON, make_active=True)

    def activate_from_semester_json(
        self, path: Path | None = None, *, make_active: bool = True
    ) -> dict[str, Any]:
        """Insert or refresh a semester row from ``frameworks/semester.json``.

        Args:
            path: Path to semester JSON (default ``frameworks/semester.json``).
            make_active: If True, this semester becomes the inherited active one.
        """
        target = path or SEMESTER_JSON
        payload = json.loads(target.read_text(encoding="utf-8"))
        label = str(payload.get("semester") or "2026-2027 S1")
        year_display, term = parse_semester_label(label)
        source_pdf = str((payload.get("calendar") or {}).get("local_pdf") or "")
        blob = json.dumps(payload)
        with self._lock:
            existing = self.conn.execute(
                "SELECT id FROM semesters WHERE label = ?", (label,)
            ).fetchone()
            if existing:
                self.conn.execute(
                    """
                    UPDATE semesters
                    SET year_display = ?, term = ?, source_pdf = ?, payload_json = ?
                    WHERE id = ?
                    """,
                    (year_display, term, source_pdf, blob, int(existing["id"])),
                )
                semester_id = int(existing["id"])
            else:
                cur = self.conn.execute(
                    """
                    INSERT INTO semesters
                        (label, year_display, term, source_pdf, is_active,
                         payload_json, created_at)
                    VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (label, year_display, term, source_pdf, blob, _now()),
                )
                semester_id = int(cur.lastrowid)
            if make_active:
                self.conn.execute("UPDATE semesters SET is_active = 0")
                self.conn.execute(
                    "UPDATE semesters SET is_active = 1 WHERE id = ?", (semester_id,)
                )
            self.conn.commit()
        return self.get_semester(semester_id)

    def set_active_semester(self, semester_id: int) -> dict[str, Any]:
        """Mark one semester as the inherited active term.

        Args:
            semester_id: Semesters primary key.
        """
        self.get_semester(semester_id)
        with self._lock:
            self.conn.execute("UPDATE semesters SET is_active = 0")
            self.conn.execute(
                "UPDATE semesters SET is_active = 1 WHERE id = ?", (semester_id,)
            )
            self.conn.commit()
        return self.get_semester(semester_id)

    def list_semesters(self) -> list[dict[str, Any]]:
        """Return all semesters, active first."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM semesters ORDER BY is_active DESC, id DESC"
            ).fetchall()
        return [self._semester_dict(row) for row in rows]

    def active_semester(self) -> dict[str, Any] | None:
        """Return the inherited active semester, if any."""
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM semesters WHERE is_active = 1 LIMIT 1"
            ).fetchone()
        return self._semester_dict(row) if row else None

    def get_semester(self, semester_id: int) -> dict[str, Any]:
        """Return one semester or raise KeyError."""
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM semesters WHERE id = ?", (semester_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"semester {semester_id}")
        return self._semester_dict(row)

    def _semester_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Attach parsed payload and IT-dashboard fields to a semester row."""
        payload = json.loads(row["payload_json"])
        data = dict(row)
        instructional = payload.get("instructional") or {}
        exam = payload.get("exam_window") or {}
        data["payload"] = payload
        data["raw_json"] = payload
        data["instructional_first"] = instructional.get("first_day_of_school")
        data["instructional_last"] = instructional.get("last_instructional_day_before_exams")
        data["exam_window_json"] = json.dumps(exam.get("secondary_exam_days") or [])
        data["pd_days_json"] = json.dumps(payload.get("pd_days") or [])
        data["holidays_json"] = json.dumps(payload.get("holidays") or [])
        return data

    def get_user(self, user_id: int) -> dict[str, Any] | None:
        """Return a user by id."""
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Alias used by auth after Google / 2SV."""
        return self.get_user(user_id)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Return a user by email (case-insensitive)."""
        key = (email or "").strip().lower()
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE lower(email) = ?", (key,)
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_google_sub(self, sub: str) -> dict[str, Any] | None:
        """Return a user by Google subject identifier."""
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM users WHERE google_sub = ?", (sub,)
            ).fetchone()
        return dict(row) if row else None

    def register_staff(self, email: str, display_name: str = "") -> dict[str, Any]:
        """Add a staff Google email to the allowlist.

        Args:
            email: Personal Google account.
            display_name: Optional label.

        Returns:
            User dict.

        Raises:
            ValueError: If the email is empty or already IT-only conflict.
        """
        key = (email or "").strip().lower()
        if "@" not in key:
            raise ValueError("Enter a Google email address")
        existing = self.get_user_by_email(key)
        if existing:
            return existing
        with self._lock:
            cur = self.conn.execute(
                """
                INSERT INTO users (email, display_name, role, created_at)
                VALUES (?, ?, 'staff', ?)
                """,
                (key, (display_name or key.split("@")[0]).strip(), _now()),
            )
            self.conn.commit()
            user_id = int(cur.lastrowid)
        return self.get_user(user_id) or {}

    def list_staff(self) -> list[dict[str, Any]]:
        """Return IT and staff users."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM users ORDER BY role, email"
            ).fetchall()
        return [dict(row) for row in rows]

    def link_google(
        self, user_id: int, google_sub: str, display_name: str | None = None
    ) -> dict[str, Any]:
        """Attach a Google subject id after OAuth.

        Args:
            user_id: Users primary key.
            google_sub: Google ``sub`` claim.
            display_name: Optional profile name.
        """
        with self._lock:
            if display_name:
                self.conn.execute(
                    "UPDATE users SET google_sub = ?, display_name = ? WHERE id = ?",
                    (google_sub, display_name, user_id),
                )
            else:
                self.conn.execute(
                    "UPDATE users SET google_sub = ? WHERE id = ?",
                    (google_sub, user_id),
                )
            self.conn.commit()
        return self.get_user(user_id) or {}

    def set_verification_code(self, user_id: int, code: str) -> None:
        """Store a first-login email code."""
        with self._lock:
            self.conn.execute(
                "UPDATE users SET verification_code = ? WHERE id = ?",
                (code, user_id),
            )
            self.conn.commit()

    def mark_verified(self, user_id: int) -> dict[str, Any]:
        """Clear the email code and stamp verified_at."""
        with self._lock:
            self.conn.execute(
                """
                UPDATE users
                SET verified_at = ?, verification_code = NULL, last_login_at = ?
                WHERE id = ?
                """,
                (_now(), _now(), user_id),
            )
            self.conn.commit()
        return self.get_user(user_id) or {}

    def record_login(self, user_id: int) -> None:
        """Stamp last_login_at."""
        with self._lock:
            self.conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (_now(), user_id),
            )
            self.conn.commit()

    def list_ontario_courses(self, q: str = "") -> list[dict[str, Any]]:
        """Search the course catalog by code or title."""
        needle = f"%{(q or '').strip().upper()}%"
        with self._lock:
            if (q or "").strip():
                rows = self.conn.execute(
                    """
                    SELECT * FROM ontario_courses
                    WHERE upper(code) LIKE ? OR upper(title) LIKE ?
                    ORDER BY grade, code
                    """,
                    (needle, needle),
                ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT * FROM ontario_courses ORDER BY grade, code"
                ).fetchall()
        return [dict(row) for row in rows]

    def get_course(self, code: str) -> dict[str, Any] | None:
        """Return one catalog course."""
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM ontario_courses WHERE code = ?",
                ((code or "").strip().upper(),),
            ).fetchone()
        return dict(row) if row else None

    def expectations_for(self, code: str) -> list[dict[str, Any]]:
        """Return inherited overall/specific expectations for a course code."""
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT * FROM expectations
                WHERE course_code = ?
                ORDER BY kind DESC, code
                """,
                ((code or "").strip().upper(),),
            ).fetchall()
        return [dict(row) for row in rows]

    def _code_for_semester_course(self, semester_id: int, ontario_code: str) -> str | None:
        """Return the shared live-access code for this course this semester."""
        with self._lock:
            row = self.conn.execute(
                """
                SELECT live_access_code FROM course_offerings
                WHERE semester_id = ? AND ontario_code = ?
                LIMIT 1
                """,
                (semester_id, ontario_code),
            ).fetchone()
        return str(row["live_access_code"]) if row else None

    def assign_course(
        self, *, semester_id: int, ontario_code: str, teacher_user_id: int
    ) -> dict[str, Any]:
        """Assign an Ontario course to a teacher for a semester.

        Mints one 8-character live-access code per (semester, course), reused
        if another teacher is assigned the same course.

        Args:
            semester_id: Active or chosen semester.
            ontario_code: Catalog course code.
            teacher_user_id: Staff or IT user id.

        Returns:
            Offering dict.

        Raises:
            KeyError: If semester, course, or user is missing.
            ValueError: If the teacher is not registered.
        """
        code = (ontario_code or "").strip().upper()
        if self.get_course(code) is None:
            raise KeyError(f"course {code}")
        self.get_semester(semester_id)
        teacher = self.get_user(teacher_user_id)
        if teacher is None:
            raise KeyError(f"user {teacher_user_id}")
        existing = self.get_offering_for(semester_id, code, teacher_user_id)
        if existing:
            return existing
        shared = self._code_for_semester_course(semester_id, code)
        live_code = shared or generate_live_access_code()
        if shared is None:
            while self.get_offering_by_code(live_code):
                live_code = generate_live_access_code()
        expects = self.expectations_for(code)
        status = "verified" if expects else "unverified"
        imscc = None
        if code == "MCF3M":
            from paths import MCF3M_IMSCC

            if MCF3M_IMSCC.is_file():
                imscc = str(MCF3M_IMSCC)
        with self._lock:
            cur = self.conn.execute(
                """
                INSERT INTO course_offerings (
                    semester_id, ontario_code, teacher_user_id, live_access_code,
                    imscc_path, expectations_status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    semester_id,
                    code,
                    teacher_user_id,
                    live_code,
                    imscc,
                    status,
                    _now(),
                ),
            )
            self.conn.commit()
            offering_id = int(cur.lastrowid)
        return self.get_offering(offering_id)

    def get_offering(self, offering_id: int) -> dict[str, Any]:
        """Return one offering or raise KeyError."""
        with self._lock:
            row = self.conn.execute(
                """
                SELECT o.*, u.email AS teacher_email, u.display_name AS teacher_name,
                       s.label AS semester_label, s.year_display AS year_display,
                       s.term AS term, c.title AS course_title
                FROM course_offerings o
                JOIN users u ON u.id = o.teacher_user_id
                JOIN semesters s ON s.id = o.semester_id
                JOIN ontario_courses c ON c.code = o.ontario_code
                WHERE o.id = ?
                """,
                (offering_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"offering {offering_id}")
        return dict(row)

    def get_offering_for(
        self, semester_id: int, ontario_code: str, teacher_user_id: int
    ) -> dict[str, Any] | None:
        """Return the offering for this teacher/course/semester if present."""
        with self._lock:
            row = self.conn.execute(
                """
                SELECT id FROM course_offerings
                WHERE semester_id = ? AND ontario_code = ? AND teacher_user_id = ?
                """,
                (semester_id, (ontario_code or "").strip().upper(), teacher_user_id),
            ).fetchone()
        if row is None:
            return None
        return self.get_offering(int(row["id"]))

    def offerings_for_live_code(self, live_access_code: str) -> list[dict[str, Any]]:
        """Return every offering that shares this course live-access code."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT id FROM course_offerings WHERE live_access_code = ?",
                (live_access_code,),
            ).fetchall()
        return [self.get_offering(int(row["id"])) for row in rows]

    def get_offering_by_code(self, live_access_code: str) -> dict[str, Any] | None:
        """Look up a course offering by the shared student code."""
        found = self.offerings_for_live_code(live_access_code)
        return found[0] if found else None

    def list_offerings(
        self,
        *,
        semester_id: int | None = None,
        teacher_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """List offerings, optionally filtered."""
        clauses: list[str] = []
        args: list[Any] = []
        if semester_id is not None:
            clauses.append("o.semester_id = ?")
            args.append(semester_id)
        if teacher_user_id is not None:
            clauses.append("o.teacher_user_id = ?")
            args.append(teacher_user_id)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT o.*, u.email AS teacher_email, u.display_name AS teacher_name,
                   s.label AS semester_label, s.year_display AS year_display,
                   s.term AS term, c.title AS course_title
            FROM course_offerings o
            JOIN users u ON u.id = o.teacher_user_id
            JOIN semesters s ON s.id = o.semester_id
            JOIN ontario_courses c ON c.code = o.ontario_code
            {where}
            ORDER BY o.ontario_code, u.email
        """
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [dict(row) for row in rows]

    def list_curriculum_documents(self) -> list[dict[str, Any]]:
        """Return registered Ontario curriculum source documents."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM curriculum_documents ORDER BY subject, grades"
            ).fetchall()
        return [dict(row) for row in rows]

    def count_recent_code_attempts(self, ip: str, seconds: int = 600) -> int:
        """Count Student Code POSTs from an IP in the last ``seconds``."""
        cutoff = datetime.now().timestamp() - seconds
        with self._lock:
            rows = self.conn.execute(
                "SELECT ts FROM student_code_attempts WHERE ip = ?", (ip,)
            ).fetchall()
        n = 0
        for row in rows:
            try:
                ts = datetime.fromisoformat(str(row["ts"])).timestamp()
            except ValueError:
                continue
            if ts >= cutoff:
                n += 1
        return n

    def record_code_attempt(self, ip: str) -> int:
        """Log a Student Code attempt and return the recent-window count."""
        with self._lock:
            self.conn.execute(
                "INSERT INTO student_code_attempts (ip, ts) VALUES (?, ?)",
                (ip, _now()),
            )
            self.conn.commit()
        return self.count_recent_code_attempts(ip, seconds=600)


class SchoolDB(LovesDB):
    """LLOVES facade: school tables plus a GameShowDB on the same sqlite file."""

    def __init__(
        self,
        db_path: Path | None = None,
        data_dir: Path | None = None,
        *,
        it_email: str = IT_EMAIL_DEFAULT,
    ) -> None:
        """Open school + game-show tables.

        Args:
            db_path: Shared sqlite file.
            data_dir: Uploads/logs for Game Show.
            it_email: Bootstrap IT account.
        """
        import sys

        try:
            from paths import DEFAULT_DB_PATH, MGS_DIR
        except ImportError:
            from lms.paths import DEFAULT_DB_PATH, MGS_DIR

        path = Path(db_path or DEFAULT_DB_PATH)
        store = Path(data_dir or path.parent)
        super().__init__(path, it_email=it_email)
        if str(MGS_DIR) not in sys.path:
            sys.path.append(str(MGS_DIR))
        import importlib.util

        spec = importlib.util.spec_from_file_location("mgs_db", MGS_DIR / "db.py")
        if spec is None or spec.loader is None:
            raise ImportError("Math Game Show db.py is missing")
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("mgs_db", mod)
        spec.loader.exec_module(mod)
        self.game = mod.GameShowDB(path, store)

    def close(self) -> None:
        """Close both sqlite connections."""
        try:
            self.game.close()
        except Exception:
            pass
        super().close()

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """Alias for ``get_user``."""
        return self.get_user(user_id)

    def get_active_semester(self) -> dict[str, Any] | None:
        """Alias for ``active_semester``."""
        return self.active_semester()

    def search_ontario_courses(self, query: str = "", limit: int = 40) -> list[dict[str, Any]]:
        """Autocomplete wrapper with a row cap."""
        return self.list_ontario_courses(query)[: int(limit)]

    def get_ontario_course(self, code: str) -> dict[str, Any] | None:
        """Alias for ``get_course``."""
        return self.get_course(code)

    def list_expectations(self, course_code: str) -> list[dict[str, Any]]:
        """Alias for ``expectations_for``."""
        return self.expectations_for(course_code)

    def list_staff(self) -> list[dict[str, Any]]:
        """Staff list with pending/active status and assigned codes."""
        people = super().list_staff()
        out = []
        for person in people:
            item = dict(person)
            item["status"] = "active" if item.get("verified_at") else "pending"
            offs = self.list_offerings(teacher_user_id=int(item["id"]))
            item["assigned_codes"] = ", ".join(o["ontario_code"] for o in offs) or None
            out.append(item)
        return out

    def assign_course(
        self,
        *,
        teacher_user_id: int,
        ontario_code: str,
        semester_id: int | None = None,
        imscc_path: str | None = None,
    ) -> dict[str, Any]:
        """Assign a course using the active semester when ``semester_id`` is omitted."""
        semester = (
            self.get_semester(semester_id)
            if semester_id is not None
            else self.get_active_semester()
        )
        if not semester:
            raise ValueError("Activate a semester before assigning courses")
        if self.get_course(ontario_code) is None:
            raise ValueError(
                f"Unknown Ontario course code {ontario_code}. "
                "Ask IT to add a curriculum source."
            )
        offering = super().assign_course(
            semester_id=int(semester["id"]),
            ontario_code=ontario_code,
            teacher_user_id=teacher_user_id,
        )
        if imscc_path:
            with self._lock:
                self.conn.execute(
                    "UPDATE course_offerings SET imscc_path = ? WHERE id = ?",
                    (imscc_path, int(offering["id"])),
                )
                self.conn.commit()
            offering = self.get_offering(int(offering["id"]))
        return offering

    def rotate_live_access_code(self, offering_id: int) -> dict[str, Any]:
        """Mint a new shared key for this (semester, course) pair."""
        offering = self.get_offering(offering_id)
        new_code = generate_live_access_code()
        while self.get_offering_by_code(new_code):
            new_code = generate_live_access_code()
        with self._lock:
            self.conn.execute(
                """
                UPDATE course_offerings SET live_access_code = ?
                WHERE semester_id = ? AND ontario_code = ?
                """,
                (new_code, offering["semester_id"], offering["ontario_code"]),
            )
            self.conn.commit()
        return self.get_offering(offering_id)

    def record_code_attempt(self, ip: str) -> int:
        """Log an attempt and return the count in the last 10 minutes."""
        super().record_code_attempt(ip)
        return self.count_recent_code_attempts(ip, seconds=600) + 0

    def list_offerings(
        self,
        *,
        teacher_user_id: int | None = None,
        semester_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Offerings with class sections and roster sizes."""
        rows = super().list_offerings(
            semester_id=semester_id, teacher_user_id=teacher_user_id
        )
        out = []
        for item in rows:
            item = dict(item)
            item["classes"] = self.classes_for_offering(int(item["id"]))
            item["roster_size"] = sum(
                int(c.get("student_count") or 0) for c in item["classes"]
            )
            out.append(item)
        return out

    def classes_for_offering(self, offering_id: int) -> list[dict[str, Any]]:
        """Game-show sections linked to an offering."""
        with self.game._lock:
            rows = self.game.conn.execute(
                "SELECT * FROM classes WHERE offering_id = ? ORDER BY days, time, id",
                (int(offering_id),),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["student_count"] = self.game._student_count(int(item["id"]))
            result.append(item)
        return result

    def list_staff_classes(
        self, teacher_user_id: int, semester_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Classes this teacher populated in the (active) semester."""
        semester = (
            self.get_semester(semester_id)
            if semester_id is not None
            else self.get_active_semester()
        )
        if not semester:
            return []
        with self.game._lock:
            rows = self.game.conn.execute(
                """
                SELECT cl.*, o.live_access_code, o.ontario_code AS offering_code,
                       s.label AS semester_label
                FROM classes cl
                JOIN course_offerings o ON o.id = cl.offering_id
                JOIN semesters s ON s.id = o.semester_id
                WHERE cl.teacher_user_id = ? AND o.semester_id = ?
                ORDER BY cl.course_code, cl.days, cl.time
                """,
                (int(teacher_user_id), int(semester["id"])),
            ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["student_count"] = self.game._student_count(int(item["id"]))
            out.append(item)
        return out

    def teacher_owns_class(self, teacher_user_id: int, class_id: int) -> bool:
        """True when the class belongs to this teacher (IT may open any class)."""
        user = self.get_user(teacher_user_id)
        if user and user["role"] == "it":
            try:
                self.game.get_class(class_id)
            except KeyError:
                return False
            return True
        with self.game._lock:
            row = self.game.conn.execute(
                "SELECT teacher_user_id FROM classes WHERE id = ?",
                (int(class_id),),
            ).fetchone()
        return bool(row) and int(row["teacher_user_id"] or 0) == int(teacher_user_id)

    def live_games_for_access_code(self, live_access_code: str) -> list[dict[str, Any]]:
        """Live games for every section sharing this course key."""
        offering = self.get_offering_by_code(live_access_code)
        if not offering:
            return []
        with self.game._lock:
            rows = self.game.conn.execute(
                """
                SELECT g.id AS game_id, g.class_id, g.status, g.session_id,
                       cl.days, cl.time, cl.course_code, cl.offering_id
                FROM games g
                JOIN classes cl ON cl.id = g.class_id
                JOIN course_offerings o ON o.id = cl.offering_id
                WHERE o.semester_id = ? AND o.ontario_code = ? AND g.status = 'live'
                ORDER BY cl.days, cl.time, cl.id
                """,
                (offering["semester_id"], offering["ontario_code"]),
            ).fetchall()
        return [dict(r) for r in rows]

    def classes_for_access_code(self, live_access_code: str) -> list[dict[str, Any]]:
        """All class sections that share this student key."""
        offering = self.get_offering_by_code(live_access_code)
        if not offering:
            return []
        with self.game._lock:
            rows = self.game.conn.execute(
                """
                SELECT cl.* FROM classes cl
                JOIN course_offerings o ON o.id = cl.offering_id
                WHERE o.semester_id = ? AND o.ontario_code = ?
                ORDER BY cl.days, cl.time, cl.id
                """,
                (offering["semester_id"], offering["ontario_code"]),
            ).fetchall()
        return [dict(r) for r in rows]

    def find_class_by_codename(
        self, live_access_code: str, codename: str
    ) -> dict[str, Any] | None:
        """Disambiguate overlapping live sections by roster Codename."""
        name = (codename or "").strip()
        if not name:
            return None
        classes = self.classes_for_access_code(live_access_code)
        matches = []
        with self.game._lock:
            for cls in classes:
                row = self.game.conn.execute(
                    """
                    SELECT id FROM students
                    WHERE class_id = ? AND lower(codename) = ?
                    """,
                    (int(cls["id"]), name.lower()),
                ).fetchone()
                if row:
                    matches.append(cls)
        if len(matches) == 1:
            return matches[0]
        return None

    def enrich_class(self, class_payload: dict[str, Any]) -> dict[str, Any]:
        """Attach offering semester label and live access code."""
        offering_id = class_payload.get("offering_id")
        if not offering_id:
            return class_payload
        try:
            offering = self.get_offering(int(offering_id))
        except KeyError:
            return class_payload
        try:
            semester = self.get_semester(int(offering["semester_id"]))
        except KeyError:
            semester = {}
        class_payload["live_access_code"] = offering["live_access_code"]
        class_payload["semester_label"] = (semester or {}).get("label")
        class_payload["ontario_code"] = offering["ontario_code"]
        class_payload["expectations_status"] = offering.get("expectations_status")
        class_payload["imscc_path"] = offering.get("imscc_path")
        return class_payload

    def upsert_document(self, **fields: Any) -> int:
        """Insert or update a curriculum PDF registry row."""
        title = str(fields.get("title") or "").strip()
        with self._lock:
            existing = self.conn.execute(
                "SELECT id FROM curriculum_documents WHERE title = ?", (title,)
            ).fetchone()
            values = (
                title,
                str(fields.get("jurisdiction") or "Ontario"),
                fields.get("grades"),
                fields.get("subject"),
                fields.get("source_url"),
                fields.get("local_path"),
            )
            if existing:
                self.conn.execute(
                    """
                    UPDATE curriculum_documents
                    SET title = ?, jurisdiction = ?, grades = ?, subject = ?,
                        source_url = ?, local_path = ?
                    WHERE id = ?
                    """,
                    (*values, int(existing["id"])),
                )
                doc_id = int(existing["id"])
            else:
                cur = self.conn.execute(
                    """
                    INSERT INTO curriculum_documents
                        (title, jurisdiction, grades, subject, source_url, local_path)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                doc_id = int(cur.lastrowid)
            self.conn.commit()
        return doc_id

    def upsert_ontario_course(
        self,
        code: str,
        title: str,
        *,
        grade: int | None = None,
        pathway: str | None = None,
        document_id: int | None = None,
        content_root: str | None = None,
        expectations_status: str | None = None,
    ) -> None:
        """Insert or update one Ontario course-code catalog row."""
        key = (code or "").strip().upper()
        status = expectations_status or "unverified"
        with self._lock:
            cols = {
                row["name"]
                for row in self.conn.execute("PRAGMA table_info(ontario_courses)")
            }
            status_col = (
                "expectations_status" if "expectations_status" in cols else "verification_status"
            )
            self.conn.execute(
                f"""
                INSERT INTO ontario_courses (
                    code, title, grade, pathway, document_id, content_root, {status_col}
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    title = excluded.title,
                    grade = COALESCE(excluded.grade, ontario_courses.grade),
                    pathway = COALESCE(excluded.pathway, ontario_courses.pathway),
                    document_id = COALESCE(excluded.document_id, ontario_courses.document_id),
                    content_root = COALESCE(excluded.content_root, ontario_courses.content_root)
                """,
                (key, title.strip(), grade, pathway, document_id, content_root, status),
            )
            self.conn.commit()

    def replace_course_expectations(
        self, course_code: str, rows: list[dict[str, Any]], *, status: str
    ) -> int:
        """Replace overall/specific expectation rows for one course."""
        key = course_code.strip().upper()
        count = 0
        with self._lock:
            self.conn.execute("DELETE FROM expectations WHERE course_code = ?", (key,))
            for item in rows:
                statement = str(item.get("statement") or "").strip()
                code = str(item.get("code") or "").strip()
                kind = str(item.get("kind") or "").strip()
                if not statement or not code or kind not in {"overall", "specific"}:
                    continue
                self.conn.execute(
                    """
                    INSERT INTO expectations (
                        course_code, kind, code, parent_code, strand,
                        statement, verification_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        kind,
                        code,
                        item.get("parent_code"),
                        item.get("strand"),
                        statement,
                        str(item.get("verification_status") or status),
                    ),
                )
                count += 1
            cols = {
                row["name"]
                for row in self.conn.execute("PRAGMA table_info(ontario_courses)")
            }
            if "expectations_status" in cols:
                self.conn.execute(
                    "UPDATE ontario_courses SET expectations_status = ? WHERE code = ?",
                    (status, key),
                )
            elif "verification_status" in cols:
                self.conn.execute(
                    "UPDATE ontario_courses SET verification_status = ? WHERE code = ?",
                    (status, key),
                )
            self.conn.commit()
        return count
