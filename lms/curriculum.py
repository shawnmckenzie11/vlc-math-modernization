"""Ontario curriculum catalog: PDF registry, course codes, MCF3M expectations.

Never invents expectation wording. Course titles come from local Ministry PDFs
when extractable; other documents are registered as sources until a PDF exists.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from school_db import SchoolDB
from paths import (
    MCF3M_EXPECTATIONS,
    MATH_CURRICULUM_PDF,
    ONTARIO_SOURCES_DIR,
    REPO_ROOT,
)

logger = logging.getLogger(__name__)

# Official Ontario secondary curriculum PDFs (Ministry / edu.gov.on.ca).
# Local copies live under lms/sources/ontario-curriculum/ when downloaded.
ONTARIO_DOCUMENTS: list[dict[str, str]] = [
    {
        "title": "The Ontario Curriculum, Grades 11 and 12: Mathematics (revised)",
        "subject": "Mathematics",
        "grades": "11-12",
        "source_url": "https://www.edu.gov.on.ca/eng/curriculum/secondary/math1112currb.pdf",
        "local_path": "courses/MCF3M/sources/ontario-math-curriculum-gr-11-12.pdf",
        "filename": "",
    },
    {
        "title": "The Ontario Curriculum, Grades 11 and 12: English",
        "subject": "English",
        "grades": "11-12",
        "source_url": "https://www.edu.gov.on.ca/eng/curriculum/secondary/english1112currb.pdf",
        "local_path": "lms/sources/ontario-curriculum/english-11-12.pdf",
        "filename": "english-11-12.pdf",
    },
    {
        "title": "The Ontario Curriculum, Grades 11 and 12: Science",
        "subject": "Science",
        "grades": "11-12",
        "source_url": "https://www.edu.gov.on.ca/eng/curriculum/secondary/2009science11_12.pdf",
        "local_path": "lms/sources/ontario-curriculum/science-11-12.pdf",
        "filename": "science-11-12.pdf",
    },
    {
        "title": "The Ontario Curriculum, Grades 11 and 12: Canadian and World Studies",
        "subject": "Canadian and World Studies",
        "grades": "11-12",
        "source_url": "https://www.edu.gov.on.ca/eng/curriculum/secondary/2015cws11and12.pdf",
        "local_path": "lms/sources/ontario-curriculum/canadian-world-studies-11-12.pdf",
        "filename": "canadian-world-studies-11-12.pdf",
    },
    {
        "title": "The Ontario Curriculum, Grades 11 and 12: The Arts",
        "subject": "The Arts",
        "grades": "11-12",
        "source_url": "https://www.edu.gov.on.ca/eng/curriculum/secondary/arts1112curr2010.pdf",
        "local_path": "lms/sources/ontario-curriculum/arts-11-12.pdf",
        "filename": "arts-11-12.pdf",
    },
    {
        "title": "The Ontario Curriculum, Grades 11 and 12: Business Studies",
        "subject": "Business Studies",
        "grades": "11-12",
        "source_url": "https://www.edu.gov.on.ca/eng/curriculum/secondary/business1112currb.pdf",
        "local_path": "lms/sources/ontario-curriculum/business-11-12.pdf",
        "filename": "business-11-12.pdf",
    },
    {
        "title": "The Ontario Curriculum, Grades 11 and 12: Technological Education",
        "subject": "Technological Education",
        "grades": "11-12",
        "source_url": "https://www.edu.gov.on.ca/eng/curriculum/secondary/2009teched1112curr.pdf",
        "local_path": "lms/sources/ontario-curriculum/technological-education-11-12.pdf",
        "filename": "technological-education-11-12.pdf",
    },
]

_TOC_COURSE_RE = re.compile(
    r"(.+?),\s*(University(?:/College)?|College|Workplace)\s+Preparation\s*\(([A-Z]{3}[34][A-Z0-9])\)",
)
_GENERIC_CODE_RE = re.compile(
    r"(.+?),\s*(University(?:/College)?|College|Workplace|Open)\s+Preparation\s*\(([A-Z]{3}[3-4][A-Z0-9])\)",
)
_GRADE_HEADING_RE = re.compile(r"Grade\s+(11|12)\b")

_PATHWAY_MAP = {
    "University": "U",
    "University/College": "M",
    "College": "C",
    "Workplace": "E",
    "Open": "O",
}


def _pdf_text(path: Path) -> str:
    """Extract plain text from a PDF using PyMuPDF when available.

    Args:
        path: Local PDF.

    Returns:
        Concatenated page text, or empty if the file/library is missing.
    """
    if not path.is_file():
        return ""
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF is not installed; skipping PDF extract for %s", path)
        return ""
    doc = fitz.open(path)
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def extract_courses_from_pdf_text(text: str) -> list[dict[str, Any]]:
    """Parse Ministry TOC-style ``Title, Pathway Preparation (CODE)`` lines.

    Grade is taken from the nearest preceding ``Grade 11`` / ``Grade 12``
    heading. Titles are the PDF wording (plus grade when a heading exists).

    Args:
        text: Extracted PDF text.

    Returns:
        Course dicts with code, title, grade, pathway.
    """
    if not text:
        return []
    current_grade: int | None = None
    found: dict[str, dict[str, Any]] = {}
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        grade_match = _GRADE_HEADING_RE.search(line)
        if grade_match and len(line) < 40:
            current_grade = int(grade_match.group(1))
        match = _GENERIC_CODE_RE.search(line) or _TOC_COURSE_RE.search(line)
        if not match:
            continue
        name = match.group(1).strip(" .")
        # TOC lines may include leftover leaders from the previous entry.
        name = re.sub(r"^[\d.\s]+", "", name)
        name = re.sub(r".*\s{2,}", "", name)
        if len(name) > 80:
            name = name[-80:]
            name = re.sub(r"^[^A-Za-z]+", "", name)
        pathway_label = match.group(2).strip()
        code = match.group(3).strip().upper()
        grade = current_grade
        if code[3:4] == "3":
            grade = grade or 11
        elif code[3:4] == "4":
            grade = grade or 12
        title = name
        if grade and "Grade" not in title:
            title = f"{name}, Grade {grade}, {pathway_label} Preparation"
        else:
            title = f"{name}, {pathway_label} Preparation"
        found[code] = {
            "code": code,
            "title": title,
            "grade": grade,
            "pathway": _PATHWAY_MAP.get(pathway_label, pathway_label[:1]),
        }
    return list(found.values())


def load_mcf3m_expectation_rows(seed_path: Path | None = None) -> list[dict[str, Any]]:
    """Flatten ``expectations_seed.json`` into school ``expectations`` rows.

    Args:
        seed_path: Override path (tests).

    Returns:
        Rows with kind/code/parent/strand/statement/verification_status.
        Empty if the seed file is missing (never fabricates statements).
    """
    path = Path(seed_path or MCF3M_EXPECTATIONS)
    if not path.is_file():
        logger.warning("MCF3M expectations seed missing at %s", path)
        return []
    seed = json.loads(path.read_text(encoding="utf-8"))
    status = str(seed.get("verification_status") or "verified_from_pdf_text_extraction")
    rows: list[dict[str, Any]] = []
    for strand in seed.get("strands") or []:
        strand_code = str(strand.get("code") or "")
        strand_name = str(strand.get("name") or strand_code)
        strand_label = f"{strand_code} {strand_name}".strip()
        for overall in strand.get("overall") or []:
            rows.append(
                {
                    "kind": "overall",
                    "code": overall.get("code"),
                    "parent_code": None,
                    "strand": strand_label,
                    "statement": overall.get("statement"),
                    "verification_status": status,
                }
            )
        for specific in strand.get("specific") or []:
            rows.append(
                {
                    "kind": "specific",
                    "code": specific.get("code"),
                    "parent_code": specific.get("overall") or specific.get("parent_code"),
                    "strand": strand_label,
                    "statement": specific.get("statement"),
                    "verification_status": status,
                }
            )
    return rows


def seed_curriculum(school: SchoolDB) -> dict[str, Any]:
    """Register documents, extract course codes from local PDFs, inherit MCF3M.

    Args:
        school: Open school database.

    Returns:
        Summary counts for logs/tests.
    """
    ONTARIO_SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {
        "documents": 0,
        "courses": 0,
        "mcf3m_expectations": 0,
        "pdfs_extracted": [],
        "pdfs_missing": [],
    }
    math_doc_id: int | None = None
    for spec in ONTARIO_DOCUMENTS:
        rel = spec.get("local_path") or ""
        local = (REPO_ROOT / rel) if rel else None
        exists = bool(local and local.is_file())
        doc_id = school.upsert_document(
            title=spec["title"],
            jurisdiction="Ontario",
            grades=spec.get("grades"),
            subject=spec.get("subject"),
            source_url=spec.get("source_url"),
            local_path=rel if exists else rel,
        )
        summary["documents"] += 1
        if spec["subject"] == "Mathematics":
            math_doc_id = doc_id
        target = local if exists else None
        if target is None:
            summary["pdfs_missing"].append(spec["title"])
            continue
        text = _pdf_text(target)
        courses = extract_courses_from_pdf_text(text)
        if not courses:
            summary["pdfs_missing"].append(f"{spec['title']} (no codes extracted)")
            continue
        summary["pdfs_extracted"].append(spec["subject"])
        content_root_by_code = {}
        mcf_root = REPO_ROOT / "courses" / "MCF3M"
        if mcf_root.is_dir():
            content_root_by_code["MCF3M"] = "courses/MCF3M"
        for course in courses:
            school.upsert_ontario_course(
                course["code"],
                course["title"],
                grade=course.get("grade"),
                pathway=course.get("pathway"),
                document_id=doc_id,
                content_root=content_root_by_code.get(course["code"]),
                expectations_status=(
                    "verified" if course["code"] == "MCF3M" else "unverified"
                ),
            )
            summary["courses"] += 1

    # MCF3M overall/specific from the existing verified seed — not invented.
    mcf_rows = load_mcf3m_expectation_rows()
    if mcf_rows:
        if math_doc_id is None:
            math_doc_id = school.upsert_document(
                title="The Ontario Curriculum, Grades 11 and 12: Mathematics (revised)",
                jurisdiction="Ontario",
                grades="11-12",
                subject="Mathematics",
                local_path=str(MATH_CURRICULUM_PDF.relative_to(REPO_ROOT)),
            )
        if not school.get_ontario_course("MCF3M"):
            school.upsert_ontario_course(
                "MCF3M",
                "Functions and Applications, Grade 11, University/College Preparation",
                grade=11,
                pathway="M",
                document_id=math_doc_id,
                content_root="courses/MCF3M",
                expectations_status="verified",
            )
            summary["courses"] += 1
        summary["mcf3m_expectations"] = school.replace_course_expectations(
            "MCF3M", mcf_rows, status="verified"
        )
    return summary
