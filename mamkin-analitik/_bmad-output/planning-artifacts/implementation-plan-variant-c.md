# План реализации — Вариант C (Гибрид)

## Обзор архитектуры

```
@Sbernasledtsvo_bot ──→ OpenClaw gateway
                              │
                    ┌─────────┴─────────┐
                    │                   │
          create-bt-agent        bt-generator-agent
          (основной диалог)      (фоновый, генерация)
                    │                   │
                    ▼                   ▼
          ┌─────────────────┐  ┌──────────────────┐
          │ questioner      │  │ generator         │
          │ compiler        │  │ ← draft-generator │
          │ controller      │  │ ← github-pages    │
          │ learning-engine │  └──────────────────┘
          │ session-manager │
          └─────────────────┘
                    │                   │
                    └─────────┬─────────┘
                              ▼
                    Session Context (JSON)
                    session-storage/active/
                    session-storage/completed/
```

### Команды
| Команда | Обработчик | Описание |
|---------|-----------|----------|
| `/создатьбт` | create-bt-agent | Начать новую сессию опроса |
| `/start` | create-bt-agent | Проверка/восстановление сессии |
| `/cancel` | create-bt-agent | Завершить сессию |
| `/history` | create-bt-agent | История сессий |
| `/back` | create-bt-agent | Вернуться к предыдущему блоку |

---

## Этап 1. Подготовка инфраструктуры (0.5 дня)

### 1.1 Обновить config.yaml
Изменить:
- `telegram.bot_token_env` → используется @Sbernasledtsvo_bot (единый)
- Убрать `session.encryption: aes-256`
- Убрать `telegram.port` / `webhook_path` (управление через gateway)
- Добавить `telegram.commands` для `/создатьбт`

### 1.2 Создать точки входа агентов
- `agents/create-bt-agent/index.js` — главный агент диалога
- `agents/bt-generator-agent/index.js` — фоновый агент генерации

### 1.3 Настроить OpenClaw gateway
- Зарегистрировать команду `/создатьбт` → `create-bt-agent`
- Привязать оба агента к @Sbernasledtsvo_bot

**Файлы:**
- `config.yaml` (обновление)
- `agents/create-bt-agent/index.js` (создание)
- `agents/bt-generator-agent/index.js` (создание)

---

## Этап 2. Создание create-bt-agent (1.5 дня)

### 2.1 Оркестратор (агент-роутер)
Единая точка входа. Принимает сообщение от OpenClaw gateway, определяет тип:

```javascript
// Псевдокод
async function handleMessage(ctx) {
  const { sessionId, telegramUserId, text } = ctx;

  // Загрузить/создать сессию
  let session = await sessionManager.load(sessionId);
  if (!session) {
    session = await sessionManager.create({ telegramUserId });
    return surveyEngine.startSurvey(session);
  }

  // Определить фазу
  switch (session.phase) {
    case 'survey':
      return surveyEngine.processAnswer(session, text);
    case 'compile':
      return compiler.generate(session);
    case 'review':
      return controller.validate(session);
    case 'waiting_generator':
      return checkGeneratorStatus(session);
    default:
      return sessionCommands.handle(session, text);
  }
}
```

### 2.2 Фаза 1: Survey (опрос)
Используем существующий `lib/survey-engine.js` как модуль.

- `surveyEngine.startSurvey(session)` → возвращает первый вопрос
- `surveyEngine.processAnswer(session, text)` → возвращает следующий вопрос или маркер завершения

### 2.3 Фаза 2: Compile (составление)
Используем `lib/compiler.js` и `agents/compiler/prompt.md`. Вызывается при `session.phase = 'compile'`.

- `compiler.generate(context)` → формирует текст БТ по 7 блокам
- Результат → поле `draft` в Session Context

### 2.4 Фаза 3: Controller (контроль качества)
Используем `agents/controller/index.js` и `agents/controller/prompt.md`.

- `controller.validate(draft)` → проверка полноты (7/7 блоков) + глубины
- Если OK → `session.phase = 'generation'`
- Если нет → возвращаем на доработку пользователю (`session.phase = 'survey'`, `session.revisionBlock = X`)

### 2.5 Запуск bt-generator-agent
При `session.phase = 'generation'`:

1. Сохранить Session Context
2. Сообщить пользователю: "⏳ Ваш документ готовится. Это займёт около минуты."
3. Запустить bt-generator-agent через `sessions_spawn` с параметрами: sessionId, sessionContextPath, telegramUserId
4. `session.phase = 'waiting_generator'`

### 2.6 Проверка статуса генерации
При следующем сообщении пользователя (если `phase = 'waiting_generator'`):

1. Прочитать Session Context
2. Если `generationStatus === 'done'` → отправить ссылки пользователю, отметить завершение
3. Если `generationStatus === 'failed'` → предложить повторить
4. Если `generationStatus === 'in_progress'` → "Ваш документ ещё готовится..."

