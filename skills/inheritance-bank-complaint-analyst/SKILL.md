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

**Состав источников — утверждён 28.08.2026 (FR-01), проверено живыми пробами.**
Отчёт: `docs/complaints-monitoring/source-parsing-2026-08-27.md`.
Перепроверить источники: `python3 scripts/katya_source_probe.py`.

❗ **Правило темпа:** не быстрее **1 запроса в 2 секунды** к одному домену.
Пачка запросов (78 за 9 с) → banki.ru банит IP на ~1,5 часа (`http=000`).
Проверено: 55 карточек подряд с `sleep 2` — ни одного отказа.
Все запросы: `curl -s -L --compressed -m 20 -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36'`.

#### Ядро 1: banki.ru — двухступенчатый разбор
```
а) https://www.banki.ru/services/responses/list/?page=N     # N=1..3 (до 6), 25 отзывов/стр
б) https://www.banki.ru/services/responses/bank/response/<id>/   # карточка, полный текст
```
- в ленте есть заголовки и дата-время (`2026-08-27 15:24:47`) → фильтр по дате без открытия карточек
- тема в ленте **не видна** (заголовки вида «Отзыв») → карточки качать обязательно (лимит 60/прогон)
- карточка: ~60 КБ, полный текст + `datePublished`
- объём: **50–75 отзывов/сутки** (стр.1 — сегодня/вчера, стр.6 — −2 дня)
- ❌ не работает: `?search=` (игнорируется), `/services/responses/list/ajax/` (без ссылок и текста), `sitemap.xml` (404)
- опция сужения: `?rate[]=1&rate[]=2` (плохие оценки) — может срезать жалобы с нейтральной оценкой

#### Ядро 2: pravoved.ru
```
а) https://pravoved.ru/questions/            # 15 свежих вопросов, ~20 % тематических
б) https://pravoved.ru/search/?q=<запрос>     # релевантное, но архив 2016–2021
в) https://pravoved.ru/question/<id>/        # карточка, datePublished ISO
```
- ⚠️ **пагинации нет** ни в ленте, ни в поиске (`?page=2` отдаёт то же), сортировки по дате нет
- следствие: одна утренняя проходка теряет часть потока; для полноты нужен опрос каждые 2–4 часа (решение не принято)
- запросы поиска: «наследство банк», «вклад умершего», «завещание счет банк»
- если `web_fetch` вернул блок «похожие вопросы» — брать `og:description` через curl

#### Дополнительно
```
pikabu.ru:    https://pikabu.ru/tag/Наследство  (+ ?page=2)   — только лента
advgazeta.ru: https://www.advgazeta.ru/novosti/                    — HTML (RSS 404)
```
- pikabu: текст поста без JS **недоступен** (201 КБ / ~350 слов, `og:description` нет) → классификация по заголовку и сниппету из ленты

#### ❌ Не использовать (проверено 27–28.08.2026)
| Домен | Причина |
|---|---|
| 9111.ru | `http 447` — блок IP VPS на ленте и поиске |
| otzovik.com | лента — JS-заглушка (6 КБ/145 слов), поиск 404; карточки читаются, но списка свежих нет |
| sravni.ru | тег 404, поиск — 1 упоминание на 471 КБ, `/novosti/` → `/mag/` |
| asn-news.ru | лента живая, наследственных тем нет |
| kp.ru | поиск и RSS 404 |
| SearXNG / web_search | погашен 23.08.2026 / провайдер отключён |

**Тематический фильтр (python, без LLM):** стемы `наследств`, `наследник`, `наследодател`,
`завещан`, `вклад умерш`, `смерти вкладчика` + отсев всего, что есть в `katya-extra-seen.json`.

<details>
<summary>Исторические способы сбора (не работают, оставлены для контекста)</summary>

- Banki.ru AJAX API `/services/responses/list/ajax/` — с августа 2026 отдаёт 167 КБ без ссылок и текста
- Страницы топ-15 банков `/services/responses/bank/{slug}/` — слаги: `sberbank`, `vtb`, `alfabank`,
  `tcs`, `gazprombank`, `sovcombank`, `psb`, `rshb`, `pochtabank`, `uralsib`, `raiffeisen`, `ozon`,
  `yandex`, `mts`, `rencredit` (можно использовать точечно, пауза 3–5 с)
- SearXNG `http://localhost:8888/search?q=<query>&format=json` — погашен 23.08.2026
- Запросы вида `site:banki.ru наследство отказ` — требуют внешнего поисковика

</details>

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
