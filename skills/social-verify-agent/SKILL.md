# social-verify-agent — Верификация НПА

## Назначение
Проверка актуальности и корректности каждого НПА через consultant.ru перед добавлением в базу.

## Триггер
- Вызов от `social-search-agent` через `sessions_send`
- Ручной запуск: `sessions_send(agentId="social-verify-agent")`

## Алгоритм
1. Получить входящий список НПА (от search-agent)
2. Для каждого НПА:
   a. Выполнить `web_search` по полному названию + "consultant.ru" для поиска актуальной редакции
   b. Если найден — зафиксировать: дата редакции, статус (действует/утратил силу), ссылка
   c. Если не найден — пометить как "requires manual check"
3. Записать результат в `/home/user1/nasledstvo/data/social-npa-db.json`
   - Формат:
   ```json
   {
     "npaId": "...",
     "title": "Федеральный закон №...",
     "url": "https://www.consultant.ru/...",
     "lastChecked": "2026-07-29",
     "status": "active" | "expired" | "manual_check",
     "lastEdition": "2026-06-15",
     "categories": ["детские пособия", "инвалидность", "ветераны", "СВО"]
   }
   ```
4. Вернуть подтверждение: сколько НПА проверено, сколько активно

## Интеграция с social-category-matcher
База `social-npa-db.json` доступна для использования `social-consult-agent` и `social-category-matcher` для поиска релевантных НПА по категориям.
