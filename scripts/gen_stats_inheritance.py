#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генерация reports/stats-inheritance.html из katya-summary-7d.json (только чтение)."""
import json, html, datetime, os

BASE = "/home/user1/.openclaw/agents/shared/katya-summary-7d.json"
OUT = "/home/user1/.openclaw/workspace/reports/stats-inheritance.html"
MODEL = "deepseek/deepseek-v4-flash"

d = json.load(open(BASE, encoding="utf-8"))
base = d["base"]
win = d["window"]

now = datetime.datetime.now().astimezone()
run_str = now.strftime("%d.%m.%Y %H:%M")

e = lambda s: html.escape(str(s if s is not None else ""))

def bar(val, mx, cls, w=220):
    px = max(4, round(val / mx * w)) if mx else 4
    return ('<td style="width:100%"><span class="bar-track">'
            f'<span class="bar-fill {cls}" style="width:{px}px"></span></span></td>')

# ── 2. Топ-10 банков ────────────────────────────────────────────
by_bank = base["byBank"]
unknown = by_bank.get("не определён", 0)
banks = sorted([(k, v) for k, v in by_bank.items() if k != "не определён"],
               key=lambda x: (-x[1], x[0]))
top10 = banks[:10]
bank_rows = []
mx = top10[0][1] if top10 else 1
for k, v in top10:
    bank_rows.append(f'<tr><td>{e(k)}</td>{bar(v, mx, "bar-other")}<td class="cnt">{v}</td></tr>')
if unknown:
    bank_rows.append(f'<tr><td>не определён</td>{bar(unknown, max(mx, unknown), "bar-src")}'
                     f'<td class="cnt">{unknown}</td></tr>')
bank_rows = "\n".join(bank_rows)

# ── 3. Динамика по месяцам ─────────────────────────────────────
months = sorted(base["byMonth"].items())
mmx = max([v for _, v in months], default=1)
month_rows = "\n".join(
    f'<tr><td>{e(m)}</td>{bar(v, mmx, "bar-month")}<td class="cnt">{v}</td></tr>'
    for m, v in months)

# ── 4. Источники ───────────────────────────────────────────────
sources = sorted(base["bySource"].items(), key=lambda x: (-x[1], x[0]))
smx = sources[0][1] if sources else 1
tot = base["total"] or 1
src_rows = "\n".join(
    f'<tr><td>{e(s)}</td>{bar(v, smx, "bar-src")}'
    f'<td class="cnt">{v} · {v / tot * 100:.1f}%</td></tr>'
    for s, v in sources)

# ── 5. Окно 7 дней ─────────────────────────────────────────────
if win.get("total", 0) == 0:
    window_html = ('<p class="sub-note"><b>За окно (7 дней) новых жалоб нет.</b> '
                   'Общая статистика по базе при этом не обнуляется — '
                   f'в базе по-прежнему <b>{base["total"]}</b> записей.</p>')
