#!/usr/bin/env python3
"""
Generate stats-inheritance.html from katya-data.json
"""
import json
import os
from datetime import datetime, timedelta
from collections import Counter, defaultdict

# Load data
with open('/home/user1/.openclaw/workspace/memory/katya-data.json', 'r') as f:
    data = json.load(f)

# Normalize bank names
def normalize_bank(bank):
    if bank in ('Сбербанк', 'Сбер'):
        return 'Сбер'
    if bank.startswith('ВТБ'):
        return 'ВТБ'
    return bank

for r in data:
    r['bank_norm'] = normalize_bank(r['bank'])

# Dates
now = datetime.now()
today = '2026-07-09'
yesterday = '2026-07-08'
yesterday_str = '08 Июля 2026'

current_month = '2026-07'
prev_month = '2026-06'
current_year = '2026'

# Month names in Russian
month_names = {
    '01': 'Янв', '02': 'Фев', '03': 'Мар', '04': 'Апр', '05': 'Май', '06': 'Июн',
    '07': 'Июл', '08': 'Авг', '09': 'Сен', '10': 'Окт', '11': 'Ноя', '12': 'Дек'
}

# Group data by date
def get_ym(date_str):
    return date_str[:7]

def get_month_label(ym):
    y, m = ym.split('-')
    if y == '2026':
        return month_names[m]
    elif y == '2025':
        return f"{month_names[m]} 2025"

# ========== SECTION 2: Yesterday ==========
yesterday_records = [r for r in data if r['date'] == yesterday]
yesterday_sber = sum(1 for r in yesterday_records if r['bank_norm'] == 'Сбер')
yesterday_other = len(yesterday_records) - yesterday_sber

# Build yesterday links
yesterday_links = []
for r in yesterday_records:
    bank_display = r['bank_norm']
    if r['url'] and r['url'].strip():
        yesterday_links.append(f'<a href="{r["url"]}" target="_blank">{bank_display}: {r["title"]}</a>')
    else:
        yesterday_links.append(f'{bank_display}: {r["description"]}')

if not yesterday_links:
    yesterday_content = '          <span style="opacity:0.5">Новых жалоб не обнаружено</span>'
else:
    yesterday_content = '          ' + '<br>\n          '.join(yesterday_links)

yesterday_sber_color = 'var(--green)' if yesterday_sber == 0 else 'var(--red)'
yesterday_other_color = 'var(--green)' if yesterday_other == 0 else 'var(--red)'

# ========== SECTION 3: Current month ==========
curr_records = [r for r in data if get_ym(r['date']) == current_month]
curr_total = len(curr_records)
curr_sber = sum(1 for r in curr_records if r['bank_norm'] == 'Сбер')
curr_other = curr_total - curr_sber

# Bank list for current month
curr_bank_counter = Counter()
for r in curr_records:
    if r['bank_norm'] != 'Сбер':
        curr_bank_counter[r['bank']] += 1
curr_bank_list = sorted(curr_bank_counter.items(), key=lambda x: -x[1])

if curr_bank_list:
    curr_bank_str = ', '.join(f'{b} — {c}' for b, c in curr_bank_list)
else:
    curr_bank_str = 'Новых жалоб не обнаружено'

# Dynamics - compare with previous month
prev_records = [r for r in data if get_ym(r['date']) == prev_month]
prev_sber = sum(1 for r in prev_records if r['bank_norm'] == 'Сбер')
prev_other = len(prev_records) - prev_sber

def trend_color(val):
    if val > 0: return 'var(--red)'
    elif val < 0: return 'var(--green)'
    else: return 'var(--text-secondary)'

def fmt_delta(val):
    if val > 0: return f'+{val}'
    elif val < 0: return str(val)
    else: return '0'

delta_sber = curr_sber - prev_sber
delta_other = curr_other - prev_other

curr_total_color = 'var(--green)' if curr_total == 0 else 'var(--red)'
curr_sber_color_disp = 'var(--green)' if curr_sber == 0 else 'var(--red)'
curr_other_color_disp = 'var(--green)' if curr_other == 0 else 'var(--red)'

# ========== SECTION 4: Bank bars for current year ==========
year_records = [r for r in data if r['date'].startswith(current_year + '-')]
year_bank_counter = Counter()
for r in year_records:
    year_bank_counter[r['bank_norm']] += 1

# Combine same banks (normalized already)
sber_count_year = year_bank_counter.get('Сбер', 0)
total_year = len(year_records)

# Group by original bank for bars (use bank_norm)
year_by_norm = Counter()
for r in year_records:
    year_by_norm[r['bank_norm']] += 1

