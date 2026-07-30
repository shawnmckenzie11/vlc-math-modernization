#!/usr/bin/env python3
"""Scaffold a new Canvas module with wiki pages into an unpacked IMSCC tree.

Updates ``course_settings/module_meta.xml``, ``imsmanifest.xml``, and creates
``wiki_content/*.html`` stubs. Regenerating inventory afterward is recommended.
"""

from __future__ import annotations

import argparse
import re
import secrets
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNPACKED = ROOT / "courses/MCF3M/canvas/unpacked"

CC_NS = "http://www.imsglobal.org/xsd/imsccv1p1/imscp_v1p1"
CANVAS_NS = "http://canvas.instructure.com/xsd/cccv1p0"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"


def canvas_identifier() -> str:
    """Generate a Canvas-style identifier (``g`` + 32 hex chars)."""
    return "g" + secrets.token_hex(16)


def slugify(title: str) -> str:
    """Convert a title into a wiki filename stem."""
    parts: list[str] = []
    for ch in title.lower():
        if ch.isalnum():
            parts.append(ch)
        elif ch in " /-_.:":
            parts.append("-")
    slug = "".join(parts)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "untitled"


def wiki_html(title: str, identifier: str, body_html: str | None = None) -> str:
    """Build a minimal Canvas wiki page HTML document.

    Args:
        title: Page title shown to students.
        identifier: Resource identifier embedded in meta tags.
        body_html: Optional inner HTML; a placeholder is used when omitted.
    """
    body = body_html or (
        f"<h2>{_escape(title)}</h2>\n"
        "<p><!-- Draft page created by scripts/canvas_add_module.py -->"
        "</p>\n"
        "<p>Replace this stub with lesson content. Tag teacher notes with "
        "Ontario expectation codes (e.g. A1.3) after querying "
        "<code>courses/MCF3M/curriculum/mcf3m.sqlite</code>.</p>\n"
    )
    return (
        "<html>\n"
        "<head>\n"
        '<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>\n'
        f"<title>{_escape(title)}</title>\n"
        f'<meta name="identifier" content="{identifier}"/>\n'
        '<meta name="editing_roles" content="teachers"/>\n'
        '<meta name="workflow_state" content="unpublished"/>\n'
        "</head>\n"
        f"<body>\n{body}</body>\n"
        "</html>\n"
    )


