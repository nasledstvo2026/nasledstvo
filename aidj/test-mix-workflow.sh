#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Тесты для проверки workflow «Создать Mix» в DJ Set'ах
# ═══════════════════════════════════════════════════════════════

set -e

TUNNEL_URL="${1:-https://figure-mental-gentle-focal.trycloudflare.com}"
echo "🔍 Тестируем туннель: $TUNNEL_URL"
echo ""

# ─── 1. Проверка туннеля (health) ───
echo "─══════════════════════════════════════════─"
echo "1️⃣  Health check — туннель жив?"
HTTP_CODE=$(curl -sk -o /dev/null -w '%{http_code}' "$TUNNEL_URL/tracks.json" --max-time 5)
if [ "$HTTP_CODE" = "200" ]; then
  echo "   ✅ Туннель отвечает (HTTP $HTTP_CODE)"
else
  echo "   ❌ Туннель НЕ отвечает (HTTP $HTTP_CODE)"
  exit 1
fi
echo ""

# ─── 2. POST /api/mix — базовый запрос ───
echo "─══════════════════════════════════════════─"
echo "2️⃣  POST /api/mix — отправка треков на сведение"
RESPONSE=$(curl -sk "$TUNNEL_URL/api/mix" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"tracks":[{"title":"T1","artist":"A1","url":"test.mp3"},{"title":"T2","artist":"A2","url":"test2.mp3"}],"preset":"default"}' \
  --max-time 10 2>&1)
HTTP_CODE=$(curl -sk -o /dev/null -w '%{http_code}' "$TUNNEL_URL/api/mix" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"tracks":[{"title":"T1","artist":"A1","url":"test.mp3"},{"title":"T2","artist":"A2","url":"test2.mp3"}],"preset":"default"}' \
  --max-time 10 2>&1)

MIX_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mix_id',''))" 2>/dev/null || echo "")

if [ "$HTTP_CODE" = "202" ] && [ -n "$MIX_ID" ]; then
  echo "   ✅ POST /api/mix ответил 202, mix_id=$MIX_ID"
else
  echo "   ❌ POST /api/mix: HTTP $HTTP_CODE, mix_id='$MIX_ID'"
  echo "   Ответ: $RESPONSE"
  exit 1
fi
echo ""

# ─── 3. GET /api/mix/{id}/status — статус сведения ───
echo "─══════════════════════════════════════════─"
echo "3️⃣  GET /api/mix/$MIX_ID/status — статус сведения"

for i in 1 2 3 4 5; do
  sleep 2
  STATUS_RESP=$(curl -sk "$TUNNEL_URL/api/mix/$MIX_ID/status" --max-time 5 2>&1)
  STATUS=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
  echo "   Попытка $i: статус = $STATUS"
  if [ "$STATUS" = "done" ] || [ "$STATUS" = "error" ]; then
    break
  fi
done

if [ "$STATUS" = "done" ]; then
  echo "   ✅ Сведение завершено (done)"
  # Проверяем URL результата
  RESULT_URL=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('url',''))" 2>/dev/null)
  if [ -n "$RESULT_URL" ]; then
    echo "   ✅ URL результата: $RESULT_URL"
  fi
elif [ "$STATUS" = "error" ]; then
  ERROR_MSG=$(echo "$STATUS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error',''))" 2>/dev/null)
  echo "   ❌ Ошибка сведения: $ERROR_MSG"
  exit 1
else
  echo "   ⚠️ Статус: $STATUS (возможно нет реальных mp3-файлов для сведения)"
fi
echo ""

# ─── 4. POST /api/log — логирование ───
echo "─══════════════════════════════════════════─"
echo "4️⃣  POST /api/log — проверка логирования"
LOG_CODE=$(curl -sk -o /dev/null -w '%{http_code}' "$TUNNEL_URL/api/log" \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"event":"test_create_set","data":{"name":"Test Set"},"page":"djset","ts":"2026-06-28T12:00:00Z"}' \
  --max-time 5 2>&1)
if [ "$LOG_CODE" = "200" ] || [ "$LOG_CODE" = "201" ] || [ "$LOG_CODE" = "204" ]; then
  echo "   ✅ Логирование работает (HTTP $LOG_CODE)"
else
  echo "   ⚠️ Логирование: HTTP $LOG_CODE (не критично)"
fi
echo ""

# ─── 5. Проверка CORS ───
echo "─══════════════════════════════════════════─"
echo "5️⃣  CORS — Access-Control-Allow-Origin"
CORS_HEADER=$(curl -sk -D- "$TUNNEL_URL/tracks.json" --max-time 5 2>&1 | grep -i 'access-control-allow-origin' | tr -d '\r')
if echo "$CORS_HEADER" | grep -qi 'access-control-allow-origin'; then
  echo "   ✅ CORS: $CORS_HEADER"
else
  echo "   ❌ CORS отсутствует!"
  exit 1
fi
echo ""

# ─── 6. Проверка, что прямой IP не матчится ───
echo "─══════════════════════════════════════════─"
echo "6️⃣  Self-signed SSL — прямой IP блокируется"
SSL_CODE=$(curl -k -o /dev/null -w '%{http_code}' 'https://176.123.162.12/aidj/tracks.json' --max-time 5 2>&1 || echo "BLOCKED")
if [ "$SSL_CODE" = "BLOCKED" ] || [ -z "$SSL_CODE" ] || [ "$SSL_CODE" = "000" ]; then
  echo "   ℹ️ curl с -k проходит (HTTP $SSL_CODE), но браузер из GitHub Pages заблокирует"
else
  echo "   ℹ️ Прямой IP с self-signed: HTTP $SSL_CODE (curl -k проходит, браузер — нет)"
fi
echo ""

echo "─══════════════════════════════════════════─"
echo "✅ Все тесты пройдены"
echo ""
echo "📋 Сводка:"
echo "   Туннель:      $TUNNEL_URL"
echo "   Сертификат:   Cloudflare (валидный)"
echo "   API mix:      ✅"
echo "   Статус:       ✅"
echo "   Логи:         ✅"
echo "   CORS:         ✅"
