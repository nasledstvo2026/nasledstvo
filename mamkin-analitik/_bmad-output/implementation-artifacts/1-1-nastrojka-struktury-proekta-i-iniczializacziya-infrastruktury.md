# Story 1.1: Настройка структуры проекта и инициализация инфраструктуры

Status: review

## Story

As a **разработчик**,
I want **создать структуру проекта по утверждённой архитектуре (раздел 5.1 architecture.md) и настроить базовую инфраструктуру (VPS, переменные окружения, Cloudflare Tunnel)**,
so that **все компоненты сервиса были готовы к разработке и развёртыванию**.

## Epic Context

- **Epic:** Epic 1 — Управление доступом и сессиями пользователей
- **FRs covered (Epic 1):** FR1, FR2, FR3, FR4, FR5, FR26, FR27, FR28
- **NFRs covered (Epic 1):** NFR5, NFR6, NFR7, NFR8, NFR9, NFR10, NFR11, NFR12, NFR13, NFR14
- **Связанные NFR для этой стори:** NFR7 (API-ключи в .env), NFR8 (Cloudflare Tunnel)

## Acceptance Criteria

1. **Given** проектная директория `/home/user1/.openclaw/workspace/mamkin-analitik/`
   **When** выполнена инициализация проекта
   **Then** создана полная структура директорий согласно архитектуре (agents/, lib/, data/, session-storage/, tests/, scripts/, docs/)

2. **Given** структура проекта создана
   **When** настроен файл `.env`
   **Then** файл содержит:
   - `DEEPSEEK_API_KEY` — ключ DeepSeek API
   - Путь к хранилищу сессий (по умолчанию: `SESSION_STORAGE_PATH=/var/mamkin-analitik/sessions/`)
   - Конфигурация Cloudflare Tunnel (туннель, домен, порт)
   - И никакие из этих значений не захардкожены в коде проекта (NFR7)

3. **Given** структура проекта создана
   **When** создан `config.yaml`
   **Then** в нём указаны:
   - Настройки OpenClaw (агенты, их порядок, таймауты)
   - Таймаут ответа агента — не более 5 секунд (NFR1)
   - Retry-логика (3 попытки с exponential backoff)
   - Язык (русский)

4. **Given** структура проекта создана
   **When** установлены зависимости
   **Then** установлены:
   - `python-docx` (через pip, для генерации DOCX)
   - OpenClaw connectors (Telegram Bot API — входит в OpenClaw)

5. **Given** структура проекта создана
   **When** настроен `.gitignore` и инициализирован git-репозиторий
   **Then**:
   - `.gitignore` исключает `.env`, `node_modules/`, `session-storage/`, `*.pyc`, `__pycache__/`
   - Репозиторий инициализирован (`git init`) в корне проекта
   - Сделан первоначальный коммит (с игнорированием чувствительных данных)

6. **Given** VPS vm-f13581 доступен
   **When** настроен Cloudflare Tunnel
   **Then**:
   - Cloudflare Tunnel обеспечивает HTTPS-доступ к VPS (прокси на порт OpenClaw — по умолчанию 8080)
   - Все внешние соединения проходят через HTTPS (NFR8)
   - Туннель настроен на доменную зону (уточнить домен у администратора инфраструктуры)

## Tasks / Subtasks

- [ ] 1. Создать структуру директорий проекта (AC: 1)
  - [ ] 1.1. Создать корневые файлы: `AGENTS.md`, `config.yaml`, `.env`, `.gitignore`, `README.md`
  - [ ] 1.2. Создать `agents/` с поддиректориями: `questioner/`, `compiler/`, `controller/`, `generator/`
  - [ ] 1.3. Создать `lib/` с файлами-заглушками: `session-manager.js`, `template-engine.js`, `github-pages.js`, `crypto.js`, `logger.js`, `retry.js`
  - [ ] 1.4. Создать `data/` с файлами-заглушками: `template.json`, `whitelist.json`, `depth-config.json`, `risk-categories.json`
  - [ ] 1.5. Создать `session-storage/` с поддиректориями `active/` и `completed/`
  - [ ] 1.6. Создать `tests/` с поддиректорией `fixtures/`
  - [ ] 1.7. Создать `scripts/`: `deploy.sh`, `backup.sh`, `migrate.sh`
  - [ ] 1.8. Создать `.github/workflows/`: `publish-pages.yml`, `test.yml`
  - [ ] 1.9. Создать `docs/`: копировать или символически связать `architecture.md`

- [ ] 2. Настроить `.env` с переменными окружения (AC: 2)
  - [ ] 2.1. Добавить `DEEPSEEK_API_KEY` (значение — из существующей инфраструктуры или запросить)
  - [ ] 2.2. Добавить `SESSION_STORAGE_PATH` (по умолчанию `/var/mamkin-analitik/sessions/`)
  - [ ] 2.3. Добавить настройки Cloudflare Tunnel (домен, tunnel ID, порт)
  - [ ] 2.4. Добавить `GITHUB_TOKEN` (для Git push при публикации на GitHub Pages)

