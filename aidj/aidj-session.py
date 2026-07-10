#!/usr/bin/env python3
"""
AI DJ — Session Manager (updated for sequential mixing)

Usage:
  python3 aidj-session.py start              # Begin new session (clears old mix)
  python3 aidj-session.py add-track <file>    # Add track to sequential mix
  python3 aidj-session.py cancel             # Cancel session
  python3 aidj-session.py status             # Get current session state
  python3 aidj-session.py done               # Finalize (session stays, player shows final mix)
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MIX_MGR = BASE_DIR / "aidj-mix.py"
SESSION_FILE = BASE_DIR / "session.json"
UPLOADS_DIR = BASE_DIR / "static" / "uploads"


def load_session():
    if SESSION_FILE.exists():
        try:
            return json.loads(SESSION_FILE.read_text())
        except:
            pass
    return None


def save_session(data: dict):
    SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_start():
    # Clear old mix and session
    subprocess.run([sys.executable, str(MIX_MGR), "clear"],
                   capture_output=True, timeout=30)
    data = {
        "state": "collecting",
        "track_count": 0,
        "created_at": __import__("datetime").datetime.now().isoformat()
    }
    save_session(data)
    print("SESSION_STARTED")


def cmd_add_track(filepath: str):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    fpath = Path(filepath)
    if not fpath.exists():
        print("FILE_NOT_FOUND")
        return

    # Copy to uploads
    ts = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = fpath.suffix or ".mp3"
    dest = UPLOADS_DIR / f"track_{ts}_{fpath.stem}{ext}"
    import shutil
    shutil.copy2(str(fpath), str(dest))

    # Add to sequential mix
    result = subprocess.run(
        [sys.executable, str(MIX_MGR), "add", str(dest)],
        capture_output=True, text=True, timeout=180
    )
    output = result.stdout.strip()

    session = load_session()
    if session:
        session["track_count"] = session.get("track_count", 0) + 1
        session["last_track"] = str(dest)
        save_session(session)

    print(output)


def cmd_cancel():
    subprocess.run([sys.executable, str(MIX_MGR), "clear"],
                   capture_output=True, timeout=30)
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    # Clean uploads
    if UPLOADS_DIR.exists():
        import shutil
        shutil.rmtree(UPLOADS_DIR, ignore_errors=True)
    print("SESSION_CANCELLED")


def cmd_done():
    session = load_session()
    if not session:
        print("NO_SESSION")
        return
    session["state"] = "done"
    save_session(session)
    print("SESSION_DONE")


def cmd_status():
    session = load_session()
    if not session:
        print("NO_SESSION")
        return

    print(f"STATE={session.get('state', 'unknown')}")
    print(f"TRACKS={session.get('track_count', 0)}")

    # Get mix status
    result = subprocess.run(
        [sys.executable, str(MIX_MGR), "status"],
        capture_output=True, text=True, timeout=10
    )
    print(result.stdout.strip())


def main():
    if len(sys.argv) < 2:
        print("Usage: aidj-session.py <start|add-track <file>|cancel|done|status>")
        sys.exit(1)

    cmd = sys.argv[1]
    handlers = {
        "start": lambda: cmd_start(),
        "cancel": lambda: cmd_cancel(),
        "done": lambda: cmd_done(),
        "status": lambda: cmd_status(),
    }

    if cmd == "add-track":
        if len(sys.argv) < 3:
            print("MISSING_FILE")
            sys.exit(1)
        cmd_add_track(sys.argv[2])
    elif cmd in handlers:
        handlers[cmd]()
    else:
        print(f"UNKNOWN: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
