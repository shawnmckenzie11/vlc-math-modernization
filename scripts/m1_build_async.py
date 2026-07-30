#!/usr/bin/env python3
"""Build Module 1 question SQLite DB and render the async HTML page from it.

Usage:
    python3 scripts/m1_build_async.py
    python3 scripts/m1_build_async.py --validate-only

Reads seed data from
`courses/MCF3M/modules/01-change-and-transformation/questions/seed_data.py`,
applies `questions/schema.sql`, writes `questions/m1_questions.sqlite`, and
regenerates `async/index.html` and `async/questions.html`.
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = ROOT / "courses/MCF3M/modules/01-change-and-transformation"
QUESTIONS_DIR = MODULE_DIR / "questions"
ASYNC_DIR = MODULE_DIR / "async"
SCHEMA_PATH = QUESTIONS_DIR / "schema.sql"
DB_PATH = QUESTIONS_DIR / "m1_questions.sqlite"
SEED_PATH = QUESTIONS_DIR / "seed_data.py"
HTML_PATH = ASYNC_DIR / "index.html"
QUESTIONS_HTML_PATH = ASYNC_DIR / "questions.html"
CURRICULUM_DB = ROOT / "courses/MCF3M/curriculum/mcf3m.sqlite"

TARGET_COUNTS = {
    "s1_relations": {"example": 2, "formative": 1, "practice": 3},
    "s2_constant_change": {"example": 4, "formative": 2, "practice": 6},
    "s3_life_bridge": {"example": 4, "formative": 2, "practice": 6},
    "s4_three_forms": {"example": 8, "formative": 4, "practice": 12},
    "s5_convert_forms": {"example": 12, "formative": 6, "practice": 18},
    "s6_transformations": {"example": 10, "formative": 5, "practice": 15},
}


def load_seed_module():
    """Import seed_data.py from the Module 1 questions folder.

    Returns:
        The loaded module object exposing SECTIONS, RESOURCES, ITEMS.
    """
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"Missing seed data: {SEED_PATH}")
    spec = importlib.util.spec_from_file_location("m1_seed_data", SEED_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load seed module from {SEED_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def known_expectation_codes(conn_curriculum: sqlite3.Connection) -> set[str]:
    """Return the set of valid specific expectation codes from curriculum DB.

    Args:
        conn_curriculum: Open connection to mcf3m.sqlite.

    Returns:
        Set of codes like 'A2.1'.
    """
    rows = conn_curriculum.execute(
        "SELECT code FROM specific_expectations"
    ).fetchall()
    return {r[0] for r in rows}


def validate_seed(seed, valid_codes: set[str]) -> None:
    """Validate section/item counts and expectation codes before writing DB.

    Args:
        seed: Loaded seed module.
        valid_codes: Codes present in curriculum DB.

    Raises:
        AssertionError / ValueError on structural problems.
    """
    sections = {s["section_key"]: s for s in seed.SECTIONS}
    assert set(sections) == set(TARGET_COUNTS), (
        f"Section keys mismatch: {set(sections)} vs {set(TARGET_COUNTS)}"
    )

    counts: dict[str, dict[str, int]] = {
        key: {"example": 0, "formative": 0, "practice": 0} for key in TARGET_COUNTS
    }
    for item in seed.ITEMS:
        sk = item["section_key"]
        if sk not in counts:
            raise ValueError(f"Unknown section_key on item: {sk}")
        counts[sk][item["item_type"]] += 1
        for code in item.get("expectations", []):
            if code not in valid_codes:
                raise ValueError(
                    f"Invented or unknown expectation code {code!r} on {item['title']!r}"
                )
        if item["item_type"] == "formative":
            fj = item.get("formative_json")
            if not fj or "choices" not in fj:
                raise ValueError(f"Formative missing choices: {item['title']}")
            if not any(c.get("correct") for c in fj["choices"]):
                raise ValueError(f"Formative has no correct choice: {item['title']}")
        if item["item_type"] in ("example", "practice") and not item.get("solution_html"):
            raise ValueError(f"Missing solution_html: {item['title']}")
        sid = item.get("smart_id")
        if not sid:
            raise ValueError(f"Missing smart_id on item: {item['title']}")
        if not re.fullmatch(r"M1-S[1-6]-[EFP]\d{2}", sid):
            raise ValueError(f"Bad smart_id format: {sid!r} on {item['title']!r}")

    smart_ids = [i["smart_id"] for i in seed.ITEMS]
    if len(smart_ids) != len(set(smart_ids)):
        raise ValueError("Duplicate smart_id values in seed")

    for sk, target in TARGET_COUNTS.items():
        for kind, n in target.items():
            got = counts[sk][kind]
            if got != n:
                raise AssertionError(
                    f"{sk} {kind}: expected {n}, got {got}"
                )

    if hasattr(seed, "validate_counts"):
        seed.validate_counts()

    for resource in seed.RESOURCES:
        if resource.get("kind") != "desmos":
            continue
        steps = (resource.get("interaction_steps_html") or "").strip()
        if not steps:
            raise ValueError(
                "Desmos resource missing interaction_steps_html: "
                f"{resource.get('title')!r} ({resource.get('section_key')})"
            )
        if "<li>" not in steps and "<ol>" not in steps:
            raise ValueError(
                "Desmos interaction_steps_html should include concrete list steps: "
                f"{resource.get('title')!r}"
            )


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create a fresh Module 1 questions database from schema.sql.

    Args:
        db_path: Destination sqlite path.

    Returns:
        Open write connection.
    """
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema)
    return conn


