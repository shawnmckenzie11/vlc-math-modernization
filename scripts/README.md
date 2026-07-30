# Scripts

| Script | Purpose |
|--------|---------|
| `extract_mcf3m_expectations.py` | Build `courses/MCF3M/curriculum/mcf3m.sqlite` + markdown from seed JSON |
| `query_expectations.py` | CLI search/show/list against the SQLite DB |
| `canvas_unpack.py` | Unpack `courses/MCF3M/sources/mcf3m-canvas-export.imscc` → `canvas/unpacked/` |
| `canvas_inventory.py` | Write `courses/MCF3M/canvas/inventory.json` + `INVENTORY.md` |
| `canvas_add_module.py` | Scaffold a module + wiki pages into the unpacked tree |
| `canvas_pack.py` | Re-pack unpacked tree to a new `.imscc` for Canvas import |

```bash
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/extract_mcf3m_expectations.py
python3 scripts/query_expectations.py search "annuity"

python3 scripts/canvas_unpack.py --clean
python3 scripts/canvas_inventory.py
python3 scripts/canvas_add_module.py --title "Module N: Title" --pages "Learning Goals" "Lesson 1"
python3 scripts/canvas_pack.py
```
