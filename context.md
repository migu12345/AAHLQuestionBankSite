# AA HL Question Bank: current context

Updated: 2026-09-17

## Project and working preferences

- Multi-subject IB question bank in `C:\Users\migue\AAHLQuestionBankSite`; Render deploys `main` from GitHub.
- Keep fixes surgical. Commit and push completed changes. Keep this file and `CONTEXT_WINDOW_EXPORT.md` current.
- Frontend JSON is served by Flask. Most images and PDFs use the public Cloudflare R2 asset host. The local Python environment is `C:\Users\migue\.venvs\AAHLQuestionBankSite`.

## Recently completed

- Fixed the Render Docker image so Economics, ESS, and History JSON loads. Added `/health` and `scripts/smoke_check.py` to check required routes.
- Added the Economics Paper 1/2/3 filter and a Physics/Tutoring markscheme audit.
- Removed duplicate Tutoring markschemes, leaving 713 questions and 713 unique markschemes.
- Linked five verified Physics markscheme screenshots. Removed one phantom Physics question with no real source question.
- Prepared clean crops for `phys_m17_p3_tz2_q13_hl` and `phys_m17_p3_tz2_q9_sl`.

## Current work

- The two May 2017 Physics Paper 3 crops are now linked in `data/physics/processed/questions.json` and served by Flask from the Render image. `src/asset-base.js` routes only these two PNGs to the app origin because public R2 has an incorrect Q13 image and no Q9 image. Docker and health/smoke checks include both files.
- The local markscheme audit passes: 2,979 Physics questions, 713 Tutoring questions, no missing or mismatched references. The local smoke check passes 34 routes.
- Check `git status` and the latest commit for publication state. Docker is not installed locally, so confirm the Docker build on Render.

## Next steps

1. Confirm the latest commit reached GitHub, then check the new Render deployment serves both PNGs and both Physics records show the correct markscheme.
2. If R2 upload access becomes available, sync the two correct crops to their matching R2 keys and remove the temporary app-origin routing and Docker copies after byte comparison.
3. Continue targeted question and markscheme quality checks; avoid broad rebuilds of already-correct papers.
