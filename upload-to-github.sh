#!/bin/bash
# Upload file to the GitHub Pages repo (replaces old upload-to-timeweb.sh)
# Usage: upload-to-github.sh <local-file> <remote-filename>
# Example: upload-to-github.sh ./report.html report-katya.html

set -e

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <local-file> <remote-filename>"
  exit 1
fi

LOCAL="$1"
REMOTE="$2"
REPO_DIR="/home/user1/.openclaw/workspace"

cd "$REPO_DIR"

cp "$LOCAL" "$REMOTE"
git add -A
git commit -m "Upload: $REMOTE" 2>/dev/null || true
git push 2>&1

echo "Uploaded: $REMOTE -> https://nasledstvo2026.github.io/nasledstvo/$REMOTE"
