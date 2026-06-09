#!/usr/bin/env python3
"""
Process all new Math PDFs from ~/Downloads/Math and add them to the tutoring question bank.

Handles two PDF formats:
  Format A (TopClassTutors):  "N. question text ... (Total N marks)"
  Format B (IB Questionbank): "[N marks]\n...\nNa.\ntext" or "[N marks]\nN.\ntext"

Run from project root:
    python3 scripts/tutoring/build_all_new_pdfs.py
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from textwrap import wrap
from typing import Dict, List, Optional, Tuple

import sys

ROOT = Path(__file__).resolve().parents[2]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz
from pypdf import PdfReader

MATH_DIR = Path("/Users/s933863@aics.espritscholen.nl/Downloads/Math")
QUESTIONS_JSON = ROOT / "data" / "tutoring" / "processed" / "questions.json"
MARKSCHEMES_JSON = ROOT / "data" / "tutoring" / "processed" / "markschemes.json"
IMAGES_Q_DIR = ROOT / "data" / "tutoring" / "processed" / "images" / "questions"
IMAGES_MS_DIR = ROOT / "data" / "tutoring" / "processed" / "images" / "markschemes"

# ─────────────────────────────────────────────────────────────────────────────
# PDF configuration — one entry per new PDF to process.
# (source_file, unit, topic, level, paper_type, format, id_prefix)
# format: "topclass" | "ib_qbank" | "ib_qbank_simple"
# ─────────────────────────────────────────────────────────────────────────────
PDF_CONFIGS = [
    # Topic 1 — new HL files
    ("Topic_1_1_Algebra_Sequences_Series.pdf",
     "Topic 1 Number and Algebra", "Number and Algebra", "HL", None, "topclass", "t1_seq"),
    ("Topic_1_3_Algebra_Counting_Principles (1).pdf",
     "Topic 1 Number and Algebra", "Number and Algebra", "HL", None, "topclass", "t1_cnt"),
    # Topic 1 — IB qbank style
    ("Topic 1 Part 1 T.pdf",
     "Topic 1 Number and Algebra", "Number and Algebra", "SL", None, "ib_qbank", "t1p1"),
    # Topic 2 — IB qbank style
    ("T2-5 T (2).pdf",
     "Topic 2 Functions", "Functions", "HL", None, "ib_qbank_simple", "t2_5"),
    ("T2-6 T (1).pdf",
     "Topic 5 Calculus", "Calculus", "HL", None, "ib_qbank_simple", "t2_6"),
    ("Topic 2 Part 1 T.pdf",
     "Topic 2 Functions", "Functions", "SL", None, "ib_qbank", "t2p1"),
    # Topic 3
    ("Math_SL_Circular_FunctionsTrigonometry.pdf",
     "Topic 3 Geometry and Trigonometry", "Geometry and Trigonometry", "SL", None, "topclass", "t3_trig"),
    ("Topic 3 Part 1 T (1).pdf",
     "Topic 3 Geometry and Trigonometry", "Geometry and Trigonometry", "SL", None, "ib_qbank", "t3p1"),
    # Topic 4
    ("Math_SL_Statistics_Probability_2022 (1).pdf",
     "Topic 4 Statistics and Probability", "Statistics and Probability", "SL", None, "topclass", "t4_sl"),
    ("statistics (1).pdf",
     "Topic 4 Statistics and Probability", "Statistics and Probability", "HL", None, "topclass", "t4_hl"),
    # Topic 5
    ("Math_SL_Calculus_Julius (1).pdf",
     "Topic 5 Calculus", "Calculus", "SL", None, "topclass", "t5_sl"),
    ("Limits_derivatives (1).pdf",
     "Topic 5 Calculus", "Calculus", "HL", None, "topclass", "t5_lim"),
    ("Topic_6_Calculus.pdf",
     "Topic 5 Calculus", "Calculus", "HL", None, "topclass", "t5_hl"),
    ("T6-1 T HL.pdf",
     "Topic 5 Calculus", "Calculus", "HL", None, "ib_qbank", "t5_t61"),
    ("T6-2P1 T.pdf",
     "Topic 5 Calculus", "Calculus", "HL", "Paper 1", "ib_qbank_simple", "t5_p1"),
    ("T6-2P2 T.pdf",
     "Topic 5 Calculus", "Calculus", "HL", "Paper 2", "ib_qbank_simple", "t5_p2"),
    ("Topic 6 Part 1 T SL.pdf",
     "Topic 5 Calculus", "Calculus", "SL", None, "ib_qbank", "t5_sl2"),
]

ALREADY_PROCESSED = {
    "Binomila Theorem.pdf", "Math_SL_Algebra.pdf", "Math_SL_Algebra_Exp_Log.pdf",
    "Topic_1_2_Algebra_Exponents_Logarithms_2023.pdf", "Topic_1_4_Algebra_Mathematical_Induction.pdf",
    "Topic_1_5_Algebra_Complex_Numbers.pdf", "Math_SL_Functions_Equations_2023.pdf",
    "DP1_and_DP2_AA_HL_Course_Overview_2025_2027 (1) (1).pdf", "Math test Miguel (2).pdf",
}

# ─────────────────────────────────────────────────────────────────────────────
# Subtopic inference per topic
# ─────────────────────────────────────────────────────────────────────────────

def infer_subtopic_t1(text: str) -> str:
    t = text.lower()
    if re.search(r"\bcomplex\b|argand|modulus|argument|de moivre|z\^n|\broot of unity\b", t):
        return "Complex numbers"
    if re.search(r"\binduction\b|prove.*n\s*=|n\s*\+\s*1|base case|inductive", t):
        return "Proof by induction"
    if re.search(r"\bpermut\b|\bcombin\b|c\(\d|p\(\d|\bnpr\b|\bncr\b|select.*ways|choose", t):
        return "Counting principles"
    if re.search(r"\bexponent\b|\blogarithm\b|\blog\b|\bln\b|exponential equat", t):
        return "Exponents and logarithms"
    if re.search(r"\bbinomial\b|\bexpansion\b|pascal|general term|coefficient of x", t):
        return "Binomial theorem"
    if re.search(r"\barithmetic\b|\bgeometric\b|\bsequence\b|\bseries\b|\bsum\b|common ratio|common diff", t):
        return "Sequences and series"
    return "Number and algebra"


def infer_subtopic_t2(text: str) -> str:
    t = text.lower()
    if re.search(r"\bfactor theorem\b|\bremainder theorem\b|exactly divis|divisible by|polynomial", t):
        return "Polynomial functions"
    if re.search(r"\bquadratic\b|ax\^2|discriminant|vertex|complete the square|two equal roots", t):
        return "Quadratic functions"
    if re.search(r"\bcomposite\b|g\(f\(|f\(g\(|g∘f", t):
        return "Composite and inverse functions"
    if re.search(r"\binverse\b|f\^{-1}|f⁻¹", t):
        return "Composite and inverse functions"
    if re.search(r"\btransform\b|\btranslat\b|\breflect\b|\bstretch\b", t):
        return "Transformations of functions"
    if re.search(r"\bexponential\b|\bln\b|\blog\b|logarithm", t):
        return "Exponential and logarithmic functions"
    if re.search(r"\bdomain\b|\brange\b|\basymptote\b|\brational\b", t):
        return "Domain, range and asymptotes"
    return "Functions and equations"


def infer_subtopic_t3(text: str) -> str:
    t = text.lower()
    if re.search(r"\bvector\b|scalar product|dot product|cross product|angle between", t):
        return "Vectors"
    if re.search(r"\bsine rule\b|\bcosine rule\b|area of triangle|triangle", t):
        return "Triangle trigonometry"
    if re.search(r"\bidentit\b|double angle|compound angle|addition formula|sin.*cos|cos.*sin", t):
        return "Trigonometric identities"
    if re.search(r"\bsolve\b.*\bsin\b|\bsolve\b.*\bcos\b|\bsolve\b.*\btan\b|trig.*equation", t):
        return "Trigonometric equations"
    if re.search(r"\bsin\b|\bcos\b|\btan\b|amplitude|period|ferris wheel|sinusoidal", t):
        return "Trigonometric functions"
    return "Geometry and trigonometry"


def infer_subtopic_t4(text: str) -> str:
    t = text.lower()
    if re.search(r"\bnormal distribution\b|normal curve|standardiz|z.score|n\(μ", t):
        return "Normal distribution"
    if re.search(r"\bpoisson\b|mean.*event|rate.*occur", t):
        return "Poisson distribution"
    if re.search(r"\bbinomial distribution\b|b\(n,p\)|n trials|bernoulli", t):
        return "Binomial distribution"
    if re.search(r"\bdiscrete\b.*random|probability distribution|e\(x\)|expected value|variance", t):
        return "Discrete distributions"
    if re.search(r"\bconfidence interval\b|\bhypothesis test\b|\bt-test\b|\bchi", t):
        return "Statistical inference"
    if re.search(r"\bcorrelation\b|\bregression\b|least square|line of best", t):
        return "Regression and correlation"
    if re.search(r"\bconditional\b|bayes|p\(a\|b\)|mutually exclusive|independent events", t):
        return "Probability"
    if re.search(r"\bprobability\b|sample space|event|p\(a\)", t):
        return "Probability"
    return "Statistics and probability"


def infer_subtopic_t5(text: str) -> str:
    t = text.lower()
    if re.search(r"\bdifferential equation\b|dy/dx\s*=|separabl|homogeneous ode|integrating factor", t):
        return "Differential equations"
    if re.search(r"\bmaclaurin\b|\btaylor\b|series expansion|power series", t):
        return "Series and approximation"
    if re.search(r"\blimit\b|\blim\b|convergence|epsilon|delta|l'hopital", t):
        return "Limits"
    if re.search(r"\bvolume\b.*revolv|disk method|shell method|solid of revolution", t):
        return "Applications of integration"
    if re.search(r"\barea\b.*enclos|definite integral|area under|improper integral", t):
        return "Applications of integration"
    if re.search(r"\bintegrat\b|\banti.deriv\b|indefinite integral", t):
        return "Integration techniques"
    if re.search(r"\brelated rate\b|\brate of change\b|d/dt|optimization\b|\bmaximum\b.*calculus\b", t):
        return "Applications of differentiation"
    if re.search(r"\bchain rule\b|\bproduct rule\b|\bquotient rule\b|implicit diff", t):
        return "Differentiation techniques"
    if re.search(r"\bderivative\b|\bdifferentiat\b|gradient\b.*function|f'|dy/dx", t):
        return "Differentiation"
    return "Calculus"


SUBTOPIC_INFERRERS = {
    "Number and Algebra": infer_subtopic_t1,
    "Functions": infer_subtopic_t2,
    "Geometry and Trigonometry": infer_subtopic_t3,
    "Statistics and Probability": infer_subtopic_t4,
    "Calculus": infer_subtopic_t5,
}


# ─────────────────────────────────────────────────────────────────────────────
# Text cleaning utilities
# ─────────────────────────────────────────────────────────────────────────────

def normalize_ws(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def cleanup_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        l = line.strip()
        if not l:
            lines.append("")
            continue
        if re.match(r"^\d+\s*\|\s*P\s*a\s*g\s*e", l):
            continue
        if re.match(r"^Page\s+\d+\s+of\s+\d+", l):
            continue
        if "TopClassTutors" in l or "IB Revision Courses" in l:
            continue
        lines.append(l)
    return normalize_ws("\n".join(lines))


# ─────────────────────────────────────────────────────────────────────────────
# Format A (TopClassTutors): "N. text ... (Total N marks)"
# ─────────────────────────────────────────────────────────────────────────────

def split_topclass(text: str) -> List[Dict]:
    lines = text.splitlines()
    current_num: Optional[int] = None
    current_lines: List[str] = []
    output: List[Dict] = []

    def flush() -> None:
        if current_num is None:
            return
        body = normalize_ws("\n".join(current_lines))
        if len(body) < 15:
            return
        output.append({"question_number": str(current_num), "question_text": body})

    for line in lines:
        m = re.match(r"^(\d{1,2})\.\s+", line)
        if m:
            flush()
            current_num = int(m.group(1))
            current_lines = [line]
        elif current_num is not None:
            current_lines.append(line)
    flush()
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Format B simple (T6-2P1/P2, T2-5, T2-6): "[N marks]\nN.\ntext"
# ─────────────────────────────────────────────────────────────────────────────

def split_ib_simple(text: str) -> List[Dict]:
    """
    Parse IB qbank PDFs. Handles both:
      "[N marks]\\nN. text" (T6-2P1 style)
      "stem [N marks]\\nN.\\ntext" (T2-5 style)
    Groups sub-parts (Na.) by parent number.
    """
    lines = text.splitlines()
    n = len(lines)
    output: List[Dict] = []
    marks_pending = 0
    i = 0

    while i < n:
        stripped = lines[i].strip()

        # Standalone "[N marks]" accumulates pending marks.
        m_marks = re.match(r"^\[(\d+)\s+marks?\]$", stripped, re.IGNORECASE)
        if m_marks:
            marks_pending += int(m_marks.group(1))
            i += 1
            continue

        # "N." or "Na." at start of line (may have text after, may be standalone).
        m_q = re.match(r"^(\d{1,2})([a-z]?)\.\s*(.*)", stripped)
        if m_q:
            parent = int(m_q.group(1))
            rest_text = m_q.group(3).strip()

            # Gather continuation lines until next question or marks line.
            body_lines = [stripped] if rest_text else []
            i += 1
            while i < n:
                nl = lines[i].strip()
                if re.match(r"^\[(\d+)\s+marks?\]$", nl, re.IGNORECASE):
                    break
                if re.match(r"^(\d{1,2})[a-z]?\.\s", nl) or re.match(r"^(\d{1,2})[a-z]?\.$", nl):
                    break
                body_lines.append(lines[i])
                i += 1
            body = normalize_ws("\n".join(body_lines))
            used_marks = marks_pending
            marks_pending = 0

            # Merge sub-parts into parent question.
            if output and output[-1]["question_number"] == str(parent):
                output[-1]["question_text"] += ("\n\n" + body) if body else ""
                if used_marks:
                    output[-1]["marks"] = (output[-1].get("marks") or 0) + used_marks
            else:
                output.append({
                    "question_number": str(parent),
                    "question_text": body,
                    "marks": used_marks or None,
                })
            continue

        i += 1
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Format B (IB Questionbank): stem before part, "Na." identifier
# ─────────────────────────────────────────────────────────────────────────────

def split_ib_qbank(text: str) -> List[Dict]:
    """
    Parse IB questionbank exports where question structure is:
      [stem text]
      [instruction] [N marks]
      Na.
      [sub-part text, optional]
    Group all sub-parts into one question per parent number.
    """
    lines = text.splitlines()
    n = len(lines)
    output: List[Dict] = []

    # Detect all part identifiers and their positions.
    # A part identifier is a line matching exactly "Na." or "N." where N is 1-99.
    part_positions: List[Tuple[int, int, str]] = []  # (line_idx, parent_num, raw_id)
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = re.match(r"^(\d{1,2})([a-z]?)\.$", stripped)
        if m and 1 <= int(m.group(1)) <= 99:
            parent = int(m.group(1))
            part_id = stripped
            part_positions.append((i, parent, part_id))

    if not part_positions:
        # Fallback: treat as topclass format
        return split_topclass(text)

    # Group by parent number.
    # For each parent question, the text spans from just before the first part's
    # preceding stem text to just before the next parent's first part.
    parent_starts: Dict[int, int] = {}
    for idx, (line_idx, parent, _) in enumerate(part_positions):
        if parent not in parent_starts:
            # The question stem starts some lines above this part identifier.
            # Walk backwards to find where the stem starts (after the previous part).
            prev_end = part_positions[idx - 1][0] if idx > 0 else 0
            # Look for the stem: non-empty content after the previous part end
            stem_start = prev_end
            for j in range(prev_end, line_idx):
                if lines[j].strip():
                    stem_start = j
                    break
            parent_starts[parent] = stem_start

    # Sort parent numbers
    sorted_parents = sorted(parent_starts.keys())

    for pi, parent in enumerate(sorted_parents):
        # Find the end of this question: start of next parent's stem
        if pi + 1 < len(sorted_parents):
            next_parent = sorted_parents[pi + 1]
            end_line = parent_starts[next_parent]
        else:
            end_line = n

        # Gather all text for this parent question
        body_lines = lines[parent_starts[parent]:end_line]
        body = normalize_ws("\n".join(body_lines))

        # Extract total marks from [N marks] annotations
        total_marks = 0
        for m in re.finditer(r"\[(\d+)\s+marks?\]", body, re.IGNORECASE):
            total_marks += int(m.group(1))

        if len(body) < 10:
            continue

        output.append({
            "question_number": str(parent),
            "question_text": body,
            "marks": total_marks if total_marks else None,
        })

    return output


def extract_marks_from_text(text: str) -> Optional[int]:
    m = re.search(r"\(Total\s+(\d+)\s+marks?\)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\[(\d+)\s+marks?\]", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    sub_marks = re.findall(r"\((\d+)\)", text)
    if sub_marks:
        return sum(int(x) for x in sub_marks)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Image cropping (shared)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StartPos:
    qnum: int
    page: int
    y: float


def detect_starts(doc: fitz.Document, supports_parts: bool = False) -> List[StartPos]:
    """
    Detect the visual start position of each parent question number in the PDF.
    For part-based PDFs (supports_parts=True), also handles "Na." identifiers,
    but only records the FIRST occurrence of each parent number.
    """
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

                # Match "N." at start of line (with following text)
                m = re.match(r"^(\d{1,2})\.\s+", line_text)
                if m:
                    qnum = int(m.group(1))

                # Match standalone "Na." or "N." (IB qbank part identifier)
                if qnum is None and supports_parts:
                    m2 = re.match(r"^(\d{1,2})[a-z]?\.$", line_text)
                    if m2:
                        qnum = int(m2.group(1))

                # Match "[N marks]" followed by "N." on next line — pending
                if qnum is None:
                    m_dot = re.match(r"^(\d{1,2})\.$", line_text)
                    if m_dot:
                        pending_num = int(m_dot.group("num") if hasattr(m_dot, "num") else m_dot.group(1))
                        pending_y = y
                        pending_x = x
                        qnum = pending_num
                    m_pending = re.match(r"^(\d{1,2})$", line_text)
                    if m_pending:
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


def crop_question(doc: fitz.Document, starts: List[StartPos], qnum: int, out_prefix: Path) -> List[str]:
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
        top = 40.0
        bottom = float(page.rect.height) - 20.0
        left = 18.0
        right = float(page.rect.width) - 18.0
        if pno == s.page:
            top = max(30.0, s.y - 80)  # 80px above detected start captures 2-3 lines of preamble
        if n is not None and pno == n.page:
            bottom = min(bottom, n.y - 2.0)
        if bottom <= top + 15.0:
            continue
        clip = fitz.Rect(left, top, right, bottom)
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        if s.page == last_page:
            out_file = out_prefix.with_suffix(".png")
        else:
            out_file = out_prefix.parent / f"{out_prefix.name}_p{pno - s.page + 1}.png"
        pix.save(str(out_file))
        rel = out_file.relative_to(ROOT / "data" / "tutoring" / "processed").as_posix()
        image_paths.append(rel)
    return image_paths


def fallback_page_image(doc: fitz.Document, question_text: str, qnum: int, out_prefix: Path) -> List[str]:
    key_words = re.findall(r"[A-Za-z]{4,}", question_text)
    key = " ".join(key_words[:8]).lower() if key_words else ""
    if not key:
        return []
    best_page = None
    best_score = 0
    for pno in range(len(doc)):
        page_text = doc[pno].get_text("text").lower()
        score = sum(1 for w in key_words[:8] if w.lower() in page_text)
        if f"{qnum}." in page_text or f"{qnum}a." in page_text:
            score += 3
        if score > best_score:
            best_score = score
            best_page = pno
    if best_page is None or best_score < 3:
        return []
    page = doc[best_page]
    clip = fitz.Rect(18.0, 30.0, float(page.rect.width) - 18.0, float(page.rect.height) - 20.0)
    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
    out_file = out_prefix.with_suffix(".png")
    pix.save(str(out_file))
    rel = out_file.relative_to(ROOT / "data" / "tutoring" / "processed").as_posix()
    return [rel]


# ─────────────────────────────────────────────────────────────────────────────
# Markscheme generation (SVG)
# ─────────────────────────────────────────────────────────────────────────────

def build_markscheme_text(q: Dict) -> str:
    qtext = str(q.get("question_text", ""))
    topic = q.get("topic", "")
    infer_fn = SUBTOPIC_INFERRERS.get(topic, lambda t: "")
    subtopic = q.get("subtopic", "")
    qn = q.get("question_number", "")
    marks = int(q.get("marks") or 0)

    steps_by_method = {
        "Differentiation":         ["f′(x) = d/dx[...]", "apply chain/product/quotient rule", "simplify"],
        "Integration techniques":  ["∫f(x)dx = F(x)+C", "choose substitution or parts", "evaluate bounds if definite"],
        "Applications of differentiation": ["set f′(x)=0", "solve for critical points", "classify max/min"],
        "Applications of integration": ["set up integral with bounds", "evaluate ∫f(x)dx", "include units"],
        "Limits":                  ["check form (0/0, ∞/∞)", "apply L'Hôpital or algebra", "evaluate limit"],
        "Differential equations":  ["separate variables", "integrate both sides", "apply initial condition"],
        "Sequences and series":    ["identify type (arithmetic/geometric)", "write general term", "apply sum formula"],
        "Exponents and logarithms":["take log of both sides", "apply log laws", "solve algebraically"],
        "Binomial theorem":        ["Tᵣ₊₁=C(n,r)·aⁿ⁻ʳ·bʳ", "match required power", "substitute and simplify"],
        "Counting principles":     ["identify permutation or combination", "apply ⁿPᵣ or C(n,r)", "multiply by arrangement factor"],
        "Proof by induction":      ["base case: verify n=1", "assume true for n=k", "prove for n=k+1"],
        "Complex numbers":         ["write z=a+bi or r(cosθ+i sinθ)", "apply De Moivre / Argand", "compute result"],
        "Probability":             ["define sample space", "apply P(A∩B)=P(A)·P(B|A)", "verify axioms"],
        "Normal distribution":     ["standardise: Z=(X−μ)/σ", "look up P(Z<z)", "interpret in context"],
        "Polynomial functions":    ["apply factor/remainder theorem", "factorise fully", "state roots"],
        "Trigonometric functions": ["use amplitude/period formula", "find key values (0,max,min)", "sketch or solve"],
        "Trigonometric equations": ["rearrange to sin/cos/tan = k", "find principal value", "add period, restrict domain"],
        "Triangle trigonometry":   ["identify known sides/angles", "apply sine or cosine rule", "solve for unknown"],
        "Vectors":                 ["write vectors in component form", "apply dot/cross product", "interpret geometrically"],
    }

    method_steps = steps_by_method.get(subtopic, ["set up equation", "apply relevant rule", "simplify and state answer"])
    if marks <= 2:
        method_steps = method_steps[:2]

    lines = [f"{qn}."]
    for i, step in enumerate(method_steps):
        roman = ["(i)", "(ii)", "(iii)", "(iv)", "(v)"]
        prefix = roman[i] if i < len(roman) else f"({i+1})"
        lines.append(f"  {prefix}  {step}")
    return "\n".join(lines)


def render_svg(title: str, text: str) -> str:
    wrapped: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            wrapped.append("")
            continue
        chunks = wrap(line, width=95, break_long_words=False, break_on_hyphens=False)
        wrapped.extend(chunks if chunks else [""])
    line_height = 30
    top_pad = 120
    bottom_pad = 60
    height = top_pad + (max(len(wrapped), 1) * line_height) + bottom_pad
    width = 1400
    y = 160
    lines_svg = []
    for line in wrapped:
        content = escape(line) if line else " "
        looks_math = any(c in line for c in ["=", "^", "√", "∫", "d/dx", "f′", "log", "±", "⁻¹", "∑"])
        weight = "700" if line.startswith("(") and len(line) < 8 else "500"
        fill = "#1d2f57" if weight == "700" else "#1f2a44"
        font_family = "Cambria Math, STIX Two Math, Times New Roman, serif" if looks_math else "Arial, Helvetica, sans-serif"
        lines_svg.append(
            f'<text x="70" y="{y}" font-family="{font_family}" '
            f'font-size="28" font-weight="{weight}" fill="{fill}">{content}</text>'
        )
        y += line_height
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f'  <rect x="20" y="20" width="{width-40}" height="{height-40}" rx="18" ry="18" fill="#f5f7fb" stroke="#c6cfdf" stroke-width="2"/>\n'
        f'  <rect x="20" y="20" width="{width-40}" height="54" rx="18" ry="18" fill="#e7eef9" stroke="#c6cfdf" stroke-width="2"/>\n'
        f'  <text x="50" y="57" font-family="Arial, Helvetica, sans-serif" font-size="36" font-weight="700" fill="#213a6a">Markscheme answer</text>\n'
        f'  <text x="70" y="110" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#243451">{escape(title)}</text>\n'
        f'  {"".join(lines_svg)}\n'
        f'</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main processing
# ─────────────────────────────────────────────────────────────────────────────

def process_pdf(cfg: Tuple, q_payload: Dict, ms_payload: Dict) -> int:
    src_name, unit, topic, level, paper_type, fmt, id_prefix = cfg
    pdf_path = MATH_DIR / src_name
    if not pdf_path.exists():
        print(f"  SKIP (not found): {src_name}")
        return 0

    infer_fn = SUBTOPIC_INFERRERS.get(topic, lambda t: "")

    # Extract text
    reader = PdfReader(str(pdf_path))
    raw_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    clean = cleanup_text(raw_text)

    # Parse questions based on format
    if fmt == "topclass":
        raw_qs = split_topclass(clean)
    elif fmt == "ib_qbank_simple":
        raw_qs = split_ib_simple(clean)
    elif fmt == "ib_qbank":
        raw_qs = split_ib_qbank(clean)
    else:
        raw_qs = split_topclass(clean)

    print(f"  Parsed {len(raw_qs)} questions from '{src_name}'")
    if not raw_qs:
        return 0

    # Build question records
    safe_prefix = id_prefix.replace(" ", "_").replace("(", "").replace(")", "").lower()
    new_questions = []
    for q_raw in raw_qs:
        qn = q_raw["question_number"]
        qid = f"{safe_prefix}_q{qn}"
        qtext = q_raw.get("question_text", "")
        subtopic = infer_fn(qtext)
        marks = q_raw.get("marks") or extract_marks_from_text(qtext)
        new_questions.append({
            "id": qid,
            "unit": unit,
            "topic": topic,
            "subtopic": subtopic,
            "source_file": src_name,
            "question_number": qn,
            "title": f"Q{qn}",
            "question_text": qtext,
            "question_image_paths": [],
            "level": level,
            "paper_type": paper_type,
            "marks": marks,
        })

    # Crop images
    fitz_doc = fitz.open(str(pdf_path))
    supports_parts = fmt in ("ib_qbank", "ib_qbank_simple")
    starts = detect_starts(fitz_doc, supports_parts=supports_parts)
    print(f"  Detected {len(starts)} question starts in PDF")

    for q in new_questions:
        qnum = int(q["question_number"])
        out_prefix = IMAGES_Q_DIR / q["id"]
        paths = crop_question(fitz_doc, starts, qnum, out_prefix)
        if not paths:
            paths = fallback_page_image(fitz_doc, q["question_text"], qnum, out_prefix)
        q["question_image_paths"] = paths
        status = f"{len(paths)} image(s)" if paths else "NO IMAGES"
        print(f"    Q{qnum}: {status}")
    fitz_doc.close()

    # Update questions.json — remove any existing entries from this source
    existing_qs = q_payload.get("questions", [])
    existing_qs = [q for q in existing_qs if q.get("source_file") != src_name]
    existing_qs.extend(new_questions)
    q_payload["questions"] = existing_qs

    # Generate markschemes
    existing_ms = ms_payload.get("questions", [])
    existing_ms = [m for m in existing_ms if not str(m.get("id", "")).startswith(safe_prefix)]

    new_markschemes = []
    for q in new_questions:
        ms_text = build_markscheme_text(q)
        svg = render_svg(q["title"], ms_text)
        svg_file = IMAGES_MS_DIR / f"{q['id']}.svg"
        svg_file.write_text(svg, encoding="utf-8")
        ms_entry = {
            "id": q["id"],
            "title": q["title"],
            "source_file": q["source_file"],
            "topic": q["topic"],
            "subtopic": q["subtopic"],
            "question_number": q["question_number"],
            "worked_solution_text": ms_text,
            "markscheme_image_paths": [f"images/markschemes/{q['id']}.svg"],
            "draft": True,
        }
        new_markschemes.append(ms_entry)
    existing_ms.extend(new_markschemes)
    ms_payload["questions"] = existing_ms

    return len(new_questions)


def main() -> None:
    IMAGES_Q_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_MS_DIR.mkdir(parents=True, exist_ok=True)

    q_payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    ms_payload = json.loads(MARKSCHEMES_JSON.read_text(encoding="utf-8"))

    total_added = 0
    for cfg in PDF_CONFIGS:
        src_name = cfg[0]
        print(f"\nProcessing: {src_name}")
        added = process_pdf(cfg, q_payload, ms_payload)
        total_added += added
        print(f"  → {added} questions added")

    QUESTIONS_JSON.write_text(json.dumps(q_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MARKSCHEMES_JSON.write_text(json.dumps(ms_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    all_qs = q_payload.get("questions", [])
    all_ms = ms_payload.get("questions", [])
    print(f"\nDone. Added {total_added} new questions.")
    print(f"Total questions.json: {len(all_qs)}")
    print(f"Total markschemes.json: {len(all_ms)}")


if __name__ == "__main__":
    main()
