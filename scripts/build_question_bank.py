#!/usr/bin/env python3
"""Build AA HL question bank from raw papers and markschemes (multi-session)."""

from __future__ import annotations

import json
import re
import sys
from difflib import SequenceMatcher
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

from pypdf import PdfReader  # type: ignore

PAPERS_DIR = ROOT / "data" / "raw" / "papers"
MARKSCHEMES_DIR = ROOT / "data" / "raw" / "markschemes"
OUT_FILE = ROOT / "data" / "processed" / "questions.json"
PROCESSED_IMAGES_DIR = ROOT / "data" / "processed" / "images"

FILE_PAPER_RE = re.compile(r"paper_(?P<paper>\d)", re.IGNORECASE)
FILE_TZ_RE = re.compile(r"(?:__|_)TZ(?P<tz>\d)_(?:HL|SL)", re.IGNORECASE)
EXAM_RE = re.compile(r"\b(?P<code>[MN]\d{2})/5/MATHX/[HS]P(?P<paper>\d)/ENG(?:/TZ(?P<tz>\d))?/XX")
PREFIX_RE = re.compile(r"^(?P<code>[mn]\d{2})_")


@dataclass
class PaperMeta:
    filename: str
    paper_no: int
    session: str
    session_code: str
    tz: Optional[int]
    level: str

    @property
    def paper_type(self) -> str:
        return f"Paper {self.paper_no}"

    @property
    def paper_label(self) -> str:
        if self.tz is None:
            return f"{self.session} {self.paper_type} {self.level}"
        return f"{self.session} {self.paper_type} TZ{self.tz} {self.level}"


