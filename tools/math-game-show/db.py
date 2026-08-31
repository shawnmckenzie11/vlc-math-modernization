#!/usr/bin/env python3
"""SQLite schema and queries for the Math Game Show local app."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from csv_import import parse_canvas_grades_csv
from schedule import (
    TIME_OPTIONS,
    format_header_label,
    format_time_label,
    next_meeting_datetime,
    parse_time_label,
    store_days,
    unique_header_label,
)
from teams import (
    assign_balanced,
    assign_manual,
    assign_random,
    color_for_team,
    default_team_name,
    validate_team_count,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY,
    year TEXT NOT NULL,
    semester TEXT NOT NULL,
    course_code TEXT NOT NULL,
    days TEXT NOT NULL,
    time TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    canvas_id TEXT NOT NULL,
    last_display TEXT NOT NULL,
    first_name TEXT NOT NULL,
    UNIQUE(class_id, canvas_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    starts_at TEXT NOT NULL,
    header_label TEXT NOT NULL,
    status TEXT NOT NULL,
    log_path TEXT,
    source TEXT NOT NULL DEFAULT 'game'
);

CREATE TABLE IF NOT EXISTS session_scores (
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    present INTEGER NOT NULL DEFAULT 0,
    points REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, student_id)
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    event_seq INTEGER NOT NULL DEFAULT 0,
    last_event_json TEXT,
    owns_session INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS point_events (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    ts TEXT NOT NULL,
    from_kind TEXT NOT NULL,
    from_id INTEGER,
    to_kind TEXT NOT NULL,
    to_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    team_rule TEXT,
    UNIQUE(session_id, seq)
);

CREATE TABLE IF NOT EXISTS game_teams (
    id INTEGER PRIMARY KEY,
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS game_memberships (
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES game_teams(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    PRIMARY KEY (game_id, student_id)
);

CREATE TABLE IF NOT EXISTS team_buckets (
    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES game_teams(id) ON DELETE CASCADE,
    points REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (game_id, team_id)
);

CREATE TABLE IF NOT EXISTS subtotals (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    through_session_id INTEGER REFERENCES sessions(id) ON DELETE SET NULL,
    through_starts_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subtotal_scores (
    subtotal_id INTEGER NOT NULL REFERENCES subtotals(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    points REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (subtotal_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id);
CREATE INDEX IF NOT EXISTS idx_sessions_class ON sessions(class_id);
CREATE INDEX IF NOT EXISTS idx_games_class ON games(class_id);
CREATE INDEX IF NOT EXISTS idx_events_session ON point_events(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_subtotals_class ON subtotals(class_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_game
    ON games(class_id) WHERE status != 'ended';
"""

TEAM_RULES = ("each_member", "split_members", "team_only")


def split_amount(amount: float, n_members: int) -> list[float]:
    """Give each member the same share, rounded to one decimal place.

    The team board still shows the full awarded amount; any rounding
    leftover is stored on the team-only bucket (see ``award_points``).

    Args:
        amount: Points to split (must be positive).
        n_members: Present team size.

    Returns:
        Per-member credits, each ``round(amount / n, 1)``.
    """
    if n_members < 1:
        raise ValueError("Cannot split team points across an empty team")
    share = round(float(amount) / float(n_members), 1)
    return [share] * int(n_members)


def as_points(value: Any) -> float:
    """Round a credit to one decimal place.

    Args:
        value: Raw numeric (int, float, or SQLite number).

    Returns:
        Value rounded to one tenth.
    """
    return round(float(value or 0), 1)

# Future TODO (Teacher Game Dashboard): allow students to award points to one
# another. Scoring is teacher-only until then; keep the log `from` field.


