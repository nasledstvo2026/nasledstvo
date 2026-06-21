# Dropbox Tools — работа с файлами

## Установка
- Python SDK: `pip3 install dropbox --break-system-packages` (уже установлен)

## Токен доступа

Чтобы скрипты работали, нужен **OAuth 2 access token** от твоего Dropbox-аккаунта:

1. Зайди на https://www.dropbox.com/developers/apps
2. Create app → Scoped access → App folder или Full Dropbox
3. В настройках приложения → **Generate access token** (в разделе OAuth 2)
4. Скопируй токен и передай мне — сохраню в `~/.dropbox_token`

## Скрипты

### `dropbox-get.py` — скачать файл из Dropbox
- По прямому пути в Dropbox (нужен токен)
- По расшаренной ссылке (токен не нужен)

### `dropbox-upload.py` — загрузить файл в Dropbox (нужен токен)

## Использование в задачах

Из cron/задач дёргать так:

```bash
python3 /home/user1/.openclaw/workspace/scripts/dropbox-get.py \
  --token "$(cat ~/.dropbox_token)" \
  --path "/Dropbox/папка/файл.xlsx" \
  --output /home/user1/.openclaw/workspace/data/file.xlsx
```

Или по shared link:

```bash
python3 /home/user1/.openclaw/workspace/scripts/dropbox-get.py \
  --shared-link "https://www.dropbox.com/s/xxxxx/file.xlsx?dl=0" \
  --output /home/user1/.openclaw/workspace/data/file.xlsx
```
