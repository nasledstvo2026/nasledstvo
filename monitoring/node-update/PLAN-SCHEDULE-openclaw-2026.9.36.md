# План-график: OpenClaw 2026.9.33 → 2026.9.36

Окно: **сегодня, 31.10.2026, 23:00–00:20 MSK** (резерв: 01.11, 04:00–05:30).
Хост: vm-f13581. Бюджетный гейт: 149 с окно, 2 с × число агентов.

## Подготовка (до окна)

### 18:00–18:20 — бэкап и гигиена
1. Свежий каталог `~/.openclaw/backups/upgrade-2026.9.36-$(date +%Y%m%d-%H%M)/`:
   sqlite + wal + shm, openclaw.json, юнит, override.conf, env, versions.txt, ROLLBACK.md.
2. `openclaw doctor --fix` вне процесса gateway через systemd-run (по согласию владельца).
3. Зафиксировать baseline: `free -m`, `df -h /`, `node -v`, `openclaw --version`, `automations list`, `openclaw agents list`.

**Проверки P1 (все обязательны):**
- [ ] бэкап существует, sqlite > 20 МБ, `PRAGMA integrity_check` = ok
- [ ] `openclaw doctor --fix` завершился, отчёта о незавершённой миграции нет
- [ ] health = 200, юнит active
- [ ] свободно на диске ≥ 2 ГиБ
- [ ] активных update-scope нет

### 22:30–22:40 — сокращение ростера
1. `cp openclaw.json openclaw.json.bak-$(date +%Y%m%d-%H%M)`.
2. В `agents.entries` оставить **2 агента**: `main` и `kirill-family-advocate` (допуск 4 с вместо 20 с).
3. Рестарт шлюза (владелец). State агентов не трогаем.

**Проверки P2:**
- [ ] JSON валиден (`python3 -m json.tool`)
- [ ] `openclaw agents list` = 2
- [ ] health = 200, RSS < 1,2 ГиБ, available ≥ 1500 МиБ

### 22:45–22:55 — пауза фоновой нагрузки
Выключить до конца окна: heartbeat-main, asv-agent-monitor-morning/evening, barbershop (21:00 и месячный), lena-search/verify/html (02:00–02:20), Memory Dreaming (03:00), stats-agent (08:20), skill-collection-review-*, lena-healthcheck.

**Проверки P3:**
- [ ] в `automations list` все перечисленные disabled
- [ ] нет активных прогонов (`pgrep -af 'lena|stats-agent|asv' | grep -v grep` пусто)

## Окно

### 23:00 — T0: чистый рестарт
Владелец: `/restart`.
**Проверка P4:** health 200, RSS < 1,2 ГиБ, available ≥ 1500 МиБ, load < 0,5, swap used < 100 МиБ. Иначе — стоп, окно переносим.

### 23:05 — T+5: старт обновления
Владелец: `/update`. Зафиксировать время и scope-id.
**Проверка P5:** scope создан, handoff.log растёт, версия пока 9.33 (норма).

### 23:05–23:45 — мониторинг (только чтение, не вмешиваться)
Каждые 5 минут: scope active, рост handoff.log, 39 снапшотов, новых failure-json нет.
**Проверка P6 (гейт):** к T+40 либо scope закрыт и версия 9.36, либо зафиксирован откат.

### 23:45 — T+40: верификация
- [ ] `openclaw --version` = 2026.9.36 (и package.json)
- [ ] health/readyz = 200, MainPID сменился
- [ ] `openclaw update status --json` → available:false, pending нет
- [ ] в handoff.log нет `update-inspection-deferred`
- [ ] новый failure-json не появился
- [ ] `openclaw gateway status --deep` без protocol mismatch

## Возврат и функциональные проверки

### 23:50 — вернуть конфиг и кроны
1. Вернуть полный `openclaw.json` из бэкапа, рестарт (владелец).
2. Включить все automations обратно.
**Проверка P7:**
- [ ] `openclaw agents list` = 10
- [ ] все кроны enabled, nextRunAt в будущем
- [ ] health 200

### 00:00 — смоук-тесты
- [ ] `check.py` АСВ → CLEAN
- [ ] `node -e` fetch к API АСВ ок
- [ ] канал Telegram отвечает (короткий ответ в этот чат)
- [ ] диск/память в норме

### 00:10 — отчёт
Запись в `memory/2026-10-31.md`, короткий итог в чат, закрыть окно.

## Аварийные сценарии

- **Откат сработал (версия 9.33, новый failure-json):** проверить `packageRollbackVerified`, `service: healthy`; вернуть конфиг/кроны; зафиксировать причину; план Б — 2026.10.9 или RAM 8 ГиБ.
- **Шлюз не поднялся (health ≠ 200 > 3 мин):** владелец — `systemctl --user restart openclaw-gateway.service`; если не помогло: `npm i -g openclaw@2026.9.33`, restore sqlite/config, рестарт.
- **Scope висит > 20 мин без роста лога и без смены версии:** остановить только transient-unit `systemctl --user stop openclaw-update-….scope`, вернуть конфиг, разбираться отдельно.
- **Запрещено:** запускать update из процесса gateway, удалять lock-файлы, рекурсивный chmod, `npm install -g openclaw` вручную при живом апдейте.
