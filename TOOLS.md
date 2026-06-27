# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## Dropbox

- **SDK:** Python dropbox 12.0.2 (`pip3 install dropbox --break-system-packages`)
- **Скрипт скачивания:** `scripts/dropbox-get.py`
- **Требуется:** OAuth 2 access token в `~/.dropbox_token`, либо shared link
- **Режимы:**
  - По пути в Dropbox (с refresh token — рекомендуется): `--path "/folder/file.ext" --output ./file.ext`
  - С явным access token: `--token TOKEN --path "/folder/file.ext" --output ./file.ext`
  - По shared link: `--shared-link "https://www.dropbox.com/s/xxx/file?dl=0" --output ./file.ext`
- **Refresh token** (бессрочный): `~/.dropbox_refresh_token`
- **App creds:** `~/.dropbox_app_creds` (app_key + app_secret)
- **Владелец:** 9215691@inbox.ru (Kirill)

## Yandex Music API
- **Токен:** `y0__wgBEPPn3YsEGI_CRCCe8YSKGLzb3G0HcIjxhfJUCZOS7lYBvqjC` (получен 27.06.2026)
- **Библиотека:** `yandex-music 3.0.0`
- **Поиск:** `client.search('текст').tracks.results[0]`
- **Скачивание:** работает только preview (30 сек). Полный трек — через yt-dlp (mail.ru/VK Music)
- **Обновление токена:** `curl -X POST 'https://oauth.yandex.ru/token' -d 'grant_type=refresh_token' -d 'refresh_token=***' -d 'client_id=...'`

## VK Music / Mail.ru (yt-dlp)
- **Приоритет:** #1 при поиске и скачивании mp3 треков
- **Команда:** `yt-dlp -f 0 -o "output.mp3" "https://my.mail.ru/music/search/<поисковый запрос>"`
- **Файлы:** полные mp3 128-160kbps, ~10 MB за трек
- **Поиск ID:** `yt-dlp --print "id,title" "https://my.mail.ru/music/search/<запрос>"`
- **Guns N' Roses, Rolling Stones** и другие западные группы могут быть недоступны в РФ

## GitHub Pages (текущий хостинг)

- **Сайт:** https://nasledstvo2026.github.io/nasledstvo/
- **Репозиторий:** git@github.com:nasledstvo2026/nasledstvo.git
- **SSH ключ:** `~/.ssh/id_ed25519` (добавлен на GitHub)
- **Публикация:** `./publish-report.sh <local-file> <filename>`
- **Загрузка:** `./upload-to-github.sh <local-file> <filename>`
- **Обновление дат:** `./update-index-github.sh <report-filename> <timestamp>`

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

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
