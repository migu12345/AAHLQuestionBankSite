#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

MANUAL = ROOT / "data" / "physics" / "processed" / "manual_papers.json"
OUT = ROOT / "data" / "physics" / "processed" / "questions.json"
IMAGES_ROOT = ROOT / "data" / "physics" / "processed" / "images"


@dataclass
class StartPos:
    qnum: int
    page: int
    y: float


def norm_ws(s: str) -> str:
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def clean_text_for_topic(s: str) -> str:
    s = s.lower().replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def infer_topic(question_text: str, paper_code: str) -> tuple[str, str]:
    t = clean_text_for_topic(question_text)
    if paper_code.upper() == "1A":
        return ("A-E mixed", "Multiple-choice mixed")

    rules = [
        (["velocity", "acceleration", "force", "momentum", "energy", "power", "circular"], "Space, time and motion", "Mechanics"),
        (["thermal", "temperature", "gas", "pressure", "internal energy", "current", "voltage", "resistance", "circuit"], "Particulate nature of matter", "Thermal / electricity"),
        (["wave", "frequency", "wavelength", "interference", "diffraction", "standing wave", "doppler"], "Wave behaviour", "Wave phenomena"),
        (["electric field", "magnetic field", "gravitational field", "induction", "flux", "capacitor"], "Fields", "Electric/magnetic/gravitational fields"),
        (["nuclear", "radioactive", "decay", "quantum", "photon", "fission", "fusion", "half life"], "Nuclear and quantum physics", "Nuclear / quantum"),
    ]
    for kws, topic, sub in rules:
        if any(kw in t for kw in kws):
            return (topic, sub)
    return ("Unsorted", "Unsorted")


def detect_starts(doc: fitz.Document, kind: str) -> List[StartPos]:
    starts: Dict[int, tuple[int, float]] = {}
    for pno in range(len(doc)):
        page = doc[pno]
        blocks = page.get_text("dict").get("blocks", [])
        prev = ""
        pending: Optional[int] = None
        pending_y: Optional[float] = None
        pending_x: Optional[float] = None

        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(span.get("text", "") for span in spans).strip()
                if not text:
                    continue
                x = float(line.get("bbox", [0, 0, 0, 0])[0])
                y = float(line.get("bbox", [0, 0, 0, 0])[1])

                qn: Optional[int] = None
                m_plain = re.match(r"^(\d{1,2})$", text)
                m_dot = re.match(r"^(\d{1,2})\.$", text)
                m_inline = re.match(r"^(\d{1,2})\.\s+", text)

                if m_plain:
                    pending = int(m_plain.group(1))
                    pending_y = y
                    pending_x = x
                elif m_dot:
                    pending = int(m_dot.group(1))
                    pending_y = y
                    pending_x = x
                    qn = pending
                elif m_inline:
                    qn = int(m_inline.group(1))

                if kind == "markscheme":
                    m_ms = re.match(r"^(\d{1,2})\s+", text)
                    if m_ms and x <= 95:
                        qn = int(m_ms.group(1))

                if qn is None and pending is not None and x <= 120 and re.match(r"^(?:\(|[A-Za-z])", text):
                    qn = pending

                if qn is not None and 1 <= qn <= 60 and qn not in starts:
                    if x <= 120 or (pending_x is not None and pending_x <= 120):
                        starts[qn] = (pno, pending_y if pending_y is not None else y)
                        pending = None
                        pending_y = None
                        pending_x = None

                prev = text

    out = [StartPos(qnum=q, page=pg, y=y) for q, (pg, y) in starts.items()]
    out.sort(key=lambda s: (s.page, s.y))
    return out


def is_blank_answer_page(page: fitz.Page, clip: fitz.Rect) -> bool:
    text = page.get_text("text", clip=clip).lower()
    if "please do not write on this page" in text:
        return True
    if "answers written on this page" in text and "will not be marked" in text:
        return True
    alpha = re.sub(r"[^a-z]+", "", text)
    return len(alpha) < 16


