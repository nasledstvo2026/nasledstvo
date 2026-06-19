#!/usr/bin/env python3
"""Генерация HTML-дашборда статистики OpenClaw (glass-morphism дизайн)."""
import json, datetime, subprocess, os

now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3)))
date_str = now.strftime('%d.%m.%Y %H:%M МСК')
today_str = now.strftime('%d.%m.%Y')

with open('/tmp/_usage_status.json') as f: us = json.load(f)
with open('/tmp/_usage_cost.json') as f: uc = json.load(f)
with open('/tmp/_status.json') as f: st = json.load(f)

us_p = us.get('payload', {})
uc_p = uc.get('payload', {})
st_p = st.get('payload', {})

# --- Providers (API + manual deepseek) ---
providers_html = ""
for p in us_p.get('providers', []):
    name = p.get('displayName', p.get('provider', '?'))
    windows_html = ""
    for w in p.get('windows', []):
        label = w['label']
        pct = w['usedPercent']
        if 'resetAt' in w and w['resetAt']:
            reset = datetime.datetime.fromtimestamp(w['resetAt']/1000, tz=datetime.timezone(datetime.timedelta(hours=3)))
            reset_str = reset.strftime('%d.%m %H:%M')
        else:
            reset_str = '—'
        color = 'green' if pct < 50 else 'yellow' if pct < 80 else 'red'
        windows_html += f"""
        <div class="item">
          <p class="title">{label} — <span class="sentiment {color}">{pct}%</span></p>
          <div style="background:rgba(255,255,255,.06);border-radius:6px;height:8px;overflow:hidden;margin:8px 0">
            <div style="height:100%;width:{pct}%;background:var(--{'green' if pct < 50 else 'yellow' if pct < 80 else 'red'});border-radius:6px"></div>
          </div>
          <p class="meta">Сброс: {reset_str}</p>
        </div>"""
    providers_html += f"""
  <div class="section">
    <span class="tag blue">🔌 {name}</span>
    {windows_html}
  </div>"""

# DeepSeek — считаем runs за сегодня
providers_html += """
  <div class="section">
    <span class="tag green">🔌 DeepSeek (API directa)</span>
    <div class="highlight green"><p>Подключён через cron-задачи. Лимиты отслеживаются на platform.deepseek.com.</p></div>
  </div>"""

# --- Tasks table per cron job ---
# Read cron jobs list
cron_data = {}
try:
    cron_file = '/home/user1/.openclaw/cron/jobs.json'
    with open(cron_file) as f:
        cron_data = json.load(f)
except Exception:
    pass

jobs = cron_data if isinstance(cron_data, list) else cron_data.get('jobs', [])

def fmt_time(ms):
    if not ms:
        return '—'
    dt = datetime.datetime.fromtimestamp(ms/1000, tz=datetime.timezone(datetime.timedelta(hours=3)))
    return dt.strftime('%H:%M:%S')

def fmt_date(ms):
    if not ms:
        return '—'
    dt = datetime.datetime.fromtimestamp(ms/1000, tz=datetime.timezone(datetime.timedelta(hours=3)))
    return dt.strftime('%d.%m %H:%M')

def fmt_duration(ms):
    if not ms:
        return '—'
    s = ms / 1000
    if s < 60:
        return f'{s:.0f}с'
    return f'{s/60:.1f}м'

rows_html = ""
for j in jobs:
    name = j.get('name', '?')
    schedule = j.get('schedule', {})
    expr = schedule.get('expr', '—')
    state = j.get('state', {})
    last_status = state.get('lastRunStatus', '—')
    last_run = fmt_date(state.get('lastRunAtMs'))
    duration = fmt_duration(state.get('lastDurationMs'))
    errors = state.get('consecutiveErrors', 0)
    next_run = fmt_date(state.get('nextRunAtMs'))
    enabled = '✅' if j.get('enabled', True) else '⏸️'

    if last_status == 'ok':
        status_html = '<span class="sentiment positive">✅ ok</span>'
    elif last_status == 'error':
        diag = state.get('lastDiagnosticSummary', '')
        status_html = f'<span class="sentiment negative">❌ ошибка</span>'
        if diag:
            status_html += f'<br><span style="font-size:11px;color:var(--text-faint)">{diag[:80]}</span>'
    else:
        status_html = '—'

    model = j.get('payload', {}).get('model', 'default')
    model_short = model.split('/')[-1] if '/' in model else model

    rows_html += f"""
      <tr>
        <td>{enabled}</td>
        <td><strong>{name}</strong><br><span style="font-size:11px;color:var(--text-faint)">{expr} · {model_short}</span></td>
        <td>{last_run}</td>
        <td>{duration}</td>
        <td>{status_html}</td>
        <td>{next_run}</td>
      </tr>"""

