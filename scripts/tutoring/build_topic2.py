#!/usr/bin/env python3
"""Build Topic 2 Functions tutoring bank: parse PDF, crop images, generate markschemes, update JSON files."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from html import escape
from pathlib import Path
from textwrap import wrap
from typing import Dict, List, Optional, Tuple

import sys

ROOT = Path(__file__).resolve().parents[2]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore
from pypdf import PdfReader  # type: ignore

SOURCE_PDF = Path("/Users/s933863@aics.espritscholen.nl/Documents/Tutoring Questions/Topic 2 Functions/Math_SL_Functions_Equations_2023.pdf")
QUESTIONS_JSON = ROOT / "data" / "tutoring" / "processed" / "questions.json"
MARKSCHEMES_JSON = ROOT / "data" / "tutoring" / "processed" / "markschemes.json"
IMAGES_Q_DIR = ROOT / "data" / "tutoring" / "processed" / "images" / "questions"
IMAGES_MS_DIR = ROOT / "data" / "tutoring" / "processed" / "images" / "markschemes"

TOPIC = "Functions"
UNIT = "Topic 2 Functions"
SOURCE_FILE = SOURCE_PDF.name

SUPERSCRIPT_MAP = str.maketrans({"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻", "+": "⁺"})


# ── subtopic inference ───────────────────────────────────────────────────────

def infer_subtopic(text: str) -> str:
    t = text.lower()
    if re.search(r"\bcomposite\b|g\s*[∘°]\s*f|g\(f\(|\bf\(\s*g\(", t):
        return "Composite and inverse functions"
    if re.search(r"\binverse\b|f\s*[\-−]?\s*1\s*\(|f\^[\-−]1|f⁻¹|g\s*[\-−]?\s*1\s*\(", t):
        return "Composite and inverse functions"
    if re.search(r"\bquadratic\b|ax\^2|kx\^2|two equal roots?\b|discriminant\b|vertex\b|complete the square", t):
        return "Quadratic functions"
    if re.search(r"\btranslat|reflect|stretch|transform|horizontal shift|vertical shift", t):
        return "Transformations of functions"
    if re.search(r"\bexponential\b|bacteria\b|population\b|growth\b|decay\b|per annum\b|compound interest\b|forest fire\b", t):
        return "Exponential and logarithmic functions"
    if re.search(r"\bln\b|\blog\b|logarithm", t):
        return "Exponential and logarithmic functions"
    if re.search(r"\bsin\b|\bcos\b|\btan\b|\btrigonometric\b|\bsinusoidal\b|\bamplitude\b|\bperiod\b", t):
        return "Trigonometric functions"
    if re.search(r"\bdomain\b|\brange\b|\bpiecewise\b|\basymptote\b|\bhorizontal asymptote\b", t):
        return "Domain, range and asymptotes"
    return "Functions and equations"


# ── question extraction from PDF ─────────────────────────────────────────────

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
        if re.match(r"^\d+\s*\|\s*P a g e", l):
            continue
        if re.match(r"^\d+\s*\|\s*P\s*a\s*g\s*e", l):
            continue
        if "TopClassTutors" in l or "IB Revision Courses" in l:
            continue
        lines.append(l)
    return normalize_ws("\n".join(lines))


def split_questions(text: str) -> List[Dict[str, str]]:
    lines = text.splitlines()
    current_num: Optional[int] = None
    current_lines: List[str] = []
    output: List[Dict[str, str]] = []

    def flush() -> None:
        if current_num is None:
            return
        body = normalize_ws("\n".join(current_lines))
        if len(body) < 15:
            return
        output.append({"question_number": str(current_num), "question_text": body})

    for line in lines:
        m = re.match(r"^(?P<num>\d{1,2})\.\s+", line)
        if m:
            flush()
            current_num = int(m.group("num"))
            current_lines = [line]
        elif current_num is not None:
            current_lines.append(line)
    flush()
    return output


# ── image cropping ────────────────────────────────────────────────────────────

@dataclass
class StartPos:
    qnum: int
    page: int
    y: float


def detect_starts(doc: fitz.Document) -> List[StartPos]:
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
                m = re.match(r"^(?P<num>\d{1,2})\.\s+", line_text)
                qnum: Optional[int] = None
                if m:
                    qnum = int(m.group("num"))
                else:
                    m_dot = re.match(r"^(?P<num>\d{1,2})\.$", line_text)
                    if m_dot:
                        pending_num = int(m_dot.group("num"))
                        pending_y = y
                        pending_x = x
                        qnum = pending_num
                    m_pending = re.match(r"^(?P<num>\d{1,2})$", line_text)
                    if m_pending:
                        pending_num = int(m_pending.group("num"))
                        pending_y = y
                        pending_x = x
                        continue
                    if pending_num is not None:
                        if (pending_x is not None and pending_x < 80) and re.match(r"^[A-Za-z(]", line_text):
                            qnum = pending_num
                            y = pending_y if pending_y is not None else y
                        pending_num = None
                        pending_y = None
                        pending_x = None
                if qnum is None:
                    continue
                if qnum < 1 or qnum > 120:
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
            top = max(30.0, s.y - 8.0)
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
        if str(qnum) + "." in page_text:
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


# ── markscheme generation ─────────────────────────────────────────────────────

def find_total_marks(text: str) -> int:
    m = re.search(r"\(Total\s+(\d+)\s+marks?\)", text, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    marks = [int(x) for x in re.findall(r"\((\d+)\)", text)]
    if marks:
        return max(sum(marks), max(marks))
    return 4


def extract_parts(text: str) -> List[Tuple[str, str]]:
    matches = list(re.finditer(r"(?:(?<=^)|(?<=\n)|(?<=\s))\(([a-e])\)(?=\s)", text))
    if not matches:
        body = re.sub(r"\s+", " ", text).strip()
        return [("a", body)]
    parts: List[Tuple[str, str]] = []
    for i, m in enumerate(matches):
        label = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = re.sub(r"\s+", " ", text[start:end]).strip()
        if body:
            parts.append((label, body))
    return parts or [("a", re.sub(r"\s+", " ", text).strip())]


def normalize_prompt(prompt: str) -> str:
    text = unicodedata.normalize("NFKC", prompt)
    text = re.sub(r"\(Total\s+\d+\s+marks?\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\d+\)", " ", text)
    text = re.sub(r"\bIB\s*Maths?\s*\d+\b", " ", text, flags=re.IGNORECASE)
    text = text.replace("<=", "≤").replace(">=", "≥").replace("!=", "≠").replace("+/-", "±")
    text = re.sub(r"\bsqrt\b", "√", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpi\b", "π", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def detect_method(prompt: str) -> str:
    p = prompt.lower()
    if "composite" in p or "g(f(" in p or "f(g(" in p or "°" in p:
        return "composite"
    if "inverse" in p or "f-1" in p or "f⁻¹" in p or "g-1" in p:
        return "inverse"
    if "solve" in p or "equal roots" in p or "discriminant" in p:
        return "solve"
    if "expand" in p or "binomial" in p:
        return "binomial"
    if "differentiat" in p or "derivative" in p or "f'(" in p:
        return "differentiate"
    if "integrat" in p or "integral" in p or "area" in p:
        return "integrate"
    if "log" in p or "ln" in p or "exponential" in p:
        return "logs"
    if "transform" in p or "translat" in p or "reflect" in p or "stretch" in p:
        return "transform"
    if "domain" in p or "range" in p or "asymptote" in p:
        return "domain"
    if "sketch" in p or "graph" in p or "intercept" in p or "maximum" in p or "minimum" in p:
        return "graph"
    return "general"


def compact_symbolic_lines(prompt: str, marks: int, context: str = "") -> List[str]:
    method = detect_method(f"{context} {prompt}")
    templates: Dict[str, List[str]] = {
        "composite": ["(g∘f)(x) = g(f(x))", "substitute f(x) into g", "simplify"],
        "inverse": ["y = f(x)", "swap x and y", "solve for y", "f⁻¹(x) = ..."],
        "solve": ["ax²+bx+c=0", "Δ=b²-4ac", "x=(-b±√Δ)/(2a)", "x ∈ domain"],
        "binomial": ["Tᵣ₊₁=C(n,r)·a^(n-r)·b^r", "match power", "substitute r", "simplify"],
        "differentiate": ["d/dx[xⁿ]=n·xⁿ⁻¹", "d/dx[eˣ]=eˣ, d/dx[lnx]=1/x", "f′(x)=..."],
        "integrate": ["∫xⁿdx=xⁿ⁺¹/(n+1)+C", "∫eˣdx=eˣ+C", "evaluate bounds"],
        "logs": ["log(ab)=loga+logb", "log(aᵏ)=kloga", "logₐx=y ⇔ aʸ=x", "argument>0"],
        "transform": ["f(x-h)+k: shift right h, up k", "af(x): vertical stretch a", "f(bx): horizontal stretch 1/b"],
        "domain": ["set domain: exclude values where undefined", "range: consider shape/asymptotes"],
        "graph": ["find intercepts: f(x)=0, f(0)", "find vertex/turning point", "note symmetry/asymptotes"],
        "general": ["equation setup", "algebra simplify", "check domain/restriction"],
    }
    lines = templates.get(method, templates["general"])[:]
    if marks <= 2:
        lines = lines[:2]
    return lines


def assign_part_marks(parts: List[Tuple[str, str]], total: int, original: str) -> List[int]:
    explicit = [int(x) for x in re.findall(r"\((\d+)\)", original)]
    if explicit and len(explicit) >= len(parts):
        return explicit[: len(parts)]
    base = total // len(parts)
    rem = total % len(parts)
    return [base + (1 if i < rem else 0) for i in range(len(parts))]


def build_markscheme_entry(question: Dict) -> Dict:
    qtext = str(question.get("question_text", ""))
    total_marks = find_total_marks(qtext)
    parts = extract_parts(qtext)
    part_marks = assign_part_marks(parts, total_marks, qtext)
    part_entries = []
    for (label, prompt), marks in zip(parts, part_marks):
        lines = compact_symbolic_lines(prompt, marks, context=qtext)
        part_entries.append({
            "part": label,
            "marks": marks,
            "prompt_excerpt": prompt[:180],
            "worked_steps": lines,
        })
    text_lines = []
    qn = question.get("question_number")
    if qn:
        text_lines.append(f"{qn}.")
    for part in part_entries:
        text_lines.append(f"({part['part']})")
        roman = ["(i)", "(ii)", "(iii)", "(iv)", "(v)", "(vi)"]
        for i, row in enumerate(part["worked_steps"]):
            prefix = roman[i] if i < len(roman) else f"({i+1})"
            text_lines.append(f"  {prefix}  {row}")
        text_lines.append("")
    return {
        "id": question["id"],
        "title": question.get("title"),
        "source_file": question.get("source_file"),
        "topic": question.get("topic"),
        "subtopic": question.get("subtopic"),
        "question_number": question.get("question_number"),
        "total_marks": total_marks,
        "parts": part_entries,
        "worked_solution_text": "\n".join(text_lines).strip(),
        "draft": True,
    }


# ── SVG markscheme image renderer ────────────────────────────────────────────

def render_svg(title: str, text: str) -> str:
    wrapped: list[str] = []
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
        is_part = line.startswith("Part (")
        is_method = line.startswith("METHOD ")
        looks_math = any(token in line for token in ["=", "^", "√", "∫", "d/dx", "f′", "log", "±", "⁻¹"])
        weight = "700" if (is_part or is_method) else "500"
        fill = "#1d2f57" if (is_part or is_method) else "#1f2a44"
        font_family = "Cambria Math, STIX Two Math, Times New Roman, serif" if looks_math else "Arial, Helvetica, sans-serif"
        lines_svg.append(
            f'<text x="70" y="{y}" font-family="{font_family}" '
            f'font-size="28" font-weight="{weight}" fill="{fill}">{content}</text>'
        )
        y += line_height
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect x="20" y="20" width="{width-40}" height="{height-40}" rx="18" ry="18" fill="#f5f7fb" stroke="#c6cfdf" stroke-width="2"/>
  <rect x="20" y="20" width="{width-40}" height="54" rx="18" ry="18" fill="#e7eef9" stroke="#c6cfdf" stroke-width="2"/>
  <text x="50" y="57" font-family="Arial, Helvetica, sans-serif" font-size="36" font-weight="700" fill="#213a6a">Markscheme answer</text>
  <text x="70" y="110" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#243451">{escape(title)}</text>
  {''.join(lines_svg)}
</svg>"""


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    IMAGES_Q_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_MS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Extract questions from PDF using pypdf
    reader = PdfReader(str(SOURCE_PDF))
    raw_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    clean_text = cleanup_text(raw_text)
    raw_questions = split_questions(clean_text)
    print(f"Parsed {len(raw_questions)} questions from {SOURCE_PDF.name}")

    # 2. Build question records with subtopics
    stem = SOURCE_PDF.stem.lower().replace(" ", "_")
    new_questions = []
    for q in raw_questions:
        qn = q["question_number"]
        qid = f"t2_{stem}_q{qn}"
        subtopic = infer_subtopic(q["question_text"])
        new_questions.append({
            "id": qid,
            "unit": UNIT,
            "topic": TOPIC,
            "subtopic": subtopic,
            "source_file": SOURCE_FILE,
            "question_number": qn,
            "title": f"Q{qn}",
            "question_text": q["question_text"],
            "question_image_paths": [],
        })

    # 3. Crop question images using fitz
    fitz_doc = fitz.open(str(SOURCE_PDF))
    starts = detect_starts(fitz_doc)
    print(f"Detected {len(starts)} question start positions in PDF")

    for q in new_questions:
        qnum = int(q["question_number"])
        out_prefix = IMAGES_Q_DIR / q["id"]
        paths = crop_question(fitz_doc, starts, qnum, out_prefix)
        if not paths:
            paths = fallback_page_image(fitz_doc, q["question_text"], qnum, out_prefix)
        q["question_image_paths"] = paths
        status = f"{len(paths)} image(s)" if paths else "NO IMAGES"
        print(f"  Q{qnum}: {status}")
    fitz_doc.close()

    # 4. Load existing questions.json, remove any old Topic 2 entries, append new ones
    q_payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    existing_qs = q_payload.get("questions", [])
    existing_qs = [q for q in existing_qs if q.get("unit") != UNIT]
    existing_qs.extend(new_questions)
    q_payload["questions"] = existing_qs
    QUESTIONS_JSON.write_text(json.dumps(q_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Updated questions.json: now {len(existing_qs)} total questions")

    # 5. Generate markschemes for new questions
    ms_payload = json.loads(MARKSCHEMES_JSON.read_text(encoding="utf-8"))
    existing_ms = ms_payload.get("questions", [])
    existing_ms = [m for m in existing_ms if m.get("id", "").startswith("t2_") is False]
    # Remove any t2_ entries
    existing_ms = [m for m in existing_ms if not str(m.get("id", "")).startswith("t2_")]

    new_markschemes = []
    for q in new_questions:
        entry = build_markscheme_entry(q)
        # Render SVG
        svg = render_svg(str(entry["title"]), str(entry["worked_solution_text"]))
        svg_file = IMAGES_MS_DIR / f"{q['id']}.svg"
        svg_file.write_text(svg, encoding="utf-8")
        entry["markscheme_image_paths"] = [f"images/markschemes/{q['id']}.svg"]
        new_markschemes.append(entry)

    existing_ms.extend(new_markschemes)
    ms_payload["questions"] = existing_ms
    MARKSCHEMES_JSON.write_text(json.dumps(ms_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Updated markschemes.json: now {len(existing_ms)} total entries")
    print(f"Topic 2 done: {len(new_questions)} questions, {len(new_markschemes)} markschemes")


if __name__ == "__main__":
    main()
