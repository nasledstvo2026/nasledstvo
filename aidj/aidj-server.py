#!/usr/bin/env python3
"""
AI DJ — API Server
Handles CRUD for DJ Sets and triggers audio mixing.
Run: python3 aidj-server.py
Port: 8766
"""

import json
import os
import sys
import uuid
import subprocess
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ─── Paths ───
BASE_DIR = Path(__file__).resolve().parent
SETS_DIR = BASE_DIR / 'sets'
STATIC_DIR = BASE_DIR / 'static'
SETS_INDEX = SETS_DIR / 'sets-index.json'

# ─── Network ───
HOST = '176.123.162.12'
PORT = 8766
NGINX_BASE = os.environ.get('NGINX_BASE', 'https://176.123.162.12/aidj')

# Moscow TZ
MOSCOW_OFFSET = timedelta(hours=3)

def moscow_now():
    return datetime.now(timezone.utc) + MOSCOW_OFFSET

# ─── Ensure directories ───
SETS_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)
if not SETS_INDEX.exists():
    SETS_INDEX.write_text('[]', encoding='utf-8')

# ─── App ───
app = Flask(__name__)
CORS(app)

# active mixing jobs
mixing_jobs = {}


# ══════════════════════════════════════════
#   Dropbox треки
# ══════════════════════════════════════════

def get_dropbox_tracks():
    """
    Получает список mp3 из Dropbox /ai-dj/files/
    Возвращает список dict: {title, artist, dropbox_path, duration, bpm}
    """
    try:
        sys.path.insert(0, str(BASE_DIR.parent / 'scripts'))
        from dropbox_utils import list_files
        files = list_files('/ai-dj/files/')
        tracks = []
        for f in files:
            name = f.get('name', '')
            if not name.lower().endswith('.mp3'):
                continue
            # Парсим название: "Artist — Title.mp3" или "Title.mp3"
            stem = name.rsplit('.', 1)[0]
            if ' — ' in stem:
                artist, title = stem.split(' — ', 1)
            elif ' - ' in stem:
                artist, title = stem.split(' - ', 1)
            else:
                artist = 'Unknown'
                title = stem
            tracks.append({
                'title': title.strip(),
                'artist': artist.strip(),
                'dropbox_path': f['path_display'] if 'path_display' in f else f'/ai-dj/files/{name}',
                'duration': None,
                'bpm': None,
            })
        return tracks
    except Exception as e:
        print(f"[WARN] Dropbox list failed: {e}", file=sys.stderr)
        return []


# ══════════════════════════════════════════
#   Sets CRUD
# ══════════════════════════════════════════

def load_index():
    try:
        return json.loads(SETS_INDEX.read_text(encoding='utf-8'))
    except Exception:
        return []

def save_index(index):
    SETS_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')

def load_set(set_id):
    path = SETS_DIR / f'set-{set_id}.json'
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding='utf-8'))

def generate_set_id():
    return moscow_now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:4]


# ─── GET /api/sets — список сетов ───
@app.route('/api/sets', methods=['GET'])
def api_list_sets():
    index = load_index()
    return jsonify(index)

# ─── GET /api/sets/tracklist — треки из Dropbox ───
@app.route('/api/sets/tracklist', methods=['GET'])
def api_tracklist():
    tracks = get_dropbox_tracks()
    return jsonify(tracks)

# ─── GET /api/sets/<set_id> — детали сета ───
@app.route('/api/sets/<set_id>', methods=['GET'])
def api_get_set(set_id):
    data = load_set(set_id)
    if data is None:
        return jsonify({'error': 'Set not found'}), 404
    return jsonify(data)

# ─── POST /api/sets/create — создать сет ───
@app.route('/api/sets/create', methods=['POST'])
def api_create_set():
    body = request.get_json()
    if not body:
        return jsonify({'error': 'Empty body'}), 400
    name = body.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    tracks = body.get('tracks', [])
    if len(tracks) < 2:
        return jsonify({'error': 'At least 2 tracks required'}), 400

    set_id = generate_set_id()
    now = moscow_now().isoformat()
    data = {
        'id': set_id,
        'name': name,
        'created': now,
        'updated': now,
        'tracks': tracks,
    }
    # Write file
    path = SETS_DIR / f'set-{set_id}.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    # Update index
    index = load_index()
    index.append({
        'id': set_id,
        'name': name,
        'track_count': len(tracks),
        'created': now,
        'updated': now,
    })
    save_index(index)

    return jsonify({'ok': True, 'id': set_id}), 201

