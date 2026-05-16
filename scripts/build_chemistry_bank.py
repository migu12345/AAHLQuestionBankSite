#!/usr/bin/env python3
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

MANUAL = ROOT / "data" / "chemistry" / "processed" / "manual_papers.json"
OUT = ROOT / "data" / "chemistry" / "processed" / "questions.json"
IMAGES_ROOT = ROOT / "data" / "chemistry" / "processed" / "images"

TOPIC_OVERRIDES: Dict[str, tuple[str, str, float, List[str]]] = {}


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


def keyword_in_text(text: str, keyword: str) -> bool:
    kw = keyword.lower().strip()
    if not kw:
        return False
    pattern = r"\b" + re.escape(kw) + r"\b"
    if re.search(pattern, text) is not None:
        return True
    if " " not in kw:
        for suffix in ("s", "es"):
            if re.search(r"\b" + re.escape(kw + suffix) + r"\b", text) is not None:
                return True
    return False


def infer_topic(question_text: str, paper_code: str) -> tuple[str, str, float, List[str]]:
    # IB Chemistry 2025+ curriculum (first examined May 2025).
    # Structure 1–3 and Reactivity 1–3.
    t = clean_text_for_topic(question_text)
    rules = [
        # Structure 1: Particulate nature of matter
        (
            ["atom", "molecule", "ion", "element", "compound", "mixture", "solid", "liquid", "gas",
             "state of matter", "kinetic theory", "brownian motion", "particle model", "pure substance"],
            "Structure 1: Particulate nature of matter",
            "S1.1 Introduction to particulate matter",
        ),
        (
            ["nucleus", "proton", "neutron", "electron", "atomic number", "mass number", "isotope",
             "relative atomic mass", "nuclear charge", "nuclear model", "rutherford", "bohr", "subatomic"],
            "Structure 1: Particulate nature of matter",
            "S1.2 The nuclear atom",
        ),
        (
            ["electron configuration", "shell", "subshell", "orbital", "aufbau", "pauli", "hund",
             "ionization energy", "electron affinity", "first ionization", "successive ionization",
             "energy level", "principal quantum number", "s orbital", "p orbital", "d orbital",
             "electromagnetic spectrum", "emission spectrum", "absorption spectrum", "photon", "wavelength"],
            "Structure 1: Particulate nature of matter",
            "S1.3 Electron configurations",
        ),
        (
            ["mole", "avogadro", "molar mass", "relative molecular mass", "empirical formula",
             "molecular formula", "percentage composition", "limiting reagent", "theoretical yield",
             "stoichiometry", "mass spectrometry", "mass spectrum"],
            "Structure 1: Particulate nature of matter",
            "S1.4 Counting particles: The mole",
        ),
        (
            ["ideal gas", "gas law", "pressure", "volume", "temperature", "boyle", "charles",
             "avogadro law", "pv", "nrt", "kelvin", "molar volume", "real gas", "van der waals"],
            "Structure 1: Particulate nature of matter",
            "S1.5 Ideal gases",
        ),
        # Structure 2: Bonding and structure
        (
            ["ionic bond", "ionic compound", "lattice energy", "cation", "anion", "electrostatic",
             "ionic radius", "coordination number", "nacl", "sodium chloride", "crystal lattice",
             "ionic structure"],
            "Structure 2: Bonding and structure",
            "S2.1 Ionic bonding and structure",
        ),
        (
            ["covalent bond", "covalent", "lewis structure", "dot and cross", "sigma bond", "pi bond",
             "double bond", "triple bond", "bond order", "bond length", "bond energy", "electronegativity",
             "polarity", "polar covalent", "dipole", "vsepr", "molecular geometry", "bond angle",
             "lone pair", "electron domain", "resonance", "delocalized", "molecular orbital"],
            "Structure 2: Bonding and structure",
            "S2.2 Covalent bonding and structure",
        ),
        (
            ["metallic bond", "metallic", "sea of electrons", "delocalized electrons", "metal",
             "electrical conductivity", "malleability", "ductility", "alloy", "metallic structure"],
            "Structure 2: Bonding and structure",
            "S2.3 Metallic bonding and structure",
        ),
        (
            ["intermolecular force", "van der waals", "london dispersion", "dipole dipole",
             "hydrogen bond", "boiling point", "melting point", "volatility", "viscosity",
             "network covalent", "diamond", "graphite", "fullerene", "nanotube", "polymer",
             "superconductor", "liquid crystal"],
            "Structure 2: Bonding and structure",
            "S2.4 From models to materials (HL)",
        ),
        # Structure 3: Classification of matter
        (
            ["periodic table", "period", "group", "periodicity", "atomic radius", "electronegativity trend",
             "ionization energy trend", "electron affinity trend", "metallic character", "transition metal",
             "d block", "lanthanide", "actinide", "alkali metal", "alkaline earth", "halogen", "noble gas",
             "oxide", "hydroxide", "chloride", "reactivity trend"],
            "Structure 3: Classification of matter",
            "S3.1 The periodic table",
        ),
        (
            ["functional group", "organic", "alkane", "alkene", "alkyne", "alcohol", "aldehyde",
             "ketone", "carboxylic acid", "ester", "ether", "amine", "amide", "halogenoalkane",
             "homologous series", "structural formula", "displayed formula", "skeletal formula",
             "isomer", "structural isomer", "stereoisomer", "optical isomer", "geometric isomer",
             "benzene", "aromatic", "phenol", "iupac", "nomenclature"],
            "Structure 3: Classification of matter",
            "S3.2 Functional groups and organic compounds",
        ),
        # Reactivity 1: What drives chemical reactions?
        (
            ["enthalpy", "calorimetry", "heat of combustion", "heat of neutralization",
             "heat of formation", "bond enthalpy", "hess", "exothermic", "endothermic",
             "enthalpy change", "temperature change", "specific heat capacity", "calorimeter",
             "q = mc", "standard enthalpy"],
            "Reactivity 1: What drives chemical reactions?",
            "R1.1 Measuring enthalpy changes",
        ),
        (
            ["born haber cycle", "lattice enthalpy", "ionization energy cycle", "electron affinity cycle",
             "energy cycle", "formation enthalpy cycle", "hess cycle", "hess law"],
            "Reactivity 1: What drives chemical reactions?",
            "R1.2 Energy cycles in reactions (HL)",
        ),
        (
            ["fuel", "fossil fuel", "combustion", "carbon dioxide", "greenhouse", "climate change",
             "biofuel", "hydrogen fuel", "fuel cell", "nuclear energy", "renewable", "energy density",
             "coal", "petroleum", "natural gas", "alkane combustion"],
            "Reactivity 1: What drives chemical reactions?",
            "R1.3 Energy from fuels",
        ),
        (
            ["entropy", "gibbs", "free energy", "spontaneous", "delta g", "delta s", "delta h",
             "second law", "disorder", "thermodynamics", "feasibility", "spontaneity"],
            "Reactivity 1: What drives chemical reactions?",
            "R1.4 Entropy and spontaneity",
        ),
        # Reactivity 2: How much, how fast and how far?
        (
            ["stoichiometry", "molar ratio", "limiting reactant", "excess reactant", "yield",
             "percentage yield", "concentration", "molarity", "titration", "dilution",
             "solution stoichiometry", "precipitation", "gravimetric"],
            "Reactivity 2: How much, how fast and how far?",
            "R2.1 How much? Stoichiometry",
        ),
        (
            ["rate of reaction", "reaction rate", "rate law", "rate constant", "order of reaction",
             "activation energy", "arrhenius", "catalyst", "enzyme", "collision theory",
             "maxwell boltzmann", "reaction mechanism", "rate determining step", "half life",
             "concentration time graph", "temperature effect on rate"],
            "Reactivity 2: How much, how fast and how far?",
            "R2.2 How fast? Reaction kinetics",
        ),
        (
            ["equilibrium", "le chatelier", "equilibrium constant", "kc", "kp", "equilibrium expression",
             "position of equilibrium", "dynamic equilibrium", "haber process", "contact process",
             "reversible reaction", "equilibrium shift", "concentration effect", "pressure effect"],
            "Reactivity 2: How much, how fast and how far?",
            "R2.3 How far? Chemical equilibrium",
        ),
        # Reactivity 3: What are the mechanisms of change?
        (
            ["acid", "base", "ph", "pka", "pkb", "strong acid", "weak acid", "buffer", "proton",
             "bronsted lowry", "lewis acid", "lewis base", "neutralization", "hydrolysis",
             "amphoteric", "titration curve", "indicator", "autoionization", "water ionization",
             "kw", "hydroxide"],
            "Reactivity 3: What are the mechanisms of change?",
            "R3.1 Proton transfer (acid-base) reactions",
        ),
        (
            ["redox", "oxidation", "reduction", "oxidation state", "oxidation number", "half equation",
             "half reaction", "oxidizing agent", "reducing agent", "electrochemistry", "electrolysis",
             "electrode", "electrolytic cell", "galvanic cell", "voltaic cell", "standard electrode potential",
             "emf", "cell potential", "anode", "cathode", "faraday", "standard hydrogen electrode"],
            "Reactivity 3: What are the mechanisms of change?",
            "R3.2 Electron transfer (redox) reactions",
        ),
        (
            ["substitution", "addition", "elimination", "free radical", "electrophile", "nucleophile",
             "carbocation", "carbanion", "radical", "sn1", "sn2", "e1", "e2", "halogenation",
             "markovnikov", "anti markovnikov", "chain reaction", "initiation", "propagation",
             "termination", "alkene addition", "hydrogenation", "hydration", "halogenoalkane"],
            "Reactivity 3: What are the mechanisms of change?",
            "R3.3 Electron sharing reactions",
        ),
        (
            ["coordination compound", "complex ion", "ligand", "chelate", "dative bond",
             "coordinate bond", "central metal ion", "coordination number", "bidentate",
             "polydentate", "edta", "stability constant", "transesterification", "esterification",
             "condensation polymer", "addition polymer", "nucleophilic addition", "acylation",
             "friedel crafts"],
            "Reactivity 3: What are the mechanisms of change?",
            "R3.4 Electron pair sharing reactions (HL)",
        ),
    ]

    scored: List[tuple[int, str, str, List[str]]] = []
    for kws, topic, sub in rules:
        matched = [kw for kw in kws if keyword_in_text(t, kw)]
        if matched:
            score = len(matched) * 10 + sum(min(len(m), 20) for m in matched)
            scored.append((score, topic, sub, matched))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_topic, best_sub, matched = scored[0]
        confidence = 0.8 if len(matched) >= 2 else 0.6
        reasons = [f"keyword match: {len(matched)}", f"matched: {', '.join(matched[:4])}"]
        if len(scored) > 1:
            reasons.append(f"runner-up score: {scored[1][0]}")
        return (best_topic, best_sub, confidence, reasons)

    if str(paper_code).upper() in {"1", "1A"}:
        return ("Unsorted", "Multiple-choice mixed", 0.25, ["no confident MCQ keyword match"])

    paper_no = 0
    m = re.search(r"(\d)", str(paper_code))
    if m:
        paper_no = int(m.group(1))
    if paper_no == 3:
        return ("Reactivity 3: What are the mechanisms of change?", "R3.3 Electron sharing reactions", 0.2, ["paper 3 fallback"])
    if paper_no == 2:
        return ("Reactivity 2: How much, how fast and how far?", "R2.1 How much? Stoichiometry", 0.2, ["paper 2 fallback"])
    return ("Unsorted", "Unsorted", 0.1, ["no keyword match"])


