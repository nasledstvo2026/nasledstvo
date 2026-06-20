#!/usr/bin/env python3
"""
AI DJ — Sequential Mix Manager

Manages the current mix state and progressive mixing.
mix-current.json is polled by player/index.html for live updates.

Usage:
  python3 aidj-mix.py add <audio_file> [--bpm N] [--name "Track Name"]
  python3 aidj-mix.py clear
  python3 aidj-mix.py status
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
ENGINE = BASE_DIR / "aidj-engine.py"
CURRENT_MIX = BASE_DIR / "mix-current.json"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"


def load_mix() -> dict:
    if CURRENT_MIX.exists():
        try:
            return json.loads(CURRENT_MIX.read_text())
        except:
            pass
    return {"tracks": [], "url": None, "duration": 0, "total_bpm": 0, "mix_count": 0}


def save_mix(data: dict):
    CURRENT_MIX.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def add_track(filepath: str, name: str = None, bpm: float = None):
    mix = load_mix()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Detect BPM if not provided
    if bpm is None:
        result = subprocess.run(
            ["aubio", "tempo", filepath],
            capture_output=True, text=True, timeout=30
        )
        out = result.stdout.strip()
        if out:
            try:
                bpm = float(out.split()[-1])
            except:
                bpm = 120.0
        else:
            bpm = 120.0

    track_name = name or Path(filepath).name
    track_info = {"name": track_name, "bpm": round(bpm, 1)}

    if not mix["tracks"]:
        # First track — just copy as initial mix
        first_output = STATIC_DIR / f"aidj_mix_{ts}.mp3"
        import shutil
        shutil.copy2(filepath, first_output)

        mix["tracks"] = [track_info]
        mix["url"] = f"/aidj_mix_{ts}.mp3"
        mix["total_bpm"] = round(bpm, 1)
        mix["mix_count"] = 1
        mix["duration"] = get_duration(str(first_output))
        save_mix(mix)
        print(f"MIX_INIT|{first_output}|{track_name}|{bpm}")
        return

    # Sequential mix: current mix + new track
    current_mp3 = BASE_DIR / mix["url"].lstrip("/")
    if not current_mp3.exists():
        current_mp3 = list(STATIC_DIR.glob("aidj_mix_*.mp3"))
        if current_mp3:
            current_mp3 = sorted(current_mp3)[-1]
        else:
            print("NO_CURRENT_MIX")
            return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_output = STATIC_DIR / f"aidj_mix_{ts}.mp3"

    # Run engine: current mix + new track
    print(f"SEQ_MIX|{current_mp3}|{filepath} -> {new_output}", file=sys.stderr)

    result = subprocess.run(
        [sys.executable, str(ENGINE),
         str(current_mp3), filepath,
         "--output", str(new_output),
         "--crossfade", "15",
         "--json", "--verbose"],
        capture_output=True, text=True, timeout=120
    )

    output = result.stdout.strip()
    if result.returncode != 0 or not output:
        print(f"SEQ_ERROR|{result.stderr[:300]}")
        return

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        print(f"JSON_ERROR|{output[:200]}")
        return

    if data.get("status") != "ok":
        print(f"MIX_ERROR|{data.get('error', 'unknown')}")
        return

    # Update mix state
    mix["tracks"].append(track_info)
    mix["url"] = f"/{new_output.name}"
    mix["duration"] = data.get("duration", 0)
    mix["mix_count"] += 1
    # Average BPM
    bpm_sum = sum(t["bpm"] for t in mix["tracks"])
    mix["total_bpm"] = round(bpm_sum / len(mix["tracks"]), 1)
    save_mix(mix)

    print(f"MIX_UPDATED|{new_output.name}|{mix['mix_count']} треков|{mix['duration']}с|{mix['total_bpm']} BPM")


def get_duration(filepath: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries",
           "format=duration", "-of", "json", filepath]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        d = json.loads(result.stdout)
        return round(float(d["format"]["duration"]), 1)
    except:
        return 0.0


def cmd_clear():
    mix = {"tracks": [], "url": None, "duration": 0, "total_bpm": 0, "mix_count": 0}
    save_mix(mix)
    # Clean old mixes
    for f in STATIC_DIR.glob("aidj_mix_*.mp3"):
        f.unlink()
    print("MIX_CLEARED")


def cmd_status():
    mix = load_mix()
    if not mix["tracks"]:
        print("NO_MIX")
    else:
        print(f"TRACKS={mix['mix_count']}")
        print(f"DURATION={mix['duration']}s")
        print(f"BPM={mix['total_bpm']}")
        print(f"URL={mix['url']}")
        for t in mix["tracks"]:
            print(f"TRACK|{t['name']}|{t['bpm']} BPM")


def main():
    parser = argparse.ArgumentParser(description="AI DJ — Sequential Mix Manager")
    parser.add_argument("command", choices=["add", "clear", "status"])
    parser.add_argument("file", nargs="?", help="Audio file to add")
    parser.add_argument("--name", help="Track display name")
    parser.add_argument("--bpm", type=float, help="BPM override")

    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    if args.command == "add":
        if not args.file:
            print("MISSING_FILE")
            sys.exit(1)
        if not Path(args.file).exists():
            print("FILE_NOT_FOUND")
            sys.exit(1)
        add_track(args.file, args.name, args.bpm)
    elif args.command == "clear":
        cmd_clear()
    elif args.command == "status":
        cmd_status()


if __name__ == "__main__":
    main()
