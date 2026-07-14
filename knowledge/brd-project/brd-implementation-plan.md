# План работ: Мультиагентная система генерации BRD
## Версия 1.0 — 14.07.2026

---

## Условные обозначения
- ✅ — можно делать параллельно
- ➡️ — строго последовательно
- 🔁 — итерация
- ⚠️ — точка принятия решения

---

## Фаза 0: Подготовка и бекап

### 0.1. Создать резервную копию состояния

```bash
# Текущий workspace
cd /home/user1/.openclaw/workspace
tar -czf /tmp/brd-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
  knowledge/brd-project/ \
  AGENTS.md \
  SOUL.md \
  TOOLS.md \
  MEMORY.md \
  cron/ \
  scripts/

# Конфигурация OpenClaw
cp ~/.openclaw/gateway.yaml /tmp/gateway.yaml.backup.$(date +%Y%m%d)

# GitHub — убедиться что всё закоммичено
cd /home/user1/.openclaw/workspace
git status
git add -A
git commit -m "backup before BRD system: $(date +%Y-%m-%d_%H%M)"
git push
```

### 0.2. Проверить состояние системы
- ✅ `openclaw status` — Gateway работает
- ✅ `openclaw gateway agent list` — текущие агенты
- ✅ `cron list` — текущие задачи
- ✅ `sessions_list` — активные сессии

### 0.3. Прочитать ТЗ полностью
- `knowledge/brd-project/brd-tz-v4.md` — финальная версия
- `knowledge/brd-project/brd-architecture-v1.md` — архитектура (сверяем)

---

## Фаза 1: Создание агентов через Skill Workshop

### 1.1 Создать Controller (оркестратор)
➡️ `skill_workshop(action="create", name="ba-controller", description="BRD Controller — оркестратор мультиагентной системы генерации BRD")`
- SKILL.md: триггер «Создать БТ», жизненный цикл, таймауты, экспорт .docx
- Без биндинга
- agentId: `ba-controller`

### 1.2 Создать Questioner (интервьюер)
✅ параллельно с 1.1
➡️ `skill_workshop(action="create", name="ba-questioner", description="BRD Questioner — старший бизнес-аналитик, интервью с пользователем")`
- SKILL.md: не верь пользователю, 5 Whys, 3 сущности, протокол
- Биндинг к чату Кирилла (telegram:346428630)
- agentId: `ba-questioner`

### 1.3 Создать Compiler (аналитик)
✅ параллельно с 1.1
➡️ `skill_workshop(action="create", name="ba-compiler", description="BRD Compiler — системный архитектор, RCA + Web Search + Impact Mapping")`
- SKILL.md: формула RCA, web_search, SMART, Impact Mapping, Few-Shot
- Без биндинга
- agentId: `ba-compiler`

### 1.4 Создать Verifier (аудитор)
✅ параллельно с 1.1
➡️ `skill_workshop(action="create", name="ba-verifier", description="BRD Verifier — логический аудитор, RCA Integrity + SMART + лингвистический комплаенс")`
- SKILL.md: 3 проверки, итерации до 2, вердикт
- Без биндинга
- agentId: `ba-verifier`

### 1.5 Проверить создание
- ✅ `openclaw gateway agent list` — видны 4 новых агента
- ✅ `ls ~/.openclaw/workspace/skills/ba-*/SKILL.md` — все файлы на месте
- ✅ `memory_search(query="BRD agent ba-controller")` — агент в системе

---

## Фаза 2: Настройка маршрутизации и протокола

### 2.1 Триггер «Создать БТ» в AGENTS.md
➡️ отредактировать `AGENTS.md`
- Добавить раздел: **«Создать БТ» — триггер для Controller**
- Правило: Кирилл (346428630) → `ba-controller`
- Формат: как у Адвоката (sessions_send, дождаться ответа)

### 2.2 Настроить биндинг Questioner-а
➡️ `openclaw gateway agent update ba-questioner --bind telegram:346428630`
- Проверить: sessions_send от Controller → Questioner → пишет в чат
- Проверить: сообщения Кирилла НЕ идут напрямую Questioner-у (только через Controller)

### 2.3 Настроить .md → .docx скрипт
➡️ создать `scripts/brd-to-docx.py`
- python-docx
- Поля: Meta → Description Goal Metrics Impacts References
- Вход: md_log (строка или файл)
- Выход: `bt_<дата>_<UUID>.docx`

---

## Фаза 3: Тестирование

### 3.1 Модульные тесты (каждый агент изолированно)

#### Test 1: Controller — триггер
1. Написать «Создать БТ» в чат
2. ✅ Ожидание: Controller получает сообщение, создаёт UUID, отправляет md_log Questioner-у
3. ⚠️ Результат: триггер сработал / не сработал

#### Test 2: Questioner — интервью
1. Изолированная отправка md_log от Controller
2. ✅ Questioner начинает диалог в чате
3. Ответить на 5+ вопросов
4. ✅ Questioner завершает, возвращает md_log с QuestionLog
5. ⚠️ Результат: диалог состоялся, лог заполнен

#### Test 3: Questioner — таймаут
1. Отправить md_log, не отвечать 16 минут
2. ✅ Questioner через 15 мин: «Вы не отвечаете, сохраняю что есть»
3. ⚠️ Результат: таймаут сработал, частичные данные сохранены

