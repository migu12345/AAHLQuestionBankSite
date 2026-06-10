# Context Window Export (for new chat)

Date: 2026-06-10 (updated)
Project: `AA-HL-Question-Bank`

## Current State
- Biology bank: LIVE with 3299 questions from 182 papers (2016–2025).
- Chemistry bank: LIVE with questions from 188 papers (2016–2025).
- Physics bank: markscheme crops fixed (2026-06-10).
- **Math/Tutoring bank: 713 questions across Topics 1–5 (HL + SL), full AA bank UI parity.**
- User preference: **surgical fixes only**.
- User preference: auto **commit + push** after work.
- User preference: keep `CONTEXT_WINDOW_EXPORT.md` updated.
- User preference: when `All levels` is selected, prioritize `SL` and suppress `HL` duplicates (biology/chemistry only).
- User constraint: do not change Paper 1A / Paper 2 / Paper 3 logic when fixing unrelated issues.

## Most Recent Completed Work (2026-06-10, twelfth session)

### Tutoring bank — comprehensive preamble bleed fix (all T-style PDFs)

**Problem:** In T-style compilation PDFs, Q(n+1)'s preamble (setup text, diagrams like
circle/waterwheel) appears ABOVE its detected sub-part label. Two bugs resulted:
1. Q(n)'s bottom crop = Q(n+1).y - 10 → included Q(n+1)'s preamble (bleed)
2. Q(n+1)'s top crop also missed its own preamble (existing `_gap_based_top` with
   threshold=30px triggered on answer-box gaps, returning wrong top)

**Fix:** New `_find_preamble_start()` in `recrop_tutoring_preambles.py`:
1. Filters out "..." answer-box filler lines (_is_dotted_line)
2. Recognises both standalone ("1b.") AND inline ("1c. Find the value...") sub-part
   labels using 3 regex patterns; skips them during the gap walk
3. Finds first gap >20px after Q(n)'s last sub-part content
4. Returns y-coordinate where Q(n+1)'s preamble starts

**Key change in crop_question_from_top:**
- `preamble_detect=True` PDFs: use `_find_preamble_start` as PRIMARY for both
  TOP and BOTTOM computation (NOT `_gap_based_top` which misfires on blank answer boxes)
- `preamble_detect=False` PDFs (P1/P2 style, non-T-style inline): unchanged

**New `preamble_detect` field in T_STYLE:**
- True: T6-1, T2-5, T2-6, Topic 6 Part 1 SL, Topic 2 Part 1, Topic 3 Part 1, Topic 1 Part 1
- False: T6-2P1, T6-2P2 (P1/P2 style), all non-T-style PDFs

523 images re-cropped. R2 sync needed.

---

## Most Recent Completed Work (2026-06-10, eleventh session)

### Tutoring bank — preamble crop fix (Topic 1 Part 1 T.pdf + Topic 6 Part 1 T SL.pdf)

**Problem 1:** `Topic 1 Part 1 T.pdf` was set to `top_preamble=80` (sparse), but its
inter-question gaps are < 80px, causing Q16c content (sequence "5, 6.7, 8.4") to
bleed into Q17's crop. Fixed by changing to `top=bottom=10` (same as other dense PDFs).

**Problem 2:** `Topic 6 Part 1 T SL.pdf` used `top_preamble=10`, but several questions
have their full preamble (function definition + diagram) appearing well above their
first sub-label:
- Q7: waterwheel diagram 231px above "7a."
- Q8: f(x)=e^{-x²} graph ~170px above "8a."

**Fix:** `_gap_based_top()` in `recrop_tutoring_preambles.py`:
1. Finds last label of a different question on the current page.
2. Walks forward until a text gap > 30px (clear section break).
3. Returns `boundary_y + 20` as the crop top ONLY IF a text line exists within
   50px after it (confirming genuine preamble content follows).
