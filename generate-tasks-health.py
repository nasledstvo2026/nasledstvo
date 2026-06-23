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
from datetime import datetime, timezone, timedelta
from croniter import croniter

# ═══════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════
DATA_FILE = os.path.join(os.path.dirname(__file__), "tasks-data.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "tasks.html")
WORKSPACE = os.path.dirname(__file__)

# Маппинг: имя cron-задачи (из openclaw cron list) → имя в tasks-data.json
CRON_TO_TASK = {
    "Сводка жалоб: наследство в банках (5 площадок)": "Сводка жалоб — наследство",
    "📊 Обновление статистики жалоб (stats-inheritance)": "Обновление статистики",
    "Ежедневная сводка: наследство и банки": "Дайджест новостей",
    "📋 Роза: сводка изменений в законах по пособиям": "Изменения в законах по пособиям",
    "Ирина: еженедельный обзор НПА": "Обзор НПА",
    "Анализ новостей по вкладам 1991 — понедельник": "Вклады 1991 — понедельник",
    "РЖД 1Р-37R — итоги торгов": "РЖД 1Р-37R — итоги",
    "Анализ новостей по вкладам 1991 — четверг": "Вклады 1991 — четверг",
    "📊 Активность пользователей": "Активность пользователей",
    "Бэкап: полный (раз в неделю)": "Бэкап: полный",
}

# Обратный маппинг: task_name → cron_name
TASK_TO_CRON = {v: k for k, v in CRON_TO_TASK.items()}

MSK_TZ = timezone(timedelta(hours=3))

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


# Цены моделей из openclaw.json (per 1M tokens)
COST_MODELS = {
    "deepseek-chat":      {"input": 0.27, "output": 1.10, "cacheRead": 0.07},
    "deepseek-v4-flash":   {"input": 0.14, "output": 0.28, "cacheRead": 0.028},
    "deepseek-v4-pro":     {"input": 1.74, "output": 3.48, "cacheRead": 0.145},
    "deepseek-reasoner":   {"input": 0.28, "output": 0.42, "cacheRead": 0.028},
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

def compute_period_ms(schedule):
    """Вычисляет период cron-расписания в мс через croniter"""
    expr = schedule.get("expr", "")
    tz_str = schedule.get("tz", "Europe/Moscow")
    if not expr:
        return None
    try:
        from pytz import timezone as pytz_tz
        tz = pytz_tz(tz_str)
    except Exception:
        tz = timezone.utc
    try:
        base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=tz)
        cron = croniter(expr, base)
        t1 = cron.get_next(datetime)
        t2 = cron.get_next(datetime)
        return int((t2 - t1).total_seconds() * 1000)
    except Exception as e:
        print(f"  ⚠️ croniter: {e} для expr={expr}")
        return None


def extract_data_from_stdout(cmd_list):
    """Выполняет команду, вырезает JSON из stdout (до первой '{') и парсит"""
    try:
        r = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        out = r.stdout
        idx = out.find('{')
        if idx < 0:
            return None
        return json.loads(out[idx:])
    except Exception:
        return None


def fetch_gateway_metrics():
    """
    Получает из Gateway актуальные метрики (duration, latency, cache, cost, last_run)
    для всех задач. Возвращает dict {task_name: {key: val}}.
    """
    jobs_data = extract_data_from_stdout(["openclaw", "cron", "list", "--json"])
    if not jobs_data:
        print("⚠️ Не удалось получить список задач из Gateway")
        return {}

    jobs = jobs_data.get("jobs", [])
    cron_map = {j["name"]: j for j in jobs}
    result = {}

    for cron_name, task_name in CRON_TO_TASK.items():
        job = cron_map.get(cron_name)
        if not job:
            print(f"  ⚠️ {cron_name}: задача не найдена в Gateway")
            continue

        state = job.get("state", {})
        payload = job.get("payload", {})
        schedule = job.get("schedule", {})
        job_id = job.get("id", "")

        last_run_ms = state.get("lastRunAtMs")
        last_dur_ms = state.get("lastDurationMs")
        timeout_s = payload.get("timeoutSeconds")
        next_run_ms = state.get("nextRunAtMs")

        metrics = {}

        # ── last_run ──
        if last_run_ms:
            dt = datetime.fromtimestamp(last_run_ms / 1000, tz=timezone.utc).astimezone(MSK_TZ)
            metrics["last_run"] = dt.strftime("%d.%m %H:%M")

        # ── duration_pct ──
        if last_dur_ms is not None and timeout_s and timeout_s > 0:
            metrics["duration_pct"] = round(last_dur_ms / (timeout_s * 1000) * 100)

        # ── latency_min (через croniter) ──
        if last_run_ms and next_run_ms and schedule:
            period_ms = compute_period_ms(schedule)
            if period_ms:
                expected_ms = next_run_ms - period_ms
                lat_min = max(0, (last_run_ms - expected_ms) / 60000)
                metrics["latency_min"] = round(lat_min, 1)

        # ── success_rate (последние 3 запуска) + cache/cost ──
        if job_id:
            runs_data = extract_data_from_stdout(
                ["openclaw", "cron", "runs", "--id", job_id, "--limit", "5"]
            )
            if runs_data:
                entries = runs_data.get("entries", [])
                # SR считаем по последним 3 запускам (любым, не только успешным)
                last_3 = entries[:3]
                if len(last_3) > 0:
                    ok_count = sum(1 for e in last_3 if e.get("status") == "ok")
                    metrics["success_rate"] = round(ok_count / len(last_3) * 100)

                # cache_hit_pct + cost_per_run из последнего успешного run
                for entry in entries:
                    if entry.get("status") != "ok":
                        continue
                    usage = entry.get("usage", {})
                    inp = usage.get("input_tokens", 0)
                    out = usage.get("output_tokens", 0)
                    total = usage.get("total_tokens", 0)
                    if not inp or not total or total < (inp + out):
                        continue  # данные некорректны

                    cache_read = total - inp - out
                    if inp + cache_read > 0:
                        metrics["cache_hit_pct"] = round(cache_read / (inp + cache_read) * 100)

                    # Стоимость: берём модель из run или fallback
                    model = entry.get("model", "deepseek-chat")
                    model_key = model.replace("deepseek/", "")
                    price = COST_MODELS.get(model_key, COST_MODELS["deepseek-chat"])
                    cost = (inp * price["input"] + cache_read * price["cacheRead"] + out * price["output"]) / 1_000_000
                    metrics["cost_per_run"] = round(cost, 4)
                    break  # берём только последний успешный

        print(f"  ✓ {task_name}: SR={metrics.get('success_rate','?')}% dur={metrics.get('duration_pct','?')}% "
              f"lat={metrics.get('latency_min','?')}м "
              f"cache={metrics.get('cache_hit_pct','?')}% "
              f"cost=${metrics.get('cost_per_run','?')} "
              f"last={metrics.get('last_run','?')}")
        result[task_name] = metrics

    return result


def merge_gateway_metrics(tasks, gw_metrics):
    """Обновляет метрики задач из Gateway, сохраняя статичные поля"""
    updated = []
    for t in tasks:
        name = t.get("task", "")
        gw = gw_metrics.get(name, {})
        for key in ("success_rate", "duration_pct", "latency_min", "cache_hit_pct", "cost_per_run", "last_run"):
            if key in gw:
                t[key] = gw[key]
        updated.append(t)
    return updated


def fmt_apply_status(task_name, health_idx):
    """Форматирует статус авто-применения для колонки"""
    if health_idx >= 80:
        return '<span class="stat-na">—</span>'
    try:
        tr = load_tracker()
        entry = tr.get("cycle", {}).get(task_name)
        if not entry or "count" not in entry:
            return '<span class="stat-na">—</span>'
        c = entry["count"]
        if c == 1:
            return '<span style="color:#d29922;font-size:12px;">⏳ 1/2 циклов</span>'
        elif c >= 2:
            return '<span style="color:#58a6ff;font-size:12px;">⚙️ готово к применению</span>'
    except Exception:
        pass
    return '<span class="stat-na">—</span>'


def load_job_map():
    """Загружает маппинг task_name → job_id из Gateway"""
    data = extract_data_from_stdout(["openclaw", "cron", "list", "--json"])
    if not data:
        return {}
    result = {}
    for job in data.get("jobs", []):
        name = job.get("name", "")
        task = CRON_TO_TASK.get(name)
        if task:
            result[task] = job.get("id", "")
    return result


TRACKER_FILE = os.path.join(WORKSPACE, "memory", "rec-tracker.json")


def load_tracker():
    """Загружает трекер повторяющихся рекомендаций"""
    if not os.path.exists(TRACKER_FILE):
        return {"cycle": {}}
    try:
        with open(TRACKER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"cycle": {}}


def save_tracker(tracker):
    """Сохраняет трекер"""
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(tracker, f, ensure_ascii=False, indent=2)


def make_rec_key(metrics):
    """Формирует ключ рекомендации для отслеживания"""
    sr = metrics.get("success_rate", 100)
    dur = metrics.get("duration_pct", 0)
    cost = metrics.get("cost_per_run", None)
    if sr is not None and sr < 90:
        return f"sr-{sr}"
    if dur > 80:
        return f"dur-{dur}"
    if dur < 20:
        return f"dur-low-{dur}"
    if cost is not None and cost > 0.05:
        return f"cost-{cost}"
    return ""


def apply_one_recommendation(task_name, job_map, metrics):
    """Применяет изменение через openclaw cron edit"""
    job_id = job_map.get(task_name)
    if not job_id:
        return None

    sr = metrics.get("success_rate", 100)
    dur = metrics.get("duration_pct", 0)
    cost = metrics.get("cost_per_run", None)
    changes = []

    # 1. Duration > 80% → увеличить таймаут
    if sr is not None and sr >= 90 and dur > 80:
        timeout_s = round(400 * 1.5)  # увеличиваем на 50%
        timeout_s = min(timeout_s, 600)
        cmd = ["openclaw", "cron", "edit", "--id", job_id, "--timeout-seconds", str(timeout_s)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            changes.append(f"timeout→{timeout_s}с")
            print(f"  ⚙️ {task_name}: таймаут увеличен до {timeout_s}с")

    # 2. Duration < 20% → уменьшить таймаут
    if sr is not None and sr >= 90 and dur < 20:
        timeout_s = 120  # уменьшаем до разумного минимума
        cmd = ["openclaw", "cron", "edit", "--id", job_id, "--timeout-seconds", str(timeout_s)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            changes.append(f"timeout→{timeout_s}с")
            print(f"  ⚙️ {task_name}: таймаут уменьшен до {timeout_s}с")

    # 3. Cost > $0.05 со SR >= 90 → flash
    if sr is not None and sr >= 90 and cost is not None and cost > 0.05:
        cmd = ["openclaw", "cron", "edit", "--id", job_id, "--model", "deepseek/deepseek-v4-flash"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            changes.append("model→flash")
            print(f"  ⚙️ {task_name}: модель переключена на flash (было ${cost}/run)")

    return changes if changes else None


def apply_recommendations(tasks, job_map):
    """Проверяет повторяющиеся рекомендации и применяет изменения"""
    tracker = load_tracker()
    cycle_data = tracker.get("cycle", {})
    now = datetime.now().strftime("%H:%M")
    changes_made = []

    for t in tasks:
        name = t["task"]
        health_idx, _ = calc_health(t)
        if health_idx >= 80:
            # Задача зелёная — очищаем трекер
            if name in cycle_data:
                del cycle_data[name]
            continue

        # SR < 90 — не применяем автоизменения
        sr = t.get("success_rate")
        if sr is not None and sr < 90:
            if name in cycle_data:
                del cycle_data[name]
            continue

        key = make_rec_key(t)
        if not key:
            if name in cycle_data:
                del cycle_data[name]
            continue

        prev = cycle_data.get(name, {})
        if prev.get("key") == key:
            count = prev.get("count", 1) + 1
        else:
            count = 1

        cycle_data[name] = {"key": key, "count": count, "updated": now}

        # Применяем на 2-м цикле
        if count >= 2:
            result = apply_one_recommendation(name, job_map, t)
            if result:
                changes_made.append((name, result))
                del cycle_data[name]  # сбрасываем после применения

    tracker["cycle"] = cycle_data
    save_tracker(tracker)
    return changes_made


def generate_recommendation(metrics, health_idx):
    """Генерирует рекомендацию на основе метрик"""
    if health_idx >= 80:
        return '<span style="color:var(--text-dim,#8b949e);">✅ Всё ОК</span>'

    sr = metrics.get("success_rate", 100)
    dur = metrics.get("duration_pct", 0)
    lat = metrics.get("latency_min", 0)
    cache = metrics.get("cache_hit_pct", None)
    cost = metrics.get("cost_per_run", None)

    parts = []

    # Приоритет 1: SR < 90% — главная проблема
    if sr is not None and sr < 90:
        parts.append(f"SR {sr}% — есть ошибки, проверить стабильность")

    # Приоритет 2: остальные метрики (только критичное, если SR в порядке)
    if sr is None or sr >= 90:
        if dur > 80:
            parts.append(f"Duration {dur}% — увеличить таймаут")
        elif dur >= 50:
            parts.append(f"Duration {dur}% — близко к лимиту")
        elif dur < 20:
            parts.append(f"Duration {dur}% — можно уменьшить таймаут")

        if lat > 15:
            parts.append(f"Latency {lat} мин — перенести расписание")

        if cache is not None and cache < 50:
            parts.append(f"Cache {cache}% — низкая эффективность промпта")

        if cost is not None and cost > 0.05:
            parts.append(f"Cost ${cost:.4f} — дорого, рассмотреть Flash")

    if not parts:
        return '<span style="color:var(--text-dim,#8b949e);">✅ Всё ОК</span>'
    return "⚠️ " + ". ".join(parts)


def gen_task_row(t, biz=True):
    """Генерирует строку <tr> для задачи"""
    health_idx, health_color = calc_health(t)
    sr = t["success_rate"]
    dur = t["duration_pct"]
    lat = t["latency_min"]
    cache = t["cache_hit_pct"]
    cost = t["cost_per_run"]

    # Рекомендация на основе метрик
    tip_html = generate_recommendation(t, health_idx)
    apply_html = fmt_apply_status(t["task"], health_idx)

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
            <td style="text-align:center;">{apply_html}</td>
            <td style="text-align:center;">{health_badge(health_idx, health_color)}</td>
          </tr>"""


def gen_tasks_html(tasks):
    biz_rows = []
    srv_rows = []
    for t in tasks:
        if t["task"] in BIZ_TASKS:
            biz_rows.append(gen_task_row(t, biz=True))
        else:
            srv_rows.append(gen_task_row(t, biz=False))

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
    <h2 style="font-size:14px;margin-bottom:10px;color:var(--text,#c9d1d9);">💡 Легенда</h2>
    <table class="legend-table">
      <thead>
        <tr><th>Метрика</th><th style="text-align:center;"><span class="tl tl-green"></span> 🟢</th><th style="text-align:center;"><span class="tl tl-yellow"></span> 🟡</th><th style="text-align:center;"><span class="tl tl-red"></span> 🔴</th><th>Описание</th></tr>
      </thead>
      <tbody>
        <tr><td>⏱ Duration</td><td style="text-align:center;">&lt;50%</td><td style="text-align:center;">50–80%</td><td style="text-align:center;">&gt;80%</td><td>Доля времени от таймаута</td></tr>
        <tr><td>📈 Success Rate</td><td style="text-align:center;">100%</td><td style="text-align:center;">&lt;100%</td><td style="text-align:center;">&lt;90%</td><td>Процент успешных запусков</td></tr>
        <tr><td>📬 Latency</td><td style="text-align:center;">≤1 мин</td><td style="text-align:center;">2–15 мин</td><td style="text-align:center;">&gt;15 мин</td><td>Задержка старта относительно расписания</td></tr>
        <tr><td>💎 Cache Hit</td><td style="text-align:center;">&gt;80%</td><td style="text-align:center;">50–80%</td><td style="text-align:center;">&lt;50%</td><td>cacheRead / (input + cacheRead) × 100</td></tr>
        <tr><td>💰 Cost / Run</td><td style="text-align:center;">&lt;$0.01</td><td style="text-align:center;">$0.01–0.05</td><td style="text-align:center;">&gt;$0.05</td><td>По тарифам модели из openclaw.json</td></tr>
        <tr><td>🩺 Health Index</td><td style="text-align:center;">≥80</td><td style="text-align:center;">50–79</td><td style="text-align:center;">&lt;50</td><td>SR×30% + Dur×25% + Lat×20% + Cache×15% + Cost×10%. Hard Stop: SR&lt;90% → 0</td></tr>
      </tbody>
    </table>
  </div>

  <!-- ═══════════════════════════════════════════════════ -->
  <!-- ОПИСАНИЕ СИСТЕМЫ -->
  <!-- ═══════════════════════════════════════════════════ -->
  <div class="section" style="padding:16px 20px;background:rgba(33,38,45,.3);border-radius:10px;margin-bottom:16px;">
    <h2 style="font-size:14px;margin-bottom:10px;color:var(--text,#c9d1d9);">🔧 Как это работает</h2>
    <ul style="margin:0;padding:0 0 0 18px;font-size:12.5px;line-height:1.7;color:var(--text-dim,#8b949e);">
      <li><b style="color:var(--text,#c9d1d9);">Метрики</b> — все значения (Duration, Latency, Cache, Cost, SR) рассчитываются автоматически из Gateway при каждом обновлении (каждые 3ч)</li>
      <li><b style="color:var(--text,#c9d1d9);">🩺 Health Index</b> — SR×30% + Duration×25% + Latency×20% + Cache×15% + Cost×10%. Hard Stop: SR&lt;90% → 0</li>
      <li><b style="color:var(--text,#c9d1d9);">💡 Рекомендации</b> — генерируются автоматически по текущим метрикам. Если SR &lt; 90% — рекомендация только про ошибки. Если SR в порядке — анализируются остальные метрики</li>
      <li><b style="color:var(--text,#c9d1d9);">⚙️ Авто-применение</b> — если рекомендация повторяется 2 цикла подряд (6ч), скрипт сам меняет конфигурацию: увеличивает/уменьшает таймаут при перегрузке/недогрузке, переключает дорогие задачи на flash-модель</li>
      <li><b style="color:var(--text,#c9d1d9);">🔒 Безопасность</b> — задачи с SR &lt; 90% исключены из авто-применения. Сначала стабильность, потом оптимизация</li>
      <li><b style="color:var(--text,#c9d1d9);">💡 Колонка «Проработка»</b> — наследие старого оптимизатора (отключён). Не используется</li>
    </ul>
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
            <th class="col-metric col-apply">⚙️ Авто-прим.</th>
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
            <th class="col-metric col-apply">⚙️ Авто-прим.</th>
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
.col-apply {{ min-width: 80px; }}
.stat-na {{ color: var(--text-dim,#8b949e); font-size: 12px; }}
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
.legend-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; line-height: 1.6; }}
.legend-table th {{ text-align: left; padding: 6px 8px; background: rgba(33,38,45,.5); border-bottom: 1px solid var(--glass-border,#21262d); color: var(--text-dim,#8b949e); font-weight: 600; font-size: 11px; white-space: nowrap; }}
.legend-table td {{ padding: 5px 8px; border-bottom: 1px solid rgba(33,38,45,.3); color: var(--text-dim,#8b949e); font-size: 12px; }}
.legend-table td:first-child {{ color: var(--text,#c9d1d9); font-weight: 500; white-space: nowrap; }}
.legend-table td:last-child {{ font-size: 11.5px; color: var(--text-dim-dim,#6e7681); }}
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

    print("📡 Получаю метрики из Gateway (duration, latency, cache, cost)...")
    gw_metrics = fetch_gateway_metrics()
    if gw_metrics:
        tasks = merge_gateway_metrics(tasks, gw_metrics)
        print(f"✅ Обновлено {len(gw_metrics)} задач из Gateway")
    else:
        print("⚠️ Gateway недоступен — метрики остаются из tasks-data.json")

    # Сохраняем обновлённые данные обратно в JSON
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    print("💾 tasks-data.json сохранён с актуальными метриками")

    html = gen_tasks_html(tasks)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ tasks.html сгенерирован — {len(tasks)} задач")

    # Применение рекомендаций (по 2+ циклам)
    print("🔧 Проверяю рекомендации для авто-применения...")
    job_map = load_job_map()
    if job_map:
        changes = apply_recommendations(tasks, job_map)
        if changes:
            for name, chgs in changes:
                print(f"  ✓ {name}: применено {', '.join(chgs)}")
        else:
            print("  Нет изменений")
    else:
        print("  ⚠️ Не удалось загрузить job_map")

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
