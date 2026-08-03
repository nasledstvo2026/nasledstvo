# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

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
- OpenClaw 2026.6.11, порт 18789, systemd user unit `openclaw-gateway.service`
- Workspace: `/home/user1/phoenix/` | fz425-agent: `/home/user1/phoenix/fz425-agent/`
- Перезапуск: ТОЛЬКО `bash ~/phoenix/safe-restart.sh` (НЕ systemctl restart!)
- Команда «почини Феникса» → SSH-подключение + диагностика (статус, логи, диск/RAM)
- ⚠️ fail2ban банит IP на ~10 мин после перебора пользователей — не перебирать
- ⚠️ `openclaw tui` на Фениксе перезаписывает openclaw.json — не трогать конфиг из TUI
- ⚠️ НЕ ставить `tools.allow: ['message']` — такого инструмента нет, агенты становятся немыми
- Маршрутизация: «Федор» в начале сообщения → fz425-agent; иначе main (подробности: memory/2026-08-01.md)

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

## Related

- [Agent workspace](/concepts/agent-workspace)
