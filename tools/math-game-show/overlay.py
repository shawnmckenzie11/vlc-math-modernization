#!/usr/bin/env python3
"""Launch the always-on-top Electron scoreboard overlay.

The Game Show server must already be running. This only starts the floating
strip; it does not replace the Zoom share window.

Usage (from the repo root):
    python3 tools/math-game-show/overlay.py --class 1
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

OVERLAY_DIR = Path(__file__).resolve().parent / "overlay"


def main(argv: list[str] | None = None) -> int:
    """Run Electron against the overlay package.

    Args:
        argv: Optional CLI args (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--class-id", "--class", dest="class_id", type=int, default=1)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)

    npm = shutil.which("npm")
    if npm is None:
        print("npm is required for the overlay (install Node, then npm install in overlay/).")
        return 1
    if not (OVERLAY_DIR / "node_modules" / "electron").exists():
        print("Installing Electron in tools/math-game-show/overlay …")
        install = subprocess.run([npm, "install"], cwd=OVERLAY_DIR, check=False)
        if install.returncode != 0:
            return install.returncode
    cmd = [
        npm,
        "start",
        "--",
        f"--class={args.class_id}",
        f"--host={args.host}",
        f"--port={args.port}",
    ]
    return subprocess.call(cmd, cwd=OVERLAY_DIR)


if __name__ == "__main__":
    raise SystemExit(main())
