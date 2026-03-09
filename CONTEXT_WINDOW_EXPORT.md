# Context Window Export (for new chat)

Date: 2026-03-10
Project: `AA-HL-Question-Bank`
Latest pushed commit: `2f9c271` (main)

## Current State
- Physics bank is active focus.
- Main recurring issues: markscheme alignment, missing badge correctness, and classification quality.
- User preference: **surgical fixes only** (avoid global rebuilds that break already-good mappings).
- User preference: auto **commit + push** after work unless told otherwise.
- User preference: keep `CONTEXT_WINDOW_EXPORT.md` updated after each completed task for chat handoff continuity.
- User preference: when `All levels` is selected, prioritize `SL` and suppress `HL` duplicates.
- User constraint: do not change Paper 1A / Paper 2 / Paper 3 logic when fixing current Paper 1B issues.

## Most Recent Change (last task)
- Request: combine Paper 1A and Paper 1B in Physics Papers to match real exam flow.
- Fix applied in `src/physics-papers.js`:
  - for 2025+ sessions, merges `Paper 1A` + `Paper 1B` into a single launcher card: `Paper 1 (1A + 1B)`;
  - combined card opens physics bundle mode for `paperNo=1` without exact paper-code lock, so both sections load together;
  - combined exam mode duration is the official Paper 1 total (`SL 90m`, `HL 120m`);
  - non-2025 papers and other paper codes remain unchanged.
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
