# Context Window Export (for new chat)

Date: 2026-03-10
Project: `AA-HL-Question-Bank`
Latest pushed commit: `ed770a2` (main)

## Current State
- Physics bank is active focus.
- Main recurring issues: markscheme alignment, missing badge correctness, and classification quality.
- User preference: **surgical fixes only** (avoid global rebuilds that break already-good mappings).
- User preference: auto **commit + push** after work unless told otherwise.
- User preference: keep `CONTEXT_WINDOW_EXPORT.md` updated after each completed task for chat handoff continuity.
- User preference: when `All levels` is selected, prioritize `SL` and suppress `HL` duplicates.
- User constraint: do not change Paper 1A / Paper 2 / Paper 3 logic when fixing current Paper 1B issues.

## Most Recent Change (last task)
- Request: create a new `Physics Papers` launcher page like Math Papers and wire exam mode timings for Physics SL/HL.
- Added:
  - `src/physics-papers.html`
  - `src/physics-papers.js`
- Navigation wired:
  - new home card on `src/index.html`
  - direct link from `src/physics/index.html` to `physics-papers.html`
- Physics bundle improvements (`src/physics/app.js`):
  - added support for `paperCode` query param (`1`, `1A`, `1B`, `2`, `3`);
  - bundle filtering now matches exact paper code when provided;
  - bundle paper type preselect now respects paper code (for example `Paper 1B`).
- Exam mode durations configured in Physics Papers:
  - 2025+ (new syllabus): SL `1A/1B = 90m`, `2 = 90m`; HL `1A/1B = 120m`, `2 = 150m`.
  - pre-2025 (legacy): SL `1 = 45m`, `2 = 75m`, `3 = 60m`; HL `1 = 60m`, `2 = 135m`, `3 = 75m`.
- Source references used for timings:
  - IB DP Physics subject brief (first assessment 2025)
  - IB exam schedule archives (for pre-2025 durations)
- Commit/push: `ed770a2` to `origin/main`.

## Key Decisions Already Made
- Old Physics MCQ `Paper 1` should be treated as `Paper 1A` equivalent behavior.
- Paper 1A/1 questions are 1 mark each.
- Side-by-side markscheme overlay is required UX pattern.
- Keep stable mappings stable; do not mass-regenerate everything if unnecessary.

## Known Open Problem Areas
- Some Physics markscheme mappings (especially Paper 2/3 edge cases) still need precise per-question checks.
- Some entries can still show wrong/no markscheme in specific years/timezones.
- Classifier still needs improvement to reduce unsorted/misclassified cases.
- User supplied a full keyword map for A/B/C/D/E topics and subtopics and expects near-zero unsorted.

## Important Files
- Physics UI: `src/physics/app.js`
- Physics styles: `src/styles.css`
- Metadata/classification script: `scripts/refresh_physics_metadata.py`
- Markscheme mapping script: `scripts/rebuild_physics_markschemes.py`
- Physics data: `data/physics/processed/questions.json`
- Physics images:
  - `data/physics/processed/images/questions/`
  - `data/physics/processed/images/markschemes/`

## Infra Context
- App deploy target: Render.
- Asset offload target: Cloudflare R2.
- Public R2 URL referenced: `https://pub-f7419ca433e9434bad2f9e89e252c205.r2.dev`

## Local Run (quick)
From repo root:
```bash
cd /Users/s933863@aics.espritscholen.nl/Downloads/Project/AA-HL-Question-Bank
python3 server.py
```
Then open: `http://localhost:8080`

## Existing Prior Handoff
- Earlier condensed handoff also exists at:
  - `CHAT_HANDOFF_CONTEXT.md`

## Note
- This is a concise export summary, not a full raw transcript.
