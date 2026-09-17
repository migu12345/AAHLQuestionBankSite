"""Audit Physics and Tutoring question/markscheme links and optional R2 assets."""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which("git") or str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/cmd/git.exe")
CURL = shutil.which("curl.exe") or shutil.which("curl")
DEFAULT_CDN = "https://pub-f7419ca433e9434bad2f9e89e252c205.r2.dev"


def questions(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))["questions"]


def tracked_assets(subject):
    prefix = f"data/{subject}/processed/"
    output = subprocess.check_output(
        [GIT, "ls-files", "--cached", "--", prefix],
        cwd=ROOT,
        text=True,
    )
    return {path.removeprefix(prefix) for path in output.splitlines()}


def audit():
    problems = []
    for subject in ("physics", "tutoring"):
        records = questions(f"data/{subject}/processed/questions.json")
        ids = [record["id"] for record in records]
        duplicates = sorted(id_ for id_, count in Counter(ids).items() if count > 1)
        assets = tracked_assets(subject)
        paths = [
            (record["id"], path)
            for record in records
            for path in record.get("question_image_paths", [])
            + (record.get("markscheme_image_paths", []) if subject == "physics" else [])
        ]
        if subject == "tutoring":
            markschemes = questions("data/tutoring/processed/markschemes.json")
            ms_ids = [record["id"] for record in markschemes]
            ms_duplicates = sorted(id_ for id_, count in Counter(ms_ids).items() if count > 1)
            missing_ms = sorted(set(ids) - set(ms_ids))
            orphan_ms = sorted(set(ms_ids) - set(ids))
            paths += [
                (record["id"], path)
                for record in markschemes
                for path in record.get("markscheme_image_paths", [])
            ]
            print(f"Tutoring: {len(records)} questions, {len(markschemes)} markschemes")
            for name, values in (
                ("duplicate markscheme IDs", ms_duplicates),
                ("questions without markschemes", missing_ms),
                ("orphan markschemes", orphan_ms),
            ):
                if values:
                    problems.append((name, values))
        else:
            empty_questions = sorted(
                record["id"] for record in records if not record.get("question_text", "").strip()
            )
            missing_screenshots = sorted(
                record["id"]
                for record in records
                if record.get("has_markscheme")
                and not record.get("markscheme_image_paths")
                and not record.get("mcq_answer")
            )
            print(f"Physics: {len(records)} questions")
            if empty_questions:
                problems.append(("Physics questions without text", empty_questions))
            if missing_screenshots:
                problems.append(("Physics markscheme screenshots missing", missing_screenshots))

        if duplicates:
            problems.append((f"{subject} duplicate question IDs", duplicates))
        absent = sorted({path for _, path in paths if path not in assets})
        misnamed = sorted({path for id_, path in paths if not PurePosixPath(path).stem.startswith(id_)})
        if absent:
            problems.append((f"{subject} paths absent from Git", absent))
        if misnamed:
            problems.append((f"{subject} paths assigned to another ID", misnamed))
        print(f"  {len(paths)} image references; {len(absent)} absent from Git; {len(misnamed)} mismatched IDs")

    for label, values in problems:
        print(f"{label} ({len(values)}):")
        for value in values:
            print(f"  {value}")
    return bool(problems)


def verify_remote(path, cdn_base):
    if not path.startswith("data/"):
        raise ValueError(f"Asset path must start with data/: {path}")
    local = subprocess.check_output([GIT, "show", f":{path}"], cwd=ROOT)
    if not CURL:
        raise RuntimeError("curl is required for verified HTTPS asset downloads")
    remote = subprocess.check_output(
        [CURL, "-fLsS", "--max-time", "30", cdn_base.rstrip("/") + "/" + path],
        stderr=subprocess.PIPE,
    )
    same = hashlib.sha256(local).digest() == hashlib.sha256(remote).digest()
    print(f"{'MATCH' if same else 'MISMATCH'} {path} (Git {len(local)} bytes; R2 {len(remote)} bytes)")
    return same


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset", action="append", default=[], help="Repo-relative asset path to compare with R2")
    parser.add_argument("--cdn-base", default=DEFAULT_CDN)
    args = parser.parse_args()
    has_problems = audit()
    for path in args.asset:
        try:
            if not verify_remote(path, args.cdn_base):
                has_problems = True
        except Exception as error:
            print(f"FAILED {path}: {error}")
            has_problems = True
    return 1 if has_problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
