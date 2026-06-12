#!/usr/bin/env python3
"""Build the Economics question bank from IB past paper PDFs."""
import sys
import re
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / '.deps'))
import fitz  # PyMuPDF

ROOT = Path(__file__).parent.parent
PDF_BASE = Path('/Users/s933863@aics.espritscholen.nl/Desktop/Downloads/IB PAST PAPERS - YEAR')
OUT_DIR = ROOT / 'data/economics/processed'
IMG_DIR = OUT_DIR / 'images'
IMG_DIR.mkdir(parents=True, exist_ok=True)

PAPER_TYPES = {1: 'Essay', 2: 'Data Response', 3: 'Quantitative'}
PAPER_MARKS = {1: 25, 2: None, 3: 25}

SKIP_LANGS = ['French', 'Spanish', 'German', 'Portuguese', 'Chinese']

# Topics that appear as section headers (longer/more specific phrases first)
TOPIC_KEYWORDS = {
    'international economics': 'International Economics',
    'development economics': 'Development Economics',
    'international trade': 'International Economics',
    'global economy': 'International Economics',
    'microeconomics': 'Microeconomics',
    'macroeconomics': 'Macroeconomics',
}

# Keywords to infer topic from question text when section header is absent (older papers)
MICRO_KEYWORDS = [
    'elasticity', 'demand curve', 'supply curve', 'monopoly', 'oligopoly',
    'perfectly competitive', 'price discrimination', 'market failure',
    'externality', 'public good', 'factor of production', 'diminishing returns',
    'cost curve', 'revenue', 'profit maximiz', 'allocative efficiency',
    'productive efficiency', 'merit good', 'demerit', 'subsidy', 'indirect tax',
    'consumer surplus', 'producer surplus', 'deadweight loss', 'price ceiling',
    'price floor', 'minimum wage',
]
MACRO_KEYWORDS = [
    'gdp', 'aggregate demand', 'aggregate supply', 'inflation', 'unemployment',
    'fiscal policy', 'monetary policy', 'interest rate', 'money supply',
    'economic growth', 'business cycle', 'keynesian', 'monetarist',
    'multiplier', 'government spending', 'taxation', 'budget deficit',
    'trade cycle', 'deflationary gap', 'inflationary gap', 'national income',
    'circular flow', 'gni', 'gnp', 'current account',
]
INTL_KEYWORDS = [
    'exchange rate', 'balance of payments', 'tariff', 'quota', 'free trade',
    'trade protection', 'comparative advantage', 'terms of trade',
    'current account deficit', 'trade deficit', 'dumping', 'wto',
]
DEV_KEYWORDS = [
    'economic development', 'developing countr', 'hdi', 'human development',
    'poverty', 'inequality', 'foreign aid', 'microfinance', 'debt relief',
    'fair trade', 'sustainable development',
]


def infer_topic_from_text(text: str) -> str | None:
    lower = text.lower()
    intl = sum(1 for k in INTL_KEYWORDS if k in lower)
    dev = sum(1 for k in DEV_KEYWORDS if k in lower)
    macro = sum(1 for k in MACRO_KEYWORDS if k in lower)
    micro = sum(1 for k in MICRO_KEYWORDS if k in lower)
    counts = [('International Economics', intl), ('Development Economics', dev),
              ('Macroeconomics', macro), ('Microeconomics', micro)]
    best = max(counts, key=lambda x: x[1])
    return best[0] if best[1] >= 1 else None


def parse_pdf_metadata(path: Path) -> dict | None:
    name = path.stem
    if any(lang in name for lang in SKIP_LANGS):
        return None

    is_markscheme = name.endswith('_markscheme')
    clean = name.replace('__', '_')
    if is_markscheme:
        clean = clean[:-len('_markscheme')]

    m = re.match(r'Economics_paper_(\d)(?:_(TZ\d))?(?:_(SL|HL))?$', clean, re.IGNORECASE)
    if not m:
        return None

    paper_num = int(m.group(1))
    tz = m.group(2)         # None if absent
    level = (m.group(3) or '').upper() or None
    if not level:
        return None

    year = None
    session = None
    for part in path.parts:
        yr = re.match(r'^(\d{4}) Examination Session$', part)
        if yr:
            year = int(yr.group(1))
        sess = re.match(r'^(May|November) \d{4} Examination Session$', part)
        if sess:
            session = sess.group(1)

    if year is None or session is None:
        return None

    return {
        'year': year,
        'session': session,
        'tz': tz,
        'level': level,
        'paper_num': paper_num,
        'is_markscheme': is_markscheme,
        'path': path,
    }


