# Тесты миграции DeepSeek V3 → V4

## 1. Проверка моделей в OpenClaw
```bash
openclaw models list --provider deepseek
```
Ожидается: `deepseek/deepseek-v4-flash` и `deepseek/deepseek-v4-pro` (и больше не `deepseek-chat`)

## 2. Проверка Gateway
```bash
openclaw status
```
Ожидается: Gateway running, модель по умолчанию `deepseek/deepseek-v4-flash`

## 3. Быстрый тест новой модели
```bash
openclaw run --model deepseek/deepseek-v4-flash "Скажи 'ok'"
```
Ожидается: ответ "ok" за <30 сек

## 4. Тест агентов
Для каждого агента (katya-agent, search-agent, verify-agent, stats-agent, katrin-agent, auditor-agent, medhelp-agent, medcheck-agent, mamkin-analitik, bmad-master):
```bash
openclaw run --agent <agent-id> "Ответь OK (только OK)"
```
Ожидается: "OK"

## 5. Тест cron-задач (принудительный запуск)
```bash
# Данил (пн) — сейчас с ошибками
openclaw cron run --force e001daa1
# Данил (чт)
openclaw cron run --force ef30162f
# search-agent
openclaw cron run --force 822d930b
# verify-agent
openclaw cron run --force 0104b513
# katya-agent
openclaw cron run --force fc34d68b
# stats-agent
openclaw cron run --force eec06e3c
# backup
openclaw cron run --force a7ec1604
```
Ожидается: status=ok, без timeouts

## 6. Проверка Telegram-доставки
Проверить, что Катя, Данил, Лена получили уведомления (вручную)

## 7. Проверка отчётов на сайте
https://nasledstvo2026.github.io/nasledstvo/stats-inheritance.html
https://nasledstvo2026.github.io/nasledstvo/report-danil.html
