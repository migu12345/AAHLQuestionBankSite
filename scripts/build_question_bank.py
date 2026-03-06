#!/usr/bin/env python3
"""Build AA HL question bank from raw papers and markschemes (multi-session)."""

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

from pypdf import PdfReader  # type: ignore

PAPERS_DIR = ROOT / "data" / "raw" / "papers"
MARKSCHEMES_DIR = ROOT / "data" / "raw" / "markschemes"
OUT_FILE = ROOT / "data" / "processed" / "questions.json"
PROCESSED_IMAGES_DIR = ROOT / "data" / "processed" / "images"

FILE_PAPER_RE = re.compile(r"paper_(?P<paper>\d)", re.IGNORECASE)
FILE_TZ_RE = re.compile(r"(?:__|_)TZ(?P<tz>\d)_HL", re.IGNORECASE)
EXAM_RE = re.compile(r"\b(?P<code>[MN]\d{2})/5/MATHX/HP(?P<paper>\d)/ENG(?:/TZ(?P<tz>\d))?/XX")
PREFIX_RE = re.compile(r"^(?P<code>[mn]\d{2})_")


@dataclass
class PaperMeta:
    filename: str
    paper_no: int
    session: str
    session_code: str
    tz: Optional[int]

    @property
    def paper_type(self) -> str:
        return f"Paper {self.paper_no}"

    @property
    def paper_label(self) -> str:
        if self.tz is None:
            return f"{self.session} {self.paper_type} HL"
        return f"{self.session} {self.paper_type} TZ{self.tz} HL"


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


