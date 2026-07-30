# MCF3M Canvas working tree

## Convention

| Path | Tracked? | Purpose |
|------|----------|---------|
| `courses/MCF3M/sources/mcf3m-canvas-export.imscc` | yes (binary archive) | Immutable-ish source export |
| `courses/MCF3M/canvas/unpacked/` | **no** (gitignored) | Editable Common Cartridge working copy |
| `courses/MCF3M/canvas/INVENTORY.md` | yes | Human-readable module/page map |
| `courses/MCF3M/canvas/inventory.json` | yes | Machine-readable inventory for agents |
| `courses/MCF3M/sources/mcf3m-canvas-edited.imscc` | optional / local | Re-pack output for Canvas re-import |

Agents should read the inventory even when the unpack is absent. Unpack only when making edits.

## Workflow

```bash
python3 scripts/canvas_unpack.py --clean
# edit courses/MCF3M/canvas/unpacked/ …
python3 scripts/canvas_inventory.py
python3 scripts/canvas_pack.py   # optional re-import archive
```

Full agent brief: [`agents/canvas-course-updater.md`](../../../agents/canvas-course-updater.md).
