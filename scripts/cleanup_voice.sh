#!/bin/sh
set -eu
HOURS="${VOICE_RETENTION_HOURS:-24}"
MINS=$((HOURS * 60))
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
LIST="$(mktemp)"
trap 'rm -f "$LIST"' EXIT
: > "$LIST"
find /home/user1/.openclaw/media/inbound -maxdepth 1 -type f \( -iname '*.ogg' -o -iname '*.oga' -o -iname '*.opus' \) -mmin +"$MINS" -print >> "$LIST" 2>/dev/null || true
find /home/user1/.openclaw/workspace/media/inbound -maxdepth 1 -type f \( -iname '*.ogg' -o -iname '*.oga' -o -iname '*.opus' \) -mmin +"$MINS" -print >> "$LIST" 2>/dev/null || true
find /home/user1/.openclaw/agents -path '*/workspace/media/inbound/*' -type f \( -iname '*.ogg' -o -iname '*.oga' -o -iname '*.opus' \) -mmin +"$MINS" -print >> "$LIST" 2>/dev/null || true
COUNT=$(wc -l < "$LIST" | tr -d ' ')
if [ "$DRY" = 1 ]; then
  echo "dry_run=1 retention_hours=$HOURS candidates=$COUNT"
  sed 's/^/would_delete /' "$LIST"
  exit 0
fi
DELETED=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  if rm -f -- "$f"; then DELETED=$((DELETED + 1)); echo "deleted $f"; fi
done < "$LIST"
echo "retention_hours=$HOURS deleted=$DELETED"