def seed_db(conn: sqlite3.Connection, seed) -> None:
    """Insert sections, resources, items, and expectation links.

    Args:
        conn: Open Module 1 questions DB connection.
        seed: Loaded seed module.
    """
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        ("module_id", "M1"),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        ("title", "Change & Transformation"),
    )
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?)",
        ("generated_by", "scripts/m1_build_async.py"),
    )

    for section in seed.SECTIONS:
        conn.execute(
            """
            INSERT INTO sections(
                section_key, title, student_title, weight_percent, sort_order,
                intro_html, hook_html, hook_kind
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                section["section_key"],
                section["title"],
                section["student_title"],
                section["weight_percent"],
                section["sort_order"],
                section["intro_html"],
                section["hook_html"],
                section.get("hook_kind", "reflection"),
            ),
        )

    for subsection in getattr(seed, "SUBSECTIONS", []):
        conn.execute(
            """
            INSERT INTO subsections(
                subsection_key, section_key, title, intro_html, sort_order
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                subsection["subsection_key"],
                subsection["section_key"],
                subsection["title"],
                subsection["intro_html"],
                subsection.get("sort_order", 0),
            ),
        )

    for resource in seed.RESOURCES:
        conn.execute(
            """
            INSERT INTO resources(
                section_key, kind, title, url, embed_url, sort_order, notes,
                interaction_steps_html, content_group, block_title, subsection_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resource["section_key"],
                resource["kind"],
                resource["title"],
                resource["url"],
                resource.get("embed_url"),
                resource.get("sort_order", 0),
                resource.get("notes"),
                resource.get("interaction_steps_html"),
                resource.get("content_group"),
                resource.get("block_title"),
                resource.get("subsection_key"),
            ),
        )

    for item in seed.ITEMS:
        cur = conn.execute(
            """
            INSERT INTO items(
                smart_id, module_id, section_key, item_type, subtype, title, stem_html,
                solution_html, formative_json, difficulty, source,
                artifact_tags_json, cluster_title, sort_order, subsection_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["smart_id"],
                "M1",
                item["section_key"],
                item["item_type"],
                item.get("subtype", "conceptual"),
                item["title"],
                item["stem_html"],
                item.get("solution_html"),
                json.dumps(item["formative_json"])
                if item.get("formative_json") is not None
                else None,
                item.get("difficulty", 2),
                item.get("source", "original:m1-rebuild"),
                json.dumps(item.get("artifact_tags", [])),
                item.get("cluster_title"),
                item.get("sort_order", 0),
                item.get("subsection_key"),
            ),
        )
        item_id = cur.lastrowid
        for code in item.get("expectations", []):
            conn.execute(
                "INSERT INTO item_expectations(item_id, expectation_code) VALUES (?, ?)",
                (item_id, code),
            )
    conn.commit()


def load_expectation_titles() -> dict[str, str]:
    """Load short display titles for specific expectation codes.

    Returns:
        Mapping of code -> truncated curriculum statement.
    """
    titles: dict[str, str] = {}
    if not CURRICULUM_DB.exists():
        return titles
    cur = sqlite3.connect(CURRICULUM_DB)
    for row in cur.execute("SELECT code, statement FROM specific_expectations"):
        text = " ".join((row[1] or "").split())
        titles[row[0]] = text[:72] + ("…" if len(text) > 72 else "")
    cur.close()
    return titles


def fetch_expectations_for_item(conn: sqlite3.Connection, item_id: int) -> list[str]:
    """List expectation codes tagged to one item.

    Args:
        conn: Questions DB connection.
        item_id: items.id value.

    Returns:
        Sorted list of expectation codes.
    """
    rows = conn.execute(
        """
        SELECT expectation_code FROM item_expectations
        WHERE item_id = ? ORDER BY expectation_code
        """,
        (item_id,),
    ).fetchall()
    return [r["expectation_code"] for r in rows]


