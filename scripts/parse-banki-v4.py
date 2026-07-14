#!/usr/bin/env python3
"""
Парсер отзывов banki.ru v4 — ИСПРАВЛЕННАЯ версия

Ищет data-module-options в правильном месте страницы,
декодирует HTML-entities, парсит JSON.
"""

import json, os, re, sys, urllib.request
from datetime import datetime, timedelta
from html import unescape

SHARED = '/home/user1/.openclaw/agents/shared'
RAW_FILE = os.path.join(SHARED, 'katya-raw.json')
DATA_FILE = os.path.join(SHARED, 'katya-data.json')
STATS_FILE = os.path.join(SHARED, 'katya-stats-data.md')

KEYWORDS = [
    'наследств', 'умер', 'умерш', 'наследник', 'наследодател',
    'завещание', 'завещательн', 'свидетельств о смерти',
    'вклад умерш', 'счет умерш', 'выплата наслед',
    'вступил в наслед', 'отказ наслед', 'свидетельство о смерти',
    'восстановл срок', 'наследственн', 'похороны',
]

STOPKEYWORDS = [
    '115-фз', 'антиотмывочн', 'сомнительн', 'ркл',
    'обнал', 'фишинг', 'похитил', 'украл',
]

def fetch(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
        'Accept': 'text/html',
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"FETCH ERROR: {e}")
        return None

def extract_responses(html):
    """Извлекает responses.data из data-module-options"""
    # Ищем data-module-options, который содержит "responses"
    # Ищем по кускам — data-module-options с ключевым словом responses
    for m in re.finditer(r'data-module-options=["\']({.*?})["\']', html, re.DOTALL):
        raw = m.group(1)
        if 'responses' not in raw:
            continue
        
        # Декодируем HTML entities
        raw_decoded = unescape(raw)
        
        # Бывает JSON с обратными слешами — убираем экранирование
        raw_decoded = raw_decoded.replace('\\/', '/')
        
        try:
            data = json.loads(raw_decoded)
            if 'responses' in data:
                items = data['responses'].get('data', [])
                if items:
                    print(f"  Found block: {len(raw_decoded)} bytes, {len(items)} items")
                    return items
        except json.JSONDecodeError:
            continue
    
    return []

def parse_date(dt_str):
    if not dt_str:
        return None
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
        try:
            return datetime.strptime(str(dt_str)[:19], fmt).date()
        except:
            pass
    return None

def main():
    target_dates = set()
    args = sys.argv[1:]
    if args and args[0] == '--today':
        target_dates.add(datetime.now().strftime('%Y-%m-%d'))
    elif args and args[0] == '--date' and len(args) > 1:
        target_dates.add(args[1])
    else:
        y = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        t = datetime.now().strftime('%Y-%m-%d')
        target_dates.update([y, t])
    
    target_str = list(target_dates)[0]
    print(f"[banki parser v4] Date: {target_str}")
    
    all_responses = []
    
    for page in range(1, 4):
        url = f'https://www.banki.ru/services/responses/list/?page={page}'
        print(f"Page {page}...", end=' ', flush=True)
        html = fetch(url)
        if not html:
            print("FAIL")
            continue
        
        items = extract_responses(html)
        print(f"{len(items)} raw items")
        
        for item in items:
            title = item.get('title', '')
            text = item.get('text', '')
            text_clean = re.sub(r'<[^>]+>', '', text).strip()
            
            company = item.get('company', {})
            if isinstance(company, dict):
                bank_name = company.get('name', 'Неизвестно')
            else:
                bank_name = str(company)
            
            date_create = str(item.get('dateCreate', ''))
            item_id = item.get('id', '')
            
            combined = (title + ' ' + text_clean).lower()
            has_kw = any(k in combined for k in KEYWORDS)
            is_stop = any(s in combined for s in STOPKEYWORDS)
            
            parsed_date = parse_date(date_create)
            date_str = str(parsed_date) if parsed_date else date_create[:10]
            
            all_responses.append({
                'id': item_id,
                'date': date_str,
                'bank': bank_name,
                'title': title,
                'text': text_clean[:300],
                'has_keyword': has_kw,
                'is_stopword': is_stop,
            })
        
        # Проверка свежести
        recent_ids = set()
        for r in all_responses[-30:]:
            for t in target_dates:
                if t in r.get('date', ''):
                    recent_ids.add(t)
        if not recent_ids and page >= 2:
            print("No fresh data, stopping")
            break
    
    # Фильтр
    matched = [r for r in all_responses if r.get('has_keyword') and not r.get('is_stopword')]
    stop_matched = [r for r in all_responses if r.get('has_keyword') and r.get('is_stopword')]
    
    # Если за вчера ничего нет — показываем всё что нашли за последние дни
    if not matched:
        matched_by_kw = [r for r in all_responses if r.get('has_keyword')]
        if matched_by_kw:
            print(f"\nNo matching for {target_str}, showing all keyword matches:")
            for r in matched_by_kw[:5]:
                print(f"  {r['bank']}: {r['title'][:60]} (date: {r['date']})")
    
    print(f"\nTotal parsed: {len(all_responses)}")
    print(f"Keyword matches: {len([r for r in all_responses if r.get('has_keyword')])}")
    print(f"Valid complaints: {len(matched)}")
    if stop_matched:
        print(f"Filtered out: {len(stop_matched)}")
    
    # Save
    if not matched:
        matched = [{
            'date': target_str,
            'bank': '-',
            'title': 'Новых жалоб по наследству не найдено',
            'text': f'banki.ru за {target_str}: не найдено',
            'url': '',
            'source': 'banki.ru'
        }]
    
    with open(RAW_FILE, 'w', encoding='utf-8') as f:
        json.dump(matched, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(matched)} to {RAW_FILE}")
    
    # katya-data.json
    existing = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    if not isinstance(existing, list):
        existing = []
    
    seen_urls = {e.get('url', '') for e in existing if e.get('url')}
    banki_base = 'https://www.banki.ru/services/responses/bank/response/'
    
    new_count = 0
    for r in matched:
        if r.get('title', '').startswith('Новых'):
            continue
        url = f'{banki_base}{r.get("id", "")}/'
        if url in seen_urls:
            continue
        seen_urls.add(url)
        existing.append({
            'date': r.get('date', target_str),
            'bank': r.get('bank', 'Неизвестно'),
            'title': r.get('title', ''),
            'description': r.get('text', '')[:300],
            'url': url,
            'source': 'banki.ru'
        })
        new_count += 1
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"Added {new_count} new to {DATA_FILE}")
    
    # Stats
    real_results = [r for r in matched if not r.get('title', '').startswith('Новых')]
    sber_count = sum(1 for r in real_results if 'сбер' in r.get('bank', '').lower())
    other_count = len(real_results) - sber_count
    
    line = f"\n{target_str} | Сбер: {sber_count} | Другие: {other_count}"
    banks = {}
    for r in real_results:
        b = r.get('bank', '')
        if b:
            banks[b] = banks.get(b, 0) + 1
    if banks:
        line += ' | ' + ', '.join(f'{b} {c}' for b, c in sorted(banks.items(), key=lambda x: -x[1]))
    
    with open(STATS_FILE, 'a', encoding='utf-8') as f:
        f.write(line)
    print(f"Stats: {target_str} | Сбер: {sber_count} | Другие: {other_count}")
    
    if real_results:
        print(f"\n=== Found: {len(real_results)} ===")
        for r in real_results:
            print(f"  [{r['bank']}] {r['title'][:60]} ({r['date']})")
    else:
        print("\nNothing found")

if __name__ == '__main__':
    main()
