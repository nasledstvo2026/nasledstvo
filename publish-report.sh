#!/bin/bash
# Publish report: copy to repo + git commit & push to GitHub Pages
# Usage: publish-report.sh <local-file> <remote-filename>
# Example: publish-report.sh /tmp/report-lena.html report-lena.html

set -e

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <local-file> <remote-filename>"
  exit 1
fi

LOCAL="$1"
REMOTE="$2"
REPO_DIR="/home/user1/.openclaw/workspace"
TIMESTAMP="$(TZ=Europe/Moscow date '+%d.%m.%Y %H:%M')"

cd "$REPO_DIR"

# Copy report to workspace
cp "$LOCAL" "$REMOTE"

# Map to element id for nasledstvo.html
case "$REMOTE" in
  report-lena.html)    ID="ud-lena" ;;
  report-danil.html)   ID="ud-danil" ;;
  report-danil-thu.html) ID="ud-danil-thu" ;;
  *) ID="" ;;
esac

# Update timestamp on nasledstvo.html
if [ -n "$ID" ]; then
  python3 -c "
import re
with open('nasledstvo.html', 'r') as f:
    c = f.read()
c = re.sub(r'(<span id=\"$ID\">)[^<]*(</span>)', r'\g<1>$TIMESTAMP\g<2>', c)
with open('nasledstvo.html', 'w') as f:
    f.write(c)
" 2>/dev/null || true
  echo "Timestamp updated on nasledstvo.html ($ID)"
fi

# Commit & push
git add -A
git commit -m "Report: $REMOTE — $TIMESTAMP" 2>/dev/null || echo "Nothing new to commit"
git push 2>&1

echo "Done: $REMOTE published at $TIMESTAMP"
echo "   Site: https://nasledstvo2026.github.io/nasledstvo/"
