#!/usr/bin/env python3
"""Focused tests for Math Game Show CSV, teams, schedule, and game persist."""

from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

from csv_import import parse_canvas_grades_csv, parse_student_name  # noqa: E402
from schedule import (  # noqa: E402
    format_header_label,
    heuristic_year_semester,
    next_meeting_datetime,
    parse_semester_field,
    picker_year_semester,
    unique_header_label,
    wizard_defaults,
)
from db import GameShowDB, split_amount  # noqa: E402
from teams import assign_balanced, assign_manual  # noqa: E402
import server as game_server  # noqa: E402

REAL_CSV = Path("/Users/shawnscomputer/Downloads/2026-08-31T1109_Grades-MCF3M-SM.csv")
FIXTURE_CSV = APP_DIR / "fixtures" / "sample-canvas-grades.csv"


class NameParseTests(unittest.TestCase):
    """Canvas Student column → last display + first name."""

    def test_comma_name(self) -> None:
        """Last, First splits on the comma."""
        last, first = parse_student_name("Axxx, Mubarik")
        self.assertEqual(last, "Axxx")
        self.assertEqual(first, "Mubarik")

    def test_spaces_around_comma(self) -> None:
        """Trim extra spaces in ``Sxxxxxx , Joy ``."""
        last, first = parse_student_name("Sxxxxxx , Joy ")
        self.assertEqual(last, "Sxxxxxx")
        self.assertEqual(first, "Joy")

    def test_zxx_hafsa_no_comma(self) -> None:
        """No comma: last token after the final space is the first name."""
        last, first = parse_student_name("Zxx Hafsa")
        self.assertEqual(last, "Zxx")
        self.assertEqual(first, "Hafsa")


class CsvImportTests(unittest.TestCase):
    """Canvas gradebook shape: header, posting row, Points Possible, students."""

    def test_fixture_seventeen_and_hafsa(self) -> None:
        """Sanitized fixture has 17 students and parses Zxx Hafsa."""
        roster = parse_canvas_grades_csv(FIXTURE_CSV.read_text(encoding="utf-8"))
        self.assertEqual(len(roster), 17)
        hafsa = next(s for s in roster if s["canvas_id"] == "90017")
        self.assertEqual(hafsa["last_display"], "Zxx")
        self.assertEqual(hafsa["first_name"], "Hafsa")
        joy = next(s for s in roster if s["canvas_id"] == "90012")
        self.assertEqual(joy["last_display"], "Sxxxxxx")
        self.assertEqual(joy["first_name"], "Joy")

    def test_real_export_if_present(self) -> None:
        """Downloads MCF3M export: 17 students, skip meta, parse Zxx Hafsa."""
        if not REAL_CSV.is_file():
            self.skipTest("real Canvas export not on this machine")
        roster = parse_canvas_grades_csv(REAL_CSV.read_text(encoding="utf-8"))
        self.assertEqual(len(roster), 17)
        hafsa = next(s for s in roster if "Hafsa" in s["first_name"] or s["student_raw"].endswith("Hafsa"))
        self.assertEqual(hafsa["last_display"], "Zxx")
        self.assertEqual(hafsa["first_name"], "Hafsa")
        self.assertTrue(all(s["canvas_id"] for s in roster))
        labels = {s["student_raw"].strip().lower() for s in roster}
        self.assertFalse(any("points possible" in x for x in labels))


