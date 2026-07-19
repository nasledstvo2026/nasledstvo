#!/bin/bash
# Тесты OpenProject — запускать после установки
# Использование: ./scripts/test-openproject.sh [HOST] [PORT]
set -e

HOST="${1:-localhost}"
PORT="${2:-8081}"
BASE="http://${HOST}:${PORT}"
PASSED=0
FAILED=0

green() { echo -e "\033[32m✓ $1\033[0m"; PASSED=$((PASSED+1)); }
red() { echo -e "\033[31m✗ $1\033[0m"; FAILED=$((FAILED+1)); }

echo "==================================="
echo "  OpenProject Tests — $(date)"
echo "  Target: $BASE"
echo "==================================="

# 1. Контейнер запущен
echo -n "1. Docker container running... "
if docker ps --format '{{.Names}}' | grep -q openproject; then
  green "OK"
else
  red "NOT RUNNING"
fi

# 2. Порт отвечает
echo -n "2. Port $PORT accessible... "
if timeout 5 bash -c "echo > /dev/tcp/$HOST/$PORT" 2>/dev/null; then
  green "OK"
else
  red "PORT NOT ACCESSIBLE"
fi

# 3. HTTP 200 на корневой URL
echo -n "3. HTTP GET / → 200... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE/" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
  green "HTTP $HTTP_CODE"
else
  red "HTTP $HTTP_CODE"
fi

# 4. API доступен
echo -n "4. API /api/v3 ... "
API_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
  -u "apikey:test" "$BASE/api/v3" 2>/dev/null || echo "000")
if [ "$API_CODE" != "000" ] && [ "$API_CODE" != "500" ]; then
  green "HTTP $API_CODE"
else
  red "HTTP $API_CODE"
fi

# 5. Страница логина
echo -n "5. Login page... "
LOGIN_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE/login" 2>/dev/null || echo "000")
if [ "$LOGIN_CODE" = "200" ]; then
  green "OK"
else
  red "HTTP $LOGIN_CODE"
fi

# 6. Docker health
echo -n "6. Container health... "
HEALTH=$(docker inspect --format='{{.State.Health.Status}}' openproject 2>/dev/null || echo "no-healthcheck")
if [ "$HEALTH" = "healthy" ]; then
  green "healthy"
elif [ "$HEALTH" = "starting" ]; then
  echo -e "\033[33m⚠ starting (wait)\033[0m"
else
  echo -e "\033[33m⚠ $HEALTH\033[0m"
fi

# 7. Место на диске
echo -n "7. Disk free > 500M... "
FREE_MB=$(df -BM / | tail -1 | awk '{print $4}' | sed 's/M//')
if [ "$FREE_MB" -gt 500 ]; then
  green "${FREE_MB}M free"
else
  red "${FREE_MB}M free (CRITICAL)"
fi

# 8. RAM
echo -n "8. RAM available > 500M... "
RAM_MB=$(free -m | awk '/^Mem:/{print $7}')
if [ "$RAM_MB" -gt 500 ]; then
  green "${RAM_MB}M available"
else
  red "${RAM_MB}M available (LOW)"
fi

echo "==================================="
echo "  Results: $PASSED passed, $FAILED failed"
echo "==================================="

[ "$FAILED" -eq 0 ] && exit 0 || exit 1
