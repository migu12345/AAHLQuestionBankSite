# Context Window Export (for new chat)

Date: 2026-05-15
Project: `AA-HL-Question-Bank`
Latest pushed commit: `6d7b866b` (main)

## Current State
- Biology bank: LIVE with 3299 questions from 182 papers (2016–2025).
- Chemistry bank: build running (~3000 images generated), commit pending.
- Physics bank: stable, existing.
- User preference: **surgical fixes only**.
- User preference: auto **commit + push** after work.
- User preference: keep `CONTEXT_WINDOW_EXPORT.md` updated.
- User preference: when `All levels` is selected, prioritize `SL` and suppress `HL` duplicates.
- User constraint: do not change Paper 1A / Paper 2 / Paper 3 logic when fixing unrelated issues.

## Most Recent Completed Work (this session)

### Biology + Chemistry Question Banks — Full Pipeline
- **Source**: IB past papers in `/Users/s933863@aics.espritscholen.nl/Documents/IB PAST PAPERS - YEAR`
- **Scope**: English-only, 2016–2025, Biology + Chemistry, both question papers and markschemes.
- **Files added**:
  - `scripts/setup_bio_chem_papers.py` — scans archive, filters English-only Bio/Chem PDFs, copies to project, writes `manual_papers.json` for both subjects. 579 PDFs copied (182 bio + 188 chem papers).
  - `scripts/build_biology_bank.py` — updated `infer_topic()` to use IB 2025+ Biology themes A–D.
  - `scripts/build_chemistry_bank.py` — new build script with IB 2025+ Chemistry topic inference (Structure 1–3, Reactivity 1–3).
  - `src/biology/app.js` / `src/biology/index.html` — full question bank UI (existing from prior session).
  - `src/chemistry/app.js` — full question bank UI (adapted from biology, chemistry paths).
  - `src/chemistry/index.html` — full question bank HTML (adapted from biology).
  - `data/biology/processed/questions.json` — 3299 biology questions.
  - `data/biology/processed/images/` — 4026 question/markscheme PNG crops.
  - `data/biology/processed/manual_papers.json` — 182 paper entries.
  - `data/chemistry/processed/manual_papers.json` — 188 paper entries.
  - `data/resources/biology/` — 182 PDFs organized in m16–n24 subdirs.
  - `data/resources/chemistry/` — 188 PDFs organized in m16–n24 subdirs.

### IB 2025+ Syllabus Alignment
- Biology topic-map: `data/biology/topic-map.json` — Themes A/B/C/D.
- Chemistry topic-map: `data/chemistry/topic-map.json` — Structure 1–3 + Reactivity 1–3.
- Both `build_biology_bank.py` and `build_chemistry_bank.py` use keyword-based `infer_topic()` matching against new curriculum names.

### Pending After This Session
- Chemistry build will finish and produce `data/chemistry/processed/questions.json` + images.
- Run `git add data/chemistry/ && git commit && git push` after chemistry build finishes.
- Consider Cloudflare R2 upload for images if served from R2 (same workflow as physics).

## Key Architecture

### Build Pipeline
1. `scripts/setup_bio_chem_papers.py` → copies PDFs + writes `manual_papers.json`
2. `python3 scripts/build_biology_bank.py` → reads `manual_papers.json`, crops PNGs, writes `questions.json`
3. `python3 scripts/build_chemistry_bank.py` → same for chemistry

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
- `bio_{session}_{paper}_{tz}_{level}_q{n}.png` (e.g., `bio_m22_p2_tz1_hl_q3.png`)
- `chem_{session}_{paper}_{tz}_{level}_q{n}.png`

## Key Decisions Already Made
- Old Physics MCQ `Paper 1` → treated as `Paper 1A` equivalent.
- Paper 1A/1 questions are 1 mark each.
- Side-by-side markscheme overlay is required UX pattern.
- Biology/Chemistry images served relative to `data/{subject}/processed/`.
- Biology/Chemistry deduplication: SL preferred over HL when `All levels` selected (via `dedupeForAllLevels()`).

## Important Files
- Physics UI: `src/physics/app.js`
- Biology UI: `src/biology/app.js`
- Chemistry UI: `src/chemistry/app.js`
- Styles: `src/styles.css`
- Physics data: `data/physics/processed/questions.json`
- Biology data: `data/biology/processed/questions.json`
- Chemistry data: `data/chemistry/processed/questions.json`

## Infra Context
- Deploy target: Render.
- Asset offload: Cloudflare R2 at `https://pub-f7419ca433e9434bad2f9e89e252c205.r2.dev`
- R2 upload script likely at root level (check existing scripts for physics).

## Local Run (quick)
```bash
cd /Users/s933863@aics.espritscholen.nl/Downloads/Project/AA-HL-Question-Bank
python3 server.py
```
Then open: `http://localhost:8080`