def find_all_pdfs() -> list:
    results = []
    seen_keys = set()
    for pdf in PDF_BASE.rglob('Economics_paper_*.pdf'):
        # Skip duplicate copies in HTML subfolders
        if 'HTML' in pdf.parts or 'files and resources' in pdf.parts:
            continue
        meta = parse_pdf_metadata(pdf)
        if meta:
            # Deduplicate by canonical identity
            key = (meta['year'], meta['session'], meta['paper_num'], meta['level'], meta['tz'], meta['is_markscheme'])
            if key not in seen_keys:
                seen_keys.add(key)
                results.append(meta)
    return sorted(results, key=lambda x: (x['year'], x['session'], x['paper_num'], x['level'], x['tz'] or ''))


def find_markscheme(meta: dict, all_pdfs: list) -> dict | None:
    for m in all_pdfs:
        if (m['is_markscheme']
                and m['year'] == meta['year']
                and m['session'] == meta['session']
                and m['paper_num'] == meta['paper_num']
                and m['level'] == meta['level']
                and m['tz'] == meta['tz']):
            return m
    return None


def detect_q_starts(page_text: str) -> list[int]:
    """Return question numbers that begin on this page."""
    # Match: N. at start of line followed by tab, 2+ spaces, or end-of-line
    qnums = set()
    for m in re.finditer(r'^[ \t]*([1-9]|1[0-5])\.(?:[ \t]*$|\t|\s{2,})', page_text, re.MULTILINE):
        qnums.add(int(m.group(1)))
    if not qnums:
        # Markscheme format: N.\n(a) — newline after period
        for m in re.finditer(r'^[ \t]*([1-9]|1[0-5])\.\s*\n', page_text, re.MULTILINE):
            qnums.add(int(m.group(1)))
    return sorted(qnums)


def detect_continuation(page_text: str) -> int | None:
    m = re.search(r'\(Question (\d+) continued\)', page_text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_section_topic(page_text: str) -> str | None:
    lower = page_text.lower()
    for keyword, topic in TOPIC_KEYWORDS.items():
        if keyword in lower:
            return topic
    return None


def extract_p1_question_text(page_text: str, qnum: int) -> str:
    """Extract question block for qnum from Paper 1 page text."""
    # Match: "N." followed by the block up to the next question or end
    pattern = rf'(?:^|\n)[ \t]*{qnum}\.[ \t\n]+(.+?)(?=\n[ \t]*(?:[1-9]|1[0-5])\.[ \t\n]|\Z)'
    m = re.search(pattern, page_text, re.DOTALL)
    if m:
        raw = m.group(1)
        # Clean up control chars and extra whitespace
        raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)
        raw = re.sub(r'\t', ' ', raw)
        raw = re.sub(r' {2,}', ' ', raw)
        return raw.strip()[:3000]
    return ''


def extract_ms_text_for_q(page_text: str, qnum: int) -> str:
    """Extract markscheme text block for qnum."""
    pattern = rf'(?:^|\n)[ \t]*{qnum}\.[ \t\n]+(.+?)(?=\n[ \t]*(?:[1-9]|1[0-5])\.[ \t\n]|\Z)'
    m = re.search(pattern, page_text, re.DOTALL)
    if m:
        raw = m.group(1)
        raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', ' ', raw)
        raw = re.sub(r'\t', ' ', raw)
        raw = re.sub(r' {2,}', ' ', raw)
        return raw.strip()[:5000]
    return ''


def render_page(page: fitz.Page, out_path: Path, scale: float = 1.5) -> None:
    if out_path.exists():
        return
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    pix.save(str(out_path))


def stem_for(meta: dict) -> str:
    sess = 'may' if meta['session'] == 'May' else 'nov'
    tz = (meta['tz'] or 'notz').lower()
    return f"{meta['year']}_{sess}_{tz}_{meta['level'].lower()}_p{meta['paper_num']}"


