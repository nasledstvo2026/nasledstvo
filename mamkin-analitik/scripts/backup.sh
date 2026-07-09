#!/bin/bash
# =============================================================================
# backup.sh — Бэкап данных сессий «Мамкин аналитик»
# =============================================================================
# Создаёт архив с сессионными данными и history.json.
# Рекомендуется запускать ежедневно через cron.
#
# Использование:
#   ./scripts/backup.sh [backup_dir]
#
# По умолчанию бэкап сохраняется в /var/backups/mamkin-analitik/
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${1:-/var/backups/mamkin-analitik}"
SESSION_DIR="${SESSION_STORAGE_PATH:-/var/mamkin-analitik/sessions/}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/mamkin-analitik-backup-$TIMESTAMP.tar.gz"

echo "💾 Бэкап Мамкин аналитик..."
echo "📂 Источник сессий: $SESSION_DIR"
echo "📦 Цель: $BACKUP_FILE"

# Создать директорию для бэкапов
mkdir -p "$BACKUP_DIR"

# Архивировать данные
tar -czf "$BACKUP_FILE" \
    -C "$SCRIPT_DIR" \
    data/template.json \
    data/whitelist.json \
    data/depth-config.json \
    data/risk-categories.json \
    history.json \
    "$SESSION_DIR" 2>/dev/null || {
        # Если SESSION_DIR не совпадает с проектом, архивируем session-storage/
        tar -czf "$BACKUP_FILE" \
            -C "$SCRIPT_DIR" \
            data/template.json \
            data/whitelist.json \
            data/depth-config.json \
            data/risk-categories.json \
            history.json \
            session-storage/
    }

echo "✅ Бэкап создан: $BACKUP_FILE"
echo "📊 Размер: $(du -h "$BACKUP_FILE" | cut -f1)"

# Удалить бэкапы старше 30 дней
find "$BACKUP_DIR" -name "mamkin-analitik-backup-*.tar.gz" -mtime +30 -delete
echo "🧹 Старые бэкапы (30+ дней) удалены."