else:
    wb = sorted(win.get("byBank", {}).items(), key=lambda x: (-x[1], x[0]))
    wby = "".join(
        f'<tr><td>{"Без банка" if k == "не определён" else e(k)}</td>'
        f'{bar(v, max([x[1] for x in wb] or [1]), "bar-src")}'
        f'<td class="cnt">{v}</td></tr>'
        for k, v in wb)
    wd = sorted(win.get("byDate", {}).items())
    wd_rows = "".join(
        f'<tr><td>{e(k)}</td>{bar(v, max([x[1] for x in wd] or [1]), "bar-month")}'
        f'<td class="cnt">{v}</td></tr>'
        for k, v in wd)
    entries = []
    for it in win.get("entries", []):
        bank = it.get("bank") or "банк не назван"
        v = it.get("verification")
        badge_cls = "badge-green" if v == "verified" else "badge-yellow"
        badge_txt = "проверено" if v == "verified" else "на проверку"
        url = it.get("url") or ""
        note = it.get("note") or ""
        entries.append(
            '<li>'
            f'<div class="e-title">{e(it.get("title"))}</div>'
            f'<div class="e-meta">{e(it.get("date") or "дата не указана")} · {e(bank)} · '
            f'{e(it.get("source"))} <span class="badge {badge_cls}">{badge_txt}</span></div>'
            f'<div class="e-desc">{e(it.get("description"))}</div>'
            + (f'<div class="e-desc" style="margin-top:6px"><i>{e(note)}</i></div>' if note else "")
            + (f'<div style="margin-top:8px"><a href="{e(url)}">{e(url)}</a></div>' if url else "")
            + '</li>')
    window_html = (
        '<div class="stat-card"><div class="num">%d</div><div class="lbl">жалоб за 7 дней</div></div>'
        '<div class="stat-card"><div class="num">%d</div><div class="lbl">verified</div></div>'
        '<div class="stat-card"><div class="num">%d</div><div class="lbl">needs_review</div></div>'
        '<p class="sub-note">Окно: <b>%s</b> — <b>%s</b></p>'
        '<h3 style="font-size:15px;margin:18px 0 8px">По банкам (за окно)</h3>'
        '<table class="bars">%s</table>'
        '<h3 style="font-size:15px;margin:18px 0 8px">По датам (за окно)</h3>'
        '<table class="bars">%s</table>'
        '<h3 style="font-size:15px;margin:18px 0 8px">Новые жалобы (за окно)</h3>'
        '<ul class="entry-list">%s</ul>'
    ) % (win["total"], win.get("totalVerified", 0), win.get("totalNeedsReview", 0),
         e(d.get("dateFrom")), e(d.get("dateTo")), wby, wd_rows, "".join(entries))

HTML = f'''<!DOCTYPE html>
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
    .stat-card {{ display:inline-block; min-width:150px; margin:6px 8px 6px 0; padding:16px 18px; border-radius:14px; background:var(--glass-bg); border:1px solid var(--glass-border); }}
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
    <p class="sub-note">Автоматический отчёт stats-agent · {run_str} (МСК) · Модель: {MODEL}</p>

    <section class="section">
      <h2>1. Общая статистика по всей базе</h2>
      <div class="stat-card"><div class="num">{base["total"]}</div><div class="lbl">всего жалоб</div></div>
      <div class="stat-card"><div class="num">{base.get("totalVerified", 0)}</div><div class="lbl">verified</div></div>
      <div class="stat-card"><div class="num">{base.get("totalNeedsReview", 0)}</div><div class="lbl">needs_review</div></div>
      <p class="sub-note">Период: <b>{e(base["firstDate"])}</b> — <b>{e(base["lastDate"])}</b> ·
      источников: {len(base["bySource"])} · банков (с «не определён»): {len(by_bank)} ·
      без даты: {base.get("withoutDate", 0)}</p>
    </section>

    <section class="section">
      <h2>2. Топ-10 банков (по всей базе)</h2>
      <table class="bars">
{bank_rows}
      </table>
      <p class="sub-note">«не определён» — жалобы, где банк не указан в тексте/сниппете
      (показан отдельной строкой, в топ-10 не входит).</p>
    </section>

    <section class="section">
      <h2>3. Динамика по месяцам</h2>
      <table class="bars">
{month_rows}
      </table>
    </section>

    <section class="section">
      <h2>4. Источники</h2>
      <table class="bars">
{src_rows}
      </table>
    </section>

    <section class="section">
      <h2>5. За последние 7 дней</h2>
{window_html}
    </section>

    <section class="section">
      <h2>6. Мета</h2>
      <p class="sub-note">
        Дата/время запуска: <b>{run_str} (МСК)</b><br>
        Модель: <b>{MODEL}</b><br>
        Всего записей в базе: <b>{base["total"]}</b><br>
        Версия агрегата: {e(d.get("generatedAt"))} · окно {e(d.get("dateFrom"))} — {e(d.get("dateTo"))}
      </p>
    </section>

    <div class="footer">Отчёт сгенерирован автоматически (stats-agent). Данные: katya-data.json</div>
  </div>
</body>
</html>
'''

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print("OK:", OUT, len(HTML), "bytes")
