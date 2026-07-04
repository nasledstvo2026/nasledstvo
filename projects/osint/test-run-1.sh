#!/bin/bash
# Run 1: Быстрые проверки osint.html и инфраструктуры
set -e

echo "=== TC-07: HTML-шаблон ==="
cd /home/user1/.openclaw/workspace

grep -q 'OSINT' osint.html && echo "✅ Заголовок OSINT" || echo "❌ Нет заголовка"
COUNT_CLASS=$(grep -c 'prob-high\|prob-mid\|prob-low' osint.html || true)
echo "   CSS-классы вероятности: $COUNT_CLASS (ожидается 3)"
COUNT_PROB=$(grep -c 'class="probability prob-' osint.html || true)
echo "   Блоки .probability: $COUNT_PROB (ожидается 3)"
grep -q 'class="meta"' osint.html && echo "✅ Мета-информация есть" || echo "❌ Нет мета"
grep -q 'class="body"' osint.html && echo "✅ Блоки .body есть" || echo "❌ Нет .body"
grep -q 'theme.css' osint.html && echo "✅ theme.css подключён" || echo "❌ Нет theme.css"
grep -q 'На главную' osint.html && echo "✅ Навигация есть" || echo "❌ Нет навигации"
grep -q 'Главная' osint.html && echo "✅ Альтернативная навигация есть" || echo "❌ Нет Главная"

echo ""
echo "=== TC-03: 3 оценки ==="
grep -co 'Вторая волна мобилизации\|СВО\|война с Европой\|Война с НАТО\|полномасштабная война' osint.html || true

echo ""
echo "=== TC-12: Логирование ==="
echo "osint-log.md заголовок есть:"
head -2 /home/user1/.openclaw/workspace/memory/osint/osint-log.md

echo ""
echo "=== TC-04: Верификация (проверка источников) ==="
echo "Уникальные источники в osint-seen.md:"
grep -oP '^\| \K[^|]+' /home/user1/.openclaw/workspace/memory/osint/osint-seen.md | sort -u

echo ""
echo "=== TC-10: Файл сборки ==="
ls -la /home/user1/.openclaw/workspace/memory/osint/osint-raw-data.json && echo "✅ osint-raw-data.json существует" || echo "❌ Файл не найден"
