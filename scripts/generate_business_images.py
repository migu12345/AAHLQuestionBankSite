#!/usr/bin/env python3
"""Generate per-question screenshots for Business Management bank."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

QUESTIONS_JSON = ROOT / "data" / "business" / "processed" / "questions.json"
OUT_DIR = ROOT / "data" / "business" / "processed" / "images"
PAPERS_DIR = ROOT / "data" / "business" / "raw" / "papers"
MARKSCHEMES_DIR = ROOT / "data" / "business" / "raw" / "markschemes"


@dataclass
class StartPos:
    qnum: int
    page: int
    y: float


def cleaned_alpha_len(text: str) -> int:
    t = text.lower()
    t = re.sub(r"\bplease do not write on this page\b", " ", t)
    t = re.sub(r"\banswers written on this page will not be marked\b", " ", t)
    t = re.sub(r"\breferences\b", " ", t)
    t = re.sub(r"\binternational baccalaureate organization\b", " ", t)
    t = re.sub(r"\bturn over\b", " ", t)
    t = re.sub(r"[^a-z]+", "", t)
    return len(t)


def non_white_ratio(page: fitz.Page, clip: fitz.Rect) -> float:
    pix = page.get_pixmap(matrix=fitz.Matrix(0.4, 0.4), clip=clip, alpha=False)
    data = pix.samples
    if not data:
        return 0.0
    n = pix.n
    if n < 3:
        return 0.0

    non_white = 0
    total = pix.width * pix.height
    for i in range(0, len(data), n):
        if data[i] < 245 or data[i + 1] < 245 or data[i + 2] < 245:
            non_white += 1
    return non_white / max(1, total)


def is_mostly_blank_page(page: fitz.Page, clip: fitz.Rect, is_first_crop_page: bool) -> bool:
    if is_first_crop_page:
        return False
    text = page.get_text("text", clip=clip)
    alpha = cleaned_alpha_len(text)
    density = non_white_ratio(page, clip)

    if re.search(r"please do not write on this page", text, flags=re.IGNORECASE):
        return True
    if re.search(r"answers written on this page will not be marked", text, flags=re.IGNORECASE):
        return True
    if re.search(r"\breferences\b", text, flags=re.IGNORECASE) and alpha < 20:
        return True
    return alpha < 20 and density < 0.035


def is_answer_space_continuation_page(text: str) -> bool:
    t = text.lower()
    if not re.search(r"\bquestion\s+\d+\s+continued\b", t):
        return False

    if re.search(r"\[maximum mark:", t):
        return False
    if re.search(r"\(\s*[a-f]\s*\)", t):
        return False
    if re.search(r"\b(define|explain|analyse|evaluate|calculate|state|discuss|identify|recommend)\b", t):
        return False

    alpha = cleaned_alpha_len(text)
    replacement_chars = text.count("\ufffd") + text.count("�")
    return alpha < 60 or replacement_chars > 120


def detect_starts(doc: fitz.Document, kind: str) -> List[StartPos]:
    starts: Dict[int, Tuple[int, float]] = {}

    for pno in range(len(doc)):
        page = doc[pno]
        blocks = page.get_text("dict").get("blocks", [])
        pending_num: int | None = None
        pending_y: float | None = None

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
                qnum = None

                if kind == "paper":
                    m = re.match(r"^(\d{1,2})\.\s*\[Maximum mark:", line_text)
                    if m:
                        qnum = int(m.group(1))
                    else:
                        m0 = re.match(r"^(\d{1,2})\.$", line_text)
                        if m0:
                            pending_num = int(m0.group(1))
                            pending_y = y
                            qnum = pending_num
                        elif pending_num is not None and re.match(r"^\([a-z]\)", line_text, flags=re.IGNORECASE):
                            qnum = pending_num
                            y = pending_y if pending_y is not None else y
                            pending_num = None
                            pending_y = None
                else:
                    m = re.match(r"^(\d{1,2})\.(?:\s|$)", line_text)
                    if not m:
                        m = re.match(r"^(\d{1,2})\s+\(", line_text)
                    if m:
                        qnum = int(m.group(1))

                if qnum is not None and qnum not in starts:
                    if qnum < 1 or qnum > 40:
                        continue
                    if kind == "markscheme" and x > 100.0:
                        continue
                    starts[qnum] = (pno, y)

    out = [StartPos(qnum=q, page=pg, y=y) for q, (pg, y) in starts.items()]
    out.sort(key=lambda s: (s.page, s.y))
    return out


def crop_question(
    doc: fitz.Document,
    starts: List[StartPos],
    qnum: int,
    out_prefix: Path,
    kind: str,
) -> List[str]:
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
        top = 48.0
        bottom = float(page.rect.height) - 24.0
        left = 24.0
        right = float(page.rect.width) - 24.0

        if kind == "markscheme":
            top = 42.0
            bottom = float(page.rect.height) - 16.0
            left = 10.0
            right = float(page.rect.width) - 10.0

        if pno == s.page:
            top = max(34.0, s.y - 8.0)
        if n is not None and pno == n.page:
            bottom = min(bottom, n.y - 2.0)

        if bottom <= top + 15.0:
            continue

        clip = fitz.Rect(left, top, right, bottom)
        clip_text = page.get_text("text", clip=clip)

        if kind == "paper" and is_answer_space_continuation_page(clip_text):
            continue

        if is_mostly_blank_page(page, clip, pno == s.page):
            continue

        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        if s.page == last_page:
            out_file = out_prefix.with_suffix(".png")
        else:
            out_file = out_prefix.parent / f"{out_prefix.name}_p{pno - s.page + 1}.png"
        pix.save(str(out_file))
        rel = out_file.relative_to(ROOT / "data" / "business" / "processed").as_posix()
        image_paths.append(rel)

    return image_paths


def ensure_dirs() -> None:
    (OUT_DIR / "questions").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "markschemes").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "case_studies").mkdir(parents=True, exist_ok=True)


def render_case_study_doc(doc: fitz.Document, out_prefix: Path) -> List[str]:
    image_paths: List[str] = []
    for pno in range(len(doc)):
        page = doc[pno]
        clip = fitz.Rect(18.0, 18.0, float(page.rect.width) - 18.0, float(page.rect.height) - 18.0)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        out_file = out_prefix.parent / f"{out_prefix.name}_p{pno + 1}.png"
        pix.save(str(out_file))
        rel = out_file.relative_to(ROOT / "data" / "business" / "processed").as_posix()
        image_paths.append(rel)
    return image_paths


def main() -> None:
    ensure_dirs()

    data = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = data.get("questions", [])

    paper_docs: Dict[str, fitz.Document] = {}
    ms_docs: Dict[str, fitz.Document] = {}
    paper_starts: Dict[str, List[StartPos]] = {}
    ms_starts: Dict[str, List[StartPos]] = {}
    case_doc_cache: Dict[str, List[str]] = {}

    for q in questions:
        source = q.get("source", {})
        paper_file = source.get("paper_file")
        ms_file = source.get("markscheme_file")

        if paper_file and paper_file not in paper_docs:
            p_path = PAPERS_DIR / paper_file
            paper_docs[paper_file] = fitz.open(str(p_path))
            paper_starts[paper_file] = detect_starts(paper_docs[paper_file], "paper")

        if ms_file and ms_file not in ms_docs:
            m_path = MARKSCHEMES_DIR / ms_file
            ms_docs[ms_file] = fitz.open(str(m_path))
            ms_starts[ms_file] = detect_starts(ms_docs[ms_file], "markscheme")

    for q in questions:
        qnum = int(q.get("question_number", 0))
        qid = q.get("id", f"q{qnum}")
        source = q.get("source", {})
        paper_file = source.get("paper_file")
        ms_file = source.get("markscheme_file")

        q_imgs: List[str] = []
        a_imgs: List[str] = []

        if paper_file in paper_docs:
            out_prefix = OUT_DIR / "questions" / qid
            q_imgs = crop_question(
                paper_docs[paper_file],
                paper_starts.get(paper_file, []),
                qnum,
                out_prefix,
                "paper",
            )

        if ms_file in ms_docs:
            out_prefix = OUT_DIR / "markschemes" / qid
            a_imgs = crop_question(
                ms_docs[ms_file],
                ms_starts.get(ms_file, []),
                qnum,
                out_prefix,
                "markscheme",
            )

        q["question_image_paths"] = q_imgs
        q["markscheme_image_paths"] = a_imgs
        q["case_study_image_paths"] = []

        case_file = q.get("case_study_file")
        if isinstance(case_file, str) and case_file:
            if case_file not in case_doc_cache:
                case_path = PAPERS_DIR / case_file
                if case_path.exists():
                    case_doc = fitz.open(str(case_path))
                    out_prefix = OUT_DIR / "case_studies" / Path(case_file).stem
                    case_doc_cache[case_file] = render_case_study_doc(case_doc, out_prefix)
                    case_doc.close()
                else:
                    case_doc_cache[case_file] = []
            q["case_study_image_paths"] = case_doc_cache.get(case_file, [])

    for d in paper_docs.values():
        d.close()
    for d in ms_docs.values():
        d.close()

    QUESTIONS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Updated {QUESTIONS_JSON} with image paths for {len(questions)} questions")


if __name__ == "__main__":
    main()
