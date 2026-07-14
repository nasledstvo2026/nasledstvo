#!/usr/bin/env python3
"""
Парсер отзывов banki.ru — вытаскивает JSON из data-module-options
на странице https://www.banki.ru/services/responses/list/

Затем фильтрует по ключевым словам наследства и дате,
сохраняет в shared-файлы для Кати.
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
    'обнал', 'мошенническ',
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
    # Ищем data-module-options с responses
    m = re.search(r'data-module-options=[\'"]({.*?responses.*?})[\'"]', html, re.DOTALL)
    if not m:
        print("No data-module-options found")
        return []
    
    raw = m.group(1)
    # unescape HTML entities
    raw = unescape(raw)
    
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        # Попробуем найти только responses.data
        m2 = re.search(r'"responses"\s*:\s*{.*?"data"\s*:\s*(\[.*?\])\s*}', raw, re.DOTALL)
        if m2:
            try:
                data = json.loads('{"data":' + m2.group(1) + '}')
                return data.get('data', [])
            except:
                pass
        return []
    
    responses = data.get('responses', {}).get('data', [])
    return responses

def parse_date(date_str):
    """Парсит дату из разных форматов"""
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%d.%m.%Y']:
        try:
            return datetime.strptime(date_str[:19], fmt).date()
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
    print(f"[banki parser v3] Target date: {target_str}")
    
    all_responses = []
    max_pages = 3
    
    for page in range(1, max_pages + 1):
        url = f'https://www.banki.ru/services/responses/list/?page={page}'
        print(f"Page {page}...", end=' ', flush=True)
        html = fetch(url)
        if not html:
            print("FAIL")
            continue
        
        items = extract_responses(html)
        print(f"{len(items)} items")
        
        for item in items:
            title = item.get('title', '')
            text = item.get('text', '')
            # Убираем HTML-теги
            text_clean = re.sub(r'<[^>]+>', '', text).strip()
            company = item.get('company', {})
            if isinstance(company, dict):
                bank_name = company.get('name', 'Неизвестно')
            else:
                bank_name = str(company)
            
            date_create = item.get('dateCreate', '')
            item_id = item.get('id', '')
            grade = item.get('grade', '')
            
            combined = (title + ' ' + text_clean).lower()
            
            # Проверка на ключевые слова
            has_keyword = any(k.lower() in combined for k in KEYWORDS)
            is_stop = any(s.lower() in combined for s in STOPKEYWORDS)
            
            # Дата
            parsed_date = parse_date(date_create)
            date_str = str(parsed_date) if parsed_date else date_create[:10]
            
            entry = {
                'id': item_id,
                'date': date_str,
                'bank': bank_name,
                'title': title,
                'text': text_clean[:300],
                'grade': grade,
                'has_keyword': has_keyword,
                'is_stopword': is_stop,
            }
            all_responses.append(entry)
        
        # Если на странице нет свежих — стоп
        has_recent = any(
            r.get('date') in target_dates
            for r in all_responses[-30:]
        )
        if not has_recent and page >= 2:
            print("No recent data, stopping")
            break
    
    # Фильтрация
    matched = [r for r in all_responses if r.get('has_keyword') and not r.get('is_stopword')]
    stop_matched = [r for r in all_responses if r.get('has_keyword') and r.get('is_stopword')]
    
    print(f"\nTotal parsed: {len(all_responses)}")
    print(f"Matching: {len(matched)}")
    if stop_matched:
        print(f"Stop-filtered: {len(stop_matched)} ({', '.join(r['bank'] + ': ' + r['title'][:30] for r in stop_matched)})")
    
    # Если ничего не найдено — создаём placeholder
    if not matched:
        matched = [{
            'date': target_str,
            'bank': '-',
            'title': 'Новых жалоб по наследству не найдено',
            'text': f'Поиск по banki.ru за {target_str} не дал результатов по ключевым словам наследства',
            'url': '',
            'source': 'banki.ru'
        }]
    
    # Сохраняем raw
    with open(RAW_FILE, 'w', encoding='utf-8') as f:
        json.dump(matched, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(matched)} to {RAW_FILE}")
    
    # Обновляем katya-data.json
    existing = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    
    if not isinstance(existing, list):
        existing = []
    
    seen_urls = set()
    for e in existing:
        u = e.get('url', '')
        if u:
            seen_urls.add(u)
    
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
    
    # Статистика
    sber_count = sum(1 for r in matched if 'сбер' in r.get('bank', '').lower())
    other_count = len(matched) - sber_count - (1 if matched and matched[0].get('title', '').startswith('Новых') else 0)
    
    date_str = target_str
    line = f"\n{date_str} | Сбер: {sber_count} | Другие: {other_count}"
    
    banks = {}
    for r in matched:
        b = r.get('bank', '')
        if b and b != '-':
            banks[b] = banks.get(b, 0) + 1
    if banks:
        line += ' | ' + ', '.join(f'{b} {c}' for b, c in sorted(banks.items(), key=lambda x: -x[1]))
    
    with open(STATS_FILE, 'a', encoding='utf-8') as f:
        f.write(line)
    print(f"Stats updated: {date_str} | Сбер: {sber_count} | Другие: {other_count}")
    
    if matched and not matched[0].get('title', '').startswith('Новых'):
        print(f"\n=== Найденные жалобы ===")
        for r in matched:
            print(f"  [{r['bank']}] {r['title'][:60]}")
    else:
        print(f"\nНовых жалоб не найдено")

if __name__ == '__main__':
    main()
