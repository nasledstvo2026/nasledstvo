# Пошаговый план работ — Социальный консультант на Фениксе

**Основание:** ТЗ `tz-social-consultant.md` (согласовано 2026-08-06)
**Исполнитель:** Лунтик (через SSH на Феникс)
**Цель:** 50 требований, 5 этапов

---

## Текущее состояние Феникса (перед стартом)

| Параметр | Значение |
|----------|----------|
| OpenClaw | 2026.6.33 |
| Агенты | main, fz425-agent, fz425-verifier |
| Навыки Феникса | diagram-maker, frontend, fz425-agent, fz425-verifier, nasledstvo-card-maker, ui-ux-pro-max |
| social-category-matcher | ❌ отсутствует на Фениксе (есть на Лунтике) |
| social-verifier-protocol | ❌ отсутствует на Фениксе (есть на Лунтике) |
| web_search | ❌ выключен (`tools.web.search.enabled: false`) |
| Биндинг Ирины (739016616) | ❌ отсутствует |
| Биндинг Кирилла (346428630) | → main + fz425-agent (двойной) |

---

## Шаг 0. Резервное копирование (бэкап)

### 0.1. Бэкап конфига Феникса

```bash
# С Лунтика:
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'cp /home/user1/.openclaw/openclaw.json /home/user1/.openclaw/openclaw.json.bak.$(date +%Y%m%d-%H%M%S)'
```

### 0.2. Бэкап всего workspace Феникса

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'tar -czf /home/user1/phoenix-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /home/user1 phoenix/'
```

### 0.3. Проверка бэкапа

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'ls -lh /home/user1/phoenix-backup-*.tar.gz | tail -1 && ls -lh /home/user1/.openclaw/openclaw.json.bak.* | tail -1'
```

> **Чекпоинт:** бэкап создан. При любом сбое — откат из бэкапа.

---

## Шаг 1. Подготовка инфраструктуры

### 1.1. Создать workspace social-consult-agent

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'mkdir -p /home/user1/phoenix/social-consult-agent/knowledge /home/user1/phoenix/social-consult-agent/memory'
```

### 1.2. Скопировать скилл social-category-matcher с Лунтика на Феникс

```bash
# С Лунтика:
scp -i ~/.ssh/fenix -o StrictHostKeyChecking=no \
  -r /home/user1/.openclaw/workspace/skills/social-category-matcher \
  user1@213.171.25.85:/home/user1/phoenix/skills/social-category-matcher

# Проверить:
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'head -5 /home/user1/phoenix/skills/social-category-matcher/SKILL.md'
```

### 1.3. Скопировать скилл social-verifier-protocol с Лунтика на Феникс

```bash
scp -i ~/.ssh/fenix -o StrictHostKeyChecking=no \
  -r /home/user1/.openclaw/workspace/skills/social-verifier-protocol \
  user1@213.171.25.85:/home/user1/phoenix/skills/social-verifier-protocol

# Проверить:
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'head -5 /home/user1/phoenix/skills/social-verifier-protocol/SKILL.md'
```

### 1.4. Создать структуру knowledge/

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 'cat > /home/user1/phoenix/social-consult-agent/knowledge/federal-law.md << "KNEOF"
# Федеральные законы по социальной поддержке

> ⚠️ Заполняется на Шаге 3. Сейчас — заглушка.

## 181-ФЗ «О социальной защите инвалидов в РФ»

### Статья 28.1. Ежемесячная денежная выплата инвалидам
(будет заполнено)

## 5-ФЗ «О ветеранах»

### Статья 16. Меры социальной поддержки ветеранов боевых действий
(будет заполнено)

KNEOF
'

# Аналогично остальные файлы-заглушки:
for f in payments-table.md categories.md svo-decrees.md moscow-region.md terms.md weekly-update.md; do
  SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
    ssh -i ~/.ssh/fenix user1@213.171.25.85 \
    "echo '# ${f%.md}\n\n> ⚠️ Заполняется на Шаге 3. Сейчас — заглушка.' > /home/user1/phoenix/social-consult-agent/knowledge/$f"
done
```

