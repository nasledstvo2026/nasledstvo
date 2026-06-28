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
NGINX_BASE = os.environ.get('NGINX_BASE', 'https://modify-builders-meals-phd.trycloudflare.com')

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
#   Локальный список треков (tracks.json)
# ══════════════════════════════════════════

TRACKS_FILE = BASE_DIR / 'tracks.json'


def read_tracks_json():
    """Читает tracks.json с локальной ФС."""
    if TRACKS_FILE.exists():
        try:
            return json.loads(TRACKS_FILE.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"[WARN] tracks.json parse failed: {e}", file=sys.stderr)
    return []


# ─── GET /tracks.json — список треков ───
@app.route('/tracks.json', methods=['GET'])
def api_tracks_json():
    return jsonify(read_tracks_json())


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

    def run_mix(sid, tracks, preset_id='default'):
        mixing_jobs[sid] = {'status': 'processing', 'eta': '~30 сек', 'started': moscow_now().isoformat()}
        try:
            if preset_id == 'oakenfold':
                preset_id = 'oakenfold_1998'

            engine = BASE_DIR / 'aidj-engine.py'
            if engine.exists():
                config_json = json.dumps({'id': sid, 'tracks': tracks, 'preset': {'preset': preset_id}})
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

    body = request.get_json(silent=True) or {}
    preset_id = body.get('preset', 'default')
    thread = threading.Thread(target=run_mix, args=(set_id, data.get('tracks', []), preset_id), daemon=True)
    thread.start()

    return jsonify({'status': 'processing', 'eta': '~30 сек'}), 202

# ─── POST /api/mix — свести треки напрямую (без сета) ───
@app.route('/api/mix', methods=['POST'])
def api_mix_tracks():
    data = request.get_json(silent=True) or {}
    tracks = data.get('tracks', [])
    if not tracks:
        return jsonify({'error': 'No tracks provided'}), 400

    mix_id = 'mix_' + uuid.uuid4().hex[:8]

    def lookup_track_path(track):
        """Convert track URL/name to local file path"""
        from urllib.parse import unquote, urlparse

        url = track.get('url', '')
        name = track.get('title', '')
        artist = track.get('artist', '')

        # Priority 1: If url contains trycloudflare, extract filename and decode
        if 'trycloudflare.com' in url:
            fname = os.path.basename(url.split('?')[0])
            fname = unquote(fname)
            print(f'[RESOLVE] Cloudflare URL -> {repr(fname)}', file=sys.stderr, flush=True)
            local = BASE_DIR / fname
            if local.exists():
                print(f'[RESOLVE] Found: {local}', file=sys.stderr, flush=True)
                return str(local)
            # Try without base_dir
            if Path(fname).exists():
                return str(Path(fname).resolve())

        # Priority 2: Extract filename from URL (handles absolute http:// URLs)
        if url:
            # URL-decode and get just the filename component
            parsed = urlparse(url)
            fname = os.path.basename(unquote(parsed.path))
            if fname:
                local = BASE_DIR / fname
                if local.exists():
                    print(f'[RESOLVE] URL filename -> {local}', file=sys.stderr, flush=True)
                    return str(local)

        # Priority 3: Search by filename match in BASEDIR
        for f in sorted(BASE_DIR.iterdir()):
            if f.suffix.lower() in ('.mp3', '.wav', '.flac', '.ogg', '.m4a'):
                fstem = str(f.stem).lower()
                nlow = name.lower()
                alow = artist.lower()
                if (nlow and nlow in fstem) or (alow and alow in fstem):
                    return str(f)

        print(f'[RESOLVE] NOT FOUND: url={url} name={name} artist={artist}', file=sys.stderr, flush=True)
        return url

    def run_direct(mid, tlist):
        mixing_jobs[mid] = {'status': 'processing', 'eta': '~30 сек', 'started': moscow_now().isoformat()}
        try:
            # Resolve local paths for tracks
            for t in tlist:
                t['filepath'] = lookup_track_path(t)

            # Resolve preset
            preset_id = data.get('preset', 'default')
            if preset_id == 'oakenfold':
                preset_id = 'oakenfold_1998'  # backward compat

            engine = BASE_DIR / 'aidj-engine.py'
            if engine.exists():
                config_json = json.dumps({'id': mid, 'tracks': tlist, 'preset': {'preset': preset_id}})
                engine_result = subprocess.run(
                    [sys.executable, str(engine), '--config', config_json],
                    capture_output=True, text=True, timeout=180
                )
                if engine_result.returncode == 0:
                    try:
                        engine_data = json.loads(engine_result.stdout.strip())
                        final_output = engine_data.get('output', '')
                        fname = os.path.basename(final_output)
                        nginx_base = NGINX_BASE.rstrip('/')
                        mix_url = f'{nginx_base}/static/{fname}'
                        mixing_jobs[mid] = {
                            'status': 'done',
                            'output': engine_data,
                            'url': mix_url,
                            'filename': fname,
                            'completed': moscow_now().isoformat()
                        }
                    except (json.JSONDecodeError, KeyError) as e:
                        mixing_jobs[mid] = {'status': 'error', 'error': f'Engine parse: {e}'}
                else:
                    mixing_jobs[mid] = {'status': 'error', 'error': engine_result.stderr.strip()[:500]}
            else:
                time.sleep(3)
                mixing_jobs[mid] = {'status': 'done', 'output': f'mix-{mid}.mp3', 'completed': moscow_now().isoformat(), 'stub': True}
        except Exception as e:
            mixing_jobs[mid] = {'status': 'error', 'error': str(e)}

    thread = threading.Thread(target=run_direct, args=(mix_id, tracks), daemon=True, name=f'mix-{mix_id}')
    thread.start()

    return jsonify({'status': 'processing', 'mix_id': mix_id, 'eta': '~30 сек'}), 202


