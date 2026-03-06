#!/usr/bin/env python3
"""Generate IB-style draft worked markschemes for tutoring questions."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_FILE = ROOT / "data" / "tutoring" / "processed" / "questions.json"
OUT_FILE = ROOT / "data" / "tutoring" / "processed" / "markschemes.json"

SUPERSCRIPT_MAP = str.maketrans({"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻", "+": "⁺"})
SUBSCRIPT_MAP = str.maketrans({"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉", "-": "₋", "+": "₊"})


def find_total_marks(text: str) -> int:
    m = re.search(r"\(Total\s+(\d+)\s+marks?\)", text, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    marks = [int(x) for x in re.findall(r"\((\d+)\)", text)]
    if marks:
        return max(sum(marks), max(marks))
    return 4


def extract_parts(text: str) -> List[Tuple[str, str]]:
    # Only treat standalone part labels like "(a) ...", not function notation f(x).
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


def detect_method(prompt: str) -> str:
    p = prompt.lower()
    if "solve" in p:
        return "solve"
    if "show that" in p or "prove" in p:
        return "prove"
    if "expand" in p or "expansion" in p or "binomial" in p or "coefficient" in p or "term in" in p:
        return "binomial"
    if "differentiat" in p or "derivative" in p:
        return "differentiate"
    if "integrat" in p or "integral" in p:
        return "integrate"
    if "complex" in p or "arg" in p or "modulus" in p or "conjugate" in p:
        return "complex"
    if "sequence" in p or "series" in p or "sum" in p or "u_n" in p or "s_n" in p:
        return "sequence"
    if "log" in p or "ln" in p or "exponential" in p:
        return "logs"
    if "inverse" in p or "f-1" in p:
        return "inverse"
    return "general"


def normalize_prompt(prompt: str) -> str:
    text = unicodedata.normalize("NFKC", prompt)
    text = re.sub(r"\(Total\s+\d+\s+marks?\)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\(\d+\)", " ", text)
    text = re.sub(r"\bIB\s*Maths?\s*\d+\b", " ", text, flags=re.IGNORECASE)
    text = text.replace("\ufffd", " ").replace("□", " ")
    text = re.sub(r"[^\x20-\x7E\u00A0-\u024F\u0370-\u03FF\u2010-\u206F\u2070-\u209F\u2200-\u22FF]+", " ", text)
    text = text.replace("<=", "≤").replace(">=", "≥").replace("!=", "≠").replace("+/-", "±")
    text = re.sub(r"\bsqrt\b", "√", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpi\b", "π", text, flags=re.IGNORECASE)
    text = re.sub(r"\binfinity\b", "∞", text, flags=re.IGNORECASE)
    text = re.sub(r"\bu_n\b", "uₙ", text)
    text = re.sub(r"\bs_n\b", "Sₙ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bx([0-9])\b", lambda m: f"x{m.group(1).translate(SUPERSCRIPT_MAP)}", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def worked_steps_for_prompt(prompt: str, marks: int, context: str = "") -> List[str]:
    method = detect_method(f"{context} {prompt}")
    expr = normalize_prompt(prompt)[:120]

    templates: Dict[str, List[str]] = {
        "solve": [
            "METHOD 1",
            f"Start with: {expr}",
            "Rearrange to standard form: ax^2 + bx + c = 0 (or equivalent).",
            "Solve using factorisation / substitution / inverse operations.",
            "For quadratics: x = (-b ± √(b² - 4ac)) / (2a).",
            "Check domain/restrictions and reject invalid roots.",
            "Final answer: valid solution set.",
            "",
            "METHOD 2",
            "Alternative route: solve simultaneously after substitution or use graph/intersection (x-, y-).",
            "Confirm both methods give the same valid value(s).",
        ],
        "prove": [
            "METHOD 1",
            f"Given: {expr}",
            "Start from one side only and simplify line by line.",
            "Use identities/algebra legally at each step.",
            "Reach target form exactly. Therefore, statement is true.",
            "",
            "METHOD 2",
            "Start from the opposite side (or use contradiction).",
            "Show both sides reduce to the same canonical expression.",
        ],
        "binomial": [
            "METHOD 1 (general term)",
            f"Given: {expr}",
            "Use Tᵣ₊₁ = C(n,r) · a^(n-r) · b^r.",
            "Match powers to find r (for required xᵏ term).",
            "Substitute r and simplify coefficient + term.",
            "Write final required term/coefficient.",
            "",
            "METHOD 2 (partial expansion)",
            "Expand only the needed leading terms and read required coefficient.",
            "Cross-check with METHOD 1 result.",
        ],
        "differentiate": [
            "METHOD 1",
            f"Given: {expr}",
            "Apply chain/product/quotient rules as needed.",
            "d/dx[xⁿ] = n·xⁿ⁻¹, d/dx[eˣ] = eˣ, d/dx[ln x] = 1/x.",
            "Simplify f'(x), then substitute required x-values.",
            "State final derivative/result.",
            "",
            "METHOD 2 (first principles when requested)",
            "f′(x) = lim(h→0) (f(x+h)-f(x))/h.",
            "Expand, cancel, factor h, then take the limit.",
        ],
        "integrate": [
            "METHOD 1",
            f"Given: {expr}",
            "Integrate term-by-term or by substitution.",
            "∫xⁿ dx = xⁿ⁺¹/(n+1) + C,  ∫eˣ dx = eˣ + C,  ∫(1/x)dx = ln|x| + C.",
            "Apply limits if definite integral.",
            "State exact final value.",
            "",
            "METHOD 2",
            "Use geometric/area interpretation when question permits.",
            "Confirm consistency with analytic result.",
        ],
        "complex": [
            "METHOD 1 (Cartesian form)",
            f"Given: {expr}",
            "Write z = a + bi and equate real/imaginary parts.",
            "|z| = √(a² + b²),  arg(z) = atan(b/a) (adjust quadrant).",
            "Use z̄ = a - bi where needed.",
            "State final result in requested form.",
            "",
            "METHOD 2 (polar form)",
            "Write z = r(cosθ + i sinθ) = r cisθ.",
            "Use De Moivre: z^n = r^n cis(nθ), then convert back if needed.",
        ],
        "sequence": [
            "METHOD 1 (formula route)",
            f"Given: {expr}",
            "Arithmetic: uₙ = u₁ + (n-1)d,  Sₙ = n/2[2u₁ + (n-1)d].",
            "Geometric: uₙ = u₁r^(n-1),  Sₙ = u₁(1-rⁿ)/(1-r), r ≠ 1.",
            "Substitute known values and solve systematically.",
            "State required u_n / S_n / n value.",
            "",
            "METHOD 2 (simultaneous equations)",
            "Use two given terms/sums to form simultaneous equations in unknowns.",
            "Solve and verify by substitution into original sequence relation.",
        ],
        "logs": [
            "METHOD 1 (log laws)",
            f"Given: {expr}",
            "Use log rules: log(ab)=log a + log b, log(a^k)=k log a.",
            "Convert to linear/quadratic form in one variable.",
            "Apply domain: log(A) defined only if A > 0.",
            "State valid solution(s) only.",
            "",
            "METHOD 2 (exponential form)",
            "Use logₐx = y  ⇔  aʸ = x.",
            "Solve in exponential form, then check domain.",
        ],
        "inverse": [
            "METHOD 1",
            f"Given: {expr}",
            "Set y = f(x), swap x and y.",
            "Rearrange to y = ... explicitly.",
            "State domain(f) and range(f) so inverse is valid.",
            "Final: f⁻¹(x) with restrictions.",
            "",
            "METHOD 2",
            "Check by composition: f(f⁻¹(x)) = x and f⁻¹(f(x)) = x.",
        ],
        "general": [
            "METHOD 1",
            f"Given: {expr}",
            "Set up equations with clear definitions of variables.",
            "Show algebraic manipulation line-by-line.",
            "Simplify and check restrictions/units.",
            "State final answer clearly.",
            "",
            "METHOD 2",
            "Use an equivalent algebraic route or substitution approach.",
            "Cross-check final value with METHOD 1.",
        ],
    }

    steps = templates[method]
    if marks <= 2:
        compact = []
        for line in steps:
            if line.startswith("METHOD 2"):
                break
            if line:
                compact.append(line)
        return compact[:6]
    return steps


def assign_part_marks(parts: List[Tuple[str, str]], total: int, original: str) -> List[int]:
    explicit = [int(x) for x in re.findall(r"\((\d+)\)", original)]
    if explicit and len(explicit) >= len(parts):
        # Prefer nearby explicit marks (common in worksheet formatting).
        return explicit[: len(parts)]

    base = total // len(parts)
    rem = total % len(parts)
    return [base + (1 if i < rem else 0) for i in range(len(parts))]


def build_markscheme_entry(question: Dict[str, object]) -> Dict[str, object]:
    qtext = str(question.get("question_text", ""))
    total_marks = find_total_marks(qtext)
    parts = extract_parts(qtext)
    part_marks = assign_part_marks(parts, total_marks, qtext)

    part_entries = []
    for (label, prompt), marks in zip(parts, part_marks):
        lines = worked_steps_for_prompt(prompt, marks, context=qtext)
        part_entries.append(
            {
                "part": label,
                "marks": marks,
                "prompt_excerpt": prompt[:180],
                "worked_steps": lines,
            }
        )

    text_lines = []
    for part in part_entries:
        text_lines.append(f"Part ({part['part']})")
        for row in part["worked_steps"]:
            text_lines.append(row)
        text_lines.append("")

    return {
        "id": question.get("id"),
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


def main() -> None:
    payload = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])
    entries = [build_markscheme_entry(q) for q in questions]

    out = {
        "course": "IB Mathematics AA HL - Tutoring Questions",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": "Auto-generated IB-style worked-solution drafts. Review and edit before formal use.",
        "questions": entries,
    }
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} draft markschemes to {OUT_FILE}")


if __name__ == "__main__":
    main()
