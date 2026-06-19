#!/bin/bash
# Инкрементальный бэкап: только изменённые файлы с Timeweb + memory + canvas
# Запуск: backup-incremental.sh
# retention: последние 7 дней

set -euo pipefail

TS=$(date +%Y-%m-%d_%H%M%S)
DIR="/home/user1/.openclaw/workspace/backup/incremental/${TS}"
mkdir -p "$DIR"

echo "=== Incremental backup ${TS} ==="

HOST="timeweb"

# 1. Timeweb — скачиваем только HTML-файлы
echo "[1/3] Timeweb (changed files)..."
mkdir -p "$DIR/timeweb"
scp "$HOST:~/public_html/"*.html \
  "$HOST:~/public_html/"*.css \
  "$HOST:~/public_html/"*.json \
  "$DIR/timeweb/" 2>/dev/null || echo "  WARNING: Timeweb SCP failed"

# 2. Memory файлы
echo "[2/3] Memory..."
cp -r /home/user1/.openclaw/workspace/memory "$DIR/memory" 2>/dev/null || true

# 3. Canvas
echo "[3/3] Canvas..."
cp /home/user1/.openclaw/canvas/*.html "$DIR/" 2>/dev/null || true

# Размер
SIZE=$(du -sh "$DIR" | cut -f1)
echo "=== Done: ${DIR} (${SIZE}) ==="

# Retention: последние 7 дней
find /home/user1/.openclaw/workspace/backup/incremental/ \
  -maxdepth 1 -type d -mtime +7 \
  ! -path "/home/user1/.openclaw/workspace/backup/incremental/" \
  -exec rm -rf {} \; 2>/dev/null || true

echo "OK"
