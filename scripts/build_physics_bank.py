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


def infer_topic(question_text: str, paper_code: str) -> tuple[str, str, float, List[str]]:
    t = clean_text_for_topic(question_text)
    common_rules = [
        (
            ["velocity", "acceleration", "displacement", "position time", "speed time", "kinematic"],
            "Space, time and motion",
            "Kinematics",
        ),
        (
            ["force", "momentum", "newton", "projectile", "impulse", "collision"],
            "Space, time and motion",
            "Forces and momentum",
        ),
        (
            ["kinetic", "potential energy", "power", "work done", "efficiency"],
            "Space, time and motion",
            "Work, energy and power",
        ),
        (
            ["circular", "rotational", "angular velocity", "angular acceleration", "torque", "moment of inertia"],
            "Space, time and motion",
            "Circular and rotational motion",
        ),
        (
            ["specific heat", "latent heat", "thermal", "thermodynamic", "entropy", "temperature", "internal energy"],
            "The particulate nature of matter",
            "Thermal physics",
        ),
        (
            ["gas law", "boyle", "charles", "ideal gas", "avogadro", "pressure volume", "pv"],
            "The particulate nature of matter",
            "Gas laws",
        ),
        (
            ["density", "young modulus", "stress", "strain", "material"],
            "The particulate nature of matter",
            "Material properties",
        ),
        (
            ["current", "voltage", "resistance", "emf", "circuit", "ohm", "kirchhoff", "capacitor"],
            "The particulate nature of matter",
            "Electric circuits",
        ),
        (
            ["wave", "frequency", "wavelength", "interference", "diffraction"],
            "Wave behaviour",
            "Wave properties",
        ),
        (
            ["lens", "mirror", "focal length", "magnification", "telescope", "microscope", "refraction", "refractive index", "critical angle", "total internal reflection", "polarization", "optical"],
            "Wave behaviour",
            "Optics",
        ),
        (
            ["standing wave", "superposition", "node", "antinode", "harmonic", "beats"],
            "Wave behaviour",
            "Superposition and standing waves",
        ),
        (
            ["doppler", "sound level", "decibel", "intensity level", "open pipe", "closed pipe"],
            "Wave behaviour",
            "Doppler and sound",
        ),
        (
            ["capacitor", "capacitance", "dielectric"],
            "Fields",
            "Capacitance",
        ),
        (
            ["electric field", "magnetic field", "lorentz", "coulomb"],
            "Fields",
            "Electric and magnetic fields",
        ),
        (
            ["induction", "flux", "faraday", "lenz", "generator", "transformer"],
            "Fields",
            "Electromagnetic induction",
        ),
        (
            ["gravitational field", "g field", "gravitational potential"],
            "Fields",
            "Gravitational fields",
        ),
        (
            ["photon", "de broglie", "quantum", "electronvolt", "photoelectric", "matter wave"],
            "Nuclear and quantum physics",
            "Quantum/modern physics",
        ),
        (
            ["radioactive", "decay", "half life"],
            "Nuclear and quantum physics",
            "Radioactivity",
        ),
        (
            ["fission", "fusion", "binding energy", "mass defect", "nuclear reaction"],
            "Nuclear and quantum physics",
            "Nuclear reactions",
        ),
        (
            ["relativity", "time dilation", "length contraction", "proper time", "lorentz factor", "speed of light"],
            "Space, time and motion",
            "Relativity",
        ),
        (
            ["black hole", "nebula", "hubble", "redshift", "big bang", "dark matter", "dark energy", "supernova", "white dwarf", "cosmic", "galaxy", "stellar", "jeans criterion"],
            "Space, time and motion",
            "A5 relativity",
        ),
        (
            ["uncertainty", "percentage uncertainty", "gradient", "best fit", "error bars", "precision", "accuracy", "systematic"],
            "Experimental analysis",
            "Data-based and practical skills",
        ),
    ]

    is_mcq = paper_code.upper() in {"1", "1A"}
    # Use richer matching for MCQ papers; fall back to mixed bucket only when no rules match.
    if is_mcq:
        for kws, topic, sub in common_rules:
            hits = sum(1 for kw in kws if kw in t)
            if hits > 0:
                confidence = 0.8 if hits >= 2 else 0.65
                return (topic, sub, confidence, [f"keyword match: {hits}"])
        return ("A-E mixed", "Multiple-choice mixed", 0.25, ["no confident MCQ keyword match"])

    for kws, topic, sub in common_rules:
        hits = sum(1 for kw in kws if kw in t)
        if hits > 0:
            confidence = 0.75 if hits >= 2 else 0.6
            return (topic, sub, confidence, [f"keyword match: {hits}"])

    # Avoid large "Unsorted" buckets for old papers with sparse/OCR-light text.
    pcode = paper_code.upper()
    if pcode == "3":
        return ("Experimental analysis", "Data-based and practical skills", 0.2, ["paper 3 fallback"])
    if pcode == "2":
        return ("Experimental analysis", "Data-based and practical skills", 0.2, ["paper 2 fallback"])
    return ("Unsorted", "Unsorted", 0.1, ["no keyword match"])