class GameShowDB:
    """Thread-safe SQLite access for classes, sessions, and live games."""

    def __init__(self, db_path: Path, data_dir: Path) -> None:
        """Open (or create) the app database.

        Args:
            db_path: Path to ``app.sqlite``.
            data_dir: Root for uploads and JSONL logs.
        """
        self.db_path = db_path
        self.data_dir = data_dir
        self.logs_dir = data_dir / "logs"
        self.uploads_dir = data_dir / "uploads"
        self._lock = threading.RLock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Add columns introduced after the first schema.

        Existing local DBs keep their data; ``owns_session`` defaults to 0.
        """
        game_cols = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(games)").fetchall()
        }
        if "owns_session" not in game_cols:
            self.conn.execute(
                "ALTER TABLE games ADD COLUMN owns_session INTEGER NOT NULL DEFAULT 0"
            )
        self._ensure_real_points("session_scores")
        self._ensure_real_points("team_buckets")
        sess_cols = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "source" not in sess_cols:
            self.conn.execute(
                "ALTER TABLE sessions ADD COLUMN source TEXT NOT NULL DEFAULT 'game'"
            )

    def _ensure_real_points(self, table: str) -> None:
        """Rebuild a scores table if ``points`` still has INTEGER affinity.

        SQLite INTEGER columns coerce 3.3 to 3, which breaks 1-decimal splits.

        Args:
            table: ``session_scores`` or ``team_buckets``.
        """
        cols = list(self.conn.execute(f"PRAGMA table_info({table})").fetchall())
        if not cols:
            return
        points = next((row for row in cols if row["name"] == "points"), None)
        if points is None or str(points["type"]).upper() == "REAL":
            return
        self.conn.execute("PRAGMA foreign_keys = OFF")
        if table == "session_scores":
            self.conn.executescript(
                """
                CREATE TABLE session_scores_v2 (
                    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                    present INTEGER NOT NULL DEFAULT 0,
                    points REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (session_id, student_id)
                );
                INSERT INTO session_scores_v2
                    SELECT session_id, student_id, present, points FROM session_scores;
                DROP TABLE session_scores;
                ALTER TABLE session_scores_v2 RENAME TO session_scores;
                """
            )
        else:
            self.conn.executescript(
                """
                CREATE TABLE team_buckets_v2 (
                    game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
                    team_id INTEGER NOT NULL REFERENCES game_teams(id) ON DELETE CASCADE,
                    points REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (game_id, team_id)
                );
                INSERT INTO team_buckets_v2 SELECT game_id, team_id, points FROM team_buckets;
                DROP TABLE team_buckets;
                ALTER TABLE team_buckets_v2 RENAME TO team_buckets;
                """
            )
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        """Close the SQLite connection."""
        with self._lock:
            self.conn.close()

    def _now(self) -> str:
        """Return an ISO-8601 local timestamp."""
        return datetime.now().replace(microsecond=0).isoformat()

    def create_class(
        self,
        *,
        year: str,
        semester: str,
        course_code: str,
        days_preset: str,
        time_label: str,
        csv_text: str,
        today: date | None = None,
    ) -> dict[str, Any]:
        """Insert a class, roster, and the first template session column.

        Args:
            year: Display year such as ``2026/27``.
            semester: ``Semester 1`` or ``Semester 2``.
            course_code: e.g. ``MCF3M``.
            days_preset: ``M/W/F`` or ``T/Th/F``.
            time_label: One of the wizard times.
            csv_text: Canvas gradebook CSV contents.
            today: Optional reference date for the first meeting.

        Returns:
            Class dict including ``id`` and imported student count.
        """
        if not year.strip() or not semester.strip() or not course_code.strip():
            raise ValueError("Year, semester, and course code are required")
        if time_label not in TIME_OPTIONS:
            raise ValueError(f"Time must be one of: {', '.join(TIME_OPTIONS)}")
        roster = parse_canvas_grades_csv(csv_text)
        days = store_days(days_preset)
        meeting = next_meeting_datetime(days, time_label, today=today)
        header = format_header_label(meeting, time_label)
        created = self._now()
        with self._lock:
            cur = self.conn.execute(
                """
                INSERT INTO classes (year, semester, course_code, days, time, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (year.strip(), semester.strip(), course_code.strip(), days, time_label, created),
            )
            class_id = int(cur.lastrowid)
            for student in roster:
                self.conn.execute(
                    """
                    INSERT INTO students (class_id, canvas_id, last_display, first_name)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        class_id,
                        student["canvas_id"],
                        student["last_display"],
                        student["first_name"],
                    ),
                )
            self.conn.execute(
                """
                INSERT INTO sessions (class_id, starts_at, header_label, status, log_path)
                VALUES (?, ?, ?, 'template', NULL)
                """,
                (class_id, meeting.isoformat(), header),
            )
            session_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            student_ids = [
                int(row["id"])
                for row in self.conn.execute(
                    "SELECT id FROM students WHERE class_id = ?", (class_id,)
                )
            ]
            for sid in student_ids:
                self.conn.execute(
                    """
                    INSERT INTO session_scores (session_id, student_id, present, points)
                    VALUES (?, ?, 0, 0)
                    """,
                    (session_id, sid),
                )
            upload_path = self.uploads_dir / f"class-{class_id}.csv"
            upload_path.write_text(csv_text, encoding="utf-8")
            self.conn.commit()
        return self.get_class(class_id)

    def list_classes(self, year: str, semester: str) -> list[dict[str, Any]]:
        """Return classes whose year/semester match the picker filter.

        Args:
            year: Display year such as ``2026/27``.
            semester: ``Semester 1`` or ``Semester 2``.
        """
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT * FROM classes
                WHERE year = ? AND semester = ?
                ORDER BY created_at DESC, id DESC
                """,
                (year, semester),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_class(self, class_id: int) -> dict[str, Any]:
        """Return one class or raise KeyError.

        Args:
            class_id: Classes primary key.
        """
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM classes WHERE id = ?", (class_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"class {class_id}")
        payload = dict(row)
        payload["student_count"] = self._student_count(class_id)
        return payload

    def _student_count(self, class_id: int) -> int:
        """Count roster rows for a class.

        Args:
            class_id: Classes primary key.
        """
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM students WHERE class_id = ?", (class_id,)
        ).fetchone()
        return int(row["n"])

    def career_totals(self, class_id: int) -> dict[int, float]:
        """Sum credited individual scores per student (all columns).

        Dashboard TOTAL is the sum of each session's credited score, which
        comes from individual events plus any team-rule credits. Pure
        team-only awards never enter this total. Frozen SUBTOTAL columns
        are snapshots and are not added again here.

        Args:
            class_id: Classes primary key.

        Returns:
            Map of student_id → summed points.
        """
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT ss.student_id AS student_id, COALESCE(SUM(ss.points), 0) AS total
                FROM students s
                LEFT JOIN session_scores ss ON ss.student_id = s.id
                WHERE s.class_id = ?
                GROUP BY s.id
                """,
                (class_id,),
            ).fetchall()
        return {int(row["student_id"]): as_points(row["total"]) for row in rows}

    def dashboard(self, class_id: int, sort: str = "last") -> dict[str, Any]:
        """Spreadsheet payload: students, mixed columns, cells, totals.

        ``columns`` interleaves live-class sessions with frozen SUBTOTAL
        snapshots. ``live_subtotals`` sums only sessions after the latest
        freeze. ``totals`` still sums every live-class column.

        Args:
            class_id: Classes primary key.
            sort: ``first`` for First Last, ``last`` for Last, First.
        """
        cls = self.get_class(class_id)
        with self._lock:
            students = [
                dict(row)
                for row in self.conn.execute(
                    "SELECT * FROM students WHERE class_id = ?", (class_id,)
                )
            ]
            sessions = [
                dict(row)
                for row in self.conn.execute(
                    """
                    SELECT * FROM sessions
                    WHERE class_id = ?
                    ORDER BY starts_at ASC, id ASC
                    """,
                    (class_id,),
                )
            ]
            score_rows = self.conn.execute(
                """
                SELECT ss.session_id, ss.student_id, ss.present, ss.points
                FROM session_scores ss
                JOIN sessions se ON se.id = ss.session_id
                WHERE se.class_id = ?
                """,
                (class_id,),
            ).fetchall()
            subtotals = [
                dict(row)
                for row in self.conn.execute(
                    """
                    SELECT * FROM subtotals
                    WHERE class_id = ?
                    ORDER BY created_at ASC, id ASC
                    """,
                    (class_id,),
                )
            ]
            sub_score_rows = self.conn.execute(
                """
                SELECT ss.subtotal_id, ss.student_id, ss.points
                FROM subtotal_scores ss
                JOIN subtotals st ON st.id = ss.subtotal_id
                WHERE st.class_id = ?
                """,
                (class_id,),
            ).fetchall()
            open_game = self.conn.execute(
                """
                SELECT id, session_id, status FROM games
                WHERE class_id = ? AND status != 'ended'
                """,
                (class_id,),
            ).fetchone()
        cells: dict[str, dict[str, Any]] = {}
        totals: dict[int, float] = {int(s["id"]): 0.0 for s in students}
        per_session: dict[int, dict[int, float]] = {}
        for row in score_rows:
            sid = int(row["student_id"])
            sess_id = int(row["session_id"])
            pts = as_points(row["points"])
            totals[sid] = as_points(totals.get(sid, 0) + pts)
            per_session.setdefault(sess_id, {})[sid] = pts
            key = f"{sess_id}:{sid}"
            cells[key] = {
                "present": bool(row["present"]),
                "points": pts,
            }
        for row in sub_score_rows:
            cells[f"sub:{row['subtotal_id']}:{row['student_id']}"] = {
                "present": False,
                "points": as_points(row["points"]),
            }
        live_ids = self._live_session_ids(sessions, subtotals)
        live_subtotals: dict[int, float] = {int(s["id"]): 0.0 for s in students}
        for sess_id in live_ids:
            for sid, pts in per_session.get(sess_id, {}).items():
                live_subtotals[sid] = as_points(live_subtotals.get(sid, 0) + pts)
        if sort == "first":
            students.sort(
                key=lambda s: (
                    str(s["first_name"]).lower(),
                    str(s["last_display"]).lower(),
                )
            )
        else:
            students.sort(
                key=lambda s: (
                    str(s["last_display"]).lower(),
                    str(s["first_name"]).lower(),
                )
            )
        columns = self._sheet_columns(sessions, subtotals)
        return {
            "class": cls,
            "sort": "first" if sort == "first" else "last",
            "students": students,
            "sessions": sessions,
            "columns": columns,
            "cells": cells,
            "live_subtotals": {str(k): v for k, v in live_subtotals.items()},
            "totals": {str(k): v for k, v in totals.items()},
            "open_game": dict(open_game) if open_game else None,
            "time_options": list(TIME_OPTIONS),
        }

    def _live_session_ids(
        self,
        sessions: list[dict[str, Any]],
        subtotals: list[dict[str, Any]],
    ) -> set[int]:
        """Session ids that count toward the live SUBTOTAL column.

        After a freeze, only sessions created afterward (higher ids than
        ``through_session_id``) are live. Frozen snapshots stay unchanged.

        Args:
            sessions: Class sessions in display order.
            subtotals: Frozen snapshots oldest-first.
        """
        if not subtotals:
            return {int(s["id"]) for s in sessions}
        last = subtotals[-1]
        through_id = last.get("through_session_id")
        if through_id is not None:
            cutoff = int(through_id)
            return {int(s["id"]) for s in sessions if int(s["id"]) > cutoff}
        through_at = str(last["through_starts_at"])
        return {
            int(s["id"])
            for s in sessions
            if str(s["starts_at"]) > through_at
        }

    def _sheet_columns(
        self,
        sessions: list[dict[str, Any]],
        subtotals: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Place frozen SUBTOTAL columns, then any newer game columns to the right.

        A freeze includes every session that existed at snapshot time (ids up
        to ``through_session_id``). Later games — even with an earlier calendar
        date — stay to the right and count toward live SUBTOTAL and TOTAL,
        not the frozen snapshot.

        Args:
            sessions: Sessions in ``starts_at``, id order.
            subtotals: Frozen rows oldest-first.
        """
        remaining = list(sessions)
        columns: list[dict[str, Any]] = []
        cutoff = 0
        for sub in subtotals:
            through_id = sub.get("through_session_id")
            if through_id is not None:
                cutoff = max(cutoff, int(through_id))
            chunk = [s for s in remaining if int(s["id"]) <= cutoff]
            remaining = [s for s in remaining if int(s["id"]) > cutoff]
            for session in chunk:
                columns.append(self._session_column(session))
            columns.append(self._subtotal_column(sub))
        for session in remaining:
            columns.append(self._session_column(session))
        return columns

    def _session_column(self, session: dict[str, Any]) -> dict[str, Any]:
        """JSON column descriptor for a live-class session.

        Args:
            session: Sessions row.
        """
        return {
            "kind": "session",
            "id": int(session["id"]),
            "header_label": session["header_label"],
            "status": session["status"],
            "log_path": session.get("log_path"),
            "source": session.get("source") or "game",
        }

    def _subtotal_column(self, sub: dict[str, Any]) -> dict[str, Any]:
        """JSON column descriptor for a frozen SUBTOTAL.

        Args:
            sub: Subtotals row.
        """
        return {
            "kind": "subtotal",
            "id": int(sub["id"]),
            "header_label": sub["name"],
            "name": sub["name"],
        }

    def _ensure_session_scores(self, session_id: int, class_id: int) -> None:
        """Insert missing zero/absent cells for every student in a session.

        Args:
            session_id: Sessions primary key.
            class_id: Classes primary key.
        """
        self.conn.execute(
            """
            INSERT OR IGNORE INTO session_scores (session_id, student_id, present, points)
            SELECT ?, id, 0, 0 FROM students WHERE class_id = ?
            """,
            (session_id, class_id),
        )

    def _ensure_subtotal_scores(self, subtotal_id: int, class_id: int) -> None:
        """Insert missing zero cells for every student on a freeze.

        Args:
            subtotal_id: Subtotals primary key.
            class_id: Classes primary key.
        """
        self.conn.execute(
            """
            INSERT OR IGNORE INTO subtotal_scores (subtotal_id, student_id, points)
            SELECT ?, id, 0 FROM students WHERE class_id = ?
            """,
            (subtotal_id, class_id),
        )

    def add_student(
        self,
        class_id: int,
        first_name: str,
        last_display: str,
        sort: str = "last",
    ) -> dict[str, Any]:
        """Append a roster row and zero cells on every existing column.

        Args:
            class_id: Classes primary key.
            first_name: Given name.
            last_display: Family name as shown when sorting Last, First.
            sort: Dashboard name order to return.

        Returns:
            Updated dashboard payload.
        """
        first = first_name.strip()
        last = last_display.strip()
        if not first or not last:
            raise ValueError("First name and last name are required")
        self.get_class(class_id)
        with self._lock:
            canvas_id = f"manual-{class_id}-{int(time.time() * 1000)}"
            self.conn.execute(
                """
                INSERT INTO students (class_id, canvas_id, last_display, first_name)
                VALUES (?, ?, ?, ?)
                """,
                (class_id, canvas_id, last, first),
            )
            student_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            session_ids = [
                int(r["id"])
                for r in self.conn.execute(
                    "SELECT id FROM sessions WHERE class_id = ?", (class_id,)
                )
            ]
            for session_id in session_ids:
                self.conn.execute(
                    """
                    INSERT OR IGNORE INTO session_scores
                        (session_id, student_id, present, points)
                    VALUES (?, ?, 0, 0)
                    """,
                    (session_id, student_id),
                )
            sub_ids = [
                int(r["id"])
                for r in self.conn.execute(
                    "SELECT id FROM subtotals WHERE class_id = ?", (class_id,)
                )
            ]
            for sub_id in sub_ids:
                self._ensure_subtotal_scores(sub_id, class_id)
            self.conn.commit()
        return self.dashboard(class_id, sort)

    def delete_student(self, class_id: int, student_id: int, sort: str = "last") -> dict[str, Any]:
        """Remove a roster row unless they are on a live game team.

        Args:
            class_id: Classes primary key.
            student_id: Students primary key.
            sort: Dashboard name order to return.

        Returns:
            Updated dashboard payload.
        """
        with self._lock:
            row = self.conn.execute(
                "SELECT id FROM students WHERE id = ? AND class_id = ?",
                (student_id, class_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"student {student_id}")
            live = self.conn.execute(
                """
                SELECT m.student_id
                FROM game_memberships m
                JOIN games g ON g.id = m.game_id
                WHERE g.class_id = ? AND g.status = 'live' AND m.student_id = ?
                """,
                (class_id, student_id),
            ).fetchone()
            if live:
                raise ValueError("Cannot remove a student who is on a live game team")
            self.conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
            self.conn.commit()
        return self.dashboard(class_id, sort)

    def add_session_column(
        self,
        class_id: int,
        meeting_date: date,
        time_label: str | None = None,
        sort: str = "last",
    ) -> dict[str, Any]:
        """Add an empty live-class column at a chosen date and time.

        Args:
            class_id: Classes primary key.
            meeting_date: Calendar day for the column.
            time_label: One of the wizard times; defaults to the class time.
            sort: Dashboard name order to return.

        Returns:
            Updated dashboard payload.
        """
        cls = self.get_class(class_id)
        label = (time_label or cls["time"]).strip()
        if label not in TIME_OPTIONS:
            raise ValueError(f"Time must be one of: {', '.join(TIME_OPTIONS)}")
        meeting = datetime.combine(meeting_date, parse_time_label(label))
        with self._lock:
            header = self._label_for_meeting(class_id, cls, meeting, time_label=label)
            self._insert_session(
                class_id, meeting, header, status="template", source="manual"
            )
            self.conn.commit()
        return self.dashboard(class_id, sort)

    def delete_session_column(
        self,
        class_id: int,
        session_id: int,
        sort: str = "last",
    ) -> dict[str, Any]:
        """Delete a live-class column that is not used by an open game.

        Args:
            class_id: Classes primary key.
            session_id: Sessions primary key.
            sort: Dashboard name order to return.

        Returns:
            Updated dashboard payload.
        """
        with self._lock:
            row = self.conn.execute(
                "SELECT id FROM sessions WHERE id = ? AND class_id = ?",
                (session_id, class_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"session {session_id}")
            open_game = self.conn.execute(
                """
                SELECT id FROM games
                WHERE class_id = ? AND session_id = ? AND status != 'ended'
                """,
                (class_id, session_id),
            ).fetchone()
            if open_game:
                raise ValueError("Cannot delete the column used by the open game")
            self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self.conn.commit()
        return self.dashboard(class_id, sort)

    def freeze_subtotal(
        self,
        class_id: int,
        name: str | None = None,
        sort: str = "last",
    ) -> dict[str, Any]:
        """Snapshot current TOTAL into a frozen column after the last class.

        The live SUBTOTAL column then only sums newer live-class columns.
        TOTAL SCORE still sums every live-class column since the course start.

        Args:
            class_id: Classes primary key.
            name: Optional header; defaults to SUBTOTAL, SUBTOTAL 2, …
            sort: Dashboard name order to return.

        Returns:
            Updated dashboard payload.
        """
        self.get_class(class_id)
        with self._lock:
            last = self.conn.execute(
                """
                SELECT * FROM sessions
                WHERE class_id = ?
                ORDER BY starts_at DESC, id DESC
                LIMIT 1
                """,
                (class_id,),
            ).fetchone()
            if last is None:
                raise ValueError("Add a live-class column before logging a subtotal")
            label = self._unique_subtotal_name(class_id, name)
            self.conn.execute(
                """
                INSERT INTO subtotals (
                    class_id, name, through_session_id, through_starts_at, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    class_id,
                    label,
                    int(last["id"]),
                    str(last["starts_at"]),
                    self._now(),
                ),
            )
            sub_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            totals = {
                int(r["student_id"]): as_points(r["total"])
                for r in self.conn.execute(
                    """
                    SELECT s.id AS student_id, COALESCE(SUM(ss.points), 0) AS total
                    FROM students s
                    LEFT JOIN session_scores ss ON ss.student_id = s.id
                    WHERE s.class_id = ?
                    GROUP BY s.id
                    """,
                    (class_id,),
                )
            }
            for sid, pts in totals.items():
                self.conn.execute(
                    """
                    INSERT INTO subtotal_scores (subtotal_id, student_id, points)
                    VALUES (?, ?, ?)
                    """,
                    (sub_id, sid, pts),
                )
            self.conn.commit()
        return self.dashboard(class_id, sort)

    def rename_subtotal(
        self,
        class_id: int,
        subtotal_id: int,
        name: str,
        sort: str = "last",
    ) -> dict[str, Any]:
        """Rename a frozen SUBTOTAL column header.

        Args:
            class_id: Classes primary key.
            subtotal_id: Subtotals primary key.
            name: New header text.
            sort: Dashboard name order to return.

        Returns:
            Updated dashboard payload.
        """
        label = name.strip()
        if not label:
            raise ValueError("Subtotal name cannot be empty")
        with self._lock:
            cur = self.conn.execute(
                "UPDATE subtotals SET name = ? WHERE id = ? AND class_id = ?",
                (label, subtotal_id, class_id),
            )
            if cur.rowcount != 1:
                raise KeyError(f"subtotal {subtotal_id}")
            self.conn.commit()
        return self.dashboard(class_id, sort)

    def _unique_subtotal_name(self, class_id: int, name: str | None) -> str:
        """Pick a non-empty freeze label that is unique in this class.

        Args:
            class_id: Classes primary key.
            name: Teacher-supplied name, or None for SUBTOTAL.
        """
        raw = (name or "").strip() or "SUBTOTAL"
        existing = {
            str(r["name"])
            for r in self.conn.execute(
                "SELECT name FROM subtotals WHERE class_id = ?", (class_id,)
            )
        }
        if raw not in existing:
            return raw
        n = 2
        while f"{raw} {n}" in existing:
            n += 1
        return f"{raw} {n}"

    def _header_set(self, class_id: int, exclude_id: int | None = None) -> set[str]:
        """Headers already used by this class.

        Args:
            class_id: Classes primary key.
            exclude_id: Session id to ignore (when retargeting).
        """
        rows = self.conn.execute(
            "SELECT id, header_label FROM sessions WHERE class_id = ?",
            (class_id,),
        ).fetchall()
        return {
            str(row["header_label"])
            for row in rows
            if exclude_id is None or int(row["id"]) != exclude_id
        }

    def _meeting_datetime(
        self,
        cls: dict[str, Any],
        *,
        today: date | None,
        meeting_date: date | None,
    ) -> datetime:
        """Resolve the session start: override date, else next calendar slot.

        Does not skip forward just because a column already exists for that
        slot. Manual dates may fall on any weekday.

        Args:
            cls: Class row dict.
            today: Reference date for the default next meeting.
            meeting_date: Teacher-chosen calendar date, if any.
        """
        clock = parse_time_label(cls["time"])
        if meeting_date is not None:
            return datetime.combine(meeting_date, clock)
        return next_meeting_datetime(cls["days"], cls["time"], today=today)

    def _label_for_meeting(
        self,
        class_id: int,
        cls: dict[str, Any],
        meeting: datetime,
        exclude_id: int | None = None,
        time_label: str | None = None,
    ) -> str:
        """Build a unique header for ``meeting`` (``_2``, ``_3``, … if needed).

        Args:
            class_id: Classes primary key.
            cls: Class row dict.
            meeting: Session start.
            exclude_id: Session being retargeted, if any.
            time_label: Wizard time string; defaults to the class start time.
        """
        base = format_header_label(meeting, time_label or cls["time"])
        return unique_header_label(base, self._header_set(class_id, exclude_id))

    def _unused_template_session(self, class_id: int) -> dict[str, Any] | None:
        """Template column that has never been scored — safe to retarget.

        Args:
            class_id: Classes primary key.
        """
        row = self.conn.execute(
            """
            SELECT * FROM sessions
            WHERE class_id = ? AND status = 'template'
              AND COALESCE(source, 'game') = 'game'
            ORDER BY id ASC
            LIMIT 1
            """,
            (class_id,),
        ).fetchone()
        if row is None:
            return None
        used = self.conn.execute(
            """
            SELECT COUNT(*) AS n FROM session_scores
            WHERE session_id = ? AND (present = 1 OR points != 0)
            """,
            (row["id"],),
        ).fetchone()
        if int(used["n"]) > 0:
            return None
        return dict(row)

    def _insert_session(
        self,
        class_id: int,
        meeting: datetime,
        header: str,
        status: str = "template",
        source: str = "game",
    ) -> dict[str, Any]:
        """Insert a session column and zero cells.

        Args:
            class_id: Classes primary key.
            meeting: Session start.
            header: Unique header label.
            status: ``template`` or ``active``.
            source: ``game`` (Begin a New Game) or ``manual`` (added column).
        """
        self.conn.execute(
            """
            INSERT INTO sessions (
                class_id, starts_at, header_label, status, log_path, source
            )
            VALUES (?, ?, ?, ?, NULL, ?)
            """,
            (class_id, meeting.isoformat(), header, status, source),
        )
        session_id = int(self.conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        self._ensure_session_scores(session_id, class_id)
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row)

    def begin_game(
        self,
        class_id: int,
        today: date | None = None,
        meeting_date: date | None = None,
    ) -> dict[str, Any]:
        """Start or resume the single open game for a class.

        Default slot is the next calendar class time from ``today``, even if
        a column already exists for that meeting. Extra plays use ``_2``,
        ``_3``, … rather than bumping to the following class day.

        Args:
            class_id: Classes primary key.
            today: Optional reference date.
            meeting_date: Optional teacher override (any calendar day).

        Returns:
            Full game-state payload.
        """
        cls = self.get_class(class_id)
        with self._lock:
            existing = self.conn.execute(
                """
                SELECT * FROM games
                WHERE class_id = ? AND status != 'ended'
                """,
                (class_id,),
            ).fetchone()
            if existing:
                self.conn.commit()
                return self.game_state(class_id, game_id=int(existing["id"]))

            meeting = self._meeting_datetime(cls, today=today, meeting_date=meeting_date)
            unused = self._unused_template_session(class_id)
            if unused:
                frozen_through = self.conn.execute(
                    "SELECT 1 FROM subtotals WHERE through_session_id = ?",
                    (int(unused["id"]),),
                ).fetchone()
                if frozen_through:
                    unused = None
            if unused:
                header = self._label_for_meeting(
                    class_id, cls, meeting, exclude_id=int(unused["id"])
                )
                self.conn.execute(
                    """
                    UPDATE sessions
                    SET starts_at = ?, header_label = ?, status = 'active'
                    WHERE id = ?
                    """,
                    (meeting.isoformat(), header, unused["id"]),
                )
                session_id = int(unused["id"])
                owns_session = 0
                self._ensure_session_scores(session_id, class_id)
            else:
                header = self._label_for_meeting(class_id, cls, meeting)
                session = self._insert_session(class_id, meeting, header, status="active")
                session_id = int(session["id"])
                owns_session = 1
            cur = self.conn.execute(
                """
                INSERT INTO games (
                    class_id, session_id, status, created_at, owns_session
                )
                VALUES (?, ?, 'attendance', ?, ?)
                """,
                (class_id, session_id, self._now(), owns_session),
            )
            game_id = int(cur.lastrowid)
            self.conn.commit()
        return self.game_state(class_id, game_id=game_id)

    def set_meeting_date(
        self,
        class_id: int,
        meeting_date: date,
        time_label: str | None = None,
        today: date | None = None,
    ) -> dict[str, Any]:
        """Move the open setup session to a teacher-chosen date and time.

        Allowed until Create Teams. Suffixes the header if that slot already
        has a column. Does not change the class's usual schedule.

        Args:
            class_id: Classes primary key.
            meeting_date: Chosen calendar date (today or later).
            time_label: One of the wizard times; defaults to the class time.
            today: Reference date for the past-date check (tests inject this).

        Returns:
            Updated game state.
        """
        cls = self.get_class(class_id)
        if meeting_date < (today or date.today()):
            raise ValueError("Choose today or a future date")
        label = (time_label or cls["time"]).strip()
        if label not in TIME_OPTIONS:
            raise ValueError(f"Time must be one of: {', '.join(TIME_OPTIONS)}")
        with self._lock:
            game = self._game_row(class_id)
            if game["status"] not in {"attendance", "teams", "names"}:
                raise ValueError("Date can only be changed during setup")
            meeting = datetime.combine(meeting_date, parse_time_label(label))
            header = self._label_for_meeting(
                class_id,
                cls,
                meeting,
                exclude_id=int(game["session_id"]),
                time_label=label,
            )
            self.conn.execute(
                """
                UPDATE sessions
                SET starts_at = ?, header_label = ?
                WHERE id = ?
                """,
                (meeting.isoformat(), header, game["session_id"]),
            )
            self.conn.commit()
        return self.game_state(class_id)

    def cancel_setup(self, class_id: int) -> dict[str, Any]:
        """Abort Begin a New Game before Create Teams.

        Drops the in-progress game. A session this begin created is removed;
        a retargeted empty template column is restored.

        Args:
            class_id: Classes primary key.

        Returns:
            ``{ok, class_id}``.
        """
        with self._lock:
            game = self._game_row(class_id)
            if game["status"] not in {"attendance", "teams", "names"}:
                raise ValueError("Cancel is only available before Create Teams")
            game_id = int(game["id"])
            session_id = int(game["session_id"])
            owns = int(game["owns_session"] or 0)
            self.conn.execute("DELETE FROM point_events WHERE game_id = ?", (game_id,))
            self.conn.execute("DELETE FROM game_memberships WHERE game_id = ?", (game_id,))
            self.conn.execute("DELETE FROM team_buckets WHERE game_id = ?", (game_id,))
            self.conn.execute("DELETE FROM game_teams WHERE game_id = ?", (game_id,))
            self.conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
            if owns:
                self.conn.execute(
                    "DELETE FROM session_scores WHERE session_id = ?", (session_id,)
                )
                self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            else:
                self.conn.execute(
                    """
                    UPDATE session_scores
                    SET present = 0, points = 0
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )
                self.conn.execute(
                    """
                    UPDATE sessions
                    SET status = 'template', log_path = NULL
                    WHERE id = ?
                    """,
                    (session_id,),
                )
            self.conn.commit()
        return {"ok": True, "class_id": class_id}

    def _game_row(self, class_id: int, game_id: int | None = None) -> sqlite3.Row:
        """Load the open game, or a specific game id.

        Args:
            class_id: Classes primary key.
            game_id: Optional games primary key.

        Raises:
            KeyError: If no matching game exists.
        """
        if game_id is not None:
            row = self.conn.execute(
                "SELECT * FROM games WHERE id = ? AND class_id = ?",
                (game_id, class_id),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT * FROM games
                WHERE class_id = ? AND status != 'ended'
                """,
                (class_id,),
            ).fetchone()
        if row is None:
            raise KeyError("no open game")
        return row

    def previous_present_ids(self, class_id: int, session_id: int) -> list[int]:
        """Present student ids from the previous session column.

        First session defaults to all absent (empty list).

        Args:
            class_id: Classes primary key.
            session_id: Current session id.
        """
        with self._lock:
            current = self.conn.execute(
                "SELECT starts_at FROM sessions WHERE id = ? AND class_id = ?",
                (session_id, class_id),
            ).fetchone()
            if current is None:
                return []
            prev = self.conn.execute(
                """
                SELECT id FROM sessions
                WHERE class_id = ? AND id != ?
                  AND starts_at <= ?
                ORDER BY starts_at DESC, id DESC
                LIMIT 1
                """,
                (class_id, session_id, current["starts_at"]),
            ).fetchone()
            if prev is None:
                return []
            rows = self.conn.execute(
                """
                SELECT student_id FROM session_scores
                WHERE session_id = ? AND present = 1
                """,
                (prev["id"],),
            ).fetchall()
        return [int(r["student_id"]) for r in rows]

    def save_attendance(self, class_id: int, present_ids: list[int]) -> dict[str, Any]:
        """Mark present/absent on the open game's session and advance to teams.

        Args:
            class_id: Classes primary key.
            present_ids: Student ids who are present.

        Returns:
            Updated game state.
        """
        present_set = {int(x) for x in present_ids}
        with self._lock:
            game = self._game_row(class_id)
            if game["status"] not in {"attendance", "teams", "names"}:
                raise ValueError("Attendance can only be edited during setup")
            if not present_set:
                raise ValueError("Mark at least one student present")
            session_id = int(game["session_id"])
            students = self.conn.execute(
                "SELECT id FROM students WHERE class_id = ?", (class_id,)
            ).fetchall()
            for row in students:
                sid = int(row["id"])
                self.conn.execute(
                    """
                    UPDATE session_scores
                    SET present = ?, points = CASE WHEN ? = 0 THEN 0 ELSE points END
                    WHERE session_id = ? AND student_id = ?
                    """,
                    (1 if sid in present_set else 0, 1 if sid in present_set else 0, session_id, sid),
                )
            # Drop any teams from a previous pass through this setup.
            self.conn.execute(
                "DELETE FROM game_memberships WHERE game_id = ?", (game["id"],)
            )
            self.conn.execute(
                "DELETE FROM team_buckets WHERE game_id = ?", (game["id"],)
            )
            self.conn.execute(
                "DELETE FROM game_teams WHERE game_id = ?", (game["id"],)
            )
            self.conn.execute(
                "UPDATE games SET status = 'teams' WHERE id = ?", (game["id"],)
            )
            self.conn.commit()
        return self.game_state(class_id)

    def set_setup_step(self, class_id: int, status: str) -> dict[str, Any]:
        """Move the open game between attendance / teams / names.

        Args:
            class_id: Classes primary key.
            status: ``attendance``, ``teams``, or ``names``.

        Returns:
            Updated game state.
        """
        if status not in {"attendance", "teams", "names"}:
            raise ValueError("Setup step must be attendance, teams, or names")
        with self._lock:
            game = self._game_row(class_id)
            if game["status"] not in {"attendance", "teams", "names", "live"}:
                raise ValueError("Cannot change setup step after End Game")
            if game["status"] == "live":
                raise ValueError("Cannot return to setup during a live game")
            if status == "names":
                n_teams = self.conn.execute(
                    "SELECT COUNT(*) AS n FROM game_teams WHERE game_id = ?",
                    (game["id"],),
                ).fetchone()
                if int(n_teams["n"]) < 1:
                    raise ValueError("Assign teams before renaming them")
            self.conn.execute(
                "UPDATE games SET status = ? WHERE id = ?", (status, game["id"])
            )
            self.conn.commit()
        return self.game_state(class_id)

    def assign_teams(
        self,
        class_id: int,
        n_teams: int,
        mode: str,
        rng: Any | None = None,
        assignments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build teams from present students (random, balanced, or manual).

        Args:
            class_id: Classes primary key.
            n_teams: Number of teams.
            mode: ``random``, ``balanced``, or ``manual``.
            rng: Optional random.Random for tests.
            assignments: Required for ``manual``: ``{student_id, team_index}``.

        Returns:
            Updated game state including team names for the rename step.
        """
        with self._lock:
            game = self._game_row(class_id)
            if game["status"] not in {"teams", "names"}:
                raise ValueError("Assign teams during the setup wizard")
            session_id = int(game["session_id"])
            present_rows = self.conn.execute(
                """
                SELECT s.id AS id, s.last_display AS last_display, s.first_name AS first_name
                FROM session_scores ss
                JOIN students s ON s.id = ss.student_id
                WHERE ss.session_id = ? AND ss.present = 1
                """,
                (session_id,),
            ).fetchall()
            present_ids = [int(r["id"]) for r in present_rows]
            validate_team_count(int(n_teams), len(present_ids))
            totals_map = {}
            for sid in present_ids:
                row = self.conn.execute(
                    """
                    SELECT COALESCE(SUM(points), 0) AS total
                    FROM session_scores WHERE student_id = ?
                    """,
                    (sid,),
                ).fetchone()
                totals_map[sid] = as_points(row["total"])
            if mode == "balanced":
                buckets = assign_balanced(
                    present_ids, int(n_teams), [totals_map[sid] for sid in present_ids]
                )
            elif mode == "random":
                buckets = assign_random(present_ids, int(n_teams), rng=rng)
            elif mode == "manual":
                buckets = assign_manual(present_ids, int(n_teams), assignments or [])
            else:
                raise ValueError("mode must be random, balanced, or manual")
            game_id = int(game["id"])
            self.conn.execute("DELETE FROM game_memberships WHERE game_id = ?", (game_id,))
            self.conn.execute("DELETE FROM team_buckets WHERE game_id = ?", (game_id,))
            self.conn.execute("DELETE FROM game_teams WHERE game_id = ?", (game_id,))
            for order, members in enumerate(buckets):
                cur = self.conn.execute(
                    """
                    INSERT INTO game_teams (game_id, name, color, sort_order)
                    VALUES (?, ?, ?, ?)
                    """,
                    (game_id, default_team_name(order), color_for_team(order), order),
                )
                team_id = int(cur.lastrowid)
                self.conn.execute(
                    """
                    INSERT INTO team_buckets (game_id, team_id, points)
                    VALUES (?, ?, 0)
                    """,
                    (game_id, team_id),
                )
                for sid in members:
                    self.conn.execute(
                        """
                        INSERT INTO game_memberships (game_id, team_id, student_id)
                        VALUES (?, ?, ?)
                        """,
                        (game_id, team_id, sid),
                    )
            self.conn.execute(
                "UPDATE games SET status = 'names' WHERE id = ?", (game_id,)
            )
            self.conn.commit()
        return self.game_state(class_id)

    def rename_teams(self, class_id: int, names: list[dict[str, Any]]) -> dict[str, Any]:
        """Apply teacher team names, then move the game to live scoring.

        Args:
            class_id: Classes primary key.
            names: List of ``{id, name}`` for each team.

        Returns:
            Updated game state (status ``live``).
        """
        with self._lock:
            game = self._game_row(class_id)
            if game["status"] not in {"names", "live"}:
                raise ValueError("Rename teams after they have been assigned")
            game_id = int(game["id"])
            for item in names:
                team_id = int(item["id"])
                name = str(item.get("name") or "").strip()
                if not name:
                    raise ValueError("Team name cannot be empty")
                cur = self.conn.execute(
                    """
                    UPDATE game_teams SET name = ?
                    WHERE id = ? AND game_id = ?
                    """,
                    (name, team_id, game_id),
                )
                if cur.rowcount != 1:
                    raise KeyError(f"team {team_id}")
            self.conn.execute(
                "UPDATE games SET status = 'live' WHERE id = ?", (game_id,)
            )
            self.conn.commit()
        return self.game_state(class_id)

    def _append_log(self, session_id: int, record: dict[str, Any]) -> Path:
        """Append one JSONL scoring action under ``data/logs/``.

        Args:
            session_id: Sessions primary key.
            record: JSON-serializable log object.

        Returns:
            Path to the log file.
        """
        path = self.logs_dir / f"session-{session_id}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return path

    def _team_member_ids(self, game_id: int, team_id: int) -> list[int]:
        """Present members of a team, stable order for split remainder.

        Args:
            game_id: Games primary key.
            team_id: Game teams primary key.
        """
        rows = self.conn.execute(
            """
            SELECT m.student_id AS student_id
            FROM game_memberships m
            JOIN students s ON s.id = m.student_id
            WHERE m.game_id = ? AND m.team_id = ?
            ORDER BY s.last_display, s.first_name, s.id
            """,
            (game_id, team_id),
        ).fetchall()
        return [int(r["student_id"]) for r in rows]

    def _credit_student(self, session_id: int, student_id: int, amount: float) -> None:
        """Add ``amount`` to a present student's credited session score.

        Args:
            session_id: Sessions primary key.
            student_id: Students primary key.
            amount: Signed points (stored to one decimal place).
        """
        credit = as_points(amount)
        cur = self.conn.execute(
            """
            UPDATE session_scores
            SET points = ROUND(points + ?, 1)
            WHERE session_id = ? AND student_id = ? AND present = 1
            """,
            (credit, session_id, student_id),
        )
        if cur.rowcount != 1:
            raise KeyError(f"student {student_id} is not present this session")

    def _bump_team_bucket(self, game_id: int, team_id: int, amount: float) -> None:
        """Add ``amount`` to the persisted team-only bucket.

        Args:
            game_id: Games primary key.
            team_id: Game teams primary key.
            amount: Points (team awards are positive; stored to one decimal).
        """
        self.conn.execute(
            """
            UPDATE team_buckets
            SET points = ROUND(points + ?, 1)
            WHERE game_id = ? AND team_id = ?
            """,
            (as_points(amount), game_id, team_id),
        )

    def _insert_event(
        self,
        *,
        session_id: int,
        game_id: int,
        seq: int,
        to_kind: str,
        to_id: int,
        amount: int,
        team_rule: str | None,
    ) -> dict[str, Any]:
        """Append an immutable point event and a JSONL line.

        Args:
            session_id: Sessions primary key.
            game_id: Games primary key.
            seq: Monotonic per-game sequence.
            to_kind: ``student`` or ``team``.
            to_id: Student or team id.
            amount: Signed amount.
            team_rule: Team credit rule, or None for individual events.

        Returns:
            The log record written to JSONL.
        """
        ts = self._now()
        self.conn.execute(
            """
            INSERT INTO point_events (
                session_id, game_id, seq, ts, from_kind, from_id,
                to_kind, to_id, amount, team_rule
            )
            VALUES (?, ?, ?, ?, 'teacher', NULL, ?, ?, ?, ?)
            """,
            (session_id, game_id, seq, ts, to_kind, to_id, amount, team_rule),
        )
        record = {
            "ts": ts,
            "seq": seq,
            "from": "teacher",
            "to_kind": to_kind,
            "to": to_id,
            "amount": amount,
            "team_rule": team_rule,
        }
        log_path = self._append_log(session_id, record)
        self.conn.execute(
            "UPDATE sessions SET log_path = ? WHERE id = ?",
            (str(log_path), session_id),
        )
        return record

    def award_points(
        self,
        class_id: int,
        *,
        kind: str,
        target_id: int,
        amount: int,
        team_rule: str | None = None,
    ) -> dict[str, Any]:
        """Apply a teacher award as an immutable event plus live caches.

        Individual awards change that student's credited score and the team's
        ESPN total. Team awards always add ``amount`` to the team total, then
        credit members according to ``team_rule``:

        * ``each_member`` — every member's credited score += amount
        * ``split_members`` — each member gets ``round(amount / n, 1)``;
          leftover tenths go on the team bucket so the ESPN total stays
          the full award
        * ``team_only`` — team bucket only; individuals unchanged

        Team awards must be positive. Individual awards may be negative.
        Future TODO: students awarding points to one another.

        Args:
            class_id: Classes primary key.
            kind: ``student`` or ``team``.
            target_id: Student id or team id.
            amount: Signed integer (team awards must be > 0).
            team_rule: Required for team awards.

        Returns:
            Updated game state (includes last_event for the scoreboard).
        """
        if amount == 0:
            raise ValueError("Amount cannot be 0")
        if kind not in {"student", "team"}:
            raise ValueError("kind must be student or team")
        if kind == "team":
            if amount < 1:
                raise ValueError("Team awards must be positive")
            rule = (team_rule or "").strip()
            if rule not in TEAM_RULES:
                raise ValueError(
                    "Team awards need a rule: each_member, split_members, or team_only"
                )
        else:
            rule = None
        with self._lock:
            game = self._game_row(class_id)
            if game["status"] != "live":
                raise ValueError("Scoring starts after teams are created")
            game_id = int(game["id"])
            session_id = int(game["session_id"])
            seq = int(game["event_seq"] or 0) + 1
            last_event: dict[str, Any]
            if kind == "student":
                member = self.conn.execute(
                    """
                    SELECT team_id FROM game_memberships
                    WHERE game_id = ? AND student_id = ?
                    """,
                    (game_id, target_id),
                ).fetchone()
                if member is None:
                    raise KeyError(f"student {target_id} is not on a live team")
                self._credit_student(session_id, target_id, amount)
                team = dict(
                    self.conn.execute(
                        "SELECT * FROM game_teams WHERE id = ?",
                        (member["team_id"],),
                    ).fetchone()
                )
                last_event = {
                    "kind": "student",
                    "student_id": target_id,
                    "team_id": int(team["id"]),
                    "team_name": team["name"],
                    "amount": amount,
                    "team_rule": None,
                    "celebrate": amount > 0,
                    "label": f"{team['name']} {amount:+d}",
                }
                self._insert_event(
                    session_id=session_id,
                    game_id=game_id,
                    seq=seq,
                    to_kind="student",
                    to_id=target_id,
                    amount=amount,
                    team_rule=None,
                )
            else:
                team_row = self.conn.execute(
                    "SELECT * FROM game_teams WHERE id = ? AND game_id = ?",
                    (target_id, game_id),
                ).fetchone()
                if team_row is None:
                    raise KeyError(f"team {target_id}")
                member_ids = self._team_member_ids(game_id, target_id)
                if rule == "each_member":
                    for sid in member_ids:
                        self._credit_student(session_id, sid, amount)
                elif rule == "split_members":
                    shares = split_amount(amount, len(member_ids))
                    for sid, share in zip(member_ids, shares, strict=True):
                        if share:
                            self._credit_student(session_id, sid, share)
                    remainder = as_points(amount - sum(shares))
                    if remainder:
                        self._bump_team_bucket(game_id, target_id, remainder)
                else:
                    self._bump_team_bucket(game_id, target_id, amount)
                last_event = {
                    "kind": "team",
                    "team_id": target_id,
                    "team_name": team_row["name"],
                    "amount": amount,
                    "team_rule": rule,
                    "celebrate": True,
                    "label": f"{team_row['name']} +{amount}",
                }
                self._insert_event(
                    session_id=session_id,
                    game_id=game_id,
                    seq=seq,
                    to_kind="team",
                    to_id=target_id,
                    amount=amount,
                    team_rule=rule,
                )
            self.conn.execute(
                """
                UPDATE games
                SET event_seq = ?, last_event_json = ?
                WHERE id = ?
                """,
                (seq, json.dumps(last_event), game_id),
            )
            self.conn.commit()
        return self.game_state(class_id)

    def end_game(self, class_id: int) -> dict[str, Any]:
        """Close the live game; keep events, team scores, and credited cells.

        Individual credited scores are already on ``session_scores``. Team
        buckets and memberships stay so the session remains inspectable.
        Dashboard cells show credited scores only (not a blended formula).

        Args:
            class_id: Classes primary key.

        Returns:
            ``{ok, class_id, session_id, log_path}``.
        """
        with self._lock:
            game = self._game_row(class_id)
            if game["status"] != "live":
                raise ValueError("End Game is only available during a live game")
            session_id = int(game["session_id"])
            game_id = int(game["id"])
            log_path = self.logs_dir / f"session-{session_id}.jsonl"
            log_path.touch(exist_ok=True)
            self.conn.execute(
                """
                UPDATE sessions
                SET status = 'ended', log_path = ?
                WHERE id = ?
                """,
                (str(log_path), session_id),
            )
            self.conn.execute(
                "UPDATE games SET status = 'ended' WHERE id = ?", (game_id,)
            )
            self.conn.commit()
        return {
            "ok": True,
            "class_id": class_id,
            "session_id": session_id,
            "log_path": str(log_path),
        }

    def game_state(self, class_id: int, game_id: int | None = None) -> dict[str, Any]:
        """Full teacher-game payload (setup or live).

        Args:
            class_id: Classes primary key.
            game_id: Optional specific game (including just-ended).
        """
        cls = self.get_class(class_id)
        with self._lock:
            game = dict(self._game_row(class_id, game_id=game_id))
            session = dict(
                self.conn.execute(
                    "SELECT * FROM sessions WHERE id = ?", (game["session_id"],)
                ).fetchone()
            )
            session["meeting_date"] = str(session["starts_at"])[:10]
            try:
                started = datetime.fromisoformat(str(session["starts_at"]))
                session["time"] = format_time_label(started.time())
            except ValueError:
                session["time"] = cls["time"]
            students = [
                dict(r)
                for r in self.conn.execute(
                    "SELECT * FROM students WHERE class_id = ? ORDER BY last_display, first_name",
                    (class_id,),
                )
            ]
            scores = {
                int(r["student_id"]): {
                    "present": bool(r["present"]),
                    "points": as_points(r["points"]),
                }
                for r in self.conn.execute(
                    "SELECT student_id, present, points FROM session_scores WHERE session_id = ?",
                    (session["id"],),
                )
            }
            teams = [
                dict(r)
                for r in self.conn.execute(
                    """
                    SELECT t.*, COALESCE(b.points, 0) AS bucket
                    FROM game_teams t
                    LEFT JOIN team_buckets b
                      ON b.team_id = t.id AND b.game_id = t.game_id
                    WHERE t.game_id = ?
                    ORDER BY t.sort_order
                    """,
                    (game["id"],),
                )
            ]
            memberships = [
                dict(r)
                for r in self.conn.execute(
                    """
                    SELECT student_id, team_id FROM game_memberships
                    WHERE game_id = ?
                    """,
                    (game["id"],),
                )
            ]
        totals = self.career_totals(class_id)
        team_of = {int(m["student_id"]): int(m["team_id"]) for m in memberships}
        present_ids = [int(s["id"]) for s in students if scores.get(int(s["id"]), {}).get("present")]
        default_present = self.previous_present_ids(class_id, int(session["id"]))
        last_event = None
        if game.get("last_event_json"):
            try:
                last_event = json.loads(str(game["last_event_json"]))
            except json.JSONDecodeError:
                last_event = None
        teams_out: list[dict[str, Any]] = []
        for team in teams:
            members = []
            individual_sum = 0.0
            for student in students:
                sid = int(student["id"])
                if team_of.get(sid) != int(team["id"]):
                    continue
                pts = as_points(scores.get(sid, {}).get("points") or 0)
                individual_sum = as_points(individual_sum + pts)
                members.append(
                    {
                        **student,
                        "session_points": pts,
                        "career_total": as_points(totals.get(sid, 0)),
                    }
                )
            bucket = as_points(team["bucket"])
            teams_out.append(
                {
                    "id": int(team["id"]),
                    "name": team["name"],
                    "color": team["color"],
                    "sort_order": int(team["sort_order"]),
                    "bucket": bucket,
                    "individual_sum": individual_sum,
                    "score": as_points(individual_sum + bucket),
                    "members": members,
                }
            )
        return {
            "class": cls,
            "game": {
                "id": int(game["id"]),
                "status": game["status"],
                "session_id": int(game["session_id"]),
                "event_seq": int(game["event_seq"] or 0),
                "last_event": last_event,
            },
            "session": session,
            "students": [
                {
                    **s,
                    "present": scores.get(int(s["id"]), {}).get("present", False),
                    "session_points": scores.get(int(s["id"]), {}).get("points", 0),
                    "career_total": totals.get(int(s["id"]), 0),
                }
                for s in students
            ],
            "present_ids": present_ids,
            "default_present_ids": default_present,
            "teams": teams_out,
            "time_options": list(TIME_OPTIONS),
        }

    def scoreboard(self, class_id: int) -> dict[str, Any]:
        """Public ESPN-bar payload: team names, colors, scores, last event.

        No roster and no Canvas IDs.

        Args:
            class_id: Classes primary key.
        """
        try:
            state = self.game_state(class_id)
        except KeyError:
            return {
                "ok": True,
                "live": False,
                "teams": [],
                "last_event": None,
                "event_seq": 0,
                "header": None,
            }
        if state["game"]["status"] != "live":
            return {
                "ok": True,
                "live": False,
                "teams": [
                    {
                        "id": t["id"],
                        "name": t["name"],
                        "color": t["color"],
                        "score": t["score"],
                    }
                    for t in state["teams"]
                ],
                "last_event": state["game"]["last_event"],
                "event_seq": state["game"]["event_seq"],
                "header": state["session"]["header_label"],
                "status": state["game"]["status"],
            }
        return {
            "ok": True,
            "live": True,
            "teams": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "color": t["color"],
                    "score": t["score"],
                }
                for t in state["teams"]
            ],
            "last_event": state["game"]["last_event"],
            "event_seq": state["game"]["event_seq"],
            "header": state["session"]["header_label"],
            "status": "live",
        }

    def session_log_path(self, session_id: int) -> Path:
        """Return the JSONL log path for a session if it exists.

        Args:
            session_id: Sessions primary key.

        Raises:
            KeyError: If the session is unknown.
            FileNotFoundError: If no log has been written yet.
        """
        with self._lock:
            row = self.conn.execute(
                "SELECT log_path FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"session {session_id}")
        fallback = self.logs_dir / f"session-{session_id}.jsonl"
        path = Path(row["log_path"]) if row["log_path"] else fallback
        if not path.is_file():
            raise FileNotFoundError(str(path))
        return path