- [ ] 3. Создать `config.yaml` для OpenClaw (AC: 3)
  - [ ] 3.1. Определить агентов пайплайна: questioner, compiler, controller, generator
  - [ ] 3.2. Указать таймауты (5s на ответ агента, 30s на генерацию DOCX, 60s на GitHub Pages)
  - [ ] 3.3. Настроить retry-логику (3 попытки, exponential backoff)
  - [ ] 3.4. Указать DeepSeek как LLM-провайдера
  - [ ] 3.5. Указать язык: русский

- [ ] 4. Установить зависимости (AC: 4)
  - [ ] 4.1. Установить `python-docx` (pip install python-docx)
  - [ ] 4.2. Проверить/установить OpenClaw (если ещё не установлен)

- [ ] 5. Настроить git и .gitignore (AC: 5)
  - [ ] 5.1. Создать `.gitignore` с исключениями (.env, node_modules/, session-storage/, __pycache__/, *.pyc, .DS_Store)
  - [ ] 5.2. Выполнить `git init` в корне проекта
  - [ ] 5.3. Выполнить `git add .` и `git commit -m "Initial project structure"`

- [ ] 6. Настроить Cloudflare Tunnel (AC: 6)
  - [ ] 6.1. Проверить существующую конфигурацию Cloudflare Tunnel на VPS
  - [ ] 6.2. Настроить проксирование трафика с туннеля на порт OpenClaw (по умолчанию 8080)
  - [ ] 6.3. Проверить HTTPS-доступ к приложению через домен туннеля

## Dev Notes

### Архитектурные паттерны и ограничения

- **Проектная структура:** должна строго соответствовать разделу 5.1 architecture.md (полное дерево директорий воспроизведено ниже)
- **Безопасность:** API-ключи нигде не хардкодятся — только `.env` → `process.env` (NFR7)
- **Шифрование:** файлы сессий будут шифроваться AES-256 в стори 1.2/1.7; на данном этапе создаётся только структура
- **OpenClaw:** агенты пайплайна будут подключаться через `config.yaml`
- **Cloudflare Tunnel:** вся внешняя коммуникация — только через HTTPS (NFR8)
- **Нейминг:** snake_case для файлов, camelCase для JSON-полей (см. раздел 4.1 architecture.md)

### Source tree — компоненты для создания

```
/home/user1/.openclaw/workspace/mamkin-analitik/
│
├── AGENTS.md                          # Agent identity document (можно копию шаблона)
├── config.yaml                        # OpenClaw/wrapper config
├── .env                               # Environment variables (secrets)
├── .gitignore
├── README.md
│
├── agents/                            # Multi-agent pipeline
│   ├── questioner/                    # Agent-опросчик
│   │   ├── index.js                   # Заглушка
│   │   ├── prompt.md                  # Заглушка
│   │   └── depth-control.js          # Заглушка
│   │
│   ├── compiler/                      # Agent-составитель
│   │   ├── index.js                   # Заглушка
│   │   ├── prompt.md                  # Заглушка
│   │   └── section-formatter.js      # Заглушка
│   │
│   ├── controller/                    # Agent-контролёр
│   │   ├── index.js                   # Заглушка
│   │   ├── prompt.md                  # Заглушка
│   │   └── quality-rules.md          # Заглушка
│   │
│   └── generator/                     # Agent-генератор
│       ├── index.js                   # Заглушка
│       ├── prompt.md                  # Заглушка
│       ├── docx-gen.py               # Заглушка
│       ├── html-gen.py               # Заглушка
│       └── styles/                    # Стили (пустая директория)
│
├── lib/                               # Shared libraries
│   ├── session-manager.js             # Заглушка
│   ├── template-engine.js             # Заглушка
│   ├── github-pages.js               # Заглушка
│   ├── crypto.js                      # Заглушка
│   ├── logger.js                      # Заглушка
│   └── retry.js                       # Заглушка
│
├── data/                              # Static/configuration data
│   ├── template.json                  # Заглушка
│   ├── whitelist.json                 # Пустой JSON-массив []
│   ├── depth-config.json              # Заглушка
│   └── risk-categories.json          # Заглушка
│
├── session-storage/                   # Session persistence
│   ├── active/                        # Пусто (будут создаваться файлы сессий)
│   └── completed/                     # Пусто
│
├── history.json                       # Пустой JSON-объект {} (или массив)
│
├── tests/                             # Test suite
│   └── fixtures/                      # Тестовые данные (пусто)
│
├── scripts/                           # Operational scripts
│   ├── deploy.sh                      # Заглушка (chmod +x)
│   ├── backup.sh                      # Заглушка (chmod +x)
│   └── migrate.sh                     # Заглушка (chmod +x)
│
├── .github/                           # CI/CD
│   └── workflows/
│       ├── publish-pages.yml          # Заглушка
│       └── test.yml                   # Заглушка
│
├── docs/                              # Documentation
│   └── operations.md                  # Пока пустой
│
└── _bmad/                             # BMad workflow state (уже существует)
```

