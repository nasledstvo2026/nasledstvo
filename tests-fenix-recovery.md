# Тесты: восстановление Феникса после перезагрузки гейтвея

## Шаг 0 — Снимок до рестарта

```bash
systemctl --user status openclaw-gateway --no-pager | head -5
systemctl --user is-active law-search.service
curl -s --max-time 3 127.0.0.1:8765/health
```

## Шаг 1 — Холодный рестарт через safe-restart.sh

Выполнить:
```bash
bash ~/phoenix/safe-restart.sh
```

⚠️ Это последняя команда в текущей сессии. После неё сессия умрёт.
Дальнейшие проверки — в НОВОЙ сессии (новый чат с Фениксом).

## Шаг 2 — Проверки после рестарта (новая сессия)

### Т1. Гейтвей запустился

```bash
systemctl --user status openclaw-gateway --no-pager | head -8
```

Ожидание: Active: active (running), PID новый, Memory < 1 GB

### Т2. law-search пережил рестарт

```bash
systemctl --user is-active law-search.service
curl -s --max-time 3 127.0.0.1:8765/health
```

Ожидание: active, status ok, chunks=2981

### Т3. Embedding API работает

```bash
curl -sG --data-urlencode "q=срок исполнения поручения налогового органа" 127.0.0.1:8765/search?k=3 | python3 -m json.tool
```

Ожидание: 3 результата, score > 0.80, есть НК ч.1

### Т4. Инструменты агента работают (не картинки)

```bash
echo "test-ok"
```

Ожидание: вывод `test-ok`, НЕ base64/картинка

### Т5. Агент может выполнить SKILL.md-верификацию

Задать вопрос: «Какой срок исполнения поручения налогового органа?»

Ожидание: ответ «3 часа» со ссылкой на 425-ФЗ, вердикт верификатора ПРИНЯТ

## Шаг 3 — Стресс-тест сессии

После Т5 задать ещё 2-3 вопроса подряд и проверить что truncation не появляется.

```bash
journalctl --user -u openclaw-gateway --no-pager --since "2 min ago" | grep truncat
```

Ожидание: нет новых записей о truncation

## Критерии успеха

| # | Что проверяем | Ожидание |
|---|---------------|----------|
| Т1 | Гейтвей жив | active (running), свежий PID |
| Т2 | law-search жив | active, 2981 chunks |
| Т3 | Embedding API | 3 результата, score > 0.80 |
| Т4 | exec работает | выводит текст, не картинки |
| Т5 | Агент + верификатор | ответ корректен, вердикт ПРИНЯТ |
| Т6 | Нет truncation | journalctl чистый |

Все 6 должны быть ✅.
