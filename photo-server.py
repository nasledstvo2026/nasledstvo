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

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # разрешаем запросы с GitHub Pages

# Состояние последнего запуска
last_result = None
is_running = False
last_run_time = None


def run_sync():
    """Запустить синхронизацию в фоновом потоке."""
    global last_result, is_running, last_run_time

    is_running = True
    try:
        # Добавляем workspace в path
        workspace = str(Path.home() / '.openclaw' / 'workspace')
        if workspace not in sys.path:
            sys.path.insert(0, workspace)

        from photo_sync import sync
        result = sync(new_only=True)
        last_result = result
    except Exception as e:
        last_result = {'success': False, 'error': str(e)}
    finally:
        is_running = False
        last_run_time = time.time()


@app.route('/sync', methods=['POST'])
def trigger_sync():
    """Запустить синхронизацию."""
    global is_running

    if is_running:
        return jsonify({
            'success': False,
            'error': 'Уже выполняется',
            'status': 'running'
        }), 409

    # Запускаем в фоне
    t = threading.Thread(target=run_sync, daemon=True)
    t.start()

    return jsonify({
        'success': True,
        'status': 'started',
        'message': 'Синхронизация запущена'
    })


@app.route('/status', methods=['GET'])
def get_status():
    """Проверить статус и результат последнего запуска."""
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