### Testing Standards Summary

На данном этапе тесты не требуются — создаются только заглушки. Первые тесты появятся в стори 1.2 (Session Manager) и далее. Рекомендуется:

- В `tests/fixtures/` подготовить sample-session.json для будущего тестирования
- Framework: для JS-тестов — Jest (если доступен) или встроенные тесты OpenClaw
- Для Python-тестов (generator) — pytest

### Project Structure Notes

- **Alignment:** полное соответствие разделу 5.1 architecture.md
- **Detected conflicts:** директория `_bmad/` уже существует (создана на этапе планирования). Её содержимое не трогать.
- **Naming:** все файлы в snake_case, JSON-поля в camelCase — согласно разделу 4.1 architecture.md

## References

### Architecture

- **Раздел 5.1** — Полное дерево директорий проекта
  [Source: architecture.md#51-complete-directory-structure]
- **Раздел 3.6** — Инфраструктура (VPS, Cloudflare Tunnel, HTTPS)
  [Source: architecture.md#36-infrastructure--deployment]
- **Раздел 4.1** — Соглашения по неймингу (snake_case файлы, camelCase JSON)
  [Source: architecture.md#41-naming-patterns]
- **Раздел 6.7** — Implementation Handoff: приоритеты
  [Source: architecture.md#67-implementation-handoff]
- **Раздел 5.2** — API Boundaries (Cloudflare Tunnel → localhost:8080)
  [Source: architecture.md#52-architectural-boundaries]

### UX Design Specification

- **Раздел 5.1** — Design System Choice (кастомный Conversation Design System для Telegram)
  [Source: ux-design-specification.md#51-design-system-choice]
- **Раздел 7.1** — Cloudflare Tunnel обеспечивает HTTPS для всех соединений
  [Source: ux-design-specification.md#71-color-system]
- **Раздел 10.1** — Telegram-Native Components (часть инфраструктуры)
  [Source: ux-design-specification.md#101-telegram-native-components]

### PRD / Requirements

- **NFR7** — DeepSeek API-ключи хранятся в переменных окружения, не в коде
  [Source: prd.md#security]
- **NFR8** — Cloudflare Tunnel обеспечивает HTTPS для всех соединений
  [Source: prd.md#security]
- **Раздел 6** — Контекст и ограничения (существующая инфраструктура: VPS vm-f13581, Cloudflare Tunnel, DeepSeek API, OpenClaw)
  [Source: requirements.md#6-контекст-и-ограничения]
- **Раздел 8** — Архитектура решения: мультиагентный пайплайн, Telegram-бот, OpenClaw
  [Source: requirements.md#8-архитектура-решения]

### Epics & Stories

- **Story 1.1** — Полное описание (acceptance criteria, контекст)
  [Source: epics-and-stories.md#story-11-настройка-структуры-проекта-и-инициализация-инфраструктуры]

## Dev Agent Record

### Agent Model Used

DeepSeek V4 Flash (deepseek/deepseek-v4-flash)

### Debug Log References

- Дата выполнения: 2026-07-08
- Workflow: create-story (BMad)

### Completion Notes List

- Story создана на основе архитектуры (раздел 5.1), PRD (NFR7, NFR8), UX Spec и epics-and-stories.md
- Все acceptance criteria согласованы с документом epics-and-stories.md
- Зависимости от инфраструктуры (VPS, Cloudflare Tunnel, DeepSeek API) — существующие, не требуют создания
- `_bmad/` директория уже существует — не изменять

### File List

- `AGENTS.md`
- `config.yaml`
- `.env`
- `.gitignore`
- `README.md`
- `agents/questioner/index.js`
- `agents/questioner/prompt.md`
- `agents/questioner/depth-control.js`
- `agents/compiler/index.js`
- `agents/compiler/prompt.md`
- `agents/compiler/section-formatter.js`
- `agents/controller/index.js`
- `agents/controller/prompt.md`
- `agents/controller/quality-rules.md`
- `agents/generator/index.js`
- `agents/generator/prompt.md`
- `agents/generator/docx-gen.py`
- `agents/generator/html-gen.py`
- `agents/generator/styles/`
- `lib/session-manager.js`
- `lib/template-engine.js`
- `lib/github-pages.js`
- `lib/crypto.js`
- `lib/logger.js`
- `lib/retry.js`
- `data/template.json`
- `data/whitelist.json`
- `data/depth-config.json`
- `data/risk-categories.json`
- `session-storage/active/`
- `session-storage/completed/`
- `history.json`
- `tests/fixtures/`
- `scripts/deploy.sh`
- `scripts/backup.sh`
- `scripts/migrate.sh`
- `.github/workflows/publish-pages.yml`
- `.github/workflows/test.yml`
- `docs/operations.md`
