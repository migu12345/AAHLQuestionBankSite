"""
Adds level, marks, and paper_type fields to existing tutoring questions.json.
Run from the project root:
    python3 scripts/tutoring/enrich_metadata.py
"""
import json
import re

QUESTIONS_PATH = "data/tutoring/processed/questions.json"

# Level inferred from source PDF headers/filenames.
SOURCE_LEVEL_MAP = {
    "Binomila Theorem.pdf": "SL",
    "Math_SL_Algebra.pdf": "SL",
    "Math_SL_Algebra_Exp_Log.pdf": "SL",
    "Math_SL_Functions_Equations_2023.pdf": "SL",
    "Topic_1_2_Algebra_Exponents_Logarithms_2023.pdf": "HL",
    "Topic_1_4_Algebra_Mathematical_Induction.pdf": "HL",
    "Topic_1_5_Algebra_Complex_Numbers.pdf": "HL",
    "Topic_1_1_Algebra_Sequences_Series.pdf": "HL",
    "Topic_1_3_Algebra_Counting_Principles.pdf": "HL",
    "Topic_6_Calculus.pdf": "HL",
    "statistics.pdf": "HL",
    "statistics (1).pdf": "HL",
    "Limits_derivatives (1).pdf": "HL",
    "Math_SL_Calculus_Julius (1).pdf": "SL",
    "Math_SL_Circular_FunctionsTrigonometry.pdf": "SL",
    "Math_SL_Statistics_Probability_2022 (1).pdf": "SL",
    "T6-1 T HL.pdf": "HL",
    "T6-2P1 T.pdf": "HL",
    "T6-2P2 T.pdf": "HL",
    "T2-5 T (2).pdf": "HL",
    "T2-6 T (1).pdf": "HL",
    "Topic 1 Part 1 T.pdf": "SL",
    "Topic 2 Part 1 T.pdf": "SL",
    "Topic 3 Part 1 T (1).pdf": "SL",
    "Topic 6 Part 1 T SL.pdf": "SL",
}

# Paper type inferred from filename where possible.
SOURCE_PAPER_MAP = {
    "T6-2P1 T.pdf": "Paper 1",
    "T6-2P2 T.pdf": "Paper 2",
}

MARKS_PATTERN = re.compile(r"\(Total\s+(\d+)\s+marks?\)", re.IGNORECASE)
MARKS_BRACKET_PATTERN = re.compile(r"\[(\d+)\s+marks?\]", re.IGNORECASE)


def extract_marks(question_text):
    text = str(question_text or "")
    m = MARKS_PATTERN.search(text)
    if m:
        return int(m.group(1))
    m = MARKS_BRACKET_PATTERN.search(text)
    if m:
        return int(m.group(1))
    return None


def main():
    with open(QUESTIONS_PATH) as f:
        data = json.load(f)

    questions = data.get("questions", [])
    updated = 0

    for q in questions:
        changed = False
        src = q.get("source_file", "")

        if "level" not in q or not q["level"]:
            level = SOURCE_LEVEL_MAP.get(src, "")
            if not level:
                # Fall back to subtopic-based inference.
                sub = str(q.get("subtopic", "")).lower()
                if "induction" in sub or "complex" in sub:
                    level = "HL"
                elif "sl" in src.lower():
                    level = "SL"
            if level:
                q["level"] = level
                changed = True

        if "paper_type" not in q or not q["paper_type"]:
            pt = SOURCE_PAPER_MAP.get(src, "")
            if pt:
                q["paper_type"] = pt
                changed = True

        if "marks" not in q or q["marks"] is None:
            marks = extract_marks(q.get("question_text", ""))
            if marks is not None:
                q["marks"] = marks
                changed = True

        if changed:
            updated += 1

    data["questions"] = questions
    with open(QUESTIONS_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Updated {updated}/{len(questions)} questions with metadata.")


if __name__ == "__main__":
    main()
