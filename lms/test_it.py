#!/usr/bin/env python3
"""IT semester activation, MCF3M assignment, and Populate Class gating."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

LMS_DIR = Path(__file__).resolve().parent
REPO_ROOT = LMS_DIR.parent
sys.path.insert(0, str(LMS_DIR))
sys.path.insert(0, str(REPO_ROOT))

os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)
os.environ.setdefault("ALLOW_DEV_VERIFICATION_CODE", "1")

from app import create_app  # noqa: E402


class ItTests(unittest.TestCase):
    """IT dashboard backend: calendar clone and course assignment."""

    def setUp(self) -> None:
        """Isolated sqlite + Flask test client."""
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.app = create_app(
            db_path=root / "lloves.sqlite",
            data_dir=root,
            testing=True,
        )
        self.school = self.app.config["SCHOOL_DB"]
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        """Close db and temp dir."""
        self.school.close()
        self.tmp.cleanup()

    def _login_it(self) -> None:
        """Finish mock Google + 2SV as the bootstrap IT user."""
        self.client.get("/auth/google?portal=it")
        self.client.get(
            "/auth/google/callback?email=solutions@mckenzian.com&name=Shawn"
        )
        user = self.school.get_user_by_email("solutions@mckenzian.com")
        assert user is not None
        self.client.post("/verify-email", data={"code": user["verification_code"]})

    def test_activate_2026_2027_s1_copies_dates(self) -> None:
        """Activating the default semester copies instructional dates from JSON."""
        row = self.school.activate_from_semester_json()
        self.assertEqual(row["label"], "2026-2027 S1")
        self.assertEqual(row["instructional_first"], "2026-09-08")
        self.assertEqual(row["instructional_last"], "2027-01-25")
        self.assertEqual(row["year_display"], "2026/27")
        self.assertEqual(row["term"], "Semester 1")
        self.assertEqual(row["is_active"], 1)
        exam = row["exam_window_json"]
        self.assertIn("2027-01-26", exam)

    def test_assign_mcf3m_attaches_a1_and_a1_3(self) -> None:
        """MCF3M inherits overall A1 and specific A1.3 from the verified seed."""
        self.school.activate_from_semester_json()
        teacher = self.school.register_staff("teacher@gmail.com")
        offering = self.school.assign_course(
            teacher_user_id=int(teacher["id"]), ontario_code="MCF3M"
        )
        self.assertEqual(len(offering["live_access_code"]), 8)
        codes = {row["code"]: row for row in self.school.list_expectations("MCF3M")}
        self.assertIn("A1", codes)
        self.assertEqual(codes["A1"]["kind"], "overall")
        self.assertIn("A1.3", codes)
        self.assertEqual(codes["A1.3"]["kind"], "specific")
        self.assertEqual(codes["A1.3"]["parent_code"], "A1")
        self.assertTrue(codes["A1"]["statement"])

    def test_second_teacher_reuses_live_access_code(self) -> None:
        """One student key per (semester, Ontario course), shared across teachers."""
        self.school.activate_from_semester_json()
        a = self.school.register_staff("a@gmail.com")
        b = self.school.register_staff("b@gmail.com")
        first = self.school.assign_course(
            teacher_user_id=int(a["id"]), ontario_code="MCF3M"
        )
        second = self.school.assign_course(
            teacher_user_id=int(b["id"]), ontario_code="MCF3M"
        )
        self.assertEqual(first["live_access_code"], second["live_access_code"])
        self.assertNotEqual(first["id"], second["id"])

    def test_staff_without_offering_cannot_populate(self) -> None:
        """Populate Class is forbidden until IT assigns a course."""
        self.school.activate_from_semester_json()
        self.school.register_staff("lonely@gmail.com")
        self.client.get("/auth/google?portal=staff")
        self.client.get("/auth/google/callback?email=lonely@gmail.com&name=Lonely")
        user = self.school.get_user_by_email("lonely@gmail.com")
        assert user is not None
        self.client.post("/verify-email", data={"code": user["verification_code"]})
        rv = self.client.post(
            "/api/staff/classes",
            json={
                "offering_id": 0,
                "days": "M/W/F",
                "time": "2:00pm",
                "codenames": ["Maple"],
            },
        )
        self.assertEqual(rv.status_code, 403)

    def test_it_activate_endpoint(self) -> None:
        """IT dashboard POST clones the school calendar."""
        self._login_it()
        rv = self.client.post("/it/semesters/activate", follow_redirects=False)
        self.assertEqual(rv.status_code, 302)
        active = self.school.get_active_semester()
        self.assertIsNotNone(active)
        self.assertEqual(active["label"], "2026-2027 S1")

    def test_syllabus_editor_needs_imscc_gracefully(self) -> None:
        """Editor route does not crash when the teacher has a class."""
        self.school.activate_from_semester_json()
        teacher = self.school.register_staff("teacher@gmail.com")
        offering = self.school.assign_course(
            teacher_user_id=int(teacher["id"]), ontario_code="MCF3M"
        )
        created = self.school.game.create_class(
            year="2026/27",
            semester="Semester 1",
            course_code="MCF3M",
            days_preset="M/W/F",
            time_label="2:00pm",
            codenames=["Maple"],
            offering_id=int(offering["id"]),
            teacher_user_id=int(teacher["id"]),
        )
        self.client.get("/auth/google?portal=staff")
        self.client.get("/auth/google/callback?email=teacher@gmail.com&name=T")
        user = self.school.get_user_by_email("teacher@gmail.com")
        assert user is not None
        self.client.post("/verify-email", data={"code": user["verification_code"]})
        rv = self.client.get(f"/staff/class/{created['id']}/syllabus/editor")
        self.assertIn(rv.status_code, {200, 302})


if __name__ == "__main__":
    unittest.main(verbosity=2)
