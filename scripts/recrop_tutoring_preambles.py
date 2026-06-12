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

# PDFs where source filename differs from the key in questions.json
PDF_ALIASES: Dict[str, str] = {
    "Math_SL_Functions_Equations_2023.pdf": "Math_SL_Functions_Equations_2023 (1).pdf",
}

# T-style PDFs: (supports_parts, max_pages, top_preamble_px, bottom_preamble_px, preamble_detect)
# max_pages=2 for short Paper-1/2 style PDFs to prevent overflow into other questions
# top_preamble_px: pixels above detected start to include (captures preamble above sub-part label).
# bottom_preamble_px: pixels before NEXT question's start where this question ends.
#   Must equal top_preamble so crops tile perfectly with no gaps and no bleeds.
# preamble_detect=True: use _find_preamble_start to precisely locate Q(n+1)'s preamble boundary,
#   fixing bleeds where Q(n+1)'s preamble sits above its detected label. Only for T-style PDFs
#   where questions have preambles (not P1/P2 style or non-T-style PDFs with inline format).
#
# Dense PDFs (min inter-Q gap < 80px): use top=bottom=10 — preamble text appears ≤6px above
#   detected start (just a marks label). 80px would bleed the previous question's content in.
# Sparse PDFs (all gaps ≥ 80px): keep top=bottom=80 — large preamble buffer is safe.
# Paper-1/2 style (T6-2P1, T6-2P2): top=5 — questions start directly, no above-label preamble.
T_STYLE: Dict[str, tuple] = {
    # Dense T-style (min gap < 80px) → top=bottom=10, preamble_detect=True
    "T6-1 T HL.pdf":               (True,  4, 10, 10, True),
    "T2-5 T (2).pdf":              (True,  3, 10, 10, True),
    "T2-6 T (1).pdf":              (True,  3, 10, 10, True),
    "Topic 6 Part 1 T SL.pdf":     (True,  4, 10, 10, True),
    "Topic 2 Part 1 T.pdf":        (True,  4, 10, 10, True),
    # Sparse T-style (all gaps ≥ 80px) → top=bottom=80, preamble_detect=True
    "Topic 3 Part 1 T (1).pdf":    (True,  4, 80, 80, True),
    # Dense T-style → top=bottom=10, preamble_detect=True
    "Topic 1 Part 1 T.pdf":        (True,  4, 10, 10, True),
    # Paper-1/2 style → top=5, preamble_detect=False (no preamble above question label)
    "T6-2P1 T.pdf":                (True,  2,  5,  5, False),
    "T6-2P2 T.pdf":                (True,  2,  5,  5, False),
    # Non-T-style PDFs: inline "N. text" format, no preamble above label → preamble_detect=False
    "Math_SL_Algebra.pdf":         (False, 3, 10, 10, False),
    "Math_SL_Calculus_Julius (1).pdf": (False, 3, 10, 10, False),
    "Math_SL_Circular_FunctionsTrigonometry.pdf": (False, 3, 10, 10, False),
    "Math_SL_Functions_Equations_2023.pdf": (False, 3, 10, 10, False),
    "Topic_6_Calculus.pdf":        (False, 3, 10, 10, False),
    "Binomila Theorem.pdf":        (False, 3, 10, 10, False),
    "Limits_derivatives (1).pdf":  (False, 3, 10, 10, False),
    "Math_SL_Algebra_Exp_Log.pdf": (False, 3, 10, 10, False),
    "Math_SL_Statistics_Probability_2022 (1).pdf": (False, 3, 10, 10, False),
    "Topic_1_1_Algebra_Sequences_Series.pdf": (False, 3, 10, 10, False),
    "Topic_1_2_Algebra_Exponents_Logarithms_2023.pdf": (False, 3, 10, 10, False),
    "Topic_1_3_Algebra_Counting_Principles (1).pdf": (False, 3, 10, 10, False),
    "Topic_1_4_Algebra_Mathematical_Induction.pdf": (False, 3, 10, 10, False),
    "Topic_1_5_Algebra_Complex_Numbers.pdf": (False, 3, 10, 10, False),
    "statistics (1).pdf":          (False, 3, 10, 10, False),
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
                    if m_pending and x < 50:
                        # Require left-margin position to avoid matching subscript/
                        # superscript digits inside math expressions (e.g. log₃27)
                        # which appear at larger x offsets (≥56px in T-style PDFs).
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


def _gap_based_top(page: fitz.Page, qnum: int, max_y: float) -> Tuple[Optional[float], bool]:
    """Compute a crop top based on where the previous question's content ends on this page.

    Returns:
      (gap_top, has_prev_content) tuple.
      has_prev_content=False means no previous question labels found — page starts fresh.
      gap_top=None means prev content found but no useful preamble close after the gap
        (caller should fall back to normal top_preamble buffer).
      gap_top=float means use this y as the crop top.

    Algorithm:
    1. Find the last sub/question label of a question ≠ qnum at y < max_y.
    2a. If a "(Total N marks)" marker appears after that label, use it as boundary_y
        (reliable end-of-question for topclass-format PDFs; avoids misidentifying
        internal paragraph gaps within a question as the question boundary).
    2b. Otherwise, scan forward from that label until the first vertical gap > 60px.
        boundary_y = last text line before that gap.
    3. candidate_top = boundary_y + 20  (clears any partial text line).
    4. Only return candidate_top if a text line appears within 50px after it
       (confirming genuine preamble content follows the boundary).
    """
    GAP_THRESHOLD = 60.0  # Raised from 30 to skip internal paragraph gaps within a question
    GAP_TOP_MARGIN = 20.0
    PREAMBLE_CHECK_WINDOW = 50.0

    lines: List[Tuple[float, str]] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            line_text = "".join(s.get("text", "") for s in spans).strip()
            y = float(line.get("bbox", [0, 0, 0, 0])[1])
            if line_text and y < max_y:
                lines.append((y, line_text))
    if not lines:
        return None, False
    lines.sort(key=lambda t: t[0])

    # Find last label of a different question
    last_prev_idx: Optional[int] = None
    for i, (y, text) in enumerate(lines):
        m = re.match(r"^(\d{1,2})[a-z]?\.$", text)
        if m and int(m.group(1)) != qnum:
            last_prev_idx = i
    if last_prev_idx is None:
        # No recognized "N." / "Na." label found — treat as fresh page.
        # The text above (if any) is assumed to be THIS question's own preamble,
        # not overflow from the previous question.  Returning has_prev_content=False
        # allows crop_question_from_top to set top=30 rather than preamble_top.
        return None, False

    # Check for "(Total N marks)" after the last prev-question label — it is
    # the definitive end-of-question marker in topclass-format PDFs, and must
    # take priority over gap-scanning which can stop at internal paragraph gaps.
    total_marks_re = re.compile(r"^\(Total\s+\d+\s+marks?\)", re.IGNORECASE)
    boundary_y = lines[last_prev_idx][0]
    found_total = False
    for i in range(last_prev_idx, len(lines)):
        y, text = lines[i]
        if total_marks_re.match(text):
            boundary_y = y
            found_total = True
            break

    if not found_total:
        # Fall back: walk forward from that label; stop at first gap > GAP_THRESHOLD
        prev_y = lines[last_prev_idx][0]
        boundary_y = prev_y
        for i in range(last_prev_idx + 1, len(lines)):
            y, _ = lines[i]
            if y - prev_y > GAP_THRESHOLD:
                break
            prev_y = y
            boundary_y = y

    candidate_top = max(30.0, boundary_y + GAP_TOP_MARGIN)

    # Only return candidate_top if there's a text line close after it,
    # confirming genuine preamble content follows the boundary.
    has_nearby_preamble = any(
        candidate_top <= y < candidate_top + PREAMBLE_CHECK_WINDOW
        for y, _ in lines
    )
    return (candidate_top if has_nearby_preamble else None), True


def _is_dotted_line(text: str) -> bool:
    """Return True if the line is mostly dots/dashes (answer-box filler)."""
    chars = text.replace(" ", "").replace("\t", "")
    if not chars:
        return True
    dot_chars = sum(1 for c in chars if c in ".·•…_–—-")
    return dot_chars / len(chars) >= 0.7


def _find_total_marks_bottom(
    page: fitz.Page,
    from_y: float,
    to_y: float,
) -> Optional[float]:
    """Scan page text in [from_y, to_y] for a '(Total N marks)' line.

    Returns the bottom y-coordinate (bbox[3]) of the last matching line,
    or None if no such line is found.  This line reliably marks the
    end of a question in non-T-style PDFs (Topic_6_Calculus.pdf,
    Math_SL_Calculus_Julius, etc.) that use the '(Total N marks)' footer.
    """
    total_re = re.compile(r"^\(Total\s+\d+\s+marks?\)", re.IGNORECASE)
    best_y1: Optional[float] = None
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not total_re.match(text):
                continue
            y0 = float(line.get("bbox", [0, 0, 0, 0])[1])
            y1 = float(line.get("bbox", [0, 0, 0, 0])[3])
            if y0 < from_y or y0 > to_y:
                continue
            if best_y1 is None or y0 > (best_y1 - 20):
                best_y1 = y1
    return best_y1


def _find_preamble_start_for_bottom(
    page: fitz.Page,
    qnum: int,
    cur_y: float,
    next_y: float,
    small_gap: float = 20.0,
    large_gap: float = 60.0,
) -> Optional[float]:
    """Find the y-coordinate where Q(n+1)'s preamble starts, for use as Q(n)'s bottom crop.

    This is a bottom-boundary variant of _find_preamble_start that handles questions
    containing diagrams. When no sub-part labels of qnum are found in the range, it
    distinguishes between:

      • Large gaps (≥ large_gap px): interior diagram gaps within Q(n)'s content —
        these are skipped; the scan continues past them.
      • Small gaps (small_gap..large_gap px): Q(n)-to-Q(n+1) preamble transitions —
        these are returned as the preamble boundary.

    When sub-part labels of qnum ARE found (the normal T-style case), the standard
    20 px threshold from the last label is used exactly as in _find_preamble_start,
    because sub-part labels anchor the scan past diagram gaps.
    """
    raw: List[Tuple[float, float, str]] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            y0 = float(line.get("bbox", [0, 0, 0, 0])[1])
            y1 = float(line.get("bbox", [0, 0, 0, 0])[3])
            if y0 > cur_y and y0 < next_y:
                raw.append((y0, y1, text))
    if not raw:
        return None

    raw.sort()
    lines = [(y0, y1, t) for y0, y1, t in raw if not _is_dotted_line(t)]
    if not lines:
        return None

    def _is_qnum_label(text: str) -> bool:
        m = re.match(r"^(\d{1,2})[a-z]?\.$", text)
        if m and int(m.group(1)) == qnum:
            return True
        m2 = re.match(r"^(\d{1,2})[a-z]\.\s", text)
        if m2 and int(m2.group(1)) == qnum:
            return True
        m3 = re.match(r"^(\d{1,2})\.\s", text)
        if m3 and int(m3.group(1)) == qnum:
            return True
        return False

    last_label_idx: Optional[int] = None
    for i, (y0, y1, text) in enumerate(lines):
        if _is_qnum_label(text):
            last_label_idx = i

    if last_label_idx is not None:
        # Sub-part labels found: anchor scan from the last one with standard threshold.
        start_idx = last_label_idx
        prev_y1 = lines[start_idx][1]
        for y0, y1, text in lines[start_idx + 1:]:
            if _is_qnum_label(text):
                prev_y1 = y1
                continue
            if y0 - prev_y1 > small_gap:
                return y0
            prev_y1 = max(prev_y1, y1)
        return None

    # No sub-part labels: scan from start, skipping large (diagram) gaps.
    prev_y1 = lines[0][1]
    for y0, y1, text in lines[1:]:
        gap = y0 - prev_y1
        if large_gap > gap >= small_gap:
            # Small gap — this is the Q(n)-to-Q(n+1) preamble boundary.
            return y0
        if gap >= large_gap:
            # Large gap — diagram within Q(n); skip it and continue scanning.
            prev_y1 = y1
            continue
        prev_y1 = max(prev_y1, y1)
    return None


def _find_preamble_start(
    page: fitz.Page,
    qnum: int,
    cur_y: float,
    next_y: float,
    gap_threshold: float = 20.0,
) -> Optional[float]:
    """Find the y-coordinate where the NEXT question's preamble starts.

    Searches text in (cur_y, next_y), filtering out answer-box dot lines,
    then walks forward from Q(qnum)'s last sub-part label (skipping additional
    sub-part labels of qnum), returning the y where the gap exceeds gap_threshold.
    """
    raw: List[Tuple[float, float, str]] = []
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            y0 = float(line.get("bbox", [0, 0, 0, 0])[1])
            y1 = float(line.get("bbox", [0, 0, 0, 0])[3])
            if y0 > cur_y and y0 < next_y:
                raw.append((y0, y1, text))
    if not raw:
        return None

    raw.sort()
    lines = [(y0, y1, t) for y0, y1, t in raw if not _is_dotted_line(t)]
    if not lines:
        return None

    def _is_qnum_label(text: str) -> bool:
        """Return True if text is any form of sub-part label for qnum."""
        # Standalone label: "1a.", "1b.", "14."
        m = re.match(r"^(\d{1,2})[a-z]?\.$", text)
        if m and int(m.group(1)) == qnum:
            return True
        # Inline label with alpha sub-part: "1c. Find the value..."
        m2 = re.match(r"^(\d{1,2})[a-z]\.\s", text)
        if m2 and int(m2.group(1)) == qnum:
            return True
        # Inline label without alpha: "6. Let f(x)=..." or "14. Solve..."
        m3 = re.match(r"^(\d{1,2})\.\s", text)
        if m3 and int(m3.group(1)) == qnum:
            return True
        return False

    # Find last sub-part label of qnum (any format)
    last_label_idx: Optional[int] = None
    for i, (y0, y1, text) in enumerate(lines):
        if _is_qnum_label(text):
            last_label_idx = i

    start_idx = last_label_idx if last_label_idx is not None else 0
    prev_y1 = lines[start_idx][1]
    for y0, y1, text in lines[start_idx + 1:]:
        if _is_qnum_label(text):
            # Another sub-part or continuation label of qnum: advance position
            prev_y1 = y1
            continue
        if y0 - prev_y1 > gap_threshold:
            return y0
        prev_y1 = max(prev_y1, y1)
    return None


def crop_question_from_top(
    doc: fitz.Document,
    starts: List[StartPos],
    qnum: int,
    out_prefix: Path,
    max_pages: int = 99,
    top_preamble: float = 80.0,
    bottom_preamble: float = 80.0,
    preamble_detect: bool = False,
) -> List[str]:
    """Crop question image. top_preamble px above detected start; bottom_preamble px before next start.

    preamble_detect=True activates preamble-aware boundary logic for T-style PDFs where
    Q(n+1)'s preamble appears above its detected label: uses _find_preamble_start to set
    both Q(n)'s bottom and Q(n+1)'s top, preventing the preamble from appearing in the
    wrong question's image.
    """
    start_idx = next((i for i, s in enumerate(starts) if s.qnum == qnum), None)
    if start_idx is None:
        return []
    s = starts[start_idx]
    n = starts[start_idx + 1] if start_idx + 1 < len(starts) else None
    last_page = min(n.page if n is not None else len(doc) - 1, s.page + max_pages - 1)
    image_paths: List[str] = []

    for pno in range(s.page, last_page + 1):
        page = doc[pno]
        top = 40.0
        bottom = float(page.rect.height) - 20.0
        left = 18.0
        right = float(page.rect.width) - 18.0
        if pno == s.page:
            prev_on_same_page = (start_idx > 0 and starts[start_idx - 1].page == s.page)
            preamble_top = max(30.0, s.y - top_preamble)

            if preamble_detect and prev_on_same_page:
                # T-style PDF, prev Q on same page: _find_preamble_start is primary
                # (handles answer-box gaps and densely-packed questions); fall back to
                # _gap_based_top only when _find_preamble_start finds nothing.
                prev_s = starts[start_idx - 1]
                preamble_y = _find_preamble_start(page, prev_s.qnum, prev_s.y, s.y)
                if preamble_y is not None:
                    top = max(30.0, preamble_y - 5.0)
                else:
                    gap_top, _ = _gap_based_top(page, s.qnum, s.y)
                    top = gap_top if gap_top is not None else preamble_top
            elif preamble_detect:
                # T-style PDF, prev Q on different page: gap-based detection.
                # _gap_based_top recognises T-style "Na." standalone labels.
                gap_top, has_overflow = _gap_based_top(page, s.qnum, s.y)
                if not prev_on_same_page and not has_overflow:
                    # No recognised overflow labels → page starts fresh.
                    top = 30.0
                elif gap_top is not None:
                    top = gap_top
                elif has_overflow and not prev_on_same_page and start_idx > 0:
                    # Prev Q's "Na." labels are on this page but _gap_based_top found
                    # no clear preamble boundary (e.g. a graph image blocks text).
                    # Scan from page top.
                    prev_s = starts[start_idx - 1]
                    preamble_y = _find_preamble_start(page, prev_s.qnum, 0, s.y)
                    top = max(30.0, preamble_y - 5.0) if preamble_y is not None else preamble_top
                else:
                    top = preamble_top
            else:
                # Non-T-style (topclass "N. text" inline format).
                # _gap_based_top does not work here: inline "N. text" labels are not
                # recognised as prev-Q boundaries, so gap detection misidentifies the
                # crop top.  Always use the simple preamble buffer (s.y − 10).
                top = preamble_top
        if n is not None and pno == n.page:
            # Try (Total N marks) as the authoritative end-of-question marker.
            # Clamp to n.y (not n.y+50) to avoid picking up Q(n+1)'s own
            # "(Total M marks)" line when the next question is very short.
            total_bottom = _find_total_marks_bottom(page, from_y=top, to_y=n.y)
            if total_bottom is not None and total_bottom > top + 20.0:
                bottom = min(bottom, total_bottom + 25)
            elif preamble_detect:
                # (Total N marks) not found — T-style PDF with [N marks] at start.
                # Use _find_preamble_start_for_bottom which skips large diagram gaps
                # within Q(n) and finds only the small gap that marks the start of
                # Q(n+1)'s preamble.
                preamble_y = _find_preamble_start_for_bottom(page, s.qnum, s.y, n.y)
                ideal = n.y - bottom_preamble
                fallback = ideal if ideal > top + 20.0 else n.y - 5.0
                if preamble_y is not None and preamble_y - 5.0 > top + 20.0:
                    bottom = min(bottom, preamble_y - 5.0)
                else:
                    bottom = min(bottom, fallback)
            else:
                ideal = n.y - bottom_preamble
                # Fall back to n.y - 5 if ideal would leave less than 20px of content
                bottom = min(bottom, ideal if ideal > top + 20.0 else n.y - 5.0)
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

    for filename, (supports_parts, max_pages, top_preamble, bottom_preamble, preamble_detect) in sorted(T_STYLE.items()):
        actual_name = PDF_ALIASES.get(filename, filename)
        pdf_path = PDF_DIR / actual_name
        if not pdf_path.exists():
            print(f"SKIP (not found): {filename} (looked for {actual_name})")
            continue
        if filename not in by_file:
            print(f"SKIP (no questions): {filename}")
            continue

        print(f"\n{filename} ({len(by_file[filename])} questions, max {max_pages} pages, top={top_preamble}px bot={bottom_preamble}px preamble_detect={preamble_detect})...")
        doc = fitz.open(str(pdf_path))
        starts = detect_starts(doc, supports_parts=supports_parts)
        print(f"  Detected {len(starts)} starts")

        changed = 0
        for entry in sorted(by_file[filename], key=lambda q: int(q.get("question_number", 0))):
            qnum = int(entry.get("question_number", 0))
            qid = entry["id"]
            out_prefix = IMAGES_Q_DIR / qid
            new_paths = crop_question_from_top(
                doc, starts, qnum, out_prefix,
                max_pages=max_pages,
                top_preamble=top_preamble,
                bottom_preamble=bottom_preamble,
                preamble_detect=preamble_detect,
            )
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
