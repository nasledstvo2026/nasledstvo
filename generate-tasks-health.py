#!/usr/bin/env python3
"""
generate-tasks-health.py — генератор tasks.html с Health Index

Формула Health Index (0–100):
  SR×0.30 + Dur×0.25 + Lat×0.20 + Cache×0.15 + Cost×0.10

Hard Stop: Success Rate < 90% → health = 0 (red)

Читает tasks-data.json, генерирует tasks.html, публикует на GitHub.
"""

import json
import os
import subprocess
import sys
from datetime import datetime

# ═══════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════
DATA_FILE = os.path.join(os.path.dirname(__file__), "tasks-data.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "tasks.html")
WORKSPACE = os.path.dirname(__file__)

WEIGHTS = {
    "success_rate": 0.30,
    "duration":     0.25,
    "latency":      0.20,
    "cache_hit":    0.15,
    "cost":         0.10,
}

# Какие задачи считаются бизнесом (по имени)
BIZ_TASKS = {
    "Сводка жалоб — наследство",
    "Обновление статистики",
    "Дайджест новостей",
    "Изменения в законах по пособиям",
    "Обзор НПА",
    "Вклады 1991 — понедельник",
    "РЖД 1Р-37R — итоги",
    "Вклады 1991 — четверг",
}


# ═══════════════════════════════════════════
# ЯДРО: расчёт Health Index
# ═══════════════════════════════════════════

def score_success_rate(sr):
    if sr >= 100:
        return 100
    elif sr >= 95:
        return 50
    else:
        return 0

def score_duration(pct):
    if pct < 50:
        return 100
    elif pct <= 80:
        return 50
    else:
        return 0

def score_latency(minutes):
    if minutes <= 1:
        return 100
    elif minutes <= 15:
        return 50
    else:
        return 0

def score_cache_hit(pct):
    if pct is None:
        return 0  # нет данных = 0
    if pct > 80:
        return 100
    elif pct >= 50:
        return 50
    else:
        return 0

def score_cost(cost):
    if cost is None:
        return 0
    if cost < 0.01:
        return 100
    elif cost <= 0.05:
        return 60
    else:
        return 20


def calc_health(metrics):
    """
    Принимает словарь с ключами:
      success_rate (float), duration_pct (float),
      latency_min (float), cache_hit_pct (float|None),
      cost_per_run (float|None)
    Возвращает (health_index: int, color: str)
    """
    sr = metrics.get("success_rate", 0)
    dur = metrics.get("duration_pct", 0)
    lat = metrics.get("latency_min", 0)
    cache = metrics.get("cache_hit_pct", None)
    cost = metrics.get("cost_per_run", None)

    # Hard Stop
    if sr < 90:
        return 0, "red"

    sr_s = score_success_rate(sr)
    dur_s = score_duration(dur)
    lat_s = score_latency(lat)
    cache_s = score_cache_hit(cache)
    cost_s = score_cost(cost)

    idx = int(
        sr_s   * WEIGHTS["success_rate"] +
        dur_s  * WEIGHTS["duration"] +
        lat_s  * WEIGHTS["latency"] +
        cache_s * WEIGHTS["cache_hit"] +
        cost_s  * WEIGHTS["cost"]
    )

    if idx >= 80:
        color = "green"
    elif idx >= 50:
        color = "yellow"
    else:
        color = "red"

    return idx, color


# ═══════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ: HTML-метрики
# ═══════════════════════════════════════════

def tl_color(val_pct):
    """Цвет точки Duration/Timeout"""
    if val_pct < 50:
        return "green"
    elif val_pct <= 80:
        return "yellow"
    return "red"

def tl_sr(sr):
    if sr >= 100:
        return "green"
    elif sr >= 95:
        return "yellow"
    return "red"

def tl_lat(minutes):
    if minutes <= 1:
        return "green"
    elif minutes <= 15:
        return "yellow"
    return "red"

def tl_cache(pct):
    if pct is None:
        return None
    if pct > 80:
        return "green"
    elif pct >= 50:
        return "yellow"
    return "red"

def tl_cost(cost):
    if cost is None:
        return None
    if cost < 0.01:
        return "green"
    elif cost <= 0.05:
        return "yellow"
    return "red"

def fmt_cost(cost):
    if cost is None:
        return '<span class="metric-na">—</span>'
    if cost < 0.01:
        return f"<${cost:.4f}"
    return f"${cost:.3f}"

def fmt_cache(pct):
    if pct is None:
        return '<span class="metric-na">—</span>'
    return f'{pct}%'

def health_badge(health_idx, color):
    """Генерирует HTML для бейджа Health Index"""
    emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
    return f'<span class="health-badge health-{color}">{emoji[color]} {health_idx}</span>'


# ═══════════════════════════════════════════
# ГЕНЕРАЦИЯ HTML
# ═══════════════════════════════════════════

def load_opt_status():
    """Читает optimizer-applied.json, возвращает dict {task_name: status}"""
    opt_file = os.path.join(WORKSPACE, "memory", "optimizer-applied.json")
    if not os.path.exists(opt_file):
        return {}
    try:
        with open(opt_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, Exception):
        return {}
    status = {}
    # Собираем все записи из history
    for entry in data.get("history", []):
        task = entry.get("task", "")
        if not task:
            continue
        action = entry.get("action")
        if action and isinstance(action, dict) and action.get("date"):
            status[task] = {"type": "done", "date": action["date"]}
        elif action == "decided":
            status[task] = {"type": "decided"}
        elif action == "seen":
            status[task] = {"type": "seen", "cycle": entry.get("cycle", 1)}
    # Решения текущего цикла — перезаписывают seen
    for dec in data.get("decisions", []):
        task = dec.get("task", "")
        if task:
            status[task] = {"type": "decided"}
    return status


def fmt_opt_status(opt_status, task_name, health_idx):
    """Форматирует HTML для колонки Проработка"""
    if health_idx >= 80:
        return '<span class="stat-na">—</span>'
    st = opt_status.get(task_name, {})
    tp = st.get("type", "")
    if tp == "done":
        date_str = st.get("date", "")[:10]
        return f'<span class="opt-done">✅ {date_str}</span>'
    if tp == "decided":
        return '<span class="opt-decided">✅ зафиксировано</span>'
    if tp == "seen":
        cyc = st.get("cycle", 1)
        if cyc == 1:
            return '<span class="opt-seen">⏳ ждём 2/2</span>'
        else:
            return '<span class="opt-seen">⏳ готово к решению</span>'
    return '<span class="opt-pending">⏳ не рассматривалось</span>'


def gen_task_row(t, biz=True, opt_status=None):
    """Генерирует строку <tr> для задачи"""
    if opt_status is None:
        opt_status = {}
    health_idx, health_color = calc_health(t)
    sr = t["success_rate"]
    dur = t["duration_pct"]
    lat = t["latency_min"]
    cache = t["cache_hit_pct"]
    cost = t["cost_per_run"]

    # Правило: для зелёных задач (>=80) скрываем рекомендацию
    if health_idx >= 80:
        tip_html = '<span style="color:var(--text-dim,#8b949e);">✅ Всё ОК</span>'
    else:
        tip_html = t["tip"]

    opt_html = fmt_opt_status(opt_status, t["task"], health_idx)

    return f"""          <tr>
            <td><span class="status-dot ok"></span> {t["task"]}</td>
            <td>{t["author"]}</td>
            <td>{t["schedule"]}</td>
            <td><span class="metric"><span class="tl tl-{tl_color(dur)}"></span> {dur}%</span></td>
            <td><span class="metric"><span class="tl tl-{tl_sr(sr)}"></span> {sr}%</span></td>
            <td><span class="metric"><span class="tl tl-{tl_lat(lat)}"></span> {"+" if lat > 0 else ""}{lat} мин</span></td>
            <td>{fmt_cache(cache)}</td>
            <td>{fmt_cost(cost)}</td>
            <td>{t["last_run"]}</td>
            <td class="rec">{tip_html}</td>
            <td style="text-align:center;">{opt_html}</td>
            <td style="text-align:center;">{health_badge(health_idx, health_color)}</td>
          </tr>"""


def gen_tasks_html(tasks):
    opt_status = load_opt_status()
    biz_rows = []
    srv_rows = []
    for t in tasks:
        if t["task"] in BIZ_TASKS:
            biz_rows.append(gen_task_row(t, biz=True, opt_status=opt_status))
        else:
            srv_rows.append(gen_task_row(t, biz=False, opt_status=opt_status))

    biz_count = len(biz_rows)
    srv_count = len(srv_rows)
    total = biz_count + srv_count
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    biz_body = "\n".join(biz_rows)
    srv_body = "\n".join(srv_rows)

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
    <div class="meta">{total} активных задач ({biz_count} бизнес + {srv_count} сервисных) · {now_str}</div>
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
      <div class="legend-desc"><code>(input×$0.27 + cache×$0.070 + output×$1.10) / 1M</code> — тарифы deepseek-chat из openclaw.json.</div>
      <div class="legend-items"><span><span class="tl tl-green"></span> &lt;$0.01</span><span><span class="tl tl-yellow"></span> $0.01–0.05</span><span><span class="tl tl-red"></span> &gt;$0.05</span></div>
    </div>
    <div class="legend-sep"></div>
    <div class="legend-metric" style="border:none;margin:0;padding:0;">
      <div class="legend-title">🩺 Health Index</div>
      <div class="legend-desc">Композитная метрика 0–100: SR×30% + Duration×25% + Latency×20% + Cache×15% + Cost×10%. Hard Stop: SR&lt;90% → 0.</div>
      <div class="legend-items"><span><span class="tl tl-green"></span> ≥80</span><span><span class="tl tl-yellow"></span> 50–79</span><span><span class="tl tl-red"></span> &lt;50</span></div>
    </div>
    <div class="legend-sep"></div>
    <div class="legend-metric" style="border:none;margin:0;padding:0;">
      <div class="legend-title">📋 Проработка рекомендаций</div>
      <div class="legend-desc">Статус обработки рекомендаций агентом-оптимизатором (автоматически, каждый 3ч)</div>
      <div class="legend-items">
        <span><span class="opt-status-dot" style="background:transparent;border:1px solid #8b949e;color:#8b949e;width:auto;height:auto;padding:0 4px;font-size:11px;border-radius:3px;">—</span> не требуется</span>
        <span><span class="opt-status-dot opt-dot-seen">⏳</span> ждём 2/2 циклов</span>
        <span><span class="opt-status-dot opt-dot-decided">✅</span> зафиксировано</span>
        <span><span class="opt-status-dot opt-dot-done">✅</span> применено + дата</span>
      </div>
    </div>
  </div>

  <!-- ═══════════════════════════════════════════════════ -->
  <!-- БИЗНЕС-ЗАДАЧИ -->
  <!-- ═══════════════════════════════════════════════════ -->
  <h2 style="font-size:18px;margin:24px 0 12px;color:var(--text,#c9d1d9);">📋 Бизнес-задачи</h2>

  <div class="section">
    <div class="table-wrapper">
      <table class="task-table">
        <thead>
          <tr>
            <th>Задача</th><th>Автор</th><th>Расписание</th>
            <th class="col-metric">⏱ Duration</th><th class="col-metric">📈 Success</th><th class="col-metric">📬 Latency</th>
            <th class="col-metric">💎 Cache</th><th class="col-metric">💰 Cost</th>
            <th>Запуск</th><th class="col-rec">💡 Рекомендация</th>
            <th class="col-metric col-opt">📋 Проработка</th>
            <th class="col-metric">🩺 System Health</th>
          </tr>
        </thead>
        <tbody>
{biz_body}
        </tbody>
      </table>
    </div>
  </div>

  <!-- ═══════════════════════════════════════════════════ -->
  <!-- СЕРВИСНЫЕ ЗАДАЧИ -->
  <!-- ═══════════════════════════════════════════════════ -->
  <h2 style="font-size:18px;margin:28px 0 12px;color:var(--text,#c9d1d9);">⚙️ Сервисные задачи</h2>

  <div class="section">
    <div class="table-wrapper">
      <table class="task-table">
        <thead>
          <tr>
            <th>Задача</th><th>Автор</th><th>Расписание</th>
            <th class="col-metric">⏱ Duration</th><th class="col-metric">📈 Success</th><th class="col-metric">📬 Latency</th>
            <th class="col-metric">💎 Cache</th><th class="col-metric">💰 Cost</th>
            <th>Запуск</th><th class="col-rec">💡 Рекомендация</th>
            <th class="col-metric col-opt">📋 Проработка</th>
            <th class="col-metric">🩺 System Health</th>
          </tr>
        </thead>
        <tbody>
{srv_body}
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
.col-opt {{ min-width: 80px; }}
.opt-pending {{ color: var(--text-dim,#8b949e); font-size: 16px; }}
.opt-seen {{ color: #d29922; font-size: 12px; font-weight: 600; white-space: nowrap; }}
.opt-decided {{ color: #58a6ff; font-size: 12px; font-weight: 600; white-space: nowrap; }}
.opt-done {{ color: #3fb950; font-size: 12px; font-weight: 600; white-space: nowrap; }}
.stat-na {{ color: var(--text-dim,#8b949e); font-size: 12px; }}
.legend-items .opt-status-dot {{ display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 3px; margin-right: 4px; font-size: 11px; vertical-align: middle; background: rgba(33,38,45,.3); }}
.task-table tbody tr {{ border-bottom: 1px solid rgba(33,38,45,.4); transition: background .15s ease; }}
.task-table tbody tr:hover {{ background: rgba(88,166,255,.04); }}
.task-table tbody td {{ padding: 9px 8px; vertical-align: middle; font-size: 12.5px; }}
.task-table tbody td:first-child {{ font-weight: 500; white-space: nowrap; }}
.task-table tbody td:nth-child(4),.task-table tbody td:nth-child(5),.task-table tbody td:nth-child(6),
.task-table tbody td:nth-child(7),.task-table tbody td:nth-child(8) {{ text-align: center; }}
.rec {{ font-size: 12px; color: var(--text,#c9d1d9); line-height: 1.45; }}
.status-dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 7px; vertical-align: middle; position: relative; top: -1px; }}
.status-dot.ok   {{ background: #3fb950; box-shadow: 0 0 5px rgba(63,185,80,.5); }}
.tl {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }}
.tl-green  {{ background: #3fb950; box-shadow: 0 0 4px rgba(63,185,80,.5); }}
.tl-yellow {{ background: #d29922; box-shadow: 0 0 4px rgba(210,153,34,.5); }}
.tl-red    {{ background: #f85149; box-shadow: 0 0 4px rgba(248,81,73,.5); }}
.metric {{ display: inline-flex; align-items: center; gap: 4px; font-variant-numeric: tabular-nums; }}
.metric-na {{ text-align: center; color: var(--text-dim,#8b949e); font-size: 12px; }}
.health-badge {{ display: inline-flex; align-items: center; gap: 3px; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; white-space: nowrap; }}
.health-green  {{ background: rgba(63,185,80,.15); color: #3fb950; }}
.health-yellow {{ background: rgba(210,153,34,.15); color: #d29922; }}
.health-red    {{ background: rgba(248,81,73,.15); color: #f85149; }}
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


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def main():
    if not os.path.exists(DATA_FILE):
        print(f"❌ Не найден {DATA_FILE}")
        sys.exit(1)

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        tasks = json.load(f)

    html = gen_tasks_html(tasks)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ tasks.html сгенерирован — {len(tasks)} задач")

    # Публикация на GitHub
    os.chdir(WORKSPACE)
    r = subprocess.run(
        ["git", "add", "tasks-data.json", "tasks.html"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"⚠️ git add: {r.stderr}")
    r = subprocess.run(
        ["git", "commit", "-m", f"tasks.html: auto-update health index ({datetime.now().strftime('%d.%m %H:%M')})"],
        capture_output=True, text=True
    )
    if r.returncode not in (0, 1):
        print(f"⚠️ git commit: {r.stderr}")
    r = subprocess.run(
        ["git", "push"],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"⚠️ git push: {r.stderr}")
    else:
        print("🚀 Опубликовано на GitHub Pages")


if __name__ == "__main__":
    main()
