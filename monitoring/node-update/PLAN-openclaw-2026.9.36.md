# План обновления OpenClaw 2026.9.33 → 2026.9.36

Дата анализа: 2026-10-31. Хост: vm-f13581 (Ubuntu, 2 vCPU, 3.8 GiB RAM, swap 4 GiB, Node v24.22.2).

## 1. Диагноз (по коду и логам)

Гейт пост-проверки в `dist/doctor-update-budget-CcadZSAw.mjs`:
- `PUBLISHED_VALIDATION_WORK_MS = 298000` (298 с)
- `INSPECTION_WINDOW_MS = 149000` (149 с — половина)
- `AGENT_INSPECTION_ALLOWANCE_MS = 2000` на агента
- `RUN_INSPECTION_ALLOWANCE_MS = 5000`
- допуск: `Date.now() + allowance <= inspectionDeadline`; иначе — defer с `errorCode=update-inspection-deferred`, `requirement=update-validation-budget`, severity=warning
- для agent-scope allowance = `agentCount x 2000` мс

У нас 10 агентов в `agents.entries` → нужно 20 000 мс. В момент проверки в окне оставалось **0 мс** → инспекция отложена → инвентарь неполный → `post-core-update-failed` → откат.

Вывод: пакет устанавливается, но пост-проверка **детерминированно** не влезает в 149-секундное окно на этой машине. Это не флейк и не битый пакет.

## 2. Опыт двух прогонов

| Прогон | Старт | Итог | Причина |
|---|---|---|---|
| #1 | 13:21 | откат | unsafe-permissions на `~/.config/systemd/user` (775) + defer инспекций |
| #2 | 15:11 | откат | тот же бюджетный гейт: 10 агентов × 2 с, 0 мс в окне |

Оба отката чистые: `packageRollbackVerified=true`, конфиг восстановлен, сервис healthy, версия 9.33 и тот же buildId.

Что уже закрыто:
- права: `~/.config`, `.config/systemd`, `.config/systemd/user`, `.service.d` → 755; юнит и override → 644
- дрейф юнита согласован: `StartLimitBurst`, `StartLimitIntervalSec`, `TimeoutStopSec`, `KillMode`
- Node обновлён до v24.22.2, тесты 15/0/1

Что осталось: только бюджет инспекции. Ретрай «как есть» даст третий такой же откат.

## 3. План

### Этап 0. Решение
9.36 — патч-релиз, не безопасность. Можно отложить. Но если обновляемся — по плану ниже.

### Этап 1. Подготовка (за день, без простоя)
1. Свежий бэкап в `~/.openclaw/backups/upgrade-2026.9.36-<ts>/`: sqlite (+wal/shm), openclaw.json, юнит, env, versions.txt, ROLLBACK.md.
2. Инвентарь: `openclaw agents list`, `automations list`, `free -h`, `nproc`, `uptime`.
3. Проверить, что state БД не в offline maintenance: нет активных сессий/прогонов; WAL не растёт.
4. `openclaw doctor --fix` вне процесса gateway (systemd-run, отдельный transient unit) — закрыть отложенные проверки заранее. Только по явному согласию владельца.

### Этап 2. Окно (ночь, 23:00–00:30 или 04:00–05:30)
1. Сократить ростер на время окна: 10 → 2–3 агента (main + максимум два нужных). Тогда allowance = 4–6 с вместо 20 с, и активация короче.
   - бэкап конфига: `cp openclaw.json openclaw.json.bak-<ts>`
   - убрать лишние записи из `agents.entries`, рестарт шлюза (владелец)
   - state агентов не трогаем, только записи в конфиге; возврат — из бэкапа
2. Выключить фоновую нагрузку на окно: кроны `asv-agent-monitor-{morning,evening}`, `barbershop:`, ночные lena; heartbeat.
3. Освободить память: рестарт шлюза перед окном (свежий RSS ~1 GiB), проверить `available >= 1.5 GiB`, swap почти не используется.
4. Контроль тишины: load < 0.5, нет активных прогонов, `health=200`.

### Этап 3. Обновление
- Владелец шлёт `/update` (managed handoff, штатный путь).
- Не вмешиваться: следить `/tmp/openclaw-update-run-handoff-*/handoff.log` и scope.
- Ожидаемое время: 30–45 мин.

### Этап 4. Проверка
- `openclaw --version` = 2026.9.36 (и `node -p ...package.json.version`)
- `health`/`readyz` = 200, юнит active, MainPID сменился
- `openclaw update status --json` → `available:false`, без pending
- `automations list` — кроны на месте; `openclaw agents list` — все агенты
- `check.py` АСВ → CLEAN, seen.json валиден
- В логах нет `update-inspection-deferred`

### Этап 5. Возврат конфигурации
- Вернуть полный `openclaw.json` из бэкапа, рестарт, включить кроны, проверить health и агентов.

### Этап 6. Откат (если снова fail)
Автоматический уже проверен дважды. Ручной:
1. `npm install -g openclaw@2026.9.33`
2. восстановить `openclaw.sqlite*` и `openclaw.json` из бэкапа
3. `systemctl --user restart openclaw-gateway.service`
4. `openclaw --version` = 2026.9.33, health 200

### Этап 7. Если не помогло
- Вариант A: 2026.10.9 (latest) — проверить, переработан ли бюджет в линии 10.x
- Вариант B: RAM 8 GiB (сейчас 3.8) — активация быстрее, окно успевает
- Вариант C: остаться на 9.33 до следующего релиза/планового апгрейда
- Вариант D: завести issue: гейт падает на deferral, который его же fixHint называет нормальным (`openclaw doctor --fix after activation`)

## 4. Ограничения и риски
- Бюджет в коде фиксирован; env/конфиг-ручки не найдены (есть только `OPENCLAW_UPDATE_RUN_ID`, `OPENCLAW_UPDATE_POST_INSTALL_DOCTOR_RESULT_PATH`).
- Сокращение ростера = агенты недоступны 15–30 мин ночью; state не страдает.
- Не удалять lock-файлы, не делать рекурсивный chmod, не запускать update из процесса gateway.
- Память: пик прошлого прогона 3.3 GiB при 3.8 GiB всего — запас критичен.