def render_resource_card(resource: sqlite3.Row, *, compact: bool = False) -> str:
    """Render one Explore media card (KA / YouTube / Desmos).

    Khan Academy lesson pages refuse iframes (framing / CSP), so ``kind=khan``
    always renders an in-page link-out card with a prominent open button.
    Khan and YouTube use a one-line modality instruction + open-resource link
    (not verbose title/notes chrome). YouTube and Desmos keep iframes when
    ``embed_url`` is set. Desmos shows an overall activity ask up front and
    puts calculator how-to steps in an expandable ``<details>``.

    Args:
        resource: Row from resources table.
        compact: When True, omit outer heading chrome (used inside tabs).

    Returns:
        HTML fragment.

    Raises:
        ValueError: If a Desmos resource is missing interaction steps.
    """
    kind = resource["kind"]
    title = html.escape(resource["title"])
    url = html.escape(resource["url"])
    notes_raw = (resource["notes"] or "").strip()
    embed = resource["embed_url"]
    link_out = kind == "khan" or not embed
    cls = "resource resource-card"
    if compact:
        cls += " resource-card-compact"
    if link_out and kind == "khan":
        cls += " resource-card-linkout"
    if kind == "desmos":
        cls += " resource-card-desmos"

    parts = [f'<div class="{cls}">']

    if kind == "youtube":
        parts.append(
            '<p class="resource-instruction">'
            "Watch the following video"
            ' · <a href="'
            f'{url}" target="_blank" rel="noopener">Open resource</a></p>'
        )
    elif kind == "khan":
        parts.append(
            '<p class="resource-instruction">'
            "Watch and complete activities here</p>"
        )
        parts.append(
            f'<p class="resource-cta">'
            f'<a class="resource-cta-btn" href="{url}" target="_blank" rel="noopener">'
            f"Open on Khan Academy</a></p>"
        )
    elif kind == "desmos":
        parts.append(
            f'<p class="resource-chrome">Desmos · {title} · '
            f'<a href="{url}" target="_blank" rel="noopener">Open resource</a></p>'
        )
        if notes_raw:
            parts.append(
                f'<p class="desmos-activity-ask">{html.escape(notes_raw)}</p>'
            )
        steps = ""
        try:
            steps = (resource["interaction_steps_html"] or "").strip()
        except (KeyError, IndexError):
            steps = ""
        if not steps:
            raise ValueError(
                f"Desmos card missing interaction_steps_html: {resource['title']!r}"
            )
        parts.append(
            '<details class="desmos-howto">'
            "<summary>How to use this calculator</summary>"
            '<div class="desmos-steps" aria-label="Desmos calculator steps">'
            f"{steps}"
            "</div>"
            "</details>"
        )
    else:
        kind_label = html.escape(kind.title())
        notes = html.escape(notes_raw)
        chrome_bits = [kind_label, title]
        if notes:
            chrome_bits.append(notes)
        chrome = " · ".join(chrome_bits)
        parts.append(
            f'<p class="resource-chrome">{chrome} · '
            f'<a href="{url}" target="_blank" rel="noopener">Open resource</a></p>'
        )

    if embed and kind != "khan":
        tall = " embed-tall" if kind == "desmos" else ""
        parts.append(
            f'<div class="embed-frame{tall}">'
            f'<iframe src="{html.escape(embed)}" title="{title}" '
            f'loading="lazy" allowfullscreen '
            f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
            f'gyroscope; picture-in-picture"></iframe></div>'
        )
    parts.append("</div>")
    return "\n".join(parts)


def render_resource(resource: sqlite3.Row) -> str:
    """Backward-compatible alias for a single Explore card.

    Args:
        resource: Row from resources table.

    Returns:
        HTML fragment.
    """
    return render_resource_card(resource)


def group_explore_resources(
    resources: list[sqlite3.Row],
) -> list[tuple[str, str, list[sqlite3.Row]]]:
    """Cluster resources into sequential Explore blocks.

    Resources that share a non-empty ``content_group`` are one tabbed block
    (same idea, alternate modalities). Empty/null ``content_group`` values
    each become their own sequential block.

    Args:
        resources: Ordered resource rows for one section.

    Returns:
        List of (group_key, block_title, rows) in display order.
    """
    buckets: dict[str, list[sqlite3.Row]] = {}
    order: list[str] = []
    singleton_i = 0
    for row in resources:
        group = (row["content_group"] or "").strip()
        if group:
            key = f"g:{group}"
        else:
            singleton_i += 1
            key = f"solo:{row['id']}:{singleton_i}"
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(row)

    blocks: list[tuple[str, str, list[sqlite3.Row]]] = []
    for key in order:
        rows = sorted(buckets[key], key=lambda r: (r["sort_order"], r["id"]))
        title = ""
        for r in rows:
            if r["block_title"]:
                title = r["block_title"]
                break
        if not title:
            title = rows[0]["title"]
        blocks.append((key, title, rows))
    return blocks


