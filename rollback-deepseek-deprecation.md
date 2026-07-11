# Откат миграции DeepSeek V3 → V4

Если что-то пошло не так после замены `deepseek-chat` на `deepseek-v4-flash`:

## Шаг 1. Восстановить openclaw.json
```bash
cp /home/user1/.openclaw/openclaw.json.backup-20260711 /home/user1/.openclaw/openclaw.json
openclaw gateway restart
```

## Шаг 2. Восстановить cron-задачи
Если cron-задачи были обновлены через `cron update` — восстановить через скрипт из бэкапа:
```bash
openclaw cron list --json > /tmp/crons-before.json
# Сравнить с /home/user1/.openclaw/workspace/deprecation-cron-backup.json
# Для каждой изменённой задачи выполнить openclaw cron update <id> <payload>
```

## Шаг 3. Проверить
- `/status` — Gateway running
- `openclaw models list --provider deepseek` — модели доступны
- Запустить каждую cron-задачу принудительно: `openclaw cron run --force <id>`
