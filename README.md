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
cd "AA-HL-Question-Bank"
python3 -m pip install -r requirements.txt
python3 server.py
```

Open `http://localhost:8080`.

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
