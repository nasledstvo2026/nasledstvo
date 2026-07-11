# План миграции DeepSeek V3 → V4 (до 24.07.2026)

## Цель
Заменить `deepseek-chat` (V3.2) и `deepseek-reasoner` на `deepseek-v4-flash` / `deepseek-v4-pro` во всех конфигах и cron-задачах до отключения эндпоинтов DeepSeek 24.07.2026.

## Этапы

### 1. 🟢 Config.yaml — агенты (8 шт.)
Заменить `"model": "deepseek/deepseek-chat"` → `"model": "deepseek/deepseek-v4-flash"` для:
- `bmad-master`
- `katrin-agent`
- `auditor-agent`
- `medhelp-agent`
- `medcheck-agent`
- `mamkin-analitik`
- `katya-agent`
- `search-agent`, `stats-agent`, `verify-agent`

Для агентов с высокой точностью (auditor-agent, katrin-agent) — `deepseek-v4-pro`.

### 2. 🟢 Cron: Данил (пн) — `e001daa1`
- model: `deepseek/deepseek-chat` → `deepseek/deepseek-v4-pro`
- timeout: 120 → 600
- Добавить fallback: `deepseek/deepseek-v4-flash`

### 3. 🟢 Cron: Данил (чт) — `ef30162f`
- model: `deepseek/deepseek-chat` → `deepseek/deepseek-v4-pro`
- timeout: 300 → 600
- Добавить fallback: `deepseek/deepseek-v4-flash`

### 4. 🟡 Cron: search-agent — `822d930b`
- model: `deepseek-chat` → `deepseek-v4-flash`
- fallback: `deepseek-v4-pro`

### 5. 🟡 Cron: verify-agent — `0104b513`
- model: `deepseek-chat` → `deepseek-v4-flash`
- fallback: `deepseek-v4-pro`

### 6. 🟡 Cron: katya-agent — `fc34d68b`
- model: `deepseek-chat` → `deepseek-v4-flash`
- fallback: `deepseek-v4-pro`

### 7. 🟡 Cron: stats-agent — `eec06e3c`
- model: `deepseek-chat` → `deepseek-v4-flash`
- fallback: `deepseek-v4-pro`

### 8. 🟢 Cron: backup — `a7ec1604`
- model: `deepseek-chat` → `deepseek-v4-flash`
- fallback: не нужен (простая задача)

### 9. 🟢 Cron: Роза — `8df8451b`
- Уже есть fallback `deepseek-v4-flash` — просто поменять primary: `deepseek-chat` → `deepseek-v4-flash`, fallback → `deepseek-v4-pro`

### 10. 🟢 Cron: Ирина — `0d49cb67`
- Уже есть fallback `deepseek-v4-flash` — поменять primary: `deepseek-chat` → `deepseek-v4-flash`, fallback → `deepseek-v4-pro`

### 11. 🟢 Cron: tasks.html — `1a2fafd9`
- Уже есть fallback `deepseek-v4-flash` — поменять primary: `deepseek-chat` → `deepseek-v4-flash`, fallback → `deepseek-v4-pro`

### 12. 🟢 Cron: Лена — `b4f0e3ed`
- Сейчас primary: `deepseek-v4-flash`, fallback: `deepseek-chat`
- После 24.07 fallback `deepseek-chat` отключат — убрать fallback или оставить только primary
- **Сейчас не трогать** — она работает

### 13. 🟢 Перезагрузка Gateway
После изменения openclaw.json: `openclaw gateway restart`

### 14. 🟢 Тестирование
- Проверить `openclaw models list --provider deepseek`
- Принудительно запустить каждую cron-задачу (`openclaw cron run --force <id>`)
- Проверить Telegram-доставку
