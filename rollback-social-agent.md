# План отката — Социальный консультант (social-agent + social-verifier)

## Условия применения
Выполнить при фатальном сбое одного из:
- social-agent не отвечает Ирине/Розе
- social-verifier не отвечает social-agent
- cron-задачи падают с ошибкой agentId
- binding не работает — сообщения не доходят

## Шаг 1 — Отключить binding для Ирины и Розы
```bash
# Временно удалить bindings через патч конфига
# Удалить из ~/.openclaw/openclaw.json блоки:
# {"agentId":"social-agent","match":{"channel":"telegram","peer":{"kind":"direct","id":"739016616"}}}
# {"agentId":"social-agent","match":{"channel":"telegram","peer":{"kind":"direct","id":"175808089"}}}
```

## Шаг 2 — Восстановить cron-задачи на main (из бэкапа)
```bash
# Восстановить старые cron-задачи из бэкапа:
openclaw cron add \
  --agent main \
  --name "Ирина: еженедельный обзор НПА" \
  --cron "6 9 * * 1" \
  --to "739016616" \
  --announce \
  --timeout-seconds 400 \
  --message "Ты — юридический аналитик. Составь еженедельный обзор НПА по соцподдержке за последние 7 дней..."

openclaw cron add \
  --agent main \
  --name "📋 Роза: сводка изменений в законах по пособиям" \
  --cron "3 9 * * 1" \
  --to "175808089" \
  --announce \
  --timeout-seconds 300 \
  --message "Ты — юридический аналитик. Составь еженедельную сводку изменений в законодательстве по пособиям..."
```

## Шаг 3 — Удалить социальный-агент и социальный-верификатор
```bash
openclaw agent remove social-agent
openclaw agent remove social-verifier
```

## Шаг 4 — Восстановить social.html
```bash
# Из бэкапа:
tar -xzf ~/.openclaw/backups/social-pages.<дата>.tar.gz -C ~/.openclaw/workspace/
git add social.html && git commit -m "rollback: restore social pages" && git push
```

## Шаг 5 — Валидация отката
- Ирина и Роза снова получают ответы от main-агента
- cron-задачи работают на main
- social.html в исходном виде
- report-irina.html не потерян

## Критические данные, которые нельзя потерять
- База знаний knowledge/social/ — не удалять, даже при откате
- AGENTS.md социальный-агент — может понадобиться при повторном развёртывании