def classify_topic(question_text: str, answer_text: str) -> Tuple[str, str]:
    # Use question text as the primary signal; markscheme text is secondary.
    # This prevents broad markscheme terms from overriding the actual question context.
    q_text = question_text.lower().replace("-", " ")

    # Strong anchors from the question itself.
    if re.search(r"\b(permutation|combination|factorial|ncr|npr|counting principle|arrangements?)\b", q_text):
        return ("Statistics and Probability", "Discrete and continuous random variables")
    if re.search(r"\b(no tied finishes?|finishing orders?|possible outcomes?|possible arrangements?)\b", q_text):
        return ("Statistics and Probability", "Discrete and continuous random variables")
    if re.search(r"\b(interquartile range|quartile|box and whisker|outlier|median)\b", q_text):
        return ("Statistics and Probability", "Probability distributions")
    if re.search(r"\b(differential equation|dy/dx|separable)\b", q_text):
        return ("Calculus", "Differential equations")
    if re.search(r"\b(maclaurin|taylor series|expansion about x ?= ?0)\b", q_text):
        return ("Calculus", "Maclaurin series")
    if re.search(r"\b(integrate|integration|integral|antiderivative|area under)\b", q_text):
        return ("Calculus", "Integration")
    if re.search(r"\b(limit|lim|continuity|continuous at)\b", q_text):
        return ("Calculus", "Limits and continuity")
    if re.search(r"\b(differentiate|differentiation|derivative|chain rule|product rule|quotient rule|tangent|normal to the curve|stationary)\b", q_text):
        return ("Calculus", "Differentiation")

    # (pattern, topic/subtopic, base_weight)
    weighted_rules: List[Tuple[re.Pattern[str], Tuple[str, str], int]] = [
        # Statistics and Probability
        (
            re.compile(r"\b(permutation|combination|factorial|ncr|npr|counting principle|arrangements?)\b"),
            ("Statistics and Probability", "Discrete and continuous random variables"),
            14,
        ),
        (
            re.compile(r"\b(no tied finishes?|finishing orders?|possible outcomes?|possible arrangements?)\b"),
            ("Statistics and Probability", "Discrete and continuous random variables"),
            12,
        ),
        (
            re.compile(r"\b(interquartile range|quartile|box and whisker|outlier|median)\b"),
            ("Statistics and Probability", "Probability distributions"),
            12,
        ),
        (
            re.compile(r"\b(hypothesis|null hypothesis|alternative hypothesis|p value|significance level|critical region)\b"),
            ("Statistics and Probability", "Hypothesis testing"),
            13,
        ),
        (
            re.compile(r"\b(correlation|regression|pearson|spearman|least squares)\b"),
            ("Statistics and Probability", "Correlation and regression"),
            12,
        ),
        (
            re.compile(r"\b(random variable|probability|normal distribution|binomial distribution|poisson|expected value|variance|standard deviation)\b"),
            ("Statistics and Probability", "Probability distributions"),
            9,
        ),
        (
            re.compile(r"\b(discrete|continuous|probability density|cumulative distribution|pdf|cdf)\b"),
            ("Statistics and Probability", "Discrete and continuous random variables"),
            9,
        ),
        # Calculus
        (
            re.compile(r"\b(differential equation|dy/dx|separable)\b"),
            ("Calculus", "Differential equations"),
            14,
        ),
        (
            re.compile(r"\b(maclaurin|taylor series|expansion about x ?= ?0)\b"),
            ("Calculus", "Maclaurin series"),
            14,
        ),
        (
            re.compile(r"\b(integrat|definite integral|indefinite integral|area under|antiderivative)\b"),
            ("Calculus", "Integration"),
            11,
        ),
        (
            re.compile(r"\b(limit|lim|continuity|continuous at)\b"),
            ("Calculus", "Limits and continuity"),
            10,
        ),
        (
            re.compile(r"\b(differentiat|derivative|chain rule|product rule|quotient rule|tangent|normal to the curve|stationary)\b"),
            ("Calculus", "Differentiation"),
            11,
        ),
        # Geometry and Trigonometry
        (
            re.compile(r"\b(vector|vectors|position vector|direction vector|i\+?j\+?k|parametric)\b"),
            ("Geometry and Trigonometry", "Vectors in 2D and 3D"),
            12,
        ),
        (
            re.compile(r"\b(line|plane|cartesian equation|normal vector|scalar product|dot product)\b"),
            ("Geometry and Trigonometry", "Lines and planes"),
            10,
        ),
        (
            re.compile(r"\b(sin|cos|tan|cot|sec|cosec|trigonometric|radian|identity)\b"),
            ("Geometry and Trigonometry", "Trigonometric identities and equations"),
            9,
        ),
        # Number and Algebra
        (
            re.compile(r"\b(complex|arg|modulus|conjugate|re\(z\)|im\(z\)|cis)\b"),
            ("Number and Algebra", "Complex numbers"),
            12,
        ),
        (
            re.compile(r"\b(arithmetic sequence|geometric sequence|u_n|s_n|recurrence|summation)\b"),
            ("Number and Algebra", "Sequences and series"),
            11,
        ),
        (
            re.compile(r"\b(induction|prove by induction)\b"),
            ("Number and Algebra", "Proof by induction"),
            14,
        ),
        (
            re.compile(r"\b(binomial theorem|binomial expansion|coefficient of x|\(a\+b\)\^n)\b"),
            ("Number and Algebra", "Binomial theorem"),
            12,
        ),
        # Functions
        (
            re.compile(r"\b(inverse function|inverse of f|one to one|bijective)\b"),
            ("Functions", "Inverse functions"),
            11,
        ),
        (
            re.compile(r"\b(logarithm|log\(|\bln\(|exponential|e\^x)\b"),
            ("Functions", "Exponential and logarithmic functions"),
            10,
        ),
        (
            re.compile(r"\b(domain|composite function|composition|range of f)\b"),
            ("Functions", "Domain, range and composition"),
            9,
        ),
        (
            re.compile(r"\b(transformation|translation|stretch|reflection|asymptote|model|modelling|f\(x\)|g\(x\))\b"),
            ("Functions", "Transformations and modelling"),
            7,
        ),
    ]

    scores: Dict[Tuple[str, str], int] = {}
    for pattern, label, weight in weighted_rules:
        q_hits = len(pattern.findall(q_text))
        if q_hits == 0:
            continue
        score = weight * (4 * q_hits)
        scores[label] = scores.get(label, 0) + score

    if not scores:
        return ("Functions", "Transformations and modelling")

    # Topic-level tie-break: favour strong non-function topics when ambiguous.
    topic_scores: Dict[str, int] = {}
    for (topic, _subtopic), score in scores.items():
        topic_scores[topic] = topic_scores.get(topic, 0) + score

    best_topic = max(topic_scores.items(), key=lambda item: item[1])[0]
    topic_candidates = [(label, score) for label, score in scores.items() if label[0] == best_topic]
    return max(topic_candidates, key=lambda item: item[1])[0]


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
    return re.sub(r"_tz\d+(?=_q\d+$)", "", rec_id)


def parse_id_parts(rec_id: str) -> Optional[Tuple[str, str, str]]:
    m = re.match(r"^(?P<session>[a-z0-9]+)_p(?P<paper>\d+)(?:_tz\d+)?_q(?P<q>\d+)$", rec_id)
    if not m:
        return None
    return (m.group("session"), m.group("paper"), m.group("q"))


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
    fallback_re = re.compile(rf"^{re.escape(session)}_p{re.escape(paper)}(?:_tz\d+)?_q{re.escape(qnum)}$")
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
            topic, subtopic = classify_topic(str(q["question_text"]), ans)

            tz_part = f"_tz{meta.tz}" if meta.tz is not None else ""
            rec_id = f"{meta.session_code}_p{meta.paper_no}{tz_part}_q{qn}"

            records.append(
                {
                    "id": rec_id,
                    "paper": meta.paper_label,
                    "session": meta.session,
                    "session_code": meta.session_code,
                    "paper_type": meta.paper_type,
                    "question_number": str(qn),
                    "title": make_title(qn, str(q["question_text"])),
                    "topic": topic,
                    "subtopic": subtopic,
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