def paper_label(meta: dict) -> str:
    tz = f" {meta['tz']}" if meta['tz'] else ''
    return f"{meta['year']} {meta['session']}{tz} {meta['level']} Paper {meta['paper_num']}"


def img_rel(img_path: Path) -> str:
    return str(img_path.relative_to(OUT_DIR))


# ── Paper 1 (Essay) ──────────────────────────────────────────────────────────

def process_p1(meta: dict, ms_meta: dict | None) -> list[dict]:
    doc = fitz.open(str(meta['path']))
    stem = stem_for(meta)

    # Collect all content pages (skip page 0 = copyright/cover only;
    # page 1 = instructions in newer format but content in older 2-page format)
    q_data = {}   # qnum -> {text, topic, ms_text}
    current_topic = None

    for pno in range(1, len(doc)):
        page = doc[pno]
        text = page.get_text('text')

        topic = extract_section_topic(text)
        if topic:
            current_topic = topic

        for qnum in detect_q_starts(text):
            if qnum not in q_data:
                q_data[qnum] = {'text': '', 'topic': current_topic, 'ms_text': ''}
            if not q_data[qnum]['text']:
                q_data[qnum]['text'] = extract_p1_question_text(text, qnum)

    # Process markscheme pages for text
    if ms_meta:
        ms_doc = fitz.open(str(ms_meta['path']))
        current_ms_qnum = None
        accumulated_text = {}

        for pno in range(len(ms_doc)):
            page = ms_doc[pno]
            text = page.get_text('text')
            new_qnums = detect_q_starts(text)
            if new_qnums:
                current_ms_qnum = new_qnums[0]
            if current_ms_qnum:
                accumulated_text.setdefault(current_ms_qnum, []).append(text)

        for qnum, pages_text in accumulated_text.items():
            combined = '\n'.join(pages_text)
            if qnum in q_data:
                q_data[qnum]['ms_text'] = extract_ms_text_for_q(combined, qnum)
            else:
                # MS has question not in question paper (edge case)
                q_data[qnum] = {'text': '', 'topic': None, 'ms_text': extract_ms_text_for_q(combined, qnum)}

        ms_doc.close()

    doc.close()

    questions = []
    for qnum in sorted(q_data):
        info = q_data[qnum]
        # Fall back to keyword inference from question text if section header gave no topic
        topic = info['topic'] or infer_topic_from_text(info['text'])
        qid = f"econ_{stem}_q{qnum}"
        questions.append({
            'id': qid,
            'year': meta['year'],
            'session': meta['session'],
            'timezone': meta['tz'],
            'level': meta['level'],
            'paper': paper_label(meta),
            'paper_number': 1,
            'paper_type': 'Essay',
            'question_number': qnum,
            'question_text': info['text'],
            'answer_text': info['ms_text'],
            'marks': 25,
            'topic': topic,
            'subtopic': None,
            'question_image_paths': [],
            'markscheme_image_paths': [],
            'source': {
                'paper_file': meta['path'].name,
                'markscheme_file': ms_meta['path'].name if ms_meta else None,
            },
        })

    return questions


# ── Paper 2 & 3 (Data Response / Quantitative) ───────────────────────────────

