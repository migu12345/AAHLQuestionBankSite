# Context Window Export (for new chat)

Date: 2026-05-16
Project: `AA-HL-Question-Bank`
Latest pushed commit: `487d2fed` (main)

## Current State
- Biology bank: LIVE with 3299 questions from 182 papers (2016–2025).
- Chemistry bank: LIVE with questions from 188 papers (2016–2025).
- Physics bank: stable, existing.
- Tutoring bank: **145 questions** — Topic 1 Number & Algebra (109 q) + Topic 2 Functions (36 q).
- User preference: **surgical fixes only**.
- User preference: auto **commit + push** after work.
- User preference: keep `CONTEXT_WINDOW_EXPORT.md` updated.
- User preference: when `All levels` is selected, prioritize `SL` and suppress `HL` duplicates.
- User constraint: do not change Paper 1A / Paper 2 / Paper 3 logic when fixing unrelated issues.

## Most Recent Completed Work (this session)

### Tutoring Bank — Topic 2 Functions
- Processed `Math_SL_Functions_Equations_2023.pdf` (20 pages, 36 questions).
- Generated 55 PNG question image crops (multi-page questions split across `_p1`, `_p2`, etc.).
- Generated draft SVG markscheme images for all 36 questions.
- Subtopics inferred: Composite/inverse functions (4), Quadratic functions (9), Transformations (5), Exponential/logarithmic (5), Trigonometric (4), Domain/range (1), General (8).
- **New script**: `scripts/tutoring/build_topic2.py` — self-contained script (parse + crop + markscheme + SVG render + JSON update).
- **UI update**: Added `Unit` filter dropdown to tutoring page (filter Topic 1 vs Topic 2).
- **UI update**: Updated search placeholder and meta display to show unit.
- Data files updated: `data/tutoring/processed/questions.json` (145 total), `data/tutoring/processed/markschemes.json` (145 total).

## Key Architecture

### Build Pipeline
1. `scripts/setup_bio_chem_papers.py` → copies PDFs + writes `manual_papers.json`
2. `python3 scripts/build_biology_bank.py` → reads `manual_papers.json`, crops PNGs, writes `questions.json`
3. `python3 scripts/build_chemistry_bank.py` → same for chemistry
4. `python3 scripts/tutoring/build_topic1.py` → parse Topic 1 PDFs → questions.json
5. `python3 scripts/tutoring/generate_images.py` → crop question PNGs for Topic 1
6. `python3 scripts/tutoring/generate_markschemes.py` → draft markschemes → markschemes.json
7. `python3 scripts/tutoring/generate_markscheme_images.py` → SVG markscheme images
8. `python3 scripts/tutoring/build_topic2.py` → all-in-one for Topic 2 (parse + crop + markscheme + SVG)

### Tutoring Source PDFs
- Topic 1: `/Users/s933863@aics.espritscholen.nl/Documents/Tutoring Questions/Topic 1 Number and Algebra/`
  - `Binomila Theorem.pdf`, `Math_SL_Algebra.pdf`, `Math_SL_Algebra_Exp_Log.pdf`,
    `Topic_1_2_Algebra_Exponents_Logarithms_2023.pdf`,
    `Topic_1_4_Algebra_Mathematical_Induction.pdf`, `Topic_1_5_Algebra_Complex_Numbers.pdf`
- Topic 2: `/Users/s933863@aics.espritscholen.nl/Documents/Tutoring Questions/Topic 2 Functions/`
  - `Math_SL_Functions_Equations_2023.pdf`

### manual_papers.json Entry Format
```json
{
  "paperLabel": "May 2022 Biology Paper 2 TZ1 HL",
  "session": "May",
  "year": 2022,
  "paperCode": "2",
  "timezone": "TZ1",
  "level": "HL",
  "paper_path": "resources/biology/m22/Biology_paper_2_TZ1_HL.pdf",
  "markscheme_path": "resources/biology/m22/Biology_paper_2_TZ1_HL_markscheme.pdf"
}
```

### Image Naming
- `bio_{session}_{paper}_{tz}_{level}_q{n}.png`
- `chem_{session}_{paper}_{tz}_{level}_q{n}.png`
- `t1_{stem}_q{n}.png` (tutoring Topic 1)
- `t2_{stem}_q{n}.png` or `t2_{stem}_q{n}_p{page}.png` (tutoring Topic 2)

## Key Decisions Already Made
- Old Physics MCQ `Paper 1` → treated as `Paper 1A` equivalent.
- Paper 1A/1 questions are 1 mark each.
- Side-by-side markscheme overlay is required UX pattern.
- Biology/Chemistry images served relative to `data/{subject}/processed/`.
- Biology/Chemistry deduplication: SL preferred over HL when `All levels` selected (via `dedupeForAllLevels()`).
- Tutoring images served same-origin (copied into Docker container via `COPY data/tutoring`).

## Important Files
- Physics UI: `src/physics/app.js`
- Biology UI: `src/biology/app.js`
- Chemistry UI: `src/chemistry/app.js`
- Tutoring UI: `src/tutoring/app.js`, `src/tutoring/index.html`
- Styles: `src/styles.css`
- Physics data: `data/physics/processed/questions.json`
- Biology data: `data/biology/processed/questions.json`
- Chemistry data: `data/chemistry/processed/questions.json`
- Tutoring data: `data/tutoring/processed/questions.json`, `data/tutoring/processed/markschemes.json`

## Infra Context
- Deploy target: Render (Docker).
- Asset offload: Cloudflare R2 at `https://pub-f7419ca433e9434bad2f9e89e252c205.r2.dev`
  - Bio/chem images are on R2 (too large for Docker image).
  - Tutoring images are in the Docker container (served same-origin).
- R2 upload script likely at root level (check existing scripts for physics).

## Local Run (quick)
```bash
cd /Users/s933863@aics.espritscholen.nl/Downloads/Project/AA-HL-Question-Bank
python3 server.py
```
Then open: `http://localhost:8080`
