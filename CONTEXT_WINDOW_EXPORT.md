# Context Window Export (for new chat)

Date: 2026-03-10
Project: `AA-HL-Question-Bank`
Latest pushed commit: `3526cb0` (main)

## Current State
- Physics bank is active focus.
- Main recurring issues: markscheme alignment, missing badge correctness, and classification quality.
- User preference: **surgical fixes only** (avoid global rebuilds that break already-good mappings).
- User preference: auto **commit + push** after work unless told otherwise.
- User preference: keep `CONTEXT_WINDOW_EXPORT.md` updated after each completed task for chat handoff continuity.
- User preference: when `All levels` is selected, prioritize `SL` and suppress `HL` duplicates.
- User constraint: do not change Paper 1A / Paper 2 / Paper 3 logic when fixing current Paper 1B issues.

## Most Recent Change (last task)
- Request: this mixed-paper exam-mode issue was intended for Math as well.
- Fix applied:
  - `src/aa-papers.js`: launcher now passes exact selected paper label via `bundlePapers`.
  - `src/app.js`: bundle mode now parses `bundlePapers` and enforces question paper label membership in that set.
- Scope: Math paper launcher + bundle filter precision only.
- Commit/push: `3526cb0` to `origin/main`.

## Latest Local Fix (not pushed yet)
- Request: Math still opened mixed questions (example: selecting 2025 Paper 2 showed ~97 questions from other years).
- Root cause found:
  - In `src/app.js` `start()`, bundle state was being force-cleared after query parsing:
    - `state.paperBundle = null`
    - exam mode bar removed
  - This disabled paper-bundle filtering and reverted to global question filtering.
- Fix applied:
  - Removed the forced reset/removal in `start()` so URL bundle params remain active.
  - Math paper launch now stays constrained to the selected paper bundle.
- Files changed:
  - `src/app.js`

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
