#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import runpy
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_JSON = ROOT / "data" / "physics" / "processed" / "questions.json"
MANUAL_JSON = ROOT / "data" / "physics" / "processed" / "manual_papers.json"
MS_IMG_DIR = ROOT / "data" / "physics" / "processed" / "images" / "markschemes"

PAPER_RE = re.compile(
    r"^(May|November)\s+(\d{4})\s+Physics\s+Paper\s+([123](?:[AB])?)(?:\s+(TZ\d|NTZ|No TZ))?\s+(HL|SL)$"
)


def parse_paper_label(label: str) -> Optional[Tuple[str, int, str, str, str]]:
    m = PAPER_RE.match(str(label or "").strip())
    if not m:
        return None
    session = m.group(1)
    year = int(m.group(2))
    paper_code = m.group(3)
    timezone = m.group(4) or "NTZ"
    if timezone == "No TZ":
        timezone = "NTZ"
    level = m.group(5)
    return (session, year, paper_code, timezone, level)


def main() -> None:
    payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])
    manual = json.loads(MANUAL_JSON.read_text(encoding="utf-8")).get("papers", [])

    manual_by_key: Dict[Tuple[str, int, str, str, str], dict] = {}
    for p in manual:
        key = (p.get("session"), int(p.get("year")), p.get("paperCode"), p.get("timezone"), p.get("level"))
        manual_by_key[key] = p

    mod = runpy.run_path(str(ROOT / "scripts" / "build_physics_bank.py"))
    fitz = mod["fitz"]
    detect_starts = mod["detect_starts"]
    crop_question = mod["crop_question"]

    ms_cache: Dict[Path, object] = {}
    starts_cache: Dict[Path, list] = {}

    candidates = [
        q
        for q in questions
        if str(q.get("paper_type", "")).strip().lower() == "paper 3"
        and not (q.get("markscheme_image_paths") or [])
    ]

    attached = 0
    unresolved = []

    for q in candidates:
        paper_meta = parse_paper_label(str(q.get("paper", "")))
        if not paper_meta:
            unresolved.append((q.get("id"), "paper label parse failed"))
            continue

        man = manual_by_key.get(paper_meta)
        if not man:
            unresolved.append((q.get("id"), "manual paper mapping not found"))
            continue

        ms_rel = man.get("markscheme_path")
        if not ms_rel:
            unresolved.append((q.get("id"), "markscheme path missing in manual_papers"))
            continue

        ms_pdf = ROOT / "data" / str(ms_rel)
        if not ms_pdf.exists():
            unresolved.append((q.get("id"), f"markscheme pdf missing: {ms_rel}"))
            continue

        if ms_pdf not in ms_cache:
            doc = fitz.open(str(ms_pdf))
            ms_cache[ms_pdf] = doc
            starts_cache[ms_pdf] = detect_starts(doc, "markscheme")

        qnum = int(str(q.get("question_number", "0")) or 0)
        if qnum <= 0:
            unresolved.append((q.get("id"), "invalid question number"))
            continue

        qid = str(q.get("id", "")).strip()
        if not qid:
            unresolved.append((q.get("id"), "missing question id"))
            continue

        for stale in MS_IMG_DIR.glob(f"{qid}*.png"):
            stale.unlink(missing_ok=True)

        rels = crop_question(ms_cache[ms_pdf], starts_cache[ms_pdf], qnum, MS_IMG_DIR / qid, "markscheme")
        if not rels:
            unresolved.append((qid, "no markscheme crop produced"))
            continue

        q["markscheme_image_paths"] = rels
        q["markscheme_images"] = rels
        q["has_markscheme"] = True
        attached += 1

    for doc in ms_cache.values():
        doc.close()

    QUESTIONS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Paper 3 missing candidates: {len(candidates)}")
    print(f"Attached markscheme screenshots: {attached}")
    print(f"Still unresolved: {len(unresolved)}")
    for qid, reason in unresolved[:50]:
        print(f"- {qid}: {reason}")


if __name__ == "__main__":
    main()
