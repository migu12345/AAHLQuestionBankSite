#!/usr/bin/env python3
"""
Extract P1 source booklet text and add sources to history questions.json.

Discovers text_booklet / resource_booklet PDFs for each P1 session,
parses Source A–D (or E–H, etc.) per prescribed subject, and stores
them in questions.json under a "sources" field on each P1 question.

Usage:
  python3 scripts/add_history_sources.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

SOURCE = Path("/Users/s933863@aics.espritscholen.nl/Desktop/Downloads/IB PAST PAPERS - YEAR")
QUESTIONS_JSON = ROOT / "data" / "history" / "processed" / "questions.json"

NON_ENGLISH = [
    "french", "german", "spanish", "arabic", "chinese", "japanese",
    "italian", "dutch", "swedish", "portuguese", "korean", "malay", "turkish",
]


def parse_session_year(path: Path):
    session = year = None
    for part in path.parts:
        m = re.search(r"(20\d\d)", part)
        if m and year is None:
            year = int(m.group(1))
        pl = part.lower()
        if "may" in pl:
            session = "May"
        elif "november" in pl:
            session = "November"
    return (session, year) if session and year else None


def session_code(session: str, year: int) -> str:
    return ("m" if session == "May" else "n") + str(year)[-2:]


def is_english(path: Path) -> bool:
    n = path.name.lower()
    return not any(lang in n for lang in NON_ENGLISH)


def extract_pdf_text(path: Path) -> str:
    doc = fitz.open(str(path))
    pages = [doc[p].get_text("text") or "" for p in range(len(doc))]
    doc.close()
    return "\n".join(pages)


def clean_booklet_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if re.match(r"^[–\-]\s*\d+\s*[–\-]$", s):  # page numbers
            continue
        if re.match(r"^[A-Z]\d{2}/\d/HIST", s):  # IB codes
            continue
        if re.match(r"^\d+\s*pages?$", s, re.I):
            continue
        if "turn over" in s.lower():
            continue
        if "international baccalaureate" in s.lower():
            continue
        if re.match(r"^[©©]", s):
            continue
        if "all rights reserved" in s.lower():
            continue
        if "prior written permission" in s.lower():
            continue
        lines.append(s)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def parse_sources(text: str) -> Dict[str, Dict[str, List]]:
    """
    Returns {ps_key: [source_dict, ...]} where ps_key = f"ps{N}".
    source_dict = {"label": "A", "attribution": "...", "text": "..."}
    """
    text = clean_booklet_text(text)
    results: Dict[str, List] = {}

    # Split into prescribed-subject blocks
    ps_splits = re.split(r"(?=\bPrescribed\s+subject\s+\d+)", text, flags=re.I)

    for ps_block in ps_splits:
        m_ps = re.match(r"Prescribed\s+subject\s+(\d+)[:\s](.+)", ps_block, re.I)
        if not m_ps:
            continue
        ps_num = int(m_ps.group(1))
        ps_key = f"ps{ps_num}"

        # Split block by "Source X" markers
        # Use lookahead so we keep the "Source X" line with the block
        source_parts = re.split(r"(?=\bSource\s+[A-Z]\b)", ps_block)

        sources = []
        for part in source_parts:
            m_src = re.match(r"Source\s+([A-Z])\s*\n?(.*)", part, re.DOTALL)
            if not m_src:
                continue
            label = m_src.group(1)
            body = m_src.group(2).strip()

            # First non-empty line(s) before the actual text are the attribution
            # Attribution ends when the "real" source content starts (longer sentences)
            body_lines = [ln for ln in body.splitlines() if ln.strip()]

            # Filter out disclaimer/reference pages
            if any(kw in body.lower() for kw in ("disclaimer:", "references:", "source used with", "accessed")):
                continue

            lower_body = body.lower()
            # Image sources have attribution describing a visual artefact
            image_keywords = ["depicts", "depicting", "cartoon", "photograph", "painting",
                              "map", "drawing", "illustrates", "illustrating", "illustration",
                              "illustrator", "poster", "portrait", "picture", "engraving",
                              "woodcut", "etching", "print by"]
            is_image = (
                "removed for copyright" in lower_body
                or any(kw in lower_body[:400] for kw in image_keywords)
                or len(body_lines) <= 2
            )

            # Collect attribution: lines up to and including the line ending with
            # a year in parentheses (e.g. "(2009)." or "(October 1520)").
            attribution_lines = []
            text_lines = []
            attribution_done = False
            for ln in body_lines:
                if re.match(r"^End of\b", ln, re.I):
                    continue
                if attribution_done:
                    text_lines.append(ln)
                else:
                    attribution_lines.append(ln)
                    if re.search(r"\(\d{4}(?:[–\-]\d{2,4})?\)[.,]?\s*$", ln):
                        attribution_done = True
                    elif ln.endswith(".") and len(attribution_lines) >= 2:
                        attribution_done = True

            attribution = " ".join(attribution_lines).strip()
            source_text = "\n".join(text_lines).strip()

            if not attribution and not source_text:
                continue  # empty block — skip

            text_source_kws = ["writing in", "writing about", "in a speech", "in a letter",
                              "published", "in a report", "in an article", "in the book",
                              "in a book", "in a journal", "in the journal"]
            is_text_source = any(kw in attribution.lower() for kw in text_source_kws)

            if "removed for copyright" in lower_body:
                source_text = "[Source text removed for copyright reasons]"
            elif is_image and not is_text_source:
                source_text = "[Visual source — not available as text]"
            elif not source_text:
                source_text = "[Source text not available]"

            sources.append({
                "label": label,
                "attribution": attribution,
                "text": source_text,
            })

        if sources:
            results[ps_key] = sources

    return results


def discover_booklets() -> List[dict]:
    """Find all English P1 source/text/resource booklets for new syllabus (2017+)."""
    found = []
    for pdf in SOURCE.rglob("*.pdf"):
        name = pdf.name.lower()
        if not is_english(pdf):
            continue
        is_booklet = (
            ("history_paper_1" in name or "history paper 1" in name)
            and ("text_booklet" in name or "resource_booklet" in name or "source_booklet" in name)
            and "art_history" not in name
        )
        if not is_booklet:
            continue
        sv = parse_session_year(pdf)
        if not sv:
            continue
        session, year = sv
        if year < 2017:
            continue
        sc = session_code(session, year)
        found.append({"path": pdf, "session": session, "year": year, "session_code": sc})
    return found


BOOKLETS_DIR = ROOT / "data" / "history" / "processed" / "source_booklets"


def main() -> None:
    import shutil
    BOOKLETS_DIR.mkdir(parents=True, exist_ok=True)

    questions = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    # Index P1 questions by session_code + ps_num
    p1_by_key: Dict[str, List[dict]] = {}
    for q in questions:
        if q.get("paper_type") != "Paper 1":
            continue
        sc = q.get("session_code", "")
        ps_num = q.get("prescribed_subject")
        if not ps_num:
            continue
        key = f"{sc}_ps{ps_num}"
        p1_by_key.setdefault(key, []).append(q)

    booklets = discover_booklets()
    # Deduplicate: keep one booklet per session_code (prefer shorter path = standard location)
    seen_sc: Dict[str, Path] = {}
    for b in sorted(booklets, key=lambda x: len(str(x["path"]))):
        sc = b["session_code"]
        if sc not in seen_sc:
            seen_sc[sc] = b["path"]

    print(f"Found {len(seen_sc)} unique source booklets")

    attached = 0
    for sc, pdf_path in sorted(seen_sc.items()):
        # Copy booklet PDF into the repo for serving
        dest = BOOKLETS_DIR / f"{sc}.pdf"
        if not dest.exists():
            shutil.copy2(str(pdf_path), str(dest))
            print(f"  Copied {pdf_path.name} → {dest.name}")

        rel_pdf = f"data/history/processed/source_booklets/{sc}.pdf"

        try:
            raw = extract_pdf_text(pdf_path)
        except Exception as e:
            print(f"  SKIP {pdf_path.name}: {e}")
            continue

        sources_by_ps = parse_sources(raw)
        if not sources_by_ps:
            print(f"  NO SOURCES: {pdf_path.name}")
            continue

        for ps_key, sources in sources_by_ps.items():
            lookup_key = f"{sc}_{ps_key}"
            qs = p1_by_key.get(lookup_key, [])
            for q in qs:
                q["sources"] = sources
                q["source_booklet_path"] = rel_pdf
                attached += 1

    QUESTIONS_JSON.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    total_p1 = sum(len(v) for v in p1_by_key.values())
    with_src = sum(1 for q in questions if q.get("paper_type") == "Paper 1" and q.get("sources"))
    print(f"Attached sources to {attached} questions")
    print(f"{with_src}/{total_p1} P1 questions now have sources")


if __name__ == "__main__":
    main()