def render_explore_blocks(
    resources: list[sqlite3.Row],
    *,
    id_prefix: str | None = None,
) -> str:
    """Render Explore media using Shawn's same-content vs sequential rule.

    - Multiple media with the same ``content_group`` → one Explore block with tabs.
    - Different ideas → separate sequential Explore blocks (never tabbed together).

    Args:
        resources: Resource rows for the section.
        id_prefix: Optional unique prefix for tab button/panel IDs (e.g. a
            subsection key) so multiple Explore blocks on one page stay unique.

    Returns:
        HTML for all Explore blocks, or empty string.
    """
    if not resources:
        return ""
    blocks = group_explore_resources(list(resources))
    parts: list[str] = []
    for bi, (_key, block_title, rows) in enumerate(blocks):
        heading = html.escape(block_title)
        if len(rows) == 1:
            parts.append(
                f'<div class="block explore-block">'
                f"<h3>Explore · {heading}</h3>"
                f"{render_resource_card(rows[0])}"
                f"</div>"
            )
            continue
        # Same-content alternate modalities → tabs
        base = id_prefix or rows[0]["section_key"]
        tab_id = f"explore-tabs-{html.escape(str(base))}-{bi}"
        buttons = []
        panels = []
        for ti, row in enumerate(rows):
            btn_id = f"{tab_id}-btn-{ti}"
            panel_id = f"{tab_id}-panel-{ti}"
            selected = "true" if ti == 0 else "false"
            hidden = "" if ti == 0 else " hidden"
            label = html.escape(row["kind"].upper() if row["kind"] != "youtube" else "Video")
            short = html.escape(row["title"][:42] + ("…" if len(row["title"]) > 42 else ""))
            buttons.append(
                f'<button type="button" class="explore-tab" role="tab" '
                f'id="{btn_id}" aria-controls="{panel_id}" aria-selected="{selected}" '
                f'data-tab-panel="{panel_id}">'
                f'<span class="explore-tab-kind">{label}</span>'
                f'<span class="explore-tab-title">{short}</span>'
                f"</button>"
            )
            panels.append(
                f'<div class="explore-tab-panel{hidden}" role="tabpanel" '
                f'id="{panel_id}" aria-labelledby="{btn_id}">'
                f"{render_resource_card(row, compact=True)}"
                f"</div>"
            )
        parts.append(
            f'<div class="block explore-block explore-block-tabs" data-explore-tabs>'
            f"<h3>Explore · {heading}</h3>"
            f'<p class="explore-tabs-hint">Same idea — pick a modality:</p>'
            f'<div class="explore-tablist" role="tablist">{"".join(buttons)}</div>'
            f'{"".join(panels)}'
            f"</div>"
        )
    return "\n".join(parts)


def _exp_data_attr(codes: list[str]) -> str:
    """Build a Canvas-portable ``data-expectations`` attribute value.

    Args:
        codes: Expectation codes in display order.

    Returns:
        Comma-separated codes, HTML-escaped for attribute use.
    """
    return html.escape(",".join(codes))


def _card_header(item: sqlite3.Row, kind_label: str) -> str:
    """Build the muted smart-id badge + kind label for a question card.

    Args:
        item: items row with smart_id.
        kind_label: Human label such as 'Example · process'.

    Returns:
        HTML for the card header line.
    """
    sid = html.escape(item["smart_id"])
    return (
        f'<div class="card-meta">'
        f'<span class="smart-id" title="Question ID">{sid}</span>'
        f'<span class="item-label">{kind_label}</span>'
        f"</div>"
    )


def render_example(
    item: sqlite3.Row, codes: list[str], titles: dict[str, str]
) -> str:
    """Render a worked / conceptual example as a Canvas-style question card.

    Args:
        item: items row.
        codes: Expectation codes for the item.
        titles: Code -> short statement map.

    Returns:
        HTML fragment.
    """
    tags = json.loads(item["artifact_tags_json"] or "[]")
    subtype = html.escape(item["subtype"] or "conceptual")
    sid = html.escape(item["smart_id"])
    data_exp = f' data-expectations="{_exp_data_attr(codes)}"' if codes else ""
    return f"""
<article class="q-card example" id="{sid}"{data_exp}>
  {_card_header(item, f"Example · {subtype}")}
  <h4>{html.escape(item['title'])}</h4>
  <div class="stem">{item['stem_html']}</div>
  <details>
    <summary>Show solution</summary>
    <div class="solution-body solution">{item['solution_html'] or ''}</div>
  </details>
  {_tags_html(tags, codes, titles)}
</article>
""".strip()


