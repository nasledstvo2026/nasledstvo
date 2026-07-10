# AI DJ — Архитектура (актуальная, 27.06.2026)

## 1. Компоненты

```
┌──────────────────────────────────────────────────────────────────┐
│                    GitHub Pages (HTTPS)                           │
│  nasledstvo2026.github.io/nasledstvo                             │
│                                                                  │
│  aidj.html          — хаб-лендинг с плитками                     │
│  aidj-delete.html   — страница удаления треков                   │
│  aidj-player.html   — плеер всех треков                          │
│  aidj-presets.html  — стили сведения диджеев                     │
│  tracks.json        — копия треклиста (для быстрой загрузки)     │
│  aidj/*.mp3         — аудиофайлы треков                          │
│  aidj/ARCHITECTURE.md — архитектурная документация               │
│  aidj/aidj-hero.jpg  — логотип для хаба                          │
│  aidj/djset.html     — DJ Set на VPS (редирект или full-page)    │
│  aidj/djset-github.html — редирект на VPS                        │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        │ fetch /tracks.json (HTTPS, same origin)
                        │ fetch /aidj/*.mp3 (HTTPS, same origin)
                        │ POST на API через Cloudflare Tunnel
                        │
┌───────────────────────▼──────────────────────────────────────────┐
│              Cloudflare Tunnel (HTTPS, валидный SSL)              │
│  about-wish-ties-capture.trycloudflare.com                       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  nginx (порты 80+443), прокси + CORS                     │    │
│  │  176.123.162.12 (VPS)                                    │    │
│  │  HTTP 80 → /aidj/ без SSL (не используется больше)       │    │
│  │  HTTPS 443 → всё через туннель                           │    │
│  └──────────────────────┬──────────────────────────────────┘    │
│                         │ proxy_pass :8766                       │
│  ┌──────────────────────▼──────────────────────────────────┐    │
│  │  Flask (aidj-server.py, порт 8766)                       │    │
│  │                                                          │    │
│  │  GET  /tracks.json        — треклист                     │    │
│  │  POST /api/tracks/delete  — удаление треков              │    │
│  │  GET  /delete             — статика aidj-delete.html    │    │
│  │  GET  /<path:filename>    — остальная статика            │    │
│  │  GET  /djset.html        — DJ Set интерфейс             │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

## 2. Детали

### 2.1. Хаб (aidj.html)

- Статическая страница на GitHub Pages
- Плитки-метро: Добавить → Telegram (инструкция), Удалить → aidj-delete.html, Слушать → aidj-player.html, Создать → djset.html
- Стиль glass-morphism, тёмная тема
- Никаких внешних запросов — грузится мгновенно

### 2.2. Страница удаления (aidj-delete.html)

- Лежит на GitHub Pages (HTTPS, тот же origin что хаб)
- `tracks.json` загружает через fetch с GitHub Pages (HTTPS, тот же origin)
- Удаление: `POST` на Cloudflare Tunnel → nginx → Flask
- URL туннеля жёстко прописан в коде (пока quick tunnel)
- **Flask делает git push** с обновлённым tracks.json после удаления

### 2.3. Плеер (aidj-player.html)

- Лежит на GitHub Pages (HTTPS)
- Динамическая загрузка треков из `tracks.json` через fetch
- Кнопка **«⟳ Обновить»** — перезагружает список из JSON
- Статистика (кол-во треков, MB) автоматически обновляется
- Аудиофайлы (mp3) лежат в репозитории → GitHub Pages → HTTPS
- Длительность парсится из поля `duration` в tracks.json

### 2.4. Cloudflare Tunnel

- Quick tunnel: `cloudflared tunnel --url http://localhost:8766`
- Бесплатный, не требует аккаунта
- Даёт HTTPS с валидным сертификатом Cloudflare (не self-signed)
- **URL меняется при перезапуске туннеля** — нужно обновлять в aidj-delete.html
- Туннель живёт, пока жив процесс cloudflared

### 2.5. tracks.json

- **Два источника:**
  - `/home/user1/.openclaw/workspace/aidj/tracks.json` — VPS (авторитетный, Flask его обновляет)
  - `/home/user1/.openclaw/workspace/tracks.json` — GitHub Pages (копия для быстрой загрузки)
- Flask после удаления обновляет VPS-копию и пушит в git (обе копии синхронизируются)
- При добавлении трека обновляются обе

### 2.6. Добавление треков

- Формат: `Лунт, добавь трек Исполнитель — Название`
- Лунт ищет mp3 в интернете, скачивает, добавляет в `tracks.json`, пушит в git
- mp3 кладутся в `aidj/` и пушатся на GitHub (>100 MB не проходят)

