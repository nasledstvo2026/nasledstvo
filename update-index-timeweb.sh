#!/bin/bash
# Update nasledstvo.html on Timeweb with fresh "updated" timestamps for a given report
# Usage: update-index-timeweb.sh <report-filename> <timestamp>
# Example: update-index-timeweb.sh report-katya.html "17.06.2026 12:44"

REPORT="$1"
TIMESTAMP="$2"

# Source credentials
[ -f "$(dirname "$0")/.env.timeweb" ] && . "$(dirname "$0")/.env.timeweb"

HOST="${TIMEWEB_HOST:-timeweb}"

if [ -z "$REPORT" ] || [ -z "$TIMESTAMP" ]; then
  echo "Usage: $0 <report-filename> <timestamp>"
  exit 1
fi

# Map report filename to span id
case "$REPORT" in
  report-katya.html)   ID="ud-katya" ;;
  report-lena.html)    ID="ud-lena" ;;
  report-danil.html)   ID="ud-danil" ;;
  report-danil-thu.html) ID="ud-danil-thu" ;;
  *)
    echo "Unknown report: $REPORT"
    exit 1
    ;;
esac

# Download nasledstvo.html, patch the span, upload back
TMPFILE=$(mktemp)
ssh "$HOST" "cat ~/public_html/nasledstvo.html" > "$TMPFILE"

python3 -c "
import sys, re
with open('$TMPFILE', 'r') as f:
    content = f.read()
content = re.sub(
    r'(<span id=\"$ID\">)[^<]*(</span>)',
    r'\g<1>$TIMESTAMP\g<2>',
    content
)
with open('$TMPFILE', 'w') as f:
    f.write(content)
"

scp "$TMPFILE" "$HOST:~/public_html/nasledstvo.html"
rm "$TMPFILE"
echo "Updated nasledstvo.html: $REPORT ($ID) -> $TIMESTAMP"
