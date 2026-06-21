#!/usr/bin/env python3
"""Скачать файл из Dropbox.

Usage:
  # По пути в Dropbox (с refresh token — рекомендуется)
  python3 dropbox-get.py --path "/Dropbox/folder/file.ext" --output ./file.ext

  # С явным access token
  python3 dropbox-get.py --token TOKEN --path "/folder/file.ext" --output ./file.ext

  # По расшаренной ссылке (токен не нужен)
  python3 dropbox-get.py --shared-link "https://www.dropbox.com/s/xxxx/file.ext?dl=0" --output ./file.ext

Конфиги:
  ~/.dropbox_app_creds — 2 строки: app_key, app_secret
  ~/.dropbox_refresh_token — refresh token (бессрочный)
"""
import argparse
import os
import re
import requests
import sys


def _get_db_instance(token=None):
    import dropbox

    if token:
        return dropbox.Dropbox(token)

    # Пробуем refresh token
    refresh_token_file = os.path.expanduser("~/.dropbox_refresh_token")
    creds_file = os.path.expanduser("~/.dropbox_app_creds")

    if os.path.exists(refresh_token_file) and os.path.exists(creds_file):
        with open(creds_file) as f:
            lines = [l.strip() for l in f if l.strip()]
            app_key, app_secret = lines[0], lines[1]
        with open(refresh_token_file) as f:
            refresh_token = f.read().strip()

        from dropbox import Dropbox
        from dropbox.oauth import DropboxOAuth2FlowNoRedirect

        # Используем refresh token напрямую
        dbx = dropbox.Dropbox(
            oauth2_access_token=None,
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret,
        )
        return dbx

    raise ValueError("Нет ни --token, ни конфигов (~/.dropbox_refresh_token + ~/.dropbox_app_creds)")


def download_via_api(remote_path, output_path, token=None):
    import dropbox

    dbx = _get_db_instance(token)

    if not remote_path.startswith("/"):
        remote_path = "/" + remote_path

    print(f"📥 Скачиваю {remote_path}...", file=sys.stderr)
    try:
        metadata, response = dbx.files_download(remote_path)
    except dropbox.exceptions.ApiError as e:
        print(f"❌ Ошибка API: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(response.content)

    size_kb = len(response.content) / 1024
    print(f"✅ {output_path} ({size_kb:.1f} KB)", file=sys.stderr)


def download_via_shared_link(shared_link, output_path):
    url = shared_link.strip()

    if "dl=0" in url:
        url = url.replace("dl=0", "dl=1")
    elif "?" in url:
        url += "&dl=1"
    else:
        url += "?dl=1"

    print(f"📥 Качаю по ссылке...", file=sys.stderr)
    r = requests.get(url, stream=True, allow_redirects=True, timeout=60)
    if r.status_code != 200:
        raw_url = re.sub(
            r"https://www\.dropbox\.com/s/([^/?]+)",
            r"https://dl.dropboxusercontent.com/s/\1",
            shared_link
        )
        print(f"⚠️ fallback на {raw_url}", file=sys.stderr)
        r = requests.get(raw_url, stream=True, allow_redirects=True, timeout=60)

    if r.status_code != 200:
        print(f"❌ HTTP {r.status_code}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"✅ {output_path} ({size_kb:.1f} KB)", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description="Скачать файл из Dropbox")
    ap.add_argument("--token", help="Access token (если не используешь refresh)")
    ap.add_argument("--path", help="Путь к файлу в Dropbox, напр. /folder/file.ext")
    ap.add_argument("--shared-link", help="Расшаренная ссылка Dropbox")
    ap.add_argument("--output", "-o", required=True, help="Куда сохранить локально")
    args = ap.parse_args()

    if args.shared_link:
        download_via_shared_link(args.shared_link, args.output)
    elif args.path:
        download_via_api(args.path, args.output, token=args.token)
    else:
        print("❌ Укажи --path или --shared-link", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
