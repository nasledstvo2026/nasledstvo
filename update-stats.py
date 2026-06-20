#!/usr/bin/env python3
"""
Update stats-inheritance.html from template.
Reads katya-stats-data.md and updates dynamic data,
preserving all styling/layout.
"""

import re, subprocess, sys
from datetime import datetime as dt, timedelta

TEMPLATE = '/home/user1/.openclaw/workspace/stats-inheritance-template.html'
LAST_FILE = '/home/user1/.openclaw/workspace/stats-inheritance.html'
DATA = '/home/user1/.openclaw/workspace/memory/katya-stats-data.md'
JSON_DATA = '/home/user1/.openclaw/workspace/memory/katya-data.json'
OUT = '/tmp/stats-inheritance.html'
PUBLISH = '/home/user1/.openclaw/workspace/publish-report.sh'

def get_yesterday():
    d = dt.now() - timedelta(days=1)
    months = ['','января','февраля','марта','апреля','мая','июня',
              'июля','августа','сентября','октября','ноября','декабря']
    return d.day, months[d.month], d.year, d.strftime('%Y-%m-%d'), d.strftime('%d.%m.%y')

def parse_data():
    with open(DATA) as f:
        text = f.read()
    
    daily = {}
    for line in text.split('\n'):
        m = re.match(r'(\d{4}-\d{2}-\d{2})\s*\|\s*Сбер:\s*(\d+)\s*\|\s*Другие:\s*(\d+)', line.strip())
        if m:
            daily[m.group(1)] = (int(m.group(2)), int(m.group(3)))
    
    monthly = {}
    for line in text.split('\n'):
        m = re.match(r'(\d{4}-\d{2})\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)', line.strip())
        if m:
            monthly[m.group(1)] = (int(m.group(2)), int(m.group(3)), int(m.group(4)))
    
    return daily, monthly

def main():
    day, month_ru, year, iso_short, iso_dot = get_yesterday()
    daily, monthly = parse_data()
    
    with open(TEMPLATE) as f:
        html = f.read()
    
    # 1. Increment version from LAST PUBLISHED file, not template
    try:
        with open(LAST_FILE) as f:
            last = f.read()
        m = re.search(r'v(\d+)', last)
    except:
        m = None
    if not m:
        m = re.search(r'v(\d+)', html)  # fallback to template
    if m:
        old_v = m.group(1)
        new_v = int(old_v) + 1
        # Replace in template (which has the baseline version)
        # Find the version tag in the output html and increment
        html = re.sub(r'v\d+', f'v{new_v}', html, count=1)
    
    # 2. Update section 2 date
    yesterday_ru = f'{day} {month_ru} {year}'
    html = re.sub(r'📅 \d+ [а-я]+ \d{4}', f'📅 {yesterday_ru}', html)
    
    # 3. Update section 2 numbers if we have data
    if iso_short in daily:
        s, o = daily[iso_short]
        # First stat-box (Сбер)
        s_color = 'var(--green)' if s == 0 else 'var(--red)'
        o_color = 'var(--green)' if o == 0 else 'var(--red)'
        
        # Replace Sber count (first occurrence with specific pattern)
        # In section 2: <div class="label">Сбер</div> ... value
        html = re.sub(
            r'(<div class="label">Сбер</div>\s*<div class="value" style="color:)[^"]+("\s*>)\d+(</div>)',
            lambda m: m.group(1) + s_color + m.group(2) + str(s) + m.group(3),
            html
        )
        # Replace Другие count in section 2
        html = re.sub(
            r'(<div class="label">Другие банки</div>\s*<div class="value" style="color:)[^"]+("\s*>)\d+(</div>)',
            lambda m: m.group(1) + o_color + m.group(2) + str(o) + m.group(3),
            html
        )
    
    # 4. Clean any comment artifacts
    html = html.replace('\n<!--', '')
    html = re.sub(r'-->\n', '\n', html)
    
    # Write output
    with open(OUT, 'w') as f:
        f.write(html)
    
    print(f'stats-inheritance.html updated — {yesterday_ru}')
    print(f'Daily records: {len(daily)}')
    
    # Publish
    r = subprocess.run([PUBLISH, OUT, 'stats-inheritance.html'],
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print('ERROR:', r.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
