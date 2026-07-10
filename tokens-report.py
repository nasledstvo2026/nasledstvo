#!/usr/bin/env python3
"""tokens-report.py — Полный отчёт по токенам: cron + прямые чаты + subagents"""

import json, subprocess, sys, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

HTML_FILE = "/tmp/tokens.html"
DATA_FILE = "/tmp/tokens-data.json"
SNAPSHOT_FILE = "/tmp/tokens-snapshot.json"

SSH_KEY = os.path.expanduser("~/.ssh/timeweb")
SSH_HOST = "cq832843@87.249.38.179"
REMOTE_DIR = "~/public_html"

MSK = timezone(timedelta(hours=3))
NOW_MS = int(time.time() * 1000)
CUTOFF_MS = NOW_MS - 86400000
TODAY = datetime.now(MSK).strftime("%Y-%m-%d")

# Маппинг session key → пользователь
SESSION_USER_MAP = {
    "346428630": "Кирилл",
    "932052526": "Катя",
    "254785028": "Лена",
    "221828063": "Данил",
    "335268873": "Роман",
    "175808089": "Роза",
    "739016616": "Ирина",
}

# Маппинг cron job → пользователь
CRON_USER_MAP = {
    "94228ca5-290b-47c2-906e-be658e0ff49b": "Катя",
    "b4f0e3ed-affb-4449-ab73-c547f0876079": "Лена",
    "e001daa1-ec86-4acf-8830-a5204df21a03": "Данил",
    "ef30162f-05de-4521-b91f-0044baf34a64": "Данил",
    "04ed00c5-d59c-4ae2-afbb-03720a93dec2": "Лена",
    "6f3b5037-c174-424d-94a1-dc5413031bb7": "Бэкапы",
    "a7ec1604-6bd8-428d-ba09-dbc894956f5b": "Бэкапы",
    "0d49cb67-c918-4123-9441-4ed146282b10": "Ирина",
    "8df8451b-1cf7-4999-ba2b-353fcd7e65ae": "Роза",
    "dd880535-864a-4720-bc61-edde8476478c": "Система",
}

CRON_JOBS = list(CRON_USER_MAP.keys())

# Маппинг модель → стоимость за 1M токенов
MODEL_COST = {
    "deepseek-chat": {"input": 0.27, "output": 1.10},
    "glm-5.1": {"input": 1.40, "output": 4.40},
}


