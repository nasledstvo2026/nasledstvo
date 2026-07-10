#!/bin/bash
# Скачивает mp3 из Dropbox (/ai-dj/files/) в репозиторий и обновляет плеер

set -e

WORKSPACE="/home/user1/.openclaw/workspace"
AIDJ_DIR="$WORKSPACE/aidj"
PLAYER_FILE="$WORKSPACE/aidj-player.html"

mkdir -p "$AIDJ_DIR"

# Скачиваем треки через dropbox-get.py
cd "$WORKSPACE"

# Получаем список файлов через Python
python3 -c "
import dropbox, os

REFRESH_TOKEN_FILE = os.path.expanduser('~/.dropbox_refresh_token')
APP_CREDS_FILE = os.path.expanduser('~/.dropbox_app_creds')

with open(REFRESH_TOKEN_FILE) as f:
    refresh_token = f.read().strip()
with open(APP_CREDS_FILE) as f:
    lines = [l.strip() for l in f if l.strip()]
    app_key, app_secret = lines[0], lines[1]

db = dropbox.Dropbox(
    oauth2_refresh_token=refresh_token,
    app_key=app_key,
    app_secret=app_secret,
)

result = db.files_list_folder('/ai-dj/files')
for entry in result.entries:
    if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith('.mp3'):
        print(f'{entry.path_lower}|{entry.name}|{entry.size}')
" 2>/dev/null | while IFS='|' read -r path name size; do
    echo "📥 $name ($((size/1024)) KB)"
    python3 scripts/dropbox-get.py \
        --path "$path" \
        --output "$AIDJ_DIR/$name" 2>/dev/null
    
    if [ $? -ne 0 ]; then
        echo "   ⚠️  Ошибка скачивания, пробую через shared link..."
        # fallback: получаем shared link и скачиваем через curl
        python3 -c "
import dropbox, os, sys, json
REFRESH_TOKEN_FILE = os.path.expanduser('~/.dropbox_refresh_token')
APP_CREDS_FILE = os.path.expanduser('~/.dropbox_app_creds')
with open(REFRESH_TOKEN_FILE) as f: refresh_token = f.read().strip()
with open(APP_CREDS_FILE) as f:
    lines = [l.strip() for l in f if l.strip()]
    app_key, app_secret = lines[0], lines[1]
db = dropbox.Dropbox(oauth2_refresh_token=refresh_token, app_key=app_key, app_secret=app_secret)
try:
    shared = db.sharing_create_shared_link_with_settings('$path')
    print(shared.url.replace('dl=0', 'dl=1'))
except:
    links = db.sharing_list_shared_links(path='$path').links
    if links:
        print(links[0].url.replace('dl=0', 'dl=1'))
    else:
        sys.exit(1)
" 2>/dev/null | xargs -I{} curl -sL "{}" -o "$AIDJ_DIR/$name"
    fi
done

echo ""
echo "✅ Треки скачаны в $AIDJ_DIR"
