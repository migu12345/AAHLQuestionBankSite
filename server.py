from pathlib import Path
from flask import Flask, jsonify, send_from_directory
import json
import re

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
QUESTIONS_FILE = PROCESSED_DIR / "questions.json"
JSON_ASSET_PATTERN = re.compile(r"assetFetch\(\s*['\"](/data/[^'\"]+\.json)['\"]")


def required_json_files():
    paths = set()
    for script in SRC_DIR.rglob("*.js"):
        paths.update(JSON_ASSET_PATTERN.findall(script.read_text(encoding="utf-8")))
    return tuple(sorted(paths))


REQUIRED_JSON_FILES = required_json_files()

app = Flask(__name__, static_folder=str(SRC_DIR), static_url_path="")


@app.get("/health")
def health():
    missing = [path for path in REQUIRED_JSON_FILES if not (BASE_DIR / path.lstrip("/")).is_file()]
    if missing:
        return jsonify({"status": "error", "missing_data": missing}), 503
    return jsonify({"status": "ok"})


@app.get("/")
def root():
    return send_from_directory(SRC_DIR, "index.html")


@app.get("/src/<path:filename>")
def src_files(filename: str):
    return send_from_directory(SRC_DIR, filename)


@app.get("/data/processed/<path:filename>")
def processed_files(filename: str):
    return send_from_directory(PROCESSED_DIR, filename)

@app.get("/data/<path:filename>")
def data_files(filename: str):
    return send_from_directory(DATA_DIR, filename)


@app.get("/admin/topic-audit")
def topic_audit():
    if not QUESTIONS_FILE.exists():
        return jsonify({"error": "questions file not found"}), 404

    payload = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])
    flagged = []
    for q in questions:
        conf = float(q.get("topic_confidence", 0.0) or 0.0)
        reasons = q.get("topic_reason", [])
        if conf < 0.7:
            flagged.append(
                {
                    "id": q.get("id"),
                    "paper": q.get("paper"),
                    "topic": q.get("topic"),
                    "subtopic": q.get("subtopic"),
                    "confidence": conf,
                    "reasons": reasons,
                    "title": q.get("title"),
                }
            )

    return jsonify(
        {
            "total_questions": len(questions),
            "flagged_low_confidence": len(flagged),
            "items": flagged,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
