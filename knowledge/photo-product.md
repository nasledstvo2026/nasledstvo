# 📸 Photo Sync — Архитектура продукта

## Назначение
Страница `photo.html` с галереей фотографий, которые синхронизируются из Dropbox (папка `/photo`). Кнопка «Обновить» — запускает синхронизацию на сервере: скачивает новые изображения, конвертирует в webp, обновляет HTML и пушит на GitHub Pages.

## Архитектура

```
[Браузер] → GitHub Pages (HTTPS)
  ├─ photo.html — страница галереи
  └─ photos/IMG_*.webp — файлы изображений (в репозитории)

[Кнопка «Обновить»]
  └─ fetch() → Cloudflare Photo Tunnel (HTTPS)
       └─ https://*.trycloudflare.com  (МЕНЯЕТСЯ ПРИ РЕСТАРТЕ)
            └─ cloudflared-photo (VPS, systemd)
                 └─ http://localhost:8767
                      └─ photo-server.py (Flask)
                           ├─ GET /sync     — запустить синхронизацию
                           └─ GET /status   — статус последнего запуска
                                └─ фото → photo_sync.py
                                     ├─ Dropbox API (папка /photo)
                                     ├─ pillow + pillow-heif (HEIC → webp)
                                     ├─ обновление photo.html (блок .photo-grid)
                                     └─ git add + commit + push
```

## Компоненты

### 1. Клиентская страница `photo.html`
- **GitHub Pages:** `https://nasledstvo2026.github.io/nasledstvo/photo.html`
- **Папка с фото:** `https://nasledstvo2026.github.io/nasledstvo/photos/`
- Кнопка «Обновить» вызывает `syncPhotos()`:
  1. Отправляет GET `/sync` на Cloudflare Tunnel
  2. Опрашивает GET `/status` каждые 2 сек (до 20 попыток)
  3. Показывает результат: сколько фото добавлено / нет новых / ошибка
- Логгирование: `sendLog(action, data)` → POST `/api/log` (сейчас 404 — эндпоинт не реализован на photo-server)

### 2. Сервер `photo-server.py`
- **Flask** на порту **8767**, слушает только localhost
- Доступен через `cloudflared-photo.service` (Cloudflare Quick Tunnel)
- **Эндпоинты:**
  - `GET /sync` — запускает синхронизацию в фоновом потоке, возвращает HTML-страницу с опросом статуса
  - `GET /status` — JSON: `{running, last_result, last_run}`
- Не имеет `/api/log` (логгирование с клиента не падает — fire-and-forget)

### 3. Движок `photo_sync.py`
- `sync(new_only=True)` — основная функция:
  1. Через `dropbox_utils.py` получает список файлов из `/photo` в Dropbox
  2. Фильтрует изображения (jpg, jpeg, png, heic, heif, gif, bmp, tiff, webp)
  3. Скачивает новые (или все, если `--all`)
  4. Конвертирует в webp (pillow + pillow-heif, quality=85, method=6)
  5. Удаляет оригинал после конвертации
  6. Обновляет блок `.photo-grid` в `photo.html` — заменяет только содержимое между `<div class="photo-grid">` и соответствующим `</div>`
  7. Сохраняет состояние: `photo-state.json` (список опубликованных файлов)
  8. `git add -A && git commit -m "📸 Photo sync — <дата>" && git push`

### 4. Cloudflare Tunnel
- **Сервис:** `cloudflared-photo.service`
- **Тип:** Quick Tunnel (URL меняется при рестарте)
- **Назначение:** проброс `localhost:8767` в публичный HTTPS
- **Named tunnel не активирован** (ждёт домен)

## Файлы на VPS

| Файл | Назначение |
|------|-----------|
| `/home/user1/.openclaw/workspace/photo-server.py` | Flask-сервер |
| `/home/user1/.openclaw/workspace/photo_sync.py` | Движок синхронизации |
| `/home/user1/.openclaw/workspace/photo.html` | Основной файл, редактируется скриптом |
| `/home/user1/.openclaw/workspace/photos/` | Папка с webp-файлами |
| `/home/user1/.openclaw/workspace/photo-state.json` | Состояние: какие файлы уже обработаны |
| `/home/user1/.openclaw/workspace/scripts/dropbox_utils.py` | Dropbox API (list_files, download_file) |

## Systemd-сервисы

```bash
sudo systemctl status photo-server      # Flask на 8767
sudo systemctl status cloudflared-photo  # Cloudflare туннель
sudo journalctl -u photo-server          # логи синхронизации
```

## Порядок обновления URL туннеля

Если `cloudflared-photo` перезапустился, URL изменился. Надо обновить в `photo.html` переменную `BASE_URL`:

```bash
NEW_URL=$(sudo journalctl -u cloudflared-photo --no-pager 2>&1 | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)
cd /home/user1/.openclaw/workspace
sed -i "s|const BASE_URL = 'https://[a-z0-9-]*\.trycloudflare\.com'|const BASE_URL = '$NEW_URL'|" photo.html
git add photo.html && git commit -m "photo: updated tunnel URL" && git push
```

## Известные проблемы

1. **`photo_files/` не работал на GitHub Pages** — переименовано в `photos/` (15.07.2026). Причина: GitHub Pages может игнорировать папки с подчёркиванием даже при наличии `.nojekyll`.
2. **Скрипт на VPS может устареть** — если править пути в `photo.html` вручную, надо обязательно синхронизировать и `photo_sync.py`, иначе скрипт перезапишет HTML со старыми путями.
3. **`/api/log` не реализован** — `sendLog()` на клиенте шлёт POST, но сервер отдаёт 404. Логирование не работает (только журнал сервера через `journalctl`).

## Требования для работы

- Python: `flask`, `flask-cors`, `Pillow`, `pillow-heif`, `dropbox` SDK
- Dropbox App: refresh token + app credentials (`~/.dropbox_token`, `~/.dropbox_refresh_token`, `~/.dropbox_app_creds`)
- Git SSH доступ к GitHub (ключ `~/.ssh/id_ed25519`)
- cloudflared установлен и настроен
- Папка `photo/` в Dropbox
