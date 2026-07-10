#!/bin/bash
# Auto-generate aidj/tracks.json from mp3 files in aidj/
# Extracts: artist, title (from filename "Artist - Title.mp3"), duration (ffprobe)

set -e
cd "$(dirname "$0")"
OUT="aidj/tracks.json"
TMPFILE=$(mktemp /tmp/tracks-json-XXXXXX)

# Collect mp3 files, sorted
FILES=$(find aidj -maxdepth 1 -name '*.mp3' -type f | sort)

if [ -z "$FILES" ]; then
  echo '[]' > "$OUT"
  echo "No mp3 files found, $OUT cleared"
  exit 0
fi

# Pass files via stdin to python
echo "$FILES" | python3 -c "
import json, subprocess, sys, os, re

files = [l.rstrip('\n') for l in sys.stdin if l.strip()]
tracks = []

for f in files:
    basename = os.path.splitext(os.path.basename(f))[0]

    # Parse 'Artist - Title.mp3'
    m = re.match(r'^(.+?)\s*-\s*(.+)$', basename)
    if m:
        artist = m.group(1).strip()
        title = m.group(2).strip()
    else:
        artist = 'Unknown'
        title = basename

    # Get duration via ffprobe
    duration_str = '?'
    try:
        res = subprocess.run(['ffprobe', '-v', 'quiet', '-show_format', f],
                           capture_output=True, text=True, timeout=10)
        for line in res.stdout.split('\n'):
            if line.startswith('duration='):
                dur = float(line.split('=', 1)[1])
                mins = int(dur // 60)
                secs = int(dur % 60)
                duration_str = f'{mins}:{secs:02d}'
                break
    except Exception:
        pass

    tracks.append({
        'title': title,
        'artist': artist,
        'url': f,
        'duration': duration_str,
        'bpm': None
    })

with open('$TMPFILE', 'w', encoding='utf-8') as f:
    json.dump(tracks, f, ensure_ascii=False, indent=2)

print(f'Generated {len(tracks)} tracks')
"

# Atomically replace
mv "$TMPFILE" "$OUT"

# Stage for commit
git add "$OUT" 2>/dev/null || true