### 1.5. Создать пустой social-npa-db.json

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'echo "[]" > /home/user1/phoenix/social-consult-agent/knowledge/social-npa-db.json'
```

### 1.6. Создать базовый SKILL.md для social-consult-agent

Содержимое — см. Приложение A в конце этого документа. Создать через `write` или `cat`:

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'cat > /home/user1/phoenix/social-consult-agent/SKILL.md << "SKILLEOF"
(содержимое из Приложения A)
SKILLEOF
'
```

### 1.7. Создать базовый AGENTS.md для social-consult-agent

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'cat > /home/user1/phoenix/social-consult-agent/AGENTS.md << "AGEOF"
# AGENTS.md — Социальный консультант

## Роль
Ты — социальный консультант РФ. Твоя задача: отвечать на вопросы по мерам социальной поддержки для трёх категорий граждан:
- Люди с инвалидностью
- Ветераны боевых действий (ВБД)
- Участники СВО и члены их семей

## Правила работы
1. **Категоризация.** Каждый запрос прогоняешь через social-category-matcher.
2. **Чтение БЗ.** По результатам категоризации читаешь файлы из knowledge/.
3. **Поиск.** Если в БЗ нет ответа — web_search по garant.ru, consultant.ru, sfr.gov.ru.
4. **Верификация.** Все факты отправляешь в social-verify-agent перед ответом.
5. **Ответ.** Только проверенные факты, со ссылками на статьи НПА, суммы — с датой актуальности.
6. **Отказ.** Запросы вне соцподдержки — вежливый отказ. «Я консультирую только по вопросам социальной поддержки...»
7. **Без домыслов.** Если точных данных нет — «требует уточнения».

## Источники (приоритет)
1. garant.ru
2. consultant.ru
3. docs.cntd.ru
4. sfr.gov.ru

## Flow
запрос → категоризация → чтение БЗ → [web_search если нужно] → черновик → sessions_send("social-verify-agent") → ответ пользователю
AGEOF
'
```

### 1.8. Создать HEARTBEAT.md, IDENTITY.md, MEMORY.md, SOUL.md, USER.md, TOOLS.md

```bash
for f in HEARTBEAT.md IDENTITY.md MEMORY.md SOUL.md USER.md TOOLS.md; do
  SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
    ssh -i ~/.ssh/fenix user1@213.171.25.85 \
    "echo '# ${f%.md}' > /home/user1/phoenix/social-consult-agent/$f"
done
```

### 1.9. Проверка структуры

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'find /home/user1/phoenix/social-consult-agent -type f | sort'
```

> **Ожидаемый результат:**
> ```
> /home/user1/phoenix/social-consult-agent/AGENTS.md
> /home/user1/phoenix/social-consult-agent/HEARTBEAT.md
> /home/user1/phoenix/social-consult-agent/IDENTITY.md
> /home/user1/phoenix/social-consult-agent/MEMORY.md
> /home/user1/phoenix/social-consult-agent/SKILL.md
> /home/user1/phoenix/social-consult-agent/SOUL.md
> /home/user1/phoenix/social-consult-agent/TOOLS.md
> /home/user1/phoenix/social-consult-agent/USER.md
> /home/user1/phoenix/social-consult-agent/knowledge/categories.md
> /home/user1/phoenix/social-consult-agent/knowledge/federal-law.md
> /home/user1/phoenix/social-consult-agent/knowledge/moscow-region.md
> /home/user1/phoenix/social-consult-agent/knowledge/payments-table.md
> /home/user1/phoenix/social-consult-agent/knowledge/social-npa-db.json
> /home/user1/phoenix/social-consult-agent/knowledge/svo-decrees.md
> /home/user1/phoenix/social-consult-agent/knowledge/terms.md
> /home/user1/phoenix/social-consult-agent/knowledge/weekly-update.md
> ```

> **Чекпоинт:** структура создана, навыки скопированы. Можно переходить к конфигурации.

---

## Шаг 2. Конфигурация агентов

### 2.1. Включить web_search на Фениксе

**Причина:** social-consult-agent и social-verify-agent нуждаются в поиске по garant.ru, consultant.ru, sfr.gov.ru.

Текущее значение: `"enabled": false`. Меняем:

