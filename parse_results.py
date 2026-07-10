#!/usr/bin/env python3
import json
import os
import re
import glob

# Month name mapping (Russian to number)
MONTH_MAP = {
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'мая': 5,
    'июн': 6, 'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12,
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}

# Bank classification
def classify_bank(url, title, content):
    text = (url + ' ' + title + ' ' + content).lower()
    
    # Sberbank indicators
    if any(x in text for x in ['сбербанк', 'сбер', 'sberbank', 'sber']):
        return 'sber'
    
    # Other banks
    if any(x in text for x in ['втб', 'vtb']):
        return 'vtb'
    if any(x in text for x in ['т-банк', 'тбанк', 'тиньк', 'tbank', 't-bank', 'tinkoff']):
        return 'tbank'
    if any(x in text for x in ['промсвязьбанк', 'псб', 'psb']):
        return 'psb'
    if any(x in text for x in ['яндекс', 'yandex', 'яндекс-банк']):
        return 'yandex'
    if any(x in text for x in ['совкомбанк', 'sovcombank']):
        return 'sovcombank'
    if any(x in text for x in ['альфа', 'alfa', 'альфа-банк']):
        return 'alfa'
    if any(x in text for x in ['газпромбанк', 'газпром']):
        return 'gazprom'
    if any(x in text for x in ['россельхоз', 'рсхб']):
        return 'rshb'
    if any(x in text for x in ['почта банк', 'почтабанк']):
        return 'pochta'
    if any(x in text for x in ['мтс банк', 'мтсбанк']):
        return 'mts'
    if any(x in text for x in ['открытие']):
        return 'otkritie'
    if any(x in text for x in ['росбанк']):
        return 'rosbank'
    if any(x in text for x in ['райффайзен']):
        return 'raiffeisen'
    if any(x in text for x in ['юнистрим']):
        return 'unistream'
    
    # If it mentions a specific bank name not in the list
    bank_keywords = ['банк']
    if any(x in text for x in bank_keywords) and not any(x in text for x in ['наследств', 'вклад умерш']):
        # Try to detect the bank name
        pass
    
    return 'other'

def extract_month_year(content, url, title):
    text = content + ' ' + url + ' ' + title
    
    # Pattern: "месяц. 2025 г." or "месяц 2025 г." or "месяц.2025"
    patterns = [
        r'(янв|фев|мар|апр|май|мая|июн|июл|авг|сен|окт|ноя|дек)\w*\s*\.?\s*(\d{4})',
        r'(\d{2})[./](\d{2})[./](\d{4})',
        r'(\d{4})[./-](\d{2})[./-](\d{2})',
        r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s*\.?\s*(\d{4})',
    ]
    
    results = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            if m.lastindex == 2:
                month_str = m.group(1).lower()[:3]
                year = m.group(2)
                if month_str in MONTH_MAP:
                    results.append((int(year), MONTH_MAP[month_str], m.group(0)))
            elif m.lastindex == 3:
                # dd.mm.yyyy or yyyy-mm-dd
                if m.group(1).isdigit() and int(m.group(1)) > 31:
                    year = int(m.group(1))
                    month = int(m.group(2))
                    results.append((year, month, m.group(0)))
                elif m.group(3).isdigit() and int(m.group(3)) > 31:
                    day = int(m.group(1))
                    month = int(m.group(2))
                    year = int(m.group(3))
                    if month >= 1 and month <= 12 and year >= 2024:
                        results.append((year, month, m.group(0)))
    
    return results

