#!/bin/bash
# generate-activity-report.sh
# Генерирует activity.html через ECharts
# Запуск: bash generate-activity-report.sh [--upload]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JSON="$SCRIPT_DIR/prompt-activity.json"
OUTPUT="$SCRIPT_DIR/activity.html"
TODAY=$(date +%Y-%m-%d)
NOW=$(date +%H:%M)

if [ -f "$SCRIPT_DIR/.env.timeweb" ]; then
  source "$SCRIPT_DIR/.env.timeweb"
fi

if [ ! -f "$JSON" ]; then
  echo '{"entries":[]}' > "$JSON"
fi

export JSON_PATH="$JSON" OUTPUT_PATH="$OUTPUT" TODAY="$TODAY" NOW="$NOW"
python3 << 'PYSCRIPT'
import json, os
from datetime import datetime, timedelta

JSON_PATH = os.environ['JSON_PATH']
OUTPUT_PATH = os.environ['OUTPUT_PATH']
TODAY = os.environ['TODAY']
NOW = os.environ['NOW']

with open(JSON_PATH) as f:
    data = json.load(f)

entries = data.get('entries', [])
total = len(entries)

# --- Analysis ---
users = {}
for e in entries:
    u = e['user']
    d = e['date']
    if u not in users:
        users[u] = {'dates': {}, 'total': 0}
    users[u]['total'] += 1
    users[u]['dates'][d] = users[u]['dates'].get(d, 0) + 1

