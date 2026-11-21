# Инфраструктура

## Инфраструктура

### GitHub Pages
- Репозиторий: `nasledstvo2026/nasledstvo`
- Ветка для пуша: `master` (workflow деплоит из master → gh-pages)
- ⚠️ НИКОГДА не пушить напрямую в `gh-pages` — воркфлоу не запустится, страница не обновится
- Workflow: `.github/workflows/deploy-pages.yml`, триггер: `push → master`
- Процесс: `git add` → `git commit` → `git push origin master` → ждать деплой (~30 сек)
- Проверка: `curl -s https://nasledstvo2026.github.io/nasledstvo/ | grep -c 'ключевое_слово'`
- Домен: `https://nasledstvo2026.github.io/nasledstvo/`
- Remote: `origin` (git@github.com:nasledstvo2026/nasledstvo.git)

### Web GUI (Control UI) — доступ
- **Приватно (штатный способ):** `https://vm-f13581.tail31d188.ts.net` — `tailscale serve` → 127.0.0.1:18789, доступно только внутри tailnet. В конфиге gateway `auth.allowTailscale: true`
- Токен (если страница запросит): в `gateway.auth.token` файла `~/.openclaw/openclaw.json`; альтернатива — `openclaw dashboard --no-open`
- Проверка: `curl -sI https://vm-f13581.tail31d188.ts.net/` → 200
- ⚠️ `trycloudflare.com` у Кирилла не открывается без VPN (запись 28.06) — публичные quick-туннели как канал не работают
- **`cloudflared-dashboard.service` — погашен 10.09.2026** (stop + disable + mask). Unit сохранён: `/etc/systemd/system/cloudflared-dashboard.service.disabled`
- Вернуть туннель (если понадобится): `sudo rm /etc/systemd/system/cloudflared-dashboard.service` (снять symlink на /dev/null) → `sudo mv /etc/systemd/system/cloudflared-dashboard.service.disabled /etc/systemd/system/cloudflared-dashboard.service` → `sudo systemctl daemon-reload && sudo systemctl enable --now cloudflared-dashboard.service`

### VPS (Лунт)
- Хост: vm-low4-8
- ОС: Linux 6.8.0-136-generic (x64)
- Node: v22.23.1
- Gateway: OpenClaw

### VPS Феникс (соседний OpenClaw)
- IP: `213.171.25.85` | пользователь: `user1` | hostname: `vm-low4-8` (НЕ vm-f13581)
- Ключ: `~/.ssh/fenix` (права 600) — идентичен `new-vps-key`
- Passphrase ключа: в `~/.ssh/askpass.sh`
- SSH: `SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force ssh -i ~/.ssh/fenix user1@213.171.25.85`
- OpenClaw 2026.7.34 (обновлён 20.09.2026), порт 18789, systemd user unit `openclaw-gateway.service`
- Workspace: `/home/user1/phoenix/` | fz425-agent: `/home/user1/phoenix/fz425-agent/`
- Перезапуск: ТОЛЬКО `bash ~/phoenix/safe-restart.sh` (НЕ systemctl restart!)
- Команда «почини Феникса» → SSH-подключение + диагностика (статус, логи, диск/RAM)
- ⚠️ fail2ban банит IP на ~10 мин после перебора пользователей — не перебирать
- ⚠️ `openclaw tui` на Фениксе перезаписывает openclaw.json — не трогать конфиг из TUI
- ⚠️ НЕ ставить `tools.allow: ['message']` — такого инструмента нет, агенты становятся немыми
- Маршрутизация: «Федор» в начале сообщения → fz425-agent; иначе main (подробности: memory/2026-08-01.md)
- Мониторинг: «статус Феникса» → SSH `bash ~/health.sh` (CPU/RAM/DISK/Swap/топ-процессы)
- Мониторинг живой: «живой статус Феникса» → 3 замера с интервалом 2 сек
- Мониторинг прогона: «прогон жив?» / «статус прогона» → SSH `bash ~/check-run.sh` (вердикт по model-fetch активности + load/RAM/диск/xlsx: ✅ завершён / 🟢 идёт / 🔴 стоит). model-fetch — главный признак реальной работы subagent'а (xlsx/лог оркестратора обновляются только при завершении региона).
- Интерактивный: tmux-сессия `monitor` (htop), подключение: `ssh -i ~/.ssh/fenix user1@213.171.25.85 -t tmux attach -t monitor`

