---
name: "skill-standards"
description: "Стандарты написания SKILL.md: структура, progressive disclosure, references/. Адаптация effective-agent-skills."
---

# skill-standards

Стандарты написания SKILL.md под OpenClaw. Адаптация effective-agent-skills от David Ondrej.

## Структура скилла

```
my-skill/
├── SKILL.md          # Обязательно: frontmatter + инструкция
├── references/       # Опционально: подробные документы, загружаются по необходимости
├── scripts/          # Опционально: вспомогательные скрипты
└── examples/         # Опционально: примеры использования
```

## SKILL.md frontmatter

```yaml
---
name: skill-name
description: Что делает скилл И когда его использовать. Включай триггер-фразы. Макс 160 байт.
---
```

## Progressive disclosure

- **Level 1** — discovery: только `name` + `description` из frontmatter в системе. Агент знает что скилл есть.
- **Level 2** — activation: при совпадении запроса агент читает полный SKILL.md в контекст.
- **Level 3** — execution: агент читает references/ скрипты только когда нужно. Они не жрут контекст до востребования.

## Правила

1. **Описание в frontmatter — краткое и ёмкое.** Включает: что делает + когда включать (триггеры). Не более 160 символов.
2. **Тело SKILL.md — конкретные инструкции.** Без воды, без общих слов. Шаги, команды, форматы.
3. **Сложное и объёмное — в references/.** Не пихать в тело SKILL.md базы знаний на 500 строк. Сделать `references/foo-knowledge.md` и сослаться.
4. **Примеры — в examples/.** Короткий пример в теле, полный — в файле.
5. **disable-model-invocation: true** — если скилл не требует вызова модели (чисто процедурный). Экономит токены.