dt_today = datetime.strptime(TODAY, '%Y-%m-%d')
dates_30 = [(dt_today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(29, -1, -1)]
date_labels_short = [(dt_today - timedelta(days=i)).strftime('%d.%m') for i in range(29, -1, -1)]

colors_user = {
    'Katya': '#58a6ff',
    'Lena':  '#bc8cff',
    'Danil': '#ff9000',
    'Roza':  '#7ee787',
    'Irina': '#f778ba',
}

# Map real names to keys for colors
user_color_key = {
    'Катя': 'Katya',
    'Лена': 'Lena',
    'Данил': 'Danil',
    'Роза': 'Roza',
    'Ирина': 'Irina',
}

sorted_users = sorted(users.items(), key=lambda x: -x[1]['total'])

# --- Counters ---
today_count = sum(1 for e in entries if e['date'] == TODAY)
seven_ago = (dt_today - timedelta(days=7)).strftime('%Y-%m-%d')
week_count = sum(1 for e in entries if e['date'] >= seven_ago)
thirty_ago = (dt_today - timedelta(days=30)).strftime('%Y-%m-%d')
month_count = sum(1 for e in entries if e['date'] >= thirty_ago)

def get_report_name(task):
    if not task:
        return ""
    tl = task.lower()
    if 'катя' in tl:
        return ' — отчет "Жалобы: наследство в банках"'
    if 'лена' in tl:
        return ' — отчет "Дайджест новостей"'
    if 'данил' in tl:
        return ' — отчет "Вклады СССР 1991"'
    if 'роза' in tl:
        return ' — отчет "Пособия и соцвыплаты"'
    if 'ирина' in tl:
        return ' — отчет "НПА меры соцподдержки"'
    return ''

def user_emoji(u):
    em = {'Катя': '\U0001F469\U0000200D\U0001F4BC',
          'Лена': '\U0001F469\U0000200D\U0001F4BB',
          'Данил': '\U0001F468\U0000200D\U0001F52C',
          'Роза': '\U0001F339',
          'Ирина': '\U0001F469\U0000200D\U0001F3EB',
          'Кирилл': '\U0001F6E0'}
    return em.get(u, '\U0001F464')

# --- HTML generation ---
parts = []
parts.append('''<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>\u0410\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439 \u2014 nasledstvo.net.ru</title>
  <link rel="stylesheet" href="theme.css">
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>
  <style>
    .activity-hero {
      text-align: center;
      padding: 40px 24px 20px;
    }
    .activity-hero .title { font-size: 28px; font-weight: 700; }
    .activity-hero .meta { color: #8b949e; font-size: 14px; margin-top: 6px; }
    .activity-hero .run-info { color: #484f58; font-size: 12px; margin-top: 4px; }
    .stats-row {
      display: flex; gap: 16px; flex-wrap: wrap;
      max-width: 900px; margin: 0 auto 24px; padding: 0 24px;
    }
    .stat-box {
      flex: 1; min-width: 140px;
      background: var(--glass-bg);
      backdrop-filter: blur(20px) saturate(1.4);
      border: 1px solid var(--glass-border);
      border-radius: 12px;
      padding: 18px 20px;
      text-align: center;
      transition: border-color 0.2s;
    }
    .stat-box:hover { border-color: rgba(255,255,255,0.12); }
    .stat-box .num { font-size: 32px; font-weight: 700; }
    .stat-box .label { font-size: 12px; color: #8b949e; margin-top: 4px; }
    .charts-section {
      max-width: 900px; margin: 0 auto 32px; padding: 0 24px;
    }
    .user-chart-card {
      background: var(--glass-bg);
      backdrop-filter: blur(20px) saturate(1.4);
      border: 1px solid var(--glass-border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 20px;
    }
    .user-chart-card:last-child { margin-bottom: 0; }
    .user-chart-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 16px;
    }
    .user-chart-header h3 {
      font-size: 16px; font-weight: 700;
      color: #e6edf3;
      margin: 0;
    }
    .user-chart-header .total-badge {
      font-size: 12px; font-weight: 600;
      color: #8b949e;
      background: rgba(255,255,255,0.06);
      padding: 4px 12px;
      border-radius: 20px;
    }
    .chart-container {
      position: relative;
      height: 220px;
      width: 100%;
    }
    .empty-state {
      text-align: center; padding: 80px 24px;
      color: #484f58;
    }
    .empty-state .icon { font-size: 48px; margin-bottom: 12px; }
    .empty-state p { font-size: 14px; }
  </style>
</head>
<body>

<div class="container">
  <a href="service_main.html" class="back">\u2190 \u0412 \u0441\u0435\u0440\u0432\u0438\u0441</a>

  <div class="activity-hero">
    <div class="title">\U0001F4CA \u0410\u043a\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u044c \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0435\u0439</div>
    <div class="meta">\u0417\u0430\u043f\u0440\u043e\u0441\u044b \u043d\u0430 \u0434\u043e\u0440\u0430\u0431\u043e\u0442\u043a\u0443 \u0437\u0430\u0434\u0430\u0447 \u043f\u043e \u0444\u043e\u0440\u043c\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044e \u043e\u0442\u0447\u0451\u0442\u043e\u0432</div>
    <div class="run-info">\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u043e: ''' + TODAY + ' ' + NOW + ' \u00b7 \u0412\u0441\u0435\u0433\u043e: ' + str(total) + '''</div>
  </div>
''')

if total == 0:
    parts.append('''
  <div class="empty-state">
    <div class="icon">\U0001F4ED</div>
    <p>\u041f\u043e\u043a\u0430 \u043d\u0435\u0442 \u0437\u0430\u043f\u0440\u043e\u0441\u043e\u0432 \u043d\u0430 \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0435 \u043f\u0440\u043e\u043c\u043f\u0442\u043e\u0432.</p>
  </div>
''')
else:
    parts.append(f'''
  <div class="stats-row">
    <div class="stat-box"><div class="num" style="color:#58a6ff;">{today_count}</div><div class="label">\u0421\u0435\u0433\u043e\u0434\u043d\u044f</div></div>
    <div class="stat-box"><div class="num" style="color:#7ee787;">{week_count}</div><div class="label">\u0417\u0430 7 \u0434\u043d\u0435\u0439</div></div>
    <div class="stat-box"><div class="num" style="color:#bc8cff;">{month_count}</div><div class="label">\u0417\u0430 30 \u0434\u043d\u0435\u0439</div></div>
    <div class="stat-box"><div class="num" style="color:#ff9000;">{total}</div><div class="label">\u0412\u0441\u0435\u0433\u043e</div></div>
  </div>

  <div class="charts-section">
''')

    for idx, (u, u_data) in enumerate(sorted_users):
        color = colors_user.get(user_color_key.get(u, ''), '#8b949e')
        count = u_data['total']
        e = user_emoji(u)
        parts.append(f'''
    <div class="user-chart-card">
      <div class="user-chart-header">
        <h3>{e} {u}</h3>
        <span class="total-badge">{count} \u0437\u0430\u043f\u0440\u043e\u0441\u043e\u0432</span>
      </div>
      <div class="chart-container" id="chart-{idx}"></div>
    </div>
''')
    parts.append('  </div>')

    # --- JS ---
    parts.append('<script>\n')
    labels_json = json.dumps(date_labels_short)
    parts.append(f'const labels = {labels_json};\n')

    for idx, (u, u_data) in enumerate(sorted_users):
        color = colors_user.get(user_color_key.get(u, ''), '#8b949e')
        counts_list = [u_data['dates'].get(d, 0) for d in dates_30]
        counts_json = json.dumps(counts_list)

        tooltip_by_date = {}
        for entry in entries:
            if entry['user'] == u:
                d = entry['date']
                if d not in tooltip_by_date:
                    tooltip_by_date[d] = []
                rn = get_report_name(entry.get('task', ''))
                tooltip_by_date[d].append(entry['request'] + rn)
        custom_data = []
        for d in dates_30:
            val = u_data['dates'].get(d, 0)
            reqs_list = tooltip_by_date.get(d, [])
            custom_data.append({'count': val, 'requests': reqs_list})
        custom_json = json.dumps(custom_data)
        max_val = max(counts_list) if counts_list else 1

        parts.append(f'''
const c{idx} = echarts.init(document.getElementById('chart-{idx}'));
c{idx}.setOption({{
  grid: {{ left: '5%', right: '5%', top: 20, bottom: 30, containLabel: true }},
  xAxis: {{
    type: 'category',
    data: labels,
    axisLabel: {{ color: '#484f58', fontSize: 10, rotate: 40, margin: 8 }},
    axisLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.08)' }} }},
    axisTick: {{ show: false }}
  }},
  yAxis: {{
    type: 'value',
    min: 0,
    splitNumber: 1,
    axisLabel: {{ color: '#8b949e', fontSize: 11 }},
    splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.04)' }} }},
    axisLine: {{ show: false }}
  }},
  tooltip: {{
    trigger: 'axis',
    backgroundColor: 'rgba(22,27,34,0.92)',
    borderColor: 'rgba(255,255,255,0.1)',
    borderWidth: 1,
    textStyle: {{ color: '#e6edf3', fontSize: 12 }},
    formatter: function(params) {{
      const i = params[0].dataIndex;
      const d = {custom_json};
      const item = d[i];
      if (item.count === 0) return '<span style="color:#484f58;">\u041d\u0435\u0442 \u0437\u0430\u043f\u0440\u043e\u0441\u043e\u0432</span>';
      let h = '<b style="color:{color};">' + params[0].axisValue + '</b>';
      h += '<br/>\U0001F4CB <b>' + item.count + '</b> \u0437\u0430\u043f\u0440\u043e\u0441' + (item.count > 1 ? '\u043e\u0432' : '');
      if (item.requests && item.requests.length > 0) {{
        h += '<br/><br/>';
        item.requests.forEach(function(r) {{
          h += '\u2022 ' + r + '<br/>';
        }});
      }}
      return h;
    }}
  }},
  series: [{{
    type: 'bar',
    data: {counts_json},
    itemStyle: {{
      color: {{
        type: 'linear',
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          {{ offset: 0, color: '{color}' }},
          {{ offset: 1, color: '{color}33' }}
        ]
      }},
      borderRadius: [4, 4, 0, 0]
    }},
    emphasis: {{
      itemStyle: {{
        color: '{color}',
        shadowBlur: 12,
        shadowColor: '{color}66'
      }}
    }}
  }}]
}});
''')

    parts.append('</script>\n')

parts.append('''
  <div class="footer">\u262D \u041B\u0443\u043D\u0442 &middot; <a href="index.html">nasledstvo.net.ru</a></div>
</div>
</body>
</html>
''')

with open(OUTPUT_PATH, 'w') as f:
    f.write(''.join(parts))

print(f"OK activity.html generated ({total} records)")
PYSCRIPT

# --- Upload ---
if [ "${1:-}" = "--upload" ]; then
  if [ -z "${TIMEWEB_HOST:-}" ] || [ -z "${TIMEWEB_WEBROOT:-}" ]; then
    echo "FAIL: TIMEWEB_HOST/TIMEWEB_WEBROOT not set"
    exit 1
  fi
  SSH_KEY="${TIMEWEB_SSH_KEY}"
  scp "$OUTPUT" "${TIMEWEB_HOST}:${TIMEWEB_WEBROOT}/activity.html"
  echo "OK uploaded"
fi