```bash
# Патч через sed (проверено на структуре конфига):
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'sed -i "s/\"enabled\": false,.*web.*search/\"enabled\": true/" /home/user1/.openclaw/openclaw.json'

# Проверить:
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'grep -A2 "web" /home/user1/.openclaw/openclaw.json | head -5'
```

### 2.2. Добавить social-consult-agent в agents.list

Вставить в `agents.list` после fz425-verifier. Точная вставка — через Python на Фениксе:

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 python3 << 'PYEOF'
import json
with open("/home/user1/.openclaw/openclaw.json") as f:
    cfg = json.load(f)

social_consult = {
    "id": "social-consult-agent",
    "description": "Социальный консультант: инвалидность, ВБД, СВО, выплаты, льготы",
    "workspace": "/home/user1/phoenix/social-consult-agent/",
    "model": {
        "primary": "deepseek/deepseek-v4-pro",
        "fallbacks": ["deepseek/deepseek-v4-flash"]
    },
    "subagents": {
        "allowAgents": ["social-verify-agent"]
    }
}

social_verify = {
    "id": "social-verify-agent",
    "description": "Верификатор НПА по соцподдержке",
    "workspace": "/home/user1/phoenix/",
    "model": {
        "primary": "deepseek/deepseek-v4-pro",
        "fallbacks": ["deepseek/deepseek-v4-flash"]
    },
    "tools": {
        "allow": ["web_search", "web_fetch", "sessions_send"]
    }
}

cfg["agents"]["list"].append(social_consult)
cfg["agents"]["list"].append(social_verify)

with open("/home/user1/.openclaw/openclaw.json", "w") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print("✅ agents added")
PYEOF
```

### 2.3. Обновить main.subagents.allowAgents

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 python3 << 'PYEOF'
import json
with open("/home/user1/.openclaw/openclaw.json") as f:
    cfg = json.load(f)

for agent in cfg["agents"]["list"]:
    if agent["id"] == "main":
        if "social-consult-agent" not in agent.setdefault("subagents", {}).setdefault("allowAgents", []):
            agent["subagents"]["allowAgents"].append("social-consult-agent")
        break

with open("/home/user1/.openclaw/openclaw.json", "w") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print("✅ main.subagents.allowAgents updated")
PYEOF
```

### 2.4. Обновить agentToAgent.allow

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 python3 << 'PYEOF'
import json
with open("/home/user1/.openclaw/openclaw.json") as f:
    cfg = json.load(f)

allow = cfg["tools"]["agentToAgent"]["allow"]
for agent_id in ["social-consult-agent", "social-verify-agent"]:
    if agent_id not in allow:
        allow.append(agent_id)

with open("/home/user1/.openclaw/openclaw.json", "w") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
print("✅ agentToAgent.allow updated:", allow)
PYEOF
```

### 2.5. Добавить биндинг для Ирины

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 python3 << 'PYEOF'
import json
with open("/home/user1/.openclaw/openclaw.json") as f:
    cfg = json.load(f)

irina_binding = {
    "agentId": "main",
    "match": {
        "channel": "telegram",
        "peer": {
            "kind": "direct",
            "id": "739016616"
        }
    }
}

# Проверить, нет ли уже такого биндинга
existing_ids = [b["match"]["peer"]["id"] for b in cfg.get("bindings", []) if b.get("match", {}).get("peer", {}).get("kind") == "direct"]
if "739016616" not in existing_ids:
    cfg.setdefault("bindings", []).append(irina_binding)
    print("✅ Irina binding added")
else:
    print("⚠️ Irina binding already exists")

with open("/home/user1/.openclaw/openclaw.json", "w") as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
PYEOF
```

### 2.6. Проверка конфига перед перезапуском

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 python3 << 'PYEOF'
import json
with open("/home/user1/.openclaw/openclaw.json") as f:
    cfg = json.load(f)

# Проверка 1: агенты в списке
agent_ids = [a["id"] for a in cfg["agents"]["list"]]
print("Агенты:", agent_ids)
assert "social-consult-agent" in agent_ids, "MISSING social-consult-agent"
assert "social-verify-agent" in agent_ids, "MISSING social-verify-agent"

