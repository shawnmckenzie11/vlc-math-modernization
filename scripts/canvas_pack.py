#!/usr/bin/env python3
"""Re-pack an unpacked Canvas IMSCC working tree into a ``.imscc`` ZIP.

Use after editing ``courses/<CODE>/canvas/unpacked/``. Re-import the resulting
archive into Canvas via Settings → Import Course Content → Common Cartridge.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNPACKED = ROOT / "courses/MCF3M/canvas/unpacked"
DEFAULT_OUT = ROOT / "courses/MCF3M/sources/mcf3m-canvas-edited.imscc"


def pack_imscc(unpacked: Path, out_path: Path) -> int:
    """Zip an unpacked cartridge tree into ``out_path``.

    Args:
        unpacked: Directory containing ``imsmanifest.xml`` at its root.
        out_path: Destination ``.imscc`` path (parent dirs created as needed).

    Returns:
        Number of files written into the archive.

    Raises:
        FileNotFoundError: If the unpacked tree is missing ``imsmanifest.xml``.
    """
    manifest = unpacked / "imsmanifest.xml"
    if not manifest.is_file():
        raise FileNotFoundError(f"Missing imsmanifest.xml in {unpacked}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(unpacked.rglob("*")):
            if not path.is_file():
                continue
            # Skip junk
            if path.name == ".DS_Store":
                continue
            arcname = str(path.relative_to(unpacked)).replace("\\", "/")
            zf.write(path, arcname)
            count += 1
    return count


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for packing an unpacked IMSCC tree."""
    parser = argparse.ArgumentParser(
        description="Pack an unpacked Canvas course tree into a .imscc archive."
    )
    parser.add_argument(
        "--unpacked",
        type=Path,
        default=DEFAULT_UNPACKED,
        help=f"Unpacked working tree (default: {DEFAULT_UNPACKED})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output .imscc path (default: {DEFAULT_OUT})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: pack unpacked tree and print archive path."""
    args = parse_args(argv)
    try:
        count = pack_imscc(args.unpacked, args.out)
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Packed {count} files -> {args.out}")
    print("Import in Canvas: Settings → Import Course Content → Common Cartridge 1.x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
