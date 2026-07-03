# Тест-кейсы: проверка после удаления сиротских файлов 03.07.2026

## 1. Сайт: основные страницы

| # | Тест | Ожидание | Команда |
|---|------|----------|---------|
| 1.1 | Главная (index.html) | HTTP 200, все секции видны | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/index.html` |
| 1.2 | Наследство | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/inheritance.html` |
| 1.3 | Социальное | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/social.html` |
| 1.4 | Сервисы | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/service.html` |
| 1.5 | AI DJ | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/aidj.html` |
| 1.6 | Фото | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/photo.html` |
| 1.7 | Закупки | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/zakupki.html` |
| 1.8 | ФармТендеролог продукт | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/pharm-tenderolog-product.html` |

## 2. Сайт: страницы со ссылкой на service.html (должны быть живы)

| # | Тест | Ожидание | Команда |
|---|------|----------|---------|
| 2.1 | Мониторинг жалоб | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/monitoring-complaints.html` |
| 2.2 | Проекты | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/projects.html` |
| 2.3 | Архитектура | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/architecture.html` |
| 2.4 | ФармТендеролог лендинг (старый) | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/pharm-tenderolog.html` |

## 3. Сайт: отчёты (доставляются по cron)

| # | Тест | Ожидание | Команда |
|---|------|----------|---------|
| 3.1 | Отчёт Лены | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/report-lena.html` |
| 3.2 | Отчёт Данила | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/report-danil.html` |
| 3.3 | Отчёт Розы | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/report-roza.html` |
| 3.4 | Отчёт Ирины | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/report-irina.html` |
| 3.5 | Статистика жалоб | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/stats-inheritance.html` |
| 3.6 | Задачи | HTTP 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/tasks.html` |

## 4. Удалённые файлы (должны отдавать 404)

| # | Тест | Ожидание | Команда |
|---|------|----------|---------|
| 4.1 | sber-claims | 404 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/sber-claims-2026.html` |
| 4.2 | stats-template | 404 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/stats-inheritance-template.html` |

## 5. Контент страниц (не сломался ли HTML)

| # | Тест | Ожидание | Команда |
|---|------|----------|---------|
| 5.1 | service.html — ссылки на monitoring-complaints, projects, architecture ведут куда надо | Текст ссылок есть | `grep -c 'monitoring-complaints\|projects\.html\|architecture\.html' service.html` |
| 5.2 | index.html — ссылки на основные продукты есть | 8+ ссылок | `grep -c 'href=' index.html` |

## 6. AI DJ функциональность

| # | Тест | Ожидание | Команда |
|---|------|----------|---------|
| 6.1 | aidj-delete.html жив | 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/aidj-delete.html` |
| 6.2 | aidj-player.html жив | 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/aidj-player.html` |
| 6.3 | djset.html жив | 200 | `curl -s -o /dev/null -w "%{http_code}" https://nasledstvo2026.github.io/nasledstvo/djset.html` |
| 6.4 | aidj-presets.html жив | 200 | `curl -s -o /dev/null -w "%{http_code}}" https://nasledstvo2026.github.io/nasledstvo/aidj-presets.html` |

## 7. Локальная консистентность

| # | Тест | Ожидание | Команда |
|---|------|----------|---------|
| 7.1 | git status — нет незакоммиченных файлов кроме ожидаемых | Чисто | `git status --short` |
| 7.2 | Ни один .html не содержит тегов к удалённым файлам | 0 вхождений | `grep -rn 'sber-claims\|stats-inheritance-template' *.html 2>/dev/null; echo "exit=$?"` |

## Критерии успеха

- Все тесты 1-3, 5-6: ✅ HTTP 200
- Все тесты 4: ✅ HTTP 404
- Тест 7: ✅ чисто
- Если любой тест из 1-3, 5-6 не проходит → **rollback**
- Если тест 4 возвращает 200 → **предупреждение, но не фатально** (GitHub Pages кеш)
- Если сервер отвечает 5xx на 3+ страницах → **rollback**
