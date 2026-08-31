# Math Game Show

Local teacher app: a private class spreadsheet (Canvas CSV in, session columns out) and a public ESPN-style scoreboard window you screen-share on Zoom. Students never get a URL. Binds **127.0.0.1** only.

**Setting this up on another Mac (you or a supply teacher):** see [TEACHER-SETUP.md](TEACHER-SETUP.md).

## Run during Zoom

From the repo root:

```bash
python3 tools/math-game-show/server.py
```

Opens [http://127.0.0.1:8766/](http://127.0.0.1:8766/). Use `--no-browser` if you already have a tab.

1. **Create New Class** (year / semester / course / Canvas CSV / days / time) or **Start Existing Class**.
2. On the class dashboard, **Begin a New Game**: confirm or change the date, then attendance → teams → names. Cancel returns to the class dashboard. A second game on the same slot is labeled `_2`, `_3`, … rather than jumping to the next class day.
3. Keep the **teacher game** window on your machine. Share the **scoreboard** window on Zoom (`/scoreboard`). There is one board: live scores if a game is running, Final Score right after End Game, otherwise waiting.
4. Optional **always-on-top overlay** (stays above Notebook/slides on your Mac; share that window on Zoom if students should see it):
   ```bash
   python3 tools/math-game-show/overlay.py
   ```
   First run installs Electron under `overlay/`. The Game Show server must already be running.
5. **End Game** writes credited individual scores into that date column and attaches a log of immutable events.

Python 3 stdlib only (sqlite3 + `ThreadingHTTPServer`). No pip install. Data lives in `tools/math-game-show/data/` (gitignored): `app.sqlite`, uploaded CSVs, JSONL logs.

Scoring stores **immutable point events** plus separate **individual credited scores** and **team scores**. The class dashboard cell is that student's credited total for the session (individual awards, plus team awards when you choose “each member” or “split”). “Team only” awards raise the ESPN bar without changing individual cells.

The class spreadsheet can add or remove students. Class columns are created by **Begin a New Game**. **Log TOTAL as Subtotal** freezes a named snapshot to the right of the last class column. A live **SUBTOTAL** column (left of **TOTAL SCORE**) then only sums newer class columns; **TOTAL SCORE** still sums every class column since the course started.

A sanitized Canvas-shaped fixture is at `fixtures/sample-canvas-grades.csv`. Do not commit real gradebook exports (IDs + first names).

## Later

- **Teacher game** — students awarding points to one another (scoring is teacher-only for now).
