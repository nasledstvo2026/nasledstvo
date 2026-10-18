# ТЗ — агент `maria` (изолированная песочница для обучения мультиагентной архитектуре)

Дата: 2026-10-18
Заказчик: Кирилл
Исполнитель: Лунтик (main-агент)

## 1. Цель

Дать Марии (Telegram sender_id `1431548892`) собственного изолированного агента, в котором она сможет:

- понять, зачем нужны агенты и как они устроены в мультиагентной архитектуре;
- создать себе агента: под-агента через `sessions_spawn` и/или навык через `skill_workshop`;
- научиться ставить агентам задачи и получать результаты.

При этом **без доступа** к:

- данным Кирилла и других пользователей;
- чужим сессиям;
- памяти основной системы (main workspace);
- конфигу gateway (`openclaw.json` с токенами/ключами);
- планировщику и админ-инструментам.

## 2. Текущее состояние (что есть сейчас)

| Что | Значение |
| --- | --- |
| Отправитель | `channel:telegram:1431548892` |
| Маршрутизация | нет binding → попадает в main-агент (общий workspace) |
| Глобальный deny (`tools.toolsBySender`) | `code_execution, cron, group:fs, group:memory, group:sessions, process, skill_workshop` |
| `exec` | **разрешён** (для PDF, осознанно с 24.09) |
| `tools.sessions.visibility` | `all` (глобально) |
| `tools.agentToAgent.enabled` | `true` |
| Docker | доступен (v29.1.3) |
| MARIA.md | режим наставника, лежит в main workspace |

**Ключевая проблема:** сейчас Мария работает в общем main-агентe. Дать ей `group:fs`/`group:sessions` = дать доступ к `MEMORY.md`, `TOOLS.md` (SSH-ключи, askpass), данным клиентов и чужим сессиям. Поэтому нужен отдельный агент.

## 3. Что делаем

### 3.1 Новый агент `maria`

```json5
{
  id: "maria",
  name: "Мария (учебный)",
  workspace: "~/.openclaw/agents/maria/workspace",
  agentDir: "~/.openclaw/agents/maria/agent",
  model: "deepseek/deepseek-v4-flash",
  tools: {
    allow: [
      // под-агенты (мультиагентность):
      "sessions_spawn", "sessions_yield", "subagents", "session_status",
      // файлы в своём workspace:
      "read", "write", "edit", "apply_patch",
      // выполнение кода:
      "exec", "code_execution",
      // навыки (создание агентов как скиллов):
      "skill_workshop",
      // веб + медиа (сохранить текущие возможности):
      "web_search", "web_fetch",
      "image_generate", "video_generate",
      // планы/цели:
      "update_plan", "create_goal", "update_goal", "get_goal",
    ],
    deny: [
      // приватность сессий — нельзя перечислять/читать/писать чужие:
      "sessions_list", "sessions_history", "sessions_send",
      // админ и инфраструктура:
      "gateway", "cron", "process", "nodes",
      // чужая память:
      "memory_search", "memory_get",
      // агент-менеджмент вне её песочницы:
      "agents_list",
    ],
  },
}
```

### 3.2 Binding (маршрутизация в maria)

Добавить в существующий массив `bindings` (рядом с katya-agent):

```json5
{
  agentId: "maria",
  match: {
    channel: "telegram",
    peer: { kind: "direct", id: "1431548892" },
  },
}
```

Порядок: peer-совпадение самое специфичное — конфликта с katya (`932052526`) нет.

### 3.3 Workspace нового агента

Создать `~/.openclaw/agents/maria/workspace/` с файлами:

- `AGENTS.md` — маршрутизация + правило «работай как наставник, следуй MARIA.md».
- `MARIA.md` — **перенести и обновить** режим наставника (см. §6).
- `SOUL.md`, `USER.md`, `TOOLS.md`, `IDENTITY.md`, `HEARTBEAT.md` — bootstrap.
- `memory/` — её собственная память (пустая на старте).

### 3.4 Убрать из глобального deny

Удалить запись `channel:telegram:1431548892` из глобального `tools.toolsBySender` — теперь её права задаются на уровне агента `maria` (иначе глобальный deny перекроет allow агента).

`allowFrom` **оставить как есть** — Мария уже в `channels.telegram.allowFrom` и `accounts.default.allowFrom` (только DM, группы не трогаем).

### 3.5 Обновить main-workspace (AGENTS.md)

Триггер `1431548892 → MARIA.md` в главном `AGENTS.md` станет неактуален (Мария больше не попадает в main). Обновить: убрать/закомментировать этот пункт, оставить остальных (Аркадий, Алиса, «Адвокат»).

## 4. Изоляция сессий (приватность)

`tools.sessions.visibility` остаётся `all` глобально (нужно Кириллу для cross-agent работы — `sessions_send` к kirill-family-advocate, barbershop-verifier и т.д.).