def crop_question(doc: fitz.Document, starts: List[StartPos], qnum: int, out_prefix: Path, kind: str) -> List[str]:
    idx = next((i for i, s in enumerate(starts) if s.qnum == qnum), None)
    if idx is None:
        return []

    s = starts[idx]
    n = starts[idx + 1] if idx + 1 < len(starts) else None
    last_page = n.page if n is not None else len(doc) - 1
    out: List[str] = []

    for pno in range(s.page, last_page + 1):
        page = doc[pno]
        left, right = 18.0, float(page.rect.width) - 18.0
        top = 42.0
        bottom = float(page.rect.height) - 18.0
        if pno == s.page:
            top = max(32.0, s.y - 8.0)
        if n is not None and pno == n.page:
            bottom = min(bottom, n.y - 2.0)
        if bottom <= top + 80.0:
            continue

        clip = fitz.Rect(left, top, right, bottom)
        if is_blank_answer_page(page, clip) and pno != s.page:
            continue

        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
        if s.page == last_page:
            out_file = out_prefix.with_suffix('.png')
        else:
            out_file = out_prefix.parent / f"{out_prefix.name}_p{pno - s.page + 1}.png"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out_file))
        out.append(out_file.relative_to(ROOT / "data" / "physics" / "processed").as_posix())

    return out


def parse_question_text_blocks(doc: fitz.Document) -> Dict[int, str]:
    text = "\n".join((doc[p].get_text("text") or "") for p in range(len(doc)))
    # Remove heavy legal pages before first numbered question line.
    mstart = re.search(r"(?m)^\s*1\.\s", text)
    if mstart:
        text = text[mstart.start():]

    patt = re.compile(r"(?ms)^\s*(?P<num>\d{1,2})\.\s*(?P<body>.*?)(?=^\s*\d{1,2}\.\s|\Z)")
    out: Dict[int, str] = {}
    for m in patt.finditer(text):
        q = int(m.group("num"))
        out[q] = norm_ws(m.group("body"))
    return out


def parse_marks_from_text(block: str) -> Optional[int]:
    nums = [int(x) for x in re.findall(r"\[(\d{1,2})\]", block)]
    if not nums:
        return None
    # heuristic: part-marks sum for total, capped for outliers
    s = sum(nums)
    if s <= 0:
        return None
    if s > 80:
        return max(nums)
    return s


def main() -> None:
    payload = json.loads(MANUAL.read_text(encoding="utf-8"))
    papers = payload.get("papers", [])
    questions: List[dict] = []

    for p in papers:
        paper_rel = p["paper_path"]
        ms_rel = p.get("markscheme_path")
        paper_path = ROOT / "data" / paper_rel
        ms_path = ROOT / "data" / ms_rel if ms_rel else None
        if not paper_path.exists():
            continue

        paper_doc = fitz.open(paper_path)
        ms_doc = fitz.open(ms_path) if ms_path and ms_path.exists() else None

        q_starts = detect_starts(paper_doc, "paper")
        ms_starts = detect_starts(ms_doc, "markscheme") if ms_doc else []
        q_text = parse_question_text_blocks(paper_doc)

        qnums = sorted({s.qnum for s in q_starts})

        session_prefix = "m" if str(p.get("session", "")).lower().startswith("may") else "n"
        session_code = f"{session_prefix}{str(p['year'])[-2:]}"

        for qn in qnums:
            base = f"phys_{session_code}_p{str(p['paperCode']).lower()}_{str(p['timezone']).lower()}_q{qn}_{str(p['level']).lower()}"
            q_img_prefix = IMAGES_ROOT / "questions" / base
            ms_img_prefix = IMAGES_ROOT / "markschemes" / base

            q_images = crop_question(paper_doc, q_starts, qn, q_img_prefix, "paper")
            ms_images = crop_question(ms_doc, ms_starts, qn, ms_img_prefix, "markscheme") if ms_doc else []

            block = q_text.get(qn, "")
            topic, subtopic = infer_topic(block, str(p["paperCode"]))

            questions.append(
                {
                    "id": base,
                    "paper": p["paperLabel"],
                    "session": p["session"],
                    "session_code": session_code,
                    "paper_type": f"Paper {p['paperCode']}",
                    "level": p["level"],
                    "question_number": str(qn),
                    "title": f"Q{qn}: {block[:120]}" if block else f"Q{qn}",
                    "topic": topic,
                    "subtopic": subtopic,
                    "topic_confidence": 0.55 if topic != "Unsorted" else 0.1,
                    "topic_reason": ["physics keyword classification"],
                    "question_text": block,
                    "answer_text": "",
                    "marks": parse_marks_from_text(block),
                    "has_markscheme": bool(ms_images),
                    "source": {
                        "paper_file": Path(paper_rel).name,
                        "markscheme_file": Path(ms_rel).name if ms_rel else "",
                    },
                    "question_image_paths": q_images,
                    "markscheme_image_paths": ms_images,
                }
            )

        paper_doc.close()
        if ms_doc:
            ms_doc.close()

    questions.sort(key=lambda x: (x.get("paper", ""), int(x.get("question_number", "0"))))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"questions": questions}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(questions)} physics questions -> {OUT}")


if __name__ == "__main__":
    main()