#### Test 4: Compiler — RCA
1. Отправить md_log с QuestionLog
2. ✅ Compiler возвращает md_log с CompiledBRD (RCA + цель + метрики + импакт)
3. ⚠️ Результат: формула RCA соблюдена, есть SMART, есть web_search

#### Test 5: Verifier — аппрув
1. Отправить md_log с CompiledBRD (хороший)
2. ✅ Verifier возвращает ✅ по всем проверкам
3. ⚠️ Результат: APPROVED

#### Test 6: Verifier — ревизия
1. Отправить md_log с CompiledBRD (сломанный — например, человеческий фактор как корень)
2. ✅ Verifier возвращает ❌ + Comment
3. Отправить Compiler-у с комментарием
4. ✅ Compiler исправляет
5. ✅ Verifier на 2-й раз ✅
6. ⚠️ Результат: итерация сработала

### 3.2 Интеграционные тесты (полный пайплайн)

#### Test 7: Полный цикл «Создать БТ»
1. Написать «Создать БТ»
2. Пройти интервью (7-10 вопросов)
3. ✅ Через < 20 мин получен .docx
4. ✅ .docx содержит: Проблема → Цель → Метрики → Импакты → Источники
5. ⚠️ Результат: полный цикл работает

#### Test 8: Compiler timeout
1. Отправить Compiler-у md_log (заставить ждать >120 сек)
2. ✅ Controller обрабатывает таймаут: RCA без web_search
3. ⚠️ Результат: fallback сработал

#### Test 9: Verifier timeout
1. Отправить Verifier-у md_log (заставить ждать >90 сек)
2. ✅ Controller: пропускает верификацию, .docx с пометкой «не верифицирован»
3. ⚠️ Результат: fallback сработал

#### Test 10: 3 итерации Verifier → Compiler
1. Создать такой CompiledBRD, что Verifier 3 раза вернёт ❌
2. ✅ Controller на 3-й раз: APPROVED_FORCED
3. ⚠️ Результат: защита от бесконечного цикла

### 3.3 Проверка экспорта .docx
#### Test 11: Формат .docx
1. Получить .docx
2. Открыть вручную (или через python-docx прочитать)
3. ✅ Секции: Description, Goal, Metrics, Impacts, References
4. ✅ Читабельно, форматирование не сломано
5. ⚠️ Результат: .docx корректен

---

## Фаза 4: Приёмка

### 4.1 Проверка с Кириллом
- ✅ Ты запускаешь «Создать БТ» — всё работает
- ✅ Проверяешь .docx — формат устраивает
- ✅ Качество интервью — достаточно деталей
- ⚠️ Твоё решение: ✅ принимаем / 🔁 доработки / ❌ откат

### 4.2 Чистка наследия BMAD (если принято)
➡️ Отдельная задача (не в этом плане):
- Удаление агента `mamkin-analitik`
- Удаление канала `mamkin-telegram`
- Архивация BMAD-кода в `archive/bmad/`
- Обновление bt.html / index.html

---

## Фаза 5: План отката

### Когда откатываем
- Любая из тестов Фазы 3 не прошла и не чинится за 2 попытки
- Ты сказал «откат»
- Прошло > 3 часов и пайплайн не собран

### Шаг 1: Восстановить бекап
```bash
cd /home/user1/.openclaw/workspace
# Найти последний бекап
ls -la /tmp/brd-backup-*.tar.gz | tail -1

# Распаковать поверх (только нужные файлы)
tar -xzf /tmp/brd-backup-2026*.tar.gz
```

### Шаг 2: Удалить новых агентов
```bash
openclaw gateway agent remove ba-controller
openclaw gateway agent remove ba-questioner
openclaw gateway agent remove ba-compiler
openclaw gateway agent remove ba-verifier
```

### Шаг 3: Удалить SKILL.md
```bash
rm -rf ~/.openclaw/workspace/skills/ba-*
```

### Шаг 4: Откатить AGENTS.md
```bash
cd /home/user1/.openclaw/workspace
git checkout AGENTS.md  # если был изменён
```

### Шаг 5: Откатить конфиг
```bash
cp /tmp/gateway.yaml.backup.* ~/.openclaw/gateway.yaml
openclaw restart
```

### Шаг 6: Проверить что вернулись
- ✅ `openclaw status` — Gateway работает
- ✅ old cron работает
- ✅ чат отвечает как раньше
- ✅ `ls skills/` — старые скиллы, без ba-*

### Шаг 7: Сделать коммит отката
```bash
git add -A
git commit -m "rollback: BRD system — back to pre-BRD state"
git push
```

---

## Тайминг

| Фаза | Описание | Оценка | Зависит от |
|------|----------|--------|-----------|
| 0 | Бекап + подготовка | 10 мин | — |
| 1 | Создание агентов (4 шт) | 30 мин | Фаза 0 |
| 2 | Маршрутизация + скрипт | 20 мин | Фаза 1 |
| 3 | Тестирование (11 тестов) | 60 мин | Фаза 2 |
| 4 | Приёмка | 15 мин | Фаза 3 |
| **Итого** | | **~2 часа 15 мин** | |

---

## Чеклист перед стартом

- [ ] Бекап сделан (`tar -czf /tmp/brd-backup-*.tar.gz ...`)
- [ ] GitHub: всё закоммичено
- [ ] `openclaw status` — OK
- [ ] ТЗ прочитано (`brd-tz-v4.md`)
- [ ] Ты подтвердил старт