def run_json(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except:
        return None


def collect_cron_runs():
    """Собирает usage из cron runs за 24ч"""
    usage = {}  # user -> {model -> {input, output, total}}
    for job_id, user in CRON_USER_MAP.items():
        data = run_json(f"openclaw cron runs --id {job_id} --limit 50 --json 2>/dev/null")
        if not data or "entries" not in data:
            continue
        for entry in data["entries"]:
            if entry.get("runAtMs", 0) < CUTOFF_MS:
                continue
            if entry.get("status") != "ok":
                continue
            model = entry.get("model", "unknown")
            u = entry.get("usage", {})
            inp = u.get("input_tokens", 0) or 0
            out = u.get("output_tokens", 0) or 0
            tot = u.get("total_tokens", 0) or 0
            if user not in usage:
                usage[user] = {}
            if model not in usage[user]:
                usage[user][model] = {"input": 0, "output": 0, "total": 0}
            usage[user][model]["input"] += inp
            usage[user][model]["output"] += out
            usage[user][model]["total"] += tot
    return usage


def collect_sessions():
    """Собирает usage из прямых чатов за 24ч (дельта от предыдущего снапшота)"""
    data = run_json("openclaw sessions list --json --limit all 2>/dev/null")
    if not data or "sessions" not in data:
        return {}

    # Загрузить предыдущий снапшот
    snapshot = {}
    if os.path.exists(SNAPSHOT_FILE):
        try:
            with open(SNAPSHOT_FILE) as f:
                snapshot = json.load(f)
        except:
            pass

    current = {}
    for s in data["sessions"]:
        key = s["key"]
        updated = s.get("updatedAt", 0)
        model = s.get("model", "unknown")
        inp = s.get("inputTokens") or 0
        out = s.get("outputTokens") or 0
        # totalTokens = размер контекста, не расход. Используем inputTokens+outputTokens
        tot = inp + out
        current[key] = {
            "model": model,
            "input": inp,
            "output": out,
            "total": tot,
            "updatedAt": updated,
            "kind": s.get("kind", ""),
        }

    # Сохранить текущий снапшот
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(current, f)

    # Считаем дельту
    usage = {}
    for key, cur in current.items():
        if cur["updatedAt"] < CUTOFF_MS:
            continue
        kind = cur["kind"]
        if kind == "cron":
            continue  # cron считаем отдельно

        # Определяем пользователя
        user = "Система"
        if kind == "direct":
            parts = key.split(":")
            if len(parts) >= 4:
                uid = parts[-1]
                user = SESSION_USER_MAP.get(uid, f"Chat {uid}")
        elif kind == "spawn-child":
            user = "Subagent"

        # Дельта от снапшота или полное значение если нового ключа не было
        prev = snapshot.get(key, {})
        prev_input = prev.get("input", 0)
        prev_output = prev.get("output", 0)
        d_input = max(0, cur["input"] - prev_input)
        d_output = max(0, cur["output"] - prev_output)
        d_total = d_input + d_output

        if d_total == 0:
            continue

        model = cur["model"]
        if user not in usage:
            usage[user] = {}
        if model not in usage[user]:
            usage[user][model] = {"input": 0, "output": 0, "total": 0}
        usage[user][model]["input"] += d_input
        usage[user][model]["output"] += d_output
        usage[user][model]["total"] += d_total

    return usage


def merge_usage(cron_usage, session_usage):
    """Объединяет usage из cron и сессий"""
    result = {}
    for src in [cron_usage, session_usage]:
        for user, models in src.items():
            if user not in result:
                result[user] = {}
            for model, vals in models.items():
                if model not in result[user]:
                    result[user][model] = {"input": 0, "output": 0, "total": 0}
                result[user][model]["input"] += vals["input"]
                result[user][model]["output"] += vals["output"]
                result[user][model]["total"] += vals["total"]
    return result


def calc_totals(usage):
    """Считает итоги по моделям и всего"""
    by_model = {}
    by_user = {}
    for user, models in usage.items():
        user_total = 0
        for model, vals in models.items():
            if model not in by_model:
                by_model[model] = {"input": 0, "output": 0, "total": 0}
            by_model[model]["input"] += vals["input"]
            by_model[model]["output"] += vals["output"]
            by_model[model]["total"] += vals["total"]
            user_total += vals["total"]
        by_user[user] = user_total

    all_total = sum(m["total"] for m in by_model.values())

    # Стоимость
    for model, vals in by_model.items():
        cost_per = MODEL_COST.get(model, {"input": 0, "output": 0})
        vals["cost"] = round(vals["input"] / 1e6 * cost_per["input"] + vals["output"] / 1e6 * cost_per["output"], 2)

    all_cost = round(sum(m.get("cost", 0) for m in by_model.values()), 2)

    return by_model, by_user, all_total, all_cost


def make_svg(data_items, colors, total, min_pct=3):
    """Генерирует SVG pie chart с подписями"""
    import math
    parts = []
    accum = 0
    for i, (label, value) in enumerate(data_items):
        pct = (value / total * 100) if total > 0 else 0
        deg = pct * 3.6
        color = colors[i % len(colors)]

        if deg < 0.5:
            accum += deg
            continue

        cx, cy, r = 100, 100, 90
        start_rad = math.radians(accum) - math.pi / 2
        end_rad = math.radians(accum + deg) - math.pi / 2

        x1 = cx + r * math.cos(start_rad)
        y1 = cy + r * math.sin(start_rad)
        x2 = cx + r * math.cos(end_rad)
        y2 = cy + r * math.sin(end_rad)

        large = 1 if deg > 180 else 0

        if deg >= 359.9:
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')
        else:
            parts.append(f'<path d="M{cx},{cy} L{x1:.2f},{y1:.2f} A{r},{r} 0 {large},1 {x2:.2f},{y2:.2f} Z" fill="{color}"/>')

        # Подпись
        if pct > min_pct:
            mid_rad = math.radians(accum + deg / 2) - math.pi / 2
            lr = r * 0.6
            lx = cx + lr * math.cos(mid_rad)
            ly = cy + lr * math.sin(mid_rad)
            parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="central" fill="#0d1117" font-size="11" font-weight="700">{label}</text>')
            parts.append(f'<text x="{lx:.1f}" y="{ly + 14:.1f}" text-anchor="middle" dominant-baseline="central" fill="#0d1117" font-size="10">{pct:.1f}%</text>')

        accum += deg

    return f'<svg viewBox="0 0 200 200" width="200" height="200">{"".join(parts)}</svg>'


def fmt(n):
    return f"{n:,}".replace(",", " ")


def generate_html(usage, by_model, by_user, all_total, all_cost, historical):
    """Генерирует HTML"""

    # Диаграмма по моделям
    model_colors = ["#7ee787", "#58a6ff", "#ff7b72", "#d2a8ff"]
    model_items = sorted(by_model.items(), key=lambda x: -x[1]["total"])
    model_svg = make_svg(
        [(m, v["total"]) for m, v in model_items],
        model_colors, all_total, min_pct=2
    )
    model_legend = ""
    for i, (m, v) in enumerate(model_items):
        pct = v["total"] / all_total * 100 if all_total > 0 else 0
        color = model_colors[i % len(model_colors)]
        model_legend += f'<div class="legend-item"><span class="legend-dot" style="background:{color}"></span><span class="legend-label">{m}</span><span class="legend-val">{fmt(v["total"])} <span class="legend-pct">({pct:.1f}%)</span></span></div>\n'

    # Диаграмма по пользователям
    user_colors = ["#58a6ff", "#7ee787", "#ff7b72", "#d2a8ff", "#ffa657", "#79c0ff", "#f0883e", "#a5d6ff"]
    user_items = sorted(by_user.items(), key=lambda x: -x[1])
    user_svg = make_svg(user_items, user_colors, all_total, min_pct=5)
    user_legend = ""
    for i, (u, t) in enumerate(user_items):
        pct = t / all_total * 100 if all_total > 0 else 0
        color = user_colors[i % len(user_colors)]
        user_legend += f'<div class="legend-item"><span class="legend-dot" style="background:{color}"></span><span class="legend-label">{u}</span><span class="legend-val">{fmt(t)} <span class="legend-pct">({pct:.1f}%)</span></span></div>\n'

    # Таблица по моделям
    model_rows = ""
    for m, v in model_items:
        cost = v.get("cost", 0)
        model_rows += f'<div class="row"><span class="label">{m}</span><span class="val">{fmt(v["total"])} · <span class="money">${cost:.2f}</span></span></div>\n'
    model_rows += f'<div class="row"><span class="label">Итого</span><span class="val">{fmt(all_total)} · <span class="money">${all_cost:.2f}</span></span></div>'

    # История за 7 дней
    days = len(historical)
    hist_rows = ""
    for m in ["deepseek-chat", "glm-5.1"]:
        s_total = sum(d.get("models", {}).get(m, {}).get("total", 0) for d in historical)
        s_cost = round(sum(d.get("models", {}).get(m, {}).get("cost", 0) for d in historical), 2)
        if s_total > 0:
            hist_rows += f'<div class="row"><span class="label">{m}</span><span class="val">{fmt(s_total)} · <span class="money">${s_cost:.2f}</span></span></div>\n'
    s_all = sum(d.get("all_total", 0) for d in historical)
    s_all_cost = round(sum(d.get("all_cost", 0) for d in historical), 2)
    hist_rows += f'<div class="row"><span class="label">Итого</span><span class="val">{fmt(s_all)} · <span class="money">${s_all_cost:.2f}</span></span></div>'

    datetime_str = datetime.now(MSK).strftime("%d.%m.%Y %H:%M")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📊 Токены — nasledstvo.net.ru</title>
<link rel="stylesheet" href="theme.css">
<style>
.block{{margin-bottom:32px}}
.block h2{{margin-bottom:8px}}
.row{{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #21262d;font-size:15px}}
.row:last-child{{border:none}}
.label{{color:#8b949e}}
.val{{font-weight:700}}
.money{{color:#7ee787}}
.sep{{border-top:2px solid #58a6ff;margin:16px 0}}
.pie-section{{margin:32px 0}}
.pie-wrapper{{display:flex;align-items:center;gap:32px;flex-wrap:wrap;justify-content:center}}
.legend{{display:flex;flex-direction:column;gap:10px;min-width:200px}}
.legend-item{{display:flex;align-items:center;gap:10px}}
.legend-dot{{width:14px;height:14px;border-radius:3px;flex-shrink:0}}
.legend-label{{min-width:80px;color:#c9d1d9}}
.legend-val{{font-weight:700;font-size:14px}}
.legend-pct{{color:#8b949e;font-weight:400;font-size:13px}}
</style>
</head>
<body>
<div class="container">
<a href="index.html" class="back">← Главная</a>
<div class="hero"><h1 class="title">📊 Токены</h1><p class="meta">Потрачено за сегодня (все источники)</p></div>

<div class="pie-section">
<h2 class="title">По моделям</h2>
<div class="pie-wrapper">
{model_svg}
<div class="legend">
{model_legend}
</div>
</div>
</div>

<div class="sep"></div>

<div class="pie-section">
<h2 class="title">По пользователям</h2>
<div class="pie-wrapper">
{user_svg}
<div class="legend">
{user_legend}
</div>
</div>
</div>

<div class="sep"></div>

<div class="block">
{model_rows}
</div>

<div class="sep"></div>

<div class="block">
<h2 class="title">За {days} дней</h2>
{hist_rows}
</div>

<div class="footer"><p>☽ Лунт · {datetime_str}</p></div>
</div>
</body>
</html>"""


def main():
    upload = "--upload" in sys.argv

    print("📊 Собираю cron runs...")
    cron_usage = collect_cron_runs()

    print("📊 Собираю sessions...")
    session_usage = collect_sessions()

    print("📊 Объединяю...")
    usage = merge_usage(cron_usage, session_usage)
    by_model, by_user, all_total, all_cost = calc_totals(usage)

    print(f"  Итого: {fmt(all_total)} токенов, ${all_cost:.2f}")
    for m, v in by_model.items():
        print(f"  {m}: {fmt(v['total'])} (${v['cost']:.2f})")

    # Загрузить историю
    print("📥 Скачиваю tokens-data.json...")
    os.system(f"scp -i {SSH_KEY} {SSH_HOST}:{REMOTE_DIR}/tokens-data.json {DATA_FILE} 2>/dev/null || true")
    try:
        with open(DATA_FILE) as f:
            historical = json.load(f)
    except:
        historical = []

    # Сохранить день
    day_record = {
        "date": TODAY,
        "all_total": all_total,
        "all_cost": all_cost,
        "models": {m: {"input": v["input"], "output": v["output"], "total": v["total"], "cost": v["cost"]} for m, v in by_model.items()},
        "users": by_user,
    }

    historical = [d for d in historical if d.get("date") != TODAY] + [day_record]
    historical = historical[-7:]

    with open(DATA_FILE, "w") as f:
        json.dump(historical, f, ensure_ascii=False)

    # Генерация HTML
    html = generate_html(usage, by_model, by_user, all_total, all_cost, historical)
    with open(HTML_FILE, "w") as f:
        f.write(html)
    print(f"✅ HTML: {os.path.getsize(HTML_FILE)} байт")

    if upload:
        print("📤 Загружаю...")
        for attempt in range(1, 4):
            r = os.system(f"scp -i {SSH_KEY} -o ConnectTimeout=10 {HTML_FILE} {DATA_FILE} {SSH_HOST}:{REMOTE_DIR}/")
            if r == 0:
                print(f"✅ Готово (попытка {attempt})")
                return
            print(f"⚠️ Попытка {attempt}/3 не удалась")
            if attempt < 3:
                print("   Жду 15с...")
                time.sleep(15)
        print("❌ Не удалось загрузить после 3 попыток")
        sys.exit(1)


if __name__ == "__main__":
    main()
