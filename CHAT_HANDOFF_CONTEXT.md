# Chat Handoff Context

Date: 2026-03-09  
Project: `AA-HL-Question-Bank`  
Latest pushed commit at handoff: `3a73ef1` (main)

## What This Project Is
- IB-style question bank web app with image-based questions and markschemes.
- Main active subject tracks in this session: Math AA, Business Management, Physics.
- Uses preprocessed JSON + image assets.

## User Working Preferences (important)
- Always auto `commit` + `push` after changes unless explicitly told otherwise.
- Be surgical: fix only requested broken parts; do not broadly regenerate if good sections already work.
- Keep already-correct mappings untouched when possible.
- User is sensitive to regressions in Physics; asks for exact markscheme-to-question alignment.

## Infra / Deployment Context
- Render used for app deployment.
- Heavy assets are being moved/served via Cloudflare R2 public URL.
- R2 public URL mentioned in chat:  
  `https://pub-f7419ca433e9434bad2f9e89e252c205.r2.dev`
- There were repeated deploy/resource issues; user asked for safer scoped updates.

## Major Product Decisions Already Made
- Paper 1/Paper 1A MCQ behavior: treat old “Paper 1” MCQ as Paper 1A equivalent.
- Paper 1A questions should be 1 mark and show A-D style answer behavior.
- Side-by-side markscheme overlay is required UX pattern.
- “Exam mode” should be in AA Papers / past-paper flows, not in main AA question bank.
- Formula booklet is embedded overlay style; user wanted better interaction/resizing behavior.

## Recent Critical Physics Issues Reported
- Wrong markscheme assignment:
  - Q1 sometimes showed Q1+Q2 markscheme.
  - Some questions showed another question’s markscheme (offset misalignment).
- “No markscheme” badge showing when markscheme actually exists.
- Some markschemes shown as extracted text instead of screenshot.
- Cropping issues:
  - top clipped in question/markscheme panes.
  - split/cut pages around continuation boundaries.
- Paper 3:
  - some were good, some broken.
  - user explicitly asked not to ruin already-good Paper 3 mappings.

## What Was Changed In Latest Commit (`3a73ef1`)
Files:
- `src/physics/app.js`
- `src/styles.css`
- `scripts/rebuild_physics_markschemes.py`
- `data/physics/processed/questions.json`
- targeted physics markscheme PNGs (mostly May 2016 P2 and May 2017 P2 TZ2 HL scope)

Behavior changes:
1. Paper 1A/Paper 1 badge logic:
   - no false `No markscheme` badge for MCQ entries.
2. Paper 2 side-by-side:
   - markscheme pane nudged down slightly via CSS class.
3. Rebuild script (`rebuild_physics_markschemes.py`):
   - improved start-anchor detection for older Paper 2 table layouts.
   - stricter fallback rules to avoid false next-question anchors.
   - crop guards to skip near-empty white crops.
   - safer top-offset and tiny-overlap skip logic.
4. Rebuild run was scoped only to:
   - `May 2016 Physics Paper 2 HL`
   - `May 2016 Physics Paper 2 SL`
   - `May 2017 Physics Paper 2 TZ2 HL`

## Remaining Risk Areas / Likely Next Work
- Physics markscheme mapping still needs spot-checking on user-reported edge examples.
- Paper 3 mappings may still contain isolated bad links; user wants per-question exactness.
- Classification quality:
  - user provided a detailed keyword map for A/B/C/D/E topics and subtopics.
  - expects near-zero “Unsorted”.
- Dupes:
  - user asked: if SL/HL duplicates exist in Paper 3, remove HL duplicate.

## Useful Files For Next Chat
- Frontend physics rendering:
  - `src/physics/app.js`
  - `src/styles.css`
- Markscheme mapping rebuild logic:
  - `scripts/rebuild_physics_markschemes.py`
- Core processed data:
  - `data/physics/processed/questions.json`
  - `data/physics/processed/manual_papers.json`
- Physics processed image outputs:
  - `data/physics/processed/images/questions/`
  - `data/physics/processed/images/markschemes/`

## Suggested Safe Workflow For Next Chat
1. Reproduce only the exact failing question IDs from screenshots.
2. Patch script logic for that failure pattern only.
3. Run rebuild with `--paper-label` scope (avoid global rebuild).
4. Validate target IDs in `questions.json`:
   - `markscheme_image_paths`
   - `has_markscheme`
   - no cross-question contamination.
5. Commit + push immediately after each stable fix.

## Note
- This file is a condensed full-session handoff, not a verbatim raw transcript.
- Keep secrets/tokens out of future commits and chat logs.

