#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stats-agent: генерация reports/stats-inheritance.html из katya-summary-7d.json.
Не пишет в базы — только читает агрегаты."""
import json, html, os, subprocess
from datetime import datetime

SHARED = "/home/user1/.openclaw/agents/shared"
SUMMARY = os.path.join(SHARED, "katya-summary-7d.json")
OUT = "/home/user1/.openclaw/workspace/reports/stats-inheritance.html"
MODEL = "deepseek/deepseek-v4-flash"
MAXPX = 220

d = json.load(open(SUMMARY, encoding="utf-8"))
base = d["base"]
win = d["window"]
byBank = base.get("byBank", {})
byMonth = base.get("byMonth", {})
bySource = base.get("bySource", {})
total = base.get("total", 0)
verified = base.get("totalVerified", 0)
needs = base.get("totalNeedsReview", 0)

now = datetime.now().strftime("%d.%m.%Y %H:%M")
e = html.escape


def bar(label, count, mx, cls, suffix=""):
    w = max(4, int(round(count / mx * MAXPX))) if mx else 4
    cnt = f"{count}{suffix}"
    return (f'<tr><td>{e(label)}</td><td style="width:100%"><span class="bar-track">'
            f'<span class="bar-fill {cls}" style="width:{w}px"></span></span></td>'
            f'<td class="cnt">{e(cnt)}</td></tr>')


# --- 2. Топ-10 банков -------------------------------------------------------
unknown = byBank.get("не определён", 0)
real = {k: v for k, v in byBank.items() if k != "не определён"}
real_sorted = sorted(real.items(), key=lambda x: (-x[1], x[0]))
top10 = real_sorted[:10]
others = real_sorted[10:]
others_sum = sum(v for _, v in others)
mxb = top10[0][1] if top10 else 1
bank_rows = "".join(bar(k, v, mxb, "bar-other") for k, v in top10)
if unknown:
    bank_rows += bar("не определён", unknown, max(mxb, unknown), "bar-src")

# --- 3. Месяцы --------------------------------------------------------------
months = sorted(byMonth.items())
mxm = max(v for _, v in months) if months else 1
month_rows = "".join(bar(k, v, mxm, "bar-month") for k, v in months)
max_month = max(months, key=lambda x: x[1]) if months else ("—", 0)
last_month = months[-1] if months else ("—", 0)

# --- 4. Источники ----------------------------------------------------------
src_sorted = sorted(bySource.items(), key=lambda x: (-x[1], x[0]))
mxs = src_sorted[0][1] if src_sorted else 1
src_rows = ""
for k, v in src_sorted:
    pct = (v / total * 100) if total else 0
    src_rows += bar(k, v, mxs, "bar-src", suffix=f" · {pct:.1f}%")

# --- 5. Окно 7 дней --------------------------------------------------------
wt = win.get("total", 0)
if wt:
    wb = win.get("byBank", {})
    wb_sorted = sorted(wb.items(), key=lambda x: (-x[1], x[0]))
    mw = wb_sorted[0][1] if wb_sorted else 1
    wbank_rows = "".join(
        bar("Без банка" if k in ("не определён", None, "") else k, v, mw, "bar-src")
        for k, v in wb_sorted)
    wd = sorted(win.get("byDate", {}).items())
    mwd = max(v for _, v in wd) if wd else 1
    wdate_rows = "".join(bar(k, v, mwd, "bar-month") for k, v in wd)
    wsrc = win.get("bySource", {})
    wsrc_txt = ", ".join(f"{e(k)} ({v})" for k, v in
                         sorted(wsrc.items(), key=lambda x: -x[1])) or "—"
    items = ""
    for it in win.get("entries", []):
        v = it.get("verification") or "needs_review"
        badge = ('<span class="badge badge-green">проверено</span>' if v == "verified"
                 else '<span class="badge badge-yellow">на проверку</span>')
        bank = it.get("bank") or "банк не назван"
        desc = e(it.get("description") or "")
        note = it.get("verification_note")
        note_html = (f'<div class="e-desc" style="margin-top:6px"><i>{e(note)}</i></div>'
                     if note else "")
        url = e(it.get("url") or "#")
        title = e(it.get("title") or "(без заголовка)")
        items += (f'<li><div class="e-title">{title}</div>'
                  f'<div class="e-meta">{e(it.get("date") or "—")} · {e(bank)} · '
                  f'{e(it.get("source") or "—")} {badge}</div>'
                  f'<div class="e-desc">{desc}</div>{note_html}'
                  f'<div style="margin-top:8px"><a href="{url}">{url}</a></div></li>')
    window_html = (
        f'<div class="stat-card"><div class="num">{wt}</div><div class="lbl">жалоб за 7 дней</div></div>'
        f'<div class="stat-card"><div class="num">{win.get("totalVerified",0)}</div>'
        f'<div class="lbl">verified</div></div>'
        f'<div class="stat-card"><div class="num">{win.get("totalNeedsReview",0)}</div>'
        f'<div class="lbl">needs_review</div></div>'
        f'<p class="sub-note">Окно: <b>{e(str(d.get("dateFrom")))}</b> — '
        f'<b>{e(str(d.get("dateTo")))}</b> · источники за окно: {wsrc_txt}</p>'
        f'<h3>По банкам (за окно)</h3><table class="bars">{wbank_rows}</table>'
        f'<h3>По датам (за окно)</h3><table class="bars">{wdate_rows}</table>'
        f'<h3>Новые жалобы (за окно)</h3><ul class="entry-list">{items}</ul>')
else:
    window_html = (f'<p class="sub-note">Окно: <b>{e(str(d.get("dateFrom")))}</b> — '
                   f'<b>{e(str(d.get("dateTo")))}</b>.<br><b>За окно новых жалоб нет.</b> '
                   f'Общая статистика по всей базе выше не обнуляется.</p>')

bank_others_note = (
    f'«не определён» — жалобы, где банк не указан в тексте/сниппете (показан отдельной '
    f'строкой, в топ-10 не входит). Прочие банки за пределами топ-10: {others_sum} жалоб '
    f'(всего банков вне «не определён»: {len(real)}).')

doc = f"""<!DOCTYPE html>
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
    h3 {{ font-size:15px; margin:18px 0 8px; color:var(--text); }}
  </style>
