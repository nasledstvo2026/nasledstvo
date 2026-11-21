# Пайплайны

### Статистика жалоб (stats-agent)
- Генератор отчёта: `scripts/stats_inheritance_gen.py` → `reports/stats-inheritance.html` (читает ТОЛЬКО агрегаты `/home/user1/.openclaw/agents/shared/katya-summary-7d.json`)
- Пайплайн: `scripts/katya_merge.py` (синк базы, идемпотентно) → генератор → `bash publish-report.sh reports/stats-inheritance.html stats-inheritance.html`
- ⚠️ `publish-report.sh` делает `git add -A` — любые мусорные файлы в workspace (напр. `advg.out`/`advg.err` от 18.09.2026) уезжают в коммит Pages. Проверять `git status` перед публикацией

### Сбор жалоб по наследству (search-agent / katya)
- ✅ (16.10.2026) Сборщик `scripts/katya_collect.py`: banki (`?type=all&page=1..12`), pravoved (лента Next.js JSON + поиск SSR-HTML), pikabu (тег, cp1251, `data-story-id`/`data-timestamp`), advgazeta (HTML). Пишет `/tmp/raw_complaints.txt` + `/tmp/filtered.json`, считает счётчики и блокировки. Кэш в `req()` (файл <15 мин — без нового запроса).
- ⚠️ У банка в ленте `?type=all` встроенный JSON `data-module-options` → `responses.data[]` содержит полный `title`/`text`/`company.name`/`dateCreate`. Карточки качать НЕ нужно.
- Урожайность banki ~0,3% (1 наследственная на ~270 отзывов полного потока). За прогон 12 стр. (~300 отзывов ≈ 5 ч потока) — обычно 0–1 кейс.
- pravoved `/search/?q=` — SSR-страница (БЕЗ `__NEXT_DATA__`), результаты в `<article class="questionBody">` / `divH3 a` — но выдача архивная (2016–2021), почти всё уже в seen.

### Сбор жалоб по наследству (search-agent / katya) — старое
- ⚠️ banki.ru: дефолтная лента `/services/responses/list/?page=N` — ЭТО КУРИРУЕМАЯ ВЫБОРКА ~25 отзывов/СУТКИ (свежайший имеет задержку ~15ч). За 7 дней (N=1..18, 450 отзывов) наследственных тем — 0.
- ✅ ПОЛНЫЙ поток — `/services/responses/list/?type=all&page=N` (25 отзывов за ~25 мин ≈ 1400/сутки; неизвестный type тоже падает в all). Наследственных ≈0,3% (1 на ~300). За 7 дней это ~10 000 отзывов / ~400 страниц → полный обход нереален под лимитом IP.
- ✅ (01.10.2026) В HTML ленты banki есть `data-module-options='{...}'` (HTML-escaped JSON, ключ `responses.data[]`) с ПОЛНЫМ текстом отзыва (`title`, `text`), `company.name` (банк) и `dateCreate`. Карточки качать НЕ нужно — экономит десятки запросов и снимает риск бана IP. Парсер: `max(re.findall(r"data-module-options='(.*?)'\s", h, re.S), key=len)` → `json.loads(html.unescape(blob))['responses']['data']`.
- У lд+json ленты (`Organization.review[]`) есть name/datePublished/reviewBody/itemReviewed.name (банк) — текст отзыва и банк доступны прямо из ленты; id/url берутся из HTML-блоков `<h3 ...ldecc766d>` (порядок совпадает 1:1, проверено).
- ⚠️ Ссылки `?keyword=/q=/search=/keywords=` ИГНОРИРУЮТСЯ (возвращается дефолт). Фильтра по ключу у банка нет.
- banki.ru: лента `/services/responses/list/?page=N` (25 отзывов/стр., пагинация до N=13 = ~7 дней), карточки `/services/responses/bank/response/<id>/`
- ⚠️ Лимит на IP ~50 запросов подряд (13 стр. ленты + ~37 карточек) → затем http=000 на ~1,5 ч. Феникс (другой IP) даёт ещё ~55 карточек, потом банит и его
- ⚠️ ld+json в карточках banki содержит literal control-чары → `json.loads(..., strict=False)`, иначе Review-блок не парсится и body=0/банк=None
- Дата карточки: `itemprop="datePublished" content=...` (в старом скрипте был неверный regex → date=None)
- Запасной egress: Феникс (`ssh -i ~/.ssh/fenix user1@213.171.25.85`) — curl там отдаёт полные карточки banki
- pravoved.ru: после ~30 запросов отдаёт 429 (rate-limit), лента без пагинации
- ✅ (01.10.2026) pravoved.ru — Next.js: полный JSON вопроса в `<script id="__NEXT_DATA__">`. Лента `/questions/`: `props.pageProps.reduxState.page.questions.questions.items` (id, title, text, url, datePublish — unix). Карточка `/question/<id>/`: `...page.question.question` (тот же набор). Поиск `/search/?q=` отдаёт СТАРОЕ (2016–2022), релевантность слабая (по «наследство банк» лезет кредит/комиссии) — фильтровать стемами и по дате.

