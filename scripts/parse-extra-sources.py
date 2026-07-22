#!/usr/bin/env python3
"""
Сборщик жалоб из pikabu.ru, otzovik.com, findozor.net, 2gis.ru через SearXNG API.
Возвращает JSON-массив в stdout.

Запуск: python3 scripts/parse-extra-sources.py
"""

import json, sys, os, time
from urllib.request import urlopen, Request
from urllib.parse import quote, urlencode
from datetime import datetime, timezone, timedelta

SEARXNG = 'http://127.0.0.1:8888'
SHARED = '/home/user1/.openclaw/agents/shared'
SEEN_FILE = os.path.join(SHARED, 'katya-extra-seen.json')
MAX_PER_SOURCE = 5  # максимум результатов с одного источника

# Источники и поисковые запросы
SOURCES = {
    'pikabu.ru': [
        'наследство банк жалоба',
        'банк не отдаёт наследство',
        'наследство банк отзыв',
    ],
    'otzovik.com': [
        'наследство банк отзыв',
        'банк наследство жалоба',
    ],
    'findozor.net': [
        'наследство банк',
        'наследство сбербанк',
    ],
    '2gis.ru': [
        'банк наследство отзыв',
        'наследство жалоба банк',
    ],
}


def load_seen():
    """Загружает ранее найденные URL для дедупликации"""
    try:
        with open(SEEN_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('urls', []))
    except:
        return set()


def save_seen(seen_urls):
    """Сохраняет seen-URL"""
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    with open(SEEN_FILE, 'w') as f:
        json.dump({'urls': list(seen_urls), 'updated': datetime.now(timezone.utc).isoformat()},
                  f, ensure_ascii=False, indent=2)


def search_source(source, query, seen_urls, results):
    """Ищет по одному запросу в одном источнике через SearXNG API"""
    q = f'site:{source} {query}'
    params = urlencode({'q': q, 'format': 'json', 'language': 'ru-RU'})
    url = f'{SEARXNG}/search?{params}'

    try:
        req = Request(url, headers={'User-Agent': 'OpenClaw/1.0'})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'[extra] SearXNG error for {source} "{query}": {e}', file=sys.stderr)
        return

    for r in data.get('results', []):
        rurl = r.get('url', '')
        if rurl in seen_urls:
            continue
        if source not in rurl:
            continue

        title = r.get('title', '')

        # Фильтр: убрать явно нерелевантное (сериалы, фильмы)
        title_lower = title.lower()
        if any(w in title_lower for w in ['сериал', 'фильм', 'кино', 'актер', 'актёр', 'трейлер']):
            continue

        results.append({
            'title': title,
            'url': rurl,
            'source': source,
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        })
        seen_urls.add(rurl)

        if len([x for x in results if x['source'] == source]) >= MAX_PER_SOURCE:
            return


def main():
    all_results = []
    seen_urls = load_seen()

    for source, queries in SOURCES.items():
        source_count = 0
        for query in queries:
            if source_count >= MAX_PER_SOURCE:
                break
            before = len(all_results)
            search_source(source, query, seen_urls, all_results)
            source_count = len([x for x in all_results if x['source'] == source])

            # Пауза между запросами чтобы не забанили движки
            time.sleep(2)

    # Убираем дубликаты по URL и обрезаем до общего лимита
    seen_urls = set()
    unique = []
    for r in all_results:
        if r['url'] not in seen_urls:
            seen_urls.add(r['url'])
            unique.append(r)
    all_results = unique[:20]

    # Сохраняем seen
    save_seen(seen_urls)

    # Выводим результат в stdout
    print(json.dumps(all_results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
