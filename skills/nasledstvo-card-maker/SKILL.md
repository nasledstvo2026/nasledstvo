---
name: "nasledstvo-card-maker"
description: "Плашки и страницы в стиле nasledstvo. Триггеры: плашка, карточка, страница, стиль портала."
---

# nasledstvo-card-maker

Создание HTML-плашек и страниц в едином glass-morphism стиле портала nasledstvo2026.github.io.

## Базовые файлы (ВСЕГДА подключать первыми)

```html
<link rel="stylesheet" href="theme.css">
<link rel="stylesheet" href="style.css">
```

Если файлов нет локально — взять из репозитория:
- `https://raw.githubusercontent.com/nasledstvo2026/nasledstvo/gh-pages/theme.css`
- `https://raw.githubusercontent.com/nasledstvo2026/nasledstvo/gh-pages/style.css`

## Дизайн-токены (НЕ ИЗОБРЕТАТЬ свои — только эти)

| Токен | Значение | Применение |
|-------|----------|------------|
| `--glass-bg` | `rgba(22,27,34,0.6)` | Фон карточек |
| `--glass-border` | `rgba(255,255,255,0.08)` | Бордер карточек |
| `--glass-shine` | `rgba(255,255,255,0.03)` | Эффект пузырька (блик) |
| `--text` | `#e6edf3` | Основной текст |
| `--text-dim` | `#8b949e` | Второстепенный текст |
| `--text-faint` | `#484f58` | Третичный текст |
| `body bg` | `#0a0e14` + radial-gradient | Фон страницы |

## Цветовая карта (строго)

| Класс | Hex бордера | Применение |
|-------|-------------|------------|
| `.blue` | `rgba(88,166,255,0.55)` | Аналитика, дашборды, ссылки |
| `.green` | `rgba(126,231,135,0.55)` | Инфраструктура, статусы, успех |
| `.purple` | `rgba(188,140,255,0.55)` | Архитектура, AI/ML, схемы |
| `.orange` | `rgba(255,144,0,0.55)` | Расчёты, штрафы, риски |
| `.pink` | `rgba(247,120,186,0.55)` | Креатив, фото |
| `.red` | `rgba(255,80,80,0.55)` | Ошибки, критика, срочное |
| `.cyan` | `rgba(86,212,221,0.55)` | Сервисы, техническое |

## Анимированные пузырьки (ОБЯЗАТЕЛЬНО на главной странице)

Добавлять в `<style>` и сразу после `<body>`:

```html
<style>
  .bubbles {
    position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden;
  }
  .bubble {
    position: absolute; bottom: -120px; border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.08), rgba(88,166,255,0.03) 50%, transparent 70%);
    backdrop-filter: blur(2px); -webkit-backdrop-filter: blur(2px);
    border: 1px solid rgba(255,255,255,0.04);
    animation: bubble-rise linear infinite;
  }
  .bubble:nth-child(1) { left: 10%; width: 60px; height: 60px; animation-duration: 18s; animation-delay: 0s; }
  .bubble:nth-child(2) { left: 25%; width: 40px; height: 40px; animation-duration: 14s; animation-delay: 3s; }
  .bubble:nth-child(3) { left: 40%; width: 80px; height: 80px; animation-duration: 22s; animation-delay: 5s; }
  .bubble:nth-child(4) { left: 55%; width: 50px; height: 50px; animation-duration: 16s; animation-delay: 2s; }
  .bubble:nth-child(5) { left: 70%; width: 35px; height: 35px; animation-duration: 12s; animation-delay: 7s; }
  .bubble:nth-child(6) { left: 85%; width: 70px; height: 70px; animation-duration: 20s; animation-delay: 4s; }
  .bubble:nth-child(7) { left: 15%; width: 45px; height: 45px; animation-duration: 15s; animation-delay: 9s; }
  .bubble:nth-child(8) { left: 60%; width: 90px; height: 90px; animation-duration: 25s; animation-delay: 1s; }
  @keyframes bubble-rise {
    0%   { transform: translateY(0) scale(1); opacity: 0; }
    10%  { opacity: 0.6; }
    80%  { opacity: 0.3; }
    100% { transform: translateY(-110vh) scale(0.6); opacity: 0; }
  }
</style>
```

```html
<div class="bubbles">
  <div class="bubble"></div>  <!-- ×8 -->
</div>
```

Характеристики: 8 пузырьков, 35-90px, 12-25s подъём, `pointer-events: none`, полупрозрачный radial-gradient + blur. Позади контента (z-index: 0).

## Два типа карточек — ВАЖНО различать

### Тип А: Бесцветная карточка (glass-пузырёк)
Без цветового класса. Имеет `::before` — эффект стеклянного блика-пузырька:
```html
<div class="card">
  ...
</div>
```
Результат: прозрачный glass-фон + блик `linear-gradient(135deg, var(--glass-shine), transparent 50%)`. **НЕТ** левой полосы.

### Тип Б: Цветная карточка (акцент-полоса)
С цветовым классом. Имеет `::after` — левую цветную полосу 5px:
```html
<div class="card ЦВЕТ">
  ...
</div>
```
Результат: цветной градиент + цветной бордер + левая полоса. **НЕТ** блика-пузырька.

⚠️ **НИКОГДА не смешивать:** либо пузырёк, либо полоса — не оба сразу.

---

# Часть 1: Плашки (карточки)

## Шаблон цветной карточки

