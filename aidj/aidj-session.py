#!/usr/bin/env python3
"""
AI DJ — Session Manager for /dj command

Stores session state in aidj/session.json between messages.
One session at a time.

Usage:
  python3 aidj-session.py start              # Begin new session
  python3 aidj-session.py set-track <file>   # Save track for current session
  python3 aidj-session.py status             # Get current session state
  python3 aidj-session.py clear              # Clear session
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

SESSION_FILE = Path(__file__).resolve().parent / "session.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"


def ensure_dirs():
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def load_session():
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, Exception):
            pass
    return None


def save_session(data: dict):
    SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def clear_session():
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    # Clean old uploads
    if UPLOADS_DIR.exists():
        import shutil
        shutil.rmtree(UPLOADS_DIR, ignore_errors=True)


def cmd_start():
    if load_session():
        print("SESSION_ALREADY_ACTIVE")
        return
    data = {
        "state": "awaiting_a",
        "track_a": None,
        "track_b": None,
        "created_at": datetime.now().isoformat()
    }
    save_session(data)
    print("SESSION_STARTED")


def cmd_set_track(filepath: str):
    ensure_dirs()
    session = load_session()
    if not session:
        print("NO_SESSION")
        return

    fpath = Path(filepath)
    if not fpath.exists():
        print("FILE_NOT_FOUND")
        return

    # Copy to uploads
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = fpath.suffix or ".mp3"
    dest = UPLOADS_DIR / f"track_{ts}_{session['state']}{ext}"
    import shutil
    shutil.copy2(str(fpath), str(dest))

    if session["state"] == "awaiting_a":
        session["track_a"] = str(dest)
        session["state"] = "awaiting_b"
        save_session(session)
        print(f"NEED_TRACK_B|{dest}")
    elif session["state"] == "awaiting_b":
        session["track_b"] = str(dest)
        session["state"] = "ready"
        save_session(session)
        print(f"READY|{dest}")
    else:
        print("SESSION_COMPLETE")


def cmd_status():
    session = load_session()
    if not session:
        print("NO_SESSION")
        return
    print(f"STATE={session['state']}")
    print(f"TRACK_A={session.get('track_a', 'none')}")
    print(f"TRACK_B={session.get('track_b', 'none')}")
    if session["state"] == "ready":
        print("IS_READY=1")
    else:
        print("IS_READY=0")


def cmd_clear():
    clear_session()
    print("SESSION_CLEARED")


def main():
    if len(sys.argv) < 2:
        print("Usage: aidj-session.py <start|set-track <file>|status|clear>")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        cmd_start()
    elif command == "set-track":
        if len(sys.argv) < 3:
            print("MISSING_FILE")
            sys.exit(1)
        cmd_set_track(sys.argv[2])
    elif command == "status":
        cmd_status()
    elif command == "clear":
        cmd_clear()
    else:
        print(f"UNKNOWN_COMMAND: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
