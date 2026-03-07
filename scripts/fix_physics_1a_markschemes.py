#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict

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


def main() -> None:
    payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    one_a = [q for q in questions if str(q.get("paper_type", "")).strip() == "Paper 1A"]
    files = sorted({(q.get("source") or {}).get("markscheme_file", "") for q in one_a if (q.get("source") or {}).get("markscheme_file", "")})

    ms_map: Dict[str, str] = {}
    for ms_file in files:
        rel = render_1a_key_image(ms_file)
        if rel:
            ms_map[ms_file] = rel

    attached = 0
    for q in one_a:
        ms_file = (q.get("source") or {}).get("markscheme_file", "")
        rel = ms_map.get(ms_file)
        if not rel:
            continue
        q["markscheme_image_paths"] = [rel]
        q["markscheme_images"] = [rel]
        q["has_markscheme"] = True
        attached += 1

    QUESTIONS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Attached 1A markscheme key image to {attached} questions")


if __name__ == "__main__":
    main()