def render_practice(
    item: sqlite3.Row, codes: list[str], titles: dict[str, str]
) -> str:
    """Render a short-answer practice item as a question card.

    Args:
        item: items row.
        codes: Expectation codes.
        titles: Code -> short statement map.

    Returns:
        HTML fragment.
    """
    tags = json.loads(item["artifact_tags_json"] or "[]")
    sid = html.escape(item["smart_id"])
    data_exp = f' data-expectations="{_exp_data_attr(codes)}"' if codes else ""
    return f"""
<article class="q-card practice" id="{sid}"{data_exp}>
  {_card_header(item, "Practice")}
  <h4>{html.escape(item['title'])}</h4>
  <div class="stem">{item['stem_html']}</div>
  <details>
    <summary>Show solution</summary>
    <div class="solution-body solution">{item['solution_html'] or ''}</div>
  </details>
  {_tags_html(tags, codes, titles)}
</article>
""".strip()


def render_formative(
    item: sqlite3.Row, codes: list[str], titles: dict[str, str]
) -> str:
    """Render a formative multiple-choice check as a question card.

    Args:
        item: items row including formative_json.
        codes: Expectation codes.
        titles: Code -> short statement map.

    Returns:
        HTML fragment.
    """
    data = json.loads(item["formative_json"] or "{}")
    choices = data.get("choices", [])
    fb_correct = html.escape(data.get("feedback_correct", "Nice work."))
    fb_incorrect = html.escape(
        data.get("feedback_incorrect", "Review the example above and try again.")
    )
    choice_html = []
    for choice in choices:
        cid = html.escape(str(choice["id"]))
        correct = "true" if choice.get("correct") else "false"
        choice_html.append(
            f'<label class="choice">'
            f'<input type="radio" name="choice" value="{cid}" data-correct="{correct}">'
            f'<span>{choice["html"]}</span></label>'
        )
    tags = json.loads(item["artifact_tags_json"] or "[]")
    sid = html.escape(item["smart_id"])
    data_exp = f' data-expectations="{_exp_data_attr(codes)}"' if codes else ""
    return f"""
<article class="q-card formative" id="{sid}"{data_exp}
  data-formative
  data-feedback-correct="{fb_correct}"
  data-feedback-incorrect="{fb_incorrect}">
  {_card_header(item, "Check your understanding")}
  <h4>{html.escape(item['title'])}</h4>
  <div class="stem">{item['stem_html']}</div>
  <form>
    <div class="choices">
      {''.join(choice_html)}
    </div>
    <div class="formative-actions">
      <button type="submit" data-action="submit">Submit</button>
      <button type="button" class="secondary" data-action="reset">Try again</button>
    </div>
  </form>
  <div class="feedback" aria-live="polite"></div>
  {_tags_html(tags, codes, titles)}
</article>
""".strip()


def _tags_html(
    tags: list[str], codes: list[str], titles: dict[str, str] | None = None
) -> str:
    """Build a quiet, Canvas-portable curriculum expectation footnote.

    Visible codes stay subtle; full statements live in ``title`` (hover) and
    ``data-expectations`` so import/scraping still has the codes.

    Args:
        tags: Artifact tag strings.
        codes: Expectation codes.
        titles: Optional code -> short statement map for footnotes.

    Returns:
        HTML fragment (may be empty).
    """
    titles = titles or {}
    parts = []
    # Artifact tags stay in the DB for later assessment wiring; omit from
    # student HTML so the page does not read like construction notes.
    _ = tags
    if codes:
        hover_bits = []
        for code in codes:
            label = titles.get(code, "")
            if label:
                hover_bits.append(f"{code} — {label}")
            else:
                hover_bits.append(code)
        title_attr = html.escape(" · ".join(hover_bits))
        visible = html.escape(" · ".join(codes))
        parts.append(
            f'<aside class="expectation-footnote" '
            f'data-expectations="{_exp_data_attr(codes)}" '
            f'title="{title_attr}">'
            f'<span class="exp-codes" aria-label="Curriculum expectations">'
            f"{visible}</span></aside>"
        )
    return "\n".join(parts)


