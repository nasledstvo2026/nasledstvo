#!/usr/bin/env python3
"""
Парсер жалоб по наследству с banki.ru для search-agent (Катя)

Алгоритм:
1. Получает через urllib страницу списка отзывов banki.ru
2. Ищет JSON-блок в HTML (banki.ru встраивает данные в JSON-LD)
3. Извлекает отзывы за указанные даты
4. Фильтрует по ключевым словам наследства
5. Сохраняет в shared-файлы
"""

import json, os, re, sys, urllib.request
from datetime import datetime, timedelta

SHARED = '/home/user1/.openclaw/agents/shared'
RAW_FILE = os.path.join(SHARED, 'katya-raw.json')
DATA_FILE = os.path.join(SHARED, 'katya-data.json')
STATS_FILE = os.path.join(SHARED, 'katya-stats-data.md')

KEYWORDS = [
    'наследств', 'умер', 'умерш', 'наследник', 'наследодател',
    'завещание', 'завещательн', 'свидетельств', 'отказ наслед',
    'вклад умерш', 'счет умерш', 'выплата наслед', 'нотариус',
    'вступил в наслед', 'отказ в выпалт', 'свидетельство о смерти',
    'восстановл срок', 'наследственн', 'похороны', 'наслед масса',
]

STOPKEYWORDS = [
    '115-фз', 'антиотмывочн', 'сомнительн', 'ркл',
    'обнал', 'мошенническ', 'похитил', 'украл', 'фишинг',
]

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'ru-RU,ru;q=0.9',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  FETCH ERROR {url}: {e}")
        return None

def parse_responses_from_page(html, target_dates):
    """Извлекает отзывы из HTML, иcпользуя JSON-LD и data-атрибуты"""
    results = []
    seen_ids = set()

    # Метод 1: JSON-LD blocks
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
            if isinstance(data, dict):
                data = [data]
            for item in data:
                rid = str(item.get('@id', item.get('identifier', '')))
                if rid in seen_ids:
                    continue
                seen_ids.add(rid)
                desc = item.get('description', '')
                name = item.get('name', '')
                combined = (name + ' ' + desc).lower()
                
                # Проверка на стоп-слова
                is_stop = any(s in combined for s in STOPKEYWORDS)
                
                # Проверка на ключевые слова
                has_kw = any(k in combined for k in KEYWORDS)
                
                if has_kw or is_stop:
                    results.append({
                        'id': rid,
                        'title': name,
                        'description': desc[:500],
                        'date_raw': str(item.get('datePublished', '')),
                        'company': str(item.get('author', {}).get('name', '')) if isinstance(item.get('author'), dict) else '',
                        'is_stopword': is_stop,
                        'url': str(item.get('url', '')),
                    })
        except:
            pass

    # Метод 2: data-response-id блоки
    for m in re.finditer(r'data-response-id="(\d+)"(.*?)(?=<article|</article|data-response-id)', html, re.DOTALL):
        rid = m.group(1)
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        block = m.group(2)

        title = ''
        t = re.search(r'response__title[^>]*>(.*?)</(?:span|div)>', block, re.DOTALL)
        if t:
            title = re.sub(r'<[^>]+>', '', t.group(1)).strip()

        text = ''
        tx = re.search(r'response__text[^>]*>(.*?)(?:</div>|<a)', block, re.DOTALL)
        if tx:
            text = re.sub(r'<[^>]+>', '', tx.group(1)).strip()

        dt = ''
        d = re.search(r'datetime="([^"]+)"', block)
        if d:
            dt = d.group(1)
        if not dt:
            d = re.search(r'(\d{2}\.\d{2}\.\d{4})', block)
            if d:
                dt = d.group(1)

        company = ''
        c = re.search(r'response__company[^>]*>(.*?)</', block, re.DOTALL)
        if c:
            company = re.sub(r'<[^>]+>', '', c.group(1)).strip()

        url = ''
        u = re.search(r'href="(/services/responses/[^"]*)"', block, re.DOTALL)
        if u:
            url = 'https://www.banki.ru' + u.group(1)

        combined = (title + ' ' + text).lower()
        is_stop = any(s in combined for s in STOPKEYWORDS)
        has_kw = any(k in combined for k in KEYWORDS)

        if has_kw or is_stop:
            results.append({
                'id': rid,
                'title': title,
                'description': text[:300],
                'date_raw': dt,
                'company': company,
                'is_stopword': is_stop,
                'url': url,
            })

    # Фильтр по датам
    filtered = []
    for r in results:
        dr = r.get('date_raw', '')
        # Парсим дату
        parsed_date = None
        for fmt in ['%Y-%m-%d', '%d.%m.%Y']:
            try:
                parsed_date = datetime.strptime(dr[:10], fmt).date()
                break
            except:
                pass
        if parsed_date and str(parsed_date) in target_dates:
            filtered.append(r)
        elif not dr:
            # Если даты нет — оставляем (проверим потом)
            pass
    # Если нет по датам — берём всё, что подходит по ключам
    if not filtered:
        filtered = [r for r in results if not r.get('is_stopword')]

    return filtered

