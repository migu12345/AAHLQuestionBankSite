#!/usr/bin/env python3
"""Comprehensive audit of all cropped question images for the tutoring bank.

Flags single-image questions that are suspiciously small (< 100px height),
which likely indicates a missing preamble or bad crop. Multi-page questions
(where the question spans multiple images) are audited differently: only
flag if ALL pages are small.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

try:
    from PIL import Image  # type: ignore
    USE_PIL = True
except ImportError:
    USE_PIL = False
    import subprocess

QUESTIONS_JSON = ROOT / "data" / "tutoring" / "processed" / "questions.json"
PROCESSED_DIR = ROOT / "data" / "tutoring" / "processed"

MIN_HEIGHT_SINGLE = 100  # px — single-image questions below this are suspicious

def get_height(img_path: Path) -> int:
    """Return pixel height of an image file."""
    if not img_path.exists():
        return -1
    if USE_PIL:
        with Image.open(img_path) as img:
            return img.height
    else:
        result = subprocess.run(
            ["sips", "-g", "pixelHeight", str(img_path)],
            capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            if "pixelHeight" in line:
                return int(line.split(":")[1].strip())
        return -1


def main() -> None:
    qs_data = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = qs_data["questions"]

    small_singles: list[tuple[str, int, str]] = []  # (qid, height, path)
    missing: list[str] = []  # qid with no image

    total = 0
    for q in questions:
        paths = q.get("question_image_paths", [])
        if not paths:
            continue  # skip questions with no image paths (non-tutoring)

        total += 1
        qid = q.get("id", "?")
        full_paths = [PROCESSED_DIR / p for p in paths]

        if not any(p.exists() for p in full_paths):
            missing.append(qid)
            continue

        if len(full_paths) == 1:
            # Single-image question: check for suspicious smallness
            h = get_height(full_paths[0])
            if h < MIN_HEIGHT_SINGLE:
                small_singles.append((qid, h, paths[0]))
        else:
            # Multi-page question: only flag if EVERY page is tiny
            heights = [get_height(p) for p in full_paths if p.exists()]
            if all(h < MIN_HEIGHT_SINGLE for h in heights):
                min_h = min(heights)
                small_singles.append((qid, min_h, f"{paths[0]} (+{len(paths)-1} more)"))

    print(f"Audited {total} questions with images.\n")

    if missing:
        print(f"MISSING ({len(missing)} questions — image file not found on disk):")
        for qid in missing:
            print(f"  {qid}")
        print()

    if small_singles:
        print(f"SUSPICIOUS SMALL CROPS ({len(small_singles)} questions — height < {MIN_HEIGHT_SINGLE}px):")
        for qid, h, path in sorted(small_singles, key=lambda x: x[1]):
            print(f"  {qid}: {h}px  ({path})")
        print()
    else:
        print("No suspiciously small single-image questions found.")

    if not missing and not small_singles:
        print("All crops look healthy!")


if __name__ == "__main__":
    main()
