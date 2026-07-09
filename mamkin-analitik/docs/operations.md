# Operations — Эксплуатация сервиса «Мамкин аналитик»

## Инфраструктура

| Компонент | Значение |
|-----------|----------|
| VPS | vm-f13581 |
| Домен (Cloudflare) | уточнить у администратора |
| OpenClaw порт | 8080 |
| Директория проекта | ~/.openclaw/workspace/mamkin-analitik/ |
| Директория сессий | /var/mamkin-analitik/sessions/ |

## Запуск и остановка

```bash
# Запуск OpenClaw
openclaw start

# Остановка
openclaw stop

# Перезапуск
openclaw restart

# Статус
openclaw status
```

## Развёртывание

```bash
# На VPS:
cd ~/.openclaw/workspace/mamkin-analitik
git pull
./scripts/deploy.sh
```

## Бэкапы

```bash
# Ручной бэкап
./scripts/backup.sh

# Ежедневный бэкап (через cron)
# Добавить в crontab:
# 0 2 * * * /home/user1/.openclaw/workspace/mamkin-analitik/scripts/backup.sh
```

## Мониторинг

- Логи OpenClaw: stdout/stderr
- Проверка здоровья: Cloudflare Tunnel Dashboard
- Мониторинг сессий: /var/mamkin-analitik/sessions/

## Восстановление после сбоя

1. Восстановить бэкап
2. Перезапустить OpenClaw
3. Проверить активные сессии

## Переменные окружения

См. .env.template для полного списка.