### 2.7 Команды управления
- `/start` → sessionCommands.handleStart(session)
- `/history` → sessionCommands.handleHistory(telegramUserId)
- `/cancel` → sessionCommands.handleCancel(session)
- `/back` → sessionCommands.handleBack(session)

Используем `lib/session-commands.js` (существует).

**Файлы (создание/изменение):**
- `agents/create-bt-agent/index.js` (создание)
- `agents/create-bt-agent/prompt.md` (создание)

---

## Этап 3. Создание bt-generator-agent (2 дня)

### 3.1 Фоновый агент
Запускается через `sessions_spawn` с параметрами:
```json
{
  "sessionId": "...",
  "sessionContextPath": "session-storage/completed/XXX.json",
  "telegramUserId": 346428630
}
```

### 3.2 Генерация DOCX
- Читает Session Context из файла
- Вызывает `draft-generator.generate(context)` → `*.docx`
- Сохраняет DOCX в `session-storage/completed/{sessionId}/`

### 3.3 Генерация веб-версии
- `draft-generator.generateHtml(context)` → `index.html`
- Использует `agents/generator/html-gen.py` (существует)

### 3.4 Публикация на GitHub Pages
- `githubPages.publish(sessionId, docxPath, htmlPath)`
- Получает URL: `docxUrl`, `htmlUrl`

### 3.5 Отправка результата пользователю
- Обновляет Session Context: `generationStatus: 'done'`, `docxUrl`, `htmlUrl`, `completedAt`
- Сохраняет в `session-storage/completed/{sessionId}/context.json`
- Отправляет сообщение в Telegram через gateway: "✅ Ваш документ готов! DOCX | Веб-версия"

### 3.6 Обработка ошибок
- При ошибке генерации → `generationStatus: 'failed'`, `error: '...'`
- Основной агент при следующем сообщении покажет: "⚠️ Произошла ошибка при генерации. Попробуйте ещё раз."
- Retry: до 3 попыток с exponential backoff (используем `lib/retry.js`)

**Файлы (создание/изменение):**
- `agents/bt-generator-agent/index.js` (создание)
- `agents/bt-generator-agent/prompt.md` (создание)

---

## Этап 4. Интеграция и тесты (1 день)

### 4.1 Интеграционные тесты
- Полный цикл: `/создатьбт` → опрос → компиляция → контроль → генерация → публикация → ссылки
- Восстановление сессии после сбоя
- Параллельные сессии (2+ пользователя)
- Падение генератора → retry / уведомление пользователя

### 4.2 Очистка legacy
- `index.js` (точка входа старого бота) → удалить или переименовать
- `lib/telegram-connector.js` → удалить (gateway управляет)
- `lib/crypto.js` → удалить (шифрование снято)
- `.env` → очистить от `TELEGRAM_BOT_TOKEN` старого бота

### 4.3 Обновить sprint-status.yaml
- Отметить Epic 6: "Интеграция с @Sbernasledtsvo_bot" со статусом `in-progress`
- Отметить Epic 4 (генерация) как пересмотренный для фонового агента

---

## Сводка по файлам

### Новые файлы
| Файл | Назначение | Размер |
|------|-----------|--------|
| `agents/create-bt-agent/index.js` | Основной агент диалога | ~200 строк |
| `agents/create-bt-agent/prompt.md` | Системный промпт для create-bt-agent | ~50 строк |
| `agents/bt-generator-agent/index.js` | Фоновый агент генерации | ~150 строк |
| `agents/bt-generator-agent/prompt.md` | Системный промпт для генерации | ~30 строк |

### Изменяемые файлы
| Файл | Изменения |
|------|-----------|
| `config.yaml` | Убрать шифрование, добавить команду /создатьбт, убрать pipeline order |
| `lib/session-manager.js` | Убрать crypto.js зависимость (шифрование снято) |

### Удаляемые файлы
| Файл | Причина |
|------|---------|
| `index.js` | Старый polling entry point |
| `lib/telegram-connector.js` | Gateway управляет Telegram |
| `lib/crypto.js` | Шифрование снято 09.07.2026 |