tasks_section = f"""
  <div class="section">
    <span class="tag green">📋 Задачи — {today_str}</span>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Задача</th>
            <th>Последний запуск</th>
            <th>Время</th>
            <th>Статус</th>
            <th>Следующий</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </div>"""

# --- Cost ---
t = uc_p.get('totals', {})
cost_section = f"""
  <div class="section">
    <span class="tag purple">💰 Токены и стоимость</span>
    <div class="stats-row">
      <div class="stat-box">
        <div class="value">{t.get('input',0):,}</div>
        <div class="label">Входящие</div>
      </div>
      <div class="stat-box">
        <div class="value">{t.get('output',0):,}</div>
        <div class="label">Исходящие</div>
      </div>
      <div class="stat-box">
        <div class="value">{t.get('cacheRead',0):,}</div>
        <div class="label">Кэш чтение</div>
      </div>
      <div class="stat-box">
        <div class="value">${t.get('totalCost',0):.4f}</div>
        <div class="label">Итого $</div>
      </div>
    </div>
  </div>"""

# --- Daily chart ---
daily = uc_p.get('daily', [])
chart_html = ""
if daily:
    max_cost = max((d.get('totalCost', 0) for d in daily if isinstance(d.get('totalCost', 0), (int, float))), default=1) or 1
    bars = ""
    for d in daily[-14:]:
        date_val = d.get('date', 0)
        try:
            if isinstance(date_val, str):
                dt = datetime.datetime.strptime(date_val[:10], '%Y-%m-%d').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
            elif isinstance(date_val, (int, float)) and date_val > 0:
                dt = datetime.datetime.fromtimestamp(date_val / 1000, tz=datetime.timezone(datetime.timedelta(hours=3)))
            else:
                continue
        except Exception:
            continue
        day_label = dt.strftime('%d.%m')
        cost = d.get('totalCost', 0) if isinstance(d.get('totalCost', 0), (int, float)) else 0
        height = max(2, round(cost / max_cost * 100))
        bars += f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%"><div style="width:100%;max-width:36px;height:{height}px;background:var(--blue);border-radius:4px 4px 0 0;min-height:2px" title="${cost:.4f}"></div><div style="font-size:10px;color:var(--text-faint);margin-top:4px;white-space:nowrap">{day_label}</div></div>'
    chart_html = f"""
  <div class="section">
    <span class="tag purple">📈 Расход по дням</span>
    <div style="display:flex;align-items:flex-end;gap:4px;height:140px;padding-top:20px">
      {bars}
    </div>
  </div>"""

# --- Sessions ---
sessions = st_p.get('sessions', {})
version = st_p.get('runtimeVersion', '?')

html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📊 OpenClaw — Статистика</title>
<link rel="stylesheet" href="theme.css">
</head>
<body>

<div class="container">
  <a href="index.html" class="back">← Назад</a>

  <div class="hero">
    <h1>📊 OpenClaw — Статистика</h1>
    <p class="sub">Мониторинг расхода токенов, стоимости и задач</p>
    <p class="date">Обновлено: {date_str} · v{version}</p>
  </div>

  {providers_html}

  {cost_section}

  {chart_html}

  {tasks_section}

  <div class="section">
    <span class="tag blue">💬 Сессии</span>
    <div class="stats-row">
      <div class="stat-box">
        <div class="value">{sessions.get('count',0)}</div>
        <div class="label">Всего</div>
      </div>
    </div>
  </div>

  <div class="footer"><strong>☽ ЛУНТ</strong> · Автообновление: 5 мин · <a href="index.html">nasledstvo.net.ru</a></div>
</div>

<meta http-equiv="refresh" content="300">
</body>
</html>"""

with open('/tmp/stats-dashboard.html', 'w') as f:
    f.write(html)
