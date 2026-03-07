#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_JSON = ROOT / "data" / "physics" / "processed" / "questions.json"
Q_IMG_DIR = ROOT / "data" / "physics" / "processed" / "images" / "questions"
MS_IMG_DIR = ROOT / "data" / "physics" / "processed" / "images" / "markschemes"
TOPIC_MAP = ROOT / "data" / "physics" / "topic-map.json"
REL_BASE = ROOT / "data" / "physics" / "processed"


TOPIC_RULES = [
    (
        "Space, time and motion",
        [
            ("Kinematics", ["velocity", "acceleration", "displacement", "distance", "projectile", "free fall"]),
            ("Forces and momentum", ["force", "newton", "momentum", "impulse", "collision", "equilibrium", "friction"]),
            ("Work, energy and power", ["work done", "kinetic energy", "potential energy", "power", "efficiency"]),
            ("Circular and rotational motion", ["centripetal", "angular", "torque", "moment of inertia", "rotation"]),
            (
                "A5 relativity",
                [
                    "relativity",
                    "special relativity",
                    "frame of reference",
                    "time dilation",
                    "length contraction",
                    "proper time",
                    "proper length",
                    "lorentz factor",
                    "relativistic",
                    "speed of light",
                    "moving in the positive x direction",
                    "moving in the negative x direction",
                ],
            ),
        ],
    ),
    (
        "The particulate nature of matter",
        [
            ("Thermal physics", ["temperature", "thermal", "internal energy", "specific heat", "latent heat"]),
            ("Gas laws", ["ideal gas", "pressure", "volume", "boyle", "charles", "avogadro"]),
            ("Electric circuits", ["current", "voltage", "resistance", "emf", "circuit", "kirchhoff", "ohm"]),
            ("Material properties", ["young modulus", "stress", "strain", "density"]),
        ],
    ),
    (
        "Wave behaviour",
        [
            ("Wave properties", ["wavelength", "frequency", "amplitude", "period", "speed of wave"]),
            ("Superposition and standing waves", ["interference", "diffraction", "standing wave", "node", "antinode"]),
            ("Optics", ["refraction", "reflection", "snell", "critical angle", "lens", "focal"]),
            ("Doppler and sound", ["doppler", "sound", "intensity", "decibel"]),
        ],
    ),
    (
        "Fields",
        [
            ("Gravitational fields", ["gravitational field", "g =", "orbit", "escape speed"]),
            ("Electric and magnetic fields", ["electric field", "potential difference", "magnetic field", "lorentz", "flux"]),
            ("Electromagnetic induction", ["induction", "faraday", "lenz", "alternating current", "transformer"]),
            ("Capacitance", ["capacitor", "capacitance", "dielectric", "time constant"]),
        ],
    ),
    (
        "Nuclear and quantum physics",
        [
            ("Radioactivity", ["half life", "decay", "alpha", "beta", "gamma", "activity"]),
            ("Nuclear reactions", ["fission", "fusion", "binding energy", "mass defect"]),
            ("Quantum/modern physics", ["photon", "de broglie", "photoelectric", "quantum", "energy level"]),
        ],
    ),
]


def normalize(text: str) -> str:
    t = text.lower().replace("-", " ")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def image_sort_key(path: Path) -> tuple[int, str]:
    name = path.stem
    m = re.search(r"_p(\d+)$", name)
    if m:
        return (int(m.group(1)), name)
    return (0, name)


def classify_topic(question_text: str) -> tuple[str, str, float]:
    text = normalize(question_text or "")
    if not text:
        return ("Unsorted", "Unsorted", 0.0)

    best_topic = "Unsorted"
    best_sub = "Unsorted"
    best_score = 0

    for topic, subgroups in TOPIC_RULES:
        for subtopic, keywords in subgroups:
            score = 0
            for kw in keywords:
                if kw in text:
                    score += 1
            if score > best_score:
                best_score = score
                best_topic = topic
                best_sub = subtopic

    confidence = min(0.95, 0.25 + 0.18 * best_score) if best_score > 0 else 0.05
    return (best_topic, best_sub, confidence)


def to_rel(paths: list[Path]) -> list[str]:
    return [p.relative_to(REL_BASE).as_posix() for p in paths]


def existing_rels_if_valid(rels: list[str]) -> list[str]:
    if not rels:
        return []
    valid: list[str] = []
    for rel in rels:
        if (REL_BASE / rel).exists():
            valid.append(rel)
    return valid


def main() -> None:
    payload = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    questions = payload.get("questions", [])

    with_q_images = 0
    with_ms_images = 0

    for q in questions:
        qid = q.get("id", "")
        existing_q = existing_rels_if_valid(list(q.get("question_image_paths") or []))
        existing_ms = existing_rels_if_valid(list(q.get("markscheme_image_paths") or []))

        if existing_q:
            q_rel = existing_q
        else:
            exact_q = Q_IMG_DIR / f"{qid}.png"
            if exact_q.exists():
                q_paths = [exact_q]
            else:
                q_paths = sorted(Q_IMG_DIR.glob(f"{qid}*.png"), key=image_sort_key)
            q_rel = to_rel(q_paths)

        if existing_ms:
            ms_rel = existing_ms
        else:
            exact_ms = MS_IMG_DIR / f"{qid}.png"
            if exact_ms.exists():
                ms_paths = [exact_ms]
            else:
                ms_paths = sorted(MS_IMG_DIR.glob(f"{qid}*.png"), key=image_sort_key)
            ms_rel = to_rel(ms_paths)

        if q_rel:
            with_q_images += 1
        if ms_rel:
            with_ms_images += 1

        topic, subtopic, conf = classify_topic(q.get("question_text", ""))
        q["topic"] = topic
        q["subtopic"] = subtopic
        q["topic_confidence"] = conf
        q["topic_reason"] = ["physics keyword scorer v2"]

        q["question_image_paths"] = q_rel
        q["markscheme_image_paths"] = ms_rel
        # Compatibility aliases for any future UI readers.
        q["question_images"] = q_rel
        q["markscheme_images"] = ms_rel
        q["has_markscheme"] = bool(ms_rel)

    QUESTIONS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    topics = {}
    for q in questions:
        topic = q.get("topic", "Unsorted")
        sub = q.get("subtopic", "Unsorted")
        topics.setdefault(topic, set()).add(sub)

    topic_payload = {
        "topics": [
            {"name": t, "subtopics": sorted(s)}
            for t, s in sorted(topics.items(), key=lambda item: item[0])
        ]
    }
    TOPIC_MAP.write_text(json.dumps(topic_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Updated {len(questions)} questions")
    print(f"Questions with images: {with_q_images}/{len(questions)}")
    print(f"Questions with markscheme images: {with_ms_images}/{len(questions)}")


if __name__ == "__main__":
    main()
