# Этап 1 — Архитектура и конфигурация

**Дата:** 07.07.2026 22:12 MSK
**Статус:** ✅ Завершён

## Что сделано

### 1.1 Директории
- Созданы: `/home/user1/.openclaw/agents/medhelp-agent/workspace/`
- Созданы: `/home/user1/.openclaw/agents/medcheck-agent/workspace/`
- Созданы: `/home/user1/.openclaw/workspace/logs/medhelp/`

### 1.2 AGENTS.md
- `medhelp-agent` — роль фронт-агента для Марии, протокол верификации, таймауты, контракт JSON, обработка вердиктов, логирование
- `medcheck-agent` — роль верификатора, иерархия источников, правила вердиктов, кеш, изоляция

### 1.3 SOUL.md
- `medhelp-agent` — профессиональный, уважительный тон
- `medcheck-agent` — сухой, формальный, только факты

### 1.4 TOOLS.md
- `medhelp-agent` — sessions_send → medcheck, web_search, web_fetch, память
- `medcheck-agent` — web_search, web_fetch, URL-шаблоны источников, кеш

### 1.5 openclaw.json
- Добавлены `medhelp-agent` и `medcheck-agent` в agents.list
- Добавлен binding: peer 1833934429 → medhelp-agent
- Глобальный agentToAgent включён

### 1.6 USER.md
- Обновлена запись Марии: добавлен binding medhelp-agent

### 1.7 Рестарт Gateway
- Gateway перезапущен, статус: running, 5 агентов

## Проблемы
- Первая версия конфига с `agentToAgent` на уровне агента была невалидна — убрал, оставил глобальный флаг
- `openclaw agents add` не добавил binding (не хватало `--workspace` во втором запуске). Binding добавлен вручную через JSON-патч

## Контрольные точки
- [x] Директории созданы
- [x] AGENTS.md для обоих агентов
- [x] SOUL.md для обоих агентов
- [x] TOOLS.md для обоих агентов
- [x] openclaw.json — agents.list + binding
- [x] allowFrom + USER.md (allowFrom уже был, добавил пометку в USER.md)
- [x] openclaw status — валидный, 5 агентов
- [x] Gateway restart — успешно
- [x] Оба агента видны в status
