# 🔄 OpenClaw Upgrade Plan — v2026.7.1-2 → Latest Stable

## 1. Инвентаризация (выполнена)
| Компонент | Статус | Размер |
|-----------|--------|--------|
| OpenClaw | 2026.7.1-2 (0790d9f) | npm global |
| Gateway | systemd user, running | pid активен |
| Node.js | v24.18.0 | — |
| Диск | 30G, 5.2G free | 82% used |
| Память | 3.8G, 2.7G used | 1.1G available |
| Git репо | nasledstvo2026/nasledstvo | clean |
| Сервисы | OpenClaw gateway, cloudflared-aidj, aidj-server | — |

## 2. План резервного копирования (Backup Plan)

### Pre-upgrade backup — полный снэпшот системы

**Путь хранения:** `/home/user1/.openclaw/workspace/backup/pre-upgrade-2026-07-26/`

#### Что бэкапим:

| # | Компонент | Путь | Назначение |
|---|-----------|------|------------|
| 1 | Конфиг OpenClaw | `~/.openclaw/openclaw.json` | Основной конфиг |
| 2 | Workspace (git) | `~/.openclaw/workspace/` | Код, html, scripts |
| 3 | Агенты | `~/.openclaw/agents/` | Конфиги агентов + shared data |
| 4 | Плагины | `~/.openclaw/npm/` | Установленные npm плагины |
| 5 | Extensions | `~/.openclaw/extensions/` | BMad Method |
| 6 | .env / credentials | `~/.openclaw/.env`, `~/.openclaw/credentials/` | API ключи, токены |
| 7 | SSH ключи | `~/.ssh/` | GitHub, VPS2 доступ |
| 8 | Dropbox | `~/.dropbox_*` | OAuth токены |
| 9 | Cloudflared | `~/.cloudflared/` | Туннельные credentials |
| 10 | NPM global list | `npm list -g --depth=0` | Версия для отката |
| 11 | Cron jobs dump | `openclaw cron list` | Полная выгрузка задач |
| 12 | Gateway status | `openclaw status` | Слепок состояния |

#### Процедура бэкапа (выполняется перед обновлением):

```bash
# 1. Создать директорию бэкапа
BACKUP_DIR="/home/user1/.openclaw/workspace/backup/pre-upgrade-$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR"

# 2. Бэкап конфигов
cp ~/.openclaw/openclaw.json "$BACKUP_DIR/openclaw.json"
cp -r ~/.openclaw/agents/shared/ "$BACKUP_DIR/agents-shared/"
[[ -f ~/.openclaw/.env ]] && cp ~/.openclaw/.env "$BACKUP_DIR/.env"
[[ -d ~/.openclaw/credentials ]] && cp -r ~/.openclaw/credentials/ "$BACKUP_DIR/credentials/"

# 3. Бэкап workspace (исключая .git, node_modules, mp3)
rsync -a --exclude='.git' --exclude='node_modules' --exclude='*.mp3' \
  ~/.openclaw/workspace/ "$BACKUP_DIR/workspace/"

# 4. NPM версия
npm list -g --depth=0 > "$BACKUP_DIR/npm-global.txt"

# 5. SSH и токены
cp -r ~/.ssh/ "$BACKUP_DIR/ssh/"
cp ~/.dropbox_* "$BACKUP_DIR/" 2>/dev/null || true
cp -r ~/.cloudflared/ "$BACKUP_DIR/cloudflared/" 2>/dev/null || true

# 6. Дамп cron-задач
openclaw cron list > "$BACKUP_DIR/cron-jobs.json" 2>&1

# 7. Статус системы
openclaw status > "$BACKUP_DIR/pre-upgrade-status.txt" 2>&1

echo "✅ Backup complete: $BACKUP_DIR"
```

## 3. План восстановления (Disaster Recovery Plan)

### Сценарий A: Gateway не стартует после обновления

```bash
# 1. Откатить версию npm
npm install -g openclaw@2026.7.1-2
# 2. Перезагрузить gateway
systemctl --user restart openclaw-gateway
# 3. Проверить статус
openclaw status
```

### Сценарий B: Конфиг повреждён / плагины сломались

