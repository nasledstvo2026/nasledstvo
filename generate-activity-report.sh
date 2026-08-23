#!/bin/bash
# generate-activity-report.sh — генерирует activity.html для GitHub Pages

DATE_LABEL="24 июля 2026"
DATE_ISO="2026-07-24"
REPORTS_TODAY=5
ACTIVE_USERS=2
TOTAL_PAGES=48

# File sizes from ls -la
KATYA_SIZE=$(du -h /home/user1/.openclaw/workspace/report-katya.html 2>/dev/null | awk '{print $1}')
STATS_SIZE=$(du -h /home/user1/.openclaw/workspace/stats-inheritance.html 2>/dev/null | awk '{print $1}')
KATYA_OTHER_SIZE=$(du -h /home/user1/.openclaw/workspace/report-katya-other.html 2>/dev/null | awk '{print $1}')
LENA_SIZE=$(du -h /home/user1/.openclaw/workspace/report-lena.html 2>/dev/null | awk '{print $1}')
TASKS_SIZE=$(du -h /home/user1/.openclaw/workspace/tasks.html 2>/dev/null | awk '{print $1}')
INDEX_SIZE=$(du -h /home/user1/.openclaw/workspace/index.html 2>/dev/null | awk '{print $1}')

cat > /home/user1/.openclaw/workspace/activity.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Активность — Лунт</title>
    <link rel="stylesheet" href="theme.css">
    <link rel="stylesheet" href="style.css">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0e1a; color: #e0e6f0; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { font-size: 1.8em; border-bottom: 2px solid #2a3a5c; padding-bottom: 10px; }
        h2 { font-size: 1.3em; margin-top: 30px; color: #8ab4f8; }
        .date-badge { background: #1a2a4a; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; color: #8ab4f8; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #1e2d42; }
        th { color: #8ab4f8; font-weight: 500; }
        .stat-card { background: #111827; border: 1px solid #1e2d42; border-radius: 12px; padding: 16px 20px; margin: 10px 0; display: inline-block; }
        .stat-card .num { font-size: 2em; font-weight: 700; color: #4ade80; }
        .stat-card .label { font-size: 0.85em; color: #94a3b8; }
        .event { padding: 8px 0; border-left: 3px solid #2a3a5c; padding-left: 14px; margin: 6px 0; }
        .event time { color: #64748b; font-size: 0.85em; }
        .report-link { color: #8ab4f8; text-decoration: none; }
        .report-link:hover { text-decoration: underline; }
        .footer { margin-top: 40px; padding-top: 15px; border-top: 1px solid #1e2d42; font-size: 0.85em; color: #64748b; }
    </style>
</head>
<body>
<div class="container">
    <h1>📊 Активность системы <span class="date-badge">HTMLEOF
echo "    ${DATE_LABEL}</span></h1>" >> /home/user1/.openclaw/workspace/activity.html

cat >> /home/user1/.openclaw/workspace/activity.html << 'HTMLEOF'

    <div style="display: flex; gap: 12px; flex-wrap: wrap; margin: 20px 0;">
        <div class="stat-card">
            <div class="num">HTMLEOF
echo "            ${REPORTS_TODAY}" >> /home/user1/.openclaw/workspace/activity.html
echo '            <div class="label">отчёта сегодня</div>' >> /home/user1/.openclaw/workspace/activity.html
echo '        </div>' >> /home/user1/.openclaw/workspace/activity.html
echo '        <div class="stat-card">' >> /home/user1/.openclaw/workspace/activity.html
echo "            <div class=\"num\">${ACTIVE_USERS}</div>" >> /home/user1/.openclaw/workspace/activity.html
echo '            <div class="label">пользователя активно</div>' >> /home/user1/.openclaw/workspace/activity.html
echo '        </div>' >> /home/user1/.openclaw/workspace/activity.html
echo '        <div class="stat-card">' >> /home/user1/.openclaw/workspace/activity.html
echo "            <div class=\"num\">${TOTAL_PAGES}</div>" >> /home/user1/.openclaw/workspace/activity.html
echo '            <div class="label">всего страниц на сайте</div>' >> /home/user1/.openclaw/workspace/activity.html
echo '        </div>' >> /home/user1/.openclaw/workspace/activity.html
echo '    </div>' >> /home/user1/.openclaw/workspace/activity.html

cat >> /home/user1/.openclaw/workspace/activity.html << 'HTMLEOF'
    <h2>📄 Отчёты за сегодня</h2>
    <table>
        <tr><th>Отчёт</th><th>Время</th><th>Размер</th></tr>
HTMLEOF

echo "        <tr><td><a class=\"report-link\" href=\"report-katya.html\">report-katya.html</a> — жалобы Кати</td><td>07:33</td><td>${KATYA_SIZE:-?}</td></tr>" >> /home/user1/.openclaw/workspace/activity.html
echo "        <tr><td><a class=\"report-link\" href=\"stats-inheritance.html\">stats-inheritance.html</a> — статистика наследства</td><td>08:11</td><td>${STATS_SIZE:-?}</td></tr>" >> /home/user1/.openclaw/workspace/activity.html
echo "        <tr><td><a class=\"report-link\" href=\"report-katya-other.html\">report-katya-other.html</a> — другие банки Кати</td><td>08:34</td><td>${KATYA_OTHER_SIZE:-?}</td></tr>" >> /home/user1/.openclaw/workspace/activity.html
echo "        <tr><td><a class=\"report-link\" href=\"report-lena.html\">report-lena.html</a> — новости Лены</td><td>20:04</td><td>${LENA_SIZE:-?}</td></tr>" >> /home/user1/.openclaw/workspace/activity.html
echo "        <tr><td><a class=\"report-link\" href=\"tasks.html\">tasks.html</a> — задачи системы</td><td>21:00</td><td>${TASKS_SIZE:-?}</td></tr>" >> /home/user1/.openclaw/workspace/activity.html
echo '        <tr><td><a class="report-link" href="activity.html">activity.html</a> — этот отчёт</td><td>23:50</td><td>—</td></tr>' >> /home/user1/.openclaw/workspace/activity.html

cat >> /home/user1/.openclaw/workspace/activity.html << 'HTMLEOF'
    </table>

    <h2>📋 Плановые обновления</h2>
    <table>
        <tr><th>Страница</th><th>Время</th><th>Размер</th></tr>
        <tr><td><a class="report-link" href="tasks.html">tasks.html</a> — задачи системы</td><td>00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00</td><td>HTMLEOF
echo "            ${TASKS_SIZE:-?}</td></tr>" >> /home/user1/.openclaw/workspace/activity.html
echo "        <tr><td><a class=\"report-link\" href=\"index.html\">index.html</a> — главная (OpenProject)</td><td>00:26</td><td>${INDEX_SIZE:-?}</td></tr>" >> /home/user1/.openclaw/workspace/activity.html

cat >> /home/user1/.openclaw/workspace/activity.html << 'HTMLEOF'
    </table>

    <h2>👤 События дня</h2>
    <div class="event">
        <time>07:33</time> — <strong>Катя</strong>: обновлён report-katya.html (жалобы по наследству)
    </div>
    <div class="event">
        <time>08:11</time> — <strong>Статистика</strong>: обновлён stats-inheritance.html
    </div>
    <div class="event">
        <time>08:34</time> — <strong>Катя</strong>: обновлён report-katya-other.html (прочие банки)
    </div>
    <div class="event">
        <time>20:04</time> — <strong>Лена</strong>: обновлён report-lena.html (новости наследства)
    </div>
    <div class="event">
        <time>21:00</time> — <strong>Система</strong>: обновлён tasks.html
    </div>
    <div class="event">
        <time>23:50</time> — <strong>Лунт</strong>: сгенерирован activity.html
    </div>

    <h2>📡 Система</h2>
    <table>
        <tr><th>Компонент</th><th>Статус</th></tr>
        <tr><td>Яндекс.XML (XMLRiver)</td><td>✅ работает</td></tr>
        <tr><td>LegalMCP (юридический сервер)</td><td>✅ работает (84/100 запросов)</td></tr>
        <tr><td>GitHub Pages</td><td>✅ работает</td></tr>
        <tr><td>Dropbox SDK</td><td>✅ доступен</td></tr>
        <tr><td>Cron-задачи</td><td>✅ активны</td></tr>
        <tr><td>OpenProject Tunnel</td><td>✅ активен</td></tr>
    </table>

    <div class="footer">
HTMLEOF
echo "        Сгенерировано Лунтом ☽ · ${DATE_ISO} 23:50 MSK" >> /home/user1/.openclaw/workspace/activity.html

cat >> /home/user1/.openclaw/workspace/activity.html << 'HTMLEOF'
    </div>
</div>
</body>
</html>
HTMLEOF

echo "✅ activity.html generated"
