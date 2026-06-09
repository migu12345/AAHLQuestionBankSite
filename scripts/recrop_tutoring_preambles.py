#!/usr/bin/env python3
"""
Re-crops question images for the T-style compilation PDFs in the tutoring bank.

Problem: The original crop used top = s.y - 8, cutting off the question preamble
(e.g. "y = xe^{3x}") that appears above the "Na." sub-part label.

Fix: crop the first page from y=32 (page top) so any preamble is always visible.
Only image files and question_image_paths in questions.json are updated.
markschemes.json is untouched.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

PDF_DIR = Path("/Users/s933863@aics.espritscholen.nl/Downloads/Math")
IMAGES_Q_DIR = ROOT / "data" / "tutoring" / "processed" / "images" / "questions"
QUESTIONS_JSON = ROOT / "data" / "tutoring" / "processed" / "questions.json"

# T-style PDFs with their supports_parts setting
T_STYLE: Dict[str, bool] = {
    "T6-1 T HL.pdf":               True,
    "T6-2P1 T.pdf":                True,
    "T6-2P2 T.pdf":                True,
    "Topic 6 Part 1 T SL.pdf":     True,
    "Topic 1 Part 1 T.pdf":        True,
    "Topic 2 Part 1 T.pdf":        True,
    "Topic 3 Part 1 T (1).pdf":    True,
    "T2-5 T (2).pdf":              True,
    "T2-6 T (1).pdf":              True,
}


@dataclass
class StartPos:
    qnum: int
    page: int
    y: float


def detect_starts(doc: fitz.Document, supports_parts: bool = False) -> List[StartPos]:
    """Exact copy of detect_starts from build_all_new_pdfs.py."""
    starts: Dict[int, Tuple[int, float]] = {}

    for pno in range(len(doc)):
        page = doc[pno]
        blocks = page.get_text("dict").get("blocks", [])
        pending_num: Optional[int] = None
        pending_y: Optional[float] = None
        pending_x: Optional[float] = None

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

                qnum: Optional[int] = None

                m = re.match(r"^(\d{1,2})\.\s+", line_text)
                if m:
                    qnum = int(m.group(1))

                if qnum is None and supports_parts:
                    m2 = re.match(r"^(\d{1,2})[a-z]?\.$", line_text)
                    if m2:
                        qnum = int(m2.group(1))

                if qnum is None:
                    m_dot = re.match(r"^(\d{1,2})\.$", line_text)
                    if m_dot:
                        pending_num = int(m_dot.group(1))
                        pending_y = y
                        pending_x = x
                        qnum = pending_num
                    m_pending = re.match(r"^(\d{1,2})$", line_text)
                    if m_pending:
                        pending_num = int(m_pending.group(1))
                        pending_y = y
                        pending_x = x
                        continue
                    if pending_num is not None:
                        if (pending_x is not None and pending_x < 80) and re.match(r"^[A-Za-z(\[]", line_text):
                            qnum = pending_num
                            y = pending_y if pending_y is not None else y
                        pending_num = None
                        pending_y = None
                        pending_x = None

                if qnum is None or qnum < 1 or qnum > 120:
                    continue
                if qnum in starts:
                    continue
                starts[qnum] = (pno, y)

    out = [StartPos(qnum=q, page=pg, y=y) for q, (pg, y) in starts.items()]
    out.sort(key=lambda s: (s.page, s.y))
    return out


def crop_question_from_top(
    doc: fitz.Document,
    starts: List[StartPos],
    qnum: int,
    out_prefix: Path,
) -> List[str]:
    """Crop with first-page top=32 to capture preamble."""
    start_idx = next((i for i, s in enumerate(starts) if s.qnum == qnum), None)
    if start_idx is None:
        return []
    s = starts[start_idx]
    n = starts[start_idx + 1] if start_idx + 1 < len(starts) else None
    last_page = n.page if n is not None else len(doc) - 1
    image_paths: List[str] = []

    for pno in range(s.page, last_page + 1):
        page = doc[pno]
        top = 40.0
        bottom = float(page.rect.height) - 20.0
        left = 18.0
        right = float(page.rect.width) - 18.0
        if pno == s.page:
            top = max(30.0, s.y - 80)  # 80px above detected start captures 2-3 lines of preamble
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
        out_file.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out_file))
        rel = out_file.relative_to(ROOT / "data" / "tutoring" / "processed").as_posix()
        image_paths.append(rel)

    return image_paths


def main() -> None:
    qs_data = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = qs_data["questions"]

    by_file: Dict[str, list] = {}
    for q in questions:
        sf = q.get("source_file", "")
        if sf in T_STYLE:
            by_file.setdefault(sf, []).append(q)

    total = 0

    for filename, supports_parts in sorted(T_STYLE.items()):
        pdf_path = PDF_DIR / filename
        if not pdf_path.exists():
            print(f"SKIP (not found): {filename}")
            continue
        if filename not in by_file:
            print(f"SKIP (no questions): {filename}")
            continue

        print(f"\n{filename} ({len(by_file[filename])} questions)...")
        doc = fitz.open(pdf_path)
        starts = detect_starts(doc, supports_parts=supports_parts)
        print(f"  Detected {len(starts)} starts")

        changed = 0
        for entry in sorted(by_file[filename], key=lambda q: int(q.get("question_number", 0))):
            qnum = int(entry.get("question_number", 0))
            qid = entry["id"]
            out_prefix = IMAGES_Q_DIR / qid
            new_paths = crop_question_from_top(doc, starts, qnum, out_prefix)
            if new_paths:
                entry["question_image_paths"] = new_paths
                changed += 1
            else:
                print(f"  WARNING: no image for {qid} (qnum={qnum})")

        doc.close()
        total += changed
        print(f"  Re-cropped {changed} questions")

    QUESTIONS_JSON.write_text(
        json.dumps(qs_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nDone. {total} questions re-cropped. markschemes.json untouched.")


if __name__ == "__main__":
    main()
