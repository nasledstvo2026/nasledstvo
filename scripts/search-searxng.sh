#!/bin/bash
# search-searxng.sh — ШАГ 1: поиск жалоб через SearXNG (без LLM)
# Сохраняет сырые результаты в memory/searxng-raw.json
# Использование: bash scripts/search-searxng.sh
set -e

OUTPUT="/home/user1/.openclaw/workspace/memory/searxng-raw.json"
SEARXNG="http://localhost:8888/search"

echo '[]' > "$OUTPUT"

QUERIES=(
  "site%3Abanki.ru+%28%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE+OR+%D1%83%D0%BC%D0%B5%D1%80%D1%88%D0%B5%D0%B3%D0%BE%29+%D0%BE%D1%82%D0%BA%D0%B0%D0%B7+%D0%B2%D1%8B%D0%BF%D0%BB%D0%B0%D1%82%D0%B0"
  "site%3Aotzovik.com+%28%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE+OR+%D1%83%D0%BC%D0%B5%D1%80%D1%88%D0%B5%D0%B3%D0%BE%29+%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D0%B0+%D0%B1%D0%B0%D0%BD%D0%BA"
  "site%3Apikabu.ru+OR+site%3Adzen.ru+%28%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE+OR+%D1%83%D0%BC%D0%B5%D1%80%D1%88%D0%B5%D0%B3%D0%BE%29+%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D0%B0+%D0%B1%D0%B0%D0%BD%D0%BA"
  "%28%D0%B2%D0%BA%D0%BB%D0%B0%D0%B4+%D1%83%D0%BC%D0%B5%D1%80%D1%88%D0%B5%D0%B3%D0%BE%29+OR+%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE+%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D0%B0+%D0%BE%D1%82%D0%BA%D0%B0%D0%B7"
  "site%3Asravni.ru+%28%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE+OR+%D1%83%D0%BC%D0%B5%D1%80%D1%88%D0%B5%D0%B3%D0%BE%29+%D0%B2%D0%BA%D0%BB%D0%B0%D0%B4+%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D0%B0"
  "site%3Avc.ru+%28%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE+OR+%D1%83%D0%BC%D0%B5%D1%80%D1%88%D0%B5%D0%B3%D0%BE%29+%D0%B1%D0%B0%D0%BD%D0%BA+%D0%B2%D0%BA%D0%BB%D0%B0%D0%B4+%D1%81%D1%83%D0%B4"
  "%D0%B7%D0%B0%D0%B2%D0%B5%D1%89%D0%B0%D0%BD%D0%B8%D0%B5+%D0%BE%D1%82%D0%BA%D0%B0%D0%B7+%D0%B1%D0%B0%D0%BD%D0%BA"
  "%D0%B2%D1%8B%D0%BF%D0%BB%D0%B0%D1%82%D0%B0+%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%B0+%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D0%B0+%D0%B1%D0%B0%D0%BD%D0%BA"
  "%D0%B7%D0%B0%D0%B2%D0%B5%D1%89%D0%B0%D1%82%D0%B5%D0%BB%D1%8C%D0%BD%D0%BE%D0%B5+%D1%80%D0%B0%D1%81%D0%BF%D0%BE%D1%80%D1%8F%D0%B6%D0%B5%D0%BD%D0%B8%D0%B5+%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D0%B0"
  "%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D0%BD%D0%B8%D0%BA+%D0%B1%D0%B0%D0%BD%D0%BA"
  "site%3Abanki.ru+%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE+%D0%BE%D1%82%D0%B7%D1%8B%D0%B2+%D0%B1%D0%B0%D0%BD%D0%BA"
)

LABELS=(
  "banki.ru наследство отказ"
  "otzovik.com наследство"
  "pikabu+dzen наследство"
  "вклад умершего наследство"
  "sravni.ru наследство"
  "vc.ru наследство"
  "завещание отказ"
  "выплата наследства жалоба"
  "завещательное распоряжение"
  "наследник банк"
  "banki.ru наследство отзыв"
)

echo "=== ШАГ 1: ПОИСК ЧЕРЕЗ SearXNG ==="

idx=0
for q in "${QUERIES[@]}"; do
  label="${LABELS[$idx]}"
  echo -n "[$((idx+1))/11] $label ... "
  
  RESULT=$(curl -s "$SEARXNG?q=$q&format=json&time_range=year&language=ru-RU&_=$RANDOM" --max-time 15 2>/dev/null)
  HIT_COUNT=$(echo "$RESULT" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(len(d.get('results',[])))" 2>/dev/null || echo "0")
  
  if [ "$HIT_COUNT" != "0" ] && [ "$HIT_COUNT" != "0" ]; then
    # Append to output
    echo "$RESULT" | python3 -c "
import sys, json
try:
    data = json.loads(sys.stdin.read())
    with open('$OUTPUT', 'r') as f:
        existing = json.load(f)
    for r in data.get('results', []):
        r['_query_idx'] = $idx
        r['_query_label'] = '$label'
        existing.append(r)
    with open('$OUTPUT', 'w') as f:
        json.dump(existing, f, ensure_ascii=False)
except: pass
" 2>/dev/null
    echo "$HIT_COUNT результатов"
  else
    echo "0"
  fi
  
  idx=$((idx + 1))
done

echo ""
echo "=== ГОТОВО ==="
TOTAL=$(python3 -c "import json; d=json.load(open('$OUTPUT')); print(len(d))" 2>/dev/null || echo "0")
echo "Всего сырых результатов: $TOTAL"
echo "Сохранено в: $OUTPUT"
