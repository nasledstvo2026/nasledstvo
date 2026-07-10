# Этап 8: Health check и мониторинг (07.07.2026 22:25)

## Статус: ЗАВЕРШЁН

### Создан cron: «MedHelp: health-check агентов»
- **Расписание:** каждый час (09:00–22:00)
- **Модель:** deepseek-chat, timeout 60s
- **Что проверяет:**
  1. medhelp-agent отвечает на тестовый запрос
  2. medcheck-agent отвечает на тестовый JSON
  3. Доступность источников (consultant.ru, cr.minzdrav.gov.ru)
- **Кому при ошибке:** Кирилл (failureAlert, 2 ошибки, cooldown 1 час)

### Создан файл `medhelp/health-check.json`
- Формат: список последних 10 проверок
- Поля: timestamp, agent, source, status, duration_ms
- Путь: `/home/user1/.openclaw/workspace/medhelp/health-check.json`

### Существующий health check обновлён
- `MedHelp: health-check источников` — создан на этапе 2
- Переименован в «MedHelp: health-check агентов + источники»
- Обновлён: проверяет и агентов, и доступность consultant.ru

### Логирование
- Все health-check результаты пишутся в `medhelp/health-check.json`
- Ошибки — через stderr (journalctl)
