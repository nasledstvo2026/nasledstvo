#!/bin/bash
# Upload an HTML file to Timeweb hosting (nasledstvo.net.ru)
# Usage: upload-to-timeweb.sh <local-file> <remote-filename>
# Example: upload-to-timeweb.sh /tmp/report.html report-katya.html

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "Usage: $0 <local-file> <remote-filename>"
  exit 1
fi

# Source credentials
[ -f "$(dirname "$0")/.env.timeweb" ] && . "$(dirname "$0")/.env.timeweb"

LOCAL="$1"
REMOTE="$2"
HOST="${TIMEWEB_HOST:-timeweb}"
WEBROOT="${TIMEWEB_WEBROOT:-~/public_html}"

scp "$LOCAL" "$HOST:$WEBROOT/$REMOTE"
echo "Uploaded: $LOCAL -> $REMOTE"
