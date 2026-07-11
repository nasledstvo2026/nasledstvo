# План отката — Адвокат (Rollback Plan)

## Катастрофический откат (полный возврат)

Применять, если:
- Агент не отвечает после регистрации
- Сломалась маршрутизация других агентов (Катрин, Мария, Катя)
- Main-сессия перестала отвечать
- Gateway не стартует

| Шаг | Команда | Что проверяем |
|-----|---------|---------------|
| 1 | `openclaw gateway stop` | Gateway остановлен |
| 2 | `cp /home/user1/.openclaw/backups/openclaw.json.2026-07-12-pre-advocate /home/user1/.openclaw/openclaw.json` | Восстановлен оригинальный конфиг |
| 3 | `cp /home/user1/.openclaw/workspace/AGENTS.md.2026-07-12-pre-advocate /home/user1/.openclaw/workspace/AGENTS.md` | Восстановлена маршрутизация |
| 4 | `cp /home/user1/.openclaw/workspace/MEMORY.md.2026-07-12-pre-advocate /home/user1/.openclaw/workspace/MEMORY.md` | Восстановлена память (без Адвоката) |
| 5 | `rm -rf /home/user1/.openclaw/agents/kirill-family-advocate` | Удалён агент |
| 6 | `openclaw gateway start` | Gateway запущен |
| 7 | Проверить bindings (Катрин, Мария, Катя) | Все живы |
| 8 | Кирилл пишет в main-чат | Лунт отвечает |
| 9 | `git checkout -- .` в workspace (опционально, если изменения мешают) | Файлы проекта останутся (safe) |

**Сообщить:** «Откат выполнен. Адвокат не активирован. Причина: [опиcaть].»

---

## Быстрый откат (если проблема только в маршрутизации)

| Шаг | Команда |
|-----|---------|
| 1 | `openclaw gateway stop` |
| 2 | Восстановить `/home/user1/.openclaw/workspace/AGENTS.md` из бэкапа |
| 3 | Если менялся конфиг — восстановить его из бэкапа |
| 4 | `openclaw gateway start` |

---

## Потерянные данные при откате

**Безопасно (ничего не теряется):**
- Проектные файлы `projects/advocate/` — не трогаем
- `knowledge/kirill/family-law.md` — не трогаем
- `dialogue-log.md` — остаётся

**Что придётся переделать:**
- Apply SKILL.md (через workshop)
- Повторная регистрация агента
- Повторная настройка isolated session

**Смежные продукты не пострадают:** никакие bindings не менялись, cron-задачи не трогались.
