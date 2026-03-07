#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore


QUESTIONS_JSON = ROOT / "data" / "physics" / "processed" / "questions.json"
IMG_Q_DIR = ROOT / "data" / "physics" / "processed" / "images" / "questions"
PHYSICS_PDF_ROOT = ROOT / "data" / "resources" / "physics"
REL_BASE = ROOT / "data" / "physics" / "processed"


@dataclass
class Pos:
    qnum: int
    page: int
    y: float


def find_pdf(name: str) -> Path | None:
    matches = list(PHYSICS_PDF_ROOT.rglob(name))
    return matches[0] if matches else None


def text_lines(page: fitz.Page) -> List[tuple[float, float, str]]:
    out: List[tuple[float, float, str]] = []
    blocks = page.get_text("dict").get("blocks", [])
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            x0, y0, *_ = line.get("bbox", [0, 0, 0, 0])
            out.append((float(x0), float(y0), text))
    out.sort(key=lambda t: (t[1], t[0]))
    return out


def detect_starts_1a(doc: fitz.Document, expected_max: int) -> Dict[int, Pos]:
    starts: Dict[int, Pos] = {}
    for pno in range(len(doc)):
        page = doc[pno]
        h = float(page.rect.height)
        for x, y, text in text_lines(page):
            if x > 95:
                continue
            if y < 55 or y > h - 100:
                continue
            m = re.match(r"^(\d{1,2})\.\s*$", text)
            if not m:
                m = re.match(r"^(\d{1,2})\.\s+\S+", text)
            if not m:
                continue
            qn = int(m.group(1))
            if qn < 1 or qn > expected_max:
                continue
            if qn in starts:
                continue
            starts[qn] = Pos(qnum=qn, page=pno, y=y)
    return starts


def option_y(page: fitz.Page, top: float, bottom: float, label: str) -> float | None:
    patt = re.compile(rf"^{label}[.)]\s+")
    for x, y, text in text_lines(page):
        if y < top or y > bottom:
            continue
        if x > 180:
            continue
        if patt.match(text):
            return y
    return None


def crop_1a_question(doc: fitz.Document, starts: Dict[int, Pos], qn: int, out_file: Path) -> str | None:
    cur = starts.get(qn)
    if not cur:
        return None

    next_pos = None
    for nxt_q in range(qn + 1, 61):
        if nxt_q in starts:
            next_pos = starts[nxt_q]
            break

    page = doc[cur.page]
    w = float(page.rect.width)
    h = float(page.rect.height)

    top = max(36.0, cur.y - 18.0)
    bottom = h - 20.0
    if next_pos and next_pos.page == cur.page:
        bottom = min(bottom, next_pos.y - 6.0)

    # Keep complete MCQ options through D when visible.
    d_y = option_y(page, top, bottom, "D")
    if d_y is not None:
        bottom = min(h - 12.0, max(bottom, d_y + 95.0))

    if bottom <= top + 80:
        return None

    clip = fitz.Rect(16.0, top, w - 16.0, bottom)
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_file))
    return out_file.relative_to(REL_BASE).as_posix()


def expected_count(level: str) -> int:
    return 40 if level == "HL" else 25


def main() -> None:
    payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])
    q1a = [q for q in questions if str(q.get("paper_type", "")).strip() == "Paper 1A"]

    # Remove invalid 1A rows beyond expected count for level.
    keep: List[dict] = []
    removed_ids: List[str] = []
    for q in questions:
        if str(q.get("paper_type", "")).strip() != "Paper 1A":
            keep.append(q)
            continue
        lvl = str(q.get("level", "HL")).upper()
        qn = int(str(q.get("question_number", "0")) or 0)
        if 1 <= qn <= expected_count(lvl):
            keep.append(q)
        else:
            removed_ids.append(q.get("id", ""))
    questions = keep
    payload["questions"] = questions
    q1a = [q for q in questions if str(q.get("paper_type", "")).strip() == "Paper 1A"]
    by_paper: Dict[tuple[str, str], List[dict]] = {}
    for q in q1a:
        src = (q.get("source") or {}).get("paper_file", "")
        lvl = str(q.get("level", "HL")).upper()
        by_paper[(src, lvl)] = by_paper.get((src, lvl), []) + [q]

    rewritten = 0
    for (paper_file, lvl), items in by_paper.items():
        pdf = find_pdf(paper_file)
        if not pdf:
            continue
        doc = fitz.open(pdf)
        starts = detect_starts_1a(doc, expected_count(lvl))
        for q in items:
            qn = int(str(q.get("question_number", "0")) or 0)
            qid = q.get("id", "")
            out = IMG_Q_DIR / f"{qid}.png"
            # Remove stale multipage fragments from earlier splits.
            for stale in IMG_Q_DIR.glob(f"{qid}_p*.png"):
                stale.unlink(missing_ok=True)
            rel = crop_1a_question(doc, starts, qn, out)
            if rel:
                q["question_image_paths"] = [rel]
                q["question_images"] = [rel]
                rewritten += 1
            q["marks"] = 1
        doc.close()

    # Cleanup image files for dropped invalid rows.
    for qid in removed_ids:
        if not qid:
            continue
        for f in IMG_Q_DIR.glob(f"{qid}*.png"):
            f.unlink(missing_ok=True)

    QUESTIONS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rewrote {rewritten} Paper 1A question images")
    print(f"Removed {len(removed_ids)} invalid Paper 1A rows")


if __name__ == "__main__":
    main()