def detect_starts(doc: fitz.Document, kind: str) -> List[StartPos]:
    starts: Dict[int, tuple[int, float, float, int]] = {}
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
                score = 0
                m_plain = re.match(r"^(\d{1,2})$", text)
                m_dot = re.match(r"^(\d{1,2})\.$", text)
                m_inline = re.match(r"^(\d{1,2})\.\s+", text)

                if m_plain and (kind == "markscheme" or x <= 90):
                    pending = int(m_plain.group(1))
                    pending_y = y
                    pending_x = x
                    score = 1
                elif m_dot:
                    pending = int(m_dot.group(1))
                    pending_y = y
                    pending_x = x
                    qn = pending
                    score = 4
                elif m_inline:
                    qn = int(m_inline.group(1))
                    score = 5

                if kind == "markscheme":
                    m_ms = re.match(r"^(\d{1,2})\s+", text)
                    if m_ms:
                        qn = int(m_ms.group(1))
                        score = max(score, 6)

                if qn is None and pending is not None and x <= 120 and re.match(r"^(?:\(|[A-Za-z])", text):
                    qn = pending
                    score = max(score, 2)

                if qn is not None and 1 <= qn <= 60:
                    eff_y = pending_y if pending_y is not None else y
                    eff_x = pending_x if pending_x is not None else x
                    left_bonus = 2 if eff_x <= 70 else (1 if eff_x <= 120 else 0)
                    cand_score = score + left_bonus

                    if eff_x <= 120 or kind == "markscheme":
                        prev = starts.get(qn)
                        replace = False
                        if prev is None:
                            replace = True
                        else:
                            prev_page, prev_y, prev_x, prev_score = prev
                            if cand_score > prev_score:
                                replace = True
                            elif cand_score == prev_score:
                                # Prefer the leftmost candidate, then earlier page/y.
                                if eff_x < prev_x - 0.5:
                                    replace = True
                                elif abs(eff_x - prev_x) <= 0.5 and (pno < prev_page or (pno == prev_page and eff_y < prev_y)):
                                    replace = True
                        if replace:
                            starts[qn] = (pno, eff_y, eff_x, cand_score)
                        pending = None
                        pending_y = None
                        pending_x = None

                prev = text

    out = [StartPos(qnum=q, page=pg, y=y) for q, (pg, y, _x, _score) in starts.items()]
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


def crop_question(
    doc: fitz.Document,
    starts: List[StartPos],
    qnum: int,
    out_prefix: Path,
    kind: str,
    top_offset: float = -8.0,
) -> List[str]:
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
            top = max(32.0, s.y + top_offset)
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


def parse_mcq_answers(ms_doc: Optional[fitz.Document]) -> Dict[int, str]:
    if ms_doc is None:
        return {}
    text = "\n".join((ms_doc[p].get_text("text") or "") for p in range(len(ms_doc)))
    text = text.replace("–", "-").replace("—", "-")
    answers: Dict[int, str] = {}
    patt = re.compile(r"(?:(?<=\n)|(?<=\s))(\d{1,2})\.?\s*([A-D]|-)\b")
    for m in patt.finditer(text):
        qn = int(m.group(1))
        if not (1 <= qn <= 60):
            continue
        ans = m.group(2).upper()
        if ans in {"A", "B", "C", "D"}:
            answers[qn] = ans
    return answers


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
        paper_code = str(p.get("paperCode", "")).upper()
        is_mcq_paper = paper_code in {"1", "1A"}
        mcq_answers = parse_mcq_answers(ms_doc) if is_mcq_paper else {}
        q_text = parse_question_text_blocks(paper_doc)

        qnums = sorted({s.qnum for s in q_starts})

        session_prefix = "m" if str(p.get("session", "")).lower().startswith("may") else "n"
        session_code = f"{session_prefix}{str(p['year'])[-2:]}"

        for qn in qnums:
            base = f"phys_{session_code}_p{str(p['paperCode']).lower()}_{str(p['timezone']).lower()}_q{qn}_{str(p['level']).lower()}"
            q_img_prefix = IMAGES_ROOT / "questions" / base
            ms_img_prefix = IMAGES_ROOT / "markschemes" / base

            q_top_offset = -16.0 if is_mcq_paper else -8.0
            q_images = crop_question(paper_doc, q_starts, qn, q_img_prefix, "paper", top_offset=q_top_offset)
            ms_images = (
                []
                if is_mcq_paper
                else (crop_question(ms_doc, ms_starts, qn, ms_img_prefix, "markscheme") if ms_doc else [])
            )
            mcq_answer = mcq_answers.get(qn, "")

            block = q_text.get(qn, "")
            topic, subtopic, topic_confidence, topic_reason = infer_topic(block, str(p["paperCode"]))

            questions.append(
                {
                    "id": base,
                    "paper": p["paperLabel"],
                    "session": p["session"],
                    "session_code": session_code,
                    "paper_type": "Paper 1A" if is_mcq_paper else f"Paper {p['paperCode']}",
                    "level": p["level"],
                    "question_number": str(qn),
                    "title": f"Q{qn}: {block[:120]}" if block else f"Q{qn}",
                    "topic": topic,
                    "subtopic": subtopic,
                    "topic_confidence": topic_confidence,
                    "topic_reason": topic_reason,
                    "question_text": block,
                    "answer_text": f"Answer: {mcq_answer}" if mcq_answer else "",
                    "mcq_answer": mcq_answer,
                    "marks": parse_marks_from_text(block),
                    "has_markscheme": bool(ms_images or mcq_answer),
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