```bash
# 1. Восстановить конфиг из бэкапа
cp ~/.openclaw/workspace/backup/pre-upgrade-*/openclaw.json ~/.openclaw/openclaw.json
# 2. Перезагрузить gateway
systemctl --user restart openclaw-gateway
```

### Сценарий C: Полный крах (восстановление на чистый VPS)

#### Этап 1 — Восстановление с GitHub:
```bash
# 1. Установить зависимости
sudo apt install git nodejs npm
sudo npm install -g n && sudo n lts

# 2. Склонировать репозиторий
mkdir -p ~/.openclaw
cd ~/.openclaw
git clone git@github.com:nasledstvo2026/nasledstvo.git workspace

# 3. Установить OpenClaw
npm install -g openclaw@2026.7.1-2
```

#### Этап 2 — Восстановление из локального бэкапа:
```bash
# 4. Восстановить конфиг
cp backup/pre-upgrade-*/openclaw.json ~/.openclaw/openclaw.json
cp -r backup/pre-upgrade-*/.env ~/.openclaw/.env
cp -r backup/pre-upgrade-*/credentials ~/.openclaw/credentials/
cp -r backup/pre-upgrade-*/ssh/ ~/.ssh/
cp -r backup/pre-upgrade-*/agents-shared/ ~/.openclaw/agents/shared/

# 5. Настроить права
chmod 600 ~/.ssh/id_ed25519
chmod 600 ~/.ssh/new-vps-key

# 6. Запустить gateway
openclaw gateway start
```

#### Этап 3 — Восстановление плагинов (если нужно):
```bash
openclaw plugins install @openclaw/deepseek-provider 2>/dev/null || true
openclaw plugins install @openclaw/searxng-plugin 2>/dev/null || true
```

## 4. Пошаговый план обновления (Upgrade Procedure)

### Шаг 1: Бэкап
- [x] Выполнить полный бэкап по плану выше
- [x] git commit + git push последних изменений
- [x] Убедиться, что backup существует и не пуст

### Шаг 2: Подготовка
- [x] Проверить disk usage (5.2G free — достаточно)
- [x] Проверить, что нет запущенных критических задач
- [x] Убедиться, что gateway работает
- [x] Дамп всех cron-задач сохранён

### Шаг 3: Обновление npm пакета
```bash
npm install -g openclaw@latest
```

### Шаг 4: Проверка gateway
- [ ] `openclaw status` — Gateway alive?
- [ ] `openclaw gateway config.schema.lookup models` — модели видны?
- [ ] `openclaw plugins list` — плагины работают?

### Шаг 5: Проверка моделей
- [ ] `deepseek/deepseek-v4-flash` — отвечает?
- [ ] `deepseek/deepseek-v4-pro` — отвечает?
- [ ] Telegram — приходит сообщение?

### Шаг 6: Проверка cron-задач
- [ ] Список cron-задач не изменился
- [ ] Каждая задача имеет правильную модель
- [ ] `failureAlert` настроены

### Шаг 7: Проверка агентов
- [ ] Агент main отвечает
- [ ] Telegram bindings работают

## 5. Тест-кейсы (Test Cases)

### TC-01: Gateway alive
**Проверка:** `openclaw status`
**Ожидание:** `Gateway alive`, версия `2026.7.2+`

### TC-02: DeepSeek модели
**Проверка:** Отправить короткий prompt
**Ожидание:** Модель отвечает, нет ошибок API

### TC-03: Telegram delivery
**Проверка:** Написать боту в Telegram
**Ожидание:** Ответ приходит в Telegram, rich message работает

### TC-04: Cron jobs intact
**Проверка:** `openclaw cron list`
**Ожидание:** Все задачи на месте, модели валидны

### TC-05: Config valid
**Проверка:** Gateway без ошибок конфига
**Ожидание:** `Config warnings` отсутствуют (кроме известных)

### TC-06: Плагины
**Проверка:** `openclaw plugins list`
**Ожидание:** clickclack и zai больше не показывают ошибку (если обновление их починило)

### TC-07: Модель deepseek
**Проверка:** `openclaw session_status`
**Ожидание:** model=deepseek/deepseek-v4-flash, работающий

### TC-08: Версия
**Проверка:** `openclaw --version`
**Ожидание:** Новая версия (выше 2026.7.1-2)
