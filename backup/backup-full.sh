#!/bin/bash
# Полный бэкап: workspace + canvas + Timeweb → backup/full/
# Запуск: backup-full.sh
# retention: последние 4 недели

set -euo pipefail

TS=$(date +%Y-%m-%d_%H%M%S)
DIR="/home/user1/.openclaw/workspace/backup/full/${TS}"
mkdir -p "$DIR"

echo "=== Full backup ${TS} ==="

# 1. Workspace (без node_modules, .git, backup)
echo "[1/3] Workspace..."
tar czf "$DIR/workspace.tar.gz" \
  --exclude="node_modules" \
  --exclude=".git" \
  --exclude="backup" \
  -C /home/user1/.openclaw/workspace \
  . 2>/dev/null || true

# 2. Canvas
echo "[2/3] Canvas..."
tar czf "$DIR/canvas.tar.gz" \
  --exclude=".git" \
  -C /home/user1/.openclaw/canvas \
  . 2>/dev/null || true

# 3. Timeweb (все файлы с сервера)
echo "[3/3] Timeweb..."
mkdir -p "$DIR/timeweb"
HOST="timeweb"
scp "$HOST:~/public_html/"*.html \
  "$DIR/timeweb/" 2>/dev/null || echo "  WARNING: Timeweb SCP failed"

# Размер
SIZE=$(du -sh "$DIR" | cut -f1)
echo "=== Done: ${DIR} (${SIZE}) ==="

# Retention: 2 календарные недели
find /home/user1/.openclaw/workspace/backup/full/ \
  -maxdepth 1 -type d -mtime +14 \
  ! -path "/home/user1/.openclaw/workspace/backup/full/" \
  -exec rm -rf {} \; 2>/dev/null || true

echo "OK"
