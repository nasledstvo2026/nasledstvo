#!/bin/bash
# Генерация HTML-дашборда статистики OpenClaw для nasledstvo.net.ru
set -euo pipefail

GATEWAY_URL="http://127.0.0.1:18789/api/v1/admin/rpc"
TOKEN=$(python3 -c 'import json;print(json.load(open("/home/user1/.openclaw/openclaw.json"))["gateway"]["auth"]["token"])')
OUTPUT="/tmp/stats-dashboard.html"

# Собираем данные в /tmp
curl -s "$GATEWAY_URL" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"method":"usage.status","params":{}}' > /tmp/_usage_status.json

curl -s "$GATEWAY_URL" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"method":"usage.cost","params":{}}' > /tmp/_usage_cost.json

curl -s "$GATEWAY_URL" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"method":"status","params":{}}' > /tmp/_status.json

# Генерируем HTML
python3 /home/user1/.openclaw/workspace/generate-stats-dashboard.py

echo "Generated: $OUTPUT"
