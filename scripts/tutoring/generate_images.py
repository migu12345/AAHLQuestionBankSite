#!/usr/bin/env python3
"""Generate per-question screenshots for tutoring PDFs and attach paths."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

QUESTIONS_JSON = ROOT / "data" / "tutoring" / "processed" / "questions.json"
OUT_DIR = ROOT / "data" / "tutoring" / "processed" / "images" / "questions"
SOURCE_DIR = Path("/Users/s933863@aics.espritscholen.nl/Documents/Tutoring Questions/Topic 1 Number and Algebra")


@dataclass
class StartPos:
    qnum: int
    page: int
    y: float


def detect_starts(doc: fitz.Document) -> List[StartPos]:
    starts: Dict[int, Tuple[int, float]] = {}
    for pno in range(len(doc)):
        page = doc[pno]
        blocks = page.get_text("dict").get("blocks", [])
        pending_num: int | None = None
        pending_y: float | None = None
        pending_x: float | None = None
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                line_text = "".join(span.get("text", "") for span in spans).strip()
                if not line_text:
                    continue
                y = float(line.get("bbox", [0, 0, 0, 0])[1])
                x = float(line.get("bbox", [0, 0, 0, 0])[0])
                m = re.match(r"^(?P<num>\d{1,2})\.\s+", line_text)
                qnum: int | None = None

                if m:
                    qnum = int(m.group("num"))
                else:
                    m_pending = re.match(r"^(?P<num>\d{1,2})$", line_text)
                    if m_pending:
                        pending_num = int(m_pending.group("num"))
                        pending_y = y
                        pending_x = x
                        continue
                    if pending_num is not None:
                        # Common in these worksheets: number line and question text are split.
                        if (pending_x is not None and pending_x < 80) and re.match(r"^[A-Za-z(]", line_text):
                            qnum = pending_num
                            y = pending_y if pending_y is not None else y
                        pending_num = None
                        pending_y = None
                        pending_x = None

                if qnum is None:
                    continue
                if qnum < 1 or qnum > 120:
                    continue
                if qnum in starts:
                    continue
                starts[qnum] = (pno, y)
    out = [StartPos(qnum=q, page=pg, y=y) for q, (pg, y) in starts.items()]
    out.sort(key=lambda s: (s.page, s.y))
    return out


def crop_question(doc: fitz.Document, starts: List[StartPos], qnum: int, out_prefix: Path) -> List[str]:
    start_idx = None
    for i, s in enumerate(starts):
        if s.qnum == qnum:
            start_idx = i
            break
    if start_idx is None:
        return []

    s = starts[start_idx]
    n = starts[start_idx + 1] if start_idx + 1 < len(starts) else None

    image_paths: List[str] = []
    last_page = n.page if n is not None else len(doc) - 1

    for pno in range(s.page, last_page + 1):
        page = doc[pno]
        top = 40.0
        bottom = float(page.rect.height) - 20.0
        left = 18.0
        right = float(page.rect.width) - 18.0

        if pno == s.page:
            top = max(30.0, s.y - 8.0)
        if n is not None and pno == n.page:
            bottom = min(bottom, n.y - 2.0)
        if bottom <= top + 15.0:
            continue

        clip = fitz.Rect(left, top, right, bottom)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        if s.page == last_page:
            out_file = out_prefix.with_suffix(".png")
        else:
            out_file = out_prefix.parent / f"{out_prefix.name}_p{pno - s.page + 1}.png"
        pix.save(str(out_file))
        rel = out_file.relative_to(ROOT / "data" / "tutoring" / "processed").as_posix()
        image_paths.append(rel)
    return image_paths


def normalize_for_match(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def question_key(question_text: str, qnum: int) -> str:
    text = question_text
    text = re.sub(rf"^\s*{qnum}\.\s*", "", text)
    text = re.sub(r"\(total\s+\d+\s+marks?\)", "", text, flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return ""
    return normalize_for_match(" ".join(words[:12]))


def fallback_page_image(doc: fitz.Document, question_text: str, qnum: int, out_prefix: Path) -> List[str]:
    key = question_key(question_text, qnum)
    if not key:
        return []

    best_page = None
    best_score = 0
    for pno in range(len(doc)):
        page_text = normalize_for_match(doc[pno].get_text("text"))
        if not page_text:
            continue
        score = 0
        if key in page_text:
            score += len(key)
        if str(qnum) in page_text:
            score += 3
        if score > best_score:
            best_score = score
            best_page = pno

    if best_page is None or best_score <= 3:
        return []

    page = doc[best_page]
    clip = fitz.Rect(18.0, 30.0, float(page.rect.width) - 18.0, float(page.rect.height) - 20.0)
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
    out_file = out_prefix.with_suffix(".png")
    pix.save(str(out_file))
    rel = out_file.relative_to(ROOT / "data" / "tutoring" / "processed").as_posix()
    return [rel]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = data.get("questions", [])

    docs: Dict[str, fitz.Document] = {}
    starts_map: Dict[str, List[StartPos]] = {}

    for q in questions:
        source_file = str(q.get("source_file", ""))
        if not source_file.lower().endswith(".pdf"):
            continue
        if source_file in docs:
            continue
        path = SOURCE_DIR / source_file
        if not path.exists():
            continue
        docs[source_file] = fitz.open(str(path))
        starts_map[source_file] = detect_starts(docs[source_file])

    for q in questions:
        source_file = str(q.get("source_file", ""))
        qid = str(q.get("id", ""))
        qnum = int(str(q.get("question_number", "0")) or "0")
        qtext = str(q.get("question_text", ""))
        q["question_image_paths"] = []
        if qnum <= 0 or source_file not in docs:
            continue
        out_prefix = OUT_DIR / qid
        paths = crop_question(docs[source_file], starts_map[source_file], qnum, out_prefix)
        if not paths:
            paths = fallback_page_image(docs[source_file], qtext, qnum, out_prefix)
        q["question_image_paths"] = paths

    for doc in docs.values():
        doc.close()

    QUESTIONS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Updated {QUESTIONS_JSON} with tutoring screenshot paths for {len(questions)} questions")


if __name__ == "__main__":
    main()
