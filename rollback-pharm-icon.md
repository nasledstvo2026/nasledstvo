# Rollback: Иконка ФармТендеролог на главной

## Дата: 30.06.2026

## Что было изменено
1. Добавлен файл `assets/pharm-tenderolog-icon.png` (32×32)
2. В `index.html` — добавлен `<img>` внутри плашки `.card.purple.aura`
3. В `style.css` — добавлены стили для `.aura-icon`

## Шаги отката

### 1. Восстановить index.html
```bash
cp index.html.bak.20260630-pharm-icon index.html
```

### 2. Удалить ненужные файлы
```bash
rm assets/pharm-tenderolog-icon.png
```

### 3. Откатить CSS (если нужно ручное изменение)
В `style.css` удалить блок:
```css
/* ─── AURA card icon ─── */
.cards .card.aura .aura-icon {
  ...
}
```

### 4. Опубликовать
```bash
git add -A
git commit -m "rollback: откат иконки ФармТендеролог"
git push
```

## Проверка
- index.html открывается без ошибок
- Плашка ФармТендеролог — без иконки, как было
- Бэкап-файл можно удалить после подтверждения