# ─── PUT /api/sets/<set_id>/update — обновить сет ───
@app.route('/api/sets/<set_id>/update', methods=['PUT'])
def api_update_set(set_id):
    body = request.get_json()
    if not body:
        return jsonify({'error': 'Empty body'}), 400

    existing = load_set(set_id)
    if existing is None:
        return jsonify({'error': 'Set not found'}), 404

    name = body.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    tracks = body.get('tracks', [])
    if len(tracks) < 2:
        return jsonify({'error': 'At least 2 tracks required'}), 400

    now = moscow_now().isoformat()
    data = {
        'id': set_id,
        'name': name,
        'created': existing.get('created', now),
        'updated': now,
        'tracks': tracks,
    }
    path = SETS_DIR / f'set-{set_id}.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    # Update index
    index = load_index()
    for entry in index:
        if entry['id'] == set_id:
            entry['name'] = name
            entry['track_count'] = len(tracks)
            entry['updated'] = now
            break
    save_index(index)

    return jsonify({'ok': True, 'id': set_id})

# ─── DELETE /api/sets/<set_id>/delete — удалить сет ───
@app.route('/api/sets/<set_id>/delete', methods=['DELETE'])
def api_delete_set(set_id):
    path = SETS_DIR / f'set-{set_id}.json'
    if path.exists():
        path.unlink()

    index = load_index()
    index = [e for e in index if e['id'] != set_id]
    save_index(index)

    return jsonify({'ok': True})

# ─── POST /api/sets/<set_id>/play — запустить сведение ───
@app.route('/api/sets/<set_id>/play', methods=['POST'])
def api_play_set(set_id):
    data = load_set(set_id)
    if data is None:
        return jsonify({'error': 'Set not found'}), 404

    if set_id in mixing_jobs and mixing_jobs[set_id]['status'] in ('processing', 'downloading'):
        return jsonify({'status': 'already_processing', 'eta': mixing_jobs[set_id].get('eta', '~30 сек')})

    def run_mix(sid, tracks):
        mixing_jobs[sid] = {'status': 'processing', 'eta': '~30 сек', 'started': moscow_now().isoformat()}
        try:
            engine = BASE_DIR / 'aidj-engine.py'
            if engine.exists():
                config_json = json.dumps({'id': sid, 'tracks': tracks})
                engine_result = subprocess.run(
                    [sys.executable, str(engine), '--config', config_json],
                    capture_output=True, text=True, timeout=180
                )
                if engine_result.returncode == 0:
                    try:
                        engine_data = json.loads(engine_result.stdout.strip())
                        final_output = engine_data.get('output', '')
                        # Extract filename for URL
                        fname = os.path.basename(final_output)
                        nginx_base = NGINX_BASE.rstrip('/')
                        mix_url = f'{nginx_base}/static/{fname}'
                        mixing_jobs[sid] = {
                            'status': 'done',
                            'output': engine_data,
                            'url': mix_url,
                            'filename': fname,
                            'completed': moscow_now().isoformat()
                        }
                    except (json.JSONDecodeError, KeyError) as e:
                        mixing_jobs[sid] = {'status': 'error', 'error': f'Engine parse: {e}'}
                else:
                    mixing_jobs[sid] = {'status': 'error', 'error': engine_result.stderr.strip()[:500]}
            else:
                # Engine not ready — stub
                time.sleep(3)
                mixing_jobs[sid] = {
                    'status': 'done',
                    'output': f'mix-{sid}.mp3',
                    'completed': moscow_now().isoformat(),
                    'stub': True
                }
        except Exception as e:
            mixing_jobs[sid] = {'status': 'error', 'error': str(e)}

    thread = threading.Thread(target=run_mix, args=(set_id, data.get('tracks', [])), daemon=True)
    thread.start()

    return jsonify({'status': 'processing', 'eta': '~30 сек'}), 202

# ─── GET /api/sets/<set_id>/status — статус сведения ───
@app.route('/api/sets/<set_id>/status', methods=['GET'])
def api_status_set(set_id):
    job = mixing_jobs.get(set_id, {})
    if not job:
        return jsonify({'status': 'idle'})
    return jsonify(job)

# ─── GET /aidj/static/<path> — раздача миксов ───
@app.route('/aidj/static/<path:filename>')
def serve_mix(filename):
    return send_from_directory(str(STATIC_DIR), filename)


# ══════════════════════════════════════════
#   Main
# ══════════════════════════════════════════

if __name__ == '__main__':
    import ssl
    p = int(os.environ.get('PORT', PORT))
    use_https = os.environ.get('USE_HTTPS', '').lower() in ('true', '1', 'yes')

    ssl_ctx = None
    scheme = 'http'
    if use_https:
        ssl_dir = BASE_DIR.parent / 'ssl'
        cert = ssl_dir / 'cert.pem'
        key = ssl_dir / 'key.pem'
        if cert.exists() and key.exists():
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(str(cert), str(key))
            scheme = 'https'
            print(f"[AI DJ Server] SSL enabled: {cert}")

    print(f"[AI DJ Server] Starting on {scheme}://{HOST}:{p}")
    print(f"[AI DJ Server] Sets dir: {SETS_DIR}")
    print(f"[AI DJ Server] Static dir: {STATIC_DIR}")
    app.run(host='0.0.0.0', port=p, ssl_context=ssl_ctx, debug=False)
