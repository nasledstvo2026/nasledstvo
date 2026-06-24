#!/bin/bash
# step2-process.sh — ШАГ 2: фильтрация и запись в _1 файлы
# Запускать ПОСЛЕ search-searxng.sh (ШАГ 1)
# Использование: bash scripts/step2-process.sh
#
# Этот скрипт выполняет механическую часть шага 2:
# 1. Парсит searxng-raw.json, извлекает URL
# 2. Проверяет даты через curl + regex на сыром HTML
# 3. Формирует JSON для вставки в katya-data_1.json
# 4. Обновляет katya-stats-data_1.md
# 5. Публикует temp-stats.html
#
# ⚠️ Фильтрация (жалоба vs новость) — за LLM. Скрипт только механика.

set -e

RAW="/home/user1/.openclaw/workspace/memory/searxng-raw.json"
DATA_1="/home/user1/.openclaw/workspace/memory/katya-data_1.json"
STATS_1="/home/user1/.openclaw/workspace/memory/katya-stats-data_1.md"

echo "=== ШАГ 2: ОБРАБОТКА РЕЗУЛЬТАТОВ ==="

if [ ! -f "$RAW" ]; then
  echo "Ошибка: нет searxng-raw.json. Сначала запусти search-searxng.sh"
  exit 1
fi

echo ""
echo "Сырых результатов: $(python3 -c "import json; d=json.load(open('$RAW')); print(len(d))")"
echo ""

# 1. Группируем по URL (дедупликация)
echo "--- ДЕДУПЛИКАЦИЯ ---"
python3 -c "
import json
data = json.load(open('$RAW'))
seen = set()
unique = []
for r in data:
    u = r.get('url', '')
    if u and u not in seen:
        seen.add(u)
        unique.append(r)
# Сохраняем уникальные
with open('$RAW', 'w') as f:
    json.dump(unique, f, ensure_ascii=False)
print(f'Уникальных URL: {len(unique)}')
" 2>/dev/null

echo ""
echo "=== СПИСОК URL С КОНТЕНТОМ ==="
echo "(Проверь и скажи Лунту, какие из них — жалобы, а какие — нет)"
echo ""

python3 -c "
import json
data = json.load(open('$RAW'))
for i, r in enumerate(data):
    title = r.get('title', '')[:80]
    url = r.get('url', '')
    content = r.get('content', '')[:120]
    print(f'[{i+1}] {title}')
    print(f'    URL: {url}')
    print(f'    {content}')
    print()
" 2>/dev/null

echo "=== КОМАНДА: проверить даты ==="
echo "Запусти: bash scripts/step2-process.sh --check-dates"
echo ""
echo "=== КОМАНДА: после фильтрации ==="
echo "1. Удали из searxng-raw.json лишние записи вручную"
echo "2. Запусти: bash scripts/step2-process.sh --save"
echo ""

if [ "$1" = "--check-dates" ]; then
  echo "=== ПРОВЕРКА ДАТ ==="
  python3 << 'PYEOF'
import json, subprocess, re
data = json.load(open('/home/user1/.openclaw/workspace/memory/searxng-raw.json'))

for i, r in enumerate(data):
    url = r.get('url', '')
    if not url:
        continue
    
    # Пробуем достать дату через curl + regex на сыром HTML
    try:
        result = subprocess.run(
            ['curl', '-s', '--max-time', '8', url],
            capture_output=True, text=True, timeout=10
        )
        html = result.stdout
        
        # Ищем даты в формате ДД.ММ.ГГГГ
        dates = re.findall(r'\d{2}\.\d{2}\.\d{4}', html)
        # Ищем даты вида "12 января 2026"
        ru_dates = re.findall(r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}', html, re.IGNORECASE)
        
        print(f'[{i+1}] {r.get("title","")[:60]}')
        if dates:
            print(f'    Даты: {", ".join(dates[:5])}')
        if ru_dates:
            print(f'    Даты (рус): {", ".join(ru_dates[:3])}')
        else:
            print(f'    Дат не найдено')
        print()
    except Exception as e:
        print(f'[{i+1}] ERROR: {e}')
        print()
PYEOF
fi

if [ "$1" = "--save" ]; then
  echo "=== СОХРАНЕНИЕ В _1 ФАЙЛЫ ==="
  python3 << 'PYEOF'
import json
from datetime import datetime

raw = json.load(open('/home/user1/.openclaw/workspace/memory/searxng-raw.json'))
data_1 = json.load(open('/home/user1/.openclaw/workspace/memory/katya-data_1.json'))

