#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

QUESTIONS_JSON = ROOT / "data" / "physics" / "processed" / "questions.json"
MS_IMG_DIR = ROOT / "data" / "physics" / "processed" / "images" / "markschemes"
PHYSICS_PDF_ROOT = ROOT / "data" / "resources" / "physics"
REL_BASE = ROOT / "data" / "physics" / "processed"


@dataclass
class StartPos:
    qnum: int
    page: int
    y: float


def find_pdf(name: str) -> Optional[Path]:
    hits = list(PHYSICS_PDF_ROOT.rglob(name))
    return hits[0] if hits else None


def detect_ms_starts(doc: fitz.Document) -> List[StartPos]:
    starts: Dict[int, tuple[int, float]] = {}
    ms_data_start_page = 0
    for pno in range(len(doc)):
        text = (doc[pno].get_text("text") or "").lower()
        if (
            "section a" in text
            and "question" in text
            and "answers" in text
            and "total" in text
            and "subject details" not in text
            and "mark allocation" not in text
        ):
            ms_data_start_page = pno
            break
    if ms_data_start_page == 0:
        for pno in range(len(doc)):
            text = (doc[pno].get_text("text") or "").lower()
            if "question" in text and "answers" in text and "total" in text and "subject details" not in text:
                ms_data_start_page = pno
                break

    for pno in range(ms_data_start_page, len(doc)):
        page = doc[pno]
        h = float(page.rect.height)
        blocks = page.get_text("dict").get("blocks", [])
        pending: Optional[int] = None
        pending_y: Optional[float] = None
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
                x = float(line.get("bbox", [0, 0, 0, 0])[0])
                y = float(line.get("bbox", [0, 0, 0, 0])[1])
                if y < 55 or y > h - 75:
                    continue
                if x > 130:
                    continue

                qn = None
                m_num = re.match(r"^(\d{1,2})$", text)
                m_inline = re.match(r"^(\d{1,2})\s+[A-Za-z(]", text)
                if m_num:
                    pending = int(m_num.group(1))
                    pending_y = y
                    qn = pending
                elif m_inline:
                    qn = int(m_inline.group(1))
                elif pending is not None and re.match(r"^[a-z]\s*$", text, re.I):
                    qn = pending

                if qn is None or not (1 <= qn <= 60):
                    continue
                if qn not in starts:
                    starts[qn] = (pno, pending_y if pending_y is not None else y)

    out = [StartPos(qnum=q, page=pg, y=y) for q, (pg, y) in starts.items()]
    out.sort(key=lambda s: (s.page, s.y))
    return out


def crop_ms(doc: fitz.Document, starts: List[StartPos], qnum: int, out_base: Path) -> List[str]:
    idx = next((i for i, s in enumerate(starts) if s.qnum == qnum), None)
    if idx is None:
        return []
    cur = starts[idx]
    nxt = starts[idx + 1] if idx + 1 < len(starts) else None
    last_page = nxt.page if nxt else len(doc) - 1

    rels: List[str] = []
    for pno in range(cur.page, last_page + 1):
        page = doc[pno]
        w = float(page.rect.width)
        h = float(page.rect.height)
        top = 46.0
        bottom = h - 18.0
        if pno == cur.page:
            top = max(40.0, cur.y - 8.0)
        if nxt is not None and pno == nxt.page:
            bottom = min(bottom, nxt.y - 2.0)
        if bottom <= top + 70.0:
            continue

        clip = fitz.Rect(18.0, top, w - 18.0, bottom)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        if cur.page == last_page:
            out_file = out_base.with_suffix(".png")
        else:
            out_file = out_base.parent / f"{out_base.name}_p{pno - cur.page + 1}.png"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out_file))
        rels.append(out_file.relative_to(REL_BASE).as_posix())
    return rels


def render_shared_ms_pages(doc: fitz.Document, ms_file: str) -> List[str]:
    stem = Path(ms_file).stem
    out_rels: List[str] = []
    for pno in range(len(doc)):
        page = doc[pno]
        text = page.get_text("text").lower()
        if pno <= 1:
            continue
        if "subject details" in text or "mark allocation" in text:
            continue
        if "question" not in text and "answers" not in text:
            continue
        out_file = MS_IMG_DIR / "shared" / f"{stem}_p{pno+1}.png"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
        pix.save(str(out_file))
        out_rels.append(out_file.relative_to(REL_BASE).as_posix())
    return out_rels


def main() -> None:
    payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    by_ms_file: Dict[str, List[dict]] = {}
    for q in questions:
        ms_file = (q.get("source") or {}).get("markscheme_file", "")
        if not ms_file:
            continue
        by_ms_file.setdefault(ms_file, []).append(q)

    total_attached = 0
    for ms_file, rows in by_ms_file.items():
        pdf = find_pdf(ms_file)
        if not pdf:
            continue
        doc = fitz.open(pdf)
        starts = detect_ms_starts(doc)
        shared_pages = render_shared_ms_pages(doc, ms_file)
        if not starts:
            for q in rows:
                q["markscheme_image_paths"] = shared_pages
                q["markscheme_images"] = shared_pages
                q["has_markscheme"] = bool(shared_pages)
                if shared_pages:
                    total_attached += 1
            doc.close()
            continue

        for q in rows:
            qid = q.get("id", "")
            qn = int(str(q.get("question_number", "0")) or 0)
            for stale in MS_IMG_DIR.glob(f"{qid}*.png"):
                stale.unlink(missing_ok=True)
            rels = crop_ms(doc, starts, qn, MS_IMG_DIR / qid)
            if not rels:
                rels = shared_pages
            q["markscheme_image_paths"] = rels
            q["markscheme_images"] = rels
            q["has_markscheme"] = bool(rels)
            if rels:
                total_attached += 1
        doc.close()

    QUESTIONS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Attached markscheme images to {total_attached} questions")


if __name__ == "__main__":
    main()
