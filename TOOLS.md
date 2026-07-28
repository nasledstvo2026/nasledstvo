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
- Ветка деплоя: `gh-pages` (НЕ master)
- Домен: `https://nasledstvo2026.github.io/nasledstvo/`
- Remote: `origin` (git@github.com:nasledstvo2026/nasledstvo.git)

### VPS (Лунт)
- Хост: vm-low4-8
- ОС: Linux 6.8.0-136-generic (x64)
- Node: v22.23.1
- Gateway: OpenClaw

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
