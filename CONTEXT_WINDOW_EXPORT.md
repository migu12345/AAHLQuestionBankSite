# Context Window Export (for new chat)

Date: 2026-05-20
Project: `AA-HL-Question-Bank`

## Current State
- Biology bank: LIVE with 3299 questions from 182 papers (2016–2025).
- Chemistry bank: LIVE with questions from 188 papers (2016–2025).
- Physics bank: stable, existing.
- **Math/Tutoring bank: 717 questions across Topics 1–5 (HL + SL), full AA bank UI parity.**
- User preference: **surgical fixes only**.
- User preference: auto **commit + push** after work.
- User preference: keep `CONTEXT_WINDOW_EXPORT.md` updated.
- User preference: when `All levels` is selected, prioritize `SL` and suppress `HL` duplicates (biology/chemistry only).
- User constraint: do not change Paper 1A / Paper 2 / Paper 3 logic when fixing unrelated issues.

## Most Recent Completed Work (2026-06-09)

### Bug Fixes

**KaTeX broken LaTeX (151 markschemes):**
Raw `<` and `>` inside `\(...\)` math blocks (e.g. `|2x|<1`) broke HTML parsing when the
`latex_solution` HTML string was set as `innerHTML` — the browser tokenizer treats `<x` or
`<\t` as tag openers. Fixed by escaping to `&lt;`/`&gt;` within all math delimiters.
KaTeX's `renderMathInElement` reads DOM text nodes which decode `&lt;` → `<` transparently.

**Crop bleed for T6-2P1 / T6-2P2 questions (P1/P2 style PDFs):**
The 80px top-preamble buffer was pulling in the previous question's last lines at the top of
the next question's image (Q10's content appeared at the top of Q11's image). Root cause:
Paper 1/2 questions start directly with "N. text" — no preamble above the question number —
so 80px was always Q10 territory, not Q11 preamble.
Fixed: `recrop_tutoring_preambles.py` now uses per-PDF `(top_preamble, bottom_preamble)`.
T6-2P1 and T6-2P2 use top=5px, bottom=80px (adaptive fallback to n.y−5 when tight).

