# Math Game Show

Local teacher app: a private class spreadsheet (Canvas CSV in, session columns out) and a public ESPN-style scoreboard window you screen-share on Zoom. Students never get a URL. Binds **127.0.0.1** only.

## Run during Zoom

From the repo root:

```bash
python3 tools/math-game-show/server.py
```

Opens [http://127.0.0.1:8766/](http://127.0.0.1:8766/). Use `--no-browser` if you already have a tab.

1. **Create New Class** (year / semester / course / Canvas CSV / days / time) or **Start Existing Class**.
2. On the class dashboard, **Begin a New Game**: confirm or change the date, then attendance → teams → names. Cancel returns to the class dashboard. A second game on the same slot is labeled `_2`, `_3`, … rather than jumping to the next class day.
3. Keep the **teacher game** window on your machine. Share the **scoreboard** window on Zoom (`/scoreboard/<class_id>`).
4. **End Game** writes credited individual scores into that date column and attaches a log of immutable events.

Python 3 stdlib only (sqlite3 + `ThreadingHTTPServer`). No pip install. Data lives in `tools/math-game-show/data/` (gitignored): `app.sqlite`, uploaded CSVs, JSONL logs.

Scoring stores **immutable point events** plus separate **individual credited scores** and **team scores**. The class dashboard cell is that student's credited total for the session (individual awards, plus team awards when you choose “each member” or “split”). “Team only” awards raise the ESPN bar without changing individual cells.

A sanitized Canvas-shaped fixture is at `fixtures/sample-canvas-grades.csv`. Do not commit real gradebook exports (IDs + first names).

## Later (out of scope for v1)

These are noted in the UI as well — do not treat them as missing bugs:

1. **Class dashboard** — add or remove students by row; add or delete live-class session columns by hand.
2. **TOTAL SCORE** — freeze TOTAL as a subtotal up to the current point, then start a fresh count.
3. **Teacher game** — students awarding points to one another (scoring is teacher-only for now).
