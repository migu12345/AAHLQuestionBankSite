#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    import sys

    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

QUESTIONS_JSON = ROOT / "data" / "physics" / "processed" / "questions.json"
Q_IMG_DIR = ROOT / "data" / "physics" / "processed" / "images" / "questions"
REL_BASE = ROOT / "data" / "physics" / "processed"
PDF_ROOT = ROOT / "data" / "resources" / "physics"

# Heuristic: very short images are almost always clipped split artifacts.
MIN_REASONABLE_HEIGHT_PX = 320


@dataclass
class Pos:
    qnum: int
    page: int
    y: float
    x: float


def find_pdf_by_filename(filename: str) -> Optional[Path]:
    matches = list(PDF_ROOT.rglob(filename))
    if not matches:
        return None
    return matches[0]


def detect_question_positions(doc: fitz.Document) -> List[Pos]:
    first_by_q: Dict[int, Pos] = {}

    for pno in range(len(doc)):
        page = doc[pno]
        blocks = page.get_text("dict").get("blocks", [])
        pending_num: Optional[int] = None
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

                qn: Optional[int] = None
                m_inline = re.match(r"^(\d{1,2})\.\s+", text)
                m_dot = re.match(r"^(\d{1,2})\.$", text)
                m_plain = re.match(r"^(\d{1,2})$", text)
                m_marks = re.match(r"^(\d{1,2})\s+\[", text)

                if m_inline:
                    qn = int(m_inline.group(1))
                elif m_dot:
                    pending_num = int(m_dot.group(1))
                    pending_x = x
                    pending_y = y
                    qn = pending_num
                elif m_plain:
                    pending_num = int(m_plain.group(1))
                    pending_x = x
                    pending_y = y
                elif m_marks:
                    qn = int(m_marks.group(1))
                elif pending_num is not None and re.match(r"^(?:\(|[A-Za-z])", text) and abs(y - pending_y) <= 120:
                    qn = pending_num
                    x = pending_x
                    y = pending_y
                    pending_num = None

                if qn is None or not (1 <= qn <= 60):
                    continue
                if y > 220:
                    # Start markers are near top/upper-middle of page; deeper matches are often graph labels.
                    continue
                if qn in first_by_q:
                    continue
                if x <= 140:
                    first_by_q[qn] = Pos(qnum=qn, page=pno, y=y, x=x)

    return sorted(first_by_q.values(), key=lambda p: (p.page, p.y, p.x))


def blank_answer_page(page: fitz.Page, clip: fitz.Rect) -> bool:
    text = page.get_text("text", clip=clip).lower()
    if "please do not write on this page" in text:
        return True
    if "answers written on this page" in text and "will not be marked" in text:
        return True
    return False


def crop_question(doc: fitz.Document, positions: List[Pos], qnum: int, out_base: Path) -> List[str]:
    idx = next((i for i, p in enumerate(positions) if p.qnum == qnum), None)
    if idx is None:
        return []
    cur = positions[idx]
    nxt = positions[idx + 1] if idx + 1 < len(positions) else None
    last_page = nxt.page if nxt else len(doc) - 1

    # Remove old outputs before rewriting.
    for old in out_base.parent.glob(f"{out_base.name}*.png"):
        old.unlink(missing_ok=True)

    written: List[str] = []
    for pno in range(cur.page, last_page + 1):
        page = doc[pno]
        left, right = 18.0, float(page.rect.width) - 18.0
        top = 42.0
        bottom = float(page.rect.height) - 18.0
        if pno == cur.page:
            # More generous top padding prevents clipped first text lines.
            top = max(24.0, cur.y - 22.0)
        if nxt is not None and pno == nxt.page:
            # Guard against false "next question" hits in mid/lower page
            # (for example diagram labels or in-question numbering).
            # IB question starts are expected near page top.
            if nxt.y <= page.rect.height * 0.35:
                bottom = min(bottom, nxt.y - 2.0)
        # If the "end at next question start" on this page leaves only a tiny strip,
        # skip this page instead of expanding into the next question content.
        if nxt is not None and pno == nxt.page and bottom <= top + 80.0:
            continue
        # Otherwise, for genuine tiny first-page crops, expand to include enough content.
        if bottom <= top + 80.0:
            bottom = min(float(page.rect.height) - 18.0, top + 720.0)
        if bottom <= top + 40.0:
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
        written.append(out_file.relative_to(REL_BASE).as_posix())
    return written


def has_clipped_image(rel_paths: List[str]) -> bool:
    if not rel_paths:
        return True
    for rel in rel_paths:
        p = REL_BASE / rel
        if not p.exists():
            return True
        pix = fitz.Pixmap(str(p))
        if pix.height < MIN_REASONABLE_HEIGHT_PX:
            return True
    return False


def main() -> None:
    payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions: List[dict] = payload.get("questions", [])

    grouped: Dict[str, List[dict]] = {}
    for q in questions:
        paper_file = (q.get("source") or {}).get("paper_file", "")
        if not paper_file:
            continue
        grouped.setdefault(paper_file, []).append(q)

    fixed = 0
    scanned = 0
    removed = 0
    remove_ids: set[str] = set()

    for paper_file, rows in grouped.items():
        # Rebuild all Paper 1B crops (they are most sensitive to continuation-page clipping),
        # and also any other rows detected as clipped.
        to_fix = [
            q
            for q in rows
            if str(q.get("paper_type", "")).strip() == "Paper 1B"
            or has_clipped_image(list(q.get("question_image_paths") or []))
        ]
        if not to_fix:
            continue
        pdf_path = find_pdf_by_filename(paper_file)
        if not pdf_path or not pdf_path.exists():
            continue
        doc = fitz.open(pdf_path)
        positions = detect_question_positions(doc)
        detected_qnums = {p.qnum for p in positions}

        # Cleanup stale/invalid Paper 1B rows created by earlier false split detection.
        for q in rows:
            if str(q.get("paper_type", "")).strip() != "Paper 1B":
                continue
            qid = str(q.get("id", "")).strip()
            qnum = int(str(q.get("question_number", "0")) or 0)
            if not qid or qnum <= 0:
                continue
            if qnum not in detected_qnums:
                remove_ids.add(qid)
                for old in Q_IMG_DIR.glob(f"{qid}*.png"):
                    old.unlink(missing_ok=True)
                removed += 1

        for q in to_fix:
            scanned += 1
            qid = str(q.get("id", "")).strip()
            qnum = int(str(q.get("question_number", "0")) or 0)
            if qid in remove_ids:
                continue
            if not qid or qnum <= 0:
                continue
            out_base = Q_IMG_DIR / qid
            rels = crop_question(doc, positions, qnum, out_base)
            if rels:
                q["question_image_paths"] = rels
                q["question_images"] = rels
                fixed += 1
        doc.close()

    if remove_ids:
        payload["questions"] = [q for q in questions if str(q.get("id", "")).strip() not in remove_ids]

    QUESTIONS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Scanned clipped candidates: {scanned}")
    print(f"Fixed question image sets: {fixed}")
    print(f"Removed stale question rows: {removed}")


if __name__ == "__main__":
    main()
