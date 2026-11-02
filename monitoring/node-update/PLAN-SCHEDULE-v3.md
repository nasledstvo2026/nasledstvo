# План-график v3: 2026.9.33 → 2026.9.36 (extended-stable)

Цель зафиксирована: **актуальный extended-stable = 2026.9.36**, канал в конфиге уже `extended-stable`, смена канала не нужна.
Окно: **сегодня, 22:50–00:15 MSK**. Подготовка (бэкап + baseline) уже выполнена в 19:19.

## Состояние на старте (проверено)
- OpenClaw 2026.9.33, канал extended-stable, Node v24.22.2 (требование 9.36: >=24.16 <25 — ок)
- Бэкап: `~/.openclaw/backups/upgrade-2026.9.36-20261031-1920/` (30 МБ): sqlite + wal + shm, openclaw.json, юнит, override, env, baseline.txt, ROLLBACK.md
- БД: integrity **ok**, quick_check **ok**, user_version 19, 7040 страниц
- Диск 8,7 ГиБ свободно, права 755/644, health 200, агентов 10
- /tmp очищен от пакета 10.9

## Бюджетное обоснование
Окно инспекции 149 с, допуск при 1 агенте — 2 с. Кандидат-фаза на 10 агентах занимала ~294 с; при 1 агенте расчётно ~85 с → запас ~64 с. Если фаза определяется фиксированными ожиданиями (offline maintenance), гейт не пройдёт — это ловится на G5 через 3 минуты после старта.

## График

### 20:00 (опционально, по согласию)
`openclaw doctor --fix` вне процесса gateway через systemd-run — снять отложенные проверки и дрейф юнита.
Проверка: команда завершилась, в отчёте нет незавершённых миграций, health 200.

### 22:30–22:40 — ростер и рестарт (владелец)
- `cp openclaw.json openclaw.json.bak-20261031-2230`
- оставить 1 агента: `main`; остальные записи — в бэкап
- `/restart`

Проверки P1: JSON валиден · `openclaw agents list` = 1 · health 200 · RSS < 1,2 ГиБ · available ≥ 1,5 ГиБ

### 22:40–22:50 — пауза фоновой нагрузки
Automations выключить: heartbeat-main, asv-agent-monitor-morning/evening, barbershop (21:00 и месячный 09:00), lena-search/verify/html (02:00–02:20), Memory Dreaming (03:00), stats-agent (08:20), все skill-collection-review-*, lena-healthcheck.
Системный cron: закомментировать строку `0 */3 * * * generate-tasks.py` (сработает в 00:00) — `crontab -l > ~/crontab.bak-20261031`, затем правка. Вернуть после окна.

Проверки P2: все automations disabled · `crontab -l` без generate-tasks · активных прогонов нет (`pgrep -af 'lena|stats-agent|asv|generate-tasks'` пусто)

### 22:50 — финальный preflight
- [ ] диск ≥ 5 ГиБ, available ≥ 1,5 ГиБ, load < 0,5, swap < 100 МиБ
- [ ] health 200, update-scope нет
- [ ] бэкап на месте, baseline.txt читается

### 22:55 — старт (`/update`)
P3: scope создан, handoff.log растёт, версия пока 9.33.

### 22:58 — G5, гейт бюджета
Смотрим, дошёл ли лог до `candidate-doctor-lint`.
- дошёл в пределах ~149 с от старта валидации → бюджет проходит
- нет → сценарий «фиксированные ожидания», ждать смысла нет

### 22:55–23:40 — мониторинг (только чтение)
Каждые 5 мин: scope active, рост лога, 39 снапшотов, новых failure-json нет. Не вмешиваться.

### 23:40 — верификация
- [ ] `openclaw --version` = 2026.9.36, package.json совпадает
- [ ] health/readyz 200, MainPID сменился, юнит active
- [ ] `openclaw update status --json` → available:false, pending нет
- [ ] в lint-отчёте нет `update-inspection-deferred`
- [ ] нового failure-json нет
- [ ] `PRAGMA quick_check` по state/openclaw.sqlite = ok

### 23:50 — возврат конфигурации
- вернуть полный `openclaw.json` из бэкапа, `/restart`
- включить все automations, вернуть строку generate-tasks в crontab

P4: `agents list` = 10 · кроны enabled с будущим nextRunAt · health 200

### 00:05 — смоук
- [ ] `check.py` АСВ → CLEAN, seen.json валиден
- [ ] Telegram отвечает (этот чат)
- [ ] `openclaw doctor` без critical
- [ ] память/диск в норме

### 00:15 — закрытие окна
Запись в `memory/2026-10-31.md`, короткий отчёт, окно закрыто.

## Аварийные сценарии
- Откат сработал (9.33 + новый failure-json): проверить `packageRollbackVerified`, `service: healthy`; вернуть конфиг/кроны; зафиксировать причину; дальше — ресурсы или ожидание релиза.
- Health ≠ 200 дольше 3 мин: владелец `systemctl --user restart openclaw-gateway.service`; если нет — restore по ROLLBACK.md.
- Scope висит > 20 мин без роста лога и без смены версии: остановить только transient-unit, вернуть конфиг, разбор отдельно.
- Запрещено: update из процесса gateway, удаление lock-файлов, рекурсивный chmod.
