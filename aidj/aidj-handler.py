#!/usr/bin/env python3
"""
AI DJ — Handler for OpenClaw /dj command.

This script is called by OpenClaw when user sends /dj.
It orchestrates the mixing flow and returns a result message.

Usage: python3 aidj-handler.py <track_a> <track_b>
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENGINE_SCRIPT = BASE_DIR / "aidj-engine.py"
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "output"
MIXES_JSON = BASE_DIR / "mixes.json"

# Web server
HOST = "176.123.162.12"  # VPS IP
PORT = 8765
GITHUB_PAGE = "https://nasledstvo2026.github.io/nasledstvo/aidj.html"


def ensure_dirs():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def mix_tracks(track_a: str, track_b: str) -> dict:
    """Run engine and get result."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_name = f"aidj_mix_{timestamp}.mp3"
    output_path = str(STATIC_DIR / output_name)

    cmd = [
        sys.executable, str(ENGINE_SCRIPT),
        track_a, track_b,
        "--output", output_path,
        "--crossfade", "15",
        "--json",
        "--verbose"
    ]

    print(f"[AI DJ Handler] Running engine...", file=__import__('sys').stderr)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        return {"status": "error", "error": result.stderr[:500]}

    try:
        data = json.loads(result.stdout.strip())
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"JSON parse: {e}"}

    if data.get("status") == "ok":
        data["url"] = f"http://{HOST}:{PORT}/{output_name}"
        data["filename"] = output_name

        # Save to mixes history
        save_mix_record(data)

    return data


def save_mix_record(data: dict):
    """Append mix record to mixes.json."""
    records = []
    if MIXES_JSON.exists():
        try:
            records = json.loads(MIXES_JSON.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            records = []

    record = {
        "timestamp": datetime.now().isoformat(),
        "bpm_a": data.get("bpm_a"),
        "bpm_b": data.get("bpm_b"),
        "duration": data.get("duration"),
        "filename": data.get("filename"),
        "url": data.get("url")
    }
    records.insert(0, record)  # newest first
    records = records[:50]  # keep last 50

    MIXES_JSON.write_text(json.dumps(records, ensure_ascii=False, indent=2))


def format_message(result: dict) -> str:
    """Format result for Telegram message."""
    if result.get("status") != "ok":
        return f"Ошибка сведения: {result.get('error', 'неизвестная')}"

    lines = [
        f"🎧 Микс готов",
        f"",
        f"A: {result.get('bpm_a', '?')} BPM | {result.get('key_a', '?')} ({result.get('camelot_a', '?')})",
        f"B: {result.get('bpm_b', '?')} BPM | {result.get('key_b', '?')} ({result.get('camelot_b', '?')})",
        f"Гармония: {result.get('harmonic_label', '?')}",
        f"Длительность: {result.get('duration', '?')}с",
        f"Crossfade: {result.get('crossfade', 15)}с",
        f"",
        f"🔗 {result.get('url', 'N/A')}",
        f"",
        f"🌐 {GITHUB_PAGE}"
    ]
    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("Usage: aidj-handler.py <track_a> <track_b>")
        sys.exit(1)

    track_a = sys.argv[1]
    track_b = sys.argv[2]

    if not os.path.exists(track_a):
        print(f"File not found: {track_a}")
        sys.exit(1)
    if not os.path.exists(track_b):
        print(f"File not found: {track_b}")
        sys.exit(1)

    ensure_dirs()
    result = mix_tracks(track_a, track_b)
    message = format_message(result)

    # Output the message for OpenClaw to deliver
    print(message)

    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
