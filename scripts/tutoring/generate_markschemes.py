#!/usr/bin/env python3
"""Generate IB-style draft worked markschemes for tutoring questions."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def detect_sequence_context(full_question_text: str) -> Dict[str, float]:
    text = normalize_prompt(full_question_text).replace("−", "-")
    out: Dict[str, float] = {}

    m_u1 = re.search(r"\bu1\s*=\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    if m_u1:
        out["u1"] = float(m_u1.group(1))

    terms = re.findall(r"\bu(\d+)\s*=\s*(-?\d+(?:\.\d+)?)", text, flags=re.IGNORECASE)
    for n_str, value_str in terms:
        out[f"u{n_str}"] = float(value_str)

    if "u1" in out:
        for key, value in out.items():
            if key.startswith("u") and key != "u1":
                n = int(key[1:])
                if n != 1:
                    out["d"] = (value - out["u1"]) / (n - 1)
                    break
    return out


def parse_number_token(tok: str) -> Optional[float]:
    tok = tok.strip()
    if not tok:
        return None
    tok = tok.replace("−", "-")
    m_frac = re.match(r"^(-?\d+)\s*/\s*(\d+)$", tok)
    if m_frac:
        den = int(m_frac.group(2))
        if den != 0:
            return int(m_frac.group(1)) / den
    m_dec = re.match(r"^-?\d+(?:\.\d+)?$", tok)
    if m_dec:
        return float(tok)
    return None


def parse_sequence_list(text: str) -> List[float]:
    # capture patterns like "3, 9, 15, ..., 1353"
    chunks = re.split(r"[,;]", text)
    vals: List[float] = []
    for c in chunks:
        c = c.strip()
        if not c or "..." in c or "…" in c:
            continue
        m = re.search(r"(-?\d+(?:\.\d+)?)", c)
        if not m:
            continue
        vals.append(float(m.group(1)))
    return vals


def try_binomial_answers(prompt: str, context: str) -> Optional[List[str]]:
    text_prompt = normalize_prompt(prompt)
    text_all = normalize_prompt(f"{context} {prompt}")
    lines: List[str] = []

    if "number of terms" in text_prompt.lower():
        m_pow = re.search(r"\(([^()]+)\)\s*\^?\s*(\d+)", text_prompt)
        if not m_pow:
            m_pow = re.search(r"\(([^()]+)\)\s*\^?\s*(\d+)", text_all)
        if m_pow:
            n = int(m_pow.group(2))
            lines.append(f"Number of terms = n + 1 = {n + 1}")
            lines.append(f"Answer: {n + 1}")
            return lines

    if "expand" in text_prompt.lower():
        m = re.search(r"\(\s*([+-]?\d+)\s*\+\s*x\s*\)\s*\^?\s*(\d+)", text_prompt, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"\(\s*x\s*\+\s*([+-]?\d+)\s*\)\s*\^?\s*(\d+)", text_prompt, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"\(\s*([+-]?\d+)\s*\+\s*x\s*\)\s*\^?\s*(\d+)", text_all, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"\(\s*x\s*\+\s*([+-]?\d+)\s*\)\s*\^?\s*(\d+)", text_all, flags=re.IGNORECASE)
        if m:
            a = int(m.group(1))
            n = int(m.group(2))
            coeffs = [math.comb(n, r) * (a ** (n - r)) for r in range(n + 1)]
            terms: List[str] = []
            for r, c in enumerate(coeffs):
                if c == 0:
                    continue
                if r == 0:
                    term = f"{c}"
                elif r == 1:
                    term = "x" if c == 1 else "-x" if c == -1 else f"{c}x"
                else:
                    sup = str(r).translate(SUPERSCRIPT_MAP)
                    term = f"x{sup}" if c == 1 else f"-x{sup}" if c == -1 else f"{c}x{sup}"
                terms.append(term)
            expansion = " + ".join(terms).replace("+ -", "- ")
            lines.append(f"(x + {a}){str(n).translate(SUPERSCRIPT_MAP)} = {expansion}")
            lines.append(f"Answer: {expansion}")
            return lines

    m_coef = re.search(
        r"\(x\s*\+\s*(\d+)y\)\s*\^?\s*(\d+).+ax\s*\^?\s*(\d+)\s*y\s*\^?\s*(\d+)",
        text_prompt,
        flags=re.IGNORECASE,
    )
    if not m_coef:
        m_coef = re.search(
        r"\(x\s*\+\s*(\d+)y\)\s*\^?\s*(\d+).+ax\s*\^?\s*(\d+)\s*y\s*\^?\s*(\d+)",
        text_all,
        flags=re.IGNORECASE,
    )
    if m_coef:
        k = int(m_coef.group(1))
        n = int(m_coef.group(2))
        p = int(m_coef.group(3))
        q = int(m_coef.group(4))
        if p + q == n:
            a = math.comb(n, q) * (k ** q)
            lines.append(f"a = C({n},{q})·{k}{str(q).translate(SUPERSCRIPT_MAP)} = {a}")
            lines.append(f"Answer: a = {a}")
            return lines

    # Term containing x^k from (x+a)^n or (a+x)^n
    if re.search(r"term\s+containing\s+x|term\s+in\s+x", text_prompt, flags=re.IGNORECASE):
        m_target = re.search(r"x\s*([0-9]+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)", text_prompt)
        m_base = re.search(r"\(\s*x\s*\+\s*([+-]?\d+)\s*\)\s*\^?\s*(\d+)", text_all, flags=re.IGNORECASE)
        if not m_base:
            m_base = re.search(r"\(\s*([+-]?\d+)\s*\+\s*x\s*\)\s*\^?\s*(\d+)", text_all, flags=re.IGNORECASE)
        if m_target and m_base:
            raw_pow = m_target.group(1).translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789"))
            k = int(raw_pow)
            a = int(m_base.group(1))
            n = int(m_base.group(2))
            if 0 <= k <= n:
                coeff = math.comb(n, k) * (a ** (n - k))
                xk = "x" if k == 1 else f"x{str(k).translate(SUPERSCRIPT_MAP)}"
                lines.append(f"T = C({n},{k})·{a}{str(n-k).translate(SUPERSCRIPT_MAP)}·{xk}")
                lines.append(f"T = {coeff}{xk if coeff != 0 else ''}")
                lines.append(f"Answer: {coeff}{xk if coeff != 0 else ''}")
                return lines

    return None


def try_sequence_answers(prompt: str, context: str) -> Optional[List[str]]:
    p = normalize_prompt(prompt).lower().replace("−", "-")
    ctx = normalize_prompt(context).lower().replace("−", "-")
    seq = detect_sequence_context(context)
    list_vals = parse_sequence_list(context)

    lines: List[str] = []
    u1 = seq.get("u1")
    d = seq.get("d")

    # infer from explicit arithmetic list
    if len(list_vals) >= 3 and d is None:
        d1 = list_vals[1] - list_vals[0]
        d2 = list_vals[2] - list_vals[1]
        if abs(d1 - d2) < 1e-9:
            d = d1
            if u1 is None:
                u1 = list_vals[0]

    # infer geometric from explicit list
    r: Optional[float] = None
    if len(list_vals) >= 3 and abs(list_vals[0]) > 1e-12:
        r1 = list_vals[1] / list_vals[0]
        r2 = list_vals[2] / list_vals[1] if abs(list_vals[1]) > 1e-12 else None
        if r2 is not None and abs(r1 - r2) < 1e-9:
            r = r1
            if u1 is None:
                u1 = list_vals[0]

    if "common difference" in p or "find d" in p:
        if d is not None:
            lines.append(f"d = {format_number(d)}")
            lines.append(f"Answer: d = {format_number(d)}")
            return lines

    if "common ratio" in p or re.search(r"\bfind r\b", p):
        if r is not None:
            lines.append(f"r = {format_number(r)}")
            lines.append(f"Answer: r = {format_number(r)}")
            return lines

    if u1 is None:
        return None

    if "find d" in p and d is not None:
        lines.append(f"d = {format_number(d)}")
        lines.append(f"Answer: d = {format_number(d)}")
        return lines

    m_un = re.search(r"\bu(\d+)\b", p)
    if ("find u" in p or "u20" in p) and m_un and d is not None:
        n = int(m_un.group(1))
        un = u1 + (n - 1) * d
        lines.append("uₙ = u₁ + (n-1)d")
        lines.append(f"u{n} = {format_number(u1)} + {n-1}·{format_number(d)} = {format_number(un)}")
        lines.append(f"Answer: u{n} = {format_number(un)}")
        return lines

    if ("find u" in p or "10th term" in p or "nth term" in p) and m_un and r is not None:
        n = int(m_un.group(1))
        un = u1 * (r ** (n - 1))
        lines.append("uₙ = u₁rⁿ⁻¹")
        lines.append(f"u{n} = {format_number(u1)}·({format_number(r)}){str(n-1).translate(SUPERSCRIPT_MAP)} = {format_number(un)}")
        lines.append(f"Answer: u{n} = {format_number(un)}")
        return lines

    m_sn = re.search(r"\bs(\d+)\b", p)
    if ("find s" in p or "s20" in p) and m_sn and d is not None:
        n = int(m_sn.group(1))
        sn = (n / 2.0) * (2 * u1 + (n - 1) * d)
        lines.append("Sₙ = n/2 [2u₁ + (n-1)d]")
        lines.append(f"S{n} = {n}/2 [2({format_number(u1)}) + {n-1}({format_number(d)})] = {format_number(sn)}")
        lines.append(f"Answer: S{n} = {format_number(sn)}")
        return lines

    if "sum to infinity" in p and r is not None and abs(r) < 1:
        s_inf = u1 / (1 - r)
        lines.append("S∞ = u₁/(1-r)")
        lines.append(f"S∞ = {format_number(u1)}/(1-{format_number(r)}) = {format_number(s_inf)}")
        lines.append(f"Answer: S∞ = {format_number(s_inf)}")
        return lines

    if re.search(r"\bfind the value of n\b", p) and d is not None:
        m_target = re.search(r"\bun\s*=\s*(-?\d+(?:\.\d+)?)", normalize_prompt(context), flags=re.IGNORECASE)
        if m_target:
            target = float(m_target.group(1))
            n_val = ((target - u1) / d) + 1 if abs(d) > 1e-12 else float("nan")
            if math.isfinite(n_val):
                lines.append(f"uₙ = u₁ + (n-1)d = {format_number(target)}")
                lines.append(f"n = (({format_number(target)} - {format_number(u1)})/{format_number(d)}) + 1 = {format_number(n_val)}")
                lines.append(f"Answer: n = {format_number(n_val)}")
                return lines

    # arithmetic sequence with known final term from listed sequence
    if "number of terms" in p and len(list_vals) >= 3 and d is not None:
        last_val_match = re.search(r"\.\.\.\s*,?\s*(-?\d+(?:\.\d+)?)", context)
        if last_val_match:
            last_val = float(last_val_match.group(1))
            n_val = ((last_val - u1) / d) + 1
            if math.isfinite(n_val):
                lines.append("uₙ = u₁ + (n-1)d")
                lines.append(f"n = (({format_number(last_val)} - {format_number(u1)})/{format_number(d)}) + 1 = {format_number(n_val)}")
                lines.append(f"Answer: number of terms = {format_number(n_val)}")
                return lines

    # compound interest
    if "compound interest" in ctx or "per annum" in ctx:
        m_principal = re.search(r"(\d+(?:\.\d+)?)\s*(?:is invested|invested)", ctx)
        m_rate = re.search(r"(\d+(?:\.\d+)?)\s*%.*per annum", ctx)
        m_years = re.search(r"after\s+(\d+)\s*(?:full\s+)?years?", p)
        if m_principal and m_rate:
            P = float(m_principal.group(1))
            r_pct = float(m_rate.group(1))
            lines.append(f"Vₙ = {format_number(P)}(1 + {format_number(r_pct/100)})ⁿ")
            if m_years:
                n = int(m_years.group(1))
                V = P * ((1 + r_pct/100) ** n)
                lines.append(f"V_{n} = {format_number(P)}(1 + {format_number(r_pct/100)}){str(n).translate(SUPERSCRIPT_MAP)} = {format_number(V)}")
                lines.append(f"Answer: {format_number(V)}")
            else:
                lines.append(f"Answer: Vₙ = {format_number(P)}(1 + {format_number(r_pct/100)})ⁿ")
            return lines

    return None


def infer_answer_lines(prompt: str, context: str) -> Optional[List[str]]:
    method = detect_method(f"{context} {prompt}")
    if method == "binomial":
        out = try_binomial_answers(prompt, context)
        if out:
            return out
    if method == "sequence":
        out = try_sequence_answers(prompt, context)
        if out:
            return out
    # Direct extraction when prompt already states required result.
    p = normalize_prompt(prompt)
    m_show = re.search(r"show that .*? is ([^.;]+)", p, flags=re.IGNORECASE)
    if m_show:
        return [f"Answer: {m_show.group(1).strip()}"]
    return None


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
        steps = compact[:6]

    answer_lines = infer_answer_lines(prompt, context)
    if answer_lines:
        steps = steps + ["", "Worked answer"] + answer_lines

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
