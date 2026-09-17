# AA HL Question Bank

IB Math AA HL question bank web app built from past papers + markschemes.

## Project Structure

- `data/raw/papers/`: AA HL paper PDFs
- `data/raw/markschemes/`: matching markscheme PDFs
- `data/processed/questions.json`: generated question metadata
- `data/processed/images/`: generated question + markscheme screenshots
- `src/`: frontend
- `scripts/`: ingestion / parsing scripts
- `server.py`: web app server

## Rebuild Data (when adding new papers)

```bash
cd "AA-HL-Question-Bank"
python3 -m pip install --target .deps pypdf pymupdf
PYTHONPATH=.deps python3 scripts/build_question_bank.py
PYTHONPATH=.deps python3 scripts/generate_question_images.py
```

## Run Web App Locally

```bash
python -m pip install -r requirements.txt
python server.py
```

Open `http://localhost:8080`.

Question metadata is served by Flask. Images and PDFs use the public R2 asset host by default, so a local checkout does not need the large binary archive.

## Asset Storage

- Default: images and PDFs load from the R2 host configured in `src/asset-base.js`.
- Two May 2017 Physics Paper 3 markschemes currently load from the app itself while their R2 copies are corrected.
- JSON files always load from this app (`/data/...`).
- To use locally generated images or PDFs, set the asset base to the local origin.

### Quick browser test

Open DevTools Console and run:

```js
setAssetBaseUrl(location.origin);
location.reload();
```

To return to the default R2 host:

```js
setAssetBaseUrl("");
location.reload();
```

You can select another asset host before app scripts:

```html
<script>window.ASSET_BASE_URL = "https://your-asset-domain.example.com";</script>
```

## Smoke Check

Run this before publishing changes:

```bash
python scripts/smoke_check.py
```

After Render deploys, check the live routes:

```bash
python scripts/smoke_check.py --base-url https://aa-hl-question-bank.onrender.com
```

## Deploy For Friends (No Code Needed For Them)

### Option A: Render (recommended)
1. Push this folder to GitHub.
2. Go to Render and create a new `Blueprint` service.
3. Select the repo; Render will use `render.yaml` + `Dockerfile`.
4. Deploy and share the URL with friends.

### Option B: Any Docker host

```bash
docker build -t aa-hl-bank .
docker run -p 8080:8080 aa-hl-bank
```
