#!/bin/bash
# Установка nginx reverse proxy с HTTPS (самоподписанный сертификат)
# Для AI DJ API + Photo Sync + Canvas — всё на одном порту 443

set -e

# 1. Создаём конфиг nginx
sudo tee /etc/nginx/sites-available/aidj > /dev/null << 'NGINXEOF'
server {
    listen 80;
    server_name 176.123.162.12;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name 176.123.162.12;

    ssl_certificate     /home/user1/.openclaw/workspace/ssl/cert.pem;
    ssl_certificate_key /home/user1/.openclaw/workspace/ssl/key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    add_header Access-Control-Allow-Origin * always;
    add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type" always;

    # Photo Sync (корень)
    location / {
        proxy_pass http://127.0.0.1:8767;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Canvas
    location /canvas/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # AI DJ API
    location /aidj/ {
        proxy_pass http://127.0.0.1:8766;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINXEOF

# 2. Активируем и отключаем дефолтный
sudo ln -sf /etc/nginx/sites-available/aidj /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 3. Проверяем конфиг
sudo nginx -t

# 4. Перезагружаем
sudo systemctl reload nginx

echo ""
echo "=== Готово ==="
echo "Photo Sync: https://176.123.162.12/"
echo "Canvas:     https://176.123.162.12/canvas/"
echo "AI DJ API:  https://176.123.162.12/aidj/"
echo "=== Проверка ==="
curl -sk -o /dev/null -w "AI DJ: %{http_code}\n" https://176.123.162.12/aidj/api/sets
echo "Браузер покажет предупреждение о сертификате — нажми «Продолжить»."
echo "После этого fetch() будет работать."
