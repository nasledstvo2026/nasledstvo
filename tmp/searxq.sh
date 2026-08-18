#!/bin/bash
# SearXNG query with strict filtering: allowed domains + date range 2026-08-12..2026-08-19
Q="$1"
curl -s --max-time 30 "http://127.0.0.1:8888/search?q=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$Q")&format=json&language=ru-RU&pageno=1&categories=news" \
| python3 -c "
import sys, json, datetime
try:
    data = json.load(sys.stdin)
except Exception as e:
    print('PARSE_ERROR', e); sys.exit()
domains = ('tass.ru','rbc.ru','kommersant.ru','vedomosti.ru','rg.ru','pravo.gov.ru','notariat.ru','banki.ru','duma.gov.ru','consultant.ru','garant.ru','nalog.gov.ru','sfr.gov.ru','mintrud.gov.ru')
lo = datetime.date(2026,8,12); hi = datetime.date(2026,8,19)
seen = set()
for r in data.get('results', []):
    url = r.get('url','')
    import urllib.parse
    host = urllib.parse.urlparse(url).netloc.lower()
    host = host[4:] if host.startswith('www.') else host
    if host not in domains: continue
    pd = r.get('publishedDate') or r.get('pubdate') or ''
    d = None
    for fmt in ('%Y-%m-%dT%H:%M:%S','%Y-%m-%d %H:%M:%S','%Y-%m-%d'):
        try:
            d = datetime.datetime.strptime(pd[:19], fmt).date(); break
        except: pass
    if d is None: continue
    if not (lo <= d <= hi): continue
    title = r.get('title','').strip()
    if not title or title in seen: continue
    seen.add(title)
    print(f'{d} | {title} | {url}')
" 2>/dev/null
