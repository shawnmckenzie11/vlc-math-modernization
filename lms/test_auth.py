#!/usr/bin/env python3
"""Auth tests for LLOVES: Google allowlist, portals, 2SV, student code."""

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

os.environ.setdefault("ALLOW_DEV_VERIFICATION_CODE", "1")
os.environ.pop("GOOGLE_CLIENT_ID", None)
os.environ.pop("GOOGLE_CLIENT_SECRET", None)

from app import create_app  # noqa: E402


class AuthTests(unittest.TestCase):
    """Google mock login, portal gating, student-code rate limit."""

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

    def _callback(self, email: str, portal: str = "staff"):
        """Mock Google OAuth: start then callback with an email."""
        self.client.get(f"/auth/google?portal={portal}")
        return self.client.get(
            f"/auth/google/callback?email={email}&name=Test",
            follow_redirects=False,
        )

    def _complete_2sv(self, email: str) -> None:
        """Submit the stored first-login email code."""
        user = self.school.get_user_by_email(email)
        assert user is not None
        code = user["verification_code"]
        self.assertTrue(code)
        rv = self.client.post("/verify-email", data={"code": code}, follow_redirects=False)
        self.assertEqual(rv.status_code, 302)

    def test_landing_has_three_actions(self) -> None:
        """Public landing shows Staff, IT, and Student Code."""
        rv = self.client.get("/")
        self.assertEqual(rv.status_code, 200)
        body = rv.get_data(as_text=True)
        self.assertIn("Staff Login", body)
        self.assertIn("IT Login", body)
        self.assertIn("Student Code", body)
        self.assertIn("Learning Live Online Virtually", body)
        self.assertNotIn(">ELC<", body)

    def test_unknown_google_403(self) -> None:
        """Unknown Google accounts are not auto-created."""
        rv = self._callback("stranger@gmail.com", "staff")
        self.assertEqual(rv.status_code, 403)
        self.assertIn("not registered", rv.get_data(as_text=True))
        self.assertIsNone(self.school.get_user_by_email("stranger@gmail.com"))

    def test_it_email_may_use_staff_portal(self) -> None:
        """Shawn's IT email can complete Staff Login after 2SV."""
        rv = self._callback("solutions@mckenzian.com", "staff")
        self.assertEqual(rv.status_code, 302)
        self.assertIn("/verify-email", rv.headers.get("Location", ""))
        self._complete_2sv("solutions@mckenzian.com")
        home = self.client.get("/staff")
        self.assertEqual(home.status_code, 200)

    def test_staff_cannot_use_it_portal(self) -> None:
        """Registered staff clicking IT get 403."""
        self.school.register_staff("teacher@gmail.com")
        rv = self._callback("teacher@gmail.com", "it")
        self.assertEqual(rv.status_code, 403)
        self.assertIn("Ask IT", rv.get_data(as_text=True))

    def test_first_login_requires_email_code_second_skips(self) -> None:
        """First LLOVES login is 2SV; later Google logins skip the email code."""
        self.school.register_staff("teacher@gmail.com")
        first = self._callback("teacher@gmail.com", "staff")
        self.assertIn("/verify-email", first.headers.get("Location", ""))
        self._complete_2sv("teacher@gmail.com")
        self.client.get("/logout")
        second = self._callback("teacher@gmail.com", "staff")
        self.assertEqual(second.status_code, 302)
        self.assertIn("/staff", second.headers.get("Location", ""))

    def test_wrong_student_code_401(self) -> None:
        """Unknown 8-char keys are rejected."""
        rv = self.client.post("/auth/student-code", data={"code": "ABCD2345"})
        self.assertEqual(rv.status_code, 401)

    def test_student_code_joins_waiting_room(self) -> None:
        """A valid course key with no live game lands in the waiting room."""
        self.school.activate_from_semester_json()
        teacher = self.school.register_staff("teacher@gmail.com")
        offering = self.school.assign_course(
            teacher_user_id=int(teacher["id"]), ontario_code="MCF3M"
        )
        rv = self.client.post(
            "/auth/student-code",
            data={"code": offering["live_access_code"]},
            follow_redirects=False,
        )
        self.assertEqual(rv.status_code, 302)
        self.assertIn("/student/waiting", rv.headers.get("Location", ""))

    def test_student_code_rate_limit(self) -> None:
        """More than 5 attempts per IP in 10 minutes is 429."""
        last = None
        for _ in range(6):
            last = self.client.post("/auth/student-code", data={"code": "ZZZZZZZZ"})
        self.assertEqual(last.status_code, 429)


if __name__ == "__main__":
    unittest.main(verbosity=2)
