# План отката — ФармТендеролог: живые закупки ЕИС

## Если что-то пошло не так

### 1. Отключить cron-задачу парсинга
```bash
# Отключить, но не удалять
openclaw cron update --id "a463562c-f180-4b52-b01f-50c277532838" --patch '{"enabled":false}'
```

### 2. Откатить zakupki.html к предыдущей версии
```bash
cd /home/user1/.openclaw/workspace
git revert 17fe5b9 --no-edit  # откат pharm-tenderolog-product.html
git revert 9fe0927 --no-edit  # откат zakupki.html + parse-zakupki.py
git push
```

### 3. Удалить zakupki-purchases.json (если мешает)
```bash
cd /home/user1/.openclaw/workspace
git rm zakupki-purchases.json
git commit -m "rollback: удалён zakupki-purchases.json"
git push
```

### 4. Включить старый health-check (если нужен)
```bash
openclaw cron update --id "6f7e566c-426c-4044-8ef5-a0f75633b574" --patch '{"enabled":true}'
```

## Проверка после отката
- https://nasledstvo2026.github.io/nasledstvo/zakupki.html — грузится без JS-ошибок
- Нет запросов к zakupki-purchases.json (404 не показывается)
- Страница продукта показывает прежние источники
