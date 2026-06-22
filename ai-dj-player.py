#!/usr/bin/env python3
"""AI DJ Player — генерирует страницу с плеером для треков из Dropbox"""

import os
import dropbox

DROPBOX_FOLDER = "/ai-dj/files"
OUTPUT_FILE = "/home/user1/.openclaw/workspace/aidj-player.html"

REFRESH_TOKEN_FILE = os.path.expanduser("~/.dropbox_refresh_token")
APP_CREDS_FILE = os.path.expanduser("~/.dropbox_app_creds")


def get_db():
    with open(REFRESH_TOKEN_FILE) as f:
        refresh_token = f.read().strip()
    with open(APP_CREDS_FILE) as f:
        lines = [l.strip() for l in f if l.strip()]
        app_key, app_secret = lines[0], lines[1]
    return dropbox.Dropbox(
        oauth2_refresh_token=refresh_token,
        app_key=app_key,
        app_secret=app_secret,
    )


def list_files(db):
    """Получает список mp3-файлов в /ai-dj/files/"""
    try:
        result = db.files_list_folder(DROPBOX_FOLDER)
    except dropbox.exceptions.ApiError:
        return []
    files = [e for e in result.entries
             if isinstance(e, dropbox.files.FileMetadata)
             and e.name.lower().endswith(".mp3")]
    return sorted(files, key=lambda f: f.name.lower())


def get_temp_link(db, path):
    """Получает временную прямую ссылку на файл (живёт ~4ч)"""
    link = db.files_get_temporary_link(path)
    return link.link


def generate_player_html(tracks):
    now = os.popen("TZ=Europe/Moscow date '+%d.%m.%Y %H:%M'").read().strip()
    
    tracks_html = ""
    for i, t in enumerate(tracks):
        display_name = t["name"].replace(".mp3", "")
        size_kb = round(t["size"] / 1024, 1)
        
        tracks_html += f"""
    <div class="track">
      <div class="track-info">
        <span class="track-num">{i+1}</span>
        <div class="track-name">{display_name}</div>
        <span class="track-size">{size_kb} KB</span>
      </div>
      <audio class="track-player" controls preload="none">
        <source src="{t['url']}" type="audio/mpeg">
      </audio>
    </div>
"""
    
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI DJ — плеер</title>
  <link rel="stylesheet" href="theme.css">
  <style>
    .player-list {{ margin-top: 16px; }}
    .track {{
      background: rgba(22,27,34,0.8);
      border: 1px solid #21262d;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .track-info {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex: 1;
      min-width: 200px;
    }}
    .track-num {{
      background: rgba(88,166,255,0.15);
      color: #58a6ff;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 0.85em;
      font-weight: 700;
      flex-shrink: 0;
    }}
    .track-name {{
      color: #f0f6fc;
      font-size: 0.95em;
      font-weight: 500;
      word-break: break-word;
    }}
    .track-size {{
      color: #8b949e;
      font-size: 0.8em;
      white-space: nowrap;
    }}
    .track-player {{
      flex-shrink: 0;
      width: 100%;
      max-width: 400px;
    }}
    .empty {{
      text-align: center;
      padding: 48px 24px;
      color: #8b949e;
    }}
    .empty-icon {{ font-size: 48px; margin-bottom: 16px; }}
    .count-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      color: #8b949e;
      font-size: 0.9em;
    }}
    .count {{ color: #58a6ff; font-weight: 600; }}
    .refresh-note {{
      color: #484f58;
      font-size: 0.8em;
      margin-top: 8px;
      text-align: right;
    }}
  </style>
</head>
<body>
<div class="container">

  <a class="back" href="aidj.html">← AI DJ</a>

  <div class="hero">
    <div class="title">🎵 Плеер</div>
    <div class="meta">Треки из Dropbox · Обновлено {now}</div>
  </div>

  <div class="section">
    <div class="count-bar">
      <span>Всего треков: <span class="count">{len(tracks)}</span></span>
    </div>

    <div class="player-list">
      {tracks_html if tracks_html else '<div class="empty"><div class="empty-icon">📂</div><p>В Dropbox пока нет треков.<br>Загрузите через AI DJ в /ai-dj/files/</p></div>'}
    </div>

    <div class="refresh-note">Ссылки обновляются раз в 4 часа. Если трек не играет — попроси Лунта обновить страницу.</div>
  </div>

  <div class="footer">
    <p>nasledstvo2026.github.io — AI DJ Player · 2026</p>
  </div>

</div>
</body>
</html>
"""
    return html


def main():
    print("AI DJ Player — генерация страницы")
    print(f"Папка: {DROPBOX_FOLDER}")
    print()
    
    db = get_db()
    print("✅ Dropbox авторизован")
    
    files = list_files(db)
    print(f"Найдено mp3: {len(files)}")
    
    tracks = []
    for f in files:
        print(f"  📄 {f.name} ({f.size / 1024:.1f} KB)", end=" ")
        link = get_temp_link(db, f.path_lower)
        print("→ ссылка получена")
        tracks.append({"name": f.name, "url": link, "size": f.size})
    
    print()
    html = generate_player_html(tracks)
    
    with open(OUTPUT_FILE, "w") as f:
        f.write(html)
    print(f"✅ Страница: {OUTPUT_FILE}")
    
    # Публикация
    os.chdir(os.path.dirname(OUTPUT_FILE))
    os.system("git add -A && git commit -m 'AI DJ Player — страница с плеером' 2>/dev/null")
    os.system("git push 2>&1")
    print("✅ Опубликовано на GitHub Pages")


if __name__ == "__main__":
    main()