# ─── GET /api/mix/<mix_id>/status — статус прямого сведения ───
@app.route('/api/mix/<mix_id>/status', methods=['GET'])
def api_mix_status(mix_id):
    job = mixing_jobs.get(mix_id, {})
    if not job:
        return jsonify({'status': 'idle'})
    return jsonify(job)


# ─── GET /api/sets/<set_id>/status — статус сведения ───
@app.route('/api/sets/<set_id>/status', methods=['GET'])
def api_status_set(set_id):
    job = mixing_jobs.get(set_id, {})
    if not job:
        return jsonify({'status': 'idle'})
    return jsonify(job)

# ─── GET /static/<path> — раздача миксов ───
@app.route('/aidj/static/<path:filename>')
@app.route('/static/<path:filename>')
def serve_mix(filename):
    return send_from_directory(str(STATIC_DIR), filename)


# ─── GET /aidj/<mp3> — раздача треков ───
@app.route('/aidj/<path:filename>')
@app.route('/<path:filename>')
def serve_audio(filename):
    return send_from_directory(str(BASE_DIR), filename)


# ─── GET /djset.html — страница DJ Set ───
@app.route('/djset.html', methods=['GET'])
def serve_djset_page():
    return send_from_directory(str(BASE_DIR), 'djset.html')


# ─── DELETE /api/tracks/delete — удалить треки ───
@app.route('/api/tracks/delete', methods=['POST'])
def api_delete_tracks():
    body = request.get_json(silent=True) or {}
    urls = body.get('urls', [])
    if not urls or not isinstance(urls, list):
        return jsonify({'ok': False, 'error': 'Нет URL для удаления'}), 400

    tracks = read_tracks_json()
    removed = 0
    errors = []
    new_tracks = []
    for t in tracks:
        if t.get('url') in urls:
            # Extract filename from full URL (or use relative path)
            raw_url = t.get('url', '')
            filename = raw_url.rstrip('/').split('/')[-1]
            filepath = BASE_DIR / filename
            if filepath.exists():
                try:
                    filepath.unlink()
                    removed += 1
                except Exception as e:
                    errors.append(f"{t.get('title')}: {e}")
            else:
                removed += 1  # file already gone, just remove from index
        else:
            new_tracks.append(t)

    # Write back tracks.json
    TRACKS_FILE.write_text(
        json.dumps(new_tracks, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8'
    )

    msg = f'Удалено {removed} треков из каталога'
    if errors:
        msg += f'. Ошибки: {"; ".join(errors)}'

    # Push to GitHub in background thread (don't block the response)
    def bg_push():
        try:
            import subprocess as sp
            wk = str(BASE_DIR.parent)
            sp.run(['git', '-C', wk, 'add', 'aidj/tracks.json'], capture_output=True, timeout=10)
            sp.run(['git', '-C', wk, 'commit', '-m', 'aidj: delete tracks via web'], capture_output=True, timeout=10)
            sp.run(['git', '-C', wk, 'push'], capture_output=True, timeout=30)
        except Exception as e:
            print(f'[WARN] Git push failed: {e}', file=sys.stderr)

    import threading
    threading.Thread(target=bg_push, daemon=True).start()

    return jsonify({'ok': True, 'removed': removed, 'errors': errors, 'message': msg, 'remaining': len(new_tracks)})


# ─── GET / → redirect to djset.html ───
@app.route('/', methods=['GET'])
def serve_root():
    return send_from_directory(str(BASE_DIR), 'djset.html')

# ─── GET /delete → страница удаления треков (same-origin) ───
@app.route('/delete', methods=['GET'])
def serve_delete_page():
    return send_from_directory(str(BASE_DIR.parent), 'aidj-delete.html')


# ══════════════════════════════════════════
#   Client-side log endpoint
# ══════════════════════════════════════════

@app.route('/api/log', methods=['POST'])
def api_client_log():
    body = request.get_json(silent=True) or {}
    event = body.get('event', 'unknown')
    details = body.get('details', {})
    user_agent = body.get('userAgent', 'unknown')
    timestamp = body.get('timestamp', datetime.now(timezone.utc).isoformat())
    screen = body.get('screen', 'unknown')

    log_line = (
        f"[CLIENT-LOG] {timestamp}"
        f" | event={event}"
        f" | details={json.dumps(details, ensure_ascii=False)}"
        f" | screen={screen}"
        f" | ua={user_agent[:100]}"
    )
    print(log_line, file=sys.stderr, flush=True)

    return jsonify({'ok': True})


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
    app.run(host='127.0.0.1', port=p, ssl_context=ssl_ctx, debug=False)
