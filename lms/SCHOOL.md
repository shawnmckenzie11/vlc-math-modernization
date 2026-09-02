# Learning Live Online Virtually & Explicitly School (LLOVES)

This folder is a **new school product**, not a rename of ELC. ELC identity stays in `frameworks/school.md`.

Shawn is IT at `solutions@mckenzian.com`.

## Run locally

```bash
python3 -m pip install -r lms/requirements.txt
python3 lms/app.py
# http://127.0.0.1:8787
```

Without `GOOGLE_CLIENT_ID`, Staff/IT login uses a mock Google email form (allowlisted accounts only).

## Environment

See `.env.example`. Set Google OAuth redirect URIs to:

- `http://127.0.0.1:8787/auth/google/callback`
- `https://<fly-app>.fly.dev/auth/google/callback`

Consent screen: External, personal Google accounts (no Workspace domain restriction). App-side allowlist: IT registers staff emails first.

## Tests

```bash
python3 -m unittest lms.test_auth lms.test_it lms.test_roster
python3 tools/math-game-show/test_app.py
```