Изоляция Марии достигается **на уровне инструментов агента `maria`**:

- `sessions_spawn` / `sessions_yield` / `subagents` — только её собственные под-агенты (изолированы, привязаны к её requester-сессии).
- `subagents` листит только под-агентов её сессии.
- `sessions_list` / `sessions_history` / `sessions_send` — **запрещены** → не может ни перечислить, ни прочитать, ни написать в чужие сессии.

Итог: она спавнит и управляет своими под-агентами, но чужого не видит.

## 5. Изоляция файловой системы — два уровня

### Уровень 1 (v1, без sandbox) — «мягкая» изоляция

Workspace агента `maria` — дефолтный cwd. Относительные пути внутри workspace, но **абсолютные пути** через `exec` могут достучаться до хоста (в т.ч. `~/.openclaw/openclaw.json` с токеном gateway).

Это приемлемо ТОЛЬКО при доверии к Марии + учебном характере задачи. Реальный риск: через `exec` (`cat /home/user1/.openclaw/openclaw.json`) она может прочитать токен.

### Уровень 2 (v2, рекомендую) — docker-sandbox

Docker доступен. Добавить агенту:

```json5
sandbox: {
  mode: "all",
  scope: "agent",
  workspaceAccess: "rw",
  backend: "docker",
  // network: "none" — по умолчанию, egress закрыт
}
```

Тогда `exec`/`read`/`write`/`edit`/`apply_patch`/`code_execution` выполняются **внутри контейнера**, где смонтирован только её workspace. Абсолютные пути хоста недоступны. `web_search`/`web_fetch`/`image_generate`/`video_generate` — gateway-сторонние, продолжают работать.

Требование: собрать/проверить sandbox-образ (`openclaw-sandbox:bookworm-slim`, см. `docs/gateway/sandboxing.md`), убедиться, что под-агенты (non-main сессии) тоже работают в контейнере.

**Решение на стыке:** v1 делаем сразу (быстро, покрывает 90% задачи обучения); v2 включаем как хардненинг после проверки, что учебный сценарий не сломался.

## 6. Обновление MARIA.md (режим наставника)

Перенести в workspace агента `maria` и скорректировать блок «Что демонстрировать» под новые права:

**Теперь доступно (можно показывать):**
- под-агенты (`sessions_spawn`): «создам агента, который сделает задачу за тебя»;
- навыки (`skill_workshop`): «оформим это как многоразового агента-навык»;
- файлы в своей песочнице (`read`/`write`): «запишем результат в файл»;
- выполнение кода (`exec`/`code_execution`);
- веб (`web_search`/`web_fetch`), картинки, видео, планы/цели.

**По-прежнему закрыто и НЕ упоминать:** чужие сессии, чужой конфиг, планировщик, админ.

**Границы (оставить):** не выбалтывать про Кирилла/других пользователей/внутренности; недоступное — мягко переводить на доступное.

## 7. Критерии приёмки

1. Сообщение от `1431548892` приходит в агент `maria` (проверка: `sessions_list` / логи — sessionKey вида `agent:maria:*`).
2. Мария может `sessions_spawn` под-агента и получить результат.
3. Мария может создать навык через `skill_workshop` (proposal), применить — только после подтверждения Кирилла.
4. Мария может читать/писать файлы в **своём** workspace.
5. Мария **не может**: `sessions_list`/`history`/`send` чужих сессий, `gateway`, `cron`, `memory_*`, читать main-workspace.
6. Кирилл (main) не потерял ничего: `sessions_send` к kirill-family-advocate / barbershop-verifier работает.
7. Аркадий (`534779071`), Алиса (`5216111644`) — без изменений.
8. (v2) `exec` Марии не видит хост-файлы вне контейнера.

## 8. Порядок внедрения

1. Бэкап `openclaw.json` (с меткой времени).
2. Добавить агент `maria` в `agents.list`.
3. Добавить binding.
4. Убрать глобальный `toolsBySender` для Марии.
5. Создать workspace `maria` + перенести/обновить MARIA.md.
6. Обновить главный `AGENTS.md`.
7. Перезапуск gateway (`restart`, не stop+start).
8. Проверить по §7.
9. (опционально) включить sandbox v2.

## 9. Откат

- Вернуть `openclaw.json` из бэкапа.
- Удалить workspace `~/.openclaw/agents/maria/` (через `trash`).
- Перезапуск gateway.

## 10. Открытые вопросы / риски

- **exec + FS-обход:** без sandbox (v1) `exec` читает хост-файлы. Либо v2 sandbox, либо убрать `exec` у Марии (но тогда потеряется генерация PDF).
- **Под-агенты и sandbox:** нужно проверить, что `sessions_spawn` из sandbox-агента корректно наследует/не наследует контейнер.
- **skill_workshop и изоляция:** proposal-скиллы Марии не должны попадать в глобальные навыки Кирилла — проверить скоуп при применении.
