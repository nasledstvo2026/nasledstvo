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

# Commit & push
git add -A
git commit -m "Report: $REMOTE — $TIMESTAMP" 2>/dev/null || echo "Nothing new to commit"
git push 2>&1

echo "Done: $REMOTE published at $TIMESTAMP"
echo "   Site: https://nasledstvo2026.github.io/nasledstvo/"