sorted_banks = sorted(year_by_norm.items(), key=lambda x: -x[1])
max_count = sorted_banks[0][1] if sorted_banks else 1

# Bar colors mapping
bar_colors = {
    'Сбер': 'sber',
    'ВТБ': 'vtb',
    'ПСБ': 'psb',
    'Т-Банк': 'tbank',
    'Газпромбанк': 'gpb',
    'Совкомбанк': 'sovcombank',
}

def get_bar_style(bank, count):
    width_px = round(count / max_count * 230)
    css_class = bar_colors.get(bank, '')
    if css_class:
        return f'class="{css_class}" style="width:{width_px}px;"'
    else:
        # No predefined class, use color map
        color_map = {
            'Альфа-Банк': '#ef4444',
            'Уралсиб': '#2d8bcf',
            'Россельхозбанк': '#1a7d38',
            'Ozon Банк': '#8b5cf6',
            'РайффайзенБанк': '#00a86b',
            'Неизвестно': '#6b7280',
            'МТС Банк': '#f59e0b',
        }
        color = color_map.get(bank, '#6b7280')
        return f'style="background:{color};width:{width_px}px;"'

# ========== SECTION 5: Monthly stats table ==========
# Group all records by month
monthly = defaultdict(lambda: {'sber': 0, 'other': 0, 'banks': Counter()})
for r in data:
    ym = get_ym(r['date'])
    if r['bank_norm'] == 'Сбер':
        monthly[ym]['sber'] += 1
    else:
        monthly[ym]['other'] += 1
        monthly[ym]['banks'][r['bank']] += 1

# All months in order (descending)
all_yms = sorted(monthly.keys(), reverse=True)

# Also need months that exist but may not have records - all months from Apr 2025 to Jul 2026
all_months_2026 = ['2026-07', '2026-06', '2026-05', '2026-04', '2026-03', '2026-02', '2026-01']
all_months_2025 = ['2025-12', '2025-11', '2025-10', '2025-09', '2025-08', '2025-07', 
                   '2025-06', '2025-05', '2025-04', '2025-03', '2025-02', '2025-01']

all_months = all_months_2026 + all_months_2025

def bank_col_str(banks_counter):
    """Format bank column with counts >1"""
    parts = []
    for b, c in sorted(banks_counter.items(), key=lambda x: -x[1]):
        if c == 1:
            parts.append(b)
        else:
            parts.append(f'{b}({c})')
    return ', '.join(parts) if parts else '—'

def month_label(ym):
    y, m = ym.split('-')
    if y == '2026':
        return month_names[m]
    elif y == '2025':
        return f"{month_names[m]} 2025"
    return ym

def sber_count_style(cnt):
    color = 'var(--green)' if cnt == 0 else 'var(--red)'
    return f'style="color:{color}"'

def other_count_style(cnt):
    color = 'var(--green)' if cnt == 0 else 'var(--red)'
    return f'style="color:{color}"'

# Totals
total_sber_2026 = sum(monthly[ym]['sber'] for ym in all_months_2026 if ym in monthly)
total_other_2026 = sum(monthly[ym]['other'] for ym in all_months_2026 if ym in monthly)
total_all_2026 = total_sber_2026 + total_other_2026

total_sber_2025 = sum(monthly[ym]['sber'] for ym in all_months_2025 if ym in monthly)
total_other_2025 = sum(monthly[ym]['other'] for ym in all_months_2025 if ym in monthly)
total_all_2025 = total_sber_2025 + total_other_2025

# ========== SECTION 6: Timeline ==========
# Sort all records by date descending
def sort_key(r):
    d = r['date']
    if d.endswith('-??'):
        d = d.replace('-??', '-01')
    return d

sorted_data = sorted(data, key=sort_key, reverse=True)

def format_date_row(d):
    """Format date for display"""
    if d.endswith('-??'):
        base = d[:7]
        y, m = base.split('-')
        if y == '2026':
            return f'{month_names[m]} 26'
        else:
            return f'{month_names[m]} {y[2:]}'
    else:
        parts = d.split('-')
        return f'{parts[2]}.{parts[1]}.{parts[0][2:]}'

def bank_short(r):
    """Short bank name"""
    return r['bank_norm']

def make_timeline_link(r):
    """Create title with link if url exists"""
    title = r['title']
    if r['url'] and r['url'].strip():
        return f'<a href="{r["url"]}" target="_blank">{title}</a>'
    else:
        return title

