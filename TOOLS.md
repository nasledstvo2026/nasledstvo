# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## Timeweb (nasledstvo.net.ru)

- **Хостинг:** Timeweb Cloud
- **IP:** 87.249.38.179
- **SSH пользователь:** `cq832843`
- **SSH ключ:** `~/.ssh/timeweb`
- **Webroot:** `~/public_html`
- **Команда:** `ssh -i ~/.ssh/timeweb cq832843@87.249.38.179`
- **SCP загрузка:** `scp -i ~/.ssh/timeweb <file> cq832843@87.249.38.179:~/public_html/`
- **Скрипты:** `upload-to-timeweb.sh`, `update-index-timeweb.sh`
- **Сайт:** https://nasledstvo.net.ru

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

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
