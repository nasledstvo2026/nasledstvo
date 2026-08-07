#!/bin/bash
cd /home/user1/.openclaw/workspace/research
n=2
for b in queries_batch2.txt queries_batch3.txt queries_batch4.txt queries_batch5.txt; do
  echo "=== RUNNING $b ==="
  BATCH=$n bash run_queries.sh < "$b"
  echo "=== DONE $b ==="
  n=$((n+1))
  sleep 30
done
echo ALL_BATCHES_DONE
