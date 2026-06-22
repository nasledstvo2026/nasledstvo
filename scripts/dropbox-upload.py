#!/usr/bin/env python3
"""Загрузка файла в Dropbox (через refresh token)"""

import sys
import os
import json
import requests

DROPBOX_UPLOAD_API = "https://content.dropboxapi.com/2/files/upload"
DROPBOX_TOKEN_URL = "https://api.dropbox.com/oauth2/token"

REFRESH_TOKEN_FILE = os.path.expanduser("~/.dropbox_refresh_token")
APP_CREDS_FILE = os.path.expanduser("~/.dropbox_app_creds")


def get_access_token():
    with open(REFRESH_TOKEN_FILE) as f:
        refresh_token = f.read().strip()
    with open(APP_CREDS_FILE) as f:
        lines = [l.strip() for l in f if l.strip()]
        app_key, app_secret = lines[0], lines[1]
    
    r = requests.post(DROPBOX_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": app_key,
        "client_secret": app_secret,
    })
    r.raise_for_status()
    return r.json()["access_token"]


def upload_file(local_path, dropbox_path):
    access_token = get_access_token()
    
    with open(local_path, "rb") as f:
        data = f.read()
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/octet-stream",
        "Dropbox-API-Arg": json.dumps({
            "path": dropbox_path,
            "mode": "add",   # "add" or "overwrite"
            "autorename": True,
            "mute": False,
        }),
    }
    
    r = requests.post(DROPBOX_UPLOAD_API, headers=headers, data=data)
    r.raise_for_status()
    result = r.json()
    return result


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python3 dropbox-upload.py <local_file> </dropbox/path>")
        sys.exit(1)
    
    local_path = sys.argv[1]
    dropbox_path = sys.argv[2]
    
    if not os.path.exists(local_path):
        print(f"Ошибка: файл {local_path} не найден")
        sys.exit(1)
    
    size = os.path.getsize(local_path)
    print(f"Загружаю {local_path} ({size / 1024:.1f} KB) → {dropbox_path}...")
    
    result = upload_file(local_path, dropbox_path)
    print(f"✅ OK → {result.get('path_display', dropbox_path)}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
