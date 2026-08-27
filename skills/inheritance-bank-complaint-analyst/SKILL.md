---
name: "inheritance-bank-complaint-analyst"
description: "Анализ жалоб по наследству в банках РФ: поиск, верификация, сводка, статистика"
---

# inheritance-bank-complaint-analyst

## Описание
Скилл для полного цикла анализа жалоб по наследству в банках РФ: поиск, верификация, сводка в Telegram, публикация статистики.

## Когда использовать
- Ежедневно будни ~11:00 (сводка для Кати)
- При запросе «покажи статистику» от Кати
- При запросе «проверь жалобу/URL» от Кати

## Процедура

### Этап 1. Поиск жалоб (search)

**Источники (по приоритету):**

#### 1.1 Banki.ru AJAX API
```
GET https://www.banki.ru/services/responses/list/ajax/
```
- Получает последние отзывы (без пагинации)
- Фильтр: текст содержит «наследств» или «наследник»

#### 1.2 Banki.ru — страницы топ-15 банков
```
GET https://www.banki.ru/services/responses/bank/{slug}/
```
- Слаги банков: `sberbank`, `vtb`, `alfabank`, `tcs` (Т-Банк), `gazprombank`, `sovcombank`, `psb`, `rshb`, `pochtabank`, `uralsib`, `raiffeisen`, `ozon`, `yandex`, `mts`, `rencredit`
- Искать: «наследств», «наследник» на странице
- Пауза между банками: 3-5 сек

#### 1.3 SearXNG (Google)
- `http://localhost:8888/search?q=<query>&format=json&language=ru-RU`
- Запросы:
  - `site:banki.ru/services/responses/bank/response/ наследство отказ`
  - `site:banki.ru/services/responses/bank/response/ умер наследство`
  - `site:banki.ru наследство не выдают деньги`
  - `site:banki.ru отказ в выдаче наследства банк`
  - `site:banki.ru/services/questions-answers/ наследство`
- Пауза между запросами: 15-30 сек

#### 1.4 Otzovik.com, Pikabu.ru (через SearXNG)
- Те же запросы с `site:otzovik.com` и `site:pikabu.ru`

**Формат результата (katya-raw.json):**
```json
[
  {
    "date": "YYYY-MM-DD",
    "bank": "название банка",
    "title": "заголовок",
    "text": "текст (первые 300 символов)",
    "url": "полный URL",
    "source": "banki.ru / otzovik.com / pikabu.ru"
  }
]
```

### Этап 2. Верификация (verify)

Для каждой записи с URL:
1. `web_fetch(url)` — проверить, что открывается
2. Проверить контекст:

**verified** — всё подтверждено:
- URL реально открывается
- В тексте есть тема наследства (отказ банка, проблемы с выплатой, ипотека умершего, вклад/счёт умершего)
- Автор — реальный пользователь (не юрист, не СМИ, не новость)

**needs_review** — сомнительно:
- URL открывается, но тема наследства неочевидна
- ИЛИ это вопрос, а не жалоба
- ИЛИ отзыв короткий/шаблонный

**rejected** — не подходит:
- URL не открывается (404, таймаут)
- Это статья юриста / новость / реклама
- Тема не про наследство (115-ФЗ, антиотмывочное, кредиты)
- Дубль (такой URL уже был в истории)

**Формат результата (katya-verified.json):**
```json
{
  "date": "YYYY-MM-DD",
  "bank": "...",
  "title": "...",
  "text": "...",
  "url": "...",
  "source": "banki.ru",
  "verification": "verified | needs_review | rejected",
  "reject_reason": "..."  // только для rejected
}
```

### Этап 3. Сводка в Telegram (для Кати)

Формат:
```
📋 Сводка жалоб — ДД.ММ

banki.ru — N:
• [Банк] — суть проблемы (url)

otzovik.com — N:
• ...

Итого: N жалоб (из них verified: N, needs_review: N)
```

Если жалоб нет:
```
Новых жалоб за вчера не обнаружено
```

