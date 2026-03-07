#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import re
from pathlib import Path
from typing import Dict, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

QUESTIONS_JSON = ROOT / "data" / "physics" / "processed" / "questions.json"
PHYSICS_PDF_ROOT = ROOT / "data" / "resources" / "physics"
MS_IMG_DIR = ROOT / "data" / "physics" / "processed" / "images" / "markschemes" / "shared"
REL_BASE = ROOT / "data" / "physics" / "processed"


def find_pdf(name: str) -> Path | None:
    hits = list(PHYSICS_PDF_ROOT.rglob(name))
    return hits[0] if hits else None


def render_1a_key_image(ms_file: str) -> str | None:
    pdf_path = find_pdf(ms_file)
    if not pdf_path:
        return None
    doc = fitz.open(pdf_path)
    # 1A markschemes are 3 pages; the answer key is on page 3.
    page_index = 2 if len(doc) >= 3 else len(doc) - 1
    if page_index < 0:
        doc.close()
        return None
    page = doc[page_index]
    w = float(page.rect.width)
    h = float(page.rect.height)
    # Crop mostly the answer table area.
    clip = fitz.Rect(18.0, 48.0, w - 18.0, h - 20.0)
    pix = page.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), clip=clip, alpha=False)
    out_file = MS_IMG_DIR / f"{Path(ms_file).stem}_answers.png"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_file))
    doc.close()
    return out_file.relative_to(REL_BASE).as_posix()


def parse_1a_answer_map(ms_file: str) -> Dict[int, str]:
    pdf_path = find_pdf(ms_file)
    if not pdf_path:
        return {}
    doc = fitz.open(pdf_path)
    page_index = 2 if len(doc) >= 3 else len(doc) - 1
    if page_index < 0:
        doc.close()
        return {}
    text = doc[page_index].get_text("text")
    doc.close()

    tokens = [ln.strip() for ln in text.splitlines() if ln.strip()]
    answers: Dict[int, str] = {}
    i = 0
    while i < len(tokens) - 1:
        m = re.match(r"^(\d{1,2})\.$", tokens[i])
        if m:
            qn = int(m.group(1))
            nxt = tokens[i + 1].strip().upper()
            if nxt in {"A", "B", "C", "D"}:
                answers[qn] = nxt
            i += 2
            continue
        i += 1
    return answers


def main() -> None:
    payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    one_a = [q for q in questions if str(q.get("paper_type", "")).strip() == "Paper 1A"]
    files = sorted({(q.get("source") or {}).get("markscheme_file", "") for q in one_a if (q.get("source") or {}).get("markscheme_file", "")})

    ms_map: Dict[str, Tuple[str, Dict[int, str]]] = {}
    for ms_file in files:
        rel = render_1a_key_image(ms_file)
        ans = parse_1a_answer_map(ms_file)
        if rel:
            ms_map[ms_file] = (rel, ans)

    attached = 0
    for q in one_a:
        ms_file = (q.get("source") or {}).get("markscheme_file", "")
        mapped = ms_map.get(ms_file)
        if not mapped:
            continue
        rel, ans_map = mapped
        q["markscheme_image_paths"] = [rel]
        q["markscheme_images"] = [rel]
        q["has_markscheme"] = True
        qn = int(str(q.get("question_number", "0")) or 0)
        q["mcq_answer"] = ans_map.get(qn, "")
        attached += 1

    QUESTIONS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Attached 1A markscheme key image to {attached} questions")


if __name__ == "__main__":
    main()