class ScheduleTests(unittest.TestCase):
    """semester.json defaults and next-meeting labels."""

    def test_semester_json_defaults(self) -> None:
        """Wizard year/semester come from frameworks/semester.json."""
        year, sem = parse_semester_field("2026-2027 S1")
        self.assertEqual(year, "2026/27")
        self.assertEqual(sem, "Semester 1")
        defaults = wizard_defaults(today=date(2026, 8, 31))
        self.assertEqual(defaults["year"], "2026/27")
        self.assertEqual(defaults["semester"], "Semester 1")
        self.assertEqual(defaults["course_code"], "MCF3M")
        self.assertEqual(defaults["picker_year"], "2026/27")
        self.assertEqual(defaults["picker_semester"], "Semester 1")

    def test_heuristic_august_is_upcoming_s1(self) -> None:
        """Jul–Aug counts as upcoming Semester 1 so summer prep matches JSON."""
        self.assertEqual(
            heuristic_year_semester(date(2026, 8, 31)),
            ("2026/27", "Semester 1"),
        )
        self.assertEqual(
            picker_year_semester(date(2026, 8, 31)),
            ("2026/27", "Semester 1"),
        )

    def test_next_meeting_tue_sep_8(self) -> None:
        """T/Th/F @ 2:00pm before school starts → Tue 9/8 2:00pm."""
        when = next_meeting_datetime(
            "Tue/Thu/Fri",
            "2:00pm",
            today=date(2026, 8, 31),
        )
        self.assertEqual(when.date(), date(2026, 9, 8))
        self.assertEqual(format_header_label(when, "2:00pm"), "Tue 9/8 2:00pm")

    def test_unique_header_suffix(self) -> None:
        """Second play of the same slot becomes ``_2``, then ``_3``."""
        base = "Tue 9/8 2:00pm"
        self.assertEqual(unique_header_label(base, set()), base)
        self.assertEqual(unique_header_label(base, {base}), "Tue 9/8 2:00pm_2")
        self.assertEqual(
            unique_header_label(base, {base, "Tue 9/8 2:00pm_2"}),
            "Tue 9/8 2:00pm_3",
        )


class BalancedAssignTests(unittest.TestCase):
    """Snake draft sends high TOTALs to different teams."""

    def test_high_totals_split(self) -> None:
        """Top two career scores are not on the same team of two."""
        ids = [1, 2, 3, 4]
        totals = [100, 90, 10, 5]
        teams = assign_balanced(ids, 2, totals)
        self.assertEqual(len(teams), 2)
        high = {1, 2}
        self.assertNotEqual(high & set(teams[0]), high)
        self.assertTrue(1 in teams[0] or 1 in teams[1])
        self.assertTrue(2 in teams[0] or 2 in teams[1])
        team_of_1 = 0 if 1 in teams[0] else 1
        team_of_2 = 0 if 2 in teams[0] else 1
        self.assertNotEqual(team_of_1, team_of_2)


class ManualAssignTests(unittest.TestCase):
    """Teacher-chosen team slots."""

    def test_places_each_student(self) -> None:
        """Present students land on the requested teams; empty teams are rejected."""
        buckets = assign_manual(
            [10, 20, 30],
            2,
            [
                {"student_id": 10, "team_index": 0},
                {"student_id": 20, "team_index": 1},
                {"student_id": 30, "team_index": 0},
            ],
        )
        self.assertEqual(buckets, [[10, 30], [20]])
        with self.assertRaises(ValueError):
            assign_manual(
                [10, 20],
                2,
                [
                    {"student_id": 10, "team_index": 0},
                    {"student_id": 20, "team_index": 0},
                ],
            )


