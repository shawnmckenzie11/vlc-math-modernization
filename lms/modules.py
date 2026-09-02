"""IMSCC unpack, inventory nav, and wiki HTML rewriting for the Modules tab."""

from __future__ import annotations

import html
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from paths import (
    MCF3M_IMSCC,
    MCF3M_INVENTORY,
    MCF3M_UNPACKED,
    REPO_ROOT,
    SCRIPTS_DIR,
)

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

logger = logging.getLogger(__name__)

PLACEHOLDER_TYPES = {
    "Quizzes::Quiz",
    "Assignment",
    "DiscussionTopic",
    "ContextModuleSubHeader",
}

_FILEBASE_RE = re.compile(r"\$IMS-CC-FILEBASE\$", re.I)
_CANVAS_REF_RE = re.compile(r"\$CANVAS_COURSE_REFERENCE\$[^\"'\s]*", re.I)
_WEB_RES_RE = re.compile(
    r"""((?:src|href)\s*=\s*["'])(?:\.\./)*web_resources/""",
    re.I,
)


def imscc_path_for_code(ontario_code: str, offering_imscc: str | None) -> Path | None:
    """Resolve a cartridge path from the offering or the MCF3M default.

    Args:
        ontario_code: Assigned course code.
        offering_imscc: Relative or absolute path stored on the offering.

    Returns:
        Path if the file exists, else None.
    """
    if offering_imscc:
        raw = Path(offering_imscc)
        candidate = raw if raw.is_absolute() else (REPO_ROOT / raw)
        if candidate.is_file():
            return candidate
    if ontario_code.upper() == "MCF3M" and MCF3M_IMSCC.is_file():
        return MCF3M_IMSCC
    return None


def unpacked_dir_for_code(ontario_code: str) -> Path:
    """Working tree for wiki_content / web_resources.

    Args:
        ontario_code: Course code.
    """
    if ontario_code.upper() == "MCF3M":
        return MCF3M_UNPACKED
    return REPO_ROOT / "courses" / ontario_code.upper() / "canvas" / "unpacked"


def inventory_path_for_code(ontario_code: str) -> Path:
    """Committed Canvas inventory JSON, when this repo has one."""
    if ontario_code.upper() == "MCF3M":
        return MCF3M_INVENTORY
    return REPO_ROOT / "courses" / ontario_code.upper() / "canvas" / "inventory.json"


def ensure_unpacked(imscc: Path, out_dir: Path) -> dict[str, Any]:
    """Unpack the cartridge when the working tree is missing.

    Args:
        imscc: ``.imscc`` archive.
        out_dir: Destination (gitignored).

    Returns:
        Status dict: ``ok``, ``unpacked``, ``error``.
    """
    wiki = out_dir / "wiki_content"
    if wiki.is_dir():
        return {"ok": True, "unpacked": False, "error": None}
    if not imscc.is_file():
        return {"ok": False, "unpacked": False, "error": "IMSCC archive is not on this machine."}
    try:
        import canvas_unpack
    except ImportError:
        logger.exception("canvas_unpack import failed")
        return {"ok": False, "unpacked": False, "error": "Unpack tool is missing."}
    try:
        canvas_unpack.unpack_imscc(imscc, out_dir, clean=False)
    except Exception as exc:  # noqa: BLE001 — surface to the Modules empty state
        logger.exception("IMSCC unpack failed")
        return {"ok": False, "unpacked": False, "error": str(exc)}
    return {"ok": True, "unpacked": True, "error": None}


def load_inventory(ontario_code: str) -> dict[str, Any] | None:
    """Load ``inventory.json`` for module navigation.

    Args:
        ontario_code: Course code.
    """
    path = inventory_path_for_code(ontario_code)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def module_nav(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten inventory modules into left-nav entries.

    Args:
        inventory: Parsed ``inventory.json``.
    """
    nav = []
    for module in inventory.get("modules") or []:
        items = []
        for item in module.get("items") or []:
            content_type = str(item.get("content_type") or "")
            href = item.get("href")
            kind = "page"
            if content_type in {"Quizzes::Quiz", "Assignment", "DiscussionTopic"}:
                kind = "placeholder"
            elif content_type == "ContextModuleSubHeader":
                kind = "header"
            elif content_type == "Attachment" or (href and str(href).startswith("web_resources/")):
                kind = "file"
            items.append(
                {
                    "title": item.get("title") or "Untitled",
                    "content_type": content_type,
                    "href": href,
                    "kind": kind,
                    "identifier": item.get("identifier"),
                }
            )
        nav.append(
            {
                "title": module.get("title") or "Module",
                "identifier": module.get("identifier"),
                "items": items,
            }
        )
    return nav


def rewrite_wiki_html(raw: str, ontario_code: str) -> str:
    """Rewrite Canvas IMSCC tokens and relative asset URLs for LLOVES.

    Args:
        raw: Unpacked wiki HTML.
        ontario_code: Course code used in file URLs.
    """
    files_root = f"/lms/modules/{ontario_code}/files/web_resources"
    html_out = _FILEBASE_RE.sub(files_root, raw)
    html_out = _CANVAS_REF_RE.sub("#", html_out)
    html_out = _WEB_RES_RE.sub(rf"\1{files_root}/", html_out)
    return html_out


def wrap_page(title: str, inner_html: str) -> str:
    """Minimal chrome around unpacked wiki HTML (no Canvas RCE).

    Args:
        title: Document title.
        inner_html: Rewritten page HTML (may include its own html/body).
    """
    # Prefer the original body when present so we do not nest documents.
    body_match = re.search(r"<body[^>]*>(.*)</body>", inner_html, re.I | re.S)
    body = body_match.group(1) if body_match else inner_html
    safe_title = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{safe_title}</title>
<style>
  body {{ font-family: "Segoe UI", system-ui, sans-serif; color: #1e293b;
         margin: 0; padding: 1rem 1.25rem 2rem; background: #fff; }}
  img, video {{ max-width: 100%; height: auto; }}
  a {{ color: #0f766e; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def placeholder_html(title: str, kind: str) -> str:
    """Quiz/assignment/discussion stand-in for LLOVES v1.

    Args:
        title: Inventory item title.
        kind: Canvas content type.
    """
    label = {
        "Quizzes::Quiz": "native quiz not in LLOVES v1",
        "Assignment": "native assignment not in LLOVES v1",
        "DiscussionTopic": "native discussion not in LLOVES v1",
    }.get(kind, "not in LLOVES v1")
    return wrap_page(
        title,
        f"<h1>{html.escape(title)}</h1><p>{html.escape(title)} — {html.escape(label)}.</p>",
    )


def safe_unpacked_file(unpacked: Path, rel: str) -> Path | None:
    """Resolve a relative path inside the unpacked tree, or None if unsafe.

    Args:
        unpacked: Unpacked IMSCC root.
        rel: URL path after the files prefix.
    """
    raw = unquote(rel or "").lstrip("/")
    candidate = (unpacked / raw).resolve()
    try:
        candidate.relative_to(unpacked.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None
