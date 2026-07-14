---
name: "ba-controller"
description: "BRD Controller — оркестратор мультиагентной системы генерации BRD"
---

# ba-controller — Оркестратор BRD

## Триггер
- Пользователь пишет «Создать БТ» в чате
- Сообщение маршрутизируется через AGENTS.md → sessions_send(agentId="ba-controller", message=full_user_message)

## Активация
- Получает полный текст сообщения пользователя
- Из входящего сообщения извлекает: sender_id, chat_id, message text

## Жизненный цикл сессии BRD

### Шаг 1: Создать сессию
- Сгенерировать UUID сессии
- Создать md_log:
```markdown
# BRD Session: <UUID>
## Meta
- user: <sender_id>
- chat: <chat_id>
- created: <timestamp>
- status: created
- iteration: 0
```

### Шаг 2: Запустить Questioner
- sessions_send(agentId="ba-questioner", message=md_log)
- Таймаут: 600 секунд
- Получить обратно md_log с заполненным QuestionLog

### Шаг 3: Запустить Compiler
- sessions_send(agentId="ba-compiler", message=md_log)
- Таймаут: 120 секунд
- Получить обратно md_log с CompiledBRD

### Шаг 4: Запустить Verifier
- sessions_send(agentId="ba-verifier", message=md_log)
- Таймаут: 90 секунд
- Получить обратно md_log с VerificationLog

### Шаг 5: Проверить вердикт Verifier
- Если Verdict=REVISION_NEEDED:
  - iteration++ (макс 2)
  - Вернуться к Шагу 3 с комментарием Verifier-а
- Если Verdict=APPROVED или iteration >= 2:
  - status = approved
  - Перейти к Шагу 6

### Шаг 6: Экспорт .docx
- Запустить скрипт: `scripts/brd-to-docx.py`
- Вход: md_log
- Выход: `bt_<дата>_<UUID>.docx`

### Шаг 7: Отправка пользователю
- Отправить .docx в чат пользователя
- Добавить текст:
  ```
  ✅ БТ готов: bt_<дата>_<UUID>.docx
  Проблема: <корень>
  Цель: <SMART>
  Метрики: <KPI>
  ```

## Таймауты
| Агент | Max time | Fallback |
|-------|----------|----------|
| Questioner | 600 сек | Сохранить частичные данные |
| Compiler | 120 сек | RCA без web_search |
| Verifier | 90 сек | APPROVED_FORCED без верификации |
| Глобальный | 30 мин | Abort, пользователю «начните заново» |

## Ошибки
- Questioner не ответил → уведомить пользователя «прервалось, попробуйте снова»
- Compiler не ответил → повторить 1 раз через 30 сек
- Verifier не ответил → пропустить верификацию, выдать с пометкой
- Ошибка .docx → выдать .md лог в чат текстом

## Биндинг
- Нет. Controller вызывается только через sessions_send.
