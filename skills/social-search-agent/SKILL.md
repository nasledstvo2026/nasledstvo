# social-search-agent — Поиск и мониторинг законов

## Назначение
Ежедневный сбор новых и обновлённых нормативно-правовых актов (НПА) и новостей по социальным пособиям, льготам и выплатам РФ.

## Триггер
- Расписание: **ежедневно в 09:03 MSK** (cron)
- Ручной запуск: `sessions_send(agentId="social-search-agent")`

## Источники
1. **fedpress.ru** — новости соцподдержки
2. **garant.ru** — изменения НПА
3. **consultant.ru** — актуальные редакции

## Алгоритм
1. Для каждого источника выполнить `web_search` с запросами:
   - `"социальные выплаты 2026 изменения" site:fedpress.ru`
   - `"пособия льготы новый закон 2026" site:garant.ru`
   - `"социальная поддержка изменения законодательства" site:consultant.ru`
2. Распарсить результаты: ссылка, заголовок, дата, краткое содержание
3. Дедуплицировать по URL
4. Записать результат в `/home/user1/nasledstvo/data/social-raw-found.json`
   - Формат: `[{ "sourceUrl", "title", "date", "summary", "source" }]`
5. Верификация найденных НПА (fallback-протокол, social-verify-agent НЕ зарегистрирован):
   - Попробовать `sessions_send(agentId="social-verify-agent", message=<JSON>)`.
   - Если ответ «agent not found» (ожидаемо — агент не в openclaw.json) → НЕ считать это ошибкой.
   - Fallback: передать кандидатов в main-сессию (`sessions_send(agentId="main")`) и верифицировать в main по протоколу `social-verifier-protocol` (приоритет источников: garant.ru → docs.cntd.ru → consultant.ru → sfr.gov.ru → nalog.gov.ru → региональные).
   - В лог записать `verify=agent-not-found→main`.
   - ⚠️ Если социальный верификатор появится в openclaw.json — вернуться к прямому вызову.

## Выход
Файл `social-raw-found.json` с новыми записями (append-only).
