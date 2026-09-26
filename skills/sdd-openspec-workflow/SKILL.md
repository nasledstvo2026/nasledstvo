---
name: "sdd-openspec-workflow"
description: "Spec-driven разработка по OpenSpec: propose → specs → tasks → validate → archive. Проверено на @fission-ai/openspec v1.13.2."
---

# SDD / OpenSpec Workflow

Рабочий процесс spec-driven разработки, проверенный на реальном пакете
`@fission-ai/openspec` v1.13.2 (репо `Fission-AI/OpenSpec`, MIT).

⚠️ ВАЖНО: пакет `openspec` (без скоупа) на npm — ПУСТЫШКА (v0.0.0, пустой index.js).
Настоящий — только `@fission-ai/openspec`. Ставить строго его.

## Установка

```bash
npm install -g @fission-ai/openspec@latest
openspec --version   # ожидаем 1.13.2+
```

Требует Node.js 20.19.0+.

## Инициализация в проекте

```bash
cd <проект>
openspec init --tools none --no-animation
```

Создаёт:
- `openspec/config.yaml` — содержит `schema: spec-driven` + опционально `context:`,
  `rules:` (per-artifact), `operations:` (apply/archive guidance)
- `openspec/specs/` — итоговые спеки (источник правды)
- `openspec/changes/archive/` — архив завершённых изменений

## Рабочий цикл (fluid, не waterfall)

```
propose → specs → design → tasks → validate → apply → archive
```

### 1. Создать изменение

```bash
openspec new change <change-name>
```

Создаёт `openspec/changes/<name>/` c `.openspec.yaml` (schema + created date).

### 2. Заполнить артефакты

4 артефакта (порядок зависимостей: proposal → specs → design → tasks):

- **proposal.md** — ЗАЧЕМ. Секции: Why, What Changes (BREAKING помечать), Capabilities
  (New/Modified — критично, это контракт с фазой specs), Impact. Кратко, 1–2 стр.
- **specs/<capability-path>/spec.md** — ЧТО система должна делать. Поведение, а не
  реализация. Одна спека на каждую capability из proposal.
- **design.md** — КАК. ОПЦИОНАЛЕН (создавать только если: кросс-модульность, новая
  зависимость, сложная миграция/секьюрити/перф). Секции: Context, Goals/Non-Goals,
  Decisions (с альтернативами), Risks/Trade-offs, Migration Plan, Open Questions.
- **tasks.md** — чек-лист реализации. Каждая задача = `- [ ] X.Y Описание` с проверкой
  выполнения прямо в тексте. Группировать по `## N. Group`. НЕ собирать тесты/доку
  в финальную группу — каждый блок несёт свои тесты/доки.

### 3. Формат спеки (критично, из schema.yaml)

```markdown
# Spec Delta

## Purpose
<!-- ТОЛЬКО для новых capability. 1–2 предложения, 50+ символов
     (иначе validate --strict ругается). Для существующих — УДАЛИТЬ секцию. -->

## ADDED Requirements

### Requirement: <имя>
Система SHALL <поведение>.

#### Scenario: <имя>
- **WHEN** <условие>
- **THEN** <ожидаемый результат>
```

Дельта-операции (заголовки `##`):
- `## ADDED Requirements` — новые capability
- `## MODIFIED Requirements` — изменённое поведение; MUST включать ПОЛНЫЙ обновлённый блок
- `## REMOVED Requirements` — MUST включать **Reason** и **Migration**
- `## RENAMED Requirements` — формат FROM:/TO:

Правила:
- Требование: `### Requirement: <имя>` + нормативные SHALL/MUST (не should/may)
- Сценарий: СТРОГО 4 решётки `#### Scenario:` (3 решётки или буллеты — тихо ломается)
- Каждое требование MUST иметь минимум 1 сценарий
- В спеке НЕ упоминать имена классов/функций, выбор библиотек, пошаговую реализацию

Проверка «нужно ли это в спеке»: если реализация может измениться без изменения
внешне видимого поведения — это НЕ в спеку.

### 4. Валидация

```bash
openspec validate <name>            # базово
openspec validate <name> --strict   # строго (Purpose 50+ chars и т.д.)
openspec status --change <name>     # прогресс по артефактам
```

Нулевой дельта-спек отклоняется, ЕСЛИ в `.openspec.yaml` нет `skip_specs: true`
(ставить только для pure refactor/tooling/docs — без изменения поведения).

### 5. Архив

```bash
openspec archive <name> --yes
```

⚠️ Блокируется, если есть незавершённые задачи (`- [ ]`). Это by design.
После архива:
- change уезжает в `openspec/changes/archive/<дата>-<name>/`
- спека переносится в `openspec/specs/<capability>/spec.md` (с `## Purpose` + `## Requirements`)

## Полезные команды CLI

```
openspec list --specs       # инвентарь существующих capability
openspec show <id> --type spec --json --no-scenarios   # overview без всего контекста
openspec show <id> --type spec                          # полная спека со сценариями
openspec templates          # пути к шаблонам артефактов
openspec instructions <artifact> --change <name> --json # enriched-инструкции
```

## Принципы (из README)

- fluid not rigid, iterative not waterfall, built for brownfield
- agree before you build: спека ДО кода
- спека живёт рядом с кодом (в репо), а не отдельным документом

## Интеграция с AI-агентами

OpenSpec рассчитан на slash-команды (`/opsx:propose`, `/opsx:apply`, `/opsx:archive`,
`/opsx:explore`) для 30+ инструментов (Claude Code, Codex, Cursor, OpenCode, Cline…).
**В OpenClaw встроенной интеграции НЕТ** (проверено: в дистрибутиве пакета нет
упоминаний openclaw/claw). В OpenClaw работаем напрямую через CLI-команды выше.

## Что это значит для «работаем ли мы по SDD»

Мы работаем по SDD тогда, когда:
1. спека (требования + сценарии) фиксируется ДО кода и живёт в `openspec/specs/`
2. изменения идут через change-папки (propose → specs → tasks)
3. соответствие проверяется `openspec validate` (а не «на глаз»)
4. спека обновляется через `openspec archive`, а не правится вручную после кода

«ТЗ → код → тест» без формальной версионируемой спеки с автопроверкой — это
spec-first/waterfall, но ещё не SDD.
