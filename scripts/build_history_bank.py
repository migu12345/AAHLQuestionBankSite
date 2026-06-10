#!/usr/bin/env python3
"""
Build IB History question bank (new syllabus, 2017+).

Discovers Paper 1 question booklets, Paper 2, and Paper 3 (all regions) from
the IB past paper archive. Extracts question text from PDFs using fitz.
Writes data/history/processed/questions.json.

Usage:
  python3 scripts/build_history_bank.py
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
OUT = ROOT / "data" / "history" / "processed" / "questions.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

NON_ENGLISH = [
    "french", "german", "spanish", "arabic", "chinese", "japanese",
    "italian", "dutch", "swedish", "portuguese", "korean", "malay", "turkish",
]
SKIP_WORDS = ["text_booklet", "resource_booklet", "markscheme", "_ms", "art_history",
              "route_1", "route_2", "source_booklet"]

# P3 region slug → display name
REGION_MAP = {
    "africa_and_the_middle_east": "Africa and the Middle East",
    "africa": "Africa and the Middle East",
    "asia_and_oceania": "Asia and Oceania",
    "asia": "Asia and Oceania",
    "europe": "Europe",
    "the_americas": "the Americas",
    "americas": "the Americas",
}

# Paper 2 topic number → topic title (consistent across all papers)
P2_TOPICS = {
    1: "Society and economy (750–1400)",
    2: "Causes and effects of wars (750–1500)",
    3: "Dynasties and rulers (750–1500)",
    4: "Societies in transition (1400–1700)",
    5: "Early Modern states (1450–1789)",
    6: "Causes and effects of Early Modern wars (1500–1750)",
    7: "Origins, development and impact of industrialization (1750–2005)",
    8: "Independence movements (1800–2000)",
    9: "Emergence and development of democratic states (1848–2000)",
    10: "Authoritarian states (20th century)",
    11: "Causes and effects of 20th century wars",
    12: "The Cold War: Superpower tensions and rivalries (20th century)",
}

# Paper 1 prescribed subject number → display name
P1_SUBJECTS = {
    1: "Military leaders",
    2: "Conquest and its impact",
    3: "The move to global war",
    4: "Rights and protest",
    5: "Conflict and intervention",
}


def norm_ws(s: str) -> str:
    s = s.replace("\xa0", " ").replace("\t", " ")
    s = re.sub(r"[ ]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_text(doc: fitz.Document) -> str:
    pages = []
    for p in doc:
        pages.append(p.get_text("text") or "")
    return "\n".join(pages)


def clean_page_artifacts(text: str) -> str:
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if re.match(r"^[–\-]\s*\d+\s*[–\-]$", s):
            continue
        if re.match(r"^\d+\s*pages?$", s, re.I):
            continue
        if "turn over" in s.lower():
            continue
        if "international baccalaureate" in s.lower():
            continue
        if re.match(r"^\d{4}\s*[–\-]\s*\d{4}$", s):
            continue
        if re.match(r"^[©©]", s):
            continue
        lines.append(s)
    return "\n".join(lines)


def is_english(path: Path) -> bool:
    n = path.name.lower()
    return not any(lang in n for lang in NON_ENGLISH)


def should_skip(path: Path) -> bool:
    n = path.name.lower()
    return any(w in n for w in SKIP_WORDS)


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


# ---------------------------------------------------------------------------
# P2 parsing
# ---------------------------------------------------------------------------

def _collect_q_text(lines: List[str], start_i: int, inline: str) -> Tuple[str, int]:
    """Return (question_text, next_i).

    PDFs use two layouts:
      - Inline: "1. Question text here"  (older PDFs)
      - Split:  "1.\t" on one line, text on the following line(s)  (newer PDFs)
    """
    if inline:
        q_text = inline
    else:
        # Text is on the next line(s)
        q_text = ""
        while start_i < len(lines):
            nxt = lines[start_i].strip().replace("\xa0", " ")
            if not nxt:
                break
            # Don't consume what looks like a question number or heading
            if re.match(r"^(\d{1,2})\.$", nxt) or re.match(r"^Topic\s+\d+|^Section\s+\d+|^Prescribed\s+subject", nxt, re.I):
                break
            if re.match(r"^(\d{1,2})\.\s+\S", nxt):
                break
            q_text += (" " if q_text else "") + nxt
            start_i += 1
        if not q_text:
            return "", start_i

    # Collect continuation lines
    while start_i < len(lines):
        nxt = lines[start_i].strip().replace("\xa0", " ")
        if not nxt:
            break
        if re.match(r"^(\d{1,2})\.$", nxt):
            break
        if re.match(r"^(\d{1,2})\.\s+\S", nxt):
            break
        if re.match(r"^Topic\s+\d+|^Section\s+\d+|^Prescribed\s+subject", nxt, re.I):
            break
        q_text += " " + nxt
        start_i += 1

    return norm_ws(q_text), start_i


def parse_p2(text: str, session: str, year: int, tz: Optional[str]) -> List[dict]:
    text = clean_page_artifacts(text)
    sc = session_code(session, year)
    tz_label = f"TZ{tz}" if tz else ""
    paper_label = f"{session} {year} Paper 2{' ' + tz_label if tz_label else ''}"

    questions = []
    current_topic_num = None

    lines = [ln.replace("\xa0", " ").replace("\t", "") for ln in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Topic heading
        m_topic = re.match(r"^Topic\s+(\d+)[:\s]", line, re.I)
        if m_topic:
            current_topic_num = int(m_topic.group(1))
            i += 1
            continue

        # Question: "N." alone or "N. text..."
        m_q = re.match(r"^(\d{1,2})\.\s*(.*)", line)
        if m_q and current_topic_num is not None:
            qnum = int(m_q.group(1))
            inline = m_q.group(2).strip()
            i += 1
            q_text, i = _collect_q_text(lines, i, inline)
            if not q_text:
                continue

            tz_slug = tz.lower() if tz else "ntz"
            qid = f"hist_{sc}_p2_{tz_slug}_q{qnum}"
            questions.append({
                "id": qid,
                "paper": paper_label,
                "session": f"{session} {year}",
                "session_code": sc,
                "year": year,
                "paper_type": "Paper 2",
                "level": "HL/SL",
                "tz": tz_label or None,
                "question_number": qnum,
                "question_text": q_text,
                "topic": P2_TOPICS.get(current_topic_num, f"Topic {current_topic_num}"),
                "topic_number": current_topic_num,
                "region": None,
                "section": None,
                "marks": 15,
            })
            continue

        i += 1

    return questions


# ---------------------------------------------------------------------------
# P3 parsing
# ---------------------------------------------------------------------------

def region_from_filename(name: str) -> str:
    n = name.lower()
    for key, display in REGION_MAP.items():
        if key in n:
            return display
    return "Unknown"


def parse_p3(text: str, session: str, year: int, tz: Optional[str], region: str) -> List[dict]:
    text = clean_page_artifacts(text)
    sc = session_code(session, year)
    tz_label = f"TZ{tz}" if tz else ""
    region_slug = re.sub(r"[^a-z0-9]+", "_", region.lower()).strip("_")
    paper_label = f"{session} {year} Paper 3 – history of {region}{' ' + tz_label if tz_label else ''}"

    questions = []
    current_section_num = None
    current_section_name = None

    lines = [ln.replace("\xa0", " ").replace("\t", "") for ln in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Section heading: "Section N: ..."
        m_sec = re.match(r"^Section\s+(\d+)[:\s](.+)", line, re.I)
        if m_sec:
            current_section_num = int(m_sec.group(1))
            current_section_name = norm_ws(f"Section {m_sec.group(1)}: {m_sec.group(2)}")
            i += 1
            continue

        # Question
        m_q = re.match(r"^(\d{1,2})\.\s*(.*)", line)
        if m_q and current_section_num is not None:
            qnum = int(m_q.group(1))
            inline = m_q.group(2).strip()
            i += 1
            q_text, i = _collect_q_text(lines, i, inline)
            if not q_text:
                continue

            tz_slug = tz.lower() if tz else ""
            qid = f"hist_{sc}_p3_{region_slug}{'_' + tz_slug if tz_slug else ''}_q{qnum}"
            questions.append({
                "id": qid,
                "paper": paper_label,
                "session": f"{session} {year}",
                "session_code": sc,
                "year": year,
                "paper_type": "Paper 3",
                "level": "HL",
                "tz": tz_label or None,
                "question_number": qnum,
                "question_text": q_text,
                "topic": f"Paper 3 – history of {region}",
                "topic_number": None,
                "region": region,
                "section": current_section_name,
                "section_number": current_section_num,
                "marks": 15,
            })
            continue

        i += 1

    return questions


# ---------------------------------------------------------------------------
# P1 parsing
# ---------------------------------------------------------------------------

def parse_p1(text: str, session: str, year: int) -> List[dict]:
    text = clean_page_artifacts(text)
    sc = session_code(session, year)
    paper_label = f"{session} {year} Paper 1"

    questions = []
    current_ps_num = None

    lines = [ln.replace("\xa0", " ").replace("\t", "") for ln in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # "Prescribed subject N: Title"
        m_ps = re.match(r"^Prescribed\s+subject\s+(\d+)[:\s](.+)", line, re.I)
        if m_ps:
            current_ps_num = int(m_ps.group(1))
            i += 1
            continue

        # Questions: "N." alone or "N. text ..."
        m_q = re.match(r"^(\d{1,2})\.\s*(.*)", line)
        if m_q and current_ps_num is not None:
            qnum = int(m_q.group(1))
            inline = m_q.group(2).strip()

            # Collect the full question block (may include sub-parts (a), (b))
            i += 1
            block_parts = [inline] if inline else []
            while i < len(lines):
                nxt = lines[i].strip()
                if not nxt:
                    i += 1
                    break
                if re.match(r"^(\d{1,2})\.$", nxt) or re.match(r"^(\d{1,2})\.\s+\S", nxt):
                    break
                if re.match(r"^Prescribed\s+subject", nxt, re.I):
                    break
                block_parts.append(nxt)
                i += 1

            if not block_parts:
                continue

            full_text = norm_ws(" ".join(block_parts))

            # Split into sub-questions if "(a)" and "(b)" present
            sub_parts = re.split(r"(?=\([a-d]\))", full_text)
            sub_parts = [s.strip() for s in sub_parts if s.strip()]

            ps_name = P1_SUBJECTS.get(current_ps_num, f"Prescribed Subject {current_ps_num}")

            if len(sub_parts) <= 1:
                # Single question
                marks_m = re.search(r"\[(\d+)\]", full_text)
                marks = int(marks_m.group(1)) if marks_m else None
                qid = f"hist_{sc}_p1_ps{current_ps_num}_q{qnum}"
                questions.append({
                    "id": qid,
                    "paper": paper_label,
                    "session": f"{session} {year}",
                    "session_code": sc,
                    "year": year,
                    "paper_type": "Paper 1",
                    "level": "HL/SL",
                    "tz": None,
                    "question_number": qnum,
                    "question_text": full_text,
                    "topic": ps_name,
                    "topic_number": current_ps_num,
                    "region": None,
                    "section": None,
                    "marks": marks,
                    "prescribed_subject": current_ps_num,
                })
            else:
                # Sub-questions a, b, ...
                for part in sub_parts:
                    sub_m = re.match(r"^\(([a-d])\)\s*(.*)", part, re.DOTALL)
                    if sub_m:
                        sub_label = sub_m.group(1)
                        sub_text = norm_ws(sub_m.group(2))
                        marks_m = re.search(r"\[(\d+)\]", sub_text)
                        marks = int(marks_m.group(1)) if marks_m else None
                        qid = f"hist_{sc}_p1_ps{current_ps_num}_q{qnum}{sub_label}"
                        questions.append({
                            "id": qid,
                            "paper": paper_label,
                            "session": f"{session} {year}",
                            "session_code": sc,
                            "year": year,
                            "paper_type": "Paper 1",
                            "level": "HL/SL",
                            "tz": None,
                            "question_number": f"{qnum}{sub_label}",
                            "question_text": sub_text,
                            "topic": ps_name,
                            "topic_number": current_ps_num,
                            "region": None,
                            "section": None,
                            "marks": marks,
                            "prescribed_subject": current_ps_num,
                        })
                    else:
                        # fallback
                        marks_m = re.search(r"\[(\d+)\]", part)
                        marks = int(marks_m.group(1)) if marks_m else None
                        qid = f"hist_{sc}_p1_ps{current_ps_num}_q{qnum}x"
                        questions.append({
                            "id": qid,
                            "paper": paper_label,
                            "session": f"{session} {year}",
                            "session_code": sc,
                            "year": year,
                            "paper_type": "Paper 1",
                            "level": "HL/SL",
                            "tz": None,
                            "question_number": qnum,
                            "question_text": norm_ws(part),
                            "topic": ps_name,
                            "topic_number": current_ps_num,
                            "region": None,
                            "section": None,
                            "marks": marks,
                            "prescribed_subject": current_ps_num,
                        })
            continue

        i += 1

    return questions


# ---------------------------------------------------------------------------
# PDF discovery
# ---------------------------------------------------------------------------

def discover_history_pdfs() -> List[dict]:
    all_pdfs = list(SOURCE.rglob("*.pdf"))
    print(f"Scanning {len(all_pdfs)} PDFs...")
    results = []
    seen: dict[tuple, Path] = {}

    for pdf in all_pdfs:
        name = pdf.name.lower()
        if not ("history_paper" in name or "history paper" in name):
            continue
        if not is_english(pdf):
            continue
        if should_skip(pdf):
            continue
        if "art_history" in name:
            continue
        if "route_1" in name or "route_2" in name or "route 1" in name or "route 2" in name:
            continue
        if name.endswith(".txt"):
            continue

        sy = parse_session_year(pdf)
        if sy is None:
            continue
        session, year = sy
        if year < 2017:
            continue

        # Determine paper type
        paper_m = re.search(r"paper[_ ]+(\d)", name)
        if not paper_m:
            continue
        paper_num = paper_m.group(1)

        # P1: only question booklets
        if paper_num == "1" and "question_booklet" not in name:
            continue

        # TZ
        tz_m = re.search(r"tz([123])", name)
        tz = tz_m.group(1) if tz_m else None

        # P3 region
        region = None
        if paper_num == "3":
            region = region_from_filename(name)

        key = (year, session, paper_num, tz or "none", region or "none")
        if key in seen:
            existing = seen[key]
            # Prefer PDFs/ over HTML/ or other locations
            if "PDFs" in str(pdf) and ("HTML" in str(existing) or "DONATED" in str(existing)):
                seen[key] = pdf
            elif "DONATED" not in str(pdf) and "DONATED" in str(existing):
                seen[key] = pdf
        else:
            seen[key] = pdf

    for (year, session, paper_num, tz, region), path in seen.items():
        results.append({
            "year": year,
            "session": session,
            "paper_num": paper_num,
            "tz": None if tz == "none" else tz,
            "region": None if region == "none" else region,
            "path": path,
        })

    return sorted(results, key=lambda r: (r["year"], r["session"], r["paper_num"], r["tz"] or ""))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    pdfs = discover_history_pdfs()
    print(f"Found {len(pdfs)} history question papers")

    all_questions: List[dict] = []
    seen_ids: set[str] = set()

    for entry in pdfs:
        year = entry["year"]
        session = entry["session"]
        paper_num = entry["paper_num"]
        tz = entry["tz"]
        region = entry["region"]
        path = entry["path"]

        print(f"  {path.name} ...", end=" ", flush=True)

        try:
            doc = fitz.open(path)
        except Exception as e:
            print(f"SKIP ({e})")
            continue

        text = extract_text(doc)

        if paper_num == "2":
            qs = parse_p2(text, session, year, tz)
        elif paper_num == "3":
            qs = parse_p3(text, session, year, tz, region or "Unknown")
        elif paper_num == "1":
            qs = parse_p1(text, session, year)
        else:
            print("SKIP (unknown paper type)")
            continue

        # Deduplicate by ID
        added = 0
        for q in qs:
            if q["id"] in seen_ids:
                continue
            seen_ids.add(q["id"])
            all_questions.append(q)
            added += 1

        print(f"{added} questions")

    all_questions.sort(key=lambda q: (q["year"], q["session"], q["paper_type"], q.get("region") or "", q.get("tz") or "", str(q["question_number"]).zfill(4)))

    OUT.write_text(json.dumps(all_questions, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(all_questions)} history questions → {OUT}")


if __name__ == "__main__":
    main()
