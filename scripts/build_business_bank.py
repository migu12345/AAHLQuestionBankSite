#!/usr/bin/env python3
"""Build Business Management question bank from raw papers and markschemes."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEPS = ROOT / ".deps"
if DEPS.exists():
    sys.path.insert(0, str(DEPS))

from pypdf import PdfReader  # type: ignore

PAPERS_DIR = ROOT / "data" / "business" / "raw" / "papers"
MARKSCHEMES_DIR = ROOT / "data" / "business" / "raw" / "markschemes"
OUT_FILE = ROOT / "data" / "business" / "processed" / "questions.json"
PROCESSED_IMAGES_DIR = ROOT / "data" / "business" / "processed" / "images"

FILE_PAPER_RE = re.compile(r"paper_(?P<paper>\d)", re.IGNORECASE)
PREFIX_RE = re.compile(r"^(?P<code>[mn]\d{2})_")
EXAM_RE = re.compile(r"\b(?P<code>[MN]\d{2})/3/BUSMT/(?:[HS]P)?(?P<paper>\d)/ENG(?:/TZ(?P<tz>\d))?/XX")
FILE_TZ_RE = re.compile(r"(?:__|_)TZ(?P<tz>\d)_(?:HL|SL)", re.IGNORECASE)


@dataclass
class PaperMeta:
    filename: str
    paper_no: int
    session: str
    session_code: str
    tz: Optional[int]
    level: str

    @property
    def paper_type(self) -> str:
        return f"Paper {self.paper_no}"

    @property
    def paper_label(self) -> str:
        if self.tz is None:
            return f"{self.session} {self.paper_type} {self.level}"
        return f"{self.session} {self.paper_type} TZ{self.tz} {self.level}"


def normalize_ws(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\ufeff", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_for_dedupe(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def clean_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw in text.splitlines():
        line = raw.replace("\xa0", " ").strip()
        if not line:
            lines.append("")
            continue
        if line in {"Turn over", "Section A", "Section B"}:
            continue
        if re.match(r"^\d+\s*pages$", line, re.IGNORECASE):
            continue
        if re.match(r"^\.+$", line):
            continue
        if re.search(r"international baccalaureate organization", line, re.IGNORECASE):
            continue
        lines.append(line)

    compact: List[str] = []
    for line in lines:
        if line == "" and compact and compact[-1] == "":
            continue
        compact.append(line)
    return compact


def extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def pair_key(filename: str) -> str:
    base = filename.lower()
    base = re.sub(r"_markscheme", "", base)
    base = re.sub(r"\.pdf$", "", base)
    return base


def infer_level_from_filename(filename: str) -> str:
    low = filename.lower()
    if "_sl" in low or "__sl" in low:
        return "SL"
    return "HL"


def session_label_from_code(code: str) -> str:
    year = f"20{code[1:]}"
    return f"May {year}" if code.startswith("M") else f"November {year}"


def detect_exam_info(path: Path) -> Tuple[str, str, Optional[int], Optional[int]]:
    reader = PdfReader(str(path))
    sample = "\n".join((reader.pages[i].extract_text() or "") for i in range(min(3, len(reader.pages))))
    m = EXAM_RE.search(sample)
    if not m:
        pm = PREFIX_RE.match(path.name)
        if pm:
            code = pm.group("code").lower()
            session = session_label_from_code(code.upper())
            return (code, session, None, None)
        return ("u00", "Unknown Session", None, None)

    code = m.group("code").lower()
    session = session_label_from_code(m.group("code"))
    tz_str = m.group("tz")
    paper_str = m.group("paper")
    tz = int(tz_str) if tz_str else None
    if tz == 0:
        tz = None
    return (code, session, tz, int(paper_str) if paper_str else None)


def parse_meta(path: Path) -> PaperMeta:
    name = path.name
    m = FILE_PAPER_RE.search(name)
    if not m:
        raise ValueError(f"Could not parse paper number from {name}")
    paper_no = int(m.group("paper"))

    code, session, tz, paper_from_code = detect_exam_info(path)
    if paper_from_code is not None:
        paper_no = paper_from_code
    if tz is None:
        mtz = FILE_TZ_RE.search(name)
        if mtz:
            tz = int(mtz.group("tz"))

    return PaperMeta(
        filename=name,
        paper_no=paper_no,
        session=session,
        session_code=code,
        tz=tz,
        level=infer_level_from_filename(name),
    )


def parse_questions_from_paper(path: Path) -> Dict[int, Dict[str, object]]:
    text = extract_pdf_text(path)
    lines = clean_lines(text)
    content = "\n".join(lines)
    # Business papers are structured by question headings (e.g. "1. (a)...")
    # and per-part marks [2 marks], not [Maximum mark: x].
    q_re = re.compile(
        r"(?ms)^\s*(?P<num>\d{1,2})\.\s+(?P<body>.*?)(?=^\s*\d{1,2}\.\s+|\Z)"
    )

    out: Dict[int, Dict[str, object]] = {}
    for m in q_re.finditer(content):
        qn = int(m.group("num"))
        if qn < 1 or qn > 40:
            continue
        body = normalize_ws(m.group("body"))
        if len(body) < 20:
            continue

        part_marks = [int(x) for x in re.findall(r"\[(\d+)\s*marks?\]", body, flags=re.IGNORECASE)]
        marks = sum(part_marks) if part_marks else 0

        out[qn] = {
            "marks": marks,
            "question_text": body,
        }
    return out


def parse_answers_from_markscheme(path: Path) -> Dict[int, str]:
    text = extract_pdf_text(path)
    lines = clean_lines(text)

    q_starts = [
        re.compile(r"^(?P<num>\d+)\.(?:\s|$)"),
        re.compile(r"^Question\s+(?P<num>\d+)\b", re.IGNORECASE),
        re.compile(r"^(?P<num>\d+)\s+\("),
    ]

    answers: Dict[int, List[str]] = {}
    current: int | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if current is not None:
                answers.setdefault(current, []).append("")
            continue

        new_q: int | None = None
        for patt in q_starts:
            m = patt.match(line)
            if m:
                new_q = int(m.group("num"))
                break

        if new_q is not None and (current is None or new_q != current):
            current = new_q

        if current is None:
            continue

        line = re.sub(r"^Question\s+\d+\s+continued\s*$", "", line, flags=re.IGNORECASE).strip()
        if not line:
            continue
        answers.setdefault(current, []).append(line)

    result: Dict[int, str] = {}
    for qn, block in answers.items():
        text_block = "\n".join(block)
        text_block = re.sub(r"\n{3,}", "\n\n", text_block)
        result[qn] = normalize_ws(text_block)
    return result


def classify_topic(question_text: str, answer_text: str) -> Tuple[str, str, float, List[str]]:
    q = re.sub(r"\s+", " ", question_text.lower())
    a = re.sub(r"\s+", " ", answer_text.lower())
    merged = f"{q} {a}"

    rules: List[Tuple[re.Pattern[str], Tuple[str, str], int]] = [
        (re.compile(r"\b(stakeholder|sole trader|partnership|private limited|public limited|multinational|mission statement|vision)\b"), ("Introduction to business management", "Business structures and stakeholders"), 18),
        (re.compile(r"\b(csr|ethic|globalization|external environment|pest|political|economic|social|technological)\b"), ("Introduction to business management", "External environment and ethics"), 16),
        (re.compile(r"\b(growth|merger|acquisition|change management|resistance to change|swot|strategy|strategic|ansoff|boston matrix|competitive advantage|contingency|risk|uncertainty|sensitivity)\b"), ("Introduction to business management", "Growth and strategy"), 15),
        (re.compile(r"\b(organization chart|span of control|delegation|centralization|decentralization|culture)\b"), ("Human Resource Management", "Organizational structure and culture"), 18),
        (re.compile(r"\b(motivation|maslow|herzberg|leadership|autocratic|democratic|laissez)\b"), ("Human Resource Management", "Motivation and leadership"), 18),
        (re.compile(r"\b(trade union|industrial action|collective bargaining|employment contract|redundancy|training)\b"), ("Human Resource Management", "Industrial relations"), 16),
        (re.compile(r"\b(source of finance|share capital|loan|overdraft|retained profit|venture capital)\b"), ("Finance and Accounts", "Sources of finance"), 18),
        (re.compile(r"\b(payback|arr|npv|investment appraisal|decision tree|expected value)\b"), ("Finance and Accounts", "Investment appraisal"), 20),
        (re.compile(r"\b(profit and loss|balance sheet|gross profit|net profit|liquidity|ratio)\b"), ("Finance and Accounts", "Final accounts and ratio analysis"), 20),
        (re.compile(r"\b(budget|variance|forecast|break even|contribution)\b"), ("Finance and Accounts", "Budgets and forecasts"), 16),
        (re.compile(r"\b(market research|primary research|secondary research|sample|demand|income elasticity|price elasticity)\b"), ("Marketing", "Market research and demand"), 20),
        (re.compile(r"\b(product|price|promotion|place|4p|branding|positioning)\b"), ("Marketing", "Marketing mix"), 18),
        (re.compile(r"\b(international marketing|global market|export|franchise|adaptation|standardization)\b"), ("Marketing", "International marketing"), 16),
        (re.compile(r"\b(lean production|quality|quality assurance|quality control|tqm|japanese)\b"), ("Operations Management", "Production methods and quality"), 18),
        (re.compile(r"\b(location|relocation|capacity|utilization|economies of scale)\b"), ("Operations Management", "Location and capacity"), 16),
        (re.compile(r"\b(stock|inventory|buffer stock|just in time|supply chain|outsourcing)\b"), ("Operations Management", "Supply chain and inventory"), 18),
    ]

    scores: Dict[Tuple[str, str], int] = {}
    reasons: List[str] = []
    for patt, label, weight in rules:
        hits = len(patt.findall(merged))
        if hits:
            delta = hits * weight
            scores[label] = scores.get(label, 0) + delta
            reasons.append(f"{label[0]}:{label[1]}+{delta}")

    if not scores:
        return ("Introduction to business management", "Growth and strategy", 0.3, ["fallback:default"])

    best, best_score = max(scores.items(), key=lambda x: x[1])
    second = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
    confidence = min(0.98, max(0.45, (best_score - second) / max(1, best_score)))
    return (best[0], best[1], round(confidence, 3), reasons[:5])


def make_title(qnum: int, question_text: str) -> str:
    flat = re.sub(r"\s+", " ", question_text).strip()
    if not flat:
        return f"Q{qnum}"
    short = flat[:90]
    if len(flat) > 90:
        short += "..."
    return f"Q{qnum}: {short}"


def tz_sort_value(paper_label: str) -> int:
    m = re.search(r"TZ(\d)", paper_label)
    if not m:
        return 999
    return int(m.group(1))


def id_without_tz(rec_id: str) -> str:
    return re.sub(r"_tz\d+(?=_q\d+(?:_[a-z]+)?$)", "", rec_id)


def parse_id_parts(rec_id: str) -> Optional[Tuple[str, str, str]]:
    m = re.match(r"^(?P<session>[a-z0-9]+)_p(?P<paper>\d+)(?:_tz\d+)?_q(?P<q>\d+)(?:_[a-z]+)?$", rec_id)
    if not m:
        return None
    return (m.group("session"), m.group("paper"), m.group("q"))


def normalized_similarity_text(text: str) -> str:
    t = text.lower().replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def remove_sl_priority_duplicates(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    sl_records = [r for r in records if str(r.get("level", "")) == "SL"]
    sl_by_paper: Dict[str, List[Dict[str, object]]] = {}
    for r in sl_records:
        sl_by_paper.setdefault(str(r.get("paper_type", "")), []).append(r)

    out: List[Dict[str, object]] = []
    for rec in records:
        if str(rec.get("level", "")) != "HL":
            out.append(rec)
            continue

        hl_q = normalized_similarity_text(str(rec.get("question_text", "")))
        hl_m = int(rec.get("marks", 0) or 0)
        paper_type = str(rec.get("paper_type", ""))
        candidates = sl_by_paper.get(paper_type, sl_records)

        duplicate = False
        for sl in candidates:
            sl_m = int(sl.get("marks", 0) or 0)
            if abs(sl_m - hl_m) > 1:
                continue
            sl_q = normalized_similarity_text(str(sl.get("question_text", "")))
            if text_similarity(sl_q, hl_q) >= 0.94:
                duplicate = True
                break

        if not duplicate:
            out.append(rec)
    return out


def build_image_index(kind: str) -> Dict[str, List[str]]:
    folder = PROCESSED_IMAGES_DIR / kind
    index: Dict[str, List[Tuple[int, str]]] = {}
    if not folder.exists():
        return {}

    for img in folder.glob("*.png"):
        stem = img.stem
        m = re.match(r"^(?P<id>.+)_p(?P<page>\d+)$", stem)
        if m:
            rec_id = m.group("id")
            page = int(m.group("page"))
        else:
            rec_id = stem
            page = 1
        rel = str(Path("images") / kind / img.name)
        index.setdefault(rec_id, []).append((page, rel))

    out: Dict[str, List[str]] = {}
    for rec_id, items in index.items():
        items.sort(key=lambda pair: pair[0])
        out[rec_id] = [rel for _, rel in items]
    return out


def extract_tz_from_filename(filename: str) -> Optional[int]:
    m = re.search(r"(?:__|_)TZ(?P<tz>\d)", filename, re.IGNORECASE)
    if not m:
        return None
    return int(m.group("tz"))


def is_case_study_candidate(filename: str) -> bool:
    low = filename.lower()
    return (
        "paper_1" in low
        and "markscheme" not in low
        and ("case_study" in low or "pre-released_statement" in low)
    )


def case_study_score(filename: str) -> int:
    low = filename.lower()
    if "pre-released_statement" in low:
        return 6
    if "case_study" in low:
        return 5
    return 1


def build_case_study_index(papers: List[Path]) -> Dict[Tuple[str, Optional[int]], str]:
    best: Dict[Tuple[str, Optional[int]], Tuple[int, str]] = {}
    for paper_path in papers:
        name = paper_path.name
        if not is_case_study_candidate(name):
            continue
        pm = PREFIX_RE.match(name)
        if not pm:
            continue
        session_code = pm.group("code").lower()
        tz = extract_tz_from_filename(name)
        score = case_study_score(name)

        key_exact = (session_code, tz)
        prev_exact = best.get(key_exact)
        if prev_exact is None or score > prev_exact[0]:
            best[key_exact] = (score, name)

        key_fallback = (session_code, None)
        prev_fallback = best.get(key_fallback)
        if prev_fallback is None or score > prev_fallback[0]:
            best[key_fallback] = (score, name)

    return {key: val[1] for key, val in best.items()}


def resolve_case_study_file(
    session_code: str, tz: Optional[int], case_index: Dict[Tuple[str, Optional[int]], str]
) -> Optional[str]:
    return case_index.get((session_code, tz)) or case_index.get((session_code, None))


def resolve_image_paths(rec_id: str, index: Dict[str, List[str]]) -> List[str]:
    if rec_id in index:
        return index[rec_id]

    no_tz = id_without_tz(rec_id)
    if no_tz in index:
        return index[no_tz]

    parts = parse_id_parts(rec_id)
    if parts is None:
        return []

    session, paper, qnum = parts
    fallback_re = re.compile(rf"^{re.escape(session)}_p{re.escape(paper)}(?:_tz\d+)?_q{re.escape(qnum)}(?:_[a-z]+)?$")
    candidates = [key for key in index.keys() if fallback_re.match(key)]
    if not candidates:
        return []

    candidates.sort()
    return index[candidates[0]]


def build() -> Dict[str, object]:
    papers = sorted(PAPERS_DIR.glob("*.pdf"))
    markschemes = sorted(MARKSCHEMES_DIR.glob("*.pdf"))

    ms_map = {pair_key(p.name): p for p in markschemes}
    case_index = build_case_study_index(papers)
    records: List[Dict[str, object]] = []

    for paper_path in papers:
        key = pair_key(paper_path.name)
        ms_path = ms_map.get(key)
        if not ms_path:
            continue

        meta = parse_meta(paper_path)
        q_map = parse_questions_from_paper(paper_path)
        a_map = parse_answers_from_markscheme(ms_path)

        for qn in sorted(q_map.keys()):
            q = q_map[qn]
            ans = a_map.get(qn, "Markscheme content not extracted for this question.")
            topic, subtopic, confidence, reasons = classify_topic(str(q["question_text"]), ans)

            tz_part = f"_tz{meta.tz}" if meta.tz is not None else ""
            rec_id = f"{meta.session_code}_p{meta.paper_no}{tz_part}_q{qn}_{meta.level.lower()}"

            records.append(
                {
                    "id": rec_id,
                    "paper": meta.paper_label,
                    "session": meta.session,
                    "session_code": meta.session_code,
                    "paper_type": meta.paper_type,
                    "level": meta.level,
                    "question_number": str(qn),
                    "title": make_title(qn, str(q["question_text"])),
                    "topic": topic,
                    "subtopic": subtopic,
                    "topic_confidence": confidence,
                    "topic_reason": reasons,
                    "question_text": q["question_text"],
                    "answer_text": ans,
                    "marks": q["marks"],
                    "source": {
                        "paper_file": paper_path.name,
                        "markscheme_file": ms_path.name,
                    },
                    "case_study_file": (
                        resolve_case_study_file(meta.session_code, meta.tz, case_index)
                        if meta.paper_no == 2
                        else None
                    ),
                }
            )

    records.sort(
        key=lambda r: (
            r.get("session_code", ""),
            int(str(r.get("paper_type", "Paper 0")).split()[-1]),
            tz_sort_value(str(r.get("paper", ""))),
            int(r["question_number"]),
            str(r.get("level", "")),
        )
    )

    deduped: List[Dict[str, object]] = []
    seen: set[Tuple[str, str]] = set()
    for rec in records:
        sig = (
            normalize_for_dedupe(str(rec.get("question_text", ""))),
            normalize_for_dedupe(str(rec.get("answer_text", ""))),
        )
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(rec)

    deduped = remove_sl_priority_duplicates(deduped)

    q_image_index = build_image_index("questions")
    ms_image_index = build_image_index("markschemes")
    for rec in deduped:
        rec_id = str(rec.get("id", ""))
        rec["question_image_paths"] = resolve_image_paths(rec_id, q_image_index)
        rec["markscheme_image_paths"] = resolve_image_paths(rec_id, ms_image_index)

    sessions = sorted({str(q.get("session", "")) for q in deduped if q.get("session")})

    return {
        "course": "IB Business Management",
        "sessions": sessions,
        "questions": deduped,
    }


def main() -> None:
    payload = build()
    OUT_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['questions'])} questions to {OUT_FILE}")


if __name__ == "__main__":
    main()
