# Scripts

| Script | Purpose |
|--------|---------|
| `extract_mcf3m_expectations.py` | Build `courses/MCF3M/curriculum/mcf3m.sqlite` + markdown from seed JSON |
| `query_expectations.py` | CLI search/show/list against the SQLite DB |

```bash
source .venv/bin/activate
pip install -r requirements.txt
python scripts/extract_mcf3m_expectations.py
python scripts/query_expectations.py search "annuity"
```