def detect_starts(doc: fitz.Document, kind: str) -> List[StartPos]:
    starts: Dict[int, tuple[int, float, float, int]] = {}
    ms_data_start_page = 0
    if kind == "markscheme":
        for pno in range(len(doc)):
            t = (doc[pno].get_text("text") or "").lower()
            if (
                "section a" in t
                and "question" in t
                and "answers" in t
                and "total" in t
                and "subject details" not in t
                and "mark allocation" not in t
            ):
                ms_data_start_page = pno
                break
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
        # Skip IB source/disclaimer pages — numbered citations (e.g. "4.", "5.") on
        # these pages would otherwise be detected as false question starts.
        if "all other texts, graphics and illustrations" in page_text_lower:
            continue
        if "disclaimer:" in page_text_lower and "references:" in page_text_lower:
            continue
        if page_text_lower.lstrip().startswith("references:"):
            continue
        page_rot = page.rotation
        rot_mat = page.rotation_matrix  # transforms native PDF coords → visual coords
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

                # Biology/chemistry markscheme table: question numbers appear in the
                # leftmost "Question" column at x ≈ 48. Restrict to x <= 65 to avoid
                # false positives from answer content (e.g. "20 different amino acids"
                # at x=147) which previously created phantom questions that truncated
                # real questions' crops to zero height.
                ms_q_col = kind == "markscheme" and x <= 65

                if m_plain and (ms_q_col or (kind != "markscheme" and x <= 90)):
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

                if qn is not None and 1 <= qn <= 60:
                    eff_y = pending_y if pending_y is not None else y
                    eff_x = pending_x if pending_x is not None else x
                    left_bonus = 2 if eff_x <= 70 else (1 if eff_x <= 120 else 0)
                    cand_score = score + left_bonus

                    if eff_x <= 120 or kind == "markscheme":
                        prev_val = starts.get(qn)
                        replace = False
                        if prev_val is None:
                            replace = True
                        else:
                            prev_page, prev_y, prev_x, prev_score = prev_val
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

                prev = text

        if kind == "markscheme" and "all other texts, graphics and illustrations" not in page_text_lower:
            # Fallback: some biology/chemistry markschemes place the next question's
            # table-header row at the bottom of the current page (y >= 720). This row
            # is in the Question column (x ≈ 48, well within x <= 65). Use actual y0
            # so crop_question ends Q_prev at y-2 and starts Q_next at y-8 (tiny crop
            # on this page, skipped by the <80px guard, then continues on next page).
            for w in page.get_text("words"):
                x0, y0, _x1, _y1, txt, *_ = w
                txt_clean = str(txt).strip().rstrip(".")
                if not re.fullmatch(r"\d{1,2}", txt_clean):
                    continue
                qn = int(txt_clean)
                if not (1 <= qn <= 60):
                    continue
                if page_rot != 0:
                    pt = fitz.Point(float(x0), float(y0)) * rot_mat
                    x_vis, y_vis = pt.x, pt.y
                else:
                    x_vis, y_vis = float(x0), float(y0)
                if not (x_vis <= 65 and y_vis >= 720):
                    continue
                eff_x = x_vis
                eff_y = y_vis
                cand_score = 9
                prev_val = starts.get(qn)
                replace = False
                if prev_val is None:
                    replace = True
                else:
                    prev_page, prev_y, prev_x, prev_score = prev_val
                    if cand_score > prev_score:
                        replace = True
                    elif cand_score == prev_score:
                        if pno < prev_page or (pno == prev_page and eff_y < prev_y):
                            replace = True
                if replace:
                    starts[qn] = (pno, eff_y, eff_x, cand_score)
                break

    out = [StartPos(qnum=q, page=pg, y=y) for q, (pg, y, _x, _score) in starts.items()]
    out.sort(key=lambda s: (s.page, s.y))
    return out