def process_p2_p3(meta: dict, ms_meta: dict | None) -> list[dict]:
    doc = fitz.open(str(meta['path']))
    stem = stem_for(meta)
    ptype = PAPER_TYPES[meta['paper_num']]

    q_pages = {}   # qnum -> [pno]
    q_texts = {}   # qnum -> str (first-page text)
    q_topics = {}  # qnum -> str
    current_qnum = None
    current_topic = None

    for pno in range(len(doc)):
        page = doc[pno]
        text = page.get_text('text')

        topic = extract_section_topic(text)
        if topic:
            current_topic = topic

        cont_qnum = detect_continuation(text)
        new_qnums = detect_q_starts(text)

        if cont_qnum:
            # Explicit continuation marker — page belongs to that question
            current_qnum = cont_qnum
            q_pages.setdefault(current_qnum, []).append(pno)
        elif new_qnums:
            # All questions that start on this page (old format: many per page;
            # new format: one per page) each get this page assigned.
            for qnum in new_qnums:
                if qnum not in q_topics:
                    q_topics[qnum] = current_topic
                if qnum not in q_texts:
                    q_texts[qnum] = text.strip()[:1500]
                q_pages.setdefault(qnum, []).append(pno)
            current_qnum = new_qnums[-1]
        elif current_qnum is not None:
            # Plain page with no markers — continuation of current question
            q_pages.setdefault(current_qnum, []).append(pno)

    # Markscheme page mapping
    ms_page_map = {}
    ms_doc = None
    if ms_meta:
        ms_doc = fitz.open(str(ms_meta['path']))
        current_ms_qnum = None
        for pno in range(len(ms_doc)):
            page = ms_doc[pno]
            text = page.get_text('text')
            cont_qnum = detect_continuation(text)
            new_qnums = detect_q_starts(text)
            if cont_qnum:
                current_ms_qnum = cont_qnum
            elif new_qnums:
                current_ms_qnum = new_qnums[0]
            # Skip first page (title page of MS)
            if current_ms_qnum and pno >= 1:
                ms_page_map.setdefault(current_ms_qnum, []).append(pno)

    questions = []
    for qnum in sorted(q_pages):
        q_imgs = []
        ms_imgs = []

        for idx, pno in enumerate(q_pages[qnum]):
            img_name = f"{stem}_q{qnum}_qp{idx+1}.png"
            img_path = IMG_DIR / img_name
            render_page(doc[pno], img_path)
            q_imgs.append(img_rel(img_path))

        if ms_doc and qnum in ms_page_map:
            for idx, pno in enumerate(ms_page_map[qnum]):
                img_name = f"{stem}_q{qnum}_ms{idx+1}.png"
                img_path = IMG_DIR / img_name
                render_page(ms_doc[pno], img_path)
                ms_imgs.append(img_rel(img_path))

        qid = f"econ_{stem}_q{qnum}"
        questions.append({
            'id': qid,
            'year': meta['year'],
            'session': meta['session'],
            'timezone': meta['tz'],
            'level': meta['level'],
            'paper': paper_label(meta),
            'paper_number': meta['paper_num'],
            'paper_type': ptype,
            'question_number': qnum,
            'question_text': q_texts.get(qnum, ''),
            'answer_text': '',
            'marks': PAPER_MARKS[meta['paper_num']],
            'topic': q_topics.get(qnum),
            'subtopic': None,
            'question_image_paths': q_imgs,
            'markscheme_image_paths': ms_imgs,
            'source': {
                'paper_file': meta['path'].name,
                'markscheme_file': ms_meta['path'].name if ms_meta else None,
            },
        })

    doc.close()
    if ms_doc:
        ms_doc.close()

    return questions


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    all_pdfs = find_all_pdfs()
    question_papers = [m for m in all_pdfs if not m['is_markscheme']]
    print(f"Found {len(all_pdfs)} PDFs ({len(question_papers)} question papers)")

    all_questions = []
    seen_ids = set()

    for i, meta in enumerate(question_papers):
        print(f"[{i+1}/{len(question_papers)}] {meta['path'].name}")
        ms_meta = find_markscheme(meta, all_pdfs)
        if not ms_meta:
            print(f"  (no markscheme found)")

        try:
            if meta['paper_num'] == 1:
                qs = process_p1(meta, ms_meta)
            else:
                qs = process_p2_p3(meta, ms_meta)
        except Exception as e:
            import traceback
            print(f"  ERROR: {e}")
            traceback.print_exc()
            continue

        added = 0
        for q in qs:
            if q['id'] not in seen_ids:
                seen_ids.add(q['id'])
                all_questions.append(q)
                added += 1
            else:
                print(f"  DUPE: {q['id']}")
        print(f"  → {added} questions (total {len(all_questions)})")

    out_path = OUT_DIR / 'questions.json'
    with open(out_path, 'w') as f:
        json.dump({'questions': all_questions}, f, indent=2)

    print(f"\nWrote {len(all_questions)} questions to {out_path}")
    print(f"Images in {IMG_DIR}")


if __name__ == '__main__':
    main()
