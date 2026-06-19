#!/bin/bash
# log-activity.sh — добавить запись в prompt-activity.json
# Использование: ./log-activity.sh <user> "<request>" "<task>" ["<change>"]
#
# Пример: ./log-activity.sh Катя "добавить ссылку на приказ 123" "Катя 08:00"
#         ./log-activity.sh Данил "сменить модель на v4" "Данил пн" "модель: deepseek-v4-flash"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JSON="$SCRIPT_DIR/prompt-activity.json"
CHANGELOG="$SCRIPT_DIR/prompt-changelog.md"

if [ "$#" -lt 3 ]; then
  echo "Использование: $0 <user> \"<request>\" \"<task>\" [\"<change>\"]" >&2
  exit 1
fi

USER="$1"
REQUEST="$2"
TASK="$3"
CHANGE="${4:-}"

DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)

# Создаём JSON, если не существует
if [ ! -f "$JSON" ]; then
  echo '{"entries":[]}' > "$JSON"
fi

# Экранируем кавычки для JSON
safe_req=$(echo "$REQUEST" | sed 's/"/\\"/g')
safe_task=$(echo "$TASK" | sed 's/"/\\"/g')
safe_change=$(echo "$CHANGE" | sed 's/"/\\"/g')

# Вставляем запись в JSON (начинало массива)
jq --arg date "$DATE" \
   --arg time "$TIME" \
   --arg user "$USER" \
   --arg request "$safe_req" \
   --arg task "$safe_task" \
   --arg change "$safe_change" \
  '.entries = [{"date": $date, "time": $time, "user": $user, "request": $request, "task": $task, "change": $change}] + .entries' \
  "$JSON" > "${JSON}.tmp" && mv "${JSON}.tmp" "$JSON"

# Запись в changelog
{
  echo ""
  echo "### $DATE $TIME"
  echo "- **$USER:** «$REQUEST» → $TASK${CHANGE:+ · $CHANGE}"
} >> "$CHANGELOG"

echo "✅ Запись добавлена: $USER / «$REQUEST»"
