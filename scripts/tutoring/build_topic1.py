#!/usr/bin/env python3
"""Build Topic 1 tutoring question bank from provided files."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

from pypdf import PdfReader  # type: ignore

SOURCE_DIR = Path("/Users/s933863@aics.espritscholen.nl/Documents/Tutoring Questions/Topic 1 Number and Algebra")
OUT_FILE = ROOT / "data" / "tutoring" / "processed" / "questions.json"

SUBTOPIC_MAP: Dict[str, str] = {
    "Binomila Theorem.pdf": "Binomial theorem",
    "Math_SL_Algebra.pdf": "Sequences and series",
    "Math_SL_Algebra_Exp_Log.pdf": "Exponents and logarithms",
    "Topic_1_2_Algebra_Exponents_Logarithms_2023.pdf": "Exponents and logarithms",
    "Topic_1_4_Algebra_Mathematical_Induction.pdf": "Proof by induction",
    "Topic_1_5_Algebra_Complex_Numbers.rtf": "Complex numbers",
}


def normalize_ws(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def extract_rtf_text(path: Path) -> str:
    try:
        cmd = ["textutil", "-convert", "txt", "-stdout", str(path)]
        return subprocess.check_output(cmd, text=True)
    except Exception:
        # Basic fallback if textutil is unavailable.
        raw = path.read_text(encoding="utf-8", errors="ignore")
        raw = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
        raw = re.sub(r"\\[a-zA-Z]+\d* ?", " ", raw)
        raw = raw.replace("{", " ").replace("}", " ")
        return raw


def cleanup_text(text: str) -> str:
    lines = []
    for line in text.splitlines():
        l = line.strip()
        if not l:
            lines.append("")
            continue
        if re.match(r"^\d+\s*\|\s*P a g e", l):
            continue
        if "IB Revision Courses" in l:
            continue
        lines.append(l)
    return normalize_ws("\n".join(lines))


def split_questions(text: str) -> List[Dict[str, str]]:
    lines = text.splitlines()
    current_num = None
    current_lines: List[str] = []
    output: List[Dict[str, str]] = []

    def flush() -> None:
        if current_num is None:
            return
        body = normalize_ws("\n".join(current_lines))
        if len(body) < 20:
            return
        output.append(
            {
                "question_number": str(current_num),
                "question_text": body,
            }
        )

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


def read_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path)
    if path.suffix.lower() == ".rtf":
        return extract_rtf_text(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def build() -> Dict[str, object]:
    questions = []
    for path in sorted(SOURCE_DIR.iterdir()):
        if path.name not in SUBTOPIC_MAP:
            continue
        raw = read_file(path)
        clean = cleanup_text(raw)
        chunks = split_questions(clean)
        subtopic = SUBTOPIC_MAP[path.name]

        for q in chunks:
            qn = q["question_number"]
            rec_id = f"t1_{path.stem.lower().replace(' ', '_')}_q{qn}"
            questions.append(
                {
                    "id": rec_id,
                    "unit": "Topic 1 Number and Algebra",
                    "topic": "Number and Algebra",
                    "subtopic": subtopic,
                    "source_file": path.name,
                    "question_number": qn,
                    "title": f"Q{qn}",
                    "question_text": q["question_text"],
                }
            )

    return {
        "course": "IB Mathematics AA HL - Tutoring Questions",
        "unit": "Topic 1 Number and Algebra",
        "questions": questions,
    }


def main() -> None:
    payload = build()
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['questions'])} tutoring questions to {OUT_FILE}")


if __name__ == "__main__":
    main()
