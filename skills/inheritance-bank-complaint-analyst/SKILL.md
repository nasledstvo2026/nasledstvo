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

1. Прочитать `katya-data.json` (исторические данные)
2. Посчитать:
   - Всего жалоб за всё время
   - По банкам (Сбер, ВТБ, Альфа, и т.д.)
   - Помесячно
   - По годам
   - Топ-3 по количеству
3. Сформировать `stats-inheritance.html` по шаблону:
   - Скопировать структуру из shared/stats-inheritance.html
   - Менять ТОЛЬКО текстовые данные (цифры, даты, ссылки)
   - НЕ менять классы, теги, стили
4. Сохранить в `/tmp/stats-inheritance.html`
5. Опубликовать:
   ```bash
   /home/user1/.openclaw/workspace/publish-report.sh /tmp/stats-inheritance.html stats-inheritance.html
   ```

### Правила дедупликации
- По полю `url` — если URL уже есть в `katya-data.json`, не добавлять
- Перед записью делать backup: `cp katya-data.json katya-data.json.backup.$(date +%Y%m%d-%H%M%S)`
- Только дописывать, никогда не перезаписывать целиком

### Ключевые слова для поиска
- наследство + банк + отказ
- наследство + банк + жалоба
- умер + банк + не отдают + деньги
- отказ + наследство + банк + выплата
- наследство + банк + проблемы

## Источники
- `/home/user1/.openclaw/agents/shared/katya-raw.json` — сырые результаты поиска
- `/home/user1/.openclaw/agents/shared/katya-verified.json` — верифицированные
- `/home/user1/.openclaw/agents/shared/katya-data.json` — вся история
- `/home/user1/.openclaw/agents/shared/stats-inheritance.html` — шаблон отчёта
- `publish-report.sh` — скрипт публикации на GitHub Pages

## Ошибки
- Если search не вернул результатов — пропустить verify, сразу написать «нет жалоб»
- Если verify-agent не отвечает >30 сек — считать результатом needs_review
- Если публикация не удалась — сохранить HTML локально, сообщить об ошибке