## 3. Хостинг

| Компонент | Хостинг | Протокол | Доступность |
|-----------|---------|----------|-------------|
| Хаб (aidj.html) | GitHub Pages | HTTPS | Всегда |
| Удаление (aidj-delete.html) | GitHub Pages | HTTPS | Всегда |
| Плеер (aidj-player.html) | GitHub Pages | HTTPS | Всегда |
| Пресеты (aidj-presets.html) | GitHub Pages | HTTPS | Всегда |
| tracks.json (fetch) | GitHub Pages | HTTPS | Всегда |
| MP3-файлы | GitHub Pages | HTTPS | Всегда |
| Треклист (авторитетный) | VPS Flask :8766 | HTTPS (Cloudflare) | Пока жив tunnel |
| API удаления | VPS Flask :8766 | HTTPS (Cloudflare) | Пока жив tunnel |
| DJ Set | VPS Flask :8766 | HTTPS (Cloudflare) | Пока жив tunnel |

## 4. Структура файлов

```
aidj/
├── ARCHITECTURE.md           # этот файл
├── aidj-server.py            # Flask сервер (основной компонент)
├── aidj-engine.py            # движок сведения (librosa + ffmpeg)
├── aidj-session.py           # управление сессиями
├── aidj-web.py               # веб-сокеты
├── aidj-mix.py               # миксер
├── aidj-handler.py           # хэндлер команды /dj
├── analizers/
│   └── track_structure.py    # анализ структуры трека
├── mixers/
│   ├── phase_mixer.py        # фазовый миксер
│   └── smart_crossfade.py    # умный кроссфейд
├── presets/                  # стили сведения
│   ├── default-preset.json
│   ├── oakenfold-preset.json
│   ├── oakenfold-fantazia-preset.json
│   ├── oakenfold-tranceport-preset.json
│   └── engine.py
├── tracks.json               # треклист (авторитетный)
├── mixes.json                # сохранённые сеты
├── sets/                     # DJ Set'ы (JSON)
├── player/index.html         # HTML5 плеер
├── djset.html                # веб-интерфейс DJ Set
├── djset-github.html         # редирект на djset.html
├── aidj-hero.jpg             # логотип для хаба
├── *.mp3                     # аудиофайлы (также в корне git)
```

## 5. Изменения от предыдущей версии

| Было | Стало | Когда | Причина |
|------|-------|-------|---------|
| HTTPS self-signed напрямую на VPS | Cloudflare Tunnel | 26.06 | Safari не принимал self-signed |
| aidj-delete.html на VPS | aidj-delete.html на GitHub Pages | 26.06 | mixed content в HTTPS-странице |
| tracks.json только на VPS | tracks.json дублирован на GitHub Pages | 26.06 | ускорение загрузки |
| Статичный список треков в плеере | Динамическая загрузка из JSON | 26.06 | автоматическое обновление списка |
| mp3 только на VPS | mp3 в git → GitHub Pages | 26.06 | плеер не играл без mp3 на Pages |
| HTTP API на VPS (порт 80) | Cloudflare Tunnel (только HTTPS) | 26.06 | Safari блокировал mixed content |
| Плитки с длинными названиями | Лаконичные: Добавить/Удалить/Слушать/Создать | 26.06 | UX |

## 6. Проблемы и TODO

### Критические
- [ ] Cloudflare Tunnel — **quick tunnel, URL меняется при перезапуске**. Настроить named tunnel с фикс. URL
- [ ] Если cloudflared упадёт — API удаления и DJ Set недоступны. Добавить systemd сервис с auto-restart

### Важные
- [ ] tracks.json может рассинхронизироваться между VPS и GitHub Pages (если править вручную)
- [ ] mp3 >100 MB не пушатся на GitHub (сейчас Fantazia 1997 — 99.3 MB, на грани)
- [ ] Нет мониторинга — жив ли туннель

### Желательные
- [ ] Перейти на Let's Encrypt при появлении домена (отказ от туннеля)
- [ ] .gitignore больше не исключает mp3 (был `aidj/*.mp3` — удалён 27.06)

## 7. Как добавить трек (SOP)

1. Пользователь пишет: `Лунт, добавь трек Исполнитель — Название`
2. Лунт ищет mp3 в открытых источниках (hitmotop, pesni.fm)
3. Скачивает в `aidj/<Исполнитель> - <Название>.mp3`
4. Добавляет запись в `aidj/tracks.json` (artist, title, url, duration, size_bytes)
5. Копирует в корневой `tracks.json`
6. Пушит всё в git
7. Через 1-2 мин трек доступен на всех страницах
