# AI DJ — Архитектура (актуальная, 26.06.2026)

## 1. Компоненты

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Pages (HTTPS)                      │
│  nasledstvo2026.github.io/nasledstvo                        │
│                                                             │
│  aidj.html          — хаб-лендинг с плитками                │
│  aidj-delete.html   — страница удаления треков              │
│  aidj-player.html   — плеер всех треков                     │
│  aidj-presets.html  — стили сведения диджеев                │
│  tracks.json        — копия треклиста (для быстрой загрузки)│
│  aidj/djset.html    — создание DJ Set (редирект)            │
└──────────────────────┬──────────────────────────────────────┘
                       │ fetch /tracks.json (HTTPS, same origin)
                       │ 
┌──────────────────────▼──────────────────────────────────────┐
│              Cloudflare Tunnel (HTTPS, валидный SSL)         │
│  about-wish-ties-capture.trycloudflare.com                  │
│                                                             │
│  ┌────────────────────────────────────────────────────┐     │
│  │  nginx (80→443, 443→Flask) + CORS заголовки set     │     │
│  │  176.123.162.12 (VPS)                               │     │
│  └──────────────────────┬─────────────────────────────┘     │
│                         │ proxy_pass :8766                   │
│  ┌──────────────────────▼─────────────────────────────┐     │
│  │  Flask (aidj-server.py, порт 8766)                  │     │
│  │                                                     │     │
│  │  GET  /tracks.json        — треклист                │     │
│  │  POST /api/tracks/delete  — удаление треков         │     │
│  │  GET  /delete             — страница удаления (old) │     │
│  │  GET  /<path:filename>    — статика (mp3 и др.)     │     │
│  │  GET  /djset.html        — DJ Set интерфейс         │     │
│  └─────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

## 2. Детали

### 2.1. Страница удаления (aidj-delete.html)

- Лежит на GitHub Pages (HTTPS, тот же origin что aidj.html)
- `tracks.json` загружает через fetch оттуда же (быстрая загрузка, без CORS)
- Удаление: `POST` на Cloudflare Tunnel → nginx → Flask
- Flask удаляет трек из `tracks.json`, пушит изменения в git, удаляет mp3 с диска

### 2.2. Cloudflare Tunnel

- Quick tunnel (без аккаунта): `cloudflared tunnel --url http://localhost:8766`
- Даёт HTTPS с валидным сертификатом (no self-signed)
- URL меняется при перезапуске! Нужно обновлять в aidj-delete.html
- **TODO:** перейти на named tunnel с фиксированным URL

### 2.3. tracks.json

- Хранится: в `/home/user1/.openclaw/workspace/aidj/tracks.json` (VPS) + копия в корне репозитория (GitHub Pages)
- После удаления трека Flask пушит обновлённую версию через git
- На GitHub Pages копия — для быстрой загрузки страницы удаления

## 3. Хостинг

| Компонент | Хостинг | Протокол |
|-----------|---------|----------|
| Хаб (aidj.html) | GitHub Pages | HTTPS |
| Удаление (aidj-delete.html) | GitHub Pages | HTTPS |
| Плеер (aidj-player.html) | GitHub Pages | HTTPS |
| Пресеты (aidj-presets.html) | GitHub Pages | HTTPS |
| tracks.json (быстрый fetch) | GitHub Pages | HTTPS |
| API / tracks.json (автор.) | VPS Flask :8766 | HTTPS (Cloudflare) |
| MP3-файлы | VPS диск | HTTPS (Cloudflare) |
| DJ Set (djset.html) | VPS Flask | HTTPS (Cloudflare) |

## 4. Структура файлов

```
aidj/
├── ARCHITECTURE.md          # этот файл
├── aidj-server.py           # Flask сервер (основной компонент)
├── aidj-engine.py           # движок сведения (librosa + ffmpeg)
├── aidj-session.py          # управление сессиями
├── aidj-web.py              # веб-сокеты
├── aidj-mix.py              # миксер
├── aidj-handler.py          # хэндлер команды /dj
├── analizers/track_structure.py  # анализ структуры трека
├── mixers/phase_mixer.py    # фазовый миксер
├── mixers/smart_crossfade.py # умный кроссфейд
├── presets/                  # стили сведения
│   ├── default-preset.json
│   ├── oakenfold-preset.json
│   ├── oakenfold-fantazia-preset.json
│   ├── oakenfold-tranceport-preset.json
│   └── engine.py
├── tracks.json               # треклист
├── mixes.json                # сохранённые сеты
├── sets/                     # DJ Set'ы (JSON)
├── player/index.html         # HTML5 плеер
├── djset.html                # веб-интерфейс DJ Set
├── djset-github.html         # редирект на djset.html
├── aidj-hero.jpg             # логотип для хаба
└── *.mp3                     # аудиофайлы
```

## 5. Изменения от предыдущей версии

| Было | Стало | Причина |
|------|-------|---------|
| HTTPS self-signed напрямую на VPS | Cloudflare Tunnel | Safari не принимал self-signed |
| aidj-delete.html на VPS (same origin) | aidj-delete.html на GitHub Pages | mixed content в HTTPS-странице |
| tracks.json только на VPS | tracks.json дублирован на GitHub Pages | ускорение загрузки страницы удаления |

## 6. Проблемы и TODO

- [ ] Перейти на named Cloudflare Tunnel (фиксированный URL, без смены при перезапуске)
- [ ] Перейти на Let's Encrypt при появлении домена (отказ от туннеля)
- [ ] tracks.json может рассинхронизироваться между VPS и GitHub Pages
- [ ] Обновление URL туннеля в aidj-delete.html при перезапуске