```html
<div class="cards" style="max-width:900px;margin:0 auto;gap:24px;">
  <div class="card ЦВЕТ">
    <a href="ССЫЛКА.html">
      <div class="card-header">
        <div class="card-header-row">
          <span class="card-tag ЦВЕТ">ТЕГ</span>
        </div>
        <h2>ЗАГОЛОВОК</h2>
      </div>
      <div class="desc">ОПИСАНИЕ (1-2 предложения)</div>
    </a>
  </div>
</div>
```

## Шаблон бесцветной карточки (glass-пузырёк)

```html
<div class="cards" style="max-width:900px;margin:0 auto;gap:24px;">
  <div class="card">
    <a href="ССЫЛКА.html">
      <div class="card-header">
        <div class="card-header-row">
          <span class="card-tag">ТЕГ</span>
        </div>
        <h2>ЗАГОЛОВОК</h2>
      </div>
      <div class="desc">ОПИСАНИЕ</div>
    </a>
  </div>
</div>
```

## Шаблон карточки с бейджем статуса

```html
<div class="card ЦВЕТ">
  <a href="ССЫЛКА.html">
    <div class="card-header">
      <div class="card-header-row">
        <h2>ЗАГОЛОВОК</h2>
        <span class="card-badge СТАТУС">СТАТУС</span>
      </div>
    </div>
    <div class="desc">ОПИСАНИЕ</div>
  </a>
</div>
```

Статусы: `daily` (зелёный), `weekly` (синий), `ondemand` (фиолетовый), `mvp` (оранжевый), `live` (красный).

---

# Часть 2: Целые страницы

## Шаблон страницы

```html
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ЗАГОЛОВОК — nasledstvo2026.github.io</title>
  <link rel="stylesheet" href="theme.css">
  <link rel="stylesheet" href="style.css">
</head>
<body>
<div class="container">
  <a href="index.html" class="back">← На главную</a>
  <div class="hero">
    <h1>ЗАГОЛОВОК СТРАНИЦЫ</h1>
    <p class="sub">Подзаголовок</p>
  </div>
  <div class="section">
    <h2>📌 Заголовок секции</h2>
    <div class="item">
      <div class="title">Заголовок элемента</div>
      <div class="meta">Мета</div>
      <div class="body">Содержимое.</div>
    </div>
    <div class="stats-row">
      <div class="stat-box"><div class="label">Метрика</div><div class="value">1 234</div></div>
    </div>
    <div class="table-wrap">
      <table class="striped-table">
        <tr><th>A</th><th>B</th></tr>
        <tr><td>X</td><td>Y</td></tr>
      </table>
    </div>
    <div class="note">⚠️ Примечание</div>
    <span class="tag">ТЕГ</span>
  </div>
  <div class="footer">Дата · <a href="...">nasledstvo</a></div>
</div>
</body>
</html>
```

### Back-ссылка — обязательна на всех страницах кроме index
```html
<a href="index.html" class="back">← На главную</a>
```

### Секция (.section) — заголовки с эмодзи (📌 🔍 ⚙️ 📊 ✅ ❌ ⚠️ 💰 📋)

### Item (.item) — вложенная карточка: .title / .meta / .body
Highlight: `<div class="item highlight">`

### Статистика — .stats-row > .stat-box > .label + .value (36px) / .num (32px)

### Таблица — .table-wrap > table.striped-table

### Заметка — .note

### Теги — .tag / .tag.red

---

# Часть 3: Абсолютные правила

1. **НЕ ИЗОБРЕТАТЬ цвета.** Только из цветовой карты.
2. **НЕ ИЗОБРЕТАТЬ CSS.** Всё в theme.css + style.css. Допустим page-specific `<style>`.
3. **Анимированные пузырьки — на каждой главной странице.** `<div class="bubbles">` с 8 `.bubble`, `position: fixed`, `pointer-events: none`, radial-gradient + blur, @keyframes bubble-rise 12-25s.
4. **Статический пузырёк (glass-shine).** Бесцветные `.card`: `::before` с `linear-gradient(135deg, var(--glass-shine), transparent 50%)`.
5. **Левая полоса-акцент.** Цветные `.card`: `::after` с 5px градиентом. ⚠️ Либо пузырёк, либо полоса.
6. **Glow-hover** на `.card` (box-shadow: 0 0 36px).
7. **Размер карточек:** max-width 900px, minmax(340px, 1fr), gap 24px.
8. **Мобильная адаптация:** <600px → 1 колонка.
9. **Шрифты:** h1 26px/800, .card h2 17px/700, .item .title 16px/600.
10. **Фон:** `#0a0e14` + двойной radial-gradient (синий + фиолетовый).
11. **Инлайн-CSS запрещён.** Исключение: page-specific `<style>`.
12. **Back-ссылка** на всех страницах кроме index.

## Проверка перед публикацией

- [ ] theme.css + style.css подключены
- [ ] Главная: анимированные пузырьки `.bubbles`
- [ ] Back-ссылка есть (для страниц-деталей)
- [ ] Hero: `<h1>` + `.sub`
- [ ] Контент разбит на `.section`
- [ ] Цвета из утверждённой палитры
- [ ] Бесцветные карточки: статичный пузырёк (::before)
- [ ] Цветные карточки: левая полоса + glow-hover
- [ ] Таблицы: `.table-wrap` > `.striped-table`
- [ ] Мобильная вёрстка
- [ ] Фон: `#0a0e14` + radial-gradient
