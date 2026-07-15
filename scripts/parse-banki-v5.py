#!/usr/bin/env python3
"""
Парсер banki.ru v5 — поиск жалоб по наследству.

ФИЛЬТРАЦИЯ:
- title ИЛИ text должны содержать ancestry-слова
- ИСКЛЮЧАЕМ: 115-ФЗ, кредитки, вклады (без наследства)
- Дата: только целевая (вчера)
"""

import json, os, re, sys, urllib.request
from datetime import datetime, timedelta
from html import unescape

SHARED = '/home/user1/.openclaw/agents/shared'
RAW_FILE = os.path.join(SHARED, 'katya-banki-raw.json')
DATA_FILE = os.path.join(SHARED, 'katya-data.json')
STATS_FILE = os.path.join(SHARED, 'katya-stats-banki.md')

# Строгие ключевые слова — ТОЛЬКО наследство
INCLUDE = {
    'наследств', 'умерш', 'наследник', 'наследодател',
    'завещание', 'завещательн', 'свидетельств о смерти',
    'отказ наслед', 'вступил в наслед', 'вклад умерш',
    'счет умерш', 'выплата наслед', 'свидетельство о смерти',
    'наследственн', 'отказ в выплат', 'смерть вклад',
    'смерть наслед', 'умер родствен', 'умер муж',
    'умер жен', 'умер родител', 'умер отец', 'умер мать',
    'умер сын', 'умер дочер', 'умер брат', 'умер сестра',
    'умер супруг', 'смерть заемщ', 'после смерти',
    'отказ выдать наслед',
}

# Исключения — отсекаем не-наследство
EXCLUDE = {
    '115-фз', 'антиотмывочн', 'сомнительн', 'ркл',
    'обнал', 'фишинг', 'похитил', 'украл', 'мошенническ',
    'сброс парол', 'аккаунт', 'доступ к личном',
    'ипотек', 'автокредит', 'потребительск',
    'кредитная карт', 'дебетовая карт', 'обналичиван',
}

# Слова, которые часто встречаются с наследством — УСИЛИВАЮТ match
BOOST = {
    'банк не выдает', 'отказывают', 'отказали', 'не отдают',
    'не могу получить', 'справка', 'нотариус', 'свидетельство',
    'госпошлин', 'вклад', 'депозит', 'счет', 'денег',
    'выплат', 'похороны', 'погребение',
}

def fetch(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None

def extract_page(html):
    for m in re.finditer(r'data-module-options=["\']({.*?})["\']', html, re.DOTALL):
        raw = m.group(1)
        if 'responses' not in raw:
            continue
        raw_decoded = unescape(raw).replace('\\/', '/')
        try:
            data = json.loads(raw_decoded)
            if 'responses' in data:
                return data['responses'].get('data', [])
        except:
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

def is_inheritance_complaint(title, text):
    combined = (title + ' ' + text).lower()
    
    # Проверка на exclude — сразу отсекаем
    for ex in EXCLUDE:
        if ex in combined:
            return False
    
    # Проверка на include
    has_include = any(kw in combined for kw in INCLUDE)
    if not has_include:
        return False
    
    # Проверка на boost — если есть include + boost = жалоба
    has_boost = any(b in combined for b in BOOST)
    
    # Без boost — всё равно берём, если include сработал и не exclude
    return True

def main():
    args = sys.argv[1:]
    if args and args[0] == '--today':
        target = datetime.now().strftime('%Y-%m-%d')
    elif args and args[0] == '--date' and len(args) > 1:
        target = args[1]
    else:
        target = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"[banki v5] Target: {target}")
    
    all_results = []
    
    for page in range(1, 5):
        url = f'https://www.banki.ru/services/responses/list/?page={page}'
        print(f"  Page {page}...", end=' ', flush=True)
        html = fetch(url)
        if not html:
            print("FAIL")
            continue
        
        items = extract_page(html)
        if not items:
            print("no data")
            continue
        print(f"{len(items)} items")
        
        for item in items:
            title = item.get('title', '')
            text = re.sub(r'<[^>]+>', '', item.get('text', '')).strip()
            date_create = str(item.get('dateCreate', ''))
            parsed = parse_date(date_create)
            
            if not parsed:
                continue
            date_str = str(parsed)
            
            # Проверяем дату — только целевая
            if date_str != target:
                continue
            
            if not is_inheritance_complaint(title, text):
                continue
            
            company = item.get('company', {})
            bank = company.get('name', 'Неизвестно') if isinstance(company, dict) else str(company)
            
            all_results.append({
                'id': item.get('id', ''),
                'date': date_str,
                'bank': bank,
                'title': title,
                'text': text[:500],
                'url': f'https://www.banki.ru/services/responses/bank/response/{item.get("id", "")}/',
            })
    
    print(f"\nFound: {len(all_results)} for {target}")
    for r in all_results:
        print(f"  [{r['bank']}] {r['title'][:60]}")
    
    # Save raw
    with open(RAW_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results if all_results else [{
            'date': target, 'bank': '-',
            'title': 'Новых жалоб по наследству не найдено',
            'text': f'banki.ru за {target}: не найдено',
            'url': '', 'source': 'banki.ru'
        }], f, ensure_ascii=False, indent=2)
    
    # Update katya-data.json
    existing = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            existing = json.load(f)
    if not isinstance(existing, list):
        existing = []
    
    seen = {e.get('url', '') for e in existing if e.get('url')}
    new = 0
    for r in all_results:
        if r['url'] in seen:
            continue
        seen.add(r['url'])
        existing.append({
            'date': r['date'], 'bank': r['bank'],
            'title': r['title'], 'description': r['text'][:300],
            'url': r['url'], 'source': 'banki.ru'
        })
        new += 1
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    print(f"Added {new} to data file")
    
    # Stats
    sber = sum(1 for r in all_results if 'сбер' in r['bank'].lower())
    other = len(all_results) - sber
    line = f"\n{target} | Сбер: {sber} | Другие: {other}"
    banks = {}
    for r in all_results:
        banks[r['bank']] = banks.get(r['bank'], 0) + 1
    if banks:
        line += ' | ' + ', '.join(f'{b} {c}' for b, c in sorted(banks.items(), key=lambda x: -x[1]))
    with open(STATS_FILE, 'a', encoding='utf-8') as f:
        f.write(line)
    print(f"Stats: {line}")

if __name__ == '__main__':
    main()
