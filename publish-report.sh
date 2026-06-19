#!/bin/bash
# Publish report: upload to Timeweb + update timestamp on index pages
# Usage: publish-report.sh <local-file> <remote-filename>
# Example: publish-report.sh /tmp/report-katya.html report-katya.html

set -e

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <local-file> <remote-filename>"
  exit 1
fi

# Source credentials
[ -f "$(dirname "$0")/.env.timeweb" ] && . "$(dirname "$0")/.env.timeweb"

LOCAL="$1"
REMOTE="$2"
HOST="${TIMEWEB_HOST:-timeweb}"
TIMESTAMP="$(TZ=Europe/Moscow date '+%d.%m.%Y %H:%M')"

# Upload report
scp "$LOCAL" "$HOST:~/public_html/$REMOTE"
echo "Uploaded: $REMOTE"

# Update timestamp on nasledstvo.html
TMPFILE=$(mktemp)
scp "$HOST:~/public_html/nasledstvo.html" "$TMPFILE" 2>/dev/null || true
if [ -s "$TMPFILE" ]; then
  python3 -c "
import re, sys
with open('$TMPFILE', 'r') as f:
    c = f.read()
report = '$REMOTE'
if 'katya' in report: eid = 'ud-katya'
elif 'lena' in report: eid = 'ud-lena'
elif 'danil' in report: eid = 'ud-danil'
else: sys.exit(0)
c = re.sub(r'(<span id=\"' + eid + r'\">)[^<]*(</span>)', r'\g<1>$TIMESTAMP\2', c)
with open('$TMPFILE', 'w') as f:
    f.write(c)
" 2>/dev/null || true
  scp "$TMPFILE" "$HOST:~/public_html/nasledstvo.html" 2>/dev/null || true
  echo "Timestamp updated on nasledstvo.html"
fi
rm -f "$TMPFILE"

echo "Done: $REMOTE published at $TIMESTAMP"