# Проверка 2: agentToAgent
print("agentToAgent.allow:", cfg["tools"]["agentToAgent"]["allow"])
assert "social-consult-agent" in cfg["tools"]["agentToAgent"]["allow"]
assert "social-verify-agent" in cfg["tools"]["agentToAgent"]["allow"]

# Проверка 3: main subagents
for a in cfg["agents"]["list"]:
    if a["id"] == "main":
        print("main.subagents.allowAgents:", a.get("subagents", {}).get("allowAgents", []))
        assert "social-consult-agent" in a.get("subagents", {}).get("allowAgents", [])

# Проверка 4: биндинг Ирины
binding_ids = [b["match"]["peer"]["id"] for b in cfg.get("bindings", []) if b.get("match", {}).get("peer", {}).get("kind") == "direct"]
print("Bindings:", binding_ids)
assert "739016616" in binding_ids, "MISSING Irina binding"

# Проверка 5: web_search
print("web_search enabled:", cfg["tools"]["web"]["search"]["enabled"])
assert cfg["tools"]["web"]["search"]["enabled"] == True, "web_search NOT enabled"

print("\n✅ Все проверки конфига пройдены")
PYEOF
```

### 2.7. Перезапуск Феникса

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'bash /home/user1/phoenix/safe-restart.sh'
```

### 2.8. Проверка запуска (подождать 15 секунд)

```bash
sleep 15 && \
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'systemctl --user is-active openclaw-gateway && echo "✅ Gateway активен"'
```

> **Чекпоинт:** конфигурация применена, Феникс перезапущен. Агенты social-consult-agent и social-verify-agent должны появиться в `sessions_list`.

---

## Шаг 3. Наполнение базы знаний

### 3.1. Заполнить terms.md (глоссарий)

Заполняется через отдельную сессию. Использовать web_search для поиска определений:

- ЕДВ (ежемесячная денежная выплата)
- НСУ (набор социальных услуг)
- ВБД (ветеран боевых действий)
- СВО (специальная военная операция)
- МСЭ (медико-социальная экспертиза)
- ИПРА (индивидуальная программа реабилитации/абилитации)
- ЕДК (ежемесячная денежная компенсация)
- ЕДВ на оплату ЖКУ

### 3.2. Заполнить federal-law.md

Собрать актуальные статьи 181-ФЗ и 5-ФЗ через web_fetch по garant.ru:

- Глава III 181-ФЗ — меры соцзащиты инвалидов (ст. 13-28.1)
- Статья 16 5-ФЗ — меры соцподдержки ВБД (категории 1-3)
- Статья 23.1 5-ФЗ — ЕДВ ветеранам

### 3.3. Заполнить payments-table.md

Собрать актуальные суммы на 2026 год через web_search:

- ЕДВ по инвалидности (I, II, III группы, дети-инвалиды)
- ЕДВ ВБД (по категориям из 5-ФЗ)
- НСУ (денежный эквивалент)
- Региональные выплаты (Москва)

### 3.4. Заполнить categories.md

Структурировать категории из ТЗ (раздел «Особенности категорий»):

- ВБД категория 1 (подп. 1-4, 8 п. 1 ст. 3 5-ФЗ)
- ВБД категория 2 (подп. 5 п. 1 ст. 3 5-ФЗ)
- ВБД категория 3 (подп. 6, 7, 9 п. 1 ст. 3 5-ФЗ)
- Инвалиды I, II, III группы, дети-инвалиды
- Участники СВО, члены семей

### 3.5. Заполнить svo-decrees.md

Собрать актуальные указы Президента и постановления Правительства по СВО:

- Указы о единовременных выплатах
- Указы о статусе и льготах
- Постановления о мерах поддержки семей

### 3.6. Заполнить moscow-region.md

Собрать региональные меры Москвы (Закон г. Москвы № 70, указы Мэра, постановления Правительства Москвы).

### 3.7. Верификация заполнения

Проверить количество строк в каждом файле:

```bash
SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force \
  ssh -i ~/.ssh/fenix user1@213.171.25.85 \
  'for f in /home/user1/phoenix/social-consult-agent/knowledge/*.md; do echo "$(wc -l < "$f") $f"; done'
```