# Берём только отфильтрованные (уже удалены не-жалобы)
new_entries = []
for r in raw:
    entry = {
        "date": r.get("publishedDate", ""),
        "bank": "",
        "title": r.get("title", ""),
        "description": r.get("content", "")[:200],
        "url": r.get("url", ""),
        "source": ""
    }
    # Определяем источник
    url = entry["url"]
    if "banki.ru" in url: entry["source"] = "banki.ru"
    elif "pikabu.ru" in url: entry["source"] = "pikabu.ru"
    elif "2gis.ru" in url: entry["source"] = "2ГИС"
    elif "otzovik.com" in url: entry["source"] = "otzovik.com"
    elif "dzen.ru" in url: entry["source"] = "Дзен"
    elif "vc.ru" in url: entry["source"] = "vc.ru"
    else: entry["source"] = "веб"
    
    # Определяем банк по ключевым словам
    txt = (entry["title"] + " " + entry["description"]).lower()
    banks = ["сбербанк", "втб", "газпромбанк", "совкомбанк", "альфа-банк", "т-банк", "псб",
             "почта банк", "ренессанс", "мтс банк", "озон банк", "яндекс банк", "мкб", "рсхб"]
    for b in banks:
        if b in txt:
            entry["bank"] = b.title()
            break
    
    new_entries.append(entry)

# Добавляем новые записи в начало data_1.json
# Сначала отфильтровываем те, что уже есть (по URL)
existing_urls = {e.get("url", "") for e in data_1}
truly_new = [e for e in new_entries if e["url"] and e["url"] not in existing_urls]

if truly_new:
    data_1 = truly_new + data_1
    with open('/home/user1/.openclaw/workspace/memory/katya-data_1.json', 'w') as f:
        json.dump(data_1, f, ensure_ascii=False, indent=2)
    print(f"Добавлено новых записей: {len(truly_new)}")
else:
    print("Новых записей нет (все URL уже есть)")

# Обновляем katya-stats-data_1.md
# Подсчитываем помесячную статистику
from collections import defaultdict
stats = defaultdict(lambda: {"sber": 0, "other": 0, "banks": []})

for e in data_1:
    d = e.get("date", "")
    if len(d) >= 7:
        ym = d[:7]
        if "сбер" in (e.get("bank", "") + e.get("title", "") + e.get("description", "")).lower():
            stats[ym]["sber"] += 1
        else:
            stats[ym]["other"] += 1
        bank_name = e.get("bank", "")
        if bank_name and bank_name.lower() != "неизвестно":
            stats[ym]["banks"].append(bank_name)

# Читаем текущий stats_1
with open('/home/user1/.openclaw/workspace/memory/katya-stats-data_1.md', 'r') as f:
    content = f.read()

# Обновляем или добавляем строки
for ym in sorted(stats.keys()):
    s = stats[ym]
    bank_list = []
    bank_counts = defaultdict(int)
    for b in s["banks"]:
        bank_counts[b] += 1
    for b, c in sorted(bank_counts.items()):
        bank_list.append(f"{b} {c}")
    
    line = f"{ym} | Сбер: {s['sber']} | Другие: {s['other']} | {', '.join(bank_list)}"
    
    # Проверяем, есть ли уже такая строка
    if ym in content:
        # Замена строки
        import re
        content = re.sub(
            rf'^{ym} \|.*$',
            line,
            content,
            flags=re.MULTILINE
        )
    else:
        # Добавить в конец
        content += f"\n{line}"

with open('/home/user1/.openclaw/workspace/memory/katya-stats-data_1.md', 'w') as f:
    f.write(content)

print("Stats _1 обновлён")
print(f"Всего записей в katya-data_1.json: {len(data_1)}")
PYEOF

  echo ""
  echo "=== ПУБЛИКАЦИЯ ==="
  echo "Запусти: bash scripts/step2-process.sh --publish"
fi

if [ "$1" = "--publish" ]; then
  echo "=== ФОРМИРУЕМ temp-stats.html ==="
  echo "(Запускается вручную через Лунта — нужно обновить HTML)"
  echo "Пока: git add + commit + push"
  cd /home/user1/.openclaw/workspace
  git add -A
  git commit -m "step2: stats update $(TZ=Europe/Moscow date '+%d.%m.%Y %H:%M')" 2>/dev/null || echo "Nothing to commit"
  git push
  echo ""
  echo "Готово: https://nasledstvo2026.github.io/nasledstvo/"
fi
