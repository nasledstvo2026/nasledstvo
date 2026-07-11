# План миграции DeepSeek V3 → V4 (до 24.07.2026)

## Цель
Заменить `deepseek-chat` (V3.2) и `deepseek-reasoner` на `deepseek-v4-flash` / `deepseek-v4-pro` во всех конфигах и cron-задачах до отключения эндпоинтов DeepSeek 24.07.2026.

## Этапы

### 1. ✅ Config.yaml — агенты (10 шт.) — ГОТОВО
Заменил `"model": "deepseek/deepseek-chat"` → `"model": "deepseek/deepseek-v4-flash"` для:
- `bmad-master`
- `medhelp-agent`
- `medcheck-agent`
- `mamkin-analitik`
- `katya-agent`
- `search-agent`, `stats-agent`, `verify-agent`

Для агентов с высокой точностью:
- `auditor-agent` → `deepseek-v4-pro`
- `katrin-agent` → `deepseek-v4-pro`

✅ Gateway перезагружен, все 10 агентов отвечают OK при тесте.

### 2. ✅ Cron: Данил (пн) — `e001daa1` — ГОТОВО
- model: `deepseek/deepseek-v4-flash` (primary), fallback: `deepseek/deepseek-v4-pro`
- timeout: 600
- ✅ Тест: запущен принудительно — OK (75 сек, доставлено в Telegram, consecutiveErrors сброшен в 0)

### 3. ✅ Cron: Данил (чт) — `ef30162f` — ГОТОВО
- model: `deepseek/deepseek-v4-flash` (primary), fallback: `deepseek/deepseek-v4-pro`
- timeout: 600
- ✅ Тест: запущен принудительно — OK (39 сек, доставлено в Telegram)

### 4. ✅ Cron: search-agent — `822d930b` — ГОТОВО
- model: `deepseek-v4-flash`, fallback: `deepseek-v4-pro`

### 5. ✅ Cron: verify-agent — `0104b513` — ГОТОВО
- model: `deepseek-v4-flash`, fallback: `deepseek-v4-pro`

### 6. ✅ Cron: katya-agent — `fc34d68b` — ГОТОВО
- model: `deepseek-v4-flash`, fallback: `deepseek-v4-pro`

### 7. ✅ Cron: stats-agent — `eec06e3c` — ГОТОВО
- model: `deepseek-v4-flash`, fallback: `deepseek-v4-pro`

### 8. ✅ Cron: backup — `a7ec1604` — ГОТОВО
- model: `deepseek-v4-flash`, fallback: нет

### 9. ✅ Cron: Роза — `8df8451b` — ГОТОВО
- model: `deepseek-v4-flash`, fallback: `deepseek-v4-pro`

### 10. ✅ Cron: Ирина — `0d49cb67` — ГОТОВО
- model: `deepseek-v4-flash`, fallback: `deepseek-v4-pro`

### 11. ✅ Cron: tasks.html — `1a2fafd9` — ГОТОВО
- model: `deepseek-v4-flash`, fallback: `deepseek-v4-pro`

### 12. ✅ Cron: Лена — `b4f0e3ed` — ГОТОВО
- model: `deepseek-v4-flash`, fallback: нет (уже чисто)
- ✅ Проверено: fallback пустой, последний запуск OK (300 сек, доставлено)

### 13. ✅ Перезагрузка Gateway — ГОТОВО
- Gateway перезагружен 11.07 20:06
- Статус: running, connectivity: ok

### 14. ✅ Тестирование — ГОТОВО
- ✅ Все 4 модели DeepSeek доступны (deepseek-chat, deepseek-reasoner, v4-flash, v4-pro)
- ✅ Все 10 агентов отвечают OK
- ✅ Cron Данил (пн) — OK (75 сек, доставлено в Telegram, consecutiveErrors: 0)
- ✅ Cron Данил (чт) — OK (39 сек, доставлено в Telegram, consecutiveErrors: 0)
- ✅ Все 11 cron-задач в статусе ok
