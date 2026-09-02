#!/usr/bin/env python3
"""Staff Upload Module Pack: IMSCC store, Modules nav, syllabus editor."""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

LMS_DIR = Path(__file__).resolve().parent
REPO_ROOT = LMS_DIR.parent
sys.path.insert(0, str(LMS_DIR))
sys.path.insert(0, str(REPO_ROOT))

os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)
os.environ.setdefault("ALLOW_DEV_VERIFICATION_CODE", "1")

from app import create_app  # noqa: E402


def _minimal_imscc_bytes() -> bytes:
    """Return a tiny Common Cartridge with one module and one wiki page."""
    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest xmlns="http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1" identifier="man1">
  <resources>
    <resource identifier="wiki1" type="webcontent" href="wiki_content/lesson-1.html"/>
  </resources>
</manifest>
"""
    modules = """<?xml version="1.0" encoding="UTF-8"?>
<modules xmlns="http://canvas.instructure.com/xsd/cccv1p0">
  <module identifier="m1">
    <title>Module 1: Start</title>
    <workflow_state>active</workflow_state>
    <position>1</position>
    <items>
      <item identifier="i1">
        <title>Lesson 1</title>
        <content_type>WikiPage</content_type>
        <workflow_state>active</workflow_state>
        <position>1</position>
        <identifierref>wiki1</identifierref>
      </item>
    </items>
  </module>
</modules>
"""
    page = """<!DOCTYPE html>
<html><head><title>Lesson 1</title></head>
<body><h1>Lesson 1</h1><p>Uploaded pack body.</p></body></html>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("imsmanifest.xml", manifest)
        archive.writestr("course_settings/module_meta.xml", modules)
        archive.writestr("wiki_content/lesson-1.html", page)
    return buf.getvalue()


