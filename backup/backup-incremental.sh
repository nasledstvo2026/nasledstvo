#!/bin/bash
# Инкрементальный бэкап: только изменённые файлы memory + canvas
# Timeweb отключён (перешли на GitHub Pages 20.06.2026)
# Запуск: backup-incremental.sh
# retention: последние 7 дней

set -euo pipefail

TS=$(date +%Y-%m-%d_%H%M%S)
DIR="/home/user1/.openclaw/workspace/backup/incremental/${TS}"
mkdir -p "$DIR"

echo "=== Incremental backup ${TS} ==="

# 1. Memory файлы
echo "[1/2] Memory..."
cp -r /home/user1/.openclaw/workspace/memory "$DIR/memory" 2>/dev/null || true

# 2. Canvas
echo "[2/2] Canvas..."
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