def is_complaint(title, content):
    """Check if the result is a complaint vs informational article"""
    text = (title + ' ' + content).lower()
    
    # These indicate a complaint/negative review
    complaint_indicators = [
        'жалоб', 'отказ', 'не выплач', 'не отда', 'игнорир', 'плохо', 
        'проблем', 'невозмож', 'превыша', 'не могу', 'не выпл',
        'тянут', 'затягив', 'морозят', 'черный список', 'никогда',
        'бесполезн', 'ужас', 'отвратит', 'кошмар', 'безобрази',
        'наруша', 'обманыв', 'мурыжат', 'отписки', 'бардак',
        'долго ждать', 'не получил', 'не хотят', 'сволочи',
    ]
    
    # These indicate informational content
    info_indicators = [
        'как получить', 'как оформить', 'инструкц', 'совет',
        'как проверить', 'как отказаться', 'нюансы', 'важно знать',
        'разъяснен', 'судебная практика', 'новости', 'новость',
        'что делать если', 'пошаговая', 'памятка',
    ]
    
    # Check for complaint-specific patterns on banki.ru
    if '/responses/' in url:
        # banki.ru response pages are user reviews
        # Low rating (1.0 is complaint)
        if 'оценка 1' in content.lower() or 'оценка 2' in content.lower():
            # But check bank name context
            complaint_keywords = ['наследств', 'вклад умерш', 'свидетельств о прав', 
                                  'отказ выплат', 'не выплач', 'не отда']
            if any(kw in text for kw in complaint_keywords):
                return True
        # Even without explicit rating, if it's a response about inheritance problems
        if any(kw in text for kw in ['не выплач', 'отказ', 'не отда', 'проблем']):
            if 'наследств' in text or 'вклад умерш' in text or 'свидетельств о прав' in text:
                return True
    elif '/questions-answers/' in url:
        return False  # Questions not necessarily complaints
    
    complaint_count = sum(1 for ind in complaint_indicators if ind in text)
    info_count = sum(1 for ind in info_indicators if ind in text)
    
    # If we see keywords like наследство + complaint pattern
    if ('наследств' in text or 'вклад умерш' in text or 'свидетельств о прав' in text):
        if complaint_count > 0 and complaint_count >= info_count:
            return True
    
    return False

def extract_date_from_url_banki(url):
    """Try to extract date from banki.ru response URL or content pattern"""
    # The dates are in the content like "автор: user  сент. 2025 г."
    pass

# Process all JSON files
all_results = {}

data_dir = '/home/user1/.openclaw/workspace/search_results'

for year_dir in ['2025', '2026']:
    for json_file in glob.glob(os.path.join(data_dir, year_dir, '*.json')):
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        for result in data.get('results', []):
            url = result.get('url', '')
            title = result.get('title', '')
            content = result.get('content', '')
            
            # Check if relevant to inheritance
            text = (url + ' ' + title + ' ' + content).lower()
            relevance_keywords = ['наследств', 'вклад умерш', 'свидетельств о прав']
            if not any(kw in text for kw in relevance_keywords):
                continue
            
            # Check if it's a complaint
            if not is_complaint(title, content):
                continue
            
            # Get dates
            dates = extract_month_year(content, url, title)
            
            # Get bank
            bank = classify_bank(url, title, content)
            
            # Create unique key by URL to avoid duplicates
            if url not in all_results:
                all_results[url] = {
                    'url': url,
                    'title': title,
                    'content': content[:300],
                    'dates': dates,
                    'bank': bank,
                }

# Print summary
print("=" * 80)
print("ALL COMPLAINTS FOUND")
print("=" * 80)

# Group by month
by_month = {}
for url, info in all_results.items():
    dates = info['dates']
    bank = info['bank']
    
    if not dates:
        # Try to infer year from context
        text = info['content'] + ' ' + info['title']
        # Check if 2025 or 2026 mentioned without month
        year_2025 = '2025' in text
        year_2026 = '2026' in text
        
        if year_2025 and not year_2026:
            key = (2025, 0)  # 0 = unknown month
        elif year_2026 and not year_2025:
            key = (2026, 0)
        else:
            # Just look at which search directory found it
            key = (0, 0)  # truly unknown
    else:
        # Take the most relevant date
        key = (dates[0][0], dates[0][1])
    
    if key not in by_month:
        by_month[key] = {'sber': 0, 'other': 0, 'total': 0, 'items': []}
    
    by_month[key]['total'] += 1
    if bank == 'sber':
        by_month[key]['sber'] += 1
    else:
        by_month[key]['other'] += 1
    
    by_month[key]['items'].append(info)

# Print by month sorted
for key in sorted(by_month.keys()):
    year, month = key
    data = by_month[key]
    month_str = f"{month:02d}" if month > 0 else "??"
    
    bank_detail = ', '.join([f"{i['bank']}: {i['title'][:60]}" for i in data['items']])
    
    print(f"{year}-{month_str} | Сбер: {data['sber']} | Другие: {data['other']} | Всего: {data['total']}")
    for item in data['items']:
        print(f"  [{item['bank']}] {item['url']}")
        dates_str = ', '.join([f"{d[0]}-{d[1]:02d}" for d in item['dates']])
        print(f"  Dates: {dates_str}")
        print(f"  Title: {item['title'][:100]}")
        print()

# Also print items without clear date
print("\n" + "=" * 80)
print("ITEMS WITHOUT CLEAR DATE")
print("=" * 80)
for url, info in all_results.items():
    if not info['dates']:
        print(f"[{info['bank']}] {info['url']}")
        print(f"  {info['title'][:120]}")
        print(f"  {info['content'][:200]}")
        print()
