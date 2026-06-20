#!/bin/bash
# Update nasledstvo.html timestamp and push to GitHub Pages
# Usage: update-index-github.sh <report-filename> <timestamp>
# Example: update-index-github.sh report-lena.html "17.06.2026 12:44"

set -e

REPORT="$1"
TIMESTAMP="$2"
REPO_DIR="/home/user1/.openclaw/workspace"

if [ -z "$REPORT" ] || [ -z "$TIMESTAMP" ]; then
  echo "Usage: $0 <report-filename> <timestamp>"
  exit 1
fi

cd "$REPO_DIR"

case "$REPORT" in
  report-lena.html)    ID="ud-lena" ;;
  report-danil.html)   ID="ud-danil" ;;
  report-danil-thu.html) ID="ud-danil-thu" ;;
  *)
    echo "Unknown report: $REPORT"
    exit 1
    ;;
esac

python3 -c "
import sys, re
with open('nasledstvo.html', 'r') as f:
    content = f.read()
content = re.sub(
    r'(<span id=\"$ID\">)[^<]*(</span>)',
    r'\g<1>$TIMESTAMP\g<2>',
    content
)
with open('nasledstvo.html', 'w') as f:
    f.write(content)
"

git add nasledstvo.html
git commit -m "Update: $REPORT timestamp -> $TIMESTAMP" 2>/dev/null || true
git push

echo "Updated nasledstvo.html: $REPORT ($ID) -> $TIMESTAMP"
