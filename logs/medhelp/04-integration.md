# Этап 4 — Интеграция medcheck-agent

**Дата:** 07.07.2026 22:17 MSK
**Статус:** ✅ Завершён

## Что сделано

### 4.1 AgentToAgent
- Глобально включён: `tools.agentToAgent.enabled: true`
- Проверено: sessions_send → medcheck-agent работает, ответ приходит

### 4.2 Контракт
- AGENTS.md medcheck-agent обновлён: парсить JSON из входящего сообщения
- Если не JSON или нет claims — отказ
- Формат ответа: JSON с verdict, details, verified_claims, sources_used

### 4.3 Изоляция
- medcheck-agent без внешнего binding
- В AGENTS.md прописан отказ не-medhelp запросам

### 4.4 Алгоритм верификации в medhelp-agent AGENTS.md
Прописан на этапе 1 (п. 1.2). Содержит:
1. Получить вопрос → сформулировать черновик ответа
2. Извлечь claims + sources
3. Отправить sessions_send → medcheck-agent
4. Получить JSON-ответ
5. ✅/🔄/❓/❌ — соответствующая обработка
6. Таймаут 45 сек, 1 ретрай

## Контрольные точки
- [x] AgentToAgent включён
- [x] Алгоритм верификации прописан
- [x] Тест: sessions_send → JSON-ответ (получен)
- [x] Изоляция прописана в AGENTS.md
