#!/usr/bin/env python3
"""Generate IB-style draft markschemes for tutoring questions."""

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


def default_lines_for_prompt(prompt: str, marks: int) -> List[str]:
    p = prompt.lower()

    if "solve" in p:
        base = [
            "M1: valid setup/manipulation of equation(s).",
            "A1: correct transformed equation / intermediate value(s).",
            "A1: correct final solution set with valid restrictions.",
        ]
    elif "show that" in p or "prove" in p:
        base = [
            "M1: valid algebraic/analytic approach using a relevant identity/theorem.",
            "A1: correct intermediate step(s) logically linked.",
            "A1: required result obtained exactly.",
        ]
    elif "expand" in p or "binomial" in p:
        base = [
            "M1: appropriate binomial structure / term selection used.",
            "A1: correct coefficient calculation.",
            "A1: correct simplified expansion/term.",
        ]
    elif "differentiat" in p or "derivative" in p:
        base = [
            "M1: valid differentiation rule(s) selected.",
            "A1: correct derivative expression.",
            "A1: correct evaluated result / stationary condition as required.",
        ]
    elif "integrat" in p or "integral" in p:
        base = [
            "M1: valid integration setup (limits/substitution/parts if needed).",
            "A1: correct antiderivative/intermediate integration step.",
            "A1: correct final exact value / expression.",
        ]
    elif "complex" in p or "arg" in p or "modulus" in p:
        base = [
            "M1: appropriate complex-number form or property used.",
            "A1: correct algebraic/trigonometric manipulation.",
            "A1: correct final value/form.",
        ]
    elif "sequence" in p or "series" in p or "sum" in p:
        base = [
            "M1: correct sequence/series model identified.",
            "A1: correct substitution into formula/recurrence.",
            "A1: correct final term/sum.",
        ]
    elif "log" in p or "ln" in p or "exponential" in p:
        base = [
            "M1: valid logarithmic/exponential transformation.",
            "A1: correct simplification/isolation step.",
            "A1: correct final solution(s), with domain checks where needed.",
        ]
    else:
        base = [
            "M1: relevant method selected and applied.",
            "A1: correct intermediate result(s).",
            "A1: correct final answer in required form.",
        ]

    count = 2 if marks <= 2 else 3
    return base[:count]


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
        lines = default_lines_for_prompt(prompt, marks)
        part_entries.append(
            {
                "part": label,
                "marks": marks,
                "prompt_excerpt": prompt[:180],
                "criteria": lines,
            }
        )

    text_lines = [
        "General marking notes:",
        "- Award method marks (M) for valid process even if arithmetic slips occur.",
        "- Award accuracy marks (A) only when supported by valid working.",
        "- Follow-through (FT) may be awarded where a prior error is carried correctly.",
        "",
    ]
    for part in part_entries:
        text_lines.append(f"Part ({part['part']}) [{part['marks']} marks]")
        for row in part["criteria"]:
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
        "markscheme_text": "\n".join(text_lines).strip(),
        "draft": True,
    }


def main() -> None:
    payload = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])
    entries = [build_markscheme_entry(q) for q in questions]

    out = {
        "course": "IB Mathematics AA HL - Tutoring Questions",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "notes": "Auto-generated IB-style draft markschemes. Review and edit before formal use.",
        "questions": entries,
    }
    OUT_FILE.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} draft markschemes to {OUT_FILE}")


if __name__ == "__main__":
    main()
