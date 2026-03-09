#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

QUESTIONS_JSON = ROOT / "data" / "physics" / "processed" / "questions.json"
MANUAL_PAPERS_JSON = ROOT / "data" / "physics" / "processed" / "manual_papers.json"
MS_IMG_DIR = ROOT / "data" / "physics" / "processed" / "images" / "markschemes"
PHYSICS_PDF_ROOT = ROOT / "data" / "resources" / "physics"
REL_BASE = ROOT / "data" / "physics" / "processed"


@dataclass
class StartPos:
    qnum: int
    page: int
    y: float


def load_manual_papers() -> Dict[str, str]:
    payload = json.loads(MANUAL_PAPERS_JSON.read_text(encoding="utf-8"))
    rows = payload.get("papers", []) if isinstance(payload, dict) else []
    out: Dict[str, str] = {}
    for r in rows:
        label = str(r.get("paperLabel", "")).strip()
        ms_rel = str(r.get("markscheme_path", "")).strip()
        if label and ms_rel:
            out[label] = ms_rel
    return out


def _to_qnum(value: object) -> int:
    s = str(value or "").strip()
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _find_ms_data_start_page(doc: fitz.Document) -> int:
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
    return ms_data_start_page


def detect_ms_starts(
    doc: fitz.Document,
    allowed_qnums: Iterable[int],
    *,
    prefer_top_table_for_p1b: bool = False,
) -> List[StartPos]:
    allowed = {q for q in allowed_qnums if 1 <= q <= 60}
    if not allowed:
        return []

    candidates: Dict[int, List[Tuple[int, float, int]]] = {q: [] for q in allowed}

    def add_candidate(qn: int, pno: int, y: float, score: int) -> None:
        if qn in candidates:
            candidates[qn].append((pno, y, score))

    for pno in range(len(doc)):
        page = doc[pno]
        page_text = page.get_text("text") or ""
        page_text_l = page_text.lower()
        has_table_header = (
            "question" in page_text_l
            and "answers" in page_text_l
            and "total" in page_text_l
            and "subject details" not in page_text_l
            and "mark allocation" not in page_text_l
        )
        is_rubric_page = any(
            phrase in page_text_l
            for phrase in (
                "each row in the",
                "maximum mark for each question subpart",
                "marking point",
                "alternative wording",
                "alternative answer",
                "alternative markscheme",
            )
        )

        # Heading fallback for layouts with explicit "Question X" labels.
        for m in re.finditer(r"(?im)^\s*question\s+(\d{1,2})\b", page_text):
            qn = int(m.group(1))
            if qn in allowed:
                add_candidate(qn, pno, 120.0, 6)

        # Text-line fallback for older table layouts where OCR loses precise
        # word coordinates for the question column (common in Paper 2).
        if has_table_header:
            lines = [ln.strip() for ln in page_text.splitlines() if ln.strip()]
            for i, ln in enumerate(lines[:-1]):
                if not re.fullmatch(r"\d{1,2}", ln):
                    continue
                if i > 40:
                    continue
                qn = int(ln)
                if qn not in allowed:
                    continue
                if prefer_top_table_for_p1b and i <= 12:
                    add_candidate(qn, pno, 120.0, 14)
                lookahead = lines[i + 1 : i + 5]
                has_subpart_a = any(re.fullmatch(r"a", nxt.lower()) for nxt in lookahead)
                has_total_then_subpart_a = (
                    len(lookahead) >= 2
                    and re.fullmatch(r"\d{1,2}", lookahead[0])
                    and re.fullmatch(r"a", lookahead[1].lower())
                )
                if has_subpart_a or has_total_then_subpart_a:
                    if prefer_top_table_for_p1b and i <= 20:
                        add_candidate(qn, pno, 120.0, 16)
                    add_candidate(qn, pno, 120.0, 8)

        # Table-row anchors: left "Question" column usually sits around x<=72, y~300-520.
        if has_table_header:
            words = page.get_text("words")
            for w in words:
                x0, y0, _x1, _y1, txt, *_ = w
                t = str(txt).strip()
                if not re.fullmatch(r"\d{1,2}\.?", t):
                    continue
                qn = int(t.rstrip("."))
                if qn not in allowed:
                    continue
                x = float(x0)
                y = float(y0)
                if prefer_top_table_for_p1b and x <= 90.0 and 120.0 <= y <= 360.0:
                    add_candidate(qn, pno, 120.0, 14)
                    continue
                # Many IB table layouts place the question number for each new
                # question near the lower-left of the page around x≈110,y≈780.
                # Treat this as a strong "new question starts on this page"
                # signal and anchor at a conservative top crop.
                if 95.0 <= x <= 130.0 and y >= 730.0:
                    add_candidate(qn, pno, 120.0, 15)
                    continue
                if x <= 72.0 and 280.0 <= y <= 540.0:
                    # Avoid page-number false positives: require a likely subpart
                    # letter on the same baseline to the right of the number.
                    line_tokens = [
                        str(v[4]).strip().lower()
                        for v in words
                        if abs(float(v[1]) - y) <= 2.0 and float(v[0]) > x and float(v[0]) <= x + 120.0
                    ]
                    if any(re.fullmatch(r"[a-e]", tok) for tok in line_tokens):
                        add_candidate(qn, pno, y, 10)
                elif 70.0 <= x <= 150.0 and y >= 730.0:
                    # Footer question indicator, conservative top anchor.
                    add_candidate(qn, pno, 120.0, 12)
        elif not is_rubric_page:
            # OCR on some old pages misses table headers completely.
            # Accept left-column numeric anchors unless this is clearly a rubric page.
            words = page.get_text("words")
            for w in words:
                x0, y0, _x1, _y1, txt, *_ = w
                t = str(txt).strip()
                if not re.fullmatch(r"\d{1,2}", t):
                    continue
                qn = int(t)
                if qn not in allowed:
                    continue
                x = float(x0)
                y = float(y0)
                if x <= 72.0 and 320.0 <= y <= 520.0:
                    line_tokens = [
                        str(v[4]).strip().lower()
                        for v in words
                        if abs(float(v[1]) - y) <= 2.0 and float(v[0]) > x and float(v[0]) <= x + 120.0
                    ]
                    if any(re.fullmatch(r"[a-e]", tok) for tok in line_tokens):
                        add_candidate(qn, pno, y, 7)

    starts: List[StartPos] = []
    for qn in sorted(allowed):
        cands = candidates.get(qn, [])
        if not cands:
            continue
        pno, y, _score = sorted(cands, key=lambda t: (-t[2], t[0], t[1]))[0]
        starts.append(StartPos(qnum=qn, page=pno, y=y))

    starts.sort(key=lambda s: (s.page, s.y, s.qnum))
    if prefer_top_table_for_p1b:
        starts = [StartPos(qnum=s.qnum, page=s.page, y=min(s.y, 120.0)) for s in starts]
    return starts


