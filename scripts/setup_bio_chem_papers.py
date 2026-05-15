#!/usr/bin/env python3
"""
Scans the IB past papers archive, finds English Biology and Chemistry papers
(with their markschemes), copies them into the project resource directories,
and writes manual_papers.json for both subjects.

Run once to populate the resource directories, then run the build scripts:
  python3 scripts/build_biology_bank.py
  python3 scripts/build_chemistry_bank.py
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

SOURCE = Path("/Users/s933863@aics.espritscholen.nl/Documents/IB PAST PAPERS - YEAR")
PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"

NON_ENGLISH = [
    "french", "german", "spanish", "dutch", "arabic", "chinese", "japanese",
    "italian", "portuguese", "swedish", "afrikaans", "malay", "turkish",
    "hindi", "polish", "slovak", "czech", "korean", "norwegian", "danish",
    "romanian", "bulgarian", "croatian", "latvian", "lithuanian", "slovenian",
    "estonian", "serbian", "hebrew", "indonesian", "persian", "thai",
    "[german]", "[french]", "[spanish]",
]


def is_english(path: Path) -> bool:
    name_lower = path.name.lower()
    return not any(lang in name_lower for lang in NON_ENGLISH)


def parse_session_year_from_path(path: Path) -> tuple[str, int] | None:
    """Extract (session, year) from the directory path."""
    parts = [p for p in path.parts]
    year = None
    session = None

    for part in parts:
        # Year from 4-digit number in folder name
        m = re.search(r"(20\d\d)", part)
        if m and year is None:
            year = int(m.group(1))

        part_lower = part.lower()
        if "may" in part_lower and "donated papers m" not in part_lower:
            session = "May"
        elif "november" in part_lower and "donated papers n" not in part_lower:
            session = "November"
        elif re.search(r"donated papers m\d\d", part_lower):
            session = "May"
        elif re.search(r"donated papers n\d\d", part_lower):
            session = "November"

    if year and session:
        return session, year
    return None


def parse_paper_meta(path: Path, session: str, year: int) -> dict | None:
    """Parse paper metadata from filename. Returns None if unparseable."""
    name = path.stem.lower()  # filename without extension
    orig_name = path.stem     # preserve original case for display

    # Skip non-English
    if not is_english(path):
        return None

    # Determine subject
    if "biology" in name or name.startswith("bio_") or "bio " in name:
        subject = "Biology"
    elif "chemistry" in name or name.startswith("chem") or "chem " in name:
        subject = "Chemistry"
    else:
        return None

    # Is it a markscheme?
    is_ms = "markscheme" in name or "_ms_" in name or name.endswith("_ms")

    # Paper number
    paper_m = re.search(r"paper[_\s]*(\d)", name)
    if not paper_m:
        # Fallback: p1, p2, p3 patterns
        p_m = re.search(r"\bp([123])\b", name)
        if p_m:
            paper_m = p_m
            paper_num = p_m.group(1)
        else:
            return None
    else:
        paper_num = paper_m.group(1)

    # Level — use [^a-z] boundaries since underscore is a word char
    if re.search(r"(?<![a-z])hl(?![a-z])", name):
        level = "HL"
    elif re.search(r"(?<![a-z])sl(?![a-z])", name):
        level = "SL"
    else:
        return None

    # Timezone
    tz_m = re.search(r"tz([12])", name)
    if tz_m:
        tz = f"TZ{tz_m.group(1)}"
    elif session == "November":
        tz = "NTZ"
    else:
        # May session without explicit TZ → single-timezone paper
        tz = "TZ1"

    return {
        "subject": subject,
        "year": year,
        "session": session,
        "paper": paper_num,
        "level": level,
        "tz": tz,
        "is_ms": is_ms,
        "path": path,
    }


def session_code(session: str, year: int) -> str:
    prefix = "m" if session == "May" else "n"
    return f"{prefix}{str(year)[-2:]}"


def dest_filename(meta: dict) -> str:
    """Generate canonical destination filename."""
    subj = meta["subject"]
    p = meta["paper"]
    tz = meta["tz"]
    lvl = meta["level"]
    suffix = "_markscheme" if meta["is_ms"] else ""
    if tz == "NTZ":
        return f"{subj}_paper_{p}__{lvl}{suffix}.pdf"
    return f"{subj}_paper_{p}_{tz}_{lvl}{suffix}.pdf"


def dest_dir(subject: str, session: str, year: int) -> Path:
    subj_lower = subject.lower()
    sc = session_code(session, year)
    return DATA / "resources" / subj_lower / sc


def paper_label(meta: dict) -> str:
    return (
        f"{meta['session']} {meta['year']} "
        f"{meta['subject']} Paper {meta['paper']} "
        f"{meta['tz']} {meta['level']}"
    )


def main() -> None:
    # Collect all Bio/Chem English PDFs and parse metadata
    all_pdfs = list(SOURCE.rglob("*.pdf"))
    print(f"Found {len(all_pdfs)} total PDFs in source archive.")

    # Parse each PDF
    papers: list[dict] = []
    for pdf in all_pdfs:
        result = parse_session_year_from_path(pdf)
        if result is None:
            continue
        session, year = result

        # Only process 2016–2025 (IB 2014+ curriculum aligned papers)
        if year < 2016 or year > 2025:
            continue

        meta = parse_paper_meta(pdf, session, year)
        if meta is None:
            continue

        papers.append(meta)

    print(f"Parsed {len(papers)} Biology/Chemistry English PDFs (2016–2025).")

    # Separate question papers from markschemes
    q_papers = [p for p in papers if not p["is_ms"]]
    ms_papers = [p for p in papers if p["is_ms"]]

    # Index markschemes by key
    def ms_key(m: dict) -> tuple:
        return (m["subject"], m["year"], m["session"], m["paper"], m["level"], m["tz"])

    ms_index: dict[tuple, dict] = {}
    for ms in ms_papers:
        k = ms_key(ms)
        # Keep first found (prefer exact match)
        if k not in ms_index:
            ms_index[k] = ms

    print(f"  Question papers: {len(q_papers)}")
    print(f"  Markschemes:     {len(ms_papers)}")

    bio_entries: list[dict] = []
    chem_entries: list[dict] = []
    copied = 0
    skipped = 0

    for qp in sorted(q_papers, key=lambda x: (x["year"], x["session"], x["subject"], x["paper"], x["level"], x["tz"])):
        k = ms_key(qp)
        ms = ms_index.get(k)

        # Also try NTZ fallback for May papers (some markschemes lack TZ)
        if ms is None and qp["tz"] != "NTZ":
            ms = ms_index.get((qp["subject"], qp["year"], qp["session"], qp["paper"], qp["level"], "NTZ"))

        # Copy question paper
        d = dest_dir(qp["subject"], qp["session"], qp["year"])
        d.mkdir(parents=True, exist_ok=True)
        q_dest = d / dest_filename(qp)
        if not q_dest.exists():
            shutil.copy2(qp["path"], q_dest)
            copied += 1

        # Copy markscheme if found
        ms_dest = None
        if ms is not None:
            ms_fname = dest_dir(ms["subject"], ms["session"], ms["year"]) / dest_filename(ms)
            ms_fname.parent.mkdir(parents=True, exist_ok=True)
            if not ms_fname.exists():
                shutil.copy2(ms["path"], ms_fname)
                copied += 1
            ms_dest = ms_fname

        # Build relative paths
        subj_lower = qp["subject"].lower()
        sc = session_code(qp["session"], qp["year"])
        q_rel = f"resources/{subj_lower}/{sc}/{q_dest.name}"
        ms_rel = f"resources/{subj_lower}/{sc}/{ms_dest.name}" if ms_dest else None

        entry = {
            "paperLabel": paper_label(qp),
            "session": qp["session"],
            "year": qp["year"],
            "paperCode": qp["paper"],
            "timezone": qp["tz"],
            "level": qp["level"],
            "paper_path": q_rel,
            "markscheme_path": ms_rel,
        }

        if qp["subject"] == "Biology":
            bio_entries.append(entry)
        else:
            chem_entries.append(entry)

    print(f"\nCopied {copied} new files, {skipped} already existed.")
    print(f"Biology entries:   {len(bio_entries)}")
    print(f"Chemistry entries: {len(chem_entries)}")

    # Write manual_papers.json
    bio_out = DATA / "biology" / "processed" / "manual_papers.json"
    chem_out = DATA / "chemistry" / "processed" / "manual_papers.json"
    bio_out.parent.mkdir(parents=True, exist_ok=True)
    chem_out.parent.mkdir(parents=True, exist_ok=True)

    bio_out.write_text(json.dumps({"papers": bio_entries}, indent=2, ensure_ascii=False), encoding="utf-8")
    chem_out.write_text(json.dumps({"papers": chem_entries}, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nWrote: {bio_out}")
    print(f"Wrote: {chem_out}")
    print("\nNext steps:")
    print("  python3 scripts/build_biology_bank.py")
    print("  python3 scripts/build_chemistry_bank.py")


if __name__ == "__main__":
    main()