class GamePersistTests(unittest.TestCase):
    """Create class → dashboard colors/TOTAL → game → End Game log."""

    def setUp(self) -> None:
        """Temp data dir and one imported fixture class."""
        self.tmp = tempfile.TemporaryDirectory()
        data_dir = Path(self.tmp.name)
        self.db = GameShowDB(data_dir / "app.sqlite", data_dir)
        csv_text = FIXTURE_CSV.read_text(encoding="utf-8")
        self.cls = self.db.create_class(
            year="2026/27",
            semester="Semester 1",
            course_code="MCF3M",
            days_preset="T/Th/F",
            time_label="2:00pm",
            csv_text=csv_text,
            today=date(2026, 8, 31),
        )

    def tearDown(self) -> None:
        """Close sqlite and drop the temp dir."""
        self.db.close()
        self.tmp.cleanup()

    def test_dashboard_template_red_zero(self) -> None:
        """New class: one date column, all absent/red, TOTAL 0."""
        dash = self.db.dashboard(self.cls["id"])
        self.assertEqual(len(dash["students"]), 17)
        self.assertEqual(len(dash["sessions"]), 1)
        self.assertEqual(dash["sessions"][0]["header_label"], "Tue 9/8 2:00pm")
        self.assertEqual(dash["sessions"][0]["status"], "template")
        for student in dash["students"]:
            cell = dash["cells"][f"{dash['sessions'][0]['id']}:{student['id']}"]
            self.assertFalse(cell["present"])
            self.assertEqual(cell["points"], 0)
            self.assertEqual(dash["totals"][str(student["id"])], 0)
            self.assertEqual(dash["live_subtotals"][str(student["id"])], 0)
        self.assertEqual(dash["columns"][0]["kind"], "session")
        listed = self.db.list_classes("2026/27", "Semester 1")
        self.assertTrue(any(c["id"] == self.cls["id"] for c in listed))

    def test_add_remove_student_and_column(self) -> None:
        """Teachers can append a roster row and a dated class column."""
        class_id = self.cls["id"]
        dash = self.db.add_student(class_id, "Ada", "Lovelace")
        self.assertEqual(len(dash["students"]), 18)
        ada = next(s for s in dash["students"] if s["first_name"] == "Ada")
        self.assertEqual(ada["last_display"], "Lovelace")
        first_session = dash["sessions"][0]["id"]
        self.assertFalse(dash["cells"][f"{first_session}:{ada['id']}"]["present"])
        dash = self.db.add_session_column(class_id, date(2026, 9, 10), "3:15pm")
        self.assertEqual(len(dash["sessions"]), 2)
        extra = next(s for s in dash["sessions"] if s["id"] != first_session)
        self.assertEqual(extra["header_label"], "Thu 9/10 3:15pm")
        self.assertEqual(extra["source"], "manual")
        dash = self.db.delete_session_column(class_id, extra["id"])
        self.assertEqual(len(dash["sessions"]), 1)
        dash = self.db.delete_student(class_id, ada["id"])
        self.assertEqual(len(dash["students"]), 17)
        with self.assertRaises(ValueError):
            self.db.add_student(class_id, "", "NoFirst")

    def test_freeze_subtotal_then_new_games_split_windows(self) -> None:
        """Frozen column keeps the old total; live SUBTOTAL only counts new games."""
        class_id = self.cls["id"]
        state = self.db.begin_game(class_id, today=date(2026, 8, 31))
        present = [s["id"] for s in state["students"][:4]]
        scorer = present[0]
        self.db.save_attendance(class_id, present)
        self.db.assign_teams(class_id, 2, "random")
        teams = self.db.game_state(class_id)["teams"]
        self.db.rename_teams(class_id, [{"id": t["id"], "name": t["name"]} for t in teams])
        self.db.award_points(class_id, kind="student", target_id=scorer, amount=10)
        self.db.end_game(class_id)
        dash = self.db.freeze_subtotal(class_id, name="Term 1")
        frozen_cols = [c for c in dash["columns"] if c["kind"] == "subtotal"]
        self.assertEqual(len(frozen_cols), 1)
        self.assertEqual(frozen_cols[0]["name"], "Term 1")
        self.assertEqual(dash["totals"][str(scorer)], 10)
        self.assertEqual(dash["live_subtotals"][str(scorer)], 0)
        self.assertEqual(
            dash["cells"][f"sub:{frozen_cols[0]['id']}:{scorer}"]["points"], 10
        )
        dash = self.db.rename_subtotal(class_id, frozen_cols[0]["id"], "Q1 freeze")
        self.assertEqual(
            next(c for c in dash["columns"] if c["kind"] == "subtotal")["name"],
            "Q1 freeze",
        )
        self.db.begin_game(class_id, today=date(2026, 8, 31))
        self.db.save_attendance(class_id, present)
        self.db.assign_teams(class_id, 2, "random")
        teams = self.db.game_state(class_id)["teams"]
        self.db.rename_teams(class_id, [{"id": t["id"], "name": t["name"]} for t in teams])
        self.db.award_points(class_id, kind="student", target_id=scorer, amount=5)
        self.db.end_game(class_id)
        dash = self.db.dashboard(class_id)
        self.assertEqual(dash["totals"][str(scorer)], 15)
        self.assertEqual(dash["live_subtotals"][str(scorer)], 5)
        self.assertEqual(
            dash["cells"][f"sub:{frozen_cols[0]['id']}:{scorer}"]["points"], 10
        )
        kinds = [c["kind"] for c in dash["columns"]]
        self.assertEqual(kinds, ["session", "subtotal", "session"])

    def test_new_game_after_freeze_stays_right_of_subtotal(self) -> None:
        """A new game column sits after a freeze even if its calendar date is earlier."""
        class_id = self.cls["id"]
        state = self.db.begin_game(class_id, today=date(2026, 8, 31))
        present = [s["id"] for s in state["students"][:4]]
        scorer = present[0]
        self.db.save_attendance(class_id, present)
        self.db.assign_teams(class_id, 2, "random")
        teams = self.db.game_state(class_id)["teams"]
        self.db.rename_teams(class_id, [{"id": t["id"], "name": t["name"]} for t in teams])
        self.db.award_points(class_id, kind="student", target_id=scorer, amount=10)
        self.db.end_game(class_id)
        later = self.db.add_session_column(class_id, date(2026, 9, 22), "2:00pm")
        later_id = next(s["id"] for s in later["sessions"] if "9/22" in s["header_label"])
        dash = self.db.freeze_subtotal(class_id, name="Term 1")
        frozen = next(c for c in dash["columns"] if c["kind"] == "subtotal")
        self.db.begin_game(class_id, today=date(2026, 8, 31))
        self.db.save_attendance(class_id, present)
        self.db.assign_teams(class_id, 2, "random")
        teams = self.db.game_state(class_id)["teams"]
        self.db.rename_teams(class_id, [{"id": t["id"], "name": t["name"]} for t in teams])
        self.db.award_points(class_id, kind="student", target_id=scorer, amount=5)
        self.db.end_game(class_id)
        dash = self.db.dashboard(class_id)
        kinds = [c["kind"] for c in dash["columns"]]
        self.assertEqual(kinds[-2:], ["subtotal", "session"])
        self.assertEqual(dash["cells"][f"sub:{frozen['id']}:{scorer}"]["points"], 10)
        self.assertEqual(dash["live_subtotals"][str(scorer)], 5)
        self.assertEqual(dash["totals"][str(scorer)], 15)
        new_session = dash["columns"][-1]
        self.assertEqual(new_session["kind"], "session")
        self.assertNotEqual(new_session["id"], later_id)

    def test_game_scoring_end_log_and_colors(self) -> None:
        """4 present, 2 random teams, individual+team awards, End Game persist."""
        class_id = self.cls["id"]
        state = self.db.begin_game(class_id, today=date(2026, 8, 31))
        self.assertEqual(state["game"]["status"], "attendance")
        present = [s["id"] for s in state["students"][:4]]
        absent_ids = [s["id"] for s in state["students"][4:]]
        state = self.db.save_attendance(class_id, present)
        state = self.db.assign_teams(class_id, 2, "random")
        self.assertEqual(len(state["teams"]), 2)
        names = [{"id": t["id"], "name": t["name"]} for t in state["teams"]]
        state = self.db.rename_teams(class_id, names)
        self.assertEqual(state["game"]["status"], "live")
        member = state["teams"][0]["members"][0]
        team = state["teams"][0]
        state = self.db.award_points(class_id, kind="student", target_id=member["id"], amount=5)
        self.assertTrue(state["game"]["last_event"]["celebrate"])
        state = self.db.award_points(
            class_id,
            kind="team",
            target_id=team["id"],
            amount=10,
            team_rule="team_only",
        )
        board = self.db.scoreboard(class_id)
        self.assertTrue(board["live"])
        scored = next(t for t in board["teams"] if t["id"] == team["id"])
        self.assertEqual(scored["score"], 15)
        self.assertTrue(board["last_event"]["celebrate"])
        ended = self.db.end_game(class_id)
        self.assertTrue(Path(ended["log_path"]).is_file())
        log_lines = Path(ended["log_path"]).read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(log_lines), 2)
        rec = json.loads(log_lines[0])
        self.assertEqual(rec["from"], "teacher")
        self.assertEqual(rec["amount"], 5)
        dash = self.db.dashboard(class_id)
        session = dash["sessions"][0]
        self.assertEqual(session["status"], "ended")
        self.assertTrue(session["log_path"])
        present_cell = dash["cells"][f"{session['id']}:{member['id']}"]
        self.assertTrue(present_cell["present"])
        self.assertEqual(present_cell["points"], 5)
        absent_cell = dash["cells"][f"{session['id']}:{absent_ids[0]}"]
        self.assertFalse(absent_cell["present"])
        self.assertEqual(absent_cell["points"], 0)
        self.assertEqual(dash["totals"][str(member["id"])], 5)

    def test_balanced_uses_career_total(self) -> None:
        """After one ended session, balanced assignment splits high TOTALs."""
        class_id = self.cls["id"]
        state = self.db.begin_game(class_id)
        four = [s["id"] for s in state["students"][:4]]
        self.db.save_attendance(class_id, four)
        self.db.assign_teams(class_id, 2, "random")
        teams = self.db.game_state(class_id)["teams"]
        self.db.rename_teams(class_id, [{"id": t["id"], "name": t["name"]} for t in teams])
        live = self.db.game_state(class_id)
        a = live["teams"][0]["members"][0]["id"]
        b = live["teams"][1]["members"][0]["id"]
        self.db.award_points(class_id, kind="student", target_id=a, amount=50)
        self.db.award_points(class_id, kind="student", target_id=b, amount=40)
        self.db.end_game(class_id)
        # Next meeting column (Thu 9/10) then balanced on the same four.
        state = self.db.begin_game(class_id, today=date(2026, 9, 10))
        self.assertEqual(state["session"]["header_label"], "Thu 9/10 2:00pm")
        self.db.save_attendance(class_id, four)
        state = self.db.assign_teams(class_id, 2, "balanced")
        team_of = {}
        for team in state["teams"]:
            for member in team["members"]:
                team_of[member["id"]] = team["id"]
        self.assertNotEqual(team_of[a], team_of[b])

    def test_same_slot_suffix_not_next_day(self) -> None:
        """A second game on the same calendar slot is ``_2``, not the next day."""
        class_id = self.cls["id"]
        state = self.db.begin_game(class_id, today=date(2026, 8, 31))
        present = [s["id"] for s in state["students"][:4]]
        self.db.save_attendance(class_id, present)
        self.db.assign_teams(class_id, 2, "random")
        teams = self.db.game_state(class_id)["teams"]
        self.db.rename_teams(class_id, [{"id": t["id"], "name": t["name"]} for t in teams])
        self.db.end_game(class_id)
        again = self.db.begin_game(class_id, today=date(2026, 8, 31))
        self.assertEqual(again["session"]["header_label"], "Tue 9/8 2:00pm_2")
        headers = [s["header_label"] for s in self.db.dashboard(class_id)["sessions"]]
        self.assertEqual(headers, ["Tue 9/8 2:00pm", "Tue 9/8 2:00pm_2"])

    def test_cancel_setup_restores_template(self) -> None:
        """Cancel before Create Teams drops the in-progress game."""
        class_id = self.cls["id"]
        self.db.begin_game(class_id, today=date(2026, 8, 31))
        self.db.cancel_setup(class_id)
        dash = self.db.dashboard(class_id)
        self.assertEqual(len(dash["sessions"]), 1)
        self.assertEqual(dash["sessions"][0]["status"], "template")
        self.assertEqual(dash["sessions"][0]["header_label"], "Tue 9/8 2:00pm")
        self.assertIsNone(dash["open_game"])

    def test_manual_date_override(self) -> None:
        """Teacher can point the setup session at another calendar day."""
        class_id = self.cls["id"]
        self.db.begin_game(class_id, today=date(2026, 8, 31))
        state = self.db.set_meeting_date(
            class_id, date(2026, 9, 10), today=date(2026, 8, 31)
        )
        self.assertEqual(state["session"]["header_label"], "Thu 9/10 2:00pm")
        self.assertEqual(state["session"]["meeting_date"], "2026-09-10")
        state = self.db.set_meeting_date(
            class_id, date(2026, 9, 10), time_label="3:15pm", today=date(2026, 8, 31)
        )
        self.assertEqual(state["session"]["header_label"], "Thu 9/10 3:15pm")
        self.assertEqual(state["session"]["time"], "3:15pm")
        with self.assertRaises(ValueError):
            self.db.set_meeting_date(
                class_id, date(2026, 8, 1), today=date(2026, 8, 31)
            )

    def test_team_credit_rules(self) -> None:
        """each_member, split_members, and team_only credit individuals differently."""
        self.assertEqual(split_amount(10, 3), [3.3, 3.3, 3.3])
        class_id = self.cls["id"]
        state = self.db.begin_game(class_id, today=date(2026, 8, 31))
        present = [s["id"] for s in state["students"][:4]]
        self.db.save_attendance(class_id, present)
        self.db.assign_teams(class_id, 2, "random")
        teams = self.db.game_state(class_id)["teams"]
        self.db.rename_teams(class_id, [{"id": t["id"], "name": t["name"]} for t in teams])
        live = self.db.game_state(class_id)
        team = next(t for t in live["teams"] if len(t["members"]) >= 2)
        n = len(team["members"])
        before = {m["id"]: m["session_points"] for m in team["members"]}
        state = self.db.award_points(
            class_id, kind="team", target_id=team["id"], amount=10, team_rule="each_member"
        )
        scored = next(t for t in state["teams"] if t["id"] == team["id"])
        for member in scored["members"]:
            self.assertEqual(member["session_points"], before[member["id"]] + 10)
        self.assertEqual(scored["bucket"], 0)
        self.assertEqual(scored["score"], scored["individual_sum"])
        self.assertEqual(scored["individual_sum"], 10 * n)

        self.db.end_game(class_id)
        state = self.db.begin_game(class_id, today=date(2026, 8, 31))
        self.db.save_attendance(class_id, present)
        self.db.assign_teams(class_id, 2, "random")
        teams = self.db.game_state(class_id)["teams"]
        self.db.rename_teams(class_id, [{"id": t["id"], "name": t["name"]} for t in teams])
        live = self.db.game_state(class_id)
        team = next(t for t in live["teams"] if len(t["members"]) >= 2)
        n = len(team["members"])
        state = self.db.award_points(
            class_id, kind="team", target_id=team["id"], amount=10, team_rule="split_members"
        )
        scored = next(t for t in state["teams"] if t["id"] == team["id"])
        credits = [m["session_points"] for m in scored["members"]]
        share = round(10 / n, 1)
        self.assertTrue(all(c == share for c in credits))
        leftover = round(10 - share * n, 1)
        self.assertEqual(scored["bucket"], leftover)
        self.assertEqual(scored["individual_sum"], round(share * n, 1))
        self.assertEqual(scored["score"], 10)

        state = self.db.award_points(
            class_id, kind="team", target_id=team["id"], amount=7, team_rule="team_only"
        )
        scored = next(t for t in state["teams"] if t["id"] == team["id"])
        self.assertEqual(scored["bucket"], leftover + 7)
        self.assertEqual(
            sum(m["session_points"] for m in scored["members"]),
            round(share * n, 1),
        )
        self.assertEqual(scored["score"], 17)
        dash = self.db.dashboard(class_id)
        # Still live; credited cells already show split points, not the team-only 7.
        session_id = state["session"]["id"]
        member_id = scored["members"][0]["id"]
        self.assertEqual(
            dash["cells"][f"{session_id}:{member_id}"]["points"],
            scored["members"][0]["session_points"],
        )
        with self.assertRaises(ValueError):
            self.db.award_points(
                class_id, kind="team", target_id=team["id"], amount=-5, team_rule="team_only"
            )


    def test_split_three_keeps_board_score(self) -> None:
        """10 split three ways is 3.3 each; ESPN team total stays 10."""
        class_id = self.cls["id"]
        state = self.db.begin_game(class_id, today=date(2026, 8, 31))
        present = [s["id"] for s in state["students"][:4]]
        self.db.save_attendance(class_id, present)
        self.db.assign_teams(
            class_id,
            2,
            "manual",
            assignments=[
                {"student_id": present[0], "team_index": 0},
                {"student_id": present[1], "team_index": 0},
                {"student_id": present[2], "team_index": 0},
                {"student_id": present[3], "team_index": 1},
            ],
        )
        teams = self.db.game_state(class_id)["teams"]
        self.db.rename_teams(class_id, [{"id": t["id"], "name": t["name"]} for t in teams])
        live = self.db.game_state(class_id)
        trio = next(t for t in live["teams"] if len(t["members"]) == 3)
        state = self.db.award_points(
            class_id, kind="team", target_id=trio["id"], amount=10, team_rule="split_members"
        )
        scored = next(t for t in state["teams"] if t["id"] == trio["id"])
        self.assertEqual([m["session_points"] for m in scored["members"]], [3.3, 3.3, 3.3])
        self.assertEqual(scored["individual_sum"], 9.9)
        self.assertEqual(scored["bucket"], 0.1)
        self.assertEqual(scored["score"], 10)
        board = self.db.scoreboard(class_id)
        shown = next(t for t in board["teams"] if t["id"] == trio["id"])
        self.assertEqual(shown["score"], 10)


