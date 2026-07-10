#!/usr/bin/env python3
"""
generate-tasks.py — генератор tasks.html
Запрашивает cron-задачи + usage из OpenClaw API + trajectory-файлы,
рендерит HTML и публикует на GitHub Pages.

Запуск:  python3 generate-tasks.py --publish
"""
import json, subprocess, sys, os, re, datetime
from pathlib import Path

HOME = Path.home()
WK = HOME / ".openclaw" / "workspace"
TRAJECTORY_DIR = HOME / ".openclaw" / "agents" / "main" / "sessions"
TZ = datetime.timezone(datetime.timedelta(hours=3))
NOW = datetime.datetime.now(TZ)

# ── Тарифы из openclaw.json ──
# deepseek-chat (все cron-задачи): input $0.27, output $1.10, cache $0.07
RATES_CHAT = {"input": 0.27, "output": 1.10, "cache": 0.07}
# deepseek-v4-flash: input $0.14, output $0.28, cache $0.028
RATES_FLASH = {"input": 0.14, "output": 0.28, "cache": 0.028}
# model → rates mapping
MODEL_RATES = {
    "deepseek-chat": RATES_CHAT,
    "deepseek/deepseek-chat": RATES_CHAT,
    "deepseek-v4-flash": RATES_FLASH,
    "deepseek/deepseek-v4-flash": RATES_FLASH,
}


