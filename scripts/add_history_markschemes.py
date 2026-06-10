#!/usr/bin/env python3
"""
Extract history markscheme text from PDFs and add markscheme_text field
to data/history/processed/questions.json.

Usage:
  python3 scripts/add_history_markschemes.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

REGION_MAP = {
    "africa_and_the_middle_east": "Africa and the Middle East",
    "africa": "Africa and the Middle East",
    "asia_and_oceania": "Asia and Oceania",
    "asia": "Asia and Oceania",
    "europe": "Europe",
    "the_americas": "the Americas",
    "americas": "the Americas",
}


def norm_ws(s: str) -> str:
    s = s.replace("\xa0", " ").replace("\t", " ")
    s = re.sub(r"[ ]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_pdf_text(path: Path) -> str:
    doc = fitz.open(str(path))
    pages = []
    for p in doc:
        pages.append(p.get_text("text") or "")
    doc.close()
    return "\n".join(pages)


def clean_ms_text(text: str) -> str:
    """Remove page headers, footers, copyright pages."""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue
        # Page number separators: "– 4 –"
        if re.match(r"^[–\-]\s*\d+\s*[–\-]$", s):
            continue
        # IB exam code headers like "M23/3/HISTX/BP1/ENG/TZ0/XX/M"
        if re.match(r"^[A-Z]\d{2}/\d/HIST", s):
            continue
        # "27 pages" or "15 pages"
        if re.match(r"^\d+\s*pages?$", s, re.I):
            continue
        # Boilerplate IB phrases
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
        if "criminal offense" in s.lower():
            continue
        if "ib organization" in s.lower():
            continue
        if "prohibited and" in s.lower():
            continue
        if "without the prior" in s.lower():
            continue
        if re.match(r"^\d{4}\s*[–\-]\s*\d{4}$", s):
            continue
        lines.append(s)
    # Collapse runs of blank lines to one
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return result.strip()


def parse_session_year(path: Path) -> Optional[Tuple[str, int]]:
    session = None
    year = None
    for part in path.parts:
        m = re.search(r"(20\d\d)", part)
        if m and year is None:
            year = int(m.group(1))
        pl = part.lower()
        if "may" in pl:
            session = "May"
        elif "november" in pl:
            session = "November"
    if year and session:
        return session, year
    return None


def session_code(session: str, year: int) -> str:
    return ("m" if session == "May" else "n") + str(year)[-2:]


def is_english(path: Path) -> bool:
    n = path.name.lower()
    return not any(lang in n for lang in NON_ENGLISH)


# ---------------------------------------------------------------------------
# P1 markscheme extraction
# ---------------------------------------------------------------------------

def parse_p1_ms(text: str) -> Dict[str, str]:
    """Return {question_key: markscheme_text}.

    question_key = f"ps{ps_num}_q{qnum}" or f"ps{ps_num}_q{qnum}{sub}" (e.g. "ps1_q1a")
    """
    text = clean_ms_text(text)
    results: Dict[str, str] = {}
    current_ps = None

    # Split text into lines for processing
    lines = [ln for ln in text.splitlines()]
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Detect "Prescribed subject N: ..."
        m_ps = re.match(r"^Prescribed\s+subject\s+(\d+)[:\s]", stripped, re.I)
        if m_ps:
            current_ps = int(m_ps.group(1))
            i += 1
            continue

        if current_ps is None:
            i += 1
            continue

        # Detect question start: "N." alone or "N. text..."
        m_q = re.match(r"^(\d{1,2})\.\s*(.*)", stripped)
        if m_q:
            qnum = int(m_q.group(1))
            # Collect block until next question number or next PS heading
            block_lines = [lines[i]]
            i += 1
            while i < n:
                nxt = lines[i].strip()
                if re.match(r"^(\d{1,2})\.\s", nxt) or re.match(r"^(\d{1,2})\.$", nxt):
                    break
                if re.match(r"^Prescribed\s+subject\s+\d+", nxt, re.I):
                    break
                block_lines.append(lines[i])
                i += 1

            block = "\n".join(block_lines).strip()

            # Check for sub-questions (a), (b), (c) in block
            sub_splits = re.split(r"(?=\n\s*\([a-d]\)\s)", block)
            if len(sub_splits) <= 1:
                # No sub-questions — single question
                key = f"ps{current_ps}_q{qnum}"
                results[key] = norm_ws(block)
            else:
                # First split may be the question header with no sub-content; skip if empty
                for part in sub_splits:
                    m_sub = re.match(r".*?\(([a-d])\)\s*(.*)", part, re.DOTALL | re.IGNORECASE)
                    if m_sub:
                        sub_label = m_sub.group(1).lower()
                        key = f"ps{current_ps}_q{qnum}{sub_label}"
                        results[key] = norm_ws(part.strip())
                    elif part.strip() and not re.match(r"^\d{1,2}\.\s*$", part.strip()):
                        # Fallback: no sub-label found, store as plain question
                        key = f"ps{current_ps}_q{qnum}"
                        results.setdefault(key, norm_ws(part.strip()))
            continue

        i += 1

    return results


# ---------------------------------------------------------------------------
# P2/P3 markscheme extraction
# ---------------------------------------------------------------------------

_SEC_RE = re.compile(r"^(Topic|Section)\s+\d+", re.I)
_SEC_N_RE = re.compile(r"^\d{1,2}:\s")  # Americas "N: Title" style
# Question patterns: "N." / "N)" / "N TZ1." / "N TZ2." etc.
_Q_RE = re.compile(r"^(\d{1,2})(?:[.)]|\s+TZ\d+[.)])\s*(.*)")
_Q_TERM_RE = re.compile(r"^(\d{1,2})(?:[.)]|\s+TZ\d+[.)])")


def _is_section(line: str) -> bool:
    return bool(_SEC_RE.match(line) or _SEC_N_RE.match(line))


def extract_markbands(text: str, paper: str = "p2") -> str:
    """Extract the generic markbands section before the first Topic/Section."""
    if paper == "p2":
        boundary = re.search(r"\nTopic\s+\d+", text)
    else:
        boundary = re.search(r"\nSection\s+\d+", text)
        if not boundary:
            boundary = re.search(r"\n\d{1,2}:\s", text)
    if not boundary:
        return ""
    # Start from "Markbands for paper" to skip cover/copyright pages
    mb_start = re.search(r"Markbands for paper\s+[23]", text, re.I)
    if mb_start:
        mb = text[mb_start.start():boundary.start()].strip()
    else:
        # Fallback: use apply-the-markbands paragraph as start
        apply_start = re.search(r"Apply the markbands", text, re.I)
        if apply_start:
            mb = text[apply_start.start():boundary.start()].strip()
        else:
            mb = text[:boundary.start()].strip()
    return norm_ws(mb)


def parse_p23_ms(text: str, paper: str = "p2") -> Dict[int, str]:
    """Return {question_number: markscheme_text} for Paper 2 or Paper 3."""
    text = clean_ms_text(text)
    markbands = extract_markbands(text, paper)
    results: Dict[int, str] = {}

    if paper == "p2":
        start_m = re.search(r"\nTopic\s+\d+", text)
    else:
        start_m = re.search(r"\nSection\s+\d+", text)
        if not start_m:
            start_m = re.search(r"\n\d{1,2}:\s", text)

    if not start_m:
        return results

    body = text[start_m.start():].strip()
    lines = body.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        stripped = lines[i].strip()

        # Section/Topic heading — skip
        if _is_section(stripped):
            i += 1
            continue

        m_q = _Q_RE.match(stripped)
        if m_q:
            qnum = int(m_q.group(1))
            block_lines = [lines[i]]
            i += 1
            while i < n:
                nxt = lines[i].strip()
                if _Q_TERM_RE.match(nxt):
                    break
                if _is_section(nxt):
                    break
                block_lines.append(lines[i])
                i += 1

            specific = norm_ws("\n".join(block_lines).strip())
            full = (markbands + "\n\n---\n\n" + specific) if markbands else specific
            results[qnum] = full
            continue

        i += 1

    return results


# ---------------------------------------------------------------------------
# PDF discovery
# ---------------------------------------------------------------------------

def discover_markschemes() -> List[dict]:
    """Find all English history markscheme PDFs for the new syllabus (2017+)."""
    results = []
    for pdf in SOURCE.rglob("*.pdf"):
        name = pdf.name.lower()
        if "history_paper" not in name and "history paper" not in name:
            continue
        if not ("markscheme" in name or "_ms" in name):
            continue
        if not is_english(pdf):
            continue
        if "route_1" in name or "route_2" in name:
            continue
        if "art_history" in name:
            continue
        sv = parse_session_year(pdf)
        if not sv:
            continue
        session, year = sv
        if year < 2017:
            continue

        sc = session_code(session, year)
        tz = None
        tz_m = re.search(r"_TZ(\d)_", pdf.name, re.I)
        if tz_m:
            tz = f"TZ{tz_m.group(1)}"

        paper_type = None
        if "_paper_1_" in name or "_paper1_" in name:
            paper_type = "P1"
        elif "_paper_2_" in name or "_paper2_" in name:
            paper_type = "P2"
        elif "_paper_3_" in name or "_paper3_" in name:
            paper_type = "P3"
        if not paper_type:
            continue

        region = None
        if paper_type == "P3":
            for slug, display in REGION_MAP.items():
                if slug in name:
                    region = display
                    break
            if not region:
                continue

        results.append({
            "path": pdf,
            "session": session,
            "year": year,
            "session_code": sc,
            "tz": tz,
            "paper_type": paper_type,
            "region": region,
        })
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    questions = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    # Build lookup: id → question dict
    by_id = {q["id"]: q for q in questions}

    markschemes = discover_markschemes()
    print(f"Found {len(markschemes)} history markscheme PDFs")

    attached = 0
    for ms in markschemes:
        path: Path = ms["path"]
        sc = ms["session_code"]
        paper_type = ms["paper_type"]
        tz = ms["tz"]
        region = ms["region"]

        try:
            raw_text = extract_pdf_text(path)
        except Exception as e:
            print(f"  SKIP {path.name}: {e}")
            continue

        if paper_type == "P1":
            ms_data = parse_p1_ms(raw_text)
            # Combine sub-question markschemes for questions stored without sub-label
            combined: Dict[str, str] = {}
            for key, ms_text in ms_data.items():
                qid = f"hist_{sc}_p1_{key}"
                if qid in by_id:
                    by_id[qid]["markscheme_text"] = ms_text
                    attached += 1
                else:
                    # e.g. key="ps1_q1a" but questions.json has "ps1_q1" (combined)
                    m_sub = re.match(r"(ps\d+_q\d+)[a-z]$", key)
                    if m_sub:
                        base_qid = f"hist_{sc}_p1_{m_sub.group(1)}"
                        combined.setdefault(base_qid, "")
                        combined[base_qid] = (combined[base_qid] + "\n\n" + ms_text).strip()
            for base_qid, ms_text in combined.items():
                if base_qid in by_id and not by_id[base_qid].get("markscheme_text"):
                    by_id[base_qid]["markscheme_text"] = ms_text
                    attached += 1

        elif paper_type == "P2":
            ms_data = parse_p23_ms(raw_text, "p2")
            # questions.json uses numeric TZ slug: "hist_{sc}_p2_1_q{N}" or "hist_{sc}_p2_ntz_q{N}"
            tz_slug = tz[-1] if tz else "ntz"  # "TZ1" → "1", None → "ntz"
            for qnum, ms_text in ms_data.items():
                qid = f"hist_{sc}_p2_{tz_slug}_q{qnum}"
                if qid in by_id:
                    by_id[qid]["markscheme_text"] = ms_text
                    attached += 1

        elif paper_type == "P3":
            ms_data = parse_p23_ms(raw_text, "p3")
            region_slug_map = {
                "Africa and the Middle East": "africa_and_the_middle_east",
                "Asia and Oceania": "asia_and_oceania",
                "Europe": "europe",
                "the Americas": "the_americas",
            }
            rslug = region_slug_map.get(region, "")
            # questions.json uses numeric TZ slug: "hist_{sc}_p3_{region}_{tz_num}_q{N}"
            tz_num = tz[-1] if tz else ""
            for qnum, ms_text in ms_data.items():
                if tz_num:
                    qid = f"hist_{sc}_p3_{rslug}_{tz_num}_q{qnum}"
                else:
                    qid = f"hist_{sc}_p3_{rslug}_q{qnum}"
                if qid in by_id:
                    by_id[qid]["markscheme_text"] = ms_text
                    attached += 1

    QUESTIONS_JSON.write_text(
        json.dumps(questions, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Attached markscheme text to {attached} questions")
    total = len(questions)
    with_ms = sum(1 for q in questions if q.get("markscheme_text"))
    print(f"{with_ms}/{total} questions now have markscheme text")


if __name__ == "__main__":
    main()
