#!/usr/bin/env python3
"""Минимальный тестовый сервер для проверки доступности VPS из корп. сети."""
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # разрешаем запросы с любых origins

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({
        "status": "ok",
        "message": "VPS доступен! Получен GET",
        "method": request.method
    })

@app.route('/ping', methods=['POST'])
def ping_post():
    data = request.get_json(silent=True) or {}
    return jsonify({
        "status": "ok",
        "message": "VPS доступен! Получен POST",
        "your_data": data
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8768, debug=False)