def run(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        print(f"⚠️  {cmd[0]} error: {r.stderr.strip()[:200]}", file=sys.stderr)
        return None
    return r.stdout.strip()


def get_jobs():
    raw = run(["openclaw", "cron", "list", "--json"])
    if not raw:
        return []
    return json.loads(raw).get("jobs", [])


def get_last_run(job_id):
    """Получить последний успешный запуск задачи с sessionId."""
    raw = run(["openclaw", "cron", "runs", "--id", job_id, "--limit", "5"])
    if not raw:
        return None
    data = json.loads(raw)
    entries = data.get("entries", [])
    # Ищем последний успешный
    for e in entries:
        if e.get("status") == "ok":
            return e
    return entries[0] if entries else None


def get_trajectory_usage(session_id, model_id):
    """Прочитать usage из trajectory-файла сессии.
    В trajectory хранятся сырые данные: input, output, cacheRead, reasoningTokens.
    """
    traj_path = TRAJECTORY_DIR / f"{session_id}.trajectory.jsonl"
    if not traj_path.exists():
        return None

    usage = {"input": 0, "output": 0, "cacheRead": 0, "reasoningTokens": 0}
    with open(traj_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "model.completed":
                continue
            u = d.get("data", {}).get("usage")
            if not u:
                continue
            inp = u.get("input", 0) or 0
            out = u.get("output", 0) or 0
            cache = u.get("cacheRead", 0) or 0
            reason = u.get("reasoningTokens", 0) or 0

            # Суммируем все model.completed в рамках сессии
            usage["input"] += inp
            usage["output"] += out
            usage["cacheRead"] += cache
            usage["reasoningTokens"] += reason

    if usage["input"] == 0 and usage["output"] == 0:
        return None
    return usage


def fmt_date(ms):
    if not ms:
        return "—"
    dt = datetime.datetime.fromtimestamp(ms / 1000, tz=TZ)
    return dt.strftime("%d.%m %H:%M")


def tl(cond_green, cond_yellow):
    if cond_green:
        return "green"
    if cond_yellow:
        return "yellow"
    return "red"


def metric_html(light, text):
    return f'<span class="metric"><span class="tl tl-{light}"></span> {text}</span>'


def na_html():
    return '<span class="metric-na">—</span>'


def calc_cost(usage, model_id):
    """Рассчитать стоимость по тарифам модели из openclaw.json."""
    if not usage:
        return None
    rates = MODEL_RATES.get(model_id, RATES_CHAT)
    inp = usage.get("input", 0)
    out = usage.get("output", 0)
    cache = usage.get("cacheRead", 0)
    cost = (inp * rates["input"] + cache * rates["cache"] + out * rates["output"]) / 1_000_000
    return cost


def cost_str(cost):
    if cost is None:
        return "—"
    if cost < 0.01:
        return f"<${cost:.4f}"
    return f"${cost:.3f}"


def cache_hit_str(usage):
    """Cache hit = cacheRead / (input + cacheRead) × 100"""
    if not usage:
        return "—", None
    inp = usage.get("input", 0)
    cache = usage.get("cacheRead", 0)
    total_prompt = inp + cache
    if total_prompt == 0:
        return "—", None
    pct = (cache / total_prompt) * 100
    light = tl(pct > 80, pct >= 50)
    return metric_html(light, f"{pct:.0f}%"), pct


def reasoning_str(usage, model_id):
    """Reasoning = reasoningTokens / output × 100.
    deepseek-chat не поддерживает reasoning (всегда None).
    """
    if not usage:
        return "—", None
    # deepseek-chat не возвращает reasoningTokens
    if "deepseek-chat" in model_id and not usage.get("reasoningTokens"):
        return "—", None
    out = usage.get("output", 0)
    reason = usage.get("reasoningTokens", 0)
    if out == 0:
        return "—", None
    pct = (reason / out) * 100
    light = tl(pct < 20, pct <= 40)
    return metric_html(light, f"{pct:.0f}%"), pct


# ── Парсинг расписания ──
WEEKDAYS = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"]


def schedule_str(cron_expr, tz_str):
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return cron_expr
    min_s, hour_s, dom_s, mon_s, dow_s = parts
    h, m = int(hour_s), int(min_s)
    time = f"{h:02d}:{m:02d}"
    if dow_s == "*" and dom_s == "*" and mon_s == "*":
        return f"Ежедневно {time}"
    if dow_s == "1-5":
        return f"Пн–Пт {time}"
    if dow_s == "0" or dow_s == "7":
        return f"Вс {time}"
    if dow_s.isdigit():
        return f"{WEEKDAYS[int(dow_s)].title()} {time}"
    if "," in dow_s:
        days = [WEEKDAYS[int(d)] for d in dow_s.split(",")]
        return f"{'–'.join([d.title() for d in days])} {time}"
    if dom_s == "1":
        return f"1-го числа {time}"
    return f"{cron_expr} ({tz_str})"


# ── Статические данные ──
AUTHORS = {
    "Сводка жалоб: наследство в банках (5 площадок)": "Катя",
    "📊 Обновление статистики жалоб (stats-inheritance)": "Катя",
    "Ежедневная сводка: наследство и банки": "Лена",
    "📋 Роза: сводка изменений в законах по пособиям": "Роза",
    "Ирина: еженедельный обзор НПА": "Ирина",
    "Анализ новостей по вкладам 1991 — понедельник": "Данил",
    "Анализ новостей по вкладам 1991 — четверг": "Данил",
    "РЖД 1Р-37R — итоги торгов": "Лена",
    "Бэкап: полный (раз в неделю)": "Кирилл",
    "📊 Активность пользователей": "—",
}

TASK_SHORT = {
    "Сводка жалоб: наследство в банках (5 площадок)": "Сводка жалоб — наследство",
    "📊 Обновление статистики жалоб (stats-inheritance)": "Обновление статистики",
    "Ежедневная сводка: наследство и банки": "Дайджест новостей",
    "📋 Роза: сводка изменений в законах по пособиям": "Изменения в законах по пособиям",
    "Ирина: еженедельный обзор НПА": "Обзор НПА",
    "Анализ новостей по вкладам 1991 — понедельник": "Вклады 1991 — понедельник",
    "Анализ новостей по вкладам 1991 — четверг": "Вклады 1991 — четверг",
    "РЖД 1Р-37R — итоги торгов": "РЖД 1Р-37R — итоги",
    "Бэкап: полный (раз в неделю)": "Бэкап: полный",
    "📊 Активность пользователей": "Активность пользователей",
}

RECOMMENDATIONS = {
    "Сводка жалоб: наследство в банках (5 площадок)": "Уменьшить таймаут с 300 до 120&nbsp;с. Перенести на 08:30 — разгрузить очередь 08:00.",
    "📊 Обновление статистики жалоб (stats-inheritance)": "Уменьшить таймаут с 300 до 120&nbsp;с.",
    "Ежедневная сводка: наследство и банки": "Перевести на sessionTarget=main или выделить sessionKey. Уменьшить таймаут с 300 до 120&nbsp;с.",
    "📋 Роза: сводка изменений в законах по пособиям": "Перенести на 08:30 пн — разгрузить очередь 09:00. Уменьшить таймаут с 300 до 120&nbsp;с.",
    "Ирина: еженедельный обзор НПА": "Увеличить таймаут с 300 до 400&nbsp;с. Сократить поисковые запросы с 3 до 2. Перенести на 09:30.",
    "Анализ новостей по вкладам 1991 — понедельник": "Перевести на sessionTarget=main. Уменьшить таймаут с 300 до 120&nbsp;с.",
    "Анализ новостей по вкладам 1991 — четверг": "Уменьшить таймаут с 300 до 120&nbsp;с.",
    "РЖД 1Р-37R — итоги торгов": "Увеличить таймаут с 60 до 90&nbsp;с.",
    "Бэкап: полный (раз в неделю)": "Увеличить таймаут со 120 до 180&nbsp;с.",
    "📊 Активность пользователей": "Увеличить таймаут с 60 до 90&nbsp;с.",
}


def generate_html(jobs, runs_data, trajectory_usage):
    rows_html = []
    now_str = NOW.strftime("%d.%m.%Y %H:%M")

    for job in jobs:
        jid = job["id"]
        name = job.get("name", "—")
        if not job.get("enabled", True):
            continue

        sched = job.get("schedule", {})
        expr = sched.get("expr", "")
        tz_s = sched.get("tz", "МСК")
        sch = schedule_str(expr, tz_s)

        timeout = job.get("payload", {}).get("timeoutSeconds", 60)
        state = job.get("state", {})
        last_run_ms = state.get("lastRunAtMs")
        last_dur_ms = state.get("lastDurationMs")
        last_status = state.get("lastRunStatus", "unknown")
        cons_err = state.get("consecutiveErrors", 0)

        # Длительность
        dur_s = last_dur_ms / 1000 if last_dur_ms else None
        dur_str = f"{dur_s:.0f} с" if dur_s else "—"
        dur_pct = (dur_s / timeout * 100) if (dur_s and timeout) else None

        if dur_pct is not None:
            dt_light = tl(dur_pct < 50, dur_pct <= 80)
            dt_html = metric_html(dt_light, f"{dur_pct:.0f}%")
        else:
            dt_html = na_html()

        if cons_err == 0 and last_status == "ok":
            sr_html = metric_html("green", "100%")
        elif cons_err > 0:
            sr_html = metric_html("red", f"{100 - cons_err * 5}%")
        else:
            sr_html = na_html()

        # Latency
        run_info = runs_data.get(jid, {})
        run_at_ms = run_info.get("runAtMs", last_run_ms)
        planned_hour = int(expr.split()[1]) if expr and len(expr.split()) > 1 else 0
        planned_min = int(expr.split()[0]) if expr and len(expr.split()) > 0 else 0
        if run_at_ms:
            run_dt = datetime.datetime.fromtimestamp(run_at_ms / 1000, tz=TZ)
            planned_dt = run_dt.replace(hour=planned_hour, minute=planned_min, second=0, microsecond=0)
            latency_min = max(0, (run_dt - planned_dt).total_seconds() / 60)
        else:
            latency_min = None

        if latency_min is None:
            lat_html = na_html()
        elif latency_min <= 1:
            lat_html = metric_html("green", "0 мин")
        elif latency_min <= 15:
            lat_html = metric_html("yellow", f"+{latency_min:.0f} мин")
        else:
            lat_html = metric_html("red", f"+{latency_min:.0f} мин")

        # Usage из trajectory (сырые данные)
        model_id = run_info.get("model", "deepseek-chat")
        sess_id = run_info.get("sessionId", "")
        usage = trajectory_usage.get(sess_id)

        cache_h, _ = cache_hit_str(usage)
        if cache_h == "—" or cache_h is None:
            cache_h = na_html()

        cost = calc_cost(usage, model_id)
        cost_h = cost_str(cost) if cost else str(na_html())

        author = AUTHORS.get(name, "—")
        short = TASK_SHORT.get(name, name)
        rec = RECOMMENDATIONS.get(name, "—")
        last_run_str = fmt_date(run_at_ms)

        rows_html.append(f"""          <tr>
            <td><span class="status-dot ok"></span> {short}</td>
            <td>{author}</td>
            <td>{sch}</td>
            <td>{dt_html}</td>
            <td>{sr_html}</td>
            <td>{lat_html}</td>
            <td>{cache_h}</td>
            <td>{cost_h}</td>
            <td>{last_run_str}</td>
            <td class="rec">{rec}</td>
          </tr>""")

    # Показываем цены из конфига (deepseek-chat, основной для крона)
    r = RATES_CHAT
    rows = "\n".join(rows_html)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Задачи — Лунт</title>
  <link rel="stylesheet" href="theme.css">
  <link rel="stylesheet" href="style.css">
</head>
<body>
<div class="container">

  <a href="service_main.html" class="back">← Назад</a>

  <div class="hero">
    <h1 class="page-title">Все cron-задачи</h1>
    <div class="meta">{len(rows_html)} активных задач · {now_str}</div>
  </div>

  <!-- ═══ Легенда ═══ -->
  <div class="section" style="padding:16px 20px;background:rgba(33,38,45,.3);border-radius:10px;margin-bottom:16px;">
    <h2 style="font-size:14px;margin-bottom:12px;color:var(--text,#c9d1d9);">💡 Легенда</h2>
    <div class="legend-metric">
      <div class="legend-title">⏱ Duration / Timeout</div>
      <div class="legend-desc">Доля времени выполнения от таймаута</div>
      <div class="legend-items"><span><span class="tl tl-green"></span> &lt;50%</span><span><span class="tl tl-yellow"></span> 50–80%</span><span><span class="tl tl-red"></span> &gt;80%</span></div>
    </div>
    <div class="legend-metric">
      <div class="legend-title">📈 Success Rate</div>
      <div class="legend-desc">Процент успешных запусков</div>
      <div class="legend-items"><span><span class="tl tl-green"></span> 100%</span><span><span class="tl tl-yellow"></span> &lt;100%</span><span><span class="tl tl-red"></span> &lt;90%</span></div>
    </div>
    <div class="legend-metric">
      <div class="legend-title">📬 Latency</div>
      <div class="legend-desc">Задержка старта относительно расписания</div>
      <div class="legend-items"><span><span class="tl tl-green"></span> ≤1 мин</span><span><span class="tl tl-yellow"></span> 2–15 мин</span><span><span class="tl tl-red"></span> &gt;15 мин</span></div>
    </div>
    <div class="legend-sep"></div>
    <div class="legend-metric">
      <div class="legend-title">💎 Cache Hit %</div>
      <div class="legend-desc"><code>cacheRead / (input + cacheRead) × 100</code> — эффективность системного промпта. Данные из trajectory сессии (сырой ответ DeepSeek API).</div>
      <div class="legend-items"><span><span class="tl tl-green"></span> &gt;80%</span><span><span class="tl tl-yellow"></span> 50–80%</span><span><span class="tl tl-red"></span> &lt;50%</span></div>
    </div>
    <div class="legend-metric" style="border:none;margin:0;padding:0;">
      <div class="legend-title">💰 Cost / Run</div>
      <div class="legend-desc"><code>(input×${r['input']:.2f} + cache×${r['cache']:.3f} + output×${r['output']:.2f}) / 1M</code> — тарифы deepseek-chat из openclaw.json.</div>
      <div class="legend-items"><span><span class="tl tl-green"></span> &lt;$0.01</span><span><span class="tl tl-yellow"></span> $0.01–0.05</span><span><span class="tl tl-red"></span> &gt;$0.05</span></div>
    </div>
  </div>

  <div class="section">
    <div class="table-wrapper">
      <table class="task-table">
        <thead>
          <tr>
            <th>Задача</th><th>Автор</th><th>Расписание</th>
            <th class="col-metric">⏱ Duration/Timeout</th><th class="col-metric">📈 Success rate</th><th class="col-metric">📬 Latency</th>
            <th class="col-metric">💎 Cache Hit</th><th class="col-metric">💰 Cost/Run</th>
            <th>Последний запуск</th><th class="col-rec">💡 Рекомендация по оптимизации</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </div>
  </div>

  <div class="footer">☽ Лунт · <a href="index.html">Главная</a> · Сгенерировано {now_str}</div>
</div>

<style>
.table-wrapper {{ overflow-x: auto; margin: 10px 0; }}
.task-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; line-height: 1.5; min-width: 1100px; }}
.task-table thead th {{ text-align: left; padding: 10px 8px; background: rgba(33,38,45,.6); border-bottom: 1px solid var(--glass-border,#21262d); color: var(--text-dim,#8b949e); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; white-space: nowrap; }}
.task-table thead th:first-child {{ border-radius: 8px 0 0 0; }}
.task-table thead th:last-child  {{ border-radius: 0 8px 0 0; }}
.col-metric {{ text-align: center !important; }}
.col-rec {{ min-width: 220px; }}
.task-table tbody tr {{ border-bottom: 1px solid rgba(33,38,45,.4); transition: background .15s ease; }}
.task-table tbody tr:hover {{ background: rgba(88,166,255,.04); }}
.task-table tbody td {{ padding: 9px 8px; vertical-align: middle; font-size: 12.5px; }}
.task-table tbody td:first-child {{ font-weight: 500; white-space: nowrap; }}
.task-table tbody td:nth-child(4),.task-table tbody td:nth-child(5),.task-table tbody td:nth-child(6),
.task-table tbody td:nth-child(7) {{ text-align: center; }}
.rec {{ font-size: 12px; color: var(--text,#c9d1d9); line-height: 1.45; }}
.status-dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 7px; vertical-align: middle; position: relative; top: -1px; }}
.status-dot.ok   {{ background: #3fb950; box-shadow: 0 0 5px rgba(63,185,80,.5); }}
.tl {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
.tl-green  {{ background: #3fb950; box-shadow: 0 0 4px rgba(63,185,80,.5); }}
.tl-yellow {{ background: #d29922; box-shadow: 0 0 4px rgba(210,153,34,.5); }}
.tl-red    {{ background: #f85149; box-shadow: 0 0 4px rgba(248,81,73,.5); }}
.metric {{ display: inline-flex; align-items: center; gap: 4px; font-variant-numeric: tabular-nums; }}
.metric-na {{ text-align: center; color: var(--text-dim,#8b949e); font-size: 12px; }}
.legend-sep {{ height: 1px; background: rgba(33,38,45,.5); margin: 12px 0; }}
.legend-metric {{ margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid rgba(33,38,45,.5); }}
.legend-metric:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}
.legend-title {{ font-size: 13px; font-weight: 600; color: var(--text,#c9d1d9); margin-bottom: 2px; }}
.legend-desc {{ font-size: 12px; color: var(--text-dim,#8b949e); margin-bottom: 6px; }}
.legend-items {{ display: flex; gap: 14px; flex-wrap: wrap; }}
.legend-items span {{ display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text-dim,#8b949e); }}
@media (max-width: 1100px) {{ .task-table {{ font-size: 12px; min-width: 800px; }} .task-table tbody td {{ padding: 7px 6px; }} .col-rec {{ min-width: 180px; }} }}
</style>
</body>
</html>"""


def main():
    publish = "--publish" in sys.argv

    print("📡 Получаю список задач...")
    jobs = get_jobs()
    active = [j for j in jobs if j.get("enabled", False)]
    print(f"   Найдено {len(active)} активных задач")

    runs_data = {}
    trajectory_usage = {}

    for j in active:
        jid = j["id"]
        name = j.get("name", "?")
        print(f"   📥 {name} ...", end=" ", flush=True)
        run = get_last_run(jid)
        if run:
            sess_id = run.get("sessionId", "")
            model_id = run.get("model", "deepseek-chat")
            runs_data[jid] = run

            # Пробуем достать usage из trajectory (сырые данные)
            tu = get_trajectory_usage(sess_id, model_id) if sess_id else None
            if tu:
                trajectory_usage[sess_id] = tu
                print(f"trajectory: cache={tu['cacheRead']} reason={tu['reasoningTokens']} cost=${calc_cost(tu, model_id):.4f}")
            else:
                print("данных trajectory нет")
        else:
            print("нет данных")
            runs_data[jid] = {}

    print("\n📝 Генерирую HTML...")
    html = generate_html(active, runs_data, trajectory_usage)
    out_path = WK / "tasks.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"   Сохранено: {out_path}")

    if publish:
        print("\n🚀 Публикую на GitHub Pages...")
        os.chdir(str(WK))
        subprocess.run(["git", "add", "tasks.html"], check=False)
        subprocess.run(["git", "commit", "-m", f"Auto-update: tasks.html — {NOW.strftime('%d.%m.%Y %H:%M')}"], capture_output=True, check=False)
        r = subprocess.run(["git", "push"], capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            print("   ✅ Опубликовано: https://nasledstvo2026.github.io/nasledstvo/tasks.html")
        else:
            print(f"   ⚠️  Ошибка push: {r.stderr.strip()[:200]}")
    else:
        print("\n💡 Запусти с --publish для публикации на GitHub Pages")


if __name__ == "__main__":
    main()
