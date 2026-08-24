# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Инфраструктура

### GitHub Pages
- Репозиторий: `nasledstvo2026/nasledstvo`
- Ветка для пуша: `master` (workflow деплоит из master → gh-pages)
- ⚠️ НИКОГДА не пушить напрямую в `gh-pages` — воркфлоу не запустится, страница не обновится
- Workflow: `.github/workflows/deploy-pages.yml`, триггер: `push → master`
- Процесс: `git add` → `git commit` → `git push origin master` → ждать деплой (~30 сек)
- Проверка: `curl -s https://nasledstvo2026.github.io/nasledstvo/ | grep -c 'ключевое_слово'`
- Домен: `https://nasledstvo2026.github.io/nasledstvo/`
- Remote: `origin` (git@github.com:nasledstvo2026/nasledstvo.git)

### VPS (Лунт)
- Хост: vm-low4-8
- ОС: Linux 6.8.0-136-generic (x64)
- Node: v22.23.1
- Gateway: OpenClaw

### VPS Феникс (соседний OpenClaw)
- IP: `213.171.25.85` | пользователь: `user1` | hostname: `vm-low4-8` (НЕ vm-f13581)
- Ключ: `~/.ssh/fenix` (права 600) — идентичен `new-vps-key`
- Passphrase ключа: в `~/.ssh/askpass.sh`
- SSH: `SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force ssh -i ~/.ssh/fenix user1@213.171.25.85`
- OpenClaw 2026.6.11, порт 18789, systemd user unit `openclaw-gateway.service`
- Workspace: `/home/user1/phoenix/` | fz425-agent: `/home/user1/phoenix/fz425-agent/`
- Перезапуск: ТОЛЬКО `bash ~/phoenix/safe-restart.sh` (НЕ systemctl restart!)
- Команда «почини Феникса» → SSH-подключение + диагностика (статус, логи, диск/RAM)
- ⚠️ fail2ban банит IP на ~10 мин после перебора пользователей — не перебирать
- ⚠️ `openclaw tui` на Фениксе перезаписывает openclaw.json — не трогать конфиг из TUI
- ⚠️ НЕ ставить `tools.allow: ['message']` — такого инструмента нет, агенты становятся немыми
- Маршрутизация: «Федор» в начале сообщения → fz425-agent; иначе main (подробности: memory/2026-08-01.md)
- Мониторинг: «статус Феникса» → SSH `bash ~/health.sh` (CPU/RAM/DISK/Swap/топ-процессы)
- Мониторинг живой: «живой статус Феникса» → 3 замера с интервалом 2 сек
- Мониторинг прогона: «прогон жив?» / «статус прогона» → SSH `bash ~/check-run.sh` (вердикт по model-fetch активности + load/RAM/диск/xlsx: ✅ завершён / 🟢 идёт / 🔴 стоит). model-fetch — главный признак реальной работы subagent'а (xlsx/лог оркестратора обновляются только при завершении региона).
- Интерактивный: tmux-сессия `monitor` (htop), подключение: `ssh -i ~/.ssh/fenix user1@213.171.25.85 -t tmux attach -t monitor`

### Поиск (XMLRiver Яндекс.XML)
- Эндпоинт: `https://xmlriver.com/search_yandex/xml?user=22347&key=***&query=...`
- user=22347, ключ вшит в промпты кронов lena-search-agent и search-agent
- ⚠️ XMLRiver НЕстабилен с этого VPS: запросы иногда висят >12с (http=000), иногда отвечают за 2с. В промптах кронов уже стоит `-m 15`; при 2+ таймаутах подряд агент переключается на прямой сбор RSS/sitemap белых доменов.
- Тариф Базовый ₽25/1000 (Яндекс.XML), расход ~₽40-90/мес
- Параметры: `lr=225` (РФ), `sortby=tm` (свежесть) / `rlv` (релевантность), `groupby` для плоской выдачи
- Ответ — XML (тэги <url>, <title>, <passage> внутри <doc>/<group>)
- Кабинет/пополнение: https://xmlriver.com/account/
- SearXNG (docker) погашен 2026-08-23; файлы сохранены в workspace/searxng/ (вернуть: `docker compose up -d`)

### Сбор новостей Лены (lena-search-agent)
- Реестр источников: `knowledge/lena/sources.json` — 14 доменов; whitelist генерится из ключей реестра
- Выходные файлы: `agents/shared/lena-raw.json` → `lena-verified.json` (verifier) → `lena-news-seen.md` (дедуп)
- `/tmp`-пути Лены: `lena_raw_sources.txt` / `lena_filtered.json` (НЕ пересекаются с search-agent)
- Сбор по типу источника: `rss` (rbc/tass/kommersant/vedomosti/mintrud) / `html` / `sitemap` (rg — 3 уровня)
- ⚠️ Все curl с `-A` (User-Agent): tass.ru без UA отдаёт 403, с UA — RSS 200. pravo.gov.ru — JS-only (API http 000), nalog.gov.ru — через rn77-зеркало
- Тематический фильтр на Этапе 1 (python, без LLM): стемы наследств/наследник/наследодател/наследован/наследуем/завещан/завещател/выморочн (без «наслед*»→наследие, без «умерш/вдов»=некрологи). Этап 2 — БЕЗ web_fetch (иначе падение LLM)
- Кроны (МСК): lena-search-agent 02:00 → lena-verify-agent 02:10 → lena-html-agent 02:20
- Бэкапы/откат 24.08: `sources.json.bak-20260824-090151`, `lena-search-prompt.bak-20260824-{090200,093000}`, `*.bak-20260824-004356.*`

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Related

- [Agent workspace](/concepts/agent-workspace)