### Неизменяемые модули (переиспользование 1:1)
| Модуль | Назначение |
|--------|-----------|
| `lib/survey-engine.js` | Движок опроса (~3600 строк) |
| `lib/compiler.js` | Составление текста БТ |
| `lib/session-manager.js` (без crypto) | Управление сессиями |
| `lib/session-context.js` | Контекст между агентами |
| `lib/session-commands.js` | Команды /start, /history, /cancel |
| `lib/template-engine.js` | Загрузка immutable шаблона |
| `lib/learning-engine.js` | Самообучение |
| `lib/draft-generator.js` | DOCX + HTML генерация |
| `lib/github-pages.js` | Публикация на GitHub Pages |
| `lib/logger.js` | Логирование |
| `lib/retry.js` | Exponential backoff |
| `lib/whitelist.js` | Управление доступом |
| `lib/history-recorder.js` | Запись истории |
| `data/template.json` | Шаблон БТ (immutable) |
| `data/depth-config.json` | Пороги глубины |
| `data/whitelist.json` | Белый список |
| `agents/questioner/` | Логика опросчика |
| `agents/compiler/` | Логика составителя |
| `agents/controller/` | Логика контролёра |
| `agents/generator/` | Логика генератора (python-docx) |

---

## Архитектурная схема взаимодействия

```
                        @Sbernasledtsvo_bot
                              │
                    ┌─────────▼─────────┐
                    │  OpenClaw Gateway  │
                    │  (маршрутизация)   │
                    └─────────┬─────────┘
                              │
                    команда /создатьбт
                              │
                    ┌─────────▼─────────────────┐
                    │  create-bt-agent          │
                    │  (единственная точка входа)│
                    └─────────┬─────────────────┘
                              │
                    ┌─────────▼──────────────────┐
                    │  Session Manager           │
                    │  → create/load/store       │
                    └─────────┬──────────────────┘
                              │
                    ┌─────────▼──────────────────┐
                    │  Фаза: SURVEY              │
                    │  survey-engine.js          │
                    │  → вопросы, глубина, риски │
                    └─────────┬──────────────────┘
                              │ (все блоки заполнены)
                              ▼
                    ┌─────────────────────────────┐
                    │  Фаза: COMPILE              │
                    │  compiler (prompt + lib)     │
                    │  → текст БТ по 7 блокам     │
                    └─────────┬──────────────────┘
                              │
                              ▼
                    ┌─────────────────────────────┐
                    │  Фаза: REVIEW               │
                    │  controller (prompt + rules) │
                    │  → проверка полноты/глубины │
                    └─────────┬──────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │ OK?              │ NO → survey (revision)
                    ▼                   ▼
          ┌─────────────────┐    ┌─────────────────┐
          │ Фаза: GENERATION│    │ Вернуться к     │
          │                 │    │ пользователю    │
          │ → сообщение     │    └─────────────────┘
          │   "готовится..."│
          │ → spawn gen     │
          └────────┬────────┘
                   │
                   ▼
         ┌─────────────────────────┐
         │ bt-generator-agent      │
         │ (фоновый, async)        │
         │                         │
         │ draft-generator.js      │
         │ → DOCX (python-docx)    │
         │ → HTML (html-gen.py)    │
         │ → GitHub Pages (push)   │
         │ → Session Context: done │
         └────────┬────────────────┘
                   │
                   ▼ (проверка при следующем сообщении)
         ┌─────────────────────────┐
         │ create-bt-agent         │
         │ → читает status=done   │
         │ → отправляет ссылки     │
         │ → завершает сессию      │
         └─────────────────────────┘
```

### Поток данных

```
Session Context (JSON):
{
  "sessionId": "abc123",
  "telegramUserId": 346428630,
  "status": "in_progress" | "waiting_generator" | "completed",
  "phase": "survey" | "compile" | "review" | "generation" | "done",
  "currentBlock": 1,
  "currentSubsection": "1.1",
  "answers": {
    "1.1": { "L1": "ответ...", "depth": 0.8 },
    "1.2": { "L1": "ответ...", "L2": "уточнение...", "depth": 0.5 }
  },
  "risks": [...],
  "draft": "текст БТ...",
  "qualityGate": { "passed": true, "scores": {...} },
  "generationStatus": "pending" | "in_progress" | "done" | "failed",
  "docxUrl": null,
  "htmlUrl": null,
  "error": null
}
```

---

## Риски и митигации

| Риск | Митигация |
|------|-----------|
| Генератор падает при spawn | Retry 3x, fallback — предложить повторить позже |
| Session Context race condition | Generator только пишет, main-agent только читает |
| Пользователь уходит во время генерации | Ссылки придут в историю, можно запросить `/history` |
| Контекст main-agent растёт | Очищать local context между сообщениями, хранить только sessionId |
| Gateway не поддерживает spawn | Альтернатива: генератор в том же агенте через exec (child_process) |

---

## Оценка времени (итого: **4 дня**)

| Этап | Дней |
|------|------|
| 1. Подготовка инфраструктуры | 0.5 |
| 2. create-bt-agent | 1.5 |
| 3. bt-generator-agent | 2.0 |
| 4. Интеграция и тесты | 1.0 |
| **Итого** | **4.0** |

*Примечание: 3 дня — если агент generator уже проверен и требует минимальной доработки. 4 дня — с учётом тестов и отладки интеграции.*
