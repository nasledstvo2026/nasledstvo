#!/bin/bash
# Query driver: runs a list of queries via bsearch.sh with pacing, saves to /tmp/rsrch/q${BATCH}_${i}.txt
mkdir -p /tmp/rsrch
B="${BATCH:-m}"
i=0
while IFS= read -r q; do
  [ -z "$q" ] && continue
  i=$((i+1))
  f="/tmp/rsrch/q${B}_${i}.txt"
  echo "### QUERY: $q" > "$f"
  ./bsearch.sh "$q" 6 >> "$f" 2>&1
  echo "[saved $f]"
  sleep 25
done
echo DONE_$B
