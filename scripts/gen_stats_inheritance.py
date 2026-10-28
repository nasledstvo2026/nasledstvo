#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, html, datetime

S = json.load(open('/home/user1/.openclaw/agents/shared/katya-summary-7d.json', encoding='utf-8'))
base = S['base']; win = S['window']
total = base['total']
byBank = base['byBank']; bySource = base['bySource']; byMonth = base['byMonth']

def esc(x): return html.escape(str(x) if x is not None else '')
def pct(n, d): return f"{n*100.0/d:.1f}%"

undef = byBank.get('не определён', 0)
banks = sorted([(k, v) for k, v in byBank.items() if k != 'не определён'], key=lambda kv: (-kv[1], kv[0]))
top = banks[:10]
rest = banks[10:]
maxb = max(v for _, v in banks) if banks else 1

bank_rows = []
for i, (name, cnt) in enumerate(top, 1):
    w = max(6, round(cnt / maxb * 240))
    bank_rows.append(
        f'<tr><td style="color:var(--text-faint)">{i}</td><td><b>{esc(name)}</b></td>'
        f'<td style="text-align:right">{cnt}</td><td style="text-align:right;color:var(--text-dim)">{pct(cnt,total)}</td>'
        f'<td><span class="bar bar-other" style="width:{w}px"></span></td></tr>')

sources = sorted(bySource.items(), key=lambda kv: (-kv[1], kv[0]))
maxs = max(v for _, v in sources) if sources else 1
src_rows = []
for name, cnt in sources:
    w = max(6, round(cnt / maxs * 220))
    src_rows.append(
        f'<tr><td><b>{esc(name)}</b></td><td style="text-align:right">{cnt}</td>'
        f'<td style="text-align:right;color:var(--text-dim)">{pct(cnt,total)}</td>'
        f'<td><span class="bar bar-sber" style="width:{w}px"></span></td></tr>')

months = sorted(byMonth.items())
maxm = max(v for _, v in months) if months else 1
mon_rows = []
for name, cnt in months:
    w = max(6, round(cnt / maxm * 220))
    mon_rows.append(
        f'<tr><td>{esc(name)}</td><td style="text-align:right">{cnt}</td>'
        f'<td><span class="bar bar-sber" style="width:{w}px"></span></td></tr>')

win_bank_rows = ''.join(
    f'<tr><td>{esc(k)}</td><td style="text-align:right">{v}</td></tr>'
    for k, v in sorted(win['byBank'].items(), key=lambda kv: -kv[1]))
win_date_rows = ''.join(
    f'<tr><td>{esc(k)}</td><td style="text-align:right">{v}</td></tr>'
    for k, v in sorted(win['byDate'].items()))

entries = []
for e in win['entries']:
    bank = e.get('bank') or 'не определён'
    vtag = 'verified' if e.get('verification') == 'verified' else 'needs_review'
    entries.append(f'''<div class="item">
  <div class="meta">{esc(e.get("date"))} · {esc(bank)} · {esc(e.get("source"))} · <span class="badge badge-banki">{esc(vtag)}</span></div>
  <div class="title"><a href="{esc(e.get("url"))}" target="_blank" rel="noopener">{esc(e.get("title"))}</a></div>
  <div class="body">{esc(e.get("description"))}</div>
</div>''')

rest_note = ''
if rest:
    rest_note = ('Прочие банки вне топ-10: ' + ', '.join(f'{esc(k)} ({v})' for k, v in rest) + '.')

win_block = ''
if win['total'] == 0:
    win_block = '<div class="note">За окно последних 7 дней новых жалоб нет.</div>'
