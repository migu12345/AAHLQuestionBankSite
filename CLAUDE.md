# CLAUDE.md — AA HL Question Bank

## User Preferences
- Surgical fixes only — don't change unrelated code.
- Auto commit + push after completing work.
- Keep `CONTEXT_WINDOW_EXPORT.md` updated before ending a session.
- When `All levels` is selected, prefer SL and suppress HL duplicates (biology/chemistry only).
- Do not touch Paper 1A / Paper 2 / Paper 3 logic when fixing unrelated issues.

## Project Overview
Multi-subject IB question bank. Subjects: Biology, Chemistry, Physics, Math/Tutoring.
- Deploy: Render (Docker), auto-deploys from GitHub main.
- Assets: Cloudflare R2 bucket `aahl-assets` — ALL images served from R2.
- R2 public URL: `https://pub-f7419ca433e9434bad2f9e89e252c205.r2.dev`
- R2 keys mirror repo paths: `data/<subject>/processed/images/...`
- `src/asset-base.js` routes images → R2, JSON files → same-origin.

## Current Progress
See `CONTEXT_WINDOW_EXPORT.md` for the latest state of markscheme completion and recent work.

## Key Files
| File | Purpose |
|------|---------|
| `src/tutoring/app.js` | Math/Tutoring bank logic |
| `src/tutoring/index.html` | Math/Tutoring UI |
| `src/biology/app.js` | Biology bank logic |
| `src/chemistry/app.js` | Chemistry bank logic |
| `src/physics/app.js` | Physics bank logic |
| `src/styles.css` | Shared styles |
| `data/tutoring/processed/questions.json` | 717 math questions |
| `data/tutoring/processed/markschemes.json` | KaTeX markschemes |

## Local Dev
```bash
python3 server.py
# → http://localhost:8080/
```

## R2 Upload (rclone — use this, not the REST script)
```bash
# Create rclone.conf temporarily (delete after use)
~/Downloads/rclone_bin/rclone-v1.74.1-osx-arm64/rclone copy ./data r2:aahl-assets/data \
  --config rclone.conf \
  --exclude "raw/**" \
  --include "*.png" --include "*.jpg" --include "*.pdf" \
  --transfers 32 --s3-upload-concurrency 8 --progress
```
rclone.conf format:
```ini
[r2]
type = s3
provider = Cloudflare
access_key_id = <Account API token access key>
secret_access_key = <secret>
endpoint = https://b958f16085766c52a302e26353ade3f1.r2.cloudflarestorage.com
```

## Markscheme Workflow
1. Write a Python `ms()` helper script to generate entries.
2. Run it → validates JSON → appends to `markschemes.json`.
3. Delete the script.
4. Commit + push.

### CRITICAL — KaTeX Delimiter Escaping
Always use **regular Python strings**, never raw strings, for `\(` and `\)` delimiters:

```python
# CORRECT
{"c": "\\(u_n = u_1 + (n-1)d\\)"}

# WRONG — produces \\( in browser, KaTeX fails
{"c": r"\\(u_n = u_1 + (n-1)d\\)"}
```

Raw strings are fine for LaTeX *inside* formulas (e.g. `r"\Rightarrow"`), but delimiters must be regular strings.

## Markscheme Table Format
Use `<table class='ms-table'>` for IB-style markscheme tables with KaTeX rendering.
