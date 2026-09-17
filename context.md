# AA HL Question Bank: current context

Updated: 2026-09-18

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

- The two May 2017 Physics Paper 3 crops are linked in `data/physics/processed/questions.json`. Both were uploaded to `aahl-assets` at their matching `data/physics/processed/images/markschemes/` keys. The public R2 copies match Git byte-for-byte.
- The temporary same-origin exception for these two PNGs has been removed from `src/asset-base.js`, Docker, health, and smoke checks. They now use the standard R2 asset routing. The uploader used local credentials and left no secrets in the repository.
- The markscheme audit passes: 2,979 Physics questions, 713 Tutoring questions, no missing or mismatched references. Cleanup commit `ffe270ac` was pushed and deployed on Render; the live smoke check passes all 32 app routes.

## Next steps

1. Continue targeted question and markscheme quality checks; avoid broad rebuilds of already-correct papers.
