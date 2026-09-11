#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stats-agent: генерация reports/stats-inheritance.html из katya-summary-7d.json (только чтение)."""
import json, html, datetime, os

SHARED = "/home/user1/.openclaw/agents/shared"
OUT = "/home/user1/.openclaw/workspace/reports/stats-inheritance.html"
MODEL = "deepseek/deepseek-v4-flash"

d = json.load(open(os.path.join(SHARED, "katya-summary-7d.json"), encoding="utf-8"))
base = d["base"]
win = d["window"]
gen = d.get("generatedAt", "")
now = datetime.datetime.now().astimezone()
stamp = now.strftime("%d.%m.%Y %H:%M")

def esc(s):
    return html.escape(str(s if s is not None else ""))

def bar(cnt, maxv, cls):
    w = max(4, round(cnt / maxv * 220)) if maxv else 4
    return (f'<tr><td>{esc()}</td></tr>')

# --- 2. Топ-10 банков (без «не определён») ---
banks = base.get("byBank", {})
undef = banks.get("не определён", 0)
ranked = sorted([(k, v) for k, v in banks.items() if k != "не определён"], key=lambda x: -x[1])
top = ranked[:10]
maxb = max([v for _, v in top] + [1])
rows_bank = "".join(
    f'<tr><td>{esc(k)}</td><td style="width:100%"><span class="bar-track">'
    f'<span class="bar-fill bar-other" style="width:{max(4, round(v/maxb*220))}px"></span></span></td>'
    f'<td class="cnt">{v}</td></tr>' for k, v in top)

# --- 3. Месяцы ---
months = base.get("byMonth", {})
mmax = max(months.values()) if months else 1
rows_month = "".join(
    f'<tr><td>{esc(m)}</td><td style="width:100%"><span class="bar-track">'
    f'<span class="bar-fill bar-month" style="width:{max(4, round(v/mmax*220))}px"></span></span></td>'
    f'<td class="cnt">{v}</td></tr>' for m, v in sorted(months.items()))

# --- 4. Источники ---
sources = base.get("bySource", {})
smax = max(sources.values()) if sources else 1
btotal = base.get("total", 0) or 1
rows_src = "".join(
    f'<tr><td>{esc(s)}</td><td style="width:100%"><span class="bar-track">'
    f'<span class="bar-fill bar-src" style="width:{max(4, round(v/smax*220))}px"></span></span></td>'
    f'<td class="cnt">{v} · {v/btotal*100:.1f}%</td></tr>' for s, v in sorted(sources.items(), key=lambda x: -x[1]))

# --- 5. Окно 7 дней ---
wtot = win.get("total", 0)
if wtot:
    wbanks = win.get("byBank", {})
    wmax = max(wbanks.values()) if wbanks else 1
    rows_wbank = "".join(
        f'<tr><td>{esc(k)}</td><td style="width:100%"><span class="bar-track">'
        f'<span class="bar-fill bar-other" style="width:{max(4, round(v/wmax*220))}px"></span></span></td>'
        f'<td class="cnt">{v}</td></tr>' for k, v in sorted(wbanks.items(), key=lambda x: -x[1]))
    wdates = win.get("byDate", {})
    dmax = max(wdates.values()) if wdates else 1
    rows_wdate = "".join(
        f'<tr><td>{esc(k)}</td><td style="width:100%"><span class="bar-track">'
        f'<span class="bar-fill bar-month" style="width:{max(4, round(v/dmax*220))}px"></span></span></td>'
        f'<td class="cnt">{v}</td></tr>' for k, v in sorted(wdates.items()))
    entries = ""
    for e in win.get("entries", []):
        bank = e.get("bank") or "не определён"
        ver = e.get("verification") or "needs_review"
        badge = "badge-green" if ver == "verified" else "badge-yellow"
        entries += (
            f'<li><div class="e-title">{esc(e.get("title"))}</div>'
            f'<div class="e-meta">{esc(e.get("date"))} · {esc(bank)} · {esc(e.get("source"))} · '
            f'<span class="badge {badge}">{esc(ver)}</span></div>'
            f'<div class="e-desc">{esc(e.get("description"))}</div>'
            f'<a href="{esc(e.get("url"))}">{esc(e.get("url"))}</a></li>')
    window_body = (
        f'<div class="stat-card"><div class="num">{wtot}</div><div class="lbl">жалоб за 7 дней</div></div>'
        f'<div class="stat-card"><div class="num">{win.get("totalVerified",0)}</div><div class="lbl">verified</div></div>'
        f'<div class="stat-card"><div class="num">{win.get("totalNeedsReview",0)}</div><div class="lbl">needs_review</div></div>'
        f'<p class="sub-note">Окно: <b>{esc(d.get("dateFrom"))}</b> — <b>{esc(d.get("dateTo"))}</b></p>'
        f'<h3>По банкам</h3><table class="bars">{rows_wbank}</table>'
        f'<h3>По датам</h3><table class="bars">{rows_wdate}</table>'
        f'<h3>Записи</h3><ul class="entry-list">{entries}</ul>')
