# MEMORY.md — Долгосрочная память Лунта

## ⚠️ Правила поведения

## 🧠 Договорённости с Кириллом (26.06.2026)

### Как работать эффективнее
1. **Симптом → диагностика, а не action.** Сначала архитектурная схема (кто/где/куда стучится). Потом план — ты утверждаешь.
2. **Одно изменение — одна проверка.** Не патчить 3+ файла за раз.
3. **Никогда не удалять файлы, если не уверен на 100%, что они никому не нужны.** `git rm` — только когда известна вся цепочка зависимостей.
4. **Сложная задача >15 мин:** сначала схема, потом действие.
5. **Перед деструктивной операцией — явное предупреждение:** «Я собираюсь сделать X. Это сломает Y.»
6. **Если 5+ сообщений без результата — признать тупик и перезайти с другой стороны.**
7. **Если Кирилл говорит «нет» или уточняет — остановиться и переспросить, не продолжать старую линию.**

### Публикация через GitHub
- **20.06.2026:** Полный переход на GitHub Pages. Timeweb отключён.
- Сайт: https://nasledstvo2026.github.io/nasledstvo/
- Публикация отчётов: скрипт `publish-report.sh` (git add + commit + push)
- Загрузка файлов: скрипт `upload-to-github.sh`
- Бэкап: git push (задачи cron #6, #7)
- Все cron-задачи больше не используют scp/SSH к Timeweb — только git push
- SSH к Timeweb больше не используется; ключ ~/.ssh/timeweb не нужен

### Ошибки
- Мало признать — сделать вывод и изменить поведение
- Если спорил с пользователем и оказался неправ — зафиксировать урок
- **20.06.2026:** Не сохранил актуальные файлы с Timeweb при первом пушe на GitHub — пришлось перезаливать. Урок: всегда бери свежий снэпшот

### Редактирование файлов на проде
- **Никогда не переписывать файлы целиком** (write) если меняется только часть — использовать edit (точечные замены)
- Если всё же нужен full rewrite — **обязательно** читать оригинал полностью и переносить ВСЁ содержимое, включая элементы которые кажутся «не твоими»
- Перед публикацией — diff оригинала и нового файла, проверить что ничего не удалено
- **12.06.2026:** Срезал карточки Розы и Ирины при перезаписи index.html —教训: write = опасно, edit = безопасно
- **19.06.2026:** Удалил весь блок cards из index.html вместо удаления ссылок внутри — сломал вёрстку. Правило: **никогда не удалять контентные блоки целиком ради удаления ссылок. Убирать только href/тег `<a>`, оставляя структуру и наполнение.** Визуал важнее отсутствия ссылки.

## 🏗️ Архитектура системы

### Инфраструктура
- **OpenClaw** на VPS (vm-f13581), Linux x64
- **Хостинг сайта:** GitHub Pages — https://nasledstvo2026.github.io/nasledstvo/
- **❌ Домен nasledstvo.net.ru — НИКОГДА не использовать.** Не упоминать, не ссылаться. Существовал только при Timeweb, сейчас мёртв.
- **Репозиторий:** https://github.com/nasledstvo2026/nasledstvo (SSH: git@github.com:nasledstvo2026/nasledstvo.git)
- **Домен:** nasledstvo2026.github.io/nasledstvo (без кастомного домена)
- **Отказались от:** Timeweb Cloud + домен nasledstvo.net.ru (19.06.2026 — Timeweb лёг, 20.06.2026 — переехали на GitHub Pages)
- **⚠️ Домен nasledstvo.net.ru больше НЕ СУЩЕСТВУЕТ — не упоминать**
- **Скрипты публикации:** `publish-report.sh`, `upload-to-github.sh` — всё через git push
- **SSH ключ GitHub:** `~/.ssh/id_ed25519` (добавлен на аккаунт nasledstvo2026)
- **Ключ Timeweb удалён:** `~/.ssh/timeweb` не используется

### AI DJ — полная архитектура продукта (28.06.2026, уточнено v2)

#### Внешний доступ
```
[Браузер] → GitHub Pages (HTTPS, валидный сертификат)
  ├─ djset.html — DJ Set'ы, создание сетов, сведение
  ├─ aidj-delete.html — удаление треков
  └─ aidj-player.html — плеер
       └─ fetch() → Cloudflare Quick Tunnel (HTTPS, валидный сертификат)
            └─ https://*.trycloudflare.com  (МЕНЯЕТСЯ ПРИ РЕСТАРТЕ)
                 └─ cloudflared (VPS, systemd-сервис)
                      └─ http://localhost:8766
                           └─ Flask (aidj-server.py)
                                ├─ GET  /tracks.json         — список треков (с VPS)
                                ├─ GET  /static/<file>       — отдача готовых миксов mp3
                                ├─ GET  /<mp3_file>          — отдача треков
                                ├─ POST /api/mix             — запустить сведение
                                ├─ POST /api/tracks/delete   — удаление треков
                                └─ POST /api/log             — client-side логирование
```

#### ⚠️ Quick Tunnel — URL меняется при рестарте
- При каждом рестарте `cloudflared-aidj.service` Cloudflare выдаёт **новый** random URL
- Сменить URL → нужно обновить **все** файлы, где он захардкожен:
  - `aidj-player.html` — fetch tracks.json
  - `aidj-delete.html` — fetch tracks.json, delete, log
  - `aidj/djset.html` — переменная `VPS_BASE`
  - `aidj/aidj-server.py` — переменная `NGINX_BASE` (формирует URL готового микса)
  - `aidj/tracks.json` (на VPS) — URL треков в коллекции

**Процедура обновления URL туннеля:**
```bash
# 1. Получить новый URL
NEW_URL=$(sudo journalctl -u cloudflared-aidj --no-pager 2>&1 | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)

# 2. Заменить во всех файлах
cd /home/user1/.openclaw/workspace
OLD_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' aidj-player.html | head -1)
sed -i "s|$OLD_URL|$NEW_URL|g" aidj-player.html aidj-delete.html aidj/djset.html aidj/tracks.json aidj/aidj-server.py

# 3. Перезапустить сервер
sudo systemctl restart aidj-server

# 4. Опубликовать на GitHub
git add -A && git commit -m "aidj: updated tunnel URL" && git push
```

#### Серверная часть
- **Flask-сервер:** `aidj-server.py` на порт 8766
  - Слушает: `localhost:8766` (только через cloudflared туннель)
  - HOST = `'176.123.162.12'` (не используется напрямую — через туннель)
  - NGINX_BASE — для формирования URL миксов. Должен совпадать с URL туннеля
- **Engine:** `aidj-engine.py` (librosa + ffmpeg) — BPM/key detection, beat-synced crossfade
- **DJ Set'ы:** `aidj/sets/set-*.json`, CRUD через веб-интерфейс (localStorage)
- **Track list:** единый `aidj/tracks.json` — живёт на VPS, обновляется при добавлении/удалении треков
  - URL треков в формате: `$TUNNEL_URL/<filename>.mp3`
  - При обновлении туннеля — заменить URL и в этом файле

#### ❌ Named tunnel создан, но не активирован
- Named tunnel: `aidj-api` (ID: `dce12743-14bc-4157-a730-c1808a26a5ef`)
- Credentials: `~/.cloudflared/aidj-credentials.json`
- **Не активирован** — нет домена в Cloudflare. Когда появится — простая DNS-запись и named tunnel заменит quick tunnel навсегда

#### Клиентские страницы (GitHub Pages)
- `aidj/djset.html` — DJ Set'ы: создание сетов, выбор треков, сведение, прослушивание
  - VPS_BASE — URL туннеля (хардкод, без слеша в конце)
- `aidj-player.html` — плеер с Club EQ (Web Audio API)
- `aidj-delete.html` — удаление треков

#### Хранение файлов
- **mp3:** на VPS в `/home/user1/.openclaw/workspace/aidj/`
- **tracks.json:** там же. При удалении трека через веб — mp3 стирается автоматически
- **Готовые миксы:** `aidj/static/mix_*.mp3`
  - Формат имени: `mix_<YYYYMMDD>_<HHMMSS>_<preset_id>.mp3`
  - preset берётся из `preset_params.get('preset', 'default')` в aidj-engine.py
- **В репозитории GitHub:** только html-страницы, server.py и tracks.json. mp3 в `.gitignore`

#### Логирование создания миксов
- Сервер пишет в stderr: `[MIX-CREATED] <filename> — <preset_name> (<N> треков, <size> MB)`
- Просмотр: `sudo journalctl -u aidj-server | grep MIX-CREATED`
- Добавлено 28.06 в строке `print(f"[MIX-CREATED] ...")` в обоих эндпоинтах run_mix (сет) и api_mix_tracks (прямой микс)

#### Логирование (sendLog)
- Все клиентские страницы шлют POST `/api/log` на VPS через туннель
- Аналитика: `sudo journalctl -u aidj-server | grep CLIENT-LOG`

#### Club EQ
- Фиксированный пресет Club, без UI, без слайдеров
- Реализация: Web Audio API, цепочка BiquadFilter-ов
- Цепочка: `source → GainNode → f60(lowshelf +4dB) → f250(peak +3dB) → f1k(peak -2dB) → f4k(peak +3dB) → f12k(highshelf +2dB) → destination`
- **Важно: фильтры подключаются ПОСЛЕ GainNode, а не до.** GainNode → фильтры → destination. Не наоборот.
- AudioContext инициализируется при первом нажатии Play (Chrome autoplay policy)
- `crossorigin="anonymous"` на audio-элементе
- Cloudflare Tunnel отдаёт `Access-Control-Allow-Origin: *` — CORS не проблема

#### Добавление нового трека (алгоритм для Лунта)
**Приоритет поиска mp3 (навсегда):**
1. **VK Music / Mail.ru** — через yt-dlp:
   - Команда: `yt-dlp -f 0 -o "<path>/aidj/<filename>.mp3" "https://my.mail.ru/music/search/<поисковый запрос>"`
   - Получает полный mp3 128-160kbps
   - Западные группы (Guns N' Roses, Rolling Stones) могут быть недоступны в РФ
2. **Hitmotop / музпоисковики** — fallback, если в VK нет
3. **Яндекс.Музыка** — только метаданные (токен в TOOLS.md, библиотека `yandex-music`). Скачивание даёт только preview 30 сек

**После скачивания:**
- Имя файла: латиница без пробелов, подчёркивания вместо пробелов
- `tracks.json`: URL через текущий Cloudflare Tunnel — `https://*.trycloudflare.com/<filename>.mp3`
- Проверить curl что mp3 отдаётся через туннель (HTTP 200)
- Git add + commit + push (только tracks.json, mp3 в .gitignore)
- **ВАЖНО:** tracks.json на VPS и на GitHub синхронизировать (на GitHub — для aidj-player.html)

### Модели LLM
- **deepseek/deepseek-v4-flash** — primary модель (чат в Telegram + новые сессии) с 19.06.2026
- **deepseek/deepseek-chat** — fallback для чата + ВСЕ cron-задачи (дёшево, изолированно)
- GLM-5.1 убрана из primary по указанию Кирилла (19.06.2026)

### Дизайн сайта
- `theme.css` — glass-morphism dark theme (#0a0e14 фон, #161b22 карточки, #21262d бордеры), DESKTOP-FIRST
- `theme.v2.css` — новая версия, используется на index.html
- `style.css` — единый стандарт для плашек на всех страницах (карточки-плашки на главной)
- **Все отчёты** подключают `theme.css` (через `<link rel="stylesheet" href="theme.css">`), без inline CSS
- Классы отчётов: `.container`, `.back`, `.hero`, `.section`, `.tag`, `.item`, `.title`, `.meta`, `.body`, `.highlight`, `.footer`, `.stats-row`, `.stat-box`, `.note`, `.essence`, `.for-citizens`
- Индексная страница (**index.html**) использует `theme.v2.css` + `style.css`

---

## 👥 Люди

### Кирилл (346428630) — Владелец
- Telegram: @Kirill_syst
- Полные права: SSH, config, cron, MEMORY.md
- Получает: алерты об ошибках, отчёты о бэкапах

### Катя (932052526) — Аналитик жалоб
- Роль: мониторинг жалоб по наследству в банках РФ
- Получает: сводка в Telegram ежедневно 08:00 + stats-inheritance.html
- report-katya.html удалён 20.06.2026
- Стиль: прямой, без милоты
- **Skill:** не создан (жалобы — разовые, не нормативная база)

### Лена (254785028) — Аналитик новостей + РЖД
- Роль: мониторинг новостей/законодательства + облигации РЖД 1Р-37R
- Получает: report-lena.html ежедневно 09:00 + сводка РЖД будни 23:55
- Обе задачи переведены на **isolated** сессию (20.06.2026)
- Дедупликация новостей: `memory/lena-news-seen.md`
- **Skill:** `lena-news-expert` (applied 28.06) — шаблоны, категории, дедупликация, LegalMCP для законов
- **Базы знаний:** `knowledge/lena/news-knowledge.md`, `knowledge/lena/rzd-knowledge.md`

### Данил (221828063) — Аналитик компенсаций
- Роль: анализ компенсаций по вкладам СССР 1991
- Получает: report-danil.html пн/чт 10:00
- **Skill:** `danil-vklady-expert` (applied 28.06) — методики расчёта, формулы, категории, LegalMCP для законов
- **База знаний:** `knowledge/danil/vklady-knowledge.md`

### Роман (335268873) — Руководитель Кати
- Роль: ИТ Лидер Трайба
- При первом обращении: рассказать про синтез данных и PowerPoint, напомнить оценить Кирилла на летнем КпТ

### Александр (459758941)
- Telegram: @SirG00se
- Роль: уточняется

---

## ⏰ Cron-задачи (9 штук)

| # | Задача | Расписание | Модель | Кому |
|---|--------|-----------|--------|------|
| 1 | 📋 Катя: сводка жалоб | ежедневно 08:00 | deepseek-chat | Катя |
| 2 | 📊 Статистика жалоб (stats-inheritance) | ежедневно 08:10 | deepseek-chat | — |
| 3 | 📰 Лена: дайджест новостей | ежедневно 09:00 (isolated) | deepseek-chat 300s | Лена |
| 4 | 💰 РЖД 1Р-37R итоги торгов | будни 23:55 (isolated) | deepseek-chat | Лена |
| 5 | 📊 Данил: вклады 1991 (пн) | понедельник 10:00 | deepseek-chat | Данил |
| 6 | 📊 Данил: вклады 1991 (чт) | четверг 10:00 | deepseek-chat | Данил |
| 7 | 💾 Бэкап полный (git push) | воскресенье 03:00 | deepseek-chat | Кирилл |
| 8 | 📋 Катрин: 44-ФЗ/224-ФЗ (LegalMCP) | пн/ср/пт 09:30 | deepseek-chat | Катрин |
|  | 📋 Роза: пособия | понедельник 09:03 | deepseek-chat | Роза |
|  | 📋 Ирина: НПА | понедельник 09:06 | deepseek-chat | Ирина |
  | 🔘 Отчёт по токенам (bash) | ежедневно 03:30 | — | tokens.html (локально) |
  | 🔄 Обновление tasks.html (Health Index) | каждые 3 часа | deepseek-chat 120s | tasks.html (авто: last_run из Gateway + Health Index) |
  | 🤖 AI DJ мониторинг туннеля | каждые 3 часа | deepseek-chat 60s | — (проверка, что туннель жив) |

### Удалённые задачи (20.06.2026)
- ~~Инкрементальный бэкап~~ (удалён)
- ~~Статистика жалоб по месяцам~~ (отключена, удалена)
- ~~Сводка жалоб (кроме Сбера)~~ (отключена, удалена)
- ~~Активность пользователей~~ (удалена 28.06.2026)

### Конфигурация задач
- **Публикация:** все отчёты через `publish-report.sh` (git add → commit → push → GitHub Pages)
- **failureAlert:** после 2 ошибок → Кириллу (cooldown 1 час)
- **sessionTarget:** Катя/Данил/Роза/Ирина/Катрин = `isolated`, Лена/РЖД = её сессия, бэкапы = `isolated`
- **timeout:** 60–600 сек

### 29.06.2026 — Катя: модель и таймаут
- Задача «Сводка жалоб» переведена с deepseek-v4-flash на deepseek-chat (primary)
- deepseek-v4-flash нестабилен: стабильно падал по таймауту 300с, а потом и по LLM error
- timeout увеличен с 300 до 600 секунд
- deepseek-chat дешевле и стабильнее для этой задачи

---

## 📊 Оптимизация токенов (10.06.2026)

### Что сделано:
- Удалён дашборд (каждые 5 мин, ~3.8M токенов/день)
- Удалены 4 статус-задачи (пересказывали отчёты Кириллу, ~1M/мес)
- Сокращены бэкапы с 3x/день до 1x/день (инкремент удалён 20.06.2026, остался только полный)
- Почищены промпты — убраны HTML-шаблоны, заменены на ссылку на theme.css
- Добавлены failureAlert на все задачи

### Результат:
- Было: ~4M токенов/день, 14 задач
- Стало: ~250k токенов/день, 7 задач
- **Экономия: ~94%**

### Метрика эффективности:
`total_tokens / successful_deliveries` — единственная честная метрика
- Катя: ~62k/отчёт
- Лена: ~36k/отчёт
- Данил: ~33k/отчёт

### Известные проблемы:
- DeepSeek Weekly/Monthly Limit — исчерпывается, нужен мониторинг
- Таймауты 120 сек при медленном ответе модели
- 8–9 июня 2026: почти все задачи падали (rate_limit)

---

## 📐 Дизайн-правила

### Единый стандарт — style.css для всех плашек (19.06.2026)
- `style.css` — единый стандарт для плашек на ЛЮБЫХ страницах сайта
- Все плашки обязаны использовать классы из style.css (`.card`, `.card.blue`, `.card-header`, `.card-footer`, `.card-badge`, `.custom-card-component`)
- Селекторы в style.css уточнены родительскими классами: `.cards .card`, `.section .custom-card-component`
- Эмодзи в контенте плашек недопустимы — style.css их не содержит, значит их быть не должно
- Связка: подключение style.css → весь контент плашек должен соответствовать его стилистике

### Главная (index.html) — карточки-плашки
- `.card-footer` содержит имена аналитиков, которые ведут раздел. Не писать «В разработке», не убирать футер.
- Формат: `Имя · Имя · Имя`
- Надписи «→ Перейти» в футере не используем — карточка и так целиком кликабельна.
- Бейджи статуса (`.card-badge`): daily/weekly/ondemand — зелёный/синий/фиолетовый.
- **В `<h2>` на карточках никаких эмодзи/картинок** — только текст (19.06.2026)
- **Glass-card** — термин для UI-стиля плашек (card blue/green/cyan с glass-morphism). Оформление: `.card-header-row` с `<h2>` + `.card-badge`, плоский `.desc`, `.card-footer` с `.person`, без эмодзи в заголовках.
- `theme.css` — единый glass-morphism, все отчёты подключают его.

### Кнопка «назад» — единый стандарт (22.06.2026)
- Класс `.back` — единый для ВСЕХ страниц
- Расположение: левый верхний угол страницы, ПЕРЕД блоком hero/заголовком
- Текст: «← Назад» на всех страницах (кроме stats-inheritance.html — отчёт Кати)
- Ссылка ведёт на страницу выше по иерархии:
  - `index.html` ← корень (без back)
  - `inheritance.html` ← index.html
  - `social.html` ← index.html
  - `report-*.html` ← соответствующая родительская страница (inheritance.html или social.html)
  - `activity.html`, `tasks.html` ← index.html
  - `service_main.html` ← index.html
  - `service.html`, `architecture.html`, `projects.html` ← service_main.html
- Единый стиль определён в `style.css` (`.back`) для страниц, подключающих style.css
- Для страниц с `theme.css` — стиль .back определён в theme.css (аналогичный glass-morphism)
- `report-irina.html` — стиль .back берётся из style.css (inline-стили удалены 22.06.2026)

## 📁 Структура файлов

### Workspace (`/home/user1/.openclaw/workspace/`)
- `AGENTS.md` — поведение агента
- `SOUL.md` — персона/стиль
- `USER.md` — пользователи и роли
- `IDENTITY.md` — кто я
- `TOOLS.md` — заметки об инструментах
- `HEARTBEAT.md` — задачи для heartbeat
- `MEMORY.md` — этот файл
- `theme.css`, `theme.v2.css`, `style.css` — CSS для сайта
- `publish-report.sh` — публикация отчёта через git push
- `upload-to-github.sh` — загрузка файла через git push
- `update-index-github.sh` — обновление дат на nasledstvo.html
- `generate-activity-report.sh` — генерация activity.html
- `backup/backup-incremental.sh` — инкрементальный бэкап
- `backup/backup-full.sh` — полный бэкап

### Memory (`/home/user1/.openclaw/workspace/memory/`)
- `sberbank-inheritance-daily.md` — свежая сводка жалоб (Катя)
- `lena-news-daily.md` — свежий дайджест новостей (Лена)
- `danil-vklady-mon.md` — анализ вкладов пн (Данил)
- `danil-vklady-thu.md` — анализ вкладов чт (Данил)
- `YYYY-MM-DD.md` — дневные заметки

### Дедупликация новостей Лены (20.06.2026)
- Обе задачи Лены (дайджест 09:00 + РЖД 23:55) переведены на **isolated** сессии
- Вместо persistent-сессии — файл `memory/lena-news-seen.md` для дедупликации
- Формат строк: `# YYYY-MM-DD | Заголовок | URL | Источник`
- Задача читает файл перед поиском, пропускает дубликаты, дописывает новые
- timeout увеличен с 180 до 300 сек

### SearXNG (17.06.2026)
- Установлен в Docker на локальном VPS
- Адрес: http://localhost:8888
- JSON API: /search?q=...&format=json
- Использует: Google, Bing, DuckDuckGo (все сразу)
- Заменил web_search и хардкодные URL во всех задачах на 3 запроса к SearXNG
- config: ~/searxng/settings.yml, docker-compose.yml

### Статистика жалоб — автообновление (19.06.2026)
- Cron "📊 Обновление статистики жалоб (stats-inheritance)" — ежедневно 08:10
- Cron читает `katya-stats-data.md`, пересчитывает помесячные суммы, генерирует `stats-inheritance.html` и публикует на GitHub Pages
- Промпт Кати (08:00): запись дневных строк в katya-stats-data.md ОБЯЗАТЕЛЬНА даже при 0 жалоб
- Конвейер: 08:00 → Катя ищет жалобы + пишет katya-stats-data.md → 08:10 → cron обновляет stats-inheritance.html
- **20.06.2026:** report-katya.html удалён. Катя больше не генерирует HTML — только сводка в Telegram
- **Править вёрстку и логику stats-inheritance.html может ТОЛЬКО Катя.** Лунт не трогает.

#### Конвейер задач Кати

**⏰ 08:00 — Сводка жалоб (isolated, deepseek-chat, 300s)**
1. 10 запросов к SearXNG + banki.ru напрямую — только за вчера
2. Фильтр: только жалобы людей, выкинуть новости/юристов
3. Запись в `memory/katya-stats-data.md` — строка `ГГГГ-ММ-ДД | Сбер: X | Другие: N`
4. Запись в `memory/katya-data.json` — каждая жалоба объектом с date/bank/title/description/url/source
5. Сводка в Telegram (банки, количество, суть). Без HTML, без публикации на сайт

**⏰ 08:10 — Обновление статистики (isolated, deepseek-chat, 300s, без ответа в чат)**
1. Читает шаблон `stats-inheritance-template.html` — структуру не трогает
2. Читает `memory/katya-stats-data.md` — пересчитывает помесячные суммы
3. Читает `memory/katya-data.json` — строит хронологию со ссылками
4. Обновляет ТОЛЬКО текстовые данные в шаблоне, сохраняя вёрстку/стили
5. Публикует через publish-report.sh → GitHub Pages

**Итог:** каждая жалоба попадает и в статистику (для таблиц), и в JSON (для хронологии).
Единственная страница Кати на сайте — stats-inheritance.html.

### Все задачи на SearXNG (17.06.2026, финал 17.06 18:00)
- Все 7 поисковых задач переведены на SearXNG через web_fetch с format=json
- **web_search больше НЕ ИСПОЛЬЗУЕТСЯ** ни в одной задаче — DDG bot-detection больше не проблема

#### Катя 08:00 — 10 запросов SearXNG, time_range=day
- наследство банки жалобы, прямые запросы
- report-katya.html больше не генерируется (удалён 20.06.2026)
- Только запись статистики + сводка в Telegram

#### Лена 09:00 — 3 запроса SearXNG, time_range=week
#### Данил пн/чт — 3 запроса SearXNG, time_range=week
#### Роза пн 09:00 — 3 запроса SearXNG, time_range=week
#### Ирина пн 09:06 — 3 запроса SearXNG, time_range=week

Общие улучшения: time_range, чистый JSON, стоп-слова, текстовые маркеры дат, deepseek-chat модель.

## 📊 Система логирования активности (18.06.2026)

Отслеживает запросы пользователей на изменение промптов.

### Компоненты:
- **`prompt-activity.json`** — структурированный лог (массив entries: date, time, user, request, task, change)
- **`prompt-changelog.md`** — человекочитаемая хронология (ведётся параллельно)
- **`log-activity.sh`** — скрипт для добавления записи: `./log-activity.sh <user> "<request>" "<task>" ["<change>"]`
- **`generate-activity-report.sh`** — читает JSON, генерирует activity.html
- **`activity.html`** — страница на GitHub Pages (4 счётчика: сегодня/7д/30д/всего, таблицы по пользователям, по задачам, лента последних 20 запросов)
- **Cron** — 23:50 ежедневно: генерация + публикация через `publish-report.sh`

### Использование:
1. Когда пользователь просит изменить промпт → запустить `log-activity.sh`
2. Cron сам перегенерирует activity.html в 23:50
3. При необходимости — ручной запуск: `bash generate-activity-report.sh && ./publish-report.sh /home/user1/.openclaw/workspace/activity.html activity.html`

### На сайте:
- Карточка «📊 Мониторинг · Активность пользователей» в разделе Сервис
- https://nasledstvo2026.github.io/nasledstvo/activity.html

## 📝 История ключевых решений

### 01.06.2026 — Запуск
- Катя назвала Лунтом
- Созданы IDENTITY.md, USER.md, SOUL.md

### 03.06.2026 — Обновление API
- Новый ключ z.ai

### 05.06.2026 — Роман
- Добавлен в белый список Telegram

### 10.06.2026 — Большая оптимизация
- Dark UI для всех отчётов, единый theme.css
- Оптимизация токенов: 14 → 7 задач, -94% расход
- Добавлены failureAlert
- Создан MEMORY.md

### 20.06.2026 — GitHub Pages
- Полный отказ от Timeweb Cloud
- Переезд на https://nasledstvo2026.github.io/nasledstvo/
- SSH-ключ для GitHub
- Все скрипты и cron-задачи переведены на git push
- MEMORY.md актуализирована

## 🔐 Кибербезопасность экосистемы (28.06.2026)

### Архитектура безопасности

```
[Интернет] → 22 (SSH) · 80 (HTTP) · 443 (HTTPS) · 631 (CUPS)
                ↓
            [UFW — ВЫКЛЮЧЕН 🔴]
                ↓
      [nginx → localhost сервисы]
         ├─ :80 — редирект на HTTPS
         ├─ :443 — self-signed SSL, проксирует:
         │   ├─ / → localhost:8767 (OpenClaw Canvas/UI)
         │   ├─ /canvas/ → localhost:8080
         │   └─ /aidj/ → localhost:8766 (Flask-AIDJ)
         └─ /aidj/ (80) → localhost:8766
```

### Текущее состояние — ИСПРАВЛЕНО (28.06.2026)

| Уровень | Компонент | Статус |
|---------|-----------|--------|
| 🟢 Ок | **UFW/iptables** | Включён. Разрешены только 22, 80, 443. Deny по умолчанию |
| 🟢 Ок | **Flask (8766/8767)** | Оба на 127.0.0.1 — только через nginx |
| 🟢 Ок | **fail2ban** | Активен. SSH jail: bantime 10m, maxretry 5, findtime 10m |
| 🟢 Ок | **CUPS (631)** | Удалён (snap). Порт закрыт |
| 🟢 Ок | **PasswordAuthentication** | no. Только ключи |
| 🟢 Ок | **~/.ssh/timeweb** | Удалён (backup есть) |
| 🟢 Ок | **SSH-ключи** | id_ed25519 с правами 600 |
| 🟢 Ок | **GitHub** | Только SSH-ключ, без пароля |
| 🟢 Ок | **SearXNG** | Только 127.0.0.1:8888 |
| 🟢 Ок | **OpenClaw Gateway** | Только 127.0.0.1:18789 |
| 🟢 Ок | **TLS** | Включён TLSv1.2/1.3, безопасные шифры |
| 🟡 Сред | **Self-signed SSL сертификат** | Браузеры ругаются. Let's Encrypt — потенциально |

### Финальная картина портов

| Порт | Сервис | Слушает | Снаружи |
|------|--------|---------|---------|
| 22 | SSH | 0.0.0.0 | ✅ только ключи + fail2ban |
| 80 | HTTP → HTTPS | 0.0.0.0 | ✅ редирект |
| 443 | HTTPS (nginx) | 0.0.0.0 | ✅ проксирует сервисы |
| 631 | ~~CUPS~~ | ❌ закрыт | ❌ |
| 8766 | aidj-server | 127.0.0.1 | ❌ только через nginx |
| 8767 | photo-server | 127.0.0.1 | ❌ только через nginx |
| 8888 | SearXNG | 127.0.0.1 | ❌ |
| 18789 | OpenClaw Gateway | 127.0.0.1 | ❌ |

### Выполненные исправления (28.06.2026)
1. ✅ UFW включён (22 → 80 → 443 → deny). Auto-enable on boot
2. ✅ aidj-server → 127.0.0.1
3. ✅ photo-server → 127.0.0.1 (8767)
4. ✅ fail2ban — установлен, SSH jail: bantime 10m, maxretry 5
5. ✅ CUPS удалён (snap), порт 631 закрыт
6. ✅ ~/.ssh/timeweb удалён (backup есть)
7. ✅ PasswordAuthentication no

### Что ещё не сделано
- Let's Encrypt для nginx (потенциально)

### Правило: безопасность при разработке
- Новые продукты и сервисы — учитывать кибербезопасность на этапе архитектуры
- Перед деплоем: какие порты открыты, нужен ли фаерволл, какая аутентификация
- Flask/Gunicorn приложения — только на 127.0.0.1, за nginx
- Все web-сервисы — за реверс-прокси, никогда напрямую на 0.0.0.0
- SSH — только ключи, PasswordAuthentication no
- Фаерволл — всегда включён с минимальными правилами
- Брутфорс-защита (fail2ban или аналог) — обязательна на SSH

## 📝 История ключевых решений

### 01.06.2026 — Запуск
- Катя назвала Лунтом
- Созданы IDENTITY.md, USER.md, SOUL.md

### 03.06.2026 — Обновление API
- Новый ключ z.ai

### 05.06.2026 — Роман
- Добавлен в белый список Telegram

### 10.06.2026 — Большая оптимизация
- Dark UI для всех отчётов, единый theme.css
- Оптимизация токенов: 14 → 7 задач, -94% расход
- Добавлены failureAlert
- Создан MEMORY.md

### 20.06.2026 — GitHub Pages
- Полный отказ от Timeweb Cloud
- Переезд на https://nasledstvo2026.github.io/nasledstvo/
- SSH-ключ для GitHub
- Все скрипты и cron-задачи переведены на git push
- MEMORY.md актуализирована

### 20.06.2026 — Удаление report-katya.html
- По просьбе Кати удалён report-katya.html из репозитория
- Обновлён промпт Кати: без HTML-генерации, только поиск + статистика + Telegram
- Почищены ссылки в nasledstvo.html и index-new.html
- Обновлены скрипты публикации

### 28.06.2026 — Большой апдейт безопасности
- Полный аудит безопасности экосистемы
- Включён UFW (правила 22/80/443, остальное deny)
- aidj-server и photo-server переведены на 127.0.0.1
- Установлен и настроен fail2ban для SSH
- CUPS удалён (snap), RCE-вектор устранён
- ~/.ssh/timeweb удалён
- PasswordAuthentication no в sshd_config
- Правило: все новые продукты проходят проверку безопасности на этапе архитектуры