def _escape(text: str) -> str:
    """Escape HTML special characters in plain text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _canvas_el(tag: str, text: str | None = None) -> ET.Element:
    """Create an element in the Canvas CCCV1p0 namespace."""
    el = ET.Element(f"{{{CANVAS_NS}}}{tag}")
    if text is not None:
        el.text = text
    return el


def _cc_el(tag: str, text: str | None = None) -> ET.Element:
    """Create an element in the IMS CC organization/resource namespace."""
    el = ET.Element(f"{{{CC_NS}}}{tag}")
    if text is not None:
        el.text = text
    return el


def next_module_position(modules_root: ET.Element) -> int:
    """Return the next module position (1-based) from module_meta.xml."""
    positions: list[int] = []
    for mod in modules_root:
        if not mod.tag.endswith("module"):
            continue
        pos_el = mod.find(f"{{{CANVAS_NS}}}position")
        if pos_el is not None and pos_el.text and pos_el.text.isdigit():
            positions.append(int(pos_el.text))
    return (max(positions) + 1) if positions else 1


def unique_wiki_path(unpacked: Path, title: str) -> tuple[str, Path]:
    """Choose a non-colliding ``wiki_content/<slug>.html`` path."""
    base = slugify(title)
    candidate = f"wiki_content/{base}.html"
    path = unpacked / candidate
    if not path.exists():
        return candidate, path
    for i in range(2, 1000):
        candidate = f"wiki_content/{base}-{i}.html"
        path = unpacked / candidate
        if not path.exists():
            return candidate, path
    raise RuntimeError(f"Could not find free wiki path for title: {title}")


def add_module(
    unpacked: Path,
    module_title: str,
    page_titles: list[str],
    *,
    workflow_state: str = "unpublished",
    sequential: bool = True,
    position: int | None = None,
) -> dict:
    """Create a module with wiki pages and wire it into the cartridge.

    Args:
        unpacked: Path to the unpacked IMSCC working tree.
        module_title: Title for the new module.
        page_titles: Titles of wiki pages to create and attach (in order).
        workflow_state: Module workflow state (default unpublished).
        sequential: Whether ``require_sequential_progress`` is true.
        position: Explicit module position; defaults to end of list.

    Returns:
        Summary dict with module identifier, position, and page paths.
    """
    module_meta_path = unpacked / "course_settings" / "module_meta.xml"
    manifest_path = unpacked / "imsmanifest.xml"
    if not module_meta_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError(
            f"Unpacked tree incomplete (need module_meta.xml + imsmanifest.xml): {unpacked}"
        )
    if not page_titles:
        raise ValueError("At least one page title is required")

    modules_root = ET.parse(module_meta_path).getroot()
    manifest_root = ET.parse(manifest_path).getroot()

    mod_pos = position if position is not None else next_module_position(modules_root)
    module_id = canvas_identifier()

    module_el = ET.Element(f"{{{CANVAS_NS}}}module", {"identifier": module_id})
    module_el.append(_canvas_el("title", module_title))
    module_el.append(_canvas_el("workflow_state", workflow_state))
    module_el.append(_canvas_el("position", str(mod_pos)))
    module_el.append(
        _canvas_el("require_sequential_progress", "true" if sequential else "false")
    )
    module_el.append(_canvas_el("locked", "false"))
    items_el = _canvas_el("items")
    module_el.append(items_el)

    # Organizations branch under LearningModules
    org_item = _find_learning_modules(manifest_root)
    org_module = _cc_el("item")
    org_module.set("identifier", module_id)
    org_module.append(_cc_el("title", module_title))

    resources_el = manifest_root.find(f"{{{CC_NS}}}resources")
    if resources_el is None:
        resources_el = _cc_el("resources")
        manifest_root.append(resources_el)

    created_pages: list[dict] = []
    for idx, page_title in enumerate(page_titles, start=1):
        page_id = canvas_identifier()
        item_id = canvas_identifier()
        rel, abs_path = unique_wiki_path(unpacked, page_title)
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(wiki_html(page_title, page_id), encoding="utf-8")

        item_el = ET.Element(f"{{{CANVAS_NS}}}item", {"identifier": item_id})
        item_el.append(_canvas_el("content_type", "WikiPage"))
        item_el.append(_canvas_el("workflow_state", "unpublished"))
        item_el.append(_canvas_el("title", page_title))
        item_el.append(_canvas_el("identifierref", page_id))
        item_el.append(_canvas_el("position", str(idx)))
        item_el.append(_canvas_el("new_tab", "false"))
        item_el.append(_canvas_el("indent", "0"))
        item_el.append(_canvas_el("link_settings_json", "null"))
        items_el.append(item_el)

        org_child = _cc_el("item")
        org_child.set("identifier", item_id)
        org_child.set("identifierref", page_id)
        org_child.append(_cc_el("title", page_title))
        org_module.append(org_child)

        res = ET.Element(
            f"{{{CC_NS}}}resource",
            {
                "identifier": page_id,
                "type": "webcontent",
                "href": rel,
            },
        )
        file_el = _cc_el("file")
        file_el.set("href", rel)
        res.append(file_el)
        resources_el.append(res)

        created_pages.append(
            {
                "title": page_title,
                "identifier": page_id,
                "item_identifier": item_id,
                "path": rel,
            }
        )

    modules_root.append(module_el)
    org_item.append(org_module)

    _write_xml(module_meta_path, modules_root, canvas_declaration=True)
    _write_xml(manifest_path, manifest_root, canvas_declaration=False)

    return {
        "module_identifier": module_id,
        "module_title": module_title,
        "position": mod_pos,
        "workflow_state": workflow_state,
        "pages": created_pages,
    }


def _find_learning_modules(manifest_root: ET.Element) -> ET.Element:
    """Return the organizations item with identifier LearningModules."""
    orgs = manifest_root.find(f"{{{CC_NS}}}organizations")
    if orgs is None:
        raise RuntimeError("imsmanifest.xml missing <organizations>")
    organization = orgs.find(f"{{{CC_NS}}}organization")
    if organization is None:
        raise RuntimeError("imsmanifest.xml missing <organization>")
    for item in organization.findall(f"{{{CC_NS}}}item"):
        if item.get("identifier") == "LearningModules":
            return item
    # Fallback: first top-level item
    first = organization.find(f"{{{CC_NS}}}item")
    if first is None:
        raise RuntimeError("imsmanifest.xml organization has no items")
    return first


def _write_xml(path: Path, root: ET.Element, *, canvas_declaration: bool) -> None:
    """Write XML with a UTF-8 declaration using a temporary namespace map."""
    # Register default xmlns only for this write to avoid cross-file pollution.
    if canvas_declaration:
        ET.register_namespace("", CANVAS_NS)
        ET.register_namespace("xsi", XSI_NS)
    else:
        ET.register_namespace("", CC_NS)
        ET.register_namespace("lom", "http://ltsc.ieee.org/xsd/imsccv1p1/LOM/resource")
        ET.register_namespace(
            "lomimscc", "http://ltsc.ieee.org/xsd/imsccv1p1/LOM/manifest"
        )
        ET.register_namespace("xsi", XSI_NS)
    rough = ET.tostring(root, encoding="unicode")
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + rough + "\n", encoding="utf-8")


def parse_pages_arg(raw: list[str]) -> list[str]:
    """Expand ``--pages`` values that may be comma-separated."""
    titles: list[str] = []
    for chunk in raw:
        for part in re.split(r"\s*,\s*", chunk):
            part = part.strip()
            if part:
                titles.append(part)
    return titles


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for scaffolding a Canvas module."""
    parser = argparse.ArgumentParser(
        description="Add a module + wiki pages to an unpacked Canvas IMSCC tree."
    )
    parser.add_argument(
        "--unpacked",
        type=Path,
        default=DEFAULT_UNPACKED,
        help=f"Unpacked working tree (default: {DEFAULT_UNPACKED})",
    )
    parser.add_argument("--title", required=True, help="Module title")
    parser.add_argument(
        "--pages",
        nargs="+",
        required=True,
        help="One or more page titles (comma-separated values also allowed)",
    )
    parser.add_argument(
        "--position",
        type=int,
        default=None,
        help="Module position (default: append at end)",
    )
    parser.add_argument(
        "--workflow-state",
        default="unpublished",
        help="Module workflow_state (default: unpublished)",
    )
    parser.add_argument(
        "--no-sequential",
        action="store_true",
        help="Do not require sequential progress",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: scaffold module + pages and print a short summary."""
    args = parse_args(argv)
    pages = parse_pages_arg(args.pages)
    try:
        result = add_module(
            args.unpacked,
            args.title,
            pages,
            workflow_state=args.workflow_state,
            sequential=not args.no_sequential,
            position=args.position,
        )
    except (OSError, ValueError, RuntimeError, ET.ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Added module: {result['module_title']}")
    print(f"  identifier: {result['module_identifier']}")
    print(f"  position:   {result['position']}")
    print(f"  state:      {result['workflow_state']}")
    for page in result["pages"]:
        print(f"  page: {page['title']} -> {page['path']} ({page['identifier']})")
    print("Next: python scripts/canvas_inventory.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
