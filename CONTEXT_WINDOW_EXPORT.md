# Context Window Export (for new chat)

Date: 2026-03-10
Project: `AA-HL-Question-Bank`
Latest pushed commit: `83bb289` (main)

## Current State
- Physics bank is active focus.
- Main recurring issues: markscheme alignment, missing badge correctness, and classification quality.
- User preference: **surgical fixes only** (avoid global rebuilds that break already-good mappings).
- User preference: auto **commit + push** after work unless told otherwise.
- User preference: keep `CONTEXT_WINDOW_EXPORT.md` updated after each completed task for chat handoff continuity.
- User preference: when `All levels` is selected, prioritize `SL` and suppress `HL` duplicates.
- User constraint: do not change Paper 1A / Paper 2 / Paper 3 logic when fixing current Paper 1B issues.

## Most Recent Change (last task)
- Request: exam mode in Physics did not hide markschemes.
- Root cause: Physics page has no exam-mode control bar, so `examMode.started` never became true.
- Fix applied in `src/physics/app.js`:
  - exam lock now applies whenever exam mode is enabled and not ended;
  - when opened via exam query params, exam mode auto-starts immediately (sets started/endTs);
  - side-by-side modal is blocked while exam is locked.
- Scope: Physics UI logic only; no Paper 1A/2/3 extraction logic changes.
- Commit/push: pending in current task.

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
