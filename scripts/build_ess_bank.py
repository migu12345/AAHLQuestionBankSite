#!/usr/bin/env python3
"""
Discovers all English ESS question PDFs from the IB past papers archive,
pairs them with markschemes, crops question images using fitz, infers
ESS topics, and writes data/ess/processed/questions.json.

Usage:
  python3 scripts/build_ess_bank.py
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

import fitz  # type: ignore

SOURCE = Path("/Users/s933863@aics.espritscholen.nl/Desktop/Downloads/IB PAST PAPERS - YEAR")
OUT = ROOT / "data" / "ess" / "processed" / "questions.json"
IMAGES_ROOT = ROOT / "data" / "ess" / "processed" / "images"
TEXT_BOOKLETS_DIR = ROOT / "data" / "ess" / "processed" / "text_booklets"

NON_ENGLISH = [
    "french", "german", "spanish", "dutch", "arabic", "chinese", "japanese",
    "italian", "portuguese", "swedish", "afrikaans", "malay", "turkish",
]


# ---------------------------------------------------------------------------
# PDF discovery
# ---------------------------------------------------------------------------

def is_english(path: Path) -> bool:
    name_lower = path.name.lower()
    return not any(lang in name_lower for lang in NON_ENGLISH)


def parse_session_year(path: Path) -> Optional[Tuple[str, int]]:
    year = None
    session = None
    for part in path.parts:
        m = re.search(r"(20\d\d)", part)
        if m and year is None:
            year = int(m.group(1))
        pl = part.lower()
        if "may" in pl:
            session = "May"
        elif "november" in pl:
            session = "November"
    if year and session:
        return session, year
    return None


def parse_ess_meta(path: Path, session: str, year: int) -> Optional[dict]:
    name = path.name.lower()
    if not is_english(path):
        return None
    if "environmental_systems" not in name and "environmental systems" not in name:
        return None
    # Skip stimulus/resource material — not question content
    if "text_booklet" in name or "text booklet" in name:
        return None
    if "resource_booklet" in name or "resource booklet" in name:
        return None

    is_ms = "markscheme" in name

    paper_m = re.search(r"paper[_ ]+(\d)", name)
    if not paper_m:
        return None
    paper_num = paper_m.group(1)

    # Timezone
    tz_m = re.search(r"tz([123])", name)
    if tz_m:
        tz = f"TZ{tz_m.group(1)}"
    elif session == "November":
        tz = "NTZ"
    else:
        tz = "TZ1"

    return {
        "year": year,
        "session": session,
        "paper": paper_num,
        "tz": tz,
        "is_ms": is_ms,
        "path": path,
    }


def discover_papers() -> List[dict]:
    all_pdfs = list(SOURCE.rglob("*.pdf"))
    print(f"Scanning {len(all_pdfs)} PDFs in archive...")
    results = []
    seen_keys: dict[tuple, Path] = {}  # deduplicate by (year, session, paper, tz, is_ms)
    for pdf in all_pdfs:
        meta_sy = parse_session_year(pdf)
        if meta_sy is None:
            continue
        session, year = meta_sy
        meta = parse_ess_meta(pdf, session, year)
        if meta is None:
            continue
        key = (year, session, meta["paper"], meta["tz"], meta["is_ms"])
        # Prefer PDFs/ folder over HTML/ folder for dedup
        if key in seen_keys:
            existing = seen_keys[key]
            if "PDFs" in str(pdf) and "HTML" in str(existing):
                seen_keys[key] = pdf
        else:
            seen_keys[key] = pdf

    for (year, session, paper, tz, is_ms), path in seen_keys.items():
        results.append({"year": year, "session": session, "paper": paper, "tz": tz, "is_ms": is_ms, "path": path})

    return results


def discover_text_booklets() -> dict[tuple, Path]:
    """
    Returns a dict keyed by (paper, year, session, tz) → source PDF path.

    2010–2016: resource/text booklet was on Paper 2.
    2017+:     text/resource booklet is on Paper 1 (syllabus change).
    Both 'text_booklet' and 'resource_booklet' naming are accepted.
    """
    seen_keys: dict[tuple, Path] = {}

    for pdf in SOURCE.rglob("*.pdf"):
        if not is_english(pdf):
            continue
        name = pdf.name.lower()
        if "environmental_systems" not in name:
            continue
        is_text = "text_booklet" in name or "resource_booklet" in name
        if not is_text or "markscheme" in name:
            continue

        paper_m = re.search(r"paper[_ ]+(\d)", name)
        if not paper_m:
            continue
        paper_num = paper_m.group(1)

        meta_sy = parse_session_year(pdf)
        if meta_sy is None:
            continue
        session, year = meta_sy

        tz_m = re.search(r"tz([123])", name)
        if tz_m:
            tz = f"TZ{tz_m.group(1)}"
        elif session == "November":
            tz = "NTZ"
        else:
            tz = "TZ1"

        key = (paper_num, year, session, tz)
        if key in seen_keys:
            existing = seen_keys[key]
            if "PDFs" in str(pdf) and "HTML" in str(existing):
                seen_keys[key] = pdf
        else:
            seen_keys[key] = pdf

    return seen_keys


def copy_text_booklets(tb_index: dict[tuple, Path]) -> dict[tuple, str]:
    """
    Copies each booklet into TEXT_BOOKLETS_DIR with a canonical name.
    Returns a dict (paper, year, session, tz) → relative path from processed/.
    """
    import shutil
    TEXT_BOOKLETS_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[tuple, str] = {}
    for (paper_num, year, session, tz), src in tb_index.items():
        sc = ("m" if session == "May" else "n") + str(year)[-2:]
        tz_slug = tz.lower()
        dest_name = f"ess_{sc}_p{paper_num}_{tz_slug}_text_booklet.pdf"
        dest = TEXT_BOOKLETS_DIR / dest_name
        if not dest.exists():
            shutil.copy2(src, dest)
        result[(paper_num, year, session, tz)] = f"text_booklets/{dest_name}"
    return result


# ---------------------------------------------------------------------------
# Topic inference
# ---------------------------------------------------------------------------

def clean_text(s: str) -> str:
    s = s.lower().replace("-", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def kw_match(text: str, kw: str) -> bool:
    if not kw:
        return False
    pattern = r"\b" + re.escape(kw.lower()) + r"\b"
    return bool(re.search(pattern, text))


def infer_topic(question_text: str) -> Tuple[str, str]:
    t = clean_text(question_text)

    rules = [
        # Topic 1: Foundations of ESS
        (
            ["systems thinking", "feedback", "positive feedback", "negative feedback",
             "open system", "closed system", "emergent", "sustainability", "environmental value",
             "ecological worldview", "anthropocentric", "biocentric", "ecocentric",
             "systems model", "input", "output", "stock", "flow"],
            "Topic 1: Foundations of ESS",
            "Systems and sustainability",
        ),
        # Topic 2: Ecosystems and ecology
        (
            ["biotic", "abiotic", "producer", "consumer", "decomposer", "detritivore",
             "food chain", "food web", "trophic level", "energy flow", "productivity",
             "gross primary", "net primary", "biomass", "nutrient cycle", "carbon cycle",
             "nitrogen cycle", "phosphorus cycle", "succession", "climax community",
             "resilience", "stability", "biome", "habitat", "population", "community",
             "ecosystem", "limiting factor", "carrying capacity"],
            "Topic 2: Ecosystems and ecology",
            "Ecosystems",
        ),
        # Topic 3: Biodiversity and conservation
        (
            ["biodiversity", "species richness", "species evenness", "genetic diversity",
             "simpson", "extinction", "invasive species", "endemic", "iucn", "red list",
             "protected area", "national park", "conservation", "habitat loss",
             "habitat fragmentation", "keystone species", "indicator species",
             "in situ", "ex situ", "captive breeding"],
            "Topic 3: Biodiversity and conservation",
            "Biodiversity",
        ),
        # Topic 4: Water and aquatic food production
        (
            ["aquifer", "water cycle", "hydrological", "freshwater", "marine",
             "ocean acidification", "eutrophication", "algal bloom", "fishery",
             "overfishing", "aquaculture", "dead zone", "runoff", "watershed",
             "water scarcity", "water pollution", "groundwater", "irrigation",
             "fish stock", "bycatch"],
            "Topic 4: Water and aquatic food production",
            "Water systems",
        ),
        # Topic 5: Soil and terrestrial food production
        (
            ["soil", "soil horizon", "humus", "mineralization", "pedogenesis",
             "erosion", "desertification", "salinization", "agriculture", "monoculture",
             "crop yield", "fertilizer", "pesticide", "organic farming", "permaculture",
             "deforestation", "slash and burn", "soil degradation", "land use",
             "food security", "food production"],
            "Topic 5: Soil and terrestrial food production",
            "Soil systems",
        ),
        # Topic 6: Atmospheric systems
        (
            ["atmosphere", "ozone", "uv radiation", "cfc", "photochemical smog",
             "acid rain", "acid deposition", "sulfur dioxide", "nitrogen oxide",
             "particulate", "air pollution", "stratosphere", "troposphere",
             "albedo", "temperature inversion"],
            "Topic 6: Atmospheric systems and societies",
            "Atmospheric systems",
        ),
        # Topic 7: Climate change and energy
        (
            ["greenhouse gas", "greenhouse effect", "carbon dioxide", "methane",
             "global warming", "climate change", "ipcc", "sea level", "coral bleaching",
             "fossil fuel", "renewable energy", "solar energy", "wind energy",
             "hydroelectric", "nuclear", "biomass energy", "carbon footprint",
             "emissions", "kyoto", "paris agreement", "mitigation", "adaptation"],
            "Topic 7: Climate change and energy production",
            "Climate and energy",
        ),
        # Topic 8: Human systems and resource use
        (
            ["population growth", "urbanization", "demographic", "ecological footprint",
             "biocapacity", "overshoot", "non renewable", "resource depletion",
             "solid waste", "recycling", "hdi", "gdp", "poverty", "resource use",
             "consumption", "waste management", "e-waste", "mining", "natural resource"],
            "Topic 8: Human systems and resource use",
            "Human systems",
        ),
    ]

    scored: List[Tuple[int, str, str]] = []
    for kws, topic, sub in rules:
        matched = [kw for kw in kws if kw_match(t, kw)]
        if matched:
            score = len(matched) * 10 + sum(min(len(m), 20) for m in matched)
            scored.append((score, topic, sub))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1], scored[0][2]

    return "Unsorted", "Unsorted"


# ---------------------------------------------------------------------------
# Question detection and cropping (adapted from biology build script)
# ---------------------------------------------------------------------------

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


def detect_starts(doc: fitz.Document, kind: str) -> List[StartPos]:
    starts: Dict[int, tuple] = {}
    ms_data_start_page = 0

    if kind == "markscheme":
        # Primary detection: find the first page with actual answer content —
        # "[N]" mark tokens together with "award" or "accept" keywords. This correctly
        # skips generic instructions pages (which use numbered list items that confuse
        # the question-start detector in newer ESS PDFs).
        for pno in range(len(doc)):
            t = (doc[pno].get_text("text") or "").lower()
            if "environmental systems and societies uses marking points" in t:
                continue  # skip the generic marking instructions page
            if re.search(r"\[\d+\]", t) and ("award" in t or "accept" in t or "do not accept" in t):
                ms_data_start_page = pno
                break
        # Fallback: original heuristic
        if ms_data_start_page == 0:
            for pno in range(len(doc)):
                t = (doc[pno].get_text("text") or "").lower()
                if "question" in t and "answers" in t and "total" in t and "subject details" not in t:
                    ms_data_start_page = pno
                    break

    for pno in range(len(doc)):
        if kind == "markscheme" and pno < ms_data_start_page:
            continue
        page = doc[pno]
        page_text_lower = (page.get_text("text") or "").lower()
        if "all other texts, graphics and illustrations" in page_text_lower:
            continue
        if "disclaimer:" in page_text_lower and "references:" in page_text_lower:
            continue
        # Skip the ESS generic marking instructions page (newer PDFs place it after the
        # Q&A table header, so ms_data_start_page doesn't exclude it). This page always
        # opens with "1. Environmental systems and societies uses marking points..." which
        # detect_starts would incorrectly treat as question 1.
        if kind == "markscheme" and "environmental systems and societies uses marking points" in page_text_lower:
            continue
        if page_text_lower.lstrip().startswith("references:"):
            continue

        page_rot = page.rotation
        rot_mat = page.rotation_matrix
        blocks = page.get_text("dict").get("blocks", [])
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
                x_raw = float(line.get("bbox", [0, 0, 0, 0])[0])
                y_raw = float(line.get("bbox", [0, 0, 0, 0])[1])
                if page_rot != 0:
                    pt = fitz.Point(x_raw, y_raw) * rot_mat
                    x, y = pt.x, pt.y
                else:
                    x, y = x_raw, y_raw
                if kind == "markscheme" and y >= 730:
                    continue

                qn: Optional[int] = None
                score = 0
                m_plain = re.match(r"^(\d{1,2})$", text)
                m_dot = re.match(r"^(\d{1,2})\.$", text)
                m_inline = re.match(r"^(\d{1,2})\.\s+", text)
                ms_q_col = kind == "markscheme" and x <= 65

                if m_plain and (ms_q_col or (kind != "markscheme" and x <= 65)):
                    pending = int(m_plain.group(1))
                    pending_y = y
                    pending_x = x
                    score = 1
                elif m_dot:
                    if kind != "markscheme" or x <= 65:
                        pending = int(m_dot.group(1))
                        pending_y = y
                        pending_x = x
                        qn = pending
                        score = 4
                elif m_inline:
                    if kind != "markscheme" or x <= 65:
                        qn = int(m_inline.group(1))
                        score = 5

                if kind == "markscheme":
                    m_ms = re.match(r"^(\d{1,2})\s+[A-Za-z(]", text)
                    if m_ms and x <= 65:
                        qn = int(m_ms.group(1))
                        score = max(score, 6)

                if qn is None and pending is not None and ((kind == "markscheme" and x <= 150) or x <= 120) and re.match(r"^(?:\(|[A-Za-z])", text):
                    qn = pending
                    score = max(score, 2)

                if qn is not None and 1 <= qn <= 40:
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
                                if eff_x < prev_x - 0.5:
                                    replace = True
                                elif abs(eff_x - prev_x) <= 0.5 and (pno < prev_page or (pno == prev_page and eff_y < prev_y)):
                                    replace = True
                        if replace:
                            starts[qn] = (pno, eff_y, eff_x, cand_score)
                        pending = None
                        pending_y = None
                        pending_x = None

    out = [StartPos(qnum=q, page=pg, y=y) for q, (pg, y, _x, _score) in starts.items()]
    out.sort(key=lambda s: (s.page, s.y))
    return out


def is_blank_answer_page(page: fitz.Page, clip: fitz.Rect) -> bool:
    text = page.get_text("text", clip=clip).lower()
    if "please do not write on this page" in text:
        return True
    if "answers written on this page" in text and "will not be marked" in text:
        return True
    if "all other texts, graphics and illustrations" in text:
        return True
    if "disclaimer:" in text and "references:" in text:
        return True
    alpha = re.sub(r"[^a-z]+", "", text)
    if len(alpha) < 16:
        return True
    stripped = re.sub(r"[a-z]\d+/[\d/a-z]+", " ", text)
    stripped = re.sub(r"[–\-]\s*\d+\s*[–\-]", " ", stripped)
    stripped = stripped.replace("turn over", " ")
    if len(re.sub(r"[^a-z]+", "", stripped)) < 30:
        return True
    return False


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
            out_file = out_prefix.with_suffix(".png")
        else:
            out_file = out_prefix.parent / f"{out_prefix.name}_p{pno - s.page + 1}.png"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(out_file))
        out.append(out_file.relative_to(ROOT / "data" / "ess" / "processed").as_posix())

    return out


def parse_question_text_blocks(doc: fitz.Document) -> Dict[int, str]:
    text = "\n".join((doc[p].get_text("text") or "") for p in range(len(doc)))
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
    s = sum(nums)
    if s <= 0:
        return None
    if s > 80:
        return max(nums)
    return s


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def session_code(session: str, year: int) -> str:
    prefix = "m" if session == "May" else "n"
    return f"{prefix}{str(year)[-2:]}"


def paper_label(session: str, year: int, paper: str, tz: str) -> str:
    tz_str = f" {tz}" if tz not in ("TZ1", "NTZ") else ("")
    if tz == "NTZ":
        tz_str = ""
    return f"{session} {year} ESS Paper {paper}{tz_str} SL"


def main() -> None:
    papers = discover_papers()
    q_papers = sorted([p for p in papers if not p["is_ms"]], key=lambda p: (p["year"], p["session"], p["paper"], p["tz"]))
    ms_papers = [p for p in papers if p["is_ms"]]

    ms_index: dict[tuple, Path] = {}
    for ms in ms_papers:
        k = (ms["year"], ms["session"], ms["paper"], ms["tz"])
        if k not in ms_index:
            ms_index[k] = ms["path"]

    tb_source = discover_text_booklets()
    tb_index = copy_text_booklets(tb_source)
    print(f"Found {len(q_papers)} ESS question papers, {len(ms_papers)} markschemes, {len(tb_index)} text booklets")

    questions: List[dict] = []

    for p in q_papers:
        paper_path = p["path"]
        ms_key = (p["year"], p["session"], p["paper"], p["tz"])
        ms_path = ms_index.get(ms_key)

        print(f"  Processing {paper_path.name} ...", end=" ", flush=True)

        try:
            paper_doc = fitz.open(paper_path)
        except Exception as e:
            print(f"SKIP (open failed: {e})")
            continue

        ms_doc = None
        if ms_path and ms_path.exists():
            try:
                ms_doc = fitz.open(ms_path)
            except Exception:
                pass

        q_starts = detect_starts(paper_doc, "paper")
        ms_starts = detect_starts(ms_doc, "markscheme") if ms_doc else []
        q_text = parse_question_text_blocks(paper_doc)

        qnums = sorted({s.qnum for s in q_starts})
        sc = session_code(p["session"], p["year"])
        tz_slug = p["tz"].lower().replace("ntz", "ntz")
        label = paper_label(p["session"], p["year"], p["paper"], p["tz"])

        print(f"{len(qnums)} questions")

        # Text booklet lookup. 2010–2016: booklet was on Paper 2.
        # 2017+: booklet is on Paper 1. Try exact TZ, fall back to shared TZ.
        def _tb(paper_num: str, tz: str) -> str:
            return (
                tb_index.get((paper_num, p["year"], p["session"], tz))
                or tb_index.get((paper_num, p["year"], p["session"], "TZ1"))
                or tb_index.get((paper_num, p["year"], p["session"], "NTZ"))
                or ""
            )
        tb_rel: str = _tb(p["paper"], p["tz"])

        for qn in qnums:
            base = f"ess_{sc}_p{p['paper']}_{tz_slug}_q{qn}"
            q_img_prefix = IMAGES_ROOT / "questions" / base
            ms_img_prefix = IMAGES_ROOT / "markschemes" / base

            q_images = crop_question(paper_doc, q_starts, qn, q_img_prefix, "paper")
            ms_images = crop_question(ms_doc, ms_starts, qn, ms_img_prefix, "markscheme") if ms_doc else []

            block = q_text.get(qn, "")
            topic, subtopic = infer_topic(block)
            marks = parse_marks_from_text(block)
            paper_type = f"Paper {p['paper']}"

            questions.append({
                "id": base,
                "paper": label,
                "session": p["session"],
                "session_code": sc,
                "paper_type": paper_type,
                "level": "SL",
                "question_number": str(qn),
                "title": f"Q{qn}: {block[:120]}" if block else f"Q{qn}",
                "topic": topic,
                "subtopic": subtopic,
                "question_text": block,
                "answer_text": "",
                "marks": marks,
                "has_markscheme": bool(ms_images),
                "text_booklet_path": tb_rel,
                "source": {
                    "paper_file": paper_path.name,
                    "markscheme_file": ms_path.name if ms_path else "",
                },
                "question_image_paths": q_images,
                "markscheme_image_paths": ms_images,
            })

        paper_doc.close()
        if ms_doc:
            ms_doc.close()

    questions.sort(key=lambda x: (x.get("paper", ""), int(x.get("question_number", "0"))))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"questions": questions}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(questions)} ESS questions -> {OUT}")


if __name__ == "__main__":
    main()
