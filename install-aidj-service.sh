#!/bin/bash
# Install AI DJ Server as systemd service
# Run: sudo bash install-aidj-service.sh

SERVICE_NAME="aidj-server"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=== Установка AI DJ Server ==="

# Create service file
sudo tee "$SERVICE_FILE" > /dev/null << 'SERVICEEOF'
[Unit]
Description=AI DJ Server — Flask API for sets & mixing
After=network.target

[Service]
Type=simple
User=user1
WorkingDirectory=/home/user1/.openclaw/workspace
ExecStart=/usr/bin/python3 /home/user1/.openclaw/workspace/aidj/aidj-server.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF

echo "✓ Файл создан: $SERVICE_FILE"

# Enable & start
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# Kill old manual process (PID from Jun 22)
sudo kill 740015 2>/dev/null || echo "  (manual process не найден)"
sleep 1

sudo systemctl start "$SERVICE_NAME"

# Verify
sleep 2
if curl -s -m5 http://176.123.162.12:8766/api/sets > /dev/null 2>&1; then
    echo "✓ Сервер запущен и отвечает"
    sudo systemctl status "$SERVICE_NAME" --no-pager | head -10
else
    echo "✗ Сервер не отвечает. Проверь: sudo journalctl -u $SERVICE_NAME -n 30"
fi