def normalize_ws(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_for_dedupe(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def clean_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw in text.splitlines():
        line = raw.replace("\xa0", " ").strip()
        if not line:
            lines.append("")
            continue

        if re.match(r"^–\s*\d+\s*–\s*[MN]\d{2}/5/MATHX/HP\d/ENG(?:/TZ\d)?/XX(?:/M)?\s*$", line):
            continue
        if line in {"Turn over", "Section A", "Section B"}:
            continue
        if re.match(r"^\d+\s*pages$", line, re.IGNORECASE):
            continue
        if re.match(r"^\.+$", line):
            continue

        lines.append(line)

    compact: List[str] = []
    for line in lines:
        if line == "" and compact and compact[-1] == "":
            continue
        compact.append(line)
    return compact


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def pair_key(filename: str) -> str:
    base = filename.lower()
    base = re.sub(r"_markscheme", "", base)
    base = re.sub(r"\.pdf$", "", base)
    return base


def infer_level_from_filename(filename: str) -> str:
    low = filename.lower()
    if "_sl" in low or "__sl" in low:
        return "SL"
    return "HL"


def session_label_from_code(code: str) -> str:
    year = f"20{code[1:]}"
    return f"May {year}" if code.startswith("M") else f"November {year}"


def detect_exam_info(path: Path) -> Tuple[str, str, Optional[int], Optional[int]]:
    reader = PdfReader(str(path))
    sample = "\n".join((reader.pages[i].extract_text() or "") for i in range(min(3, len(reader.pages))))
    m = EXAM_RE.search(sample)
    if not m:
        pm = PREFIX_RE.match(path.name)
        if pm:
            code = pm.group("code").lower()
            session = session_label_from_code(code.upper())
            return (code, session, None, None)
        return ("u00", "Unknown Session", None, None)

    code = m.group("code").lower()
    session = session_label_from_code(m.group("code"))
    tz_str = m.group("tz")
    paper_str = m.group("paper")
    tz = int(tz_str) if tz_str else None
    if tz == 0:
        tz = None
    return (code, session, tz, int(paper_str) if paper_str else None)


def parse_meta(path: Path) -> PaperMeta:
    name = path.name
    m = FILE_PAPER_RE.search(name)
    if not m:
        raise ValueError(f"Could not parse paper number from {name}")
    paper_no = int(m.group("paper"))

    code, session, tz, paper_from_code = detect_exam_info(path)
    if paper_from_code is not None:
        paper_no = paper_from_code
    if tz is None:
        mtz = FILE_TZ_RE.search(name)
        if mtz:
            tz = int(mtz.group("tz"))

    return PaperMeta(
        filename=name,
        paper_no=paper_no,
        session=session,
        session_code=code,
        tz=tz,
        level=infer_level_from_filename(name),
    )


def parse_questions_from_paper(path: Path) -> Dict[int, Dict[str, object]]:
    text = extract_pdf_text(path)
    lines = clean_lines(text)
    content = "\n".join(lines)

    content = re.sub(
        r"(?m)^([1-9])\s*\n\1\.\s*\[Maximum mark:",
        lambda m: f"{m.group(1)}{m.group(1)}. [Maximum mark:",
        content,
    )

    q_re = re.compile(
        r"(?ms)^\s*(?P<num>\d+)\.\s*\[Maximum mark:\s*(?P<marks>\d+)\]\s*(?P<body>.*?)(?=^\s*\d+\.\s*\[Maximum mark:|\Z)"
    )

    out: Dict[int, Dict[str, object]] = {}
    for m in q_re.finditer(content):
        qn = int(m.group("num"))
        marks = int(m.group("marks"))
        body = normalize_ws(m.group("body"))
        out[qn] = {
            "marks": marks,
            "question_text": body,
        }
    return out


def parse_answers_from_markscheme(path: Path) -> Dict[int, str]:
    text = extract_pdf_text(path)
    lines = clean_lines(text)

    start_idx = 0
    for i, line in enumerate(lines):
        if (
            re.match(r"^1\.\s*\(a\)", line)
            or re.match(r"^Question\s+1\b", line)
            or re.match(r"^1\s+METHOD\b", line)
            or line == "Section A"
        ):
            start_idx = i
            break

    q_starts = [
        re.compile(r"^(?P<num>\d+)\.(?:\s|$)"),
        re.compile(r"^(?P<num>\d+)\s+\("),
        re.compile(r"^(?P<num>\d+)\s+METHOD\b"),
        re.compile(r"^Question\s+(?P<num>\d+)\b", re.IGNORECASE),
    ]

    answers: Dict[int, List[str]] = {}
    current: int | None = None

    for raw_line in lines[start_idx:]:
        line = raw_line.strip()
        if not line:
            if current is not None:
                answers.setdefault(current, []).append("")
            continue

        new_q: int | None = None
        for patt in q_starts:
            m = patt.match(line)
            if m:
                new_q = int(m.group("num"))
                break

        if new_q is not None and (current is None or new_q != current):
            current = new_q

        if current is None:
            continue

        line = re.sub(r"^Question\s+\d+\s+continued\s*$", "", line, flags=re.IGNORECASE).strip()
        if not line:
            continue
        answers.setdefault(current, []).append(line)

    result: Dict[int, str] = {}
    for qn, block in answers.items():
        text_block = "\n".join(block)
        text_block = re.sub(r"\n{3,}", "\n\n", text_block)
        result[qn] = normalize_ws(text_block)
    return result


def classify_topic(question_text: str, answer_text: str) -> Tuple[str, str, float, List[str]]:
    # Question text is primary. Markscheme contributes weak evidence for OCR-damaged prompts.
    q_text_raw = question_text.lower().replace("-", " ")
    a_text_raw = answer_text.lower().replace("-", " ")
    q_text = re.sub(r"[^a-z0-9()'+*/.=,: ]+", " ", q_text_raw)
    a_text = re.sub(r"[^a-z0-9()'+*/.=,: ]+", " ", a_text_raw)
    q_text = re.sub(r"\s+", " ", q_text).strip()
    a_text = re.sub(r"\s+", " ", a_text).strip()
    merged = f"{q_text} {a_text}"

    # Hard anchors for very specific question styles.
    hard_anchors: List[Tuple[re.Pattern[str], Tuple[str, str], str]] = [
        (
            re.compile(
                r"\b(permutation|combination|factorial|ncr|npr|counting principle|arrangements?|number of ways|how many ways|share a boundary|must not be placed|no tied finishes?|seated|row of \d+ available seats|every other student|digits are distinct|six digit positive integers)\b"
            ),
            ("Statistics and Probability", "Discrete and continuous random variables"),
            "anchor:counting",
        ),
        (
            re.compile(r"\b(interquartile range|quartile|box and whisker|outlier)\b"),
            ("Statistics and Probability", "Probability distributions"),
            "anchor:quartiles",
        ),
        (
            re.compile(r"\b(hypothesis|null hypothesis|alternative hypothesis|p value|significance level|critical region)\b"),
            ("Statistics and Probability", "Hypothesis testing"),
            "anchor:hypothesis",
        ),
        (
            re.compile(r"\b(correlation|regression|pearson|spearman|least squares)\b"),
            ("Statistics and Probability", "Correlation and regression"),
            "anchor:regression",
        ),
        (
            re.compile(r"\b(differential equation|dy/dx|separable)\b"),
            ("Calculus", "Differential equations"),
            "anchor:diffeq",
        ),
        (
            re.compile(r"\b(maclaurin|taylor series|expansion about x ?= ?0)\b"),
            ("Calculus", "Maclaurin series"),
            "anchor:series",
        ),
        (
            re.compile(r"\b(binomial theorem|binomial expansion|in the expansion of|\(a\+b\)\^n|coefficient of x)\b"),
            ("Number and Algebra", "Binomial theorem"),
            "anchor:binomial",
        ),
        (
            re.compile(r"\b(prove by induction|induction step|assume true for n=k)\b"),
            ("Number and Algebra", "Proof by induction"),
            "anchor:induction",
        ),
        (
            re.compile(r"\b(z4|z3|z2|z \u2208|a\+bi|complex|argand|conjugate|modulus|argument)\b"),
            ("Number and Algebra", "Complex numbers"),
            "anchor:complex",
        ),
        (
            re.compile(r"\b(rotated 360|solid of revolution|maximum volume|rate .* increasing|increases at a constant rate)\b"),
            ("Calculus", "Integration"),
            "anchor:calculus-modelling",
        ),
    ]
    for pattern, label, reason in hard_anchors:
        if pattern.search(q_text):
            return (label[0], label[1], 0.99, [reason])

    Rule = Tuple[re.Pattern[str], Tuple[str, str], int, int]
    rules: List[Rule] = [
        # Statistics and Probability
        (
            re.compile(r"\b(permutation|combination|factorial|ncr|npr|counting principle|arrangements?|number of ways|how many ways|choose \d+)\b"),
            ("Statistics and Probability", "Discrete and continuous random variables"),
            20,
            6,
        ),
        (
            re.compile(r"\b(random variable|probability density function|probability distribution|binomial distribution|normal distribution|poisson)\b"),
            ("Statistics and Probability", "Probability distributions"),
            18,
            6,
        ),
        (
            re.compile(r"\b(die|dice|frequency table|mean|variance|standard deviation|marks obtained|class quiz)\b"),
            ("Statistics and Probability", "Probability distributions"),
            13,
            5,
        ),
        (
            re.compile(r"\b(interquartile range|quartile|box and whisker|outlier|median)\b"),
            ("Statistics and Probability", "Probability distributions"),
            18,
            5,
        ),
        (
            re.compile(r"\b(hypothesis|null hypothesis|alternative hypothesis|p value|significance level|critical region)\b"),
            ("Statistics and Probability", "Hypothesis testing"),
            18,
            7,
        ),
        (
            re.compile(r"\b(correlation|regression|pearson|spearman|least squares)\b"),
            ("Statistics and Probability", "Correlation and regression"),
            18,
            6,
        ),
        (
            re.compile(r"\b(independent events?|conditional probability|a \\cap b|a \\cup b|p\(a\)|p\(b\))\b"),
            ("Statistics and Probability", "Probability distributions"),
            12,
            5,
        ),
        # Calculus
        (
            re.compile(r"\b(differential equation|dy/dx|separable)\b"),
            ("Calculus", "Differential equations"),
            22,
            7,
        ),
        (
            re.compile(r"\b(maclaurin|taylor series|expansion about x ?= ?0)\b"),
            ("Calculus", "Maclaurin series"),
            22,
            7,
        ),
        (
            re.compile(r"\b(integral|integrate|integration|antiderivative|definite integral|indefinite integral|area under|area enclosed)\b"),
            ("Calculus", "Integration"),
            18,
            6,
        ),
        (
            re.compile(r"\b(rotated 360|solid of revolution|volume of the solid|about the y axis|about the x axis)\b"),
            ("Calculus", "Integration"),
            18,
            6,
        ),
        (
            re.compile(r"\b(limit|lim|continuity|continuous at|as x tends to)\b"),
            ("Calculus", "Limits and continuity"),
            16,
            5,
        ),
        (
            re.compile(r"\b(differentiate|differentiation|derivative|chain rule|product rule|quotient rule|stationary|tangent|normal to the curve|rate of change)\b"),
            ("Calculus", "Differentiation"),
            18,
            6,
        ),
        (
            re.compile(r"\b(related rates?|increases at a constant rate|maximum volume|minimum value|maximise|minimise)\b"),
            ("Calculus", "Differentiation"),
            16,
            6,
        ),
        # Geometry and Trigonometry
        (
            re.compile(r"\b(vector|vectors|position vector|direction vector|i\+j\+k|i,j,k|dot product|scalar product|cross product)\b"),
            ("Geometry and Trigonometry", "Vectors in 2D and 3D"),
            20,
            6,
        ),
        (
            re.compile(r"\b(line|plane|cartesian equation|normal vector|distance between skew lines|equation of plane)\b"),
            ("Geometry and Trigonometry", "Lines and planes"),
            18,
            6,
        ),
        (
            re.compile(r"\b(radian|arc length|sector area)\b"),
            ("Geometry and Trigonometry", "Radian measure"),
            20,
            6,
        ),
        (
            re.compile(r"\b(measured in radians|circumference of a circle|centre o and radius|theta is measured)\b"),
            ("Geometry and Trigonometry", "Radian measure"),
            15,
            5,
        ),
        (
            re.compile(r"\b(sin|cos|tan|cot|sec|cosec|trigonometric|trig identity|double angle)\b"),
            ("Geometry and Trigonometry", "Trigonometric identities and equations"),
            12,
            4,
        ),
        (
            re.compile(r"\b(triangle|bearing|parallelogram|cosine rule|sine rule)\b"),
            ("Geometry and Trigonometry", "Trigonometric identities and equations"),
            14,
            4,
        ),
        # Number and Algebra
        (
            re.compile(r"\b(complex|argand|conjugate|modulus|argument|re\(z\)|im\(z\)|a\+bi|z4|z3|z2)\b"),
            ("Number and Algebra", "Complex numbers"),
            22,
            7,
        ),
        (
            re.compile(r"\b(arithmetic sequence|geometric sequence|u_n|s_n|recurrence|summation|sigma notation|sum to infinity)\b"),
            ("Number and Algebra", "Sequences and series"),
            18,
            6,
        ),
        (
            re.compile(r"\b(induction|prove by contradiction|integer roots?|divisible by|multiple of|consecutive)\b"),
            ("Number and Algebra", "Proof by induction"),
            14,
            5,
        ),
        (
            re.compile(r"\b(binomial theorem|binomial expansion|in the expansion of|expansion of|\(a\+b\)\^n|coefficient of x)\b"),
            ("Number and Algebra", "Binomial theorem"),
            20,
            6,
        ),
        (
            re.compile(r"\b(quadratic equation|cubic equation|quartic equation|roots of|discriminant|remainder theorem|factor of f\(x\)|polynomial)\b"),
            ("Number and Algebra", "Sequences and series"),
            14,
            5,
        ),
        (
            re.compile(r"\b(remainder is|divided by \(x|factor of f|has two distinct real roots)\b"),
            ("Number and Algebra", "Sequences and series"),
            12,
            5,
        ),
        # Functions
        (
            re.compile(r"\b(inverse function|inverse of f|one to one|bijective)\b"),
            ("Functions", "Inverse functions"),
            18,
            6,
        ),
        (
            re.compile(r"\b(logarithm|log\(|log10|ln\(|exponential|e\^x)\b"),
            ("Functions", "Exponential and logarithmic functions"),
            15,
            5,
        ),
        (
            re.compile(r"\b(compound interest|depreciates?|depreciation|per annum|investment|value of the car)\b"),
            ("Functions", "Exponential and logarithmic functions"),
            14,
            4,
        ),
        (
            re.compile(r"\b(domain|range|composite function|composition|f o g|g o f|f\(\s*x\s*\)|g\(\s*x\s*\))\b"),
            ("Functions", "Domain, range and composition"),
            14,
            5,
        ),
        (
            re.compile(r"\b(functions f and g are defined|g\s*o\s*f|f\s*o\s*g|\(g .* f\)\(x\)|\(f .* g\)\(x\))\b"),
            ("Functions", "Domain, range and composition"),
            14,
            5,
        ),
        (
            re.compile(r"\b(the functions f \(x\)|consider the functions f|given that .* g .* f)\b"),
            ("Functions", "Domain, range and composition"),
            13,
            4,
        ),
        (
            re.compile(r"\b(transformation|translation|stretch|reflection|asymptote|model|modelling)\b"),
            ("Functions", "Transformations and modelling"),
            14,
            5,
        ),
    ]

    scores: Dict[Tuple[str, str], int] = {}
    reasons: List[str] = []
    for pattern, label, q_weight, a_weight in rules:
        q_hits = len(pattern.findall(q_text))
        a_hits = len(pattern.findall(a_text))
        if q_hits == 0 and a_hits == 0:
            continue
        delta = q_hits * q_weight + a_hits * a_weight
        scores[label] = scores.get(label, 0) + delta
        reasons.append(f"{label[0]}:{label[1]}+{delta}")

    if not scores:
        # Last-resort fallback: infer from common symbols.
        if "∫" in question_text or " dx" in merged:
            return ("Calculus", "Integration", 0.6, ["fallback:integral-symbol"])
        if re.search(r"\b(die|dice|frequency|mean|variance|event|probability|random)\b", merged):
            return ("Statistics and Probability", "Probability distributions", 0.6, ["fallback:stats-terms"])
        if re.search(r"\b(rotated 360|solid of revolution|maximum volume|rate of change)\b", merged):
            return ("Calculus", "Differentiation", 0.6, ["fallback:calc-modelling"])
        if re.search(r"\b(quadratic|cubic|quartic|roots?|discriminant|consecutive|divisible|multiple of)\b", merged):
            return ("Number and Algebra", "Proof by induction", 0.58, ["fallback:algebraic-proof"])
        if "probability" in merged or "p (" in merged:
            return ("Statistics and Probability", "Probability distributions", 0.6, ["fallback:probability"])
        return ("Functions", "Transformations and modelling", 0.3, ["fallback:default-functions"])

    topic_scores: Dict[str, int] = {}
    for (topic, _subtopic), score in scores.items():
        topic_scores[topic] = topic_scores.get(topic, 0) + score

    # Penalize over-broad functions when stronger cross-topic signals exist.
    fn_score = topic_scores.get("Functions", 0)
    strongest_other = max([v for k, v in topic_scores.items() if k != "Functions"], default=0)
    if fn_score and strongest_other >= fn_score:
        topic_scores["Functions"] = max(0, fn_score - 8)

    ranked_topics = sorted(topic_scores.items(), key=lambda item: item[1], reverse=True)
    best_topic, best_topic_score = ranked_topics[0]
    second_topic_score = ranked_topics[1][1] if len(ranked_topics) > 1 else 0

    best_subtopic, best_subtopic_score = max(
        [(label, score) for label, score in scores.items() if label[0] == best_topic],
        key=lambda item: item[1],
    )
    margin = best_topic_score - second_topic_score
    confidence = 0.45
    if best_topic_score > 0:
        confidence = min(0.98, max(0.45, margin / best_topic_score))
    reasons = [f"topic:{best_topic}={best_topic_score}", f"subtopic:{best_subtopic[1]}={best_subtopic_score}"] + reasons[:4]
    if len(ranked_topics) > 1:
        reasons.append(f"runner-up:{ranked_topics[1][0]}={second_topic_score}")

    return (best_subtopic[0], best_subtopic[1], round(confidence, 3), reasons)


def make_title(qnum: int, question_text: str) -> str:
    flat = re.sub(r"\s+", " ", question_text).strip()
    if not flat:
        return f"Question {qnum}"
    short = flat[:90]
    if len(flat) > 90:
        short = short.rstrip() + "..."
    return f"Q{qnum}: {short}"


def tz_sort_value(paper_label: str) -> int:
    m = re.search(r"TZ(\d)", paper_label)
    if not m:
        return 999
    return int(m.group(1))


def id_without_tz(rec_id: str) -> str:
    return re.sub(r"_tz\d+(?=_q\d+(?:_[a-z]+)?$)", "", rec_id)


def parse_id_parts(rec_id: str) -> Optional[Tuple[str, str, str]]:
    m = re.match(r"^(?P<session>[a-z0-9]+)_p(?P<paper>\d+)(?:_tz\d+)?_q(?P<q>\d+)(?:_[a-z]+)?$", rec_id)
    if not m:
        return None
    return (m.group("session"), m.group("paper"), m.group("q"))


def normalized_similarity_text(text: str) -> str:
    t = text.lower().replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def tz_from_paper_label(paper_label: str) -> str:
    m = re.search(r"TZ(\d)", paper_label)
    return m.group(1) if m else "none"


def remove_sl_hl_overlaps(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[Tuple[str, str, str, str], List[Dict[str, object]]] = {}
    for rec in records:
        key = (
            str(rec.get("session_code", "")),
            str(rec.get("paper_type", "")),
            tz_from_paper_label(str(rec.get("paper", ""))),
            str(rec.get("question_number", "")),
        )
        grouped.setdefault(key, []).append(rec)

    to_remove: set[str] = set()
    for bucket in grouped.values():
        hls = [r for r in bucket if str(r.get("level", "")) == "HL"]
        sls = [r for r in bucket if str(r.get("level", "")) == "SL"]
        if not hls or not sls:
            continue

        for sl in sls:
            sl_q = normalized_similarity_text(str(sl.get("question_text", "")))
            sl_a = normalized_similarity_text(str(sl.get("answer_text", "")))
            sl_marks = int(sl.get("marks", 0) or 0)
            duplicate = False

            for hl in hls:
                hl_q = normalized_similarity_text(str(hl.get("question_text", "")))
                hl_a = normalized_similarity_text(str(hl.get("answer_text", "")))
                hl_marks = int(hl.get("marks", 0) or 0)

                q_ratio = text_similarity(sl_q, hl_q)
                a_ratio = text_similarity(sl_a, hl_a)
                same_marks = sl_marks == hl_marks

                if q_ratio >= 0.95 and (a_ratio >= 0.9 or same_marks):
                    duplicate = True
                    break

            if duplicate:
                to_remove.add(str(sl.get("id", "")))

    return [r for r in records if str(r.get("id", "")) not in to_remove]


def remove_global_sl_exact_question_duplicates(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    hl_question_sigs = {
        normalize_for_dedupe(str(rec.get("question_text", "")))
        for rec in records
        if str(rec.get("level", "")) == "HL"
    }

    out: List[Dict[str, object]] = []
    for rec in records:
        if str(rec.get("level", "")) != "SL":
            out.append(rec)
            continue
        sig = normalize_for_dedupe(str(rec.get("question_text", "")))
        if sig and sig in hl_question_sigs:
            continue
        out.append(rec)
    return out


def build_image_index(kind: str) -> Dict[str, List[str]]:
    folder = PROCESSED_IMAGES_DIR / kind
    index: Dict[str, List[Tuple[int, str]]] = {}
    if not folder.exists():
        return {}

    for img in folder.glob("*.png"):
        stem = img.stem
        m = re.match(r"^(?P<id>.+)_p(?P<page>\d+)$", stem)
        if m:
            rec_id = m.group("id")
            page = int(m.group("page"))
        else:
            # Some generated images are single-page captures named without _p suffix.
            rec_id = stem
            page = 1
        rel = str(Path("images") / kind / img.name)
        index.setdefault(rec_id, []).append((page, rel))

    out: Dict[str, List[str]] = {}
    for rec_id, items in index.items():
        items.sort(key=lambda pair: pair[0])
        out[rec_id] = [rel for _, rel in items]
    return out


def resolve_image_paths(rec_id: str, index: Dict[str, List[str]]) -> List[str]:
    if rec_id in index:
        return index[rec_id]

    no_tz = id_without_tz(rec_id)
    if no_tz in index:
        return index[no_tz]

    parts = parse_id_parts(rec_id)
    if parts is None:
        return []

    session, paper, qnum = parts
    fallback_re = re.compile(rf"^{re.escape(session)}_p{re.escape(paper)}(?:_tz\d+)?_q{re.escape(qnum)}(?:_[a-z]+)?$")
    candidates = [key for key in index.keys() if fallback_re.match(key)]
    if not candidates:
        return []

    candidates.sort(key=lambda key: (0 if "_tz" in key else 1, key))
    return index[candidates[0]]


def build() -> Dict[str, object]:
    papers = sorted(PAPERS_DIR.glob("*.pdf"))
    markschemes = sorted(MARKSCHEMES_DIR.glob("*.pdf"))

    ms_map = {pair_key(p.name): p for p in markschemes}
    records: List[Dict[str, object]] = []

    for paper_path in papers:
        key = pair_key(paper_path.name)
        ms_path = ms_map.get(key)
        if not ms_path:
            continue

        meta = parse_meta(paper_path)
        q_map = parse_questions_from_paper(paper_path)
        a_map = parse_answers_from_markscheme(ms_path)

        for qn in sorted(q_map.keys()):
            q = q_map[qn]
            ans = a_map.get(qn, "Markscheme content not extracted for this question.")
            topic, subtopic, confidence, reasons = classify_topic(str(q["question_text"]), ans)

            tz_part = f"_tz{meta.tz}" if meta.tz is not None else ""
            rec_id = f"{meta.session_code}_p{meta.paper_no}{tz_part}_q{qn}_{meta.level.lower()}"

            records.append(
                {
                    "id": rec_id,
                    "paper": meta.paper_label,
                    "session": meta.session,
                    "session_code": meta.session_code,
                    "paper_type": meta.paper_type,
                    "level": meta.level,
                    "question_number": str(qn),
                    "title": make_title(qn, str(q["question_text"])),
                    "topic": topic,
                    "subtopic": subtopic,
                    "topic_confidence": confidence,
                    "topic_reason": reasons,
                    "question_text": q["question_text"],
                    "answer_text": ans,
                    "marks": q["marks"],
                    "source": {
                        "paper_file": paper_path.name,
                        "markscheme_file": ms_path.name,
                    },
                }
            )

    records.sort(
        key=lambda r: (
            r.get("session_code", ""),
            int(str(r.get("paper_type", "Paper 0")).split()[-1]),
            tz_sort_value(str(r.get("paper", ""))),
            int(r["question_number"]),
        )
    )

    # Remove exact repeated question+answer pairs across sessions/variants.
    deduped: List[Dict[str, object]] = []
    seen: set[Tuple[str, str]] = set()
    for rec in records:
        sig = (
            normalize_for_dedupe(str(rec.get("question_text", ""))),
            normalize_for_dedupe(str(rec.get("answer_text", ""))),
        )
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(rec)

    deduped = remove_sl_hl_overlaps(deduped)
    deduped = remove_global_sl_exact_question_duplicates(deduped)

    q_image_index = build_image_index("questions")
    ms_image_index = build_image_index("markschemes")
    for rec in deduped:
        rec_id = str(rec.get("id", ""))
        rec["question_image_paths"] = resolve_image_paths(rec_id, q_image_index)
        rec["markscheme_image_paths"] = resolve_image_paths(rec_id, ms_image_index)

    sessions = sorted({str(q.get("session", "")) for q in deduped if q.get("session")})

    return {
        "course": "IB Mathematics: Analysis and Approaches HL",
        "sessions": sessions,
        "questions": deduped,
    }


def main() -> None:
    payload = build()
    OUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['questions'])} questions to {OUT_FILE}")


if __name__ == "__main__":
    main()