else:
    win_block = f'''<div class="stats-row">
  <div class="stat-box"><div class="label">Новых жалоб за 7 дней</div><div class="num">{win["total"]}</div></div>
  <div class="stat-box"><div class="label">verified</div><div class="num">{win.get("totalVerified",0)}</div></div>
  <div class="stat-box"><div class="label">needs_review</div><div class="num">{win.get("totalNeedsReview",0)}</div></div>
</div>
<div class="table-wrap"><table class="striped-table">
<thead><tr><th>Банк</th><th style="text-align:right">Жалоб</th></tr></thead>
<tbody>{win_bank_rows}</tbody></table></div>
<div class="table-wrap"><table class="striped-table">
<thead><tr><th>Дата</th><th style="text-align:right">Жалоб</th></tr></thead>
<tbody>{win_date_rows}</tbody></table></div>
<h3 class="title">Записи окна</h3>
{''.join(entries)}'''

now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).strftime('%d.%m.%Y, %H:%M')

html_out = f'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Статистика жалоб — наследство в банках РФ</title>
<link rel="stylesheet" href="theme.css">
</head>
<body>
<div class="container">
<a class="back" href="index.html">← На главную</a>

<div class="hero">
  <h1>Статистика жалоб: наследство в банках РФ</h1>
  <div class="sub">Накопительная база жалоб и обращений по наследственным делам в банках</div>
  <div class="date">Отчёт сформирован {now} (Europe/Moscow)</div>
</div>

<div class="section">
<h2>1. Общая статистика по всей базе</h2>
<div class="stats-row">
  <div class="stat-box"><div class="label">Всего жалоб</div><div class="value">{total}</div></div>
  <div class="stat-box"><div class="label">verified</div><div class="value">{base.get("totalVerified",0)}</div></div>
  <div class="stat-box"><div class="label">needs_review</div><div class="value">{base.get("totalNeedsReview",0)}</div></div>
</div>
<div class="note">Период наблюдений: <b>{esc(base["firstDate"])} — {esc(base["lastDate"])}</b>. Записей без даты: {base.get("withoutDate",0)}.</div>
</div>

<div class="section">
<h2>2. Топ-10 банков</h2>
<div class="table-wrap"><table class="striped-table">
<thead><tr><th>#</th><th>Банк</th><th style="text-align:right">Жалоб</th><th style="text-align:right">Доля</th><th>График</th></tr></thead>
<tbody>{''.join(bank_rows)}</tbody></table></div>
<div class="note">Банк не определён: <b>{undef}</b> жалоб ({pct(undef,total)}). {rest_note}</div>
</div>

<div class="section">
<h2>3. Динамика по месяцам</h2>
<div class="table-wrap"><table class="striped-table">
<thead><tr><th>Месяц</th><th style="text-align:right">Жалоб</th><th>График</th></tr></thead>
<tbody>{''.join(mon_rows)}</tbody></table></div>
</div>

<div class="section">
<h2>4. Источники</h2>
<div class="table-wrap"><table class="striped-table">
<thead><tr><th>Источник</th><th style="text-align:right">Жалоб</th><th style="text-align:right">Доля</th><th>График</th></tr></thead>
<tbody>{''.join(src_rows)}</tbody></table></div>
</div>

<div class="section">
<h2>5. За последние 7 дней ({esc(S["dateFrom"])} — {esc(S["dateTo"])})</h2>
{win_block}
</div>

<div class="section">
<h2>6. Метаданные</h2>
<div class="table-wrap"><table class="striped-table detail-table"><tbody>
<tr><td>Дата и время запуска</td><td>{now} (Europe/Moscow)</td></tr>
<tr><td>Модель</td><td>deepseek/deepseek-v4-flash</td></tr>
<tr><td>Всего записей в базе</td><td>{total}</td></tr>
<tr><td>Источник агрегатов</td><td>katya-summary-7d.json (generatedAt {esc(S.get("generatedAt"))})</td></tr>
</tbody></table></div>
</div>

<div class="footer">
  <strong>Наследство в банках РФ</strong> · статистика жалоб · обновляется автоматически<br>
  <a href="https://nasledstvo2026.github.io/nasledstvo/">nasledstvo2026.github.io/nasledstvo</a>
</div>
</div>
</body>
</html>
'''

open('/home/user1/.openclaw/workspace/reports/stats-inheritance.html','w',encoding='utf-8').write(html_out)
print('OK', total, win['total'], len(html_out))
