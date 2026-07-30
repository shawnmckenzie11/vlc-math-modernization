#!/usr/bin/env python3
"""Extract MCF3M curriculum expectations into SQLite and markdown mirrors.

Loads verified seed data from expectations_seed.json (transcribed from the
Ontario curriculum PDF). Optionally cross-checks that the PDF still contains
MCF3M markers. Does not invent expectation text.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "courses/MCF3M/curriculum/expectations_seed.json"
DEFAULT_DB = ROOT / "courses/MCF3M/curriculum/mcf3m.sqlite"
DEFAULT_MD_DIR = ROOT / "courses/MCF3M/curriculum"
DEFAULT_PDF = ROOT / "courses/MCF3M/sources/ontario-math-curriculum-gr-11-12.pdf"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strands (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS overall_expectations (
    code TEXT PRIMARY KEY,
    strand_code TEXT NOT NULL REFERENCES strands(code),
    number INTEGER NOT NULL,
    statement TEXT NOT NULL,
    section_title TEXT,
    topics TEXT,
    verification_status TEXT
);

CREATE TABLE IF NOT EXISTS specific_expectations (
    code TEXT PRIMARY KEY,
    overall_code TEXT NOT NULL REFERENCES overall_expectations(code),
    strand_code TEXT NOT NULL REFERENCES strands(code),
    statement TEXT NOT NULL,
    topics TEXT,
    notes TEXT,
    verification_status TEXT
);

CREATE TABLE IF NOT EXISTS examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    specific_code TEXT REFERENCES specific_expectations(code),
    overall_code TEXT REFERENCES overall_expectations(code),
    example_text TEXT NOT NULL,
    source TEXT
);

CREATE TABLE IF NOT EXISTS mathematical_processes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    statement TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS expectations_fts USING fts5(
    code,
    kind,
    statement,
    topics,
    content=''
);
"""


def load_seed(path: Path) -> dict:
    """Load and return the expectations seed JSON document.

    Args:
        path: Path to expectations_seed.json.

    Returns:
        Parsed seed dictionary.
    """
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def crosscheck_pdf(pdf_path: Path) -> str:
    """Return a short status string after checking the curriculum PDF for MCF3M.

    Args:
        pdf_path: Path to the Ontario curriculum PDF.

    Returns:
        Status message (ok / missing / skip).
    """
    if not pdf_path.exists():
        return f"PDF missing at {pdf_path}"
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "PyMuPDF not installed; skipped PDF cross-check"
    doc = fitz.open(pdf_path)
    found = False
    for i in range(min(len(doc), 80)):
        text = doc[i].get_text()
        if "MCF3M" in text and "Functions and Applications" in text:
            found = True
            break
    doc.close()
    return "MCF3M section found in PDF" if found else "WARNING: MCF3M markers not found in PDF"


def rebuild_db(seed: dict, db_path: Path) -> None:
    """Create/replace the SQLite database from seed data.

    Args:
        seed: Expectations seed dictionary.
        db_path: Destination SQLite path.
    """
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    status = seed.get("verification_status", "unverified")

    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        ("course_code", seed["course_code"]),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        ("course_title", seed["course_title"]),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        ("source_pdf", seed.get("source_pdf", "")),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        ("verification_status", status),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        ("notes", seed.get("notes", "")),
    )

    for strand in seed["strands"]:
        conn.execute(
            "INSERT INTO strands(code, name) VALUES (?, ?)",
            (strand["code"], strand["name"]),
        )
        for oe in strand["overall"]:
            topics = ", ".join(oe.get("topics") or [])
            conn.execute(
                """INSERT INTO overall_expectations
                   (code, strand_code, number, statement, section_title, topics, verification_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    oe["code"],
                    strand["code"],
                    oe["number"],
                    oe["statement"],
                    oe.get("section_title"),
                    topics,
                    status,
                ),
            )
            conn.execute(
                "INSERT INTO expectations_fts(code, kind, statement, topics) VALUES (?, ?, ?, ?)",
                (oe["code"], "overall", oe["statement"], topics),
            )
        for se in strand["specific"]:
            topics = ", ".join(se.get("topics") or [])
            conn.execute(
                """INSERT INTO specific_expectations
                   (code, overall_code, strand_code, statement, topics, notes, verification_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    se["code"],
                    se["overall"],
                    strand["code"],
                    se["statement"],
                    topics,
                    se.get("notes"),
                    status,
                ),
            )
            conn.execute(
                "INSERT INTO expectations_fts(code, kind, statement, topics) VALUES (?, ?, ?, ?)",
                (se["code"], "specific", se["statement"], topics),
            )
            for ex in se.get("examples") or []:
                conn.execute(
                    """INSERT INTO examples(specific_code, overall_code, example_text, source)
                       VALUES (?, ?, ?, ?)""",
                    (se["code"], se["overall"], ex, "curriculum sample problem"),
                )

    for proc in seed.get("mathematical_processes", {}).get("processes", []):
        conn.execute(
            "INSERT INTO mathematical_processes(name, statement) VALUES (?, ?)",
            (proc["name"], proc["statement"]),
        )

    conn.commit()
    conn.close()