4. Falls back to normal `top_preamble` buffer if no useful gap found (e.g. Q16
   where preamble is just 4px above the sub-label and there's nothing useful below
   Q15's answer-space boundary).

523 images re-cropped. R2 sync needed.

---

## Most Recent Completed Work (2026-06-10, tenth session)

### Tutoring bank — comprehensive crop fix + duplicate removal

**Problem 1: bottom_preamble=80 was cutting question content for dense PDFs.**
When top_preamble=10 but bottom_preamble=80, questions whose next question is < 90px away
had their crop bottom fall ABOVE their own content, producing near-empty images. Fixed by
setting bottom_preamble=10 everywhere top_preamble=10 is used.

**Problem 2: Non-T-style PDFs (Math_SL_Algebra, Math_SL_Calculus_Julius, etc.) not covered
by recrop.** Extended recrop_tutoring_preambles.py to cover all affected PDFs:
- Dense (min gap < 80px): top=bottom=10
- Added PDF_ALIASES dict for Math_SL_Functions_Equations_2023.pdf → renamed (1) copy

**Full list of PDFs now recroped at top=bottom=10:**
T6-1 HL, T2-5, T2-6, Topic 2 Part 1, Topic 6 Part 1 SL, Math_SL_Algebra,
Math_SL_Calculus_Julius, Math_SL_Circular_FunctionsTrig, Math_SL_Functions_Equations_2023,
Topic_6_Calculus. T6-2P1/P2 changed to top=bottom=5.

**523 question images re-cropped.**

**Duplicates removed:** t2_5_q3, t2_6_q8, t2_6_q19, t2_6_q24 — 4 duplicates removed,
713 questions remain (was 717).

**Still pending (detection anomalies):** Topic 1 Part 1 T.pdf has detection errors
(Q2→Q27, Q36→Q5) — needs separate investigation.

**R2 sync needed** for all re-cropped images.

---

## Most Recent Completed Work (2026-06-10, ninth session)

### Tutoring bank — question crop bleed fix (T2-5, T2-6, T6-1)

**Root cause:** `top_preamble=80` in `recrop_tutoring_preambles.py` was too large for
densely-packed T-style PDFs. When the gap between consecutive question starts was < 80px,
the crop for Q(N) started inside Q(N-1)'s content. Diagnosis showed preamble text (marks
labels, leading words) appears only 4–6px above each detected question start — so
`top_preamble=10` safely captures it without bleeding.

**Affected PDFs (top_preamble changed 80→10):**
- `T2-5 T (2).pdf` — bleed pairs: Q1→Q2 (60px), Q2→Q3 (69px), Q5→Q6 (82px), Q9→Q10 (79px)
- `T2-6 T (1).pdf` — bleed pair: Q4→Q5 (48px)
- `T6-1 T HL.pdf` — bleed pairs: Q7→Q8 (77px), Q10→Q11 (63px), Q28→Q29 (54px)

**88 question images re-cropped.** R2 sync needed for updated PNG files.

**Not yet fixed (detection anomalies, needs separate investigation):**
- `Topic 1 Part 1 T.pdf` (Q2→Q27: 6px gap — likely a detection error)
- `Topic 2 Part 1 T.pdf` (Q6→Q3: 32px — detection ordering issue)
- `Topic 6 Part 1 T SL.pdf` (Q7→Q15: 79px)

---

## Most Recent Completed Work (2026-06-10, eighth session)

### History bank — remove source PDF button from P2/P3

`src/history/app.js` line 313: added `q.paper_type === "Paper 1" &&` guard so the
"Open source PDF" button only renders for P1 questions (where source booklets exist).
P2 and P3 had no `source_booklet_path` field but the template element was present.

### ESS — strip answer-space artefacts from question_text

425 ESS questions had `\x08` (backspace), `\x07` (bell), `�` (replacement chars),
and `. . . . .` dot sequences in `question_text` — these are PDF answer-line artefacts
that showed as a wall of `?` in the browser. Cleaned all 425 with a one-shot script.

---

## Most Recent Completed Work (2026-06-10, seventh session)

### ESS n22 P2 NTZ Q1 and Q2 — missing question images fixed

