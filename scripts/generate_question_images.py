#!/usr/bin/env python3
"""Generate per-question screenshots from papers and markschemes, then attach paths to questions.json."""

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

QUESTIONS_JSON = ROOT / "data" / "processed" / "questions.json"
OUT_DIR = ROOT / "data" / "processed" / "images"


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
    t = re.sub(r"\bm\d{2}/5/mathx/hp\d/eng(?:/tz\d)?/xx\b", " ", t)
    t = re.sub(r"[^a-z]+", "", t)
    return len(t)


def non_white_ratio(page: fitz.Page, clip: fitz.Rect) -> float:
    # Low-resolution sample to detect mostly blank continuation pages.
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


def is_mostly_blank_page(page: fitz.Page, clip: fitz.Rect, kind: str, is_first_crop_page: bool) -> bool:
    if is_first_crop_page:
        return False
    text = page.get_text("text", clip=clip)
    alpha = cleaned_alpha_len(text)
    density = non_white_ratio(page, clip)

    if re.search(r"please do not write on this page", text, flags=re.IGNORECASE):
        # These are IB answer-space filler pages; always exclude from question crops.
        return True
    if re.search(r"answers written on this page will not be marked", text, flags=re.IGNORECASE):
        return True
    if re.search(r"\breferences\b", text, flags=re.IGNORECASE) and alpha < 20:
        return True
    if kind == "paper":
        return alpha < 20 and density < 0.035
    return alpha < 15 and density < 0.03


