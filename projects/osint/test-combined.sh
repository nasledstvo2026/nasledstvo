#!/bin/bash
# Комбинированный тестовый прогон TC-02, TC-03, TC-05, TC-06, TC-09
# На основе osint-raw-data.json (без запуска Фазы B)

set -e
cd /home/user1/.openclaw/workspace/memory/osint

echo "============================================"
echo "  TC-01: Сбор данных (уже пройден ✅)"
echo "============================================"
python3 -c "
import json
data = json.load(open('osint-raw-data.json'))
print(f'Фактов собрано: {len(data)}')
srcs = set(d['source'] for d in data)
print(f'Источники: {len(srcs)} — {', '.join(sorted(srcs)[:5])}...')
print()

# Атрибуция
full = [d for d in data if d.get('source') and d.get('date') and d.get('fact')]
print(f'С полной атрибуцией: {len(full)}/{len(data)}')
print(f'Источники покрытия: >=80% — {\"✅\" if len(full)/len(data) >= 0.8 else \"❌\"}'  )

# Категории
cats = {}
for d in data:
    r = d.get('relevance','?')
    cats[r] = cats.get(r,0) + 1
print(f'По темам: {cats}')
"

echo ""
echo "============================================"
echo "  TC-02: Фильтрация недостоверных"
echo "============================================"
python3 -c "
import json
data = json.load(open('osint-raw-data.json'))

# Список доверенных источников
trusted_sources = ['ISW', 'The Guardian', 'Al Jazeera', 'RUSI', 'OSW', 'Meduza']
bad_markers = ['анонимный', 'без регистрации', 'без верификации', 'домен зарегистрирован']

trusted = [d for d in data if any(s in d.get('source','') for s in trusted_sources)]
untrusted = [d for d in data if d not in trusted]
propaganda = [d for d in data if any(m in d.get('source','').lower() for m in bad_markers)]

print(f'Из доверенных: {len(trusted)}')
print(f'Из непроверенных: {len(untrusted)}')
print(f'Пропагандистские (по маркерам): {len(propaganda)}')
print()
print('Непроверенные факты (должны быть отфильтрованы):')
for d in untrusted:
    print(f'  ❌ {d[\"source\"]} — {d[\"fact\"][:50]}...')
"

echo ""
echo "============================================"
echo "  TC-05: Противоречивые данные"
echo "============================================"
python3 -c "
# Проверяем текущий osint.html на наличие противоречий
import re
with open('../osint.html', 'r') as f:
    html = f.read()

# Ищем упоминания противоречий
contra = re.findall(r'противореч[иа-я]+|неопредел[её][нн][а-я]+|двойственн[а-я]+|две точки зрения|обе стороны|взаимоисключающ[а-я]+', html, re.IGNORECASE)
print(f'Упоминаний противоречий: {len(contra)}')
for c in contra[:5]:
    print(f'  ↳ \"{c}\"')
# Находим контекст
matches = list(re.finditer(r'(?s).{0,50}(противореч[иа-я]+|неопредел[её][нн][а-я]+).{0,50}', html))
for m in matches[:3]:
    txt = m.group(0).replace('\n',' ')
    print(f'  Контекст: ...{txt}...')
"

echo ""
echo "============================================"
echo "  TC-03/06: Оценки по 3 вопросам"
echo "============================================"
python3 -c "
import re
with open('../osint.html', 'r') as f:
    html = f.read()

# Ищем классы вероятности
highs = len(re.findall(r'prob-high|🔴', html))
mids = len(re.findall(r'prob-mid|🟡', html))
lows = len(re.findall(r'prob-low|🟢', html))
print(f'Красные (высок.): {highs}')
print(f'Жёлтые (средн.): {mids}')
print(f'Зелёные (низк.): {lows}')

print()

# Ищем названия разделов
sections = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE)
print(f'Разделы (h2): {len(sections)}')
for s in sections:
    print(f'  📌 {s.strip()}')

print()

# Количество фактов (строк с class=\"body\")
bodies = len(re.findall(r'class=\"body\"', html))
items = len(re.findall(r'class=\"item\"', html))
print(f'Карточек .item: {items}')
print(f'Фактов (.body): {bodies}')
print(f'Мета-данных (.meta): {len(re.findall(r\"class=.meta\", html))}')
"

echo ""
echo "============================================"
echo "  TC-09: Дедупликация"
echo "============================================"
python3 -c "
# Считаем уникальные строки в seen.md (кроме заголовков и разделителей)
with open('osint-seen.md', 'r') as f:
    lines = f.readlines()

entries = [l for l in lines if l.startswith('|') and not l.startswith('| ---') and not l.startswith('| Источник')]
print(f'Записей в osint-seen.md: {len(entries)}')

# Проверка дублей
from collections import Counter
facts = Counter()
for e in entries:
    parts = [p.strip() for p in e.split('|') if p.strip()]
    if len(parts) >= 3:
        key = '|'.join(parts[:3])
        facts[key] += 1

dupes = {k:v for k,v in facts.items() if v > 1}
print(f'Дублей: {len(dupes)}')
if dupes:
    for k,v in dupes.items():
        print(f'  ⚠️ {k} — {v} раз')
else:
    print('✅ Дублей нет')
print(f'Уникальных фактов: {len(facts)}')
"

echo ""
echo "============================================"
echo "  TC-08/15: Публикация"
echo "============================================"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://nasledstvo2026.github.io/nasledstvo/osint.html")
echo "HTTP-статус: $HTTP_CODE (ожидается 200)"
if [ "$HTTP_CODE" = "200" ]; then echo "✅"; else echo "❌"; fi

echo ""
echo "============================================"
echo "  TC-13: Лог (нет записей, но структура есть)"
echo "============================================"
head -2 osint-log.md
echo "✅ Структура лога существует (заполняется при Фазе A)"

echo ""
echo "============================================"
echo "  TC-04: Ге верификации (источники в seen.md)"
echo "============================================"
grep -v "^#" osint-seen.md | grep -v "---" | grep -v "^$" | head -3
echo "..."
FACT_COUNT=$(grep -v "^#" osint-seen.md | grep -v "---" | grep -v "^$" | grep -cP '^\|')
echo "Всего фактов в кэше: $FACT_COUNT"
