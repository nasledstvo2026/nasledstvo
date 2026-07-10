# План отката: Named Tunnel для AI DJ API

## Если named tunnel не заработал

### Шаг 1 — Восстановить quick tunnel
```bash
# Остановить named tunnel (если запущен)
sudo systemctl stop cloudflared-aidj-named

# Восстановить оригинальный quick tunnel сервис
sudo cp /etc/systemd/system/cloudflared-aidj.service.bak /etc/systemd/system/cloudflared-aidj.service
sudo systemctl daemon-reload
sudo systemctl restart cloudflared-aidj
```

### Шаг 2 — Получить новый quick tunnel URL
```bash
sudo journalctl -u cloudflared-aidj --no-pager 2>&1 | grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1
```

### Шаг 3 — Вернуть VPS_BASE в djset.html на новый URL туннеля
Отредактировать `aidj/djset.html`:
```js
const VPS_BASE = 'https://НОВЫЙ-URL.trycloudflare.com';
```

### Шаг 4 — Опубликовать
```bash
cd /home/user1/.openclaw/workspace
git add aidj/djset.html
git commit -m "aidj/djset: rollback to quick tunnel"
git push
```

## Время восстановления: ~2 минуты
