#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Pre-Tests — проверка что текущий туннель отвечает
# ═══════════════════════════════════════════════════════════════

TUNNEL_URL="${1:-https://review-formula-reflect-upon.trycloudflare.com}"
echo "🔍 Pre-check: $TUNNEL_URL"
echo ""

FAIL=0

echo "1️⃣  /tracks.json"
HTTP=$(curl -sk -o /dev/null -w '%{http_code}' "$TUNNEL_URL/tracks.json" --max-time 5)
[ "$HTTP" = "200" ] && echo "   ✅ $HTTP" || { echo "   ❌ $HTTP"; FAIL=1; }

echo "2️⃣  POST /api/mix"
MIX_RESP=$(curl -sk "$TUNNEL_URL/api/mix" -X POST -H 'Content-Type: application/json' \
  -d '{"tracks":[{"title":"T1","artist":"A1","url":"test.mp3"},{"title":"T2","artist":"A2","url":"test2.mp3"}],"preset":"default"}' --max-time 10 2>&1)
HTTP=$(curl -sk -o /dev/null -w '%{http_code}' "$TUNNEL_URL/api/mix" -X POST \
  -H 'Content-Type: application/json' \
  -d '{"tracks":[{"title":"T1","artist":"A1","url":"test.mp3"},{"title":"T2","artist":"A2","url":"test2.mp3"}],"preset":"default"}' --max-time 10 2>&1)
MIX_ID=$(echo "$MIX_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('mix_id',''))" 2>/dev/null)
[ "$HTTP" = "202" ] && [ -n "$MIX_ID" ] && echo "   ✅ HTTP $HTTP, mix_id=$MIX_ID" || { echo "   ❌ HTTP $HTTP, mix_id=$MIX_ID"; FAIL=1; }

echo "3️⃣  GET /api/mix/$MIX_ID/status"
STATUS=$(curl -sk "$TUNNEL_URL/api/mix/$MIX_ID/status" --max-time 5 2>&1)
echo "   Ответ: $STATUS" | head -3

echo "4️⃣  POST /api/log"
LOG_CODE=$(curl -sk -o /dev/null -w '%{http_code}' "$TUNNEL_URL/api/log" -X POST \
  -H 'Content-Type: application/json' \
  -d '{"event":"pre_test","data":{},"page":"djset","ts":"2026-06-28T12:00:00Z"}' --max-time 5 2>&1)
[ "$LOG_CODE" = "200" ] || [ "$LOG_CODE" = "201" ] || [ "$LOG_CODE" = "204" ] && echo "   ✅ $LOG_CODE" || { echo "   ⚠️ $LOG_CODE"; }

echo "5️⃣  CORS header"
CORS=$(curl -sk -D- "$TUNNEL_URL/tracks.json" --max-time 5 2>&1 | grep -i 'access-control-allow-origin' | tr -d '\r')
[ -n "$CORS" ] && echo "   ✅ $CORS" || { echo "   ❌ отсутствует"; FAIL=1; }

echo ""
[ "$FAIL" = "1" ] && echo "❌ Есть ошибки!" || echo "✅ Все pre-tests пройдены"
exit $FAIL