def write_markdown(seed: dict, md_dir: Path) -> None:
    """Write human-readable markdown mirrors of the expectations.

    Args:
        seed: Expectations seed dictionary.
        md_dir: Output directory for markdown files.
    """
    md_dir.mkdir(parents=True, exist_ok=True)
    index_lines = [
        "# MCF3M curriculum expectations",
        "",
        f"**Course:** {seed['course_title']} (`{seed['course_code']}`)",
        f"**Source:** `{seed.get('source_pdf', '')}` (PDF pages {seed.get('source_pages_pdf', '?')})",
        f"**Verification:** {seed.get('verification_status', 'unknown')}",
        "",
        "## Strands",
        "",
    ]

    for strand in seed["strands"]:
        path = md_dir / f"strand-{strand['code']}-{_slug(strand['name'])}.md"
        index_lines.append(f"- [{strand['code']} — {strand['name']}]({path.name})")
        lines = [
            f"# {strand['code']}. {strand['name']}",
            "",
            "## Overall expectations",
            "",
        ]
        for oe in strand["overall"]:
            lines.append(f"### {oe['code']}")
            if oe.get("section_title"):
                lines.append(f"*{oe['section_title']}*")
                lines.append("")
            lines.append(oe["statement"])
            lines.append("")
            if oe.get("topics"):
                lines.append("Topics: " + ", ".join(oe["topics"]))
                lines.append("")
        lines.append("## Specific expectations")
        lines.append("")
        for se in strand["specific"]:
            lines.append(f"### {se['code']} (overall {se['overall']})")
            lines.append("")
            lines.append(se["statement"])
            lines.append("")
            if se.get("topics"):
                lines.append("Topics: " + ", ".join(se["topics"]))
                lines.append("")
            for ex in se.get("examples") or []:
                lines.append(f"- **Sample problem:** {ex}")
            if se.get("examples"):
                lines.append("")
            if se.get("notes"):
                lines.append(f"*Note:* {se['notes']}")
                lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")

    # Processes
    proc_path = md_dir / "mathematical-processes.md"
    procs = seed.get("mathematical_processes", {})
    plines = [
        "# Mathematical process expectations (MCF3M)",
        "",
        procs.get("note", ""),
        "",
    ]
    for p in procs.get("processes", []):
        plines.append(f"## {p['name']}")
        plines.append("")
        plines.append(p["statement"])
        plines.append("")
    proc_path.write_text("\n".join(plines), encoding="utf-8")
    index_lines.extend(["", f"- [Mathematical processes]({proc_path.name})", ""])
    (md_dir / "README.md").write_text("\n".join(index_lines), encoding="utf-8")


def _slug(name: str) -> str:
    """Convert a strand name to a filesystem-friendly slug.

    Args:
        name: Human-readable strand name.

    Returns:
        Lowercase hyphenated slug.
    """
    return name.lower().replace(" ", "-")


def print_counts(db_path: Path) -> None:
    """Print row counts for expectations and examples.

    Args:
        db_path: SQLite database path.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for table in (
        "overall_expectations",
        "specific_expectations",
        "examples",
        "mathematical_processes",
    ):
        n = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n}")
    conn.close()


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for MCF3M expectation extraction.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:]).

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--md-dir", type=Path, default=DEFAULT_MD_DIR)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--skip-pdf-check", action="store_true")
    args = parser.parse_args(argv)

    if not args.seed.exists():
        print(f"Seed not found: {args.seed}", file=sys.stderr)
        return 1

    seed = load_seed(args.seed)
    if not args.skip_pdf_check:
        print(crosscheck_pdf(args.pdf))

    rebuild_db(seed, args.db)
    write_markdown(seed, args.md_dir)
    print(f"Wrote DB: {args.db}")
    print(f"Wrote markdown under: {args.md_dir}")
    print_counts(args.db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