def detect_starts(doc: fitz.Document, kind: str) -> List[StartPos]:
    starts: Dict[int, Tuple[int, float]] = {}
    start_page = 0
    if kind == "markscheme":
        # Skip examiner instructions pages; real question starts appear after "Section A".
        for pno in range(len(doc)):
            txt = doc[pno].get_text("text")
            if re.search(r"\bsection\s*a\b", txt, flags=re.IGNORECASE):
                start_page = pno
                break
    for pno in range(start_page, len(doc)):
        page = doc[pno]
        blocks = page.get_text("dict").get("blocks", [])
        prev_line = ""
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
                    prev_line = ""
                    continue

                y = float(line.get("bbox", [0, 0, 0, 0])[1])
                x = float(line.get("bbox", [0, 0, 0, 0])[0])
                qnum = None
                from_pending = False

                if kind == "paper":
                    m = re.match(r"^(\d{1,2})\.\s*\[Maximum mark:", line_text)
                    if m:
                        qnum = int(m.group(1))
                    else:
                        if re.match(r"^\[Maximum mark:", line_text) and pending_num is not None:
                            qnum = pending_num
                        m0 = re.match(r"^(\d{1,2})\.$", line_text)
                        if m0:
                            pending_num = int(m0.group(1))
                            pending_y = y
                            pending_x = x
                        m_split = re.match(r"^(\d)\.$", line_text)
                        p_split = re.match(r"^(\d)$", prev_line)
                        if m_split and p_split and int(m_split.group(1)) == int(p_split.group(1)):
                            pending_num = int(p_split.group(1) + m_split.group(1))
                            pending_y = y
                            pending_x = x
                        m2 = re.match(r"^(\d)\.\s*\[Maximum mark:", line_text)
                        p2 = re.match(r"^(\d)$", prev_line)
                        if m2 and p2 and int(m2.group(1)) == int(p2.group(1)):
                            qnum = int(p2.group(1) + m2.group(1))
                else:
                    if re.match(r"^\(\w+\)", line_text) and pending_num is not None:
                        qnum = pending_num
                        from_pending = True
                    if re.match(r"^METHOD\b", line_text, flags=re.IGNORECASE) and pending_num is not None:
                        qnum = pending_num
                        from_pending = True
                    if (
                        pending_num is not None
                        and pending_x is not None
                        and pending_x <= 65.0
                        and x <= 120.0
                        and re.match(r"^(?:EITHER\b|OR\b|THEN\b|[A-Za-z])", line_text, flags=re.IGNORECASE)
                    ):
                        qnum = pending_num
                        from_pending = True
                    # Standalone heading lines like "7" or "7." before content.
                    m0_dot = re.match(r"^(\d{1,2})\.$", line_text)
                    if m0_dot:
                        pending_num = int(m0_dot.group(1))
                        pending_y = y
                        pending_x = x
                        qnum = pending_num
                        from_pending = True
                    else:
                        m0_plain = re.match(r"^(\d{1,2})$", line_text)
                        if m0_plain:
                            pending_num = int(m0_plain.group(1))
                            pending_y = y
                            pending_x = x
                    # Only accept clear question headings; avoid "2 Method..." in instructions.
                    m = re.match(r"^(\d{1,2})\.\s+\S", line_text)
                    if not m:
                        m = re.match(r"^(\d{1,2})\.\s*\(", line_text)
                    if not m:
                        m = re.match(r"^(\d{1,2})\.\s*METHOD\b", line_text)
                    if not m:
                        m = re.match(r"^(\d{1,2})\s+\(", line_text)
                    if not m:
                        m = re.match(r"^(\d{1,2})\s+METHOD\b", line_text)
                    if not m:
                        m = re.match(r"^Question\s+(\d{1,2})\b", line_text, flags=re.IGNORECASE)
                    if m:
                        qnum = int(m.group(1))

                if qnum is not None and qnum not in starts:
                    if qnum < 1 or qnum > 12:
                        prev_line = line_text
                        continue
                    effective_x = pending_x if from_pending and pending_x is not None else x
                    if kind == "markscheme" and effective_x > 85.0:
                        prev_line = line_text
                        continue
                    starts[qnum] = (pno, pending_y if pending_y is not None else y)
                    pending_num = None
                    pending_y = None
                    pending_x = None

                prev_line = line_text

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

        # Markschemes need more generous crops to avoid clipping formulas/lines.
        if kind == "markscheme":
            top = 42.0
            bottom = float(page.rect.height) - 16.0
            left = 10.0
            right = float(page.rect.width) - 10.0

        if pno == s.page:
            top = max(34.0, s.y - 8.0)
        if n is not None and pno == n.page:
            # Keep content right up to the next heading without clipping tail lines.
            bottom = min(bottom, n.y - 2.0)

        if bottom <= top + 15.0:
            continue

        clip = fitz.Rect(left, top, right, bottom)
        if is_mostly_blank_page(page, clip, kind, pno == s.page):
            continue

        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        if s.page == last_page:
            out_file = out_prefix.with_suffix(".png")
        else:
            out_file = out_prefix.parent / f"{out_prefix.name}_p{pno - s.page + 1}.png"
        pix.save(str(out_file))
        rel = out_file.relative_to(ROOT / "data" / "processed").as_posix()
        image_paths.append(rel)

    return image_paths


def ensure_dirs() -> None:
    (OUT_DIR / "questions").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "markschemes").mkdir(parents=True, exist_ok=True)


def main() -> None:
    ensure_dirs()

    data = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = data.get("questions", [])

    paper_docs: Dict[str, fitz.Document] = {}
    ms_docs: Dict[str, fitz.Document] = {}
    paper_starts: Dict[str, List[StartPos]] = {}
    ms_starts: Dict[str, List[StartPos]] = {}

    for q in questions:
        source = q.get("source", {})
        paper_file = source.get("paper_file")
        ms_file = source.get("markscheme_file")

        if paper_file and paper_file not in paper_docs:
            p_path = ROOT / "data" / "raw" / "papers" / paper_file
            paper_docs[paper_file] = fitz.open(str(p_path))
            paper_starts[paper_file] = detect_starts(paper_docs[paper_file], "paper")

        if ms_file and ms_file not in ms_docs:
            m_path = ROOT / "data" / "raw" / "markschemes" / ms_file
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

    for d in paper_docs.values():
        d.close()
    for d in ms_docs.values():
        d.close()

    QUESTIONS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Updated {QUESTIONS_JSON} with image paths for {len(questions)} questions")


if __name__ == "__main__":
    main()