def is_blank_answer_page(page: fitz.Page, clip: fitz.Rect) -> bool:
    text = page.get_text("text", clip=clip).lower()
    if "please do not write on this page" in text:
        return True
    if "answers written on this page" in text and "will not be marked" in text:
        return True
    # IB source/disclaimer pages: blank answer space with references appended at bottom
    if "all other texts, graphics and illustrations" in text:
        return True
    if "disclaimer:" in text and "references:" in text:
        return True
    if text.lstrip().startswith("references:"):
        return True
    alpha = re.sub(r"[^a-z]+", "", text)
    if len(alpha) < 16:
        return True
    # Strip IB exam codes (e.g. m16/4/chemi/hp2/eng/tz0/xx), page numbers, and
    # "turn over" — blank answer-space pages have virtually nothing left after this.
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
        out.append(out_file.relative_to(ROOT / "data" / "chemistry" / "processed").as_posix())

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


def parse_mcq_answers(ms_doc: Optional[fitz.Document]) -> Dict[int, str]:
    if ms_doc is None:
        return {}
    answers: Dict[int, str] = {}

    for pno in range(len(ms_doc)):
        page = ms_doc[pno]
        words = page.get_text("words") or []
        if not words:
            continue
        q_tokens = []
        a_tokens = []
        for w in words:
            x0, y0, _x1, _y1, txt, *_ = w
            t = str(txt).strip().replace("–", "-").replace("—", "-")
            m_q = re.fullmatch(r"(\d{1,2})\.", t)
            if m_q:
                qn = int(m_q.group(1))
                if 1 <= qn <= 60:
                    q_tokens.append((float(x0), float(y0), qn))
                continue
            if re.fullmatch(r"[A-D\-]", t):
                a_tokens.append((float(x0), float(y0), t))

        if len(q_tokens) < 10:
            continue

        row_buckets: Dict[float, List[tuple]] = {}
        tol = 3.0

        def bucket_for(y: float) -> float:
            for ky in row_buckets.keys():
                if abs(ky - y) <= tol:
                    return ky
            return y

        for x, y, qn in q_tokens:
            ky = bucket_for(y)
            row_buckets.setdefault(ky, []).append((x, "Q", qn))
        for x, y, ans in a_tokens:
            ky = bucket_for(y)
            row_buckets.setdefault(ky, []).append((x, "A", ans))

        for ky, row in row_buckets.items():
            row.sort(key=lambda t: t[0])
            q_cells = [(x, val) for x, kind, val in row if kind == "Q"]
            a_cells = [(x, val) for x, kind, val in row if kind == "A"]
            if not q_cells or not a_cells:
                continue
            for i, (qx, qn) in enumerate(q_cells):
                next_qx = q_cells[i + 1][0] if i + 1 < len(q_cells) else float("inf")
                candidates = [(ax, a) for ax, a in a_cells if qx < ax < next_qx]
                if not candidates:
                    candidates = [(ax, a) for ax, a in a_cells if ax > qx]
                if not candidates:
                    continue
                ans = sorted(candidates, key=lambda t: t[0])[0][1]
                if ans in {"A", "B", "C", "D"}:
                    answers[int(qn)] = ans

    text = "\n".join((ms_doc[p].get_text("text") or "") for p in range(len(ms_doc)))
    text = text.replace("–", "-").replace("—", "-")
    patt = re.compile(r"(?:(?<=\n)|(?<=\s))(\d{1,2})\.?\s*([A-D]|-)\b")
    for m in patt.finditer(text):
        qn = int(m.group(1))
        if not (1 <= qn <= 60) or qn in answers:
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
            print(f"  SKIP (missing): {paper_path.name}")
            continue

        paper_doc = fitz.open(paper_path)
        ms_doc = fitz.open(ms_path) if ms_path and ms_path.exists() else None

        q_starts = detect_starts(paper_doc, "paper")
        ms_starts = detect_starts(ms_doc, "markscheme") if ms_doc else []
        paper_code = str(p.get("paperCode", "")).upper()
        is_mcq_paper = paper_code in {"1", "1A"}
        mcq_answers = parse_mcq_answers(ms_doc) if is_mcq_paper else {}
        q_text = parse_question_text_blocks(paper_doc)
        ms_text = parse_question_text_blocks(ms_doc) if ms_doc else {}

        qnums = sorted({s.qnum for s in q_starts})

        session_prefix = "m" if str(p.get("session", "")).lower().startswith("may") else "n"
        session_code = f"{session_prefix}{str(p['year'])[-2:]}"

        for qn in qnums:
            base = f"chem_{session_code}_p{str(p['paperCode']).lower()}_{str(p['timezone']).lower()}_q{qn}_{str(p['level']).lower()}"
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
            ms_block = "" if is_mcq_paper else norm_ws(ms_text.get(qn, ""))
            ms_text_fallback = (
                "Markscheme available in source PDF (image mapping for this question is still being refined)."
                if (not is_mcq_paper and ms_doc is not None and not ms_block)
                else ""
            )

            block = q_text.get(qn, "")
            topic, subtopic, topic_confidence, topic_reason = infer_topic(block, str(p["paperCode"]))
            override = TOPIC_OVERRIDES.get(base)
            if override is not None:
                topic, subtopic, topic_confidence, topic_reason = override

            paper_type = "Paper 1A" if is_mcq_paper else f"Paper {p['paperCode']}"
            marks_value = 1 if is_mcq_paper else parse_marks_from_text(block)
            questions.append(
                {
                    "id": base,
                    "paper": p["paperLabel"],
                    "session": p["session"],
                    "session_code": session_code,
                    "paper_type": paper_type,
                    "level": p["level"],
                    "question_number": str(qn),
                    "title": f"Q{qn}: {block[:120]}" if block else f"Q{qn}",
                    "topic": topic,
                    "subtopic": subtopic,
                    "topic_confidence": topic_confidence,
                    "topic_reason": topic_reason,
                    "question_text": block,
                    "answer_text": (f"Answer: {mcq_answer}" if mcq_answer else (ms_block or ms_text_fallback)),
                    "mcq_answer": mcq_answer,
                    "marks": marks_value,
                    "has_markscheme": bool(ms_images or mcq_answer or ms_block or ms_text_fallback),
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
    print(f"Wrote {len(questions)} chemistry questions -> {OUT}")


if __name__ == "__main__":
    main()
