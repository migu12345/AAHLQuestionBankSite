#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    import sys

    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

QUESTIONS_JSON = ROOT / "data" / "physics" / "processed" / "questions.json"
Q_IMG_DIR = ROOT / "data" / "physics" / "processed" / "images" / "questions"


@dataclass
class Pos:
    qnum: int
    page: int
    y: float
    x: float


def load_questions() -> dict:
    return json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))


def find_pdf_by_filename(filename: str) -> Path | None:
    matches = list((ROOT / "data" / "resources" / "physics").rglob(filename))
    if not matches:
        return None
    return matches[0]


def detect_question_positions(doc: fitz.Document) -> List[Pos]:
    """Detect likely question starts across pages. Allows two-column MCQ layout."""
    first_by_q: Dict[int, Pos] = {}

    for pno in range(len(doc)):
        page = doc[pno]
        blocks = page.get_text("dict").get("blocks", [])
        pending_num = None
        pending_x = 0.0
        pending_y = 0.0

        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(span.get("text", "") for span in spans).strip()
                if not text:
                    continue

                x = float(line.get("bbox", [0, 0, 0, 0])[0])
                y = float(line.get("bbox", [0, 0, 0, 0])[1])
                if x > page.rect.width * 0.72:
                    continue

                qn = None
                m = re.match(r"^(\d{1,2})[.)]\s+", text)
                if m:
                    qn = int(m.group(1))
                else:
                    m2 = re.match(r"^(\d{1,2})\s+\[", text)
                    if m2:
                        qn = int(m2.group(1))
                    else:
                        m3 = re.match(r"^(\d{1,2})$", text)
                        if m3:
                            pending_num = int(m3.group(1))
                            pending_x = x
                            pending_y = y
                        elif pending_num is not None and re.match(r"^(?:\(|[A-Za-z])", text):
                            qn = pending_num
                            x = pending_x
                            y = pending_y
                            pending_num = None

                if qn is None:
                    continue
                if not (1 <= qn <= 60):
                    continue
                if qn in first_by_q:
                    continue
                first_by_q[qn] = Pos(qnum=qn, page=pno, y=y, x=x)

    out = sorted(first_by_q.values(), key=lambda p: (p.page, p.y, p.x))
    return out


def blank_answer_page(page: fitz.Page, clip: fitz.Rect) -> bool:
    text = page.get_text("text", clip=clip).lower()
    return (
        "please do not write on this page" in text
        or ("answers written on this page" in text and "will not be marked" in text)
    )


def crop_from_positions(doc: fitz.Document, positions: List[Pos], qnum: int, out_base: Path) -> List[str]:
    idx = next((i for i, p in enumerate(positions) if p.qnum == qnum), None)
    if idx is None:
        return []
    cur = positions[idx]
    nxt = positions[idx + 1] if idx + 1 < len(positions) else None
    last_page = nxt.page if nxt else len(doc) - 1

    written: List[str] = []
    for pno in range(cur.page, last_page + 1):
        page = doc[pno]
        left, right = 18.0, float(page.rect.width) - 18.0
        top = 42.0
        bottom = float(page.rect.height) - 18.0
        if pno == cur.page:
            top = max(32.0, cur.y - 8.0)
        if nxt is not None and pno == nxt.page:
            bottom = min(bottom, nxt.y - 2.0)
        if bottom <= top + 40.0:
            bottom = min(float(page.rect.height) - 18.0, top + 700.0)
        if bottom <= top + 20.0:
            continue

        clip = fitz.Rect(left, top, right, bottom)
        if pno != cur.page and blank_answer_page(page, clip):
            continue

        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        if cur.page == last_page:
            out_file = out_base.with_suffix(".png")
        else:
            out_file = out_base.parent / f"{out_base.name}_p{pno - cur.page + 1}.png"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out_file))
        written.append(out_file.name)
    return written


def main() -> None:
    payload = load_questions()
    qs = payload.get("questions", [])
    missing = [q for q in qs if not (q.get("question_image_paths") or [])]
    if not missing:
        print("No missing images.")
        return

    by_paper: Dict[str, List[dict]] = {}
    for q in missing:
        paper_file = (q.get("source") or {}).get("paper_file", "")
        by_paper.setdefault(paper_file, []).append(q)

    fixed = 0
    dropped_ids = set()

    for paper_file, items in by_paper.items():
        pdf_path = find_pdf_by_filename(paper_file)
        if not pdf_path or not pdf_path.exists():
            continue
        doc = fitz.open(pdf_path)
        positions = detect_question_positions(doc)
        pos_qnums = {p.qnum for p in positions}

        for q in items:
            qnum = int(str(q.get("question_number", "0")) or 0)
            qid = q.get("id", "")
            out_base = Q_IMG_DIR / qid
            written = crop_from_positions(doc, positions, qnum, out_base)
            if written:
                fixed += 1
            elif qnum not in pos_qnums:
                # Likely false-positive question split; remove this record.
                dropped_ids.add(qid)
        doc.close()

    if dropped_ids:
        qs = [q for q in qs if q.get("id") not in dropped_ids]
        payload["questions"] = qs

    QUESTIONS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Fixed images for {fixed} missing questions")
    print(f"Dropped {len(dropped_ids)} invalid question rows")


if __name__ == "__main__":
    main()
