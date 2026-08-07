#!/bin/bash
# Brave search helper with retry: ./bsearch.sh "query" [count]
Q="$1"
COUNT="${2:-6}"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$Q")
for attempt in 1 2 3 4; do
  curl -s -m 25 -A "$UA" -o /tmp/brs.html -w "%{http_code}" "https://search.brave.com/search?q=${ENC}&source=web" > /tmp/brs.code
  code=$(cat /tmp/brs.code)
  if [ "$code" = "200" ]; then break; fi
  sleep $((attempt * 6))
done
python3 -c "
import sys, re, html
data = open('/tmp/brs.html', encoding='utf-8', errors='ignore').read()
main = data[data.find('<div id=\"main\">'):]
n = 0
for m in re.finditer(r'<a[^>]+href=\"(https?://[^\"]+)\"[^>]*>(.*?)</a>', main, re.S):
    url = m.group(1)
    if any(x in url for x in ['brave.com','cdn.search','github.com','mozilla.org','status.brave','torproject']): continue
    txt = html.unescape(re.sub(r'<[^>]+>', '', m.group(2))).strip()
    if not txt: continue
    n += 1
    print('URL:', url[:220])
    print('T:', txt[:220])
    print('---')
    if n >= int('$COUNT'): break
print('[HTTP ' + open('/tmp/brs.code').read().strip() + ']')
"