def render_section(
    conn: sqlite3.Connection,
    section: sqlite3.Row,
    titles: dict[str, str],
) -> str:
    """Render one module section from DB rows.

    When ``subsections`` rows exist for the section, Explore media, examples,
    and formative checks are interleaved under each subsection heading (with
    that subsection's intro blurb). Practice stays at the section end in
    topic-clustered accordions. Flat sections (no subsections) keep the
    previous single Explore → examples → formatives → practice layout.

    Args:
        conn: Questions DB.
        section: sections row.
        titles: Expectation code -> short statement map.

    Returns:
        HTML for the section.
    """
    sk = section["section_key"]
    resources = conn.execute(
        """
        SELECT * FROM resources WHERE section_key = ?
        ORDER BY sort_order, id
        """,
        (sk,),
    ).fetchall()
    items = conn.execute(
        """
        SELECT * FROM items WHERE section_key = ?
        ORDER BY
          CASE item_type
            WHEN 'example' THEN 1
            WHEN 'formative' THEN 2
            WHEN 'practice' THEN 3
            ELSE 4
          END,
          sort_order, id
        """,
        (sk,),
    ).fetchall()
    subsections = conn.execute(
        """
        SELECT * FROM subsections WHERE section_key = ?
        ORDER BY sort_order, subsection_key
        """,
        (sk,),
    ).fetchall()

    examples = [i for i in items if i["item_type"] == "example"]
    formatives = [i for i in items if i["item_type"] == "formative"]
    practices = [i for i in items if i["item_type"] == "practice"]

    def _row_subkey(row) -> str:
        """Return subsection_key or empty string for a resource/item row.

        Args:
            row: sqlite3.Row or mapping with optional subsection_key.

        Returns:
            Subsection key string (may be empty).
        """
        try:
            return (row["subsection_key"] or "").strip()
        except (KeyError, IndexError, TypeError):
            return ""

    def bundle(
        label: str,
        rows: list,
        renderer,
        *,
        accordion: str | bool = False,
    ) -> str:
        """Wrap a list of cards; practice/formative use collapsed accordions.

        Args:
            label: Section subheading (e.g. Practice).
            rows: Item rows to render.
            renderer: Card render function.
            accordion: ``False`` for expanded lists; ``"practice"`` for
                topic-clustered practice accordions; ``"formative"`` for
                per-check formative accordions (all collapsed, including first).

        Returns:
            HTML block or empty string.
        """
        if not rows:
            return ""

        def render_rows(group_rows: list) -> str:
            """Render one ordered list of item cards.

            Args:
                group_rows: Items in display order.

            Returns:
                Concatenated card HTML.
            """
            return "\n".join(
                renderer(
                    row,
                    fetch_expectations_for_item(conn, row["id"]),
                    titles,
                )
                for row in group_rows
            )

        mode = accordion
        if mode is True:
            mode = "practice"
        if not mode:
            return f'<div class="block"><h3>{label}</h3>\n{render_rows(rows)}\n</div>'

        if mode == "formative":
            # One collapsed group per formative — never auto-open the first.
            parts = [
                '<div class="block formative-block">'
                "<h3>Formative checks</h3>"
            ]
            for row in rows:
                summary = html.escape(row["title"] or "Formative check")
                parts.append(
                    f'<details class="formative-accordion">'
                    f"<summary>{summary}</summary>\n"
                    f"{render_rows([row])}\n"
                    f"</details>"
                )
            parts.append("</div>")
            return "\n".join(parts)

        # Group similar-topic practice by cluster_title (preserve sort order).
        clusters: dict[str, list] = {}
        order: list[str] = []
        for row in rows:
            keys = row.keys() if hasattr(row, "keys") else []
            title = ""
            if "cluster_title" in keys:
                title = (row["cluster_title"] or "").strip()
            if not title:
                title = "Practice"
            if title not in clusters:
                clusters[title] = []
                order.append(title)
            clusters[title].append(row)

        parts = ['<div class="block practice-block"><h3>Practice</h3>']
        for title in order:
            group = clusters[title]
            n = len(group)
            summary = html.escape(title)
            parts.append(
                f'<details class="practice-accordion">'
                f"<summary>{summary} "
                f'<span class="practice-count">({n})</span></summary>\n'
                f"{render_rows(group)}\n"
                f"</details>"
            )
        parts.append("</div>")
        return "\n".join(parts)

    hook_labels = {
        "reflection": "Try this",
        "exploration": "Explore",
        "discussion": "Think it through",
        "activity": "Try this",
    }
    hook_label = hook_labels.get(section["hook_kind"], "Try this")

    body_parts: list[str] = []
    if subsections:
        for sub in subsections:
            sub_key = sub["subsection_key"]
            sub_resources = [r for r in resources if _row_subkey(r) == sub_key]
            sub_examples = [i for i in examples if _row_subkey(i) == sub_key]
            sub_formatives = [i for i in formatives if _row_subkey(i) == sub_key]
            sub_practices = [i for i in practices if _row_subkey(i) == sub_key]
            body_parts.append(
                f'<section class="subsection" id="{html.escape(sub_key)}">'
                f"<h3>{html.escape(sub['title'])}</h3>"
                f'<div class="block prose subsection-intro">{sub["intro_html"]}</div>'
                f"{render_explore_blocks(sub_resources, id_prefix=sub_key)}"
                f"{bundle('Examples', sub_examples, render_example)}"
                f"{bundle('Formative checks', sub_formatives, render_formative, accordion='formative')}"
                f"{bundle('Practice', sub_practices, render_practice, accordion='practice')}"
                f"</section>"
            )
        # Orphan media/items (no subsection_key) stay after named beats.
        orphan_resources = [r for r in resources if not _row_subkey(r)]
        orphan_examples = [i for i in examples if not _row_subkey(i)]
        orphan_formatives = [i for i in formatives if not _row_subkey(i)]
        orphan_practices = [i for i in practices if not _row_subkey(i)]
        if orphan_resources or orphan_examples or orphan_formatives or orphan_practices:
            body_parts.append(render_explore_blocks(orphan_resources))
            body_parts.append(bundle("Examples", orphan_examples, render_example))
            body_parts.append(
                bundle(
                    "Formative checks",
                    orphan_formatives,
                    render_formative,
                    accordion="formative",
                )
            )
            body_parts.append(
                bundle(
                    "Practice",
                    orphan_practices,
                    render_practice,
                    accordion="practice",
                )
            )
        middle = "\n".join(p for p in body_parts if p)
    else:
        middle = "\n".join(
            p
            for p in (
                render_explore_blocks(list(resources)),
                bundle("Examples", examples, render_example),
                bundle(
                    "Formative checks",
                    formatives,
                    render_formative,
                    accordion="formative",
                ),
                bundle("Practice", practices, render_practice, accordion="practice"),
            )
            if p
        )

    return f"""
<section class="section" id="{html.escape(sk)}">
  <header class="section-head">
    <h2>{html.escape(section['student_title'])}</h2>
  </header>
  <div class="block prose intro">{section['intro_html']}</div>
  <div class="block hook">
    <h3>{html.escape(hook_label)}</h3>
    <div class="prose">{section['hook_html']}</div>
  </div>
  {middle}
</section>
""".strip()


