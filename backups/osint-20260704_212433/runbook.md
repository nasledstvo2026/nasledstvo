# OSINT-дайджест — Runbook

**Проект:** OSINT-дайджест  
**Версия:** 1.0 (04.07.2026)  
**Сайт:** https://nasledstvo2026.github.io/nasledstvo/osint.html

---

## 1. Архитектура

### Фазная архитектура A/B/C (3 независимые cron-задачи)

```
Фаза A (сбор)          → memory/osint/osint-raw-data.json    [180s]
Фаза B (анализ+HTML)   → osint.html + osint-seen.md          [300s]
Фаза C (публикация)    → git push → GitHub Pages             [60s]
```

### Расписание (3 цикла в день)

| Время | Фаза | Таймаут | Джоб |
|-------|------|---------|------|
| 05:30 / 13:30 / 19:30 | A | 180s | osint-phase-a-* |
| 05:50 / 13:50 / 19:50 | B | 300s | osint-phase-b-* |
| 05:55 / 13:55 / 19:55 | C | 60s | osint-phase-c-* |

**Зазоры:** A→B = 20 мин, B→C = 5 мин. Если B не завершилась — C публикует старый HTML.

### Файлы проекта

| Файл | Назначение |
|------|-----------|
| `memory/osint/osint-raw-data.json` | Сырые данные от Фазы A (перезаписывается каждый цикл) |
| `memory/osint/osint-seen.md` | Кэш фактов для дедупликации (накапливается) |
| `memory/osint/osint-log.md` | Лог операций (обнуляется при старте Фазы A) |
| `osint.html` | Итоговая страница дайджеста |
| `projects/osint/breq.md` | Бизнес-требования |
| `projects/osint/srs.md` | Системные требования |
| `projects/osint/test-cases.md` | Тестовые кейсы |
| `projects/osint/plan.md` | План-график |
| `skills/osint-expert/SKILL.md` | Skill с полными промптами для всех фаз |

---

## 2. Мониторинг

### Проверка статуса дайджеста
```bash
# Страница доступна?
curl -s -o /dev/null -w "%{http_code}" "https://nasledstvo2026.github.io/nasledstvo/osint.html"

# Когда был последний коммит?
cd /home/user1/.openclaw/workspace && git log --oneline -1

# Лог выполнения
cat /home/user1/.openclaw/workspace/memory/osint/osint-log.md

# Сколько фактов в кэше?
wc -l /home/user1/.openclaw/workspace/memory/osint/osint-seen.md

# Сколько сырых данных?
python3 -c "import json; print(len(json.load(open('/home/user1/.openclaw/workspace/memory/osint/osint-raw-data.json'))))"
```

### Проверка cron-задач
```bash
# Список всех OSINT-задач
openclaw cron list --agent main | grep osint
```

### Логирование ошибок
- Ошибки cron пишутся в Gateway: `openclaw cron runs --agent main <jobId>`
- Алёрты при 2+ последовательных ошибках → уведомление Кириллу (@Kirill_syst)
- Cool down ошибок: 1 час

---

## 3. Типовые инциденты

### 3.1. DeepSeek API «залип»
**Симптом:** `cron: job execution timed out (last phase: model-call-started)`
**Причина:** DeepSeek stall в часы пик (08:00–09:00 МСК = 13:00–14:00 CST)
**Действие:** Автоматическое — следующая фаза по расписанию перезапустит цикл. Если 2 подряд ошибки — приходит алерт Кириллу.
**Ручное:** Запустить force run пропущенной фазы.

### 3.2. Фаза A не собрала данные
**Симптом:** `osint-raw-data.json` пуст или содержит < 5 фактов
**Причина:** Источники недоступны или SearXNG заблокирован
**Действие:**
```bash
# Запустить Фазу A вручную
openclaw cron run --force --agent main osint-phase-a-0630
# Или обнулить лог и запустить
echo "# osint-log.md" > /home/user1/.openclaw/workspace/memory/osint/osint-log.md
```

### 3.3. Публикация не удалась
**Симптом:** `git push` ошибка или HTTP 404 на странице
**Действие:**
```bash
cd /home/user1/.openclaw/workspace
git status
git add osint.html
git commit -m "osint: ручная публикация YYYY-MM-DD-HHMM"
git push origin master
```

### 3.4. Cloudflare Tunnel изменился (не актуально для OSINT — нет туннеля)

---

## 4. Обновление промптов

Промпты хранятся **в теле cron-задач** (9 задач) и **в skill osint-expert** (как источник истины).

### Изменить промпт во всех задачах
```bash
# 1. Обновить skill
openclaw skill update osint-expert ./projects/osint/new-skill.md

# 2. Обновить каждую из 9 cron-задач через Gateway API
# (см. секцию 5 — процедура)
```

### Текущие лимиты моделей
- deepseek-chat (primary)
- deepseek-v4-flash (fallback)
- Таймаут Фазы A: 180s
- Таймаут Фазы B: 300s
- Таймаут Фазы C: 60s

---

## 5. Обновление cron-задач (процедура)

### Список всех задач
| # | Имя | Job ID |
|---|-----|--------|
| 1 | osint-phase-a-0630 | `cron get osint-phase-a-0630` |
| 2 | osint-phase-b-0650 | `cron get osint-phase-b-0650` |
| 3 | osint-phase-c-0655 | `cron get osint-phase-c-0655` |
| 4 | osint-phase-a-1430 | `cron get osint-phase-a-1430` |
| 5 | osint-phase-b-1450 | `cron get osint-phase-b-1450` |
| 6 | osint-phase-c-1455 | `cron get osint-phase-c-1455` |
| 7 | osint-phase-a-2030 | `cron get osint-phase-a-2030` |
| 8 | osint-phase-b-2050 | `cron get osint-phase-b-2050` |
| 9 | osint-phase-c-2055 | `cron get osint-phase-c-2055` |

**Изменение:** `openclaw cron update <jobId> '{"payload":{"message":"..."}}'`

---

## 6. Контакты

- **Владелец:** Кирилл (@Kirill_syst, Telegram ID: 346428630)
- **Уведомления об ошибках:** failureAlert после 2 ошибок → Telegram Кириллу
- **Все остальные:** страница публичная, без авторизации

---

## 7. Дата последнего обновления

04.07.2026 — первая версия runbook