`ess_n22_p2_ntz_q1` and `ess_n22_p2_ntz_q2` had empty `question_image_paths` due to a
dichotomous key in the PDF ("1. a. Less than 30 cm…") being misdetected as Q1 start,
preventing the real Q1 from being found.

**Fix (`scripts/build_ess_bank.py`):** Added `re.match(r"^\d+\.\s+[a-z][.\s]", text)` guard
to skip dichotomous key sub-entries in `detect_starts`. Re-ran `fix_ess_n22_images.py` to
regenerate 4 images each for Q1 and Q2. Diagnostic + fix scripts deleted after use.

**All commits now pushed to origin/main.**

**R2 sync needed** for new ESS n22 images (8 PNGs) and physics markscheme images rebuilt in
the third session.

---

## Most Recent Completed Work (2026-06-10, sixth session)

### History bank — side-by-side + source PDF

- **Side-by-side modal**: shown for any question with a markscheme. Left panel = question text
  + P1 sources; right panel = markscheme. Uses the existing `.compare-modal` / `.compare-grid`
  CSS already in styles.css.
- **"Open source PDF" link** (P1 only): opens the source booklet PDF in a new tab via
  `window.assetUrl()`. Source booklet PDFs (14 sessions, 2–15MB each) copied to
  `data/history/processed/source_booklets/{sc}.pdf` — served same-origin from Docker
  (no separate R2 upload needed since Dockerfile copies all data/).
- **`.btn-secondary` CSS class** added to styles.css for the PDF link button style.

**26 commits ahead of origin/main** — need push.

---

## Most Recent Completed Work (2026-06-10, fifth session)

### History P1 sources added

Added `sources` field to all 341 P1 questions (100%). Text and resource booklets
exist for every session (2018–2025), named either `text_booklet` or `resource_booklet`.

**Script:** `scripts/add_history_sources.py`

**Coverage:** 14 sessions × 5 prescribed subjects × 4 sources each. Text sources
extracted as full text; image/visual sources labeled `[Visual source — not available as text]`;
copyright-removed text sources labeled `[Source text removed for copyright reasons]`.

**Parsing notes:**
- Source booklets named `text_booklet` (2018–2023) or `resource_booklet` (2021, 2024–2025)
- Image detection uses keywords: "depicts", "depicting", "illustration", "illustrator", "map",
  "cartoon", "photograph", "painting", "portrait", etc.
- Attribution ends at line with year in parens e.g. "(2009)."
- "End of" lines filtered from text content

**UI:** "Sources" collapsible `<details>` panel added to P1 question cards,
showing source header (label + attribution) + text body.

**24 commits ahead of origin/main** — need push.

---

## Most Recent Completed Work (2026-06-10, fourth session)

### History bank — markschemes added

Added `markscheme_text` field to 3292/3293 history questions (99.97%) by parsing
markscheme PDFs from the IB archive.

**Script:** `scripts/add_history_markschemes.py` (standalone, run after build_history_bank.py)

**Coverage by paper type:**
- P1: bullet-point answer content per sub-question, matched by session + PS + question_number
- P2: markbands table + question-specific guidance paragraph (separated by `---`)
- P3: markbands table + question-specific guidance paragraph (separated by `---`)

**Parsing challenges solved:**
- Old-style `2017-2022` PDFs use `1.` question format; m25 PDFs use `1)` format (both supported)
- m25 P3 Americas uses `"N: Section Name"` section headers (not "Section N:")
- m25 P3 Europe/other regions use `"21 TZ1. question"` format for TZ-specific questions
- Questions stored without sub-labels (e.g. `q1` not `q1a`) get combined (a)+(b) markschemes
- TZ slug in question IDs uses just the number (`_1_`) not `_tz1_`
- Markbands extraction starts from "Markbands for paper" to skip copyright pages

**UI:** `src/history/index.html` and `src/history/app.js` — added collapsible `<details>` markscheme
panel per card. CSS in `src/styles.css` (`.ms-pre`, `.ms-divider`).

**23 commits ahead of origin/main** — need push (no R2 sync needed, history is text-only).