def render_html(conn: sqlite3.Connection) -> str:
    """Assemble the full Module 1 async HTML page from the questions DB.

    Args:
        conn: Open questions DB.

    Returns:
        Complete HTML document string.
    """
    titles = load_expectation_titles()
    sections = conn.execute(
        "SELECT * FROM sections ORDER BY sort_order"
    ).fetchall()
    nav = "\n".join(
        f'<a href="#{html.escape(s["section_key"])}">{html.escape(s["student_title"])}</a>'
        for s in sections
    )
    nav += '\n<a href="questions.html">Question bank</a>'
    body_sections = "\n".join(
        render_section(conn, s, titles) for s in sections
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCF3M Module 1 — Change &amp; Transformation</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
    onload="renderMathInElement(document.body, {{delimiters:[{{left:'$$',right:'$$',display:true}},{{left:'\\\\[',right:'\\\\]',display:true}},{{left:'$',right:'$',display:false}},{{left:'\\\\(',right:'\\\\)',display:false}}],throwOnError:false}});"></script>
</head>
<body>
  <nav class="site-nav" aria-label="Module sections">
    {nav}
  </nav>
  <div class="page-shell">
  <main class="wrap">
    <header class="hero">
      <p class="eyebrow">MCF3M · Module 1</p>
      <h1>Change &amp; Transformation</h1>
      <p class="lede">
        Life is full of change — sometimes steady, sometimes speeding up, slowing down, or
        flipping direction. This module builds the math that helps you describe those patterns
        clearly, so you can make better sense of the stories unfolding around you.
      </p>
    </header>
    {body_sections}
    <p class="footer-note">
      Regenerated from <code>questions/m1_questions.sqlite</code> via
      <code>python3 scripts/m1_build_async.py</code>. Do not hand-edit this HTML as source of truth.
    </p>
  </main>
  </div>
  <script src="module.js"></script>
</body>
</html>
"""


def _stem_preview(stem_html: str, limit: int = 120) -> str:
    """Strip tags for a plain-text stem preview in the question bank table.

    Args:
        stem_html: Raw stem HTML.
        limit: Max characters for the preview.

    Returns:
        Escaped plain-text preview.
    """
    text = re.sub(r"<[^>]+>", " ", stem_html or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return html.escape(text)


def render_questions_html(conn: sqlite3.Connection) -> str:
    """Build a filterable front-facing index of all Module 1 questions by smart_id.

    Args:
        conn: Open questions DB.

    Returns:
        Complete HTML document for questions.html.
    """
    titles = load_expectation_titles()
    _ = titles  # available if we later show short titles in the bank table
    section_titles = {
        r["section_key"]: r["student_title"]
        for r in conn.execute("SELECT section_key, student_title FROM sections")
    }
    rows = conn.execute(
        """
        SELECT i.*, GROUP_CONCAT(e.expectation_code, ', ') AS expectations
        FROM items i
        LEFT JOIN item_expectations e ON e.item_id = i.id
        GROUP BY i.id
        ORDER BY i.section_key, i.item_type, i.sort_order, i.smart_id
        """
    ).fetchall()

    # Stable sort: S1..S6 then example, formative, practice
    type_rank = {"example": 0, "formative": 1, "practice": 2}

    def sort_key(row):
        sk = row["section_key"]
        m = re.match(r"s(\d+)_", sk)
        sn = int(m.group(1)) if m else 99
        return (sn, type_rank.get(row["item_type"], 9), row["sort_order"], row["smart_id"])

    rows = sorted(rows, key=sort_key)

    trs = []
    for row in rows:
        sid = html.escape(row["smart_id"])
        exps = html.escape(row["expectations"] or "")
        sec = html.escape(section_titles.get(row["section_key"], row["section_key"]))
        typ = html.escape(row["item_type"])
        title = html.escape(row["title"])
        preview = _stem_preview(row["stem_html"])
        trs.append(
            f'<tr data-smart-id="{sid}" data-section="{html.escape(row["section_key"])}" '
            f'data-type="{typ}" data-expectations="{exps.lower()}" '
            f'data-title="{title.lower()}" data-preview="{preview.lower()}">'
            f'<td><a href="index.html#{sid}"><code>{sid}</code></a></td>'
            f"<td>{typ}</td>"
            f"<td>{sec}</td>"
            f"<td><strong>{title}</strong><div class=\"preview\">{preview}</div></td>"
            f"<td>{exps}</td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCF3M Module 1 — Question bank</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <nav class="site-nav" aria-label="Module navigation">
    <a href="index.html">Lesson page</a>
    <a href="questions.html" aria-current="page">Question bank</a>
  </nav>
  <div class="page-shell page-shell-wide">
  <main class="wrap">
    <header class="hero">
      <p class="eyebrow">MCF3M · Module 1 · Question bank</p>
      <h1>All questions by ID</h1>
      <p class="lede">
        Browse every example, formative, and practice item. Click an ID to jump to its card
        on the lesson page. Filters run in your browser — nothing is sent to a server.
      </p>
    </header>
    <div class="bank-filters" id="bank-filters">
      <label>Search
        <input type="search" id="filter-q" placeholder="ID, title, stem, expectation…" autocomplete="off">
      </label>
      <label>Section
        <select id="filter-section">
          <option value="">All</option>
          {''.join(f'<option value="{html.escape(k)}">{html.escape(v)}</option>' for k, v in section_titles.items())}
        </select>
      </label>
      <label>Type
        <select id="filter-type">
          <option value="">All</option>
          <option value="example">example</option>
          <option value="formative">formative</option>
          <option value="practice">practice</option>
        </select>
      </label>
    </div>
    <p class="bank-count" id="bank-count">{len(trs)} questions</p>
    <div class="bank-table-wrap">
      <table class="bank-table" id="bank-table">
        <thead>
          <tr>
            <th>Smart ID</th>
            <th>Type</th>
            <th>Section</th>
            <th>Title / preview</th>
            <th>Expectations</th>
          </tr>
        </thead>
        <tbody>
          {''.join(trs)}
        </tbody>
      </table>
    </div>
    <p class="footer-note">
      Generated from <code>m1_questions.sqlite</code>. Smart ID scheme:
      <code>M1-S{{section}}-{{E|F|P}}{{nn}}</code>.
    </p>
  </main>
  </div>
  <script src="questions.js"></script>
</body>
</html>
"""


def count_report(conn: sqlite3.Connection) -> str:
    """Build a human-readable counts table vs targets.

    Args:
        conn: Questions DB.

    Returns:
        Multiline report string.
    """
    lines = ["section_key | type | got | target"]
    for sk, target in TARGET_COUNTS.items():
        for kind, n in target.items():
            got = conn.execute(
                "SELECT COUNT(*) AS c FROM items WHERE section_key=? AND item_type=?",
                (sk, kind),
            ).fetchone()["c"]
            lines.append(f"{sk} | {kind} | {got} | {n}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: validate seed, build DB, render HTML.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:]).

    Returns:
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate seed counts/codes without writing DB/HTML",
    )
    args = parser.parse_args(argv)

    seed = load_seed_module()
    if not CURRICULUM_DB.exists():
        raise FileNotFoundError(f"Curriculum DB missing: {CURRICULUM_DB}")
    cur_conn = sqlite3.connect(CURRICULUM_DB)
    valid_codes = known_expectation_codes(cur_conn)
    cur_conn.close()

    validate_seed(seed, valid_codes)
    print("Seed validation OK.")
    if args.validate_only:
        return 0

    ASYNC_DIR.mkdir(parents=True, exist_ok=True)
    QUESTIONS_DIR.mkdir(parents=True, exist_ok=True)
    conn = init_db(DB_PATH)
    seed_db(conn, seed)
    HTML_PATH.write_text(render_html(conn), encoding="utf-8")
    QUESTIONS_HTML_PATH.write_text(render_questions_html(conn), encoding="utf-8")
    print(f"Wrote {DB_PATH}")
    print(f"Wrote {HTML_PATH}")
    print(f"Wrote {QUESTIONS_HTML_PATH}")
    print(count_report(conn))
    conn.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