def _http_json(base: str, path: str, payload: dict | None = None) -> dict:
    """GET or POST JSON against the test server.

    Args:
        base: Origin such as ``http://127.0.0.1:9xxx``.
        path: URL path.
        payload: If set, POST this object; otherwise GET.

    Returns:
        Parsed JSON body.
    """
    data = None
    headers = {}
    method = "GET"
    if payload is not None:
        method = "POST"
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(base + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise AssertionError(f"{exc.code} {path}: {body}") from exc


class HttpApiTests(unittest.TestCase):
    """Smoke the stdlib server the same way the teacher UI will."""

    @classmethod
    def setUpClass(cls) -> None:
        """Bind an ephemeral localhost port with a temp database."""
        cls.tmp = tempfile.TemporaryDirectory()
        data_dir = Path(cls.tmp.name)
        game_server.DB = GameShowDB(data_dir / "app.sqlite", data_dir)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), game_server.GameShowHandler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        """Stop the test server."""
        cls.httpd.shutdown()
        cls.httpd.server_close()
        if game_server.DB is not None:
            game_server.DB.close()
        cls.tmp.cleanup()

    def test_pages_and_full_flow(self) -> None:
        """Home HTML, defaults, create, dashboard, game, scoreboard, End Game."""
        with urlopen(self.base + "/", timeout=5) as resp:
            home = resp.read().decode("utf-8")
        self.assertIn("Create New Class", home)
        defaults = _http_json(self.base, "/api/defaults")
        self.assertEqual(defaults["course_code"], "MCF3M")
        created = _http_json(
            self.base,
            "/api/classes",
            {
                "year": "2026/27",
                "semester": "Semester 1",
                "course_code": "MCF3M",
                "days": "T/Th/F",
                "time": "2:00pm",
                "csv_text": FIXTURE_CSV.read_text(encoding="utf-8"),
            },
        )
        class_id = created["class"]["id"]
        listed = _http_json(self.base, "/api/classes")
        self.assertTrue(any(c["id"] == class_id for c in listed["classes"]))
        dash = _http_json(self.base, f"/api/classes/{class_id}/dashboard")
        self.assertEqual(len(dash["students"]), 17)
        self.assertEqual(dash["sessions"][0]["header_label"], "Tue 9/8 2:00pm")
        begin = _http_json(self.base, f"/api/classes/{class_id}/begin", {})
        present = [s["id"] for s in begin["students"][:4]]
        moved = _http_json(
            self.base,
            f"/api/classes/{class_id}/game/meeting",
            {"meeting_date": "2026-09-18", "time": "2:00pm"},
        )
        self.assertIn("Fri 9/18 2:00pm", moved["session"]["header_label"])
        _http_json(self.base, f"/api/classes/{class_id}/game/cancel", {})
        begin = _http_json(self.base, f"/api/classes/{class_id}/begin", {})
        _http_json(
            self.base,
            f"/api/classes/{class_id}/game/attendance",
            {"present_ids": present},
        )
        assigned = _http_json(
            self.base,
            f"/api/classes/{class_id}/game/assign",
            {"n_teams": 2, "mode": "random"},
        )
        _http_json(
            self.base,
            f"/api/classes/{class_id}/game/rename",
            {"teams": [{"id": t["id"], "name": t["name"]} for t in assigned["teams"]]},
        )
        member = assigned["teams"][0]["members"][0]
        _http_json(
            self.base,
            f"/api/classes/{class_id}/game/score",
            {"kind": "student", "id": member["id"], "amount": 5},
        )
        _http_json(
            self.base,
            f"/api/classes/{class_id}/game/score",
            {
                "kind": "team",
                "id": assigned["teams"][0]["id"],
                "amount": 10,
                "team_rule": "team_only",
            },
        )
        board = _http_json(self.base, f"/api/classes/{class_id}/scoreboard")
        self.assertTrue(board["live"])
        self.assertEqual(len(board["teams"]), 2)
        ended = _http_json(self.base, f"/api/classes/{class_id}/game/end", {})
        self.assertTrue(ended["ok"])
        dash2 = _http_json(self.base, f"/api/classes/{class_id}/dashboard")
        self.assertEqual(dash2["sessions"][0]["status"], "ended")
        with urlopen(self.base + f"/api/sessions/{dash2['sessions'][0]['id']}/log", timeout=5) as resp:
            log_body = resp.read().decode("utf-8")
        self.assertIn('"from": "teacher"', log_body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