</head>
<body>
  <div class="container">
    <h1>📊 Статистика жалоб: наследство в банках РФ</h1>
    <p class="sub-note">Автоматический отчёт stats-agent · {now} (МСК) · Модель: {MODEL}</p>
    <section class="section">
      <h2>1. Общая статистика по всей базе</h2>
      <div class="stat-card"><div class="num">{total}</div><div class="lbl">всего жалоб</div></div>
      <div class="stat-card"><div class="num">{verified}</div><div class="lbl">verified</div></div>
      <div class="stat-card"><div class="num">{needs}</div><div class="lbl">needs_review</div></div>
      <p class="sub-note">Период: <b>{e(str(base.get("firstDate")))}</b> — <b>{e(str(base.get("lastDate")))}</b> ·
      источников: {len(bySource)} · банков (с «не определён»): {len(byBank)} ·
      без даты: {base.get("withoutDate", 0)} ·
      доля verified: {(verified / total * 100 if total else 0):.1f}%</p>
    </section>
    <section class="section">
      <h2>2. Топ-10 банков (по всей базе)</h2>
      <table class="bars">
{bank_rows}
      </table>
      <p class="sub-note">{e(bank_others_note)}</p>
    </section>
    <section class="section">
      <h2>3. Динамика по месяцам</h2>
      <table class="bars">
{month_rows}
      </table>
      <p class="sub-note">Максимум: {max_month[1]} жалоб в месяц ({e(max_month[0])}). Последний месяц в базе:
      {e(last_month[0])} — {last_month[1]} жалоб (месяц не завершён).</p>
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
        Дата/время запуска: <b>{now} (МСК)</b><br>
        Модель: <b>{MODEL}</b><br>
        Всего записей в базе: <b>{total}</b><br>
        Версия агрегата: {e(str(d.get("generatedAt")))} · окно {e(str(d.get("dateFrom")))} — {e(str(d.get("dateTo")))}
      </p>
    </section>

    <div class="footer">Отчёт сгенерирован автоматически (stats-agent). Данные: katya-data.json</div>
  </div>
</body>
</html>
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(doc)

print(f"OK base={total} verified={verified} needs={needs} window={wt}")
print(f"top3=" + ", ".join(f"{k}={v}" for k, v in real_sorted[:3]))
print(f"saved {OUT} ({os.path.getsize(OUT)} bytes)")
