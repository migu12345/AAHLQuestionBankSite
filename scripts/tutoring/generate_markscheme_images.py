#!/usr/bin/env python3
"""Render tutoring worked markschemes into SVG image cards."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from textwrap import wrap

ROOT = Path(__file__).resolve().parents[2]
MARKSCHEME_JSON = ROOT / "data" / "tutoring" / "processed" / "markschemes.json"
OUT_DIR = ROOT / "data" / "tutoring" / "processed" / "images" / "markschemes"


def render_svg(title: str, text: str) -> str:
    wrapped: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            wrapped.append("")
            continue
        chunks = wrap(line, width=95, break_long_words=False, break_on_hyphens=False)
        wrapped.extend(chunks if chunks else [""])

    line_height = 30
    top_pad = 120
    bottom_pad = 60
    height = top_pad + (max(len(wrapped), 1) * line_height) + bottom_pad
    width = 1400

    y = 160
    lines_svg = []
    for line in wrapped:
        content = escape(line) if line else " "
        is_part = line.startswith("Part (")
        is_method = line.startswith("METHOD ")
        looks_math = any(token in line for token in ["=", "^", "sqrt", "∫", "d/dx", "u_n", "S_n", "f^(-1)", "log", "=>", "<=>", "±"])
        weight = "700" if (is_part or is_method) else "500"
        fill = "#1d2f57" if (is_part or is_method) else "#1f2a44"
        font_family = "Cambria Math, STIX Two Math, Times New Roman, serif" if looks_math else "Arial, Helvetica, sans-serif"
        lines_svg.append(
            f'<text x="70" y="{y}" font-family="{font_family}" '
            f'font-size="28" font-weight="{weight}" fill="{fill}">{content}</text>'
        )
        y += line_height

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect x="20" y="20" width="{width-40}" height="{height-40}" rx="18" ry="18" fill="#f5f7fb" stroke="#c6cfdf" stroke-width="2"/>
  <rect x="20" y="20" width="{width-40}" height="54" rx="18" ry="18" fill="#e7eef9" stroke="#c6cfdf" stroke-width="2"/>
  <text x="50" y="57" font-family="Arial, Helvetica, sans-serif" font-size="36" font-weight="700" fill="#213a6a">Markscheme answer</text>
  <text x="70" y="110" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="700" fill="#243451">{escape(title)}</text>
  {''.join(lines_svg)}
</svg>"""
    return svg


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.loads(MARKSCHEME_JSON.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    for q in questions:
        qid = str(q.get("id", ""))
        title = str(q.get("title", "Question"))
        text = str(q.get("worked_solution_text", "No markscheme available."))
        out_file = OUT_DIR / f"{qid}.svg"
        out_file.write_text(render_svg(title, text), encoding="utf-8")
        q["markscheme_image_paths"] = [f"images/markschemes/{qid}.svg"]

    MARKSCHEME_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Rendered {len(questions)} markscheme image cards to {OUT_DIR}")


if __name__ == "__main__":
    main()
