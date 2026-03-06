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
    matches = list(re.finditer(r"\(([a-z])\)", text))
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

    templates: Dict[str, List[str]] = {
        "solve": [
            "Step 1: Rearrange the equation into a standard solvable form.",
            "Step 2: Factorise / substitute / apply inverse operations to isolate the variable.",
            "Step 3: Solve for all candidate values and check any domain restrictions.",
            "Answer: state the complete solution set clearly.",
        ],
        "prove": [
            "Step 1: Start from the more complex side (or from a known identity).",
            "Step 2: Apply valid algebraic / trigonometric / logarithmic transformations line-by-line.",
            "Step 3: Reach exactly the required expression.",
            "Conclusion: the required result is proven.",
        ],
        "binomial": [
            "Step 1: Write the relevant binomial term using T_(r+1) = nCr * a^(n-r) * b^r.",
            "Step 2: Substitute the requested power/position condition and solve for r if needed.",
            "Step 3: Evaluate coefficient and simplify the term.",
            "Answer: give the required term/coefficient in simplified form.",
        ],
        "differentiate": [
            "Step 1: Identify the correct differentiation rule(s) (chain/product/quotient as needed).",
            "Step 2: Differentiate each part carefully and simplify.",
            "Step 3: Substitute values / solve derivative condition if required.",
            "Answer: present the final derivative/result clearly.",
        ],
        "integrate": [
            "Step 1: Set up the integral correctly (including limits if definite).",
            "Step 2: Integrate term-by-term or by substitution/parts as appropriate.",
            "Step 3: Apply limits / simplify constants and expression.",
            "Answer: give the final exact value/expression.",
        ],
        "complex": [
            "Step 1: Rewrite in a useful complex form (a + bi or r(cosθ + i sinθ)).",
            "Step 2: Apply the required operation/property (modulus, argument, conjugate, powers).",
            "Step 3: Simplify to the requested form and verify quadrant/sign where relevant.",
            "Answer: state the final complex result clearly.",
        ],
        "sequence": [
            "Step 1: Identify whether the sequence is arithmetic/geometric (or another defined recurrence).",
            "Step 2: Use the relevant formula for nth term or sum.",
            "Step 3: Substitute given values and solve for the unknown quantity.",
            "Answer: provide the requested term/sum/index.",
        ],
        "logs": [
            "Step 1: Use log/exponential laws to combine or separate terms appropriately.",
            "Step 2: Convert to an equivalent linear/exponential equation.",
            "Step 3: Solve and check domain validity (arguments of logs must be positive).",
            "Answer: give valid solution(s) only.",
        ],
        "inverse": [
            "Step 1: Let y = f(x), then swap x and y to form the inverse relation.",
            "Step 2: Rearrange to express y explicitly in terms of x.",
            "Step 3: State domain/range constraints where required.",
            "Answer: write f^(-1)(x) and any relevant restriction.",
        ],
        "general": [
            "Step 1: Identify the core method required by the question.",
            "Step 2: Carry out the method with clear algebraic working.",
            "Step 3: Simplify to the requested form and verify constraints/units.",
            "Answer: provide the final result clearly.",
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

    text_lines = [
        "IB-style Worked Solution (Draft):",
        "Use this as a model method. Check arithmetic and OCR-heavy symbols carefully.",
        "",
    ]
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