def main():
    args = sys.argv[1:]
    if args and args[0] == '--today':
        target = [datetime.now().strftime('%Y-%m-%d')]
    elif args and args[0] == '--date':
        target = [args[1]]
    else:
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        target = [yesterday, today]

    print(f"Target dates: {target}")

    all_results = []
    for page in range(1, 4):
        url = f'https://www.banki.ru/services/responses/list/?page={page}'
        print(f"Fetching page {page}...")
        html = fetch(url)
        if not html:
            continue
        print(f"  Got {len(html)} bytes")
        results = parse_responses_from_page(html, set(target + [str(datetime.now().year)]))
        print(f"  Found {len(results)} potential matches")
        all_results.extend(results)

        # Если нет результатов с датой — может отзывы устаревшие
        has_fresh = any(
            any(t in r.get('date_raw', '') for t in target)
            for r in results
        )
        if not has_fresh and page >= 2:
            print("  No fresh data, stopping")
            break

    if not all_results:
        all_results = [{
            'date': target[0] if target else datetime.now().strftime('%Y-%m-%d'),
            'bank': '-',
            'title': 'Новых жалоб не найдено',
            'description': 'Поиск по banki.ru не дал результатов за указанный период',
            'url': '',
            'source': 'banki.ru'
        }]

    # Сохраняем raw
    with open(RAW_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(all_results)} to {RAW_FILE}")

    # Обновляем katya-data.json
    existing = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f)

    seen_urls = {e.get('url', '') for e in existing if e.get('url')}
    real_new = []
    for r in all_results:
        if isinstance(r, dict) and r.get('title') == 'Новых жалоб не найдено':
            continue
        if r.get('is_stopword'):
            continue
        if r.get('url') and r['url'] in seen_urls:
            continue
        entry = {
            'date': target[0] if target else datetime.now().strftime('%Y-%m-%d'),
            'bank': r.get('company', 'Неизвестно'),
            'title': r.get('title', ''),
            'description': r.get('description', '')[:300],
            'url': r.get('url', ''),
            'source': 'banki.ru'
        }
        existing.append(entry)
        if r.get('url'):
            seen_urls.add(r['url'])
        real_new.append(r)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"Added {len(real_new)} new entries to {DATA_FILE}")

    # Статистика
    sber_count = sum(1 for r in real_new if 'сбер' in r.get('company', '').lower())
    other_count = len(real_new) - sber_count
    date_str = target[0]
    line = f"\n{date_str} | Сбер: {sber_count} | Другие: {other_count}"
    
    banks_detail = {}
    for r in real_new:
        b = r.get('company', 'Неизвестно')
        if b and b != '-':
            banks_detail[b] = banks_detail.get(b, 0) + 1
    if banks_detail:
        line += ' | ' + ', '.join(f'{b} {c}' for b, c in sorted(banks_detail.items(), key=lambda x: -x[1]))

    with open(STATS_FILE, 'a', encoding='utf-8') as f:
        f.write(line)
    print(f"Updated {STATS_FILE}: {date_str} | Сбер: {sber_count} | Другие: {other_count}")

    # Вывод найденного
    if real_new:
        print(f"\n=== Found {len(real_new)} complaints ===")
        for r in real_new:
            print(f"  [{r.get('company','?')}] {r.get('title','')[:60]}")
    else:
        print(f"\nNo new complaints found.")

if __name__ == '__main__':
    main()
