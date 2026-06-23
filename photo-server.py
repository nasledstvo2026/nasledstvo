#!/usr/bin/env python3
"""
Photo Server — Flask-эндпоинт для кнопки «Обновить» на photo.html.
Слушает на localhost:8767.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

# Добавляем workspace в path для импорта photo_sync
_WS = str(Path.home() / '.openclaw' / 'workspace')
if _WS not in sys.path:
    sys.path.insert(0, _WS)

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # разрешаем запросы с GitHub Pages

# Состояние последнего запуска
last_result = None
is_running = False
last_run_time = None


RESULT_PAGE = '''<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Photo Sync</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0a0e14;
      color: #eaf0f6;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }
    .card {
      background: #161b22;
      border: 1px solid #21262d;
      border-radius: 16px;
      padding: 32px 40px;
      max-width: 480px;
      text-align: center;
    }
    h2 { margin: 0 0 12px; }
    p { color: #8892a0; margin: 8px 0; line-height: 1.5; }
    .success { color: #4ade80; }
    .error { color: #f87171; }
    .info { color: #60a5fa; }
    .btn {
      display: inline-block;
      margin-top: 16px;
      padding: 10px 24px;
      background: linear-gradient(135deg, #00d4ff, #a855f7);
      color: #fff;
      border: none;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
    }
    .btn:hover { opacity: 0.9; }
    .spinner {
      display: inline-block;
      width: 20px;
      height: 20px;
      border: 3px solid rgba(255,255,255,0.15);
      border-top-color: #00d4ff;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin-top: 12px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div class="card">
    <div class="spinner"></div>
    <h2>\u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0437\u0430\u043f\u0443\u0449\u0435\u043d\u0430</h2>
    <p>\u041f\u0440\u043e\u0432\u0435\u0440\u044f\u044e Dropbox \u0438 \u043a\u043e\u043d\u0432\u0435\u0440\u0442\u0438\u0440\u0443\u044e \u043d\u043e\u0432\u044b\u0435 \u0444\u0430\u0439\u043b\u044b...</p>
    <p class="info" id="msg">\u041f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435 \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u043e \u0441\u0435\u043a\u0443\u043d\u0434...</p>
    <button class="btn" onclick="window.close()" id="closeBtn" style="display:none">\u0417\u0430\u043a\u0440\u044b\u0442\u044c</button>
  </div>
  <script>
    let retries = 0;
    const maxRetries = 15;
    function poll() {
      fetch('/status')
        .then(r => r.json())
        .then(data => {
          if (!data.running && data.last_result) {
            const r = data.last_result;
            if (r.success) {
              const n = r.new || 0;
              if (n > 0) {
                document.querySelector('h2').textContent = '\\u2705 \u0414\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043e ' + n + ' \u0444\u043e\u0442\u043e';
                document.getElementById('msg').textContent = '\u041e\u0431\u043d\u043e\u0432\u0438 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443 \u0447\u0435\u0440\u0435\u0437 \u043c\u0438\u043d\u0443\u0442\u0443';
                document.getElementById('msg').className = 'success';
              } else {
                document.querySelector('h2').textContent = '\\u2705 \u041d\u043e\u0432\u044b\u0445 \u0444\u043e\u0442\u043e \u043d\u0435\u0442';
                document.getElementById('msg').textContent = '\u0412\u0441\u0435 \u0444\u0430\u0439\u043b\u044b \u0430\u043a\u0442\u0443\u0430\u043b\u044c\u043d\u044b';
                document.getElementById('msg').className = 'success';
              }
            } else {
              document.querySelector('h2').textContent = '\\u274c \u041e\u0448\u0438\u0431\u043a\u0430';
              document.getElementById('msg').textContent = r.error || '\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u0430\u044f \u043e\u0448\u0438\u0431\u043a\u0430';
              document.getElementById('msg').className = 'error';
            }
            document.querySelector('.spinner').style.display = 'none';
            document.getElementById('closeBtn').style.display = 'inline-block';
          } else if (retries < maxRetries) {
            retries++;
            document.getElementById('msg').textContent = '\\u23f3 \u041e\u0436\u0438\u0434\u0430\u043d\u0438\u0435... (' + retries + '/' + maxRetries + ')';
            setTimeout(poll, 2000);
          } else {
            document.querySelector('h2').textContent = '\\u23f3 \u0412\u0440\u0435\u043c\u044f \u0432\u044b\u0448\u043b\u043e';
            document.getElementById('msg').textContent = '\u041f\u0440\u043e\u0432\u0435\u0440\u044c \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443 \u0447\u0435\u0440\u0435\u0437 \u043f\u0430\u0440\u0443 \u043c\u0438\u043d\u0443\u0442';
            document.querySelector('.spinner').style.display = 'none';
            document.getElementById('closeBtn').style.display = 'inline-block';
          }
        })
        .catch(err => {
          if (retries < maxRetries) {
            retries++;
            setTimeout(poll, 2000);
          }
        });
    }
    setTimeout(poll, 2000);
  </script>
</body>
</html>
'''


def run_sync():
    """\u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044e \u0432 \u0444\u043e\u043d\u043e\u0432\u043e\u043c \u043f\u043e\u0442\u043e\u043a\u0435."""
    global last_result, is_running, last_run_time

    is_running = True
    try:
        from photo_sync import sync
        result = sync(new_only=True)
        last_result = result
    except Exception as e:
        last_result = {'success': False, 'error': str(e)}
    finally:
        is_running = False
        last_run_time = time.time()


@app.route('/sync', methods=['GET', 'POST'])
def trigger_sync():
    """\u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044e. \u0412\u043e\u0437\u0432\u0440\u0430\u0449\u0430\u0435\u0442 HTML-\u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443 \u0441 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u043e\u043c."""
    if is_running:
        return RESULT_PAGE.replace(
            '\u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0437\u0430\u043f\u0443\u0449\u0435\u043d\u0430',
            '\u0423\u0436\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u044f\u0435\u0442\u0441\u044f'
        ), 200, {'Content-Type': 'text/html; charset=utf-8'}

    t = threading.Thread(target=run_sync, daemon=True)
    t.start()

    return RESULT_PAGE, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/', methods=['GET'])
def index():
    """Корень — простая страница."""
    return '''<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Photo Sync API</title>
<style>body{font-family:sans-serif;background:#0a0e14;color:#eaf0f6;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}.card{background:#161b22;border:1px solid #21262d;border-radius:16px;padding:32px;text-align:center}h2{margin:0 0 8px;background:linear-gradient(135deg,#00d4ff,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}p{color:#8892a0;margin:4px 0}code{color:#00d4ff;font-size:13px}</style></head>
<body><div class="card">
<h2>Photo Sync Server</h2>
<p>POST <code>/sync</code> — запустить синхронизацию</p>
<p>GET <code>/status</code> — статус последнего запуска</p>
</div></body></html>
''', 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/status', methods=['GET'])
def get_status():
    """\u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0441\u0442\u0430\u0442\u0443\u0441."""
    global last_result, is_running, last_run_time

    return jsonify({
        'running': is_running,
        'last_run': last_run_time,
        'last_result': last_result,
        'timestamp': time.time()
    })


if __name__ == '__main__':
    port = int(os.environ.get('PHOTO_SERVER_PORT', 8767))
    print(f"📸 Photo Server listening on 0.0.0.0:{port}", file=sys.stderr)
    app.run(host='0.0.0.0', port=port, debug=False)
