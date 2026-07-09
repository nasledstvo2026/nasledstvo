#!/bin/bash
# =============================================================================
# deploy.sh — Развёртывание сервиса «Мамкин аналитик» на VPS
# =============================================================================
# Выполняется на VPS после git pull для обновления сервиса.
#
# Использование:
#   ./scripts/deploy.sh
#
# Предусловия:
#   - Репозиторий склонирован на VPS в рабочую директорию
#   - OpenClaw установлен и настроен
#   - .env настроен с реальными ключами
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "🔧 Развёртывание Мамкин аналитик..."
echo "📂 Директория: $SCRIPT_DIR"

# 1. Обновить код
echo "📥 Обновление кода..."
cd "$SCRIPT_DIR"

# 2. Установить зависимости Python
if command -v pip3 &> /dev/null; then
    echo "🐍 Установка Python-зависимостей..."
    pip3 install python-docx
fi

# 3. Создать директорию для сессий
SESSION_DIR="${SESSION_STORAGE_PATH:-/var/mamkin-analitik/sessions/}"
if [ ! -d "$SESSION_DIR" ]; then
    echo "📁 Создание директории сессий: $SESSION_DIR"
    mkdir -p "$SESSION_DIR/active" "$SESSION_DIR/completed"
fi

# 4. Настроить .env
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "⚠️  .env не найден! Скопируйте .env.template в .env и заполните ключи."
    exit 1
fi

# 5. Перезапустить OpenClaw
echo "🔄 Перезапуск OpenClaw..."
if command -v systemctl &> /dev/null; then
    sudo systemctl restart openclaw
    echo "✅ OpenClaw перезапущен."
else
    echo "⚠️  systemctl не найден. Перезапустите OpenClaw вручную."
fi

echo "✅ Развёртывание завершено."