class ModulePackTests(unittest.TestCase):
    """Upload Module Pack vs preloaded MCF3M cartridge."""

    def setUp(self) -> None:
        """Isolated sqlite, one empty-course class, one MCF3M class."""
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.app = create_app(
            db_path=root / "lloves.sqlite",
            data_dir=root,
            testing=True,
        )
        self.school = self.app.config["SCHOOL_DB"]
        self.client = self.app.test_client()
        self.school.activate_from_semester_json()
        if self.school.get_ontario_course("SBI3U") is None:
            self.school.upsert_ontario_course(
                "SBI3U",
                "Biology, Grade 11, University Preparation",
                grade=11,
                pathway="U",
                expectations_status="unverified",
            )
        self.teacher = self.school.register_staff("teacher@gmail.com")
        self.eng_offering = self.school.assign_course(
            teacher_user_id=int(self.teacher["id"]), ontario_code="SBI3U"
        )
        self.mcf_offering = self.school.assign_course(
            teacher_user_id=int(self.teacher["id"]), ontario_code="MCF3M"
        )
        self.eng_class = self.school.game.create_class(
            year="2026/27",
            semester="Semester 1",
            course_code="SBI3U",
            days_preset="M/W/F",
            time_label="2:00pm",
            codenames=["Maple"],
            offering_id=int(self.eng_offering["id"]),
            teacher_user_id=int(self.teacher["id"]),
        )
        self.mcf_class = self.school.game.create_class(
            year="2026/27",
            semester="Semester 1",
            course_code="MCF3M",
            days_preset="T/Th/F",
            time_label="2:00pm",
            codenames=["Aspen"],
            offering_id=int(self.mcf_offering["id"]),
            teacher_user_id=int(self.teacher["id"]),
        )
        self.client.get("/auth/google?portal=staff")
        self.client.get("/auth/google/callback?email=teacher@gmail.com&name=T")
        user = self.school.get_user_by_email("teacher@gmail.com")
        assert user is not None
        self.client.post(
            "/verify-email", data={"code": user["verification_code"]}
        )

    def tearDown(self) -> None:
        """Close db and temp dir."""
        self.school.close()
        self.tmp.cleanup()

    def test_mcf3m_hides_upload_module_pack(self) -> None:
        """Preloaded MCF3M cartridge does not ask staff to upload an IMSCC."""
        from paths import MCF3M_IMSCC

        if not MCF3M_IMSCC.is_file():
            self.skipTest("MCF3M IMSCC is not on this machine")
        rv = self.client.get(f"/staff/class/{self.mcf_class['id']}")
        self.assertEqual(rv.status_code, 200)
        self.assertNotIn("Upload Module Pack", rv.get_data(as_text=True))

    def test_empty_course_shows_upload_and_installs_pack(self) -> None:
        """SBI3U (no preloaded IMSCC) can upload a cartridge for Modules + Syllabus."""
        dash = self.client.get(f"/staff/class/{self.eng_class['id']}")
        self.assertEqual(dash.status_code, 200)
        html = dash.get_data(as_text=True)
        self.assertIn("Upload Module Pack", html)
        self.assertIn("pack-progress", html)
        self.assertIn("/static/module_pack_upload.js", html)
        empty_nav = self.client.get(
            f"/api/staff/class/{self.eng_class['id']}/modules"
        )
        self.assertTrue(empty_nav.get_json().get("empty"))

        payload = _minimal_imscc_bytes()
        rv = self.client.post(
            f"/staff/class/{self.eng_class['id']}/module-pack",
            data={"module_pack": (io.BytesIO(payload), "english.imscc")},
            follow_redirects=False,
        )
        self.assertEqual(rv.status_code, 302)
        offering = self.school.get_offering(int(self.eng_offering["id"]))
        self.assertTrue(offering.get("imscc_path"))
        self.assertTrue(Path(offering["imscc_path"]).is_file())

        after = self.client.get(f"/staff/class/{self.eng_class['id']}")
        self.assertNotIn("Upload Module Pack", after.get_data(as_text=True))

        nav = self.client.get(f"/api/staff/class/{self.eng_class['id']}/modules")
        body = nav.get_json()
        self.assertTrue(body.get("ok"))
        self.assertFalse(body.get("empty"))
        self.assertEqual(body["modules"][0]["title"], "Module 1: Start")

        item = self.client.get(
            f"/staff/class/{self.eng_class['id']}/module-item"
            "?kind=page&title=Lesson%201&href=wiki_content/lesson-1.html"
        )
        self.assertEqual(item.status_code, 200)
        self.assertIn("Uploaded pack body", item.get_data(as_text=True))

        editor = self.client.get(
            f"/staff/class/{self.eng_class['id']}/syllabus/editor"
        )
        self.assertEqual(editor.status_code, 200)
        html_out = editor.get_data(as_text=True)
        self.assertNotIn("No module pack for this course yet", html_out)
        self.assertIn("Lesson 1", html_out)

    def test_rejects_non_imscc_upload(self) -> None:
        """A random text file is not stored as a module pack."""
        rv = self.client.post(
            f"/staff/class/{self.eng_class['id']}/module-pack",
            data={"module_pack": (io.BytesIO(b"not a zip"), "notes.txt")},
            follow_redirects=True,
        )
        self.assertEqual(rv.status_code, 200)
        self.assertIn("Module pack must be a .imscc", rv.get_data(as_text=True))
        offering = self.school.get_offering(int(self.eng_offering["id"]))
        self.assertFalse(offering.get("imscc_path"))

    def test_module_pack_status_idle_then_unpacking(self) -> None:
        """Status starts idle and reflects a written install_status.json."""
        from modules import module_pack_root, read_pack_status, write_pack_status

        rv = self.client.get(
            f"/staff/class/{self.eng_class['id']}/module-pack/status"
        )
        self.assertEqual(rv.status_code, 200)
        idle = rv.get_json()
        self.assertEqual(idle["stage"], "idle")
        self.assertFalse(idle["busy"])

        dest = module_pack_root(
            Path(self.tmp.name), int(self.eng_offering["id"])
        )
        write_pack_status(
            dest,
            stage="unpacking",
            detail="Unpacking Common Cartridge… this can take a few minutes",
        )
        busy = self.client.get(
            f"/staff/class/{self.eng_class['id']}/module-pack/status"
        ).get_json()
        self.assertEqual(busy["stage"], "unpacking")
        self.assertTrue(busy["busy"])
        self.assertIn("Unpacking Common Cartridge", busy["detail"])
        disk = read_pack_status(dest)
        self.assertEqual(disk["stage"], "unpacking")

    def test_json_upload_installs_and_reports_redirect(self) -> None:
        """XHR upload (tests run install synchronously) returns JSON + installed pack."""
        payload = _minimal_imscc_bytes()
        rv = self.client.post(
            f"/staff/class/{self.eng_class['id']}/module-pack",
            data={"module_pack": (io.BytesIO(payload), "english.imscc")},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
            },
        )
        self.assertEqual(rv.status_code, 200)
        body = rv.get_json()
        self.assertTrue(body.get("ok"))
        self.assertFalse(body.get("installing"))
        self.assertIn("pack=ok", body.get("redirect") or "")
        offering = self.school.get_offering(int(self.eng_offering["id"]))
        self.assertTrue(offering.get("imscc_path"))
        status = self.client.get(
            f"/staff/class/{self.eng_class['id']}/module-pack/status"
        ).get_json()
        self.assertEqual(status["stage"], "done")


if __name__ == "__main__":
    unittest.main(verbosity=2)