def crop_ms(
    doc: fitz.Document,
    starts: List[StartPos],
    qnum: int,
    out_base: Path,
    *,
    paper_type: str = "",
) -> List[str]:
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
            # Keep context above detected anchors so first rows are not clipped.
            # If anchor is already near top, start from the standard page margin.
            if cur.y <= 160.0:
                top = 46.0
            else:
                top = max(46.0, cur.y - 24.0)
        # Paper 1B rows often start very near page top in a compact table.
        # Treat the next-question page as belonging entirely to the next row
        # when its anchor is in the upper section to avoid cross-question bleed.
        if (
            paper_type == "paper 1b"
            and nxt is not None
            and pno == nxt.page
            and pno > cur.page
            and nxt.y <= 360.0
        ):
            continue
        if nxt is not None and pno == nxt.page and pno > cur.page and nxt.y <= 140.0:
            # When the next question clearly starts near page top, do not keep
            # a tiny sliver of this page for the current question.
            continue
        if nxt is not None and pno == nxt.page:
            bottom = min(bottom, nxt.y - 2.0)
        if bottom <= top + 90.0:
            continue

        clip = fitz.Rect(18.0, top, w - 18.0, bottom)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        # Guard against empty / whitespace-only crops when OCR anchors are weak.
        data = pix.samples
        comps = int(pix.n or 0)
        if comps >= 3 and pix.width > 0 and pix.height > 0:
            total = pix.width * pix.height
            step = max(1, total // 50000)
            white = 0
            checked = 0
            for i in range(0, total, step):
                base = i * comps
                r = data[base]
                g = data[base + 1]
                b = data[base + 2]
                if r > 245 and g > 245 and b > 245:
                    white += 1
                checked += 1
            if checked > 0 and (white / checked) > 0.998:
                continue
        if cur.page == last_page:
            out_file = out_base.with_suffix(".png")
        else:
            out_file = out_base.parent / f"{out_base.name}_p{pno - cur.page + 1}.png"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out_file))
        rels.append(out_file.relative_to(REL_BASE).as_posix())
    return rels


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild physics markscheme screenshots.")
    parser.add_argument(
        "--paper-label",
        action="append",
        default=[],
        help="Only rebuild this exact paper label (repeatable).",
    )
    parser.add_argument(
        "--paper-type",
        action="append",
        default=[],
        help="Only rebuild this exact paper type (repeatable), e.g. 'Paper 1B'.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    label_filter = {str(v).strip() for v in (args.paper_label or []) if str(v).strip()}
    paper_type_filter = {str(v).strip().lower() for v in (args.paper_type or []) if str(v).strip()}

    payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])
    manual_map = load_manual_papers()

    by_ms_path: Dict[str, List[dict]] = {}
    for q in questions:
        paper_label = str(q.get("paper", "")).strip()
        ms_rel = manual_map.get(paper_label, "")
        if not ms_rel:
            continue
        by_ms_path.setdefault(ms_rel, []).append(q)

    total_attached = 0
    for ms_rel, rows in by_ms_path.items():
        if not rows:
            continue
        if label_filter and not any(str(r.get("paper", "")).strip() in label_filter for r in rows):
            continue
        if paper_type_filter and not any(
            str(r.get("paper_type", "")).strip().lower() in paper_type_filter for r in rows
        ):
            continue

        paper1a_rows = [
            r
            for r in rows
            if str(r.get("paper_type", "")).strip().lower() in {"paper 1a", "paper 1"}
        ]
        rebuild_rows = [
            r
            for r in rows
            if str(r.get("paper_type", "")).strip().lower() in {"paper 2", "paper 1b", "paper 3"}
        ]
        if paper_type_filter:
            rebuild_rows = [
                r
                for r in rebuild_rows
                if str(r.get("paper_type", "")).strip().lower() in paper_type_filter
            ]

        # Paper 1A uses answer-key mapping; never label as "No markscheme" when
        # the MCQ answer text is present.
        for q in paper1a_rows:
            answer_text = str(q.get("answer_text") or "").strip()
            mcq_answer = str(q.get("mcq_answer") or "").strip()
            if not answer_text and mcq_answer:
                q["answer_text"] = f"Answer: {mcq_answer}"
                answer_text = str(q.get("answer_text") or "").strip()
            has_images = bool(q.get("markscheme_image_paths") or [])
            q["has_markscheme"] = bool(has_images or mcq_answer or answer_text)

        if not rebuild_rows:
            continue

        pdf = ROOT / "data" / ms_rel
        if not pdf:
            continue
        if not pdf.exists():
            continue
        doc = fitz.open(pdf)
        rebuild_types = {str(r.get("paper_type", "")).strip().lower() for r in rebuild_rows}
        prefer_top_table_for_p1b = rebuild_types == {"paper 1b"}
        starts = detect_ms_starts(doc, range(1, 61), prefer_top_table_for_p1b=prefer_top_table_for_p1b)
        if not starts:
            doc.close()
            continue

        for q in rebuild_rows:
            qid = q.get("id", "")
            qn = _to_qnum(q.get("question_number", "0"))
            qtype = str(q.get("paper_type", "")).strip().lower()
            old_rels = list(q.get("markscheme_image_paths") or [])
            rels = crop_ms(doc, starts, qn, MS_IMG_DIR / qid, paper_type=qtype) if qn > 0 else []
            if rels:
                for stale in MS_IMG_DIR.glob(f"{qid}*.png"):
                    stale.unlink(missing_ok=True)
                # Re-render after cleanup so only fresh files are referenced.
                rels = (
                    crop_ms(doc, starts, qn, MS_IMG_DIR / qid, paper_type=qtype) if qn > 0 else []
                )
            final_rels = rels if rels else old_rels
            q["markscheme_image_paths"] = final_rels
            q["markscheme_images"] = final_rels
            answer_text = str(q.get("answer_text") or "").strip()
            mcq_answer = str(q.get("mcq_answer") or "").strip()
            q["has_markscheme"] = bool(final_rels or answer_text or mcq_answer)
            if rels:
                total_attached += 1
        doc.close()

    QUESTIONS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Attached markscheme images to {total_attached} questions")


if __name__ == "__main__":
    main()
