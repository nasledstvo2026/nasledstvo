#!/bin/bash
# =============================================================================
# migrate.sh — Миграция данных сессий при изменении схемы
# =============================================================================
# Выполняет миграцию файлов сессий при изменении структуры JSON.
#
# Использование:
#   ./scripts/migrate.sh <from_version> <to_version>
#
# Пример:
#   ./scripts/migrate.sh 1.0 2.0
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SESSION_DIR="${SESSION_STORAGE_PATH:-$SCRIPT_DIR/session-storage}"

FROM_VERSION="${1:-}"
TO_VERSION="${2:-}"

if [ -z "$FROM_VERSION" ] || [ -z "$TO_VERSION" ]; then
    echo "❌ Укажите версии: $0 <from_version> <to_version>"
    echo "Пример: $0 1.0 2.0"
    exit 1
fi

echo "🔄 Миграция Мамкин аналитик: $FROM_VERSION → $TO_VERSION"
echo "📂 Директория сессий: $SESSION_DIR"

# Здесь будут добавляться скрипты миграции по мере изменения схемы
# Каждая миграция — отдельная функция

case "$FROM_VERSION" in
    "1.0")
        echo "📋 Миграция v1.0 → v2.0 не реализована (актуальная версия)."
        ;;
    *)
        echo "❌ Неизвестная версия: $FROM_VERSION"
        exit 1
        ;;
esac

echo "✅ Миграция завершена."
