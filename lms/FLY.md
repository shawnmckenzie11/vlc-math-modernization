# Fly.io (LLOVES)

Canonical config is the repository-root [`fly.toml`](../fly.toml). Deploy from the repo root so Docker copies `courses/`, `frameworks/`, `tools/`, and `scripts/`.

```bash
cd /path/to/vlc-math-modernization
fly volumes create lloves_data --region yyz --size 3   # once
fly deploy
```

Google Cloud OAuth client:

- Authorized JavaScript origins: `http://127.0.0.1:8787` and `https://<app>.fly.dev`
- Authorized redirect URIs: `http://127.0.0.1:8787/auth/google/callback` and `https://<app>.fly.dev/auth/google/callback`

Volume `/data` is `LLOVES_DB=/data/lloves.sqlite` plus unpacked IMSCC. Do not deploy from `lms/` — the image would miss curriculum PDFs and semester.json.
