# Scoreboard overlay (experiment)

A frameless Electron strip that stays on top of other apps and loads the existing localhost scoreboard (same pulses and Final Score).

This is for **your** screen while you jump between SMART Notebook and slides. Students only see it if you share this window (or the whole desktop) on Zoom.

## Run

1. Start the Game Show server (`python3 tools/math-game-show/server.py`).
2. From the repo root:

```bash
python3 tools/math-game-show/overlay.py
```

The overlay follows the single active game (live scores, or Final Score right after End Game). `--class` is ignored. Drag the bar to move it; resize from the edges. Quit from the Dock or close the window.

Requires Node/npm once. `node_modules` is gitignored.
