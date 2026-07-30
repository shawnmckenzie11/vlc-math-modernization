#!/usr/bin/env python3
"""Inventory SMART Notebook live-lesson files for MCF3M (and future courses).

Walks an extracted live-lessons modules tree, infers module/lesson labels from
folder and file names, and writes JSON + markdown manifests. Does not open or
parse .notebook ZIP contents (phase-2 extraction).
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODULES = ROOT / "courses/MCF3M/live-lessons/modules"
DEFAULT_JSON = ROOT / "courses/MCF3M/live-lessons/inventory.json"
DEFAULT_MD = ROOT / "courses/MCF3M/live-lessons/inventory.md"

# Folder names like "Module 1 - Intro to the Quadratic Function"
MODULE_FOLDER_RE = re.compile(
    r"^Module\s+(\d+)\s*[-–—]\s*(.+)$",
    re.IGNORECASE,
)
# Filenames like "3M M1L2 - Transformations..." or "3M Module 6 Lesson 2 - ..."
LESSON_CODE_RE = re.compile(
    r"(?:M(\d+)L(\d+(?:\.\d+)?)|Module\s+(\d+)\s+Lesson\s+(\d+(?:\.\d+)?))",
    re.IGNORECASE,
)

SPECIAL_FOLDERS = {
    "Exam Outline": {"module_id": "exam", "title": "Exam Outline"},
    "Learning Skills": {"module_id": "learning-skills", "title": "Learning Skills"},
}


def human_size(num_bytes: int) -> str:
    """Return a short human-readable size string for *num_bytes*."""
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def parse_module_folder(folder_name: str) -> dict:
    """Infer module id and title from a top-level folder name.

    Returns a dict with keys ``module_id``, ``module_number`` (int|None),
    and ``title``.
    """
    if folder_name in SPECIAL_FOLDERS:
        info = SPECIAL_FOLDERS[folder_name]
        return {
            "module_id": info["module_id"],
            "module_number": None,
            "title": info["title"],
        }
    match = MODULE_FOLDER_RE.match(folder_name)
    if match:
        number = int(match.group(1))
        title = match.group(2).strip()
        return {
            "module_id": f"module-{number}",
            "module_number": number,
            "title": title,
        }
    return {
        "module_id": folder_name.lower().replace(" ", "-"),
        "module_number": None,
        "title": folder_name,
    }


def parse_lesson_filename(filename: str) -> dict:
    """Extract lesson code, student/teacher variant, and stem from *filename*."""
    stem = Path(filename).stem
    is_student = "(student" in stem.lower()
    match = LESSON_CODE_RE.search(stem)
    lesson_code = None
    if match:
        if match.group(1) is not None:
            lesson_code = f"M{match.group(1)}L{match.group(2)}"
        else:
            lesson_code = f"M{match.group(3)}L{match.group(4)}"
    # Clean display title after the first " - "
    title = stem
    if " - " in stem:
        title = stem.split(" - ", 1)[1]
    title = re.sub(r"\s*\(student(?:\s*\d+)?\)\s*$", "", title, flags=re.IGNORECASE)
    return {
        "lesson_code": lesson_code,
        "variant": "student" if is_student else "teacher",
        "title": title.strip(),
        "stem": stem,
    }


def inventory_tree(modules_dir: Path) -> dict:
    """Build a structured inventory of files under *modules_dir*.

    Skips macOS junk (``.DS_Store``, ``._*``). Groups files by module folder.
    """
    if not modules_dir.is_dir():
        raise FileNotFoundError(f"Modules directory not found: {modules_dir}")

    modules: dict[str, dict] = {}
    type_counts: dict[str, int] = defaultdict(int)
    total_bytes = 0
    file_count = 0

    for folder in sorted(p for p in modules_dir.iterdir() if p.is_dir()):
        meta = parse_module_folder(folder.name)
        entries: list[dict] = []
        folder_bytes = 0
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            name = path.name
            if name == ".DS_Store" or name.startswith("._"):
                continue
            rel = path.relative_to(modules_dir).as_posix()
            size = path.stat().st_size
            suffix = path.suffix.lower().lstrip(".") or "unknown"
            parsed = parse_lesson_filename(name)
            entry = {
                "path": rel,
                "filename": name,
                "extension": suffix,
                "size_bytes": size,
                "size_human": human_size(size),
                "lesson_code": parsed["lesson_code"],
                "variant": parsed["variant"] if suffix == "notebook" else None,
                "title": parsed["title"],
            }
            entries.append(entry)
            folder_bytes += size
            total_bytes += size
            file_count += 1
            type_counts[suffix] += 1

        modules[meta["module_id"]] = {
            "folder": folder.name,
            "module_id": meta["module_id"],
            "module_number": meta["module_number"],
            "title": meta["title"],
            "file_count": len(entries),
            "size_bytes": folder_bytes,
            "size_human": human_size(folder_bytes),
            "files": entries,
        }

    return {
        "course": "MCF3M",
        "medium": "SMART Notebook",
        "generated": date.today().isoformat(),
        "modules_dir": str(modules_dir.relative_to(ROOT)),
        "summary": {
            "module_folders": len(modules),
            "file_count": file_count,
            "total_bytes": total_bytes,
            "total_human": human_size(total_bytes),
            "by_extension": dict(sorted(type_counts.items())),
            "notebook_count": type_counts.get("notebook", 0),
        },
        "modules": modules,
    }


def render_markdown(inventory: dict) -> str:
    """Render a human-readable markdown inventory from *inventory* dict."""
    summary = inventory["summary"]
    lines = [
        "# MCF3M SMART Notebook live-lessons inventory",
        "",
        f"Generated: `{inventory['generated']}`  ",
        f"Tree: `{inventory['modules_dir']}`  ",
        f"Medium: {inventory['medium']}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Module folders | {summary['module_folders']} |",
        f"| Files | {summary['file_count']} |",
        f"| `.notebook` files | {summary['notebook_count']} |",
        f"| Total size | {summary['total_human']} |",
        "",
        "### By extension",
        "",
    ]
    for ext, count in summary["by_extension"].items():
        lines.append(f"- `.{ext}`: {count}")

    lines.extend(["", "## Modules", ""])
    for module in inventory["modules"].values():
        num = module["module_number"]
        heading = (
            f"### Module {num} — {module['title']}"
            if num is not None
            else f"### {module['title']}"
        )
        lines.append(heading)
        lines.append("")
        lines.append(f"Folder: `{module['folder']}` · {module['file_count']} files · {module['size_human']}")
        lines.append("")
        lines.append("| Lesson | Variant | Type | Size | File |")
        lines.append("|--------|---------|------|------|------|")
        for f in module["files"]:
            lesson = f["lesson_code"] or "—"
            variant = f["variant"] or "—"
            lines.append(
                f"| {lesson} | {variant} | .{f['extension']} | {f['size_human']} | `{f['filename']}` |"
            )
        lines.append("")

    lines.extend(
        [
            "## Naming conventions (inferred)",
            "",
            "- Teacher files: `3M M{n}L{k} - Title.notebook` (no `(student)` suffix)",
            "- Student files: same stem with `(student)` or `(student 2)`",
            "- Some modules use `3M Module {n} Lesson {k} - Title.notebook`",
            "- Companion `.pdf` / `.png` assets sit beside notebooks in the same folder",
            "",
            "Typo preserved from source: Module 6 folder is `Sinusodial` (sinusoidal).",
            "",
        ]
    )
    return "\n".join(lines)


def write_inventory(
    modules_dir: Path,
    json_path: Path,
    md_path: Path,
) -> dict:
    """Inventory *modules_dir* and write JSON + markdown manifests.

    Returns the inventory dict that was written.
    """
    inventory = inventory_tree(modules_dir)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(inventory), encoding="utf-8")
    return inventory


def main(argv: list[str] | None = None) -> int:
    """CLI entry: build live-lesson inventory manifests."""
    parser = argparse.ArgumentParser(
        description="Inventory SMART Notebook live-lesson files for MCF3M."
    )
    parser.add_argument(
        "--modules-dir",
        type=Path,
        default=DEFAULT_MODULES,
        help="Extracted modules tree (default: courses/MCF3M/live-lessons/modules)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=DEFAULT_JSON,
        help="Output inventory JSON path",
    )
    parser.add_argument(
        "--md-out",
        type=Path,
        default=DEFAULT_MD,
        help="Output inventory markdown path",
    )
    args = parser.parse_args(argv)

    inventory = write_inventory(args.modules_dir, args.json_out, args.md_out)
    summary = inventory["summary"]
    print(
        f"Wrote {args.json_out.relative_to(ROOT)} and "
        f"{args.md_out.relative_to(ROOT)} — "
        f"{summary['file_count']} files, "
        f"{summary['notebook_count']} notebooks, "
        f"{summary['total_human']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
