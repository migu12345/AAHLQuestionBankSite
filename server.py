from pathlib import Path
from flask import Flask, jsonify, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

app = Flask(__name__, static_folder=str(SRC_DIR), static_url_path="")


@app.get("/health")
def health():
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