> **Ожидание:** каждый .md файл ≥ 20 строк (не заглушка).

> **Чекпоинт:** БЗ заполнена и верифицирована.

---

## Шаг 4. Тестирование

### 4.1. Запустить тесты согласно test-plan-social-consultant.md

Все тесты запускаются с Лунтика через `sessions_send` к main Феникса с эмуляцией sender_id Ирины, либо напрямую через Telegram от Ирины.

### 4.2. Критерии прохождения

- Тест 1 (инвалид II группы): ✅ категоризация, ✅ суммы, ✅ ссылки на НПА
- Тест 2 (льготы ВБД): ✅ категоризация, ✅ перечень льгот, ✅ ссылки на 5-ФЗ
- Тест 3 (семья мобилизованного): ✅ категоризация СВО, ✅ ссылки на указы
- Тест 4 (не по теме): ✅ вежливый отказ
- Тест 5 (стык категорий): ✅ чтение нескольких файлов БЗ
- Stateless: ✅ контекст не накапливается

### 4.3. При неудаче тестов

1. Определить корень проблемы (категоризация? поиск? верификация?)
2. Исправить
3. Перезапустить упавший тест
4. Повторить до прохождения

---

## Шаг 5. Приёмка

### 5.1. Собрать результаты тестов

См. `test-plan-social-consultant.md`, раздел «Журнал тестирования».

### 5.2. Проверить все критерии из раздела 4 ТЗ

- [x] / [ ] Все 5 тестов пройдены (категоризация ≥ 4/5)
- [x] / [ ] Stateless isolation (контекст не накапливается)
- [x] / [ ] 100% фактов проходят верификацию
- [x] / [ ] 100% ответов содержат ссылки на статьи НПА
- [x] / [ ] Время ответа ≤ 30 секунд

### 5.3. Предоставить отчёт Кириллу

Формат: сводка по тестам + замечания + решение о приёмке.

---

## Приложение A. SKILL.md для social-consult-agent

```markdown
# Социальный консультант (social-consult-agent)

Ты — агент-консультант по мерам социальной поддержки в РФ.

## Категории
- Люди с инвалидностью (I, II, III группы, дети-инвалиды)
- Ветераны боевых действий (категории 1-3 по 5-ФЗ)
- Участники СВО и члены их семей

## Алгоритм обработки запроса

### 1. Категоризация
Примени навык `social-category-matcher` для определения категории вопроса:
- `disability` — инвалидность
- `vbd` — ветераны боевых действий
- `svo` — СВО
- `not_social` — не относится к соцподдержке

### 2. Если not_social
Ответь вежливым отказом:
> «Я консультирую только по вопросам социальной поддержки: инвалидность, ветераны боевых действий, СВО. По вашему вопросу рекомендую обратиться к профильному специалисту.»

### 3. Чтение базы знаний
Прочитай релевантные файлы из `knowledge/`:
- disability → federal-law.md, payments-table.md, categories.md, terms.md, moscow-region.md
- vbd → federal-law.md, payments-table.md, categories.md, terms.md
- svo → svo-decrees.md, payments-table.md, categories.md, terms.md
- Кросс-категорийный → все перечисленные файлы

### 4. Web-поиск (если в БЗ нет ответа)
Ищи по приоритету источников:
1. site:garant.ru + ключевые слова
2. site:consultant.ru + ключевые слова
3. site:sfr.gov.ru + ключевые слова

### 5. Формирование черновика
- Каждый факт — с ссылкой на конкретную статью НПА
- Суммы — с датой актуальности
- Если точных данных нет → «требует уточнения» (не додумывать)

### 6. Верификация
Отправь все факты черновика в `social-verify-agent` через `sessions_send`.
Дождись вердикта по каждому факту.

### 7. Финальный ответ
- Только факты с вердиктом ✅
- Факты с ❌ — исключить
- Факты с 🔄 — заменить на уточнённую формулировку
- Факты с ❓ — пометить «требует уточнения»

## Ограничения
- Не консультируешь вне соцподдержки
- Не додумываешь данные
- Не используешь контекст предыдущих запросов (stateless)
- Время ответа ≤ 30 секунд
```
