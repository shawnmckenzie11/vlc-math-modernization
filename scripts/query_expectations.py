#!/usr/bin/env python3
"""Query the MCF3M curriculum expectations SQLite database.

Supports keyword/topic search, filtering by overall vs specific, and showing
linked sample problems for a given expectation code.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "courses/MCF3M/curriculum/mcf3m.sqlite"


def connect(db_path: Path) -> sqlite3.Connection:
    """Open a read-only-friendly connection to the expectations database.

    Args:
        db_path: Path to mcf3m.sqlite.

    Returns:
        SQLite connection with row factory enabled.
    """
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found: {db_path}. Run scripts/extract_mcf3m_expectations.py first."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def search(
    conn: sqlite3.Connection,
    query: str,
    kind: str = "all",
    limit: int = 50,
) -> list[sqlite3.Row]:
    """Search expectations by keyword in statement or topics.

    Args:
        conn: Open SQLite connection.
        query: Keyword or phrase to match (case-insensitive LIKE).
        kind: One of 'all', 'overall', or 'specific'.
        limit: Maximum rows to return.

    Returns:
        Matching rows with code, kind, statement, topics.
    """
    like = f"%{query}%"
    results: list[sqlite3.Row] = []

    if kind in ("all", "overall"):
        rows = conn.execute(
            """
            SELECT code, 'overall' AS kind, statement, topics, strand_code
            FROM overall_expectations
            WHERE statement LIKE ? OR topics LIKE ? OR code LIKE ?
            ORDER BY code
            LIMIT ?
            """,
            (like, like, like, limit),
        ).fetchall()
        results.extend(rows)

    if kind in ("all", "specific"):
        remaining = max(0, limit - len(results))
        rows = conn.execute(
            """
            SELECT code, 'specific' AS kind, statement, topics, strand_code
            FROM specific_expectations
            WHERE statement LIKE ? OR topics LIKE ? OR code LIKE ?
            ORDER BY code
            LIMIT ?
            """,
            (like, like, like, remaining if kind == "all" else limit),
        ).fetchall()
        results.extend(rows)

    return results


def show(conn: sqlite3.Connection, code: str) -> None:
    """Print one expectation and its linked examples.

    Args:
        conn: Open SQLite connection.
        code: Expectation code such as A2.5 or B3.
    """
    code = code.upper()
    oe = conn.execute(
        "SELECT * FROM overall_expectations WHERE code = ?", (code,)
    ).fetchone()
    if oe:
        print(f"[{oe['code']}] OVERALL ({oe['strand_code']})")
        print(oe["statement"])
        print(f"Topics: {oe['topics']}")
        children = conn.execute(
            "SELECT code, statement FROM specific_expectations WHERE overall_code = ? ORDER BY code",
            (code,),
        ).fetchall()
        if children:
            print("\nSpecific expectations:")
            for c in children:
                print(f"  {c['code']}: {c['statement'][:120]}...")
        examples = conn.execute(
            "SELECT example_text FROM examples WHERE overall_code = ?", (code,)
        ).fetchall()
        if examples:
            print("\nLinked examples:")
            for ex in examples:
                print(f"  - {ex['example_text']}")
        return

    se = conn.execute(
        "SELECT * FROM specific_expectations WHERE code = ?", (code,)
    ).fetchone()
    if not se:
        print(f"No expectation found for code: {code}", file=sys.stderr)
        return
    print(f"[{se['code']}] SPECIFIC → overall {se['overall_code']} ({se['strand_code']})")
    print(se["statement"])
    print(f"Topics: {se['topics']}")
    if se["notes"]:
        print(f"Notes: {se['notes']}")
    examples = conn.execute(
        "SELECT example_text FROM examples WHERE specific_code = ?", (code,)
    ).fetchall()
    if examples:
        print("\nSample problems:")
        for ex in examples:
            print(f"  - {ex['example_text']}")
    else:
        print("\n(No linked sample problems in DB)")


def list_all(conn: sqlite3.Connection, kind: str = "all") -> None:
    """List expectation codes and short statements.

    Args:
        conn: Open SQLite connection.
        kind: 'all', 'overall', or 'specific'.
    """
    if kind in ("all", "overall"):
        print("=== Overall ===")
        for row in conn.execute(
            "SELECT code, statement FROM overall_expectations ORDER BY code"
        ):
            print(f"{row['code']}: {row['statement']}")
    if kind in ("all", "specific"):
        print("=== Specific ===")
        for row in conn.execute(
            "SELECT code, statement FROM specific_expectations ORDER BY code"
        ):
            print(f"{row['code']}: {row['statement'][:100]}...")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for querying MCF3M expectations.

    Args:
        argv: Optional argument list.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Search by keyword/topic")
    p_search.add_argument("query")
    p_search.add_argument(
        "--kind", choices=("all", "overall", "specific"), default="all"
    )
    p_search.add_argument("--limit", type=int, default=50)

    p_show = sub.add_parser("show", help="Show one expectation + examples")
    p_show.add_argument("code")

    p_list = sub.add_parser("list", help="List expectation codes")
    p_list.add_argument(
        "--kind", choices=("all", "overall", "specific"), default="all"
    )

    args = parser.parse_args(argv)
    conn = connect(args.db)

    if args.cmd == "search":
        rows = search(conn, args.query, kind=args.kind, limit=args.limit)
        if not rows:
            print("No matches.")
            return 0
        for row in rows:
            print(f"{row['code']} [{row['kind']}] ({row['strand_code']})")
            print(f"  {row['statement'][:200]}")
            if row["topics"]:
                print(f"  topics: {row['topics']}")
            print()
    elif args.cmd == "show":
        show(conn, args.code)
    elif args.cmd == "list":
        list_all(conn, kind=args.kind)

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