### Этап 4. Статистика и публикация

1. Синхронизировать базу (идемпотентно): `python3 /home/user1/.openclaw/workspace/scripts/katya_merge.py`
2. Прочитать `katya-data.json` (накопительная база всех жалоб, список) и `katya-summary-7d.json` (готовые агрегаты `base` и `window`)
3. Посчитать по агрегатам `base`:
   - Всего жалоб за всё время (`base.total`, период `firstDate`–`lastDate`)
   - По банкам (`base.byBank`, названия уже канонизированы)
   - Помесячно (`base.byMonth`), по источникам (`base.bySource`)
   - Топ-10 банков
   - Отдельным блоком — окно 7 дней из `window`
4. Сформировать `stats-inheritance.html` по шаблону:
   - Скопировать структуру из shared/stats-inheritance.html
   - Менять ТОЛЬКО текстовые данные (цифры, даты, ссылки)
   - НЕ менять классы, теги, стили
5. Сохранить в `/home/user1/.openclaw/workspace/reports/stats-inheritance.html`
6. Опубликовать:
   ```bash
   cd /home/user1/.openclaw/workspace && bash publish-report.sh reports/stats-inheritance.html stats-inheritance.html
   ```

### Правила накопления базы (FR-17) — ЖЕЛЕЗНОЕ
`katya-data.json` — накопительная база ВСЕХ жалоб за всё время. Единственный разрешённый способ записи:

```bash
python3 /home/user1/.openclaw/workspace/scripts/katya_merge.py        # обычный прогон
python3 /home/user1/.openclaw/workspace/scripts/katya_merge.py --dry-run   # посмотреть, что изменится
```

Скрипт сам делает: бэкап базы → дедуп по нормализованному URL (без www/слеша/utm) → дополнение
новыми verified/needs_review → канонизация названий банков и источников → пересчёт сводки за 7 дней
в `katya-summary-7d.json` → дополнение seen-листа `katya-extra-seen.json`. Запись атомарная,
если записей стало бы меньше — прогон отменяется (exit 3).

- ❌ НИКОГДА не писать в `katya-data.json` через write/edit/python — ни агенту, ни человеку
- ❌ НИКОГДА не хранить в `katya-data.json` сводку «за N дней» — окно живёт только в `katya-summary-7d.json`
- ✅ Дедуп по `url`; rejected в базу не попадают (но попадают в seen-лист)
- ✅ Тесты скрипта: `python3 /home/user1/.openclaw/workspace/scripts/test_katya_merge.py` (21 кейс)
- 📌 История вопроса: в июле 2026 формулировка «обнови katya-data.json — агрегированные данные за
  7 дней» превратила базу из 82 записей в 2. Восстановлено 27.08.2026 (124 записи), правило
  зафиксировано скриптом.

### Ключевые слова для поиска
- наследство + банк + отказ
- наследство + банк + жалоба
- умер + банк + не отдают + деньги
- отказ + наследство + банк + выплата
- наследство + банк + проблемы

## Источники
- `/home/user1/.openclaw/agents/shared/katya-raw.json` — сырые результаты поиска
- `/home/user1/.openclaw/agents/shared/katya-verified.json` — верифицированные (окно прогона)
- `/home/user1/.openclaw/agents/shared/katya-data.json` — накопительная база всех жалоб (только через `katya_merge.py`)
- `/home/user1/.openclaw/agents/shared/katya-summary-7d.json` — агрегаты: окно 7 дней + вся база
- `/home/user1/.openclaw/agents/shared/katya-extra-seen.json` — seen-лист обработанных URL (только через `katya_merge.py`)
- `/home/user1/.openclaw/agents/shared/stats-inheritance.html` — шаблон отчёта
- `publish-report.sh` — скрипт публикации на GitHub Pages

## Ошибки
- Если search не вернул результатов — пропустить verify, сразу написать «нет жалоб»
- Если verify-agent не отвечает >30 сек — считать результатом needs_review
- Если публикация не удалась — сохранить HTML локально, сообщить об ошибке