else:
    window_body = ('<p class="sub-note"><b>За окно (7 дней) новых жалоб нет.</b> '
                   'Общая статистика по базе ниже/выше не обнуляется.</p>')

bank_count = len(banks)
src_count = len(sources)

doc = f'''<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Статистика жалоб — Наследство в банках РФ</title>
  <link rel="stylesheet" href="theme.css">
  <style>
    .bar-fill {{ display:inline-block; height:20px; border-radius:4px; min-width:4px; }}
    .bar-other  {{ background: linear-gradient(90deg,#7ee787,#56d4dd); }}
    .bar-src    {{ background: linear-gradient(90deg,#d2a8ff,#8957e5); }}
    .bar-month  {{ background: linear-gradient(90deg,#ffa657,#f0883e); }}
    .sub-note {{ font-size:12px; color:var(--text-dim); margin-top:8px; line-height:1.6; }}
    .entry-list {{ list-style:none; margin:0; padding:0; }}
    .entry-list li {{ padding:12px 14px; border-radius:10px; background:var(--glass-bg); border:1px solid var(--glass-border); margin-bottom:10px; }}
    .entry-list .e-title {{ font-weight:600; color:var(--text); font-size:14px; }}
    .entry-list .e-meta {{ font-size:12px; color:var(--text-dim); margin:4px 0 6px; }}
    .entry-list .e-desc {{ font-size:13px; color:var(--text-dim); line-height:1.55; }}
    .entry-list a {{ color:var(--blue); text-decoration:none; font-size:12px; word-break:break-all; }}
    .stat-card {{ display:inline-block; min-width:160px; margin:6px 8px 6px 0; padding:16px 18px; border-radius:14px; background:var(--glass-bg); border:1px solid var(--glass-border); }}
    .stat-card .num {{ font-size:30px; font-weight:800; line-height:1.1; }}
    .stat-card .lbl {{ font-size:12px; color:var(--text-dim); margin-top:4px; }}
    .badge {{ display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600; margin-left:6px; }}
    .badge-green {{ background:rgba(126,231,135,.15); color:var(--green); }}
    .badge-yellow {{ background:rgba(210,153,34,.15); color:var(--yellow); }}
    table.bars {{ width:100%; border-collapse:collapse; font-size:13px; }}
    table.bars td {{ padding:3px 6px; vertical-align:middle; }}
    table.bars tr td:first-child {{ white-space:nowrap; color:var(--text); }}
    .bar-track {{ background:var(--glass-border); border-radius:4px; height:20px; width:100%; min-width:120px; display:block; }}
    .cnt {{ text-align:right; font-weight:600; color:var(--text); white-space:nowrap; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>📊 Статистика жалоб: наследство в банках РФ</h1>
    <p class="sub-note">Автоматический отчёт stats-agent · {stamp} (МСК) · Модель: {MODEL}</p>

    <section class="card">
      <h2>1. Общая статистика по всей базе</h2>
      <div class="stat-card"><div class="num">{base.get("total",0)}</div><div class="lbl">всего жалоб</div></div>
      <div class="stat-card"><div class="num">{base.get("totalVerified",0)}</div><div class="lbl">verified</div></div>
      <div class="stat-card"><div class="num">{base.get("totalNeedsReview",0)}</div><div class="lbl">needs_review</div></div>
      <p class="sub-note">Период: <b>{esc(base.get("firstDate"))}</b> — <b>{esc(base.get("lastDate"))}</b> ·
      источников: {src_count} · банков (с «не определён»): {bank_count}</p>
    </section>

    <section class="card">
      <h2>2. Топ-10 банков (по всей базе)</h2>
      <table class="bars">
{rows_bank}
        <tr><td>не определён</td><td style="width:100%"><span class="bar-track"><span class="bar-fill bar-src" style="width:{max(4, round(undef/maxb*220))}px"></span></span></td><td class="cnt">{undef}</td></tr>
      </table>
      <p class="sub-note">«не определён» — жалобы, где банк не указан в тексте/сниппете (показан отдельной строкой, в топ-10 не входит).</p>
    </section>

    <section class="card">
      <h2>3. Динамика по месяцам</h2>
      <table class="bars">
{rows_month}
      </table>
    </section>

    <section class="card">
      <h2>4. Источники</h2>
      <table class="bars">
{rows_src}
      </table>
    </section>

    <section class="card">
      <h2>5. За последние 7 дней</h2>
{window_body}
    </section>

    <section class="card">
      <h2>6. Мета</h2>
      <p class="sub-note">
        Дата/время запуска: <b>{stamp} (МСК)</b><br>
        Модель: {MODEL}<br>
        Всего записей в базе: <b>{base.get("total",0)}</b><br>
        Версия агрегата: {esc(gen)}
      </p>
    </section>
  </div>
</body>
</html>
'''

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(doc)
print(f"OK: {OUT} ({len(doc)} bytes)")
print(f"base.total={base.get('total')} top3={[k for k,_ in ranked[:3]]} window.total={wtot}")