**ESS markscheme images fixed (2026-06-10):**
In newer ESS P1/P2 PDFs (2020+), the generic marking instructions page ("1. Environmental
systems and societies uses marking points...") appeared AFTER the Q&A table, so detect_starts
was picking it up as Q1. Fixed ms_data_start_page detection to find the first page with
actual answer content ([N] + award/accept keywords). Re-cropped all 365 ESS markscheme images.

**ESS images committed (previous session):**
755 question images, 305 markscheme images, 34 text booklet PDFs added.

**16 commits ahead of origin/main** (need push + R2 sync for new/changed images).

## Most Recent Completed Work (2026-05-20)

### KaTeX Markschemes — ALL COMPLETE (2026-05-20)

- **ALL 717/717 questions now have `latex_solution`** — 100% complete.
- This session added final 36 questions: t1_cnt (q1,q3,q5,q6,q7,q8,q10), t1_seq (q3,q6,q7,q8,q11,q14), t1_topic_1_4 induction (q1–q9), t1_topic_1_5 complex numbers (q1–q11), t1p1 (q7,q13), t3p1_q1.
- Topics covered: combinatorics, de Moivre, induction proofs, sequences/series, complex numbers (polar form, loci, cube roots of unity, Möbius transforms).
- All helper/generator scripts deleted after use.

**Previously completed (2026-05-19):**
- t4_sl (48), t4_hl (50), t2_6, t3_trig, t3p1 (29 of 30)

**Previously completed (earlier):**
- t5_hl (85), t5_p1 (25), t5_p2 (33), t5_sl, t5_lim_t61, t2, t1 (many)

**Remaining topics (in order):**
- t5/t6 (calculus — ~295 questions, largest block)

### Math/Tutoring Bank — Full Rebuild
- Processed **18 new PDFs** from `~/Downloads/Math/` covering Topics 1–5.
- **717 total questions** (up from 145): 342 HL + 375 SL.
- By topic: T1=173, T2=92, T3=59, T4=98, T5=295.
- All questions have: `level` (HL/SL), `marks`, `paper_type` (where applicable), `subtopic`.
- Question images (PNG) cropped from PDFs using fitz. All questions have ≥1 image.
- Draft markscheme SVGs auto-generated for all 717 questions.

### UI Upgrade — Tutoring page → AA bank feature parity
- **`src/tutoring/index.html`** — completely rewritten to match `aa-bank.html`:
  - Level filter, Paper Type filter, Difficulty filter, Study (saved/done) filter
  - Topic filter (dynamic subtopics), Subtopic filter
  - Search bar with toggle button
  - Question cards with Save/Done buttons + Side-by-side button
  - Compare modal (side-by-side view)
- **`src/tutoring/app.js`** — rewritten to match `src/app.js`:
  - localStorage saved/done state (`math_bank_user_actions_v1`)
  - `inferLevel()`, `inferDifficulty()` (from marks + level + paper)
  - Dynamic subtopic filtering based on selected topic
  - Side-by-side compare modal
  - Search supports `hl`, `sl`, `p1`, `p2`, `q4` shortcuts

### New Scripts
- `scripts/tutoring/enrich_metadata.py` — adds level/marks/paper_type to existing questions
- `scripts/tutoring/build_all_new_pdfs.py` — processes all new PDFs from Downloads/Math

## Key Architecture

### Build Pipeline
1. `scripts/setup_bio_chem_papers.py` → copies PDFs + writes `manual_papers.json`
2. `python3 scripts/build_biology_bank.py` → biology questions
3. `python3 scripts/build_chemistry_bank.py` → chemistry questions
4. `python3 scripts/tutoring/build_topic1.py` → original Topic 1 questions (legacy)
5. `python3 scripts/tutoring/build_topic2.py` → original Topic 2 questions (legacy)
6. `python3 scripts/tutoring/enrich_metadata.py` → adds level/marks to all questions
7. `python3 scripts/tutoring/build_all_new_pdfs.py` → processes all new PDFs

### Math/Tutoring Source PDFs (~/Downloads/Math/)
Already processed (original 145 questions):
- Topic 1: `Binomila Theorem.pdf` (SL), `Math_SL_Algebra.pdf` (SL), `Math_SL_Algebra_Exp_Log.pdf` (SL),
  `Topic_1_2_Algebra_Exponents_Logarithms_2023.pdf` (HL), `Topic_1_4_Algebra_Mathematical_Induction.pdf` (HL),
  `Topic_1_5_Algebra_Complex_Numbers.pdf` (HL)
- Topic 2: `Math_SL_Functions_Equations_2023.pdf` (SL)

New PDFs (572 questions added in this session):
- Topic 1: `Topic_1_1_Algebra_Sequences_Series.pdf` (HL), `Topic_1_3_Algebra_Counting_Principles (1).pdf` (HL),
  `Topic 1 Part 1 T.pdf` (SL)
- Topic 2: `T2-5 T (2).pdf` (HL), `Topic 2 Part 1 T.pdf` (SL)
- Topic 3: `Math_SL_Circular_FunctionsTrigonometry.pdf` (SL), `Topic 3 Part 1 T (1).pdf` (SL)
- Topic 4: `Math_SL_Statistics_Probability_2022 (1).pdf` (SL), `statistics (1).pdf` (HL)
- Topic 5: `Math_SL_Calculus_Julius (1).pdf` (SL), `Limits_derivatives (1).pdf` (HL),
  `Topic_6_Calculus.pdf` (HL), `T6-1 T HL.pdf` (HL), `T6-2P1 T.pdf` (HL P1),
  `T6-2P2 T.pdf` (HL P2), `T2-6 T (1).pdf` (HL), `Topic 6 Part 1 T SL.pdf` (SL)

Skipped: `DP1_and_DP2_AA_HL_Course_Overview_2025_2027.pdf` (course outline, no questions),
         `Math test Miguel (2).pdf` (personal test, not IB practice)

### Tutoring Data Schema (questions.json)
```json
{
  "id": "t5_hl_q1",
  "unit": "Topic 5 Calculus",
  "topic": "Calculus",
  "subtopic": "Integration techniques",
  "source_file": "Topic_6_Calculus.pdf",
  "question_number": "1",
  "title": "Q1",
  "question_text": "...",
  "question_image_paths": ["images/questions/t5_hl_q1.png"],
  "level": "HL",
  "paper_type": "Paper 1",
  "marks": 6
}
```

### Image Naming
- Legacy Topic 1/2: `t1_{stem}_q{n}.png`, `t2_{stem}_q{n}.png`
- New PDFs: `{id_prefix}_q{n}.png` or `{id_prefix}_q{n}_p{page}.png`
- Markscheme SVGs: `images/markschemes/{id}.svg`

## Key Decisions
- Old Physics MCQ `Paper 1` → treated as `Paper 1A` equivalent.
- Paper 1A/1 questions are 1 mark each.
- Side-by-side markscheme overlay is required UX pattern.
- Biology/Chemistry images served relative to `data/{subject}/processed/`.
- Biology/Chemistry deduplication: SL preferred over HL when `All levels` selected.
- Tutoring/Math images served same-origin (copied into Docker container).
- Math bank uses `math_bank_user_actions_v1` localStorage key.
- Difficulty is computed client-side from marks + level + paper type.

## Important Files
- Physics UI: `src/physics/app.js`
- Biology UI: `src/biology/app.js`
- Chemistry UI: `src/chemistry/app.js`
- Math/Tutoring UI: `src/tutoring/app.js`, `src/tutoring/index.html`
- Styles: `src/styles.css`
- Physics data: `data/physics/processed/questions.json`
- Biology data: `data/biology/processed/questions.json`
- Chemistry data: `data/chemistry/processed/questions.json`
- Math data: `data/tutoring/processed/questions.json` (717 q), `data/tutoring/processed/markschemes.json` (**717/717 with latex_solution — COMPLETE**)

## Infra Context
- Deploy target: Render (Docker).
- Asset offload: Cloudflare R2 bucket `aahl-assets` at `https://pub-f7419ca433e9434bad2f9e89e252c205.r2.dev`
  - **ALL subject images now on R2** (biology, chemistry, physics, math, tutoring, business).
  - R2 keys mirror repo paths: `data/<subject>/processed/images/...`
  - `asset-base.js` handles routing: JSON files served same-origin, images/PDFs from R2.
- **R2 Upload (future):** use rclone — dramatically faster than REST API.
  - rclone binary: `~/Downloads/rclone_bin/rclone-v1.74.1-osx-arm64/rclone`
  - Create a temp `rclone.conf` (delete after use — contains credentials):
    ```ini
    [r2]
    type = s3
    provider = Cloudflare
    access_key_id = <Account API token access key>
    secret_access_key = <secret>
    endpoint = https://b958f16085766c52a302e26353ade3f1.r2.cloudflarestorage.com
    ```
  - Upload command:
    ```bash
    rclone copy ./data r2:aahl-assets/data \
      --config rclone.conf \
      --exclude "raw/**" \
      --include "*.png" --include "*.jpg" --include "*.pdf" \
      --transfers 32 --s3-upload-concurrency 8 --progress
    ```
  - S3 endpoint: `https://b958f16085766c52a302e26353ade3f1.r2.cloudflarestorage.com`
  - Get credentials: Cloudflare dashboard → R2 → Manage R2 API Tokens → Create Account API token

## Local Run (quick)
```bash
cd "/Users/s933863@aics.espritscholen.nl/Desktop/Downloads/Project/AAHLQuestionBankSite"
python3 server.py
```
Then open: `http://localhost:8080/`
