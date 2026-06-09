#!/usr/bin/env python3
"""
Fixes the markscheme off-by-one in T6-1 T HL.pdf and Topic 6 Part 1 T SL.pdf.

In both files, the latex_solution for question N was written to match the
question_text (which is one question behind the actual image). The fix shifts
each question's latex_solution to the NEXT question's current value so it
aligns with the image:
  - q1 stays (already correct)
  - q2 gets q3's current latex_solution
  - q3 gets q4's ...
  - q(last) gets cleared (needs manual correction)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MS_PATH = ROOT / "data" / "tutoring" / "processed" / "markschemes.json"

AFFECTED = {
    "T6-1 T HL.pdf":          "t5_t61",
    "Topic 6 Part 1 T SL.pdf": "t5_sl2",
}


def fix_file(data: list[dict], source_file: str, id_prefix: str) -> int:
    # Collect entries for this file, sorted by question_number
    entries = [
        q for q in data
        if q.get("source_file") == source_file
    ]
    entries.sort(key=lambda q: int(q.get("question_number", 0)))

    if not entries:
        print(f"  No entries found for {source_file}")
        return 0

    print(f"  {source_file}: {len(entries)} entries (IDs {entries[0]['id']} … {entries[-1]['id']})")

    # Build index by question_number → list position in `data`
    idx_map: dict[int, int] = {}
    for i, q in enumerate(data):
        if q.get("source_file") == source_file:
            qn = int(q.get("question_number", 0))
            idx_map[qn] = i

    # Collect ordered question numbers
    qnums = sorted(idx_map.keys())

    # Shift: q[n] gets q[n+1]'s latex_solution, starting from q2
    # We need to do this carefully so we don't overwrite before reading.
    # Collect the old values first.
    old_solutions = {qn: data[idx_map[qn]].get("latex_solution", "") for qn in qnums}

    changes = 0
    for i, qn in enumerate(qnums):
        if i == 0:
            # q1 is already correct — skip
            continue
        if i < len(qnums) - 1:
            # q[n] = old q[n+1]'s solution
            next_qn = qnums[i + 1]
            new_sol = old_solutions[next_qn]
        else:
            # Last question — clear and mark as needing correction
            new_sol = ""

        idx = idx_map[qn]
        if data[idx].get("latex_solution", "") != new_sol:
            data[idx]["latex_solution"] = new_sol
            changes += 1

    last_id = entries[-1]["id"]
    print(f"    Shifted solutions for {len(qnums) - 2} questions; {last_id} cleared (needs manual markscheme)")
    return changes


def main() -> None:
    ms_data = json.loads(MS_PATH.read_text(encoding="utf-8"))
    questions = ms_data["questions"]

    total_changes = 0
    for source_file, id_prefix in AFFECTED.items():
        print(f"\nProcessing {source_file}:")
        total_changes += fix_file(questions, source_file, id_prefix)

    MS_PATH.write_text(
        json.dumps({"questions": questions}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nDone. {total_changes} latex_solution fields updated → {MS_PATH}")


if __name__ == "__main__":
    main()
