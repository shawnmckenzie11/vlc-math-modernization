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

    def test_extract_open_and_university_codes_from_text(self) -> None:
        """TOC parser keeps Open courses (no 'Preparation') and university codes."""
        from curriculum import extract_courses_from_pdf_text

        text = (
            "Grade 11\n"
            "English, Grade 11, University Preparation (ENG3U)\n"
            "Media Studies, Grade 11, Open (EMS3O)\n"
            "Functions, University Preparation (MCR3U)\n"
        )
        courses = {row["code"]: row for row in extract_courses_from_pdf_text(text)}
        self.assertIn("ENG3U", courses)
        self.assertIn("EMS3O", courses)
        self.assertIn("MCR3U", courses)
        self.assertIn("Open", courses["EMS3O"]["title"])
        self.assertNotIn("Open Preparation", courses["EMS3O"]["title"])
        hale = extract_courses_from_pdf_text(
            "Grade 9\nHealthy Active Living Education, Grade 9, Open (PPL1O)\n",
            grade_digits="1234",
        )
        self.assertEqual(hale[0]["code"], "PPL1O")
        self.assertEqual(hale[0]["grade"], 9)
        spaced = extract_courses_from_pdf_text(
            "Biology, Grade 11, College Preparation (SBI3C )\n"
        )
        self.assertEqual(spaced[0]["code"], "SBI3C")

    def test_catalog_is_math_science_hpe_only(self) -> None:
        """IT documents this round are Mathematics, Science, and HPE — not English/etc."""
        from curriculum import ONTARIO_DOCUMENTS

        subjects = {spec["subject"] for spec in ONTARIO_DOCUMENTS}
        self.assertIn("Mathematics", subjects)
        self.assertIn("Science", subjects)
        self.assertTrue(any("Health and Physical Education" in s for s in subjects))
        self.assertNotIn("English", subjects)
        self.assertNotIn("The Arts", subjects)
        self.assertNotIn("Business Studies", subjects)

    def test_it_search_and_assign_non_math_when_extracted(self) -> None:
        """IT autocomplete can assign a science or HPE code extracted from a local PDF."""
        from curriculum import ONTARIO_DOCUMENTS, extract_courses_from_pdf
        from paths import REPO_ROOT

        catalog = {
            row["code"]: row
            for row in self.school.search_ontario_courses("", limit=300)
        }
        self.assertIn("MCF3M", catalog)
        extracted = []
        for spec in ONTARIO_DOCUMENTS:
            if spec.get("subject") == "Mathematics":
                continue
            rel = spec.get("local_path") or ""
            if not rel:
                continue
            extracted.extend(
                extract_courses_from_pdf(
                    REPO_ROOT / rel,
                    grade_digits=spec.get("code_grade_digits") or "34",
                )
            )
        if not extracted:
            self.skipTest("No science/HPE Ontario PDF extract in this environment")
        found = [row for row in extracted if row["code"] in catalog]
        self.assertTrue(
            found,
            "seed_curriculum did not store extracted science/HPE codes",
        )
        picked = next(
            (row for row in found if row["code"] in {"SBI3U", "PPL3O", "SNC3M"}),
            found[0],
        )
        self.school.activate_from_semester_json()
        teacher = self.school.register_staff("engteacher@gmail.com")
        offering = self.school.assign_course(
            teacher_user_id=int(teacher["id"]), ontario_code=picked["code"]
        )
        self.assertEqual(offering["ontario_code"], picked["code"])
        self.assertEqual(offering["expectations_status"], "unverified")
        self._login_it()
        search = self.client.get(f"/it/courses?q={picked['code']}")
        self.assertEqual(search.status_code, 200)
        codes = {row["code"] for row in search.get_json()["courses"]}
        self.assertIn(picked["code"], codes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