def source_display(src):
    """Source display color map"""
    colors = {
        'banki.ru': 'var(--blue)',
        'pikabu.ru': 'var(--orange)',
        'otzovik.com': 'var(--green)',
        '2ГИС': 'var(--purple)',
        'findozor.net': 'var(--text-secondary)',
    }
    c = colors.get(src, 'var(--text-secondary)')
    return f'<span style="color:{c}">{src}</span>'

# ========== BUILD HTML ==========

# Version
version = 4  # incrementing from v3

# Build the file
html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Статистика жалоб по наследству в банках РФ</title>
  <link rel="stylesheet" href="theme.css">
  <style>
    :root {{
      --bg: #f5f7fa;
      --bg-secondary: #e8ecf1;
      --glass-bg: rgba(255, 255, 255, 0.85);
      --glass-border: rgba(0, 0, 0, 0.08);
      --glass-hover: rgba(0, 0, 0, 0.04);
      --glass-shine: rgba(255, 255, 255, 0.6);
      --text: #1a1a2e;
      --text-dim: #4a4a5a;
      --text-secondary: #6b6b7b;
      --text-faint: #999;
      --accent: #2563eb;
      --red: #dc2626;
      --green: #16a34a;
      --orange: #ea580c;
      --blue: #2563eb;
      --purple: #7c3aed;
      --border: rgba(0, 0, 0, 0.08);
    }}
    body {{ background: var(--bg); background-image: none; }}
    .hero + .section {{ margin-top: 4px; }}
    .section {{ margin-top: 16px; }}
    .item {{ padding: 14px; margin-bottom: 10px; }}
    .section h2 {{ margin-bottom: 10px; }}
    .item .tag {{ margin-bottom: 4px; }}
    .stats-row {{ gap: 1rem; }}
    .stat-box {{ box-shadow: 0 2px 12px rgba(0,0,0,0.1); }}
    .stat-box .value {{ font-size: 28px; }}
    .bar-chart {{ margin: 0.5rem 0; }}
    .bar {{ display: flex; align-items: center; gap: 0.5rem; margin: 0.25rem 0; }}
    .bar-label {{ width: 120px; font-size: 0.9rem; color: var(--text); text-align: right; padding-right: 12px; flex-shrink: 0; }}
    .bar-fill {{ height: 22px; border-radius: 4px; min-width: 4px; transition: width 0.3s; }}
    .bar-fill.sber {{ background: #1a9e5c; }}
    .bar-fill.vtb {{ background: #009fdf; }}
    .bar-fill.psb {{ background: #f15a24; }}
    .bar-fill.tbank {{ background: #ffdd3c; }}
    .bar-fill.gpb {{ background: #003a70; }}
    .bar-fill.sovcombank {{ background: #d42027; }}
    .bar {{ margin-bottom: 10px; }}
    .bar-val {{ font-size: 0.85rem; color: var(--text-secondary); white-space: nowrap; }}
    .mini-bar {{ display: inline-block; height: 10px; border-radius: 3px; margin-left: 0.5rem; vertical-align: middle; }}
    .mini-bar.sber {{ background: #1a9e5c; }}
    .mini-bar.other {{ background: #009fdf; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 0.5rem 0.75rem; text-align: left; border: 1px solid var(--border); }}
    th {{ color: var(--text-secondary); font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; background: var(--bg-secondary); }}
    tr:last-child td {{ border-bottom: none; }}
    tr.total td {{ font-weight: 700; color: var(--text); border-top: 2px solid var(--accent); }}
    .trend-note {{ color: var(--text-secondary); font-size: 0.85rem; }}
    table.striped-table th, table.striped-table td {{ border: 1px solid var(--border); }}
    .btn {{ display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.5rem 1rem; background: var(--accent); color: #fff; border-radius: 6px; text-decoration: none; font-size: 0.9rem; transition: background 0.2s; }}
    .btn:hover {{ background: var(--accent-hover); }}
    .yesterday-block {{ background: var(--bg-secondary); border-radius: 8px; padding: 1rem; margin: 1rem 0; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; }}
    .item small {{ color: var(--text-secondary); font-size: 0.85rem; display: block; margin-top: 0.2rem; }}
  </style>
</head>
<body>
  <div class="container">
    <a href="inheritance.html" class="back">← Кластер Наследство</a>

    <div class="hero">
      <h1>Статистика жалоб по наследству в банках <span style="font-size:0.6em;color:var(--text-secondary);font-weight:400">v{version}</span></h1>
    </div>

    <div class="section">
      <div class="item">
        <h2>📅 {yesterday_str}</h2>
        <div class="stats-row" style="margin-bottom:12px;margin-top:8px">
          <div class="stat-box">
            <div class="label">Сбер</div>
            <div class="value" style="color:{yesterday_sber_color}">{yesterday_sber}</div>
          </div>
          <div class="stat-box">
            <div class="label">Другие банки</div>
            <div class="value" style="color:{yesterday_other_color}">{yesterday_other}</div>
          </div>
        </div>
        <div style="font-size:0.9em;line-height:1.6">{yesterday_content}
        </div>
      </div>
    </div>

    <div class="section">
      <div class="item">
        <h2>📊 Июл 2026</h2>
        <div style="margin:8px 0 4px;opacity:.7;font-size:0.9em">Текущий месяц — сбор данных продолжается</div>
        <div class="stats-row">
          <div class="stat-box">
            <div class="label">Всего жалоб</div>
            <div class="value" style="color:{curr_total_color}">{curr_total}</div>
          </div>
          <div class="stat-box">
            <div class="label">Сбер · Другие</div>
            <div class="value" style="color:{curr_sber_color_disp};display:inline">{curr_sber}</div>
            <span style="font-size:28px;font-weight:700;color:var(--text-dim)"> · </span>
            <div class="value" style="color:{curr_other_color_disp};display:inline">{curr_other}</div>
          </div>
          <div class="stat-box" style="max-width:100%">
            <div class="label">Динамика</div>
            <table style="font-size:14px;width:100%;margin:8px auto;border-collapse:collapse">
              <tr style="border-bottom:1px solid var(--border)">
                <td style="padding:4px 8px;text-align:left;font-weight:600"></td>
                <td style="padding:4px 8px;text-align:center;font-weight:600">Июн</td>
                <td style="padding:4px 4px;text-align:center"></td>
                <td style="padding:4px 8px;text-align:center;font-weight:600">Июл</td>
                <td style="padding:4px 8px;text-align:center;font-weight:600">Δ</td>
              </tr>
              <tr>
                <td style="padding:4px 8px;text-align:left;color:var(--green);font-weight:600">Сбер</td>
                <td style="padding:4px 8px;text-align:center">{prev_sber}</td>
                <td style="padding:4px 4px;text-align:center">→</td>
                <td style="padding:4px 8px;text-align:center">{curr_sber}</td>
                <td style="padding:4px 8px;text-align:center"><span style="color:{trend_color(delta_sber)};font-weight:700">{fmt_delta(delta_sber)}</span></td>
              </tr>
              <tr>
                <td style="padding:4px 8px;text-align:left;color:var(--text);font-weight:600">Другие</td>
                <td style="padding:4px 8px;text-align:center">{prev_other}</td>
                <td style="padding:4px 4px;text-align:center">→</td>
                <td style="padding:4px 8px;text-align:center">{curr_other}</td>
                <td style="padding:4px 8px;text-align:center"><span style="color:{trend_color(delta_other)};font-weight:700">{fmt_delta(delta_other)}</span></td>
              </tr>
            </table>
          </div>
        </div>
        <div class="item" style="margin-top:12px">
          <div style="font-size:12px;color:var(--text-dim);margin-bottom:6px">По банкам за июль:</div>
          <div style="font-size:15px;font-weight:600;color:var(--text);line-height:1.5">
            {curr_bank_str}
          </div>
        </div>
      </div>
    </div>

    <div class="section">
      <div class="item">
                <h2>🏦 Банки · {current_year}</h2>
      <div class="bar-chart">
"""

# Build bars
for bank, count in sorted_banks:
    pct = round(count / total_year * 100, 1) if total_year > 0 else 0
    style = get_bar_style(bank, count)
    html += f"""        <div class="bar">
          <span class="bar-label">{bank}</span>
          <span class="bar-fill" {style}></span>
          <span class="bar-val">{count} ({pct}%)</span>
        </div>
"""

html += f"""      </div>
      </div>
    </div>

    <div class="section">
      <div class="item">
        <h2>📅 Статистика</h2>
      <div style="max-width:100%;overflow-x:auto">
      <table class="striped-table" style="width:100%">
        <colgroup>
          <col style="width:70px">
          <col style="width:60px">
          <col style="width:60px">
          <col style="width:60px">
          <col>
        </colgroup>
        <thead>
          <tr>
            <th>Месяц</th>
            <th>Сбер</th>
            <th>Банки</th>
            <th>Итог</th>
            <th>Банк</th>
          </tr>
        </thead>
        <tbody>
          <tr style="background:rgba(37,99,235,0.08)">
            <td><strong style="color:var(--accent)">2026</strong></td>
            <td><strong style="color:var(--accent)">{total_sber_2026}</strong></td>
            <td><strong style="color:var(--accent)">{total_other_2026}</strong></td>
            <td><strong style="color:var(--accent)">{total_all_2026}</strong></td>
            <td><strong style="color:var(--accent)"></strong></td>
          </tr>
"""

# 2026 months
for ym in all_months_2026:
    if ym in monthly:
        m = monthly[ym]
        label = month_label(ym)
        sber = m['sber']
        other = m['other']
        total = sber + other
        sber_s = sber_count_style(sber)
        other_s = other_count_style(other)
        bank_col = bank_col_str(m['banks'])
        html += f"""          <tr>
            <td>{label}</td>
            <td {sber_s}>{sber}</td>
            <td {other_s}>{other}</td>
            <td><strong>{total}</strong></td>
            <td style="white-space:nowrap">{bank_col}</td>
          </tr>
"""
    else:
        label = month_label(ym)
        html += f"""          <tr>
            <td>{label}</td>
            <td style="color:var(--green)">0</td>
            <td style="color:var(--green)">0</td>
            <td><strong>0</strong></td>
            <td style="white-space:nowrap">—</td>
          </tr>
"""

html += f"""          <tr style="background:rgba(234,88,12,0.1)">
            <td><strong style="color:var(--orange)">2025</strong></td>
            <td><strong style="color:var(--orange)">{total_sber_2025}</strong></td>
            <td><strong style="color:var(--orange)">{total_other_2025}</strong></td>
            <td><strong style="color:var(--orange)">{total_all_2025}</strong></td>
            <td><strong style="color:var(--orange)"></strong></td>
          </tr>
"""

# 2025 months
for ym in all_months_2025:
    if ym in monthly:
        m = monthly[ym]
        label = month_label(ym)
        sber = m['sber']
        other = m['other']
        total = sber + other
        sber_s = sber_count_style(sber)
        other_s = other_count_style(other)
        bank_col = bank_col_str(m['banks'])
        html += f"""          <tr>
            <td>{label}</td>
            <td {sber_s}>{sber}</td>
            <td {other_s}>{other}</td>
            <td><strong>{total}</strong></td>
            <td style="white-space:nowrap">{bank_col}</td>
          </tr>
"""
    else:
        label = month_label(ym)
        html += f"""          <tr>
            <td>{label}</td>
            <td style="color:var(--green)">0</td>
            <td style="color:var(--green)">0</td>
            <td><strong>0</strong></td>
            <td style="white-space:nowrap">—</td>
          </tr>
"""

html += """      </tbody>
      </table>
      </div>
      </div>
    </div>

    <div class="section">
      <div class="item">
        <h2>⚠️ Хронология</h2>
      <div style="overflow-x:auto">
      <table class="striped-table" style="width:100%">
        <colgroup>
          <col style="width:90px">
          <col style="width:120px">
          <col>
          <col style="width:100px">
        </colgroup>
        <thead>
          <tr>
            <th>Дата</th>
            <th>Банк</th>
            <th>Описание</th>
            <th>Источник</th>
          </tr>
        </thead>
        <tbody>
"""

for r in sorted_data:
    dsp = format_date_row(r['date'])
    bk = bank_short(r)
    link = make_timeline_link(r)
    src = source_display(r['source'])
    html += f"""          <tr>
            <td>{dsp}</td>
            <td>{bk}</td>
            <td>{link}</td>
            <td>{src}</td>
          </tr>
"""

html += f"""        </tbody>
      </table>
      </div>
      </div>
    </div>

    <div class="note" style="margin-top:24px;color:var(--text-secondary);font-size:0.85rem;text-align:center">
      📊 Данные собраны {yesterday_str} · Источники: banki.ru, pikabu.ru, otzovik.com, 2ГИС, findozor.net
    </div>

  </div>

  <footer class="footer" style="margin-top:2rem;padding:1rem 0;border-top:1px solid var(--border);text-align:center;color:var(--text-faint);font-size:0.8rem">
    Обновлено {yesterday_str} · Статистика по жалобам наследников в банках РФ
  </footer>

</body>
</html>"""

with open('/tmp/stats-inheritance.html', 'w') as f:
    f.write(html)

print("Generated successfully!")
print(f"Total records: {len(data)}")
print(f"Yesterday records: {len(yesterday_records)} (Sber: {yesterday_sber}, Other: {yesterday_other})")
print(f"Current month Jul 2026: {curr_total} total ({curr_sber} Sber, {curr_other} Other)")
print(f"Prev month Jun 2026: {len(prev_records)} total ({prev_sber} Sber, {prev_other} Other)")
print(f"Year 2026: {total_year} total")
