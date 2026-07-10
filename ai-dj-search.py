#!/usr/bin/env python3
"""AI DJ — поиск и скачивание треков через Яндекс.Музыку"""

import sys
import json
import os
from yandex_music import Client

TOKEN = "y0__wgBEPPn3YsEGN74BiDwh9eCGL_6nXwTFWHkstdqAq7ZL6Og6y71"
DOWNLOAD_DIR = "/home/user1/.openclaw/workspace/aidj"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

client = Client(TOKEN).init()


def search_tracks(query, limit=10):
    """Ищет треки по названию"""
    result = client.search(query)
    if not result or not result.tracks:
        return []
    
    tracks = result.tracks.results
    items = []
    for i, t in enumerate(tracks[:limit]):
        items.append({
            'num': i + 1,
            'id': t.id,
            'title': t.title,
            'artists': ', '.join(a.name for a in t.artists),
            'album': t.albums[0].title if t.albums else '',
            'duration': f"{t.duration_ms // 60000}:{t.duration_ms % 60000 // 1000:02d}",
        })
    return items


def download_track(track_id, filename=None):
    """Скачивает трек по ID, сохраняет в aidj/ с именем Артист - Название.mp3"""
    track = client.tracks(track_id)[0]
    artists = ', '.join(a.name for a in track.artists)
    title = track.title
    
    if not filename:
        safe_artists = "".join(c for c in artists if c.isalnum() or c in ' -_')
        safe_title = "".join(c for c in title if c.isalnum() or c in ' -_')
        filename = f"{safe_artists} - {safe_title}.mp3"
    elif not filename.endswith('.mp3'):
        filename += '.mp3'
    
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    
    # Если файл уже существует — не перекачиваем
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        if size > 0:
            return filepath, size
    
    track.download(filepath)
    
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return filepath, os.path.getsize(filepath)
    return None, 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python3 ai-dj-search.py search <название>")
        print("  python3 ai-dj-search.py download <track_id> [filename]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "search":
        query = " ".join(sys.argv[2:])
        tracks = search_tracks(query)
        print()
        if not tracks:
            print(json.dumps({"error": "Ничего не найдено"}, ensure_ascii=False))
        else:
            print(json.dumps({"found": len(tracks), "tracks": tracks},
                             ensure_ascii=False, indent=2))
    
    elif action == "download":
        track_id = sys.argv[2]
        filename = sys.argv[3] if len(sys.argv) > 3 else None
        print(f"Скачиваю трек {track_id}...")
        filepath, size = download_track(track_id, filename)
        if filepath:
            print(json.dumps({
                "ok": True,
                "filepath": filepath,
                "size_kb": round(size / 1024, 1)
            }, ensure_ascii=False, indent=2))
        else:
            print(json.dumps({"error": "Не удалось скачать трек"}, ensure_ascii=False))