---

## Most Recent Completed Work (2026-06-10, third session)

### Physics markscheme crop fix

**Root cause — two distinct bugs in `detect_ms_starts` (rebuild_physics_markschemes.py):**

1. **Modern IB format (m22–m25)**: Left-column y-range `280 <= y <= 540` excluded first-row
   entries at y≈105–120, so Q2's anchor was detected at the "b i" row (y≈345) instead
   of the "a i" row (y≈105). This caused Q1 crops to include Q2.a rows at the bottom,
   and Q2 crops to start mid-table missing Q2.a entirely.

2. **Old IB landscape format (m16–m17)**: These PDFs are stored with page Rotation=90.
   fitz returns word coordinates in native (pre-rotation) space, so the question-number
   column (native x≈266 → display y≈266 after rotation) was never detected by the
   `x <= 72` left-column rule. Fallback anchor of y=120 caused Q1's last rows to bleed
   into Q2's crop.

**Fixes applied to `scripts/rebuild_physics_markschemes.py`:**
- Lowered y-range from `280–540` to `90–700` in both the `has_table_header` and
  `elif not is_rubric_page` branches.
- Added block-scan for pages with `Rotation in (90, 270)`: reads text blocks, finds ones
  starting with a digit + letter (question + subpart), and uses `block.x0` as `display_y`
  anchor (score=12, beats text-line fallback but loses to footer).
- Rebuilt 952 markscheme images via `python3 scripts/rebuild_physics_markschemes.py`.

**22 commits ahead of origin/main** — need push + R2 sync for new/changed images.

---

## Most Recent Completed Work (2026-06-10, second session)

### History question bank — new feature

Built from scratch: `scripts/build_history_bank.py` + `data/history/processed/questions.json`
+ `src/history/index.html` + `src/history/app.js`.

**Scope:** New-syllabus IB History (2018–2025), Paper 1 / Paper 2 / Paper 3.
- **3293 questions** extracted from 104 PDF files via fitz text extraction (no images needed).
- P1: 5 prescribed subjects × ~5 questions each × sessions; includes sub-questions (a)(b).
- P2: 12 World History topics × 2 questions = 24 per paper; TZ1/TZ2/TZ3 variants.
- P3: 4 regions (Europe, Americas, Africa/ME, Asia/Oceania) × 36 questions per paper.
- Handles two PDF text layouts: "N. inline text" (older) and "N.\t\ntext on next line" (newer).

**UI:** Paper Type / Topic+Region / Section / Paper filters + search + save/done (localStorage).
Questions are pure text — no image display. New `.tag` and `.tag-subtle` CSS classes added.

**Source PDFs:** discovered from archive at `/Downloads/IB PAST PAPERS - YEAR/`, under
`Individuals and societies/` subfolders. May 2025 includes TZ3 variants.

**20 commits ahead of origin/main** — need push + R2 sync (history has no images, so no R2 needed).

---

## Most Recent Completed Work (2026-06-10)

### ESS P1 markscheme detection fix

**Root cause:** `detect_starts` was picking up numbered marking instruction items (1–10) on
the "Subject details: ... Mark allocation ..." page as if they were question starts Q1–Q10.
The code prefers EARLIER occurrences when scores tie, so instructions items on page 2 always
won over real questions on pages 3–11. All crops were tiny slivers (< 80px) and were skipped.

The existing check for `"environmental systems and societies uses marking points"` only fired
for P2-style markschemes; P1 markschemes use a differently-worded numbered list.

**Fix:** Added `if "subject details:" in page_text_lower: continue` to `detect_starts`
(same location as the existing "uses marking points" skip). This skips the instructions page
for both P1 and P2 markscheme formats.

**Effect (181 files changed):** 26 new images for May 2024 P1 TZ1+TZ2 (the original bug),
plus newly-recovered P1 markschemes for m15, m16, m19, m21, m22, n15, n16, n19, n20, n21
that were silently missing before.

**18 commits ahead of origin/main** — need push + R2 sync for all new/changed ESS images.

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