### Поиск (внешние API — выведены из схемы)
- XMLRiver (Яндекс.XML) и SearXNG **выведены из схемы** (23–28.08.2026): ключ XMLRiver невалиден (code 42), SearXNG погашен. Сбор полностью автономный — curl по белым доменам (rss/sitemap/html), без внешних поисковых API.
- `web_search`-провайдер не настроен → у всех агентов пайплайна `web_search` убран из `toolsAllow` (25.09.2026).

### Сбор новостей Лены (lena-search-agent)
- Реестр источников: `knowledge/lena/sources.json` — 17 доменов; whitelist генерится из ключей реестра
- Выходные файлы: `agents/shared/lena-raw.json` → `lena-verified.json` (verifier) → `lena-news-seen.md` (дедуп)
- `/tmp`-пути Лены: `lena_raw_sources.txt` / `lena_filtered.json` (НЕ пересекаются с search-agent)
- Сбор по типу источника: `rss` (rbc/tass/kommersant/vedomosti/mintrud/ria/lenta/interfax) / `html` (banki.ru: + жалобы /services/responses/ + вопросы /services/questions-answers/) / `sitemap` (rg — 3 уровня)
- ⚠️ Все curl с `-A` (User-Agent): tass.ru без UA отдаёт 403, с UA — RSS 200. pravo.gov.ru — JS-only (API http 000), nalog.gov.ru — через rn77-зеркало
- Тематический фильтр на Этапе 1 (python, без LLM): стемы наследств/наследник/наследодател/наследован/наследуем/завещан/завещател/выморочн (без «наслед*»→наследие, без «умерш/вдов»=некрологи). Этап 2 — БЕЗ web_fetch (иначе падение LLM)
- Кроны (МСК): lena-search-agent 02:00 → lena-verify-agent 02:10 → lena-html-agent 02:20
- Бэкапы/откат 24.08: `sources.json.bak-20260824-090151`, `lena-search-prompt.bak-20260824-{090200,093000}`, `*.bak-20260824-004356.*`
- ⚠️ Даты в `parse_html_source` (`scripts/lena_collect.py`): приоритет — URL-path (YYYY/MM/DD) → дата из контекста ленты → суффикс `-DDMM`. У notariat.ru суффикс `-2609` = год+месяц (сентябрь 2026), НЕ день: старая логика давала 2025-09-26 и теряла свежие новости. Фикс 16.09.2026, бэкап `lena_collect.py.bak-20260916-0215`
- Если `lena-raw.json` пуст — сначала `grep -icE 'наследств|завещан' /tmp/lena_raw_sources.txt` и смотреть даты в дампе, а не только raw.json

