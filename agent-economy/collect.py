#!/usr/bin/env python3
import json, os, glob, time

HOME = os.path.expanduser("~/.openclaw")
cfg = json.load(open(os.path.join(HOME, "openclaw.json")))

def mask(x):
    x = str(x)
    return x[:3] + "***" + x[-2:] if len(x) > 6 else x

agents = cfg.get("agents", {}) or {}
entries = agents.get("entries", {}) or {}
default_model = ((agents.get("defaults") or {}).get("model") or {})
if isinstance(default_model, dict):
    default_model = default_model.get("primary")

bindings = cfg.get("bindings") or agents.get("bindings") or []
tg = (cfg.get("channels") or {}).get("telegram") or {}
allow = (tg.get("allowFrom") or [])
accounts = tg.get("accounts") or {}

bound_ids = set()
doors = []
for b in bindings:
    peer = ((b.get("match") or {}).get("peer") or {})
    pid = peer.get("id")
    if pid:
        bound_ids.add(str(pid))
    doors.append({
        "agentId": b.get("agentId"),
        "peer": mask(pid) if pid else "catch-all (весь аккаунт)",
        "scope": ((b.get("match") or {}).get("accountId") or ((b.get("match") or {}).get("channel")) or "-"),
        "catch_all": not bool(pid),
    })

unbound = [mask(i) for i in allow if str(i) not in bound_ids]

skills_ws = sorted(glob.glob(os.path.join(HOME, "workspace/skills/*/SKILL.md")))
skills_workshop = sorted(glob.glob(os.path.join(HOME, "agents/*/agent/workshop-skills/*/SKILL.md")))
skill_names = sorted({os.path.basename(os.path.dirname(p)) for p in skills_ws + skills_workshop})

cron_dir = os.path.join(HOME, "cron")
cron_jobs = []
for f in glob.glob(os.path.join(cron_dir, "*.json")):
    try:
        d = json.load(open(f))
        if isinstance(d, dict):
            jobs = d.get("jobs") or d.get("entries") or []
            if isinstance(jobs, list):
                for j in jobs:
                    if isinstance(j, dict):
                        cron_jobs.append({"name": j.get("name") or j.get("id"), "schedule": j.get("schedule") or j.get("cron"), "enabled": j.get("enabled", True)})
    except Exception:
        pass

out = {
    "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
    "agents_total": len(entries),
    "agents": sorted(entries.keys()),
    "default_model": default_model,
    "skills_total": len(skill_names),
    "skills_workspace": len(skills_ws),
    "skills_workshop": len(skills_workshop),
    "skills_top": skill_names[:24],
    "channels": list((cfg.get("channels") or {}).keys()),
    "accounts": {k: {"enabled": v.get("enabled")} for k, v in accounts.items()},
    "allow_count": len(allow),
    "doors": doors,
    "unbound": unbound,
    "cron_jobs": cron_jobs,
    "cost": {"status": "refreshing", "stale_files": 1392, "note": "кэш пересчитывается — цифры расхода недоступны"},
}
os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
print(json.dumps(out, ensure_ascii=False, indent=1))
