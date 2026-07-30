---
name: curriculum-extractor
description: >-
  Extracts and queries Ontario MCF3M curriculum expectations from the local PDF
  into SQLite and markdown. Use when extracting expectations, searching topics,
  linking sample problems, or updating the MCF3M curriculum database.
---

# Curriculum extractor

## Instructions

1. Do not invent expectation codes or wording.
2. Prefer querying the existing DB before re-extracting:
   `python scripts/query_expectations.py search "keyword"`
3. To rebuild from seed + PDF helpers:
   `python scripts/extract_mcf3m_expectations.py`
4. Keep overall and specific expectations in separate tables; store examples with FKs.
5. After changes, regenerate markdown mirrors (the extract script does this).

## Key files

- `agents/curriculum-extractor.md`
- `scripts/extract_mcf3m_expectations.py`
- `scripts/query_expectations.py`
- `courses/MCF3M/curriculum/mcf3m.sqlite`
