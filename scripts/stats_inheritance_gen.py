#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор отчёта reports/stats-inheritance.html для stats-agent.
Читает ТОЛЬКО агрегаты /home/user1/.openclaw/agents/shared/katya-summary-7d.json.
Ничего не пишет в базу данных.
"""
import json, html, datetime, os

SUMMARY = "/home/user1/.openclaw/agents/shared/katya-summary-7d.json"
OUT = "/home/user1/.openclaw/workspace/reports/stats-inheritance.html"
MODEL = "deepseek/deepseek-v4-flash"
NO_BANK = "не определён"
MAXBAR = 220


def esc(s):
    return html.escape(str(s), quote=True)


def bar(val, vmax, cls):
    w = max(4, int(round(MAXBAR * (val / vmax)))) if vmax else 4
    return f'<span class="bar-track"><span class="bar-fill {cls}" style="width:{w}px"></span></span>'


def now_msk():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Moscow"))
    except Exception:
        return datetime.datetime.utcnow() + datetime.timedelta(hours=3)


def main():
    with open(SUMMARY, encoding="utf-8") as f:
        s = json.load(f)

    base = s.get("base", {})
    win = s.get("window", {})
    b_total = base.get("total", 0)
    b_ver = base.get("totalVerified", 0)
    b_nr = base.get("totalNeedsReview", 0)
    first = base.get("firstDate")
    last = base.get("lastDate")
    by_bank = base.get("byBank", {}) or {}
    by_src = base.get("bySource", {}) or {}
    by_month = base.get("byMonth", {}) or {}

    named = {k: v for k, v in by_bank.items() if k != NO_BANK}
    nob = by_bank.get(NO_BANK, 0)
    top10 = sorted(named.items(), key=lambda x: (-x[1], x[0]))[:10]
    top10_names = {k for k, _ in top10}
    others = sum(v for k, v in named.items() if k not in top10_names)
    named_banks = len(named)

    vmax_bank = max([v for _, v in top10] + [nob] + [1])
    months = sorted(by_month.items())
    vmax_month = max([v for _, v in months] + [1])
    srcs = sorted(by_src.items(), key=lambda x: (-x[1], x[0]))
    vmax_src = max([v for _, v in srcs] + [1])

    run = now_msk()
    run_str = run.strftime("%d.%m.%Y %H:%M")

    P = []
    P.append('<!DOCTYPE html>\n<html lang="ru">\n<head>')
    P.append('  <meta charset="UTF-8">')
    P.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    P.append('  <title>Статистика жалоб — Наследство в банках РФ</title>')
    P.append('  <link rel="stylesheet" href="theme.css">')
    P.append('''  <style>
    .bar-fill { display:inline-block; height:20px; border-radius:4px; min-width:4px; }
    .bar-other  { background: linear-gradient(90deg,#7ee787,#56d4dd); }
    .bar-src    { background: linear-gradient(90deg,#d2a8ff,#8957e5); }
    .bar-month  { background: linear-gradient(90deg,#ffa657,#f0883e); }
    .sub-note { font-size:12px; color:var(--text-dim); margin-top:8px; line-height:1.6; }
    .entry-list { list-style:none; margin:0; padding:0; }
    .entry-list li { padding:12px 14px; border-radius:10px; background:var(--glass-bg); border:1px solid var(--glass-border); margin-bottom:10px; }
    .entry-list .e-title { font-weight:600; color:var(--text); font-size:14px; }
    .entry-list .e-meta { font-size:12px; color:var(--text-dim); margin:4px 0 6px; }
    .entry-list .e-desc { font-size:13px; color:var(--text-dim); line-height:1.55; }
    .entry-list a { color:var(--blue); text-decoration:none; font-size:12px; word-break:break-all; }
    .stat-card { display:inline-block; min-width:150px; margin:6px 8px 6px 0; padding:16px 18px; border-radius:14px; background:var(--glass-bg); border:1px solid var(--glass-border); }
    .stat-card .num { font-size:30px; font-weight:800; line-height:1.1; }
    .stat-card .lbl { font-size:12px; color:var(--text-dim); margin-top:4px; }
    .badge { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px; font-weight:600; margin-left:6px; }
    .badge-green { background:rgba(126,231,135,.15); color:var(--green); }
    .badge-yellow { background:rgba(210,153,34,.15); color:var(--yellow); }
    table.bars { width:100%; border-collapse:collapse; font-size:13px; }
    table.bars td { padding:3px 6px; vertical-align:middle; }
    table.bars tr td:first-child { white-space:nowrap; color:var(--text); }
    .bar-track { background:var(--glass-border); border-radius:4px; height:20px; width:100%; min-width:120px; display:block; }
    .cnt { text-align:right; font-weight:600; color:var(--text); white-space:nowrap; }
    h3 { font-size:15px; margin:18px 0 8px; color:var(--text); }
  </style>
</head>
<body>
  <div class="container">''')
    P.append('    <h1>📊 Статистика жалоб: наследство в банках РФ</h1>')
    P.append(f'    <p class="sub-note">Автоматический отчёт stats-agent · {run_str} (МСК) · Модель: {MODEL}</p>')

    # 1. Общая статистика
    share_ver = f'{b_ver / b_total * 100:.1f}%' if b_total else '—'
    P.append('    <section class="section">')
    P.append('      <h2>1. Общая статистика по всей базе</h2>')
    P.append(f'      <div class="stat-card"><div class="num">{b_total}</div><div class="lbl">всего жалоб</div></div>')
    P.append(f'      <div class="stat-card"><div class="num">{b_ver}</div><div class="lbl">verified</div></div>')
    P.append(f'      <div class="stat-card"><div class="num">{b_nr}</div><div class="lbl">needs_review</div></div>')
    P.append(f'      <p class="sub-note">Период: <b>{esc(first)}</b> — <b>{esc(last)}</b> ·'
             f' источников: {len(by_src)} · банков (с «{NO_BANK}»): {len(by_bank)} ·'
             f' без даты: {base.get("withoutDate", 0)} · доля verified: {share_ver}</p>')
    P.append('    </section>')

    # 2. Топ-10 банков
    P.append('    <section class="section">')
    P.append('      <h2>2. Топ-10 банков (по всей базе)</h2>')
    P.append('      <table class="bars">')
    rows = []
    for name, v in top10:
        rows.append(f'<tr><td>{esc(name)}</td><td style="width:100%">{bar(v, vmax_bank, "bar-other")}</td><td class="cnt">{v}</td></tr>')
    rows.append(f'<tr><td>{esc(NO_BANK)}</td><td style="width:100%">{bar(nob, vmax_bank, "bar-src")}</td><td class="cnt">{nob}</td></tr>')
    P.append("".join(rows))
    P.append('      </table>')
    P.append(f'      <p class="sub-note">«{NO_BANK}» — жалобы, где банк не указан в тексте/сниппете '
             f'(показан отдельной строкой, в топ-10 не входит). Прочие банки за пределами топ-10: '
             f'{others} жалоб (всего банков вне «{NO_BANK}»: {named_banks}).</p>')
    P.append('    </section>')

    # 3. Динамика по месяцам
    P.append('    <section class="section">')
    P.append('      <h2>3. Динамика по месяцам</h2>')
    P.append('      <table class="bars">')
    mr = []
    for m, v in months:
        mr.append(f'<tr><td>{esc(m)}</td><td style="width:100%">{bar(v, vmax_month, "bar-month")}</td><td class="cnt">{v}</td></tr>')
    P.append("".join(mr))
    P.append('      </table>')
    if months:
        mmax = max(months, key=lambda x: x[1])
        lastm, lastv = months[-1]
        P.append(f'      <p class="sub-note">Максимум: {mmax[1]} жалоб в месяц ({esc(mmax[0])}). '
                 f'Последний месяц в базе: {esc(lastm)} — {lastv} жалоб (месяц не завершён).</p>')
    P.append('    </section>')

    # 4. Источники
    P.append('    <section class="section">')
    P.append('      <h2>4. Источники</h2>')
    P.append('      <table class="bars">')
    sr = []
    for name, v in srcs:
        pct = f'{v / b_total * 100:.1f}%' if b_total else '—'
        sr.append(f'<tr><td>{esc(name)}</td><td style="width:100%">{bar(v, vmax_src, "bar-src")}</td><td class="cnt">{v} · {pct}</td></tr>')
    P.append("".join(sr))
    P.append('      </table>')
    P.append('    </section>')

    # 5. Окно 7 дней
    w_total = win.get("total", 0)
    P.append('    <section class="section">')
    P.append('      <h2>5. За последние 7 дней</h2>')
    if w_total == 0:
        P.append('      <p class="sub-note">За окно новых жалоб нет. Общая статистика по базе выше не обнуляется.</p>')
    else:
        P.append(f'      <div class="stat-card"><div class="num">{w_total}</div><div class="lbl">жалоб за 7 дней</div></div>')
        P.append(f'      <div class="stat-card"><div class="num">{win.get("totalVerified", 0)}</div><div class="lbl">verified</div></div>')
        P.append(f'      <div class="stat-card"><div class="num">{win.get("totalNeedsReview", 0)}</div><div class="lbl">needs_review</div></div>')
        wsrc = win.get("bySource", {}) or {}
        wsrc_s = ", ".join(f"{esc(k)} ({v})" for k, v in sorted(wsrc.items(), key=lambda x: (-x[1], x[0])))
        P.append(f'      <p class="sub-note">Окно: <b>{esc(s.get("dateFrom"))}</b> — <b>{esc(s.get("dateTo"))}</b>'
                 f' · источники за окно: {wsrc_s or "—"}</p>')
        wbank = win.get("byBank", {}) or {}
        if wbank:
            wb_items = sorted(wbank.items(), key=lambda x: (-x[1], x[0]))
            wmax = max([v for _, v in wb_items] + [1])
            P.append('      <h3>По банкам (за окно)</h3><table class="bars">')
            wr = []
            for name, v in wb_items:
                label = "Без банка" if name == NO_BANK else name
                wr.append(f'<tr><td>{esc(label)}</td><td style="width:100%">{bar(v, wmax, "bar-src")}</td><td class="cnt">{v}</td></tr>')
            P.append("".join(wr))
            P.append('      </table>')
        wdate = win.get("byDate", {}) or {}
        if wdate:
            wd_items = sorted(wdate.items())
            wdmax = max([v for _, v in wd_items] + [1])
            P.append('      <h3>По датам (за окно)</h3><table class="bars">')
            wr = []
            for d, v in wd_items:
                wr.append(f'<tr><td>{esc(d)}</td><td style="width:100%">{bar(v, wdmax, "bar-month")}</td><td class="cnt">{v}</td></tr>')
            P.append("".join(wr))
            P.append('      </table>')
        entries = win.get("entries", []) or []
        if entries:
            P.append('      <h3>Новые жалобы (за окно)</h3><ul class="entry-list">')
            for e in entries:
                bank = e.get("bank") or "банк не назван"
                ver = e.get("verification")
                if ver == "verified":
                    badge = '<span class="badge badge-green">проверено</span>'
                else:
                    badge = '<span class="badge badge-yellow">на проверку</span>'
                P.append('        <li>')
                P.append(f'          <div class="e-title">{esc(e.get("title", ""))}</div>')
                P.append(f'          <div class="e-meta">{esc(e.get("date"))} · {esc(bank)} · {esc(e.get("source"))} {badge}</div>')
                if e.get("description"):
                    P.append(f'          <div class="e-desc">{esc(e.get("description"))}</div>')
                if e.get("verification_note"):
                    P.append(f'          <div class="e-desc" style="margin-top:6px"><i>{esc(e.get("verification_note"))}</i></div>')
                if e.get("url"):
                    P.append(f'          <div style="margin-top:8px"><a href="{esc(e.get("url"))}">{esc(e.get("url"))}</a></div>')
                P.append('        </li>')
            P.append('      </ul>')
    P.append('    </section>')

    # 6. Мета
    P.append('    <section class="section">')
    P.append('      <h2>6. Мета</h2>')
    P.append('      <p class="sub-note">')
    P.append(f'        Дата/время запуска: <b>{run_str} (МСК)</b><br>')
    P.append(f'        Модель: <b>{MODEL}</b><br>')
    P.append(f'        Всего записей в базе: <b>{b_total}</b><br>')
    P.append(f'        Версия агрегата: {esc(s.get("generatedAt"))} · окно {esc(s.get("dateFrom"))} — {esc(s.get("dateTo"))}')
    P.append('      </p>')
    P.append('    </section>')
    P.append('')
    P.append('    <div class="footer">Отчёт сгенерирован автоматически (stats-agent). Данные: katya-data.json</div>')
    P.append('  </div>\n</body>\n</html>')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(P) + "\n")

    print("OK", OUT)
    print("base:", b_total, "verified:", b_ver, "needs_review:", b_nr)
    print("top3:", top10[:3])
    print("window:", w_total, "verified:", win.get("totalVerified"), "needs_review:", win.get("totalNeedsReview"))
    print("window_byBank:", win.get("byBank"), "bySource:", win.get("bySource"))


if __name__ == "__main__":
    main()
