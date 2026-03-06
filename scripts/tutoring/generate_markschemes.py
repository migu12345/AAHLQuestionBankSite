#!/usr/bin/env python3
"""Generate IB-style draft worked markschemes for tutoring questions."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_FILE = ROOT / "data" / "tutoring" / "processed" / "questions.json"
OUT_FILE = ROOT / "data" / "tutoring" / "processed" / "markschemes.json"


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
    if "expand" in p or "binomial" in p or "coefficient" in p or "term in" in p:
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


def worked_steps_for_prompt(prompt: str, marks: int) -> List[str]:
    method = detect_method(prompt)
    expr = re.sub(r"\s+", " ", prompt).strip()[:120]

    templates: Dict[str, List[str]] = {
        "solve": [
            f"Step 1: Start from the given equation ({expr}) and rearrange into a standard form.",
            "Step 2: Use substitution/factorisation/inverse operations to isolate the unknown.",
            "Step 3: Solve all candidates and reject invalid roots using stated restrictions.",
            "Final answer: state the valid solution set only.",
        ],
        "prove": [
            f"Step 1: Begin from the required statement context: {expr}.",
            "Step 2: Apply valid identities and simplify each line clearly.",
            "Step 3: Arrive exactly at the target expression with no missing steps.",
            "Conclusion: required result shown.",
        ],
        "binomial": [
            f"Step 1: Use binomial theorem on the given expression: {expr}.",
            "Step 2: Write general term T_(r+1) = nCr * a^(n-r) * b^r and apply the requested condition.",
            "Step 3: Compute the correct coefficient/term and simplify fully.",
            "Final answer: required term/expansion/coefficient in simplest form.",
        ],
        "differentiate": [
            f"Step 1: From {expr}, choose the correct derivative rules.",
            "Step 2: Differentiate term-by-term with clear chain/product/quotient steps.",
            "Step 3: Simplify and evaluate any required values/conditions.",
            "Final answer: derivative/result in final simplified form.",
        ],
        "integrate": [
            f"Step 1: Set up integration from the given form: {expr}.",
            "Step 2: Integrate using the correct technique (standard/substitution/parts).",
            "Step 3: Apply limits (if any) and simplify exactly.",
            "Final answer: exact integral value/expression.",
        ],
        "complex": [
            f"Step 1: Rewrite the complex expression from the prompt ({expr}) in a suitable form.",
            "Step 2: Apply the required operation (modulus/argument/conjugate/powers).",
            "Step 3: Simplify and enforce correct quadrant/sign conventions.",
            "Final answer: complex result in requested form.",
        ],
        "sequence": [
            f"Step 1: Identify the sequence model from the prompt ({expr}).",
            "Step 2: Use the relevant nth-term/sum formula and substitute known values.",
            "Step 3: Solve for the required term/index/sum and simplify.",
            "Final answer: requested sequence value.",
        ],
        "logs": [
            f"Step 1: Apply log/exponential laws to the given expression: {expr}.",
            "Step 2: Convert to a solvable equation and isolate the variable.",
            "Step 3: Check all domain restrictions (log arguments > 0).",
            "Final answer: valid value(s) only.",
        ],
        "inverse": [
            f"Step 1: Start from the function statement ({expr}) and set y = f(x).",
            "Step 2: Swap x and y, then rearrange for y explicitly.",
            "Step 3: State any domain/range restrictions for invertibility.",
            "Final answer: f^(-1)(x) with relevant constraints.",
        ],
        "general": [
            f"Step 1: Parse the requirement from the prompt: {expr}.",
            "Step 2: Apply the main method with full algebraic working.",
            "Step 3: Simplify and verify any stated restrictions.",
            "Final answer: provide the required result clearly.",
        ],
    }

    steps = templates[method]
    # Keep shorter parts concise.
    if marks <= 2:
        return [steps[0], steps[1], steps[-1]]
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
        lines = worked_steps_for_prompt(prompt, marks)
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
        text_lines.append(f"Part ({part['part']}) [{part['marks']} marks]")
        for row in part["worked_steps"]:
            text_lines.append(f"- {row}")
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
