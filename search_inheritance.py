#!/usr/bin/env python3
"""Comprehensive inheritance complaint data collection (archived — SearXNG removed)"""

import json
import urllib.request
import urllib.parse
import time
import re
import os

# SearXNG удалён (14.07.2026) — скрипт сохранён для истории

QUERIES = [
    "site:banki.ru наследство Сбербанк жалоба",
    "site:banki.ru наследство ВТБ жалоба",
    "site:banki.ru наследство Т-Банк жалоба",
    "site:banki.ru наследство ПСБ жалоба",
    "site:banki.ru наследство отказ выплат",
    "site:otzovik.com наследство банк вклад",
    "site:pikabu.ru наследство банк вклад",
    "site:sravni.ru наследство вклад отказ",
    "site:vc.ru наследство банк вклад",
    '"вклад умершего" жалоба',
    '"свидетельство о праве на наследство" отказ банк',
    "наследство вклад умершего банк отказ выплатить",
    "жалоба наследство вклад Сбербанк не выплачивает",
    "наследство вклад отказали выплатить",
]

MONTH_MAP = {
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'мая': 5,
    'июн': 6, 'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12,
}

def search_searxng(query, time_range="year", pageno=1):
    """Search — disabled, SearXNG removed"""
    print(f"  [SearXNG удалён] Пропускаю запрос: {query[:50]}")
    return []
            data = json.loads(resp.read())
        return data.get('results', [])
    except Exception as e:
        print(f"  Error: {e}")
        return []

def classify_bank(url, title, content):
    text = (url + ' ' + title + ' ' + content).lower()
    
    if any(x in text for x in ['сбербанк', 'сбер', 'sberbank']):
        return 'sber'
    if any(x in text for x in ['втб', 'vtb', 'внешторг']):
        return 'vtb'
    if any(x in text for x in ['т-банк', 'тбанк', 'тиньк', 'tbank', 't-bank', 'tinkoff']):
        return 'tbank'
    if any(x in text for x in ['промсвязьбанк', 'псб', 'psb']):
        return 'psb'
    if any(x in text for x in ['яндекс', 'yandex']):
        return 'yandex'
    if any(x in text for x in ['совкомбанк', 'sovcombank']):
        return 'sovcombank'
    if any(x in text for x in ['альфа', 'alfa']):
        return 'alfa'
    if any(x in text for x in ['газпромбанк', 'газпром']):
        return 'gazprom'
    if any(x in text for x in ['россельхоз', 'рсхб']):
        return 'rshb'
    if any(x in text for x in ['почта банк', 'почтабанк']):
        return 'pochta'
    if any(x in text for x in ['открытие']):
        return 'otkritie'
    if any(x in text for x in ['росбанк']):
        return 'rosbank'
    if any(x in text for x in ['райффайзен']):
        return 'raiffeisen'
    
    return 'other'

def extract_dates(text):
    """Extract (year, month) pairs from text"""
    dates = []
    # Pattern: Russian month name + year
    for m in re.finditer(r'(янв|фев|мар|апр|май|мая|июн|июл|авг|сен|окт|ноя|дек)\w*\s*\.?\s*(\d{4})', text, re.IGNORECASE):
        month = MONTH_MAP.get(m.group(1).lower()[:3])
        year = int(m.group(2))
        if month and year in [2024, 2025, 2026]:
            dates.append((year, month))
    
    # Pattern: dd.mm.yyyy or dd/mm/yyyy
    for m in re.finditer(r'(\d{2})[./](\d{2})[./](\d{4})', text):
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if month >= 1 and month <= 12 and year in [2024, 2025, 2026]:
            dates.append((year, month))
    
    # Pattern: yyyy-mm-dd
    for m in re.finditer(r'(\d{4})[-/](\d{2})[-/](\d{2})', text):
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if month >= 1 and month <= 12 and year in [2024, 2025, 2026]:
            dates.append((year, month))
    
    return dates

def is_complaint(url, title, content):
    text = (title + ' ' + content).lower()
    
    # banki.ru responses
    if '/responses/' in url:
        # Not all responses are complaints. Check for inheritance keywords
        inheritance_kw = ['наследств', 'вклад умерш', 'свидетельств о прав']
        if not any(k in text for k in inheritance_kw):
            return False
        # Check if it's explicitly a problem (rating 1-2 or problem keywords)
        problem_kw = ['не выплач', 'отказ', 'не отда', 'не могу', 'проблем', 'игнорир',
                     'превыша', 'затягив', 'морозят', 'тянут', 'отписки']
        # Check rating in content
        rating_is_low = 'оценка 1' in text[:100] or 'оценка 2' in text[:100]
        has_problem = any(k in text for k in problem_kw)
        return rating_is_low or has_problem
    
    # pikabu - check for complaint
    if 'pikabu' in url:
        complaint_kw = ['наследств', 'вклад умерш', 'не выплач', 'отказ', 'проблем']
        return any(k in text for k in complaint_kw)
    
    # otzovik - reviews are usually complaints
    if 'otzovik' in url:
        inheritance_kw = ['наследств', 'вклад умерш', 'свидетельств о прав']
        if any(k in text for k in inheritance_kw):
            return True
    
    # General check for any page
    complaint_indicators = ['жалоб', 'не выплач', 'отказ выплат', 'отказывается', 'не отда',
                           'игнорир', 'затягив', 'морозят', 'мурыжат', 'отписки']
    info_indicators = ['как получить', 'как оформить', 'инструкция', 'совет', 'нюансы',
                      'важно знать', 'разъяснен', 'судебная практика', 'пошаговая']
    
    inheritance_kw = ['наследств', 'вклад умерш', 'свидетельств о прав']
    if any(k in text for k in inheritance_kw):
        c_count = sum(1 for ind in complaint_indicators if ind in text)
        i_count = sum(1 for ind in info_indicators if ind in text)
        return c_count > 0 and c_count >= i_count
    
    return False

def main():
    all_results = {}  # url -> info dict
    
    # Phase 1: Broad searches for 2025
    print("=== Phase 1: Searching 2025 ===")
    for i, query in enumerate(QUERIES):
        q_with_year = query + " 2025"
        print(f"[{i+1}/{len(QUERIES)}] 2025: {query[:50]}...")
        
        for page in [1, 2]:
            results = search_searxng(q_with_year, "year", page)
            if not results:
                break
            for r in results:
                url = r.get('url', '')
                if not url or url in all_results:
                    continue
                title = r.get('title', '')
                content = r.get('content', '')
                
                # Check relevance
                text = (url + ' ' + title + ' ' + content).lower()
                if not any(kw in text for kw in ['наследств', 'вклад умерш', 'свидетельств о прав']):
                    continue
                
                if is_complaint(url, title, content):
                    dates = extract_dates(content + ' ' + title)
                    bank = classify_bank(url, title, content)
                    all_results[url] = {
                        'url': url, 'title': title, 'content': content[:300],
                        'dates': dates, 'bank': bank
                    }
            time.sleep(0.3)
    
    # Phase 2: Broad searches for 2026
    print("\n=== Phase 2: Searching 2026 ===")
    for i, query in enumerate(QUERIES):
        q_with_year = query + " 2026"
        print(f"[{i+1}/{len(QUERIES)}] 2026: {query[:50]}...")
        
        for page in [1, 2]:
            results = search_searxng(q_with_year, "year", page)
            if not results:
                break
            for r in results:
                url = r.get('url', '')
                if not url or url in all_results:
                    continue
                title = r.get('title', '')
                content = r.get('content', '')
                
                text = (url + ' ' + title + ' ' + content).lower()
                if not any(kw in text for kw in ['наследств', 'вклад умерш', 'свидетельств о прав']):
                    continue
                
                if is_complaint(url, title, content):
                    dates = extract_dates(content + ' ' + title)
                    bank = classify_bank(url, title, content)
                    all_results[url] = {
                        'url': url, 'title': title, 'content': content[:300],
                        'dates': dates, 'bank': bank
                    }
            time.sleep(0.3)
    
    # Phase 3: Additional searches with specific NOT (site:banki.ru) queries to catch other platforms
    extra_queries = [
        '"не выплачивают наследство" жалоба',
        '"отказ в выплате наследства" банк',
        '"вклад умершего" банк жалоба',
        '"свидетельство о праве на наследство" "выплата"',
    ]
    print("\n=== Phase 3: Extra queries ===")
    for i, query in enumerate(extra_queries):
        print(f"[{i+1}/{len(extra_queries)}] {query[:40]}...")
        for page in [1]:
            results = search_searxng(query, "year", page)
            if not results:
                continue
            for r in results:
                url = r.get('url', '')
                if not url or url in all_results:
                    continue
                title = r.get('title', '')
                content = r.get('content', '')
                
                text = (url + ' ' + title + ' ' + content).lower()
                if not any(kw in text for kw in ['наследств', 'вклад умерш', 'свидетельств о прав']):
                    continue
                
                if is_complaint(url, title, content):
                    dates = extract_dates(content + ' ' + title)
                    bank = classify_bank(url, title, content)
                    all_results[url] = {
                        'url': url, 'title': title, 'content': content[:300],
                        'dates': dates, 'bank': bank
                    }
            time.sleep(0.3)
    
    # Phase 4: Month-specific searches to fill gaps
    print("\n=== Phase 4: Month-specific deep searches ===")
    months_2025 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    months_2026 = [1, 2, 3, 4, 5, 6]
    
    for year, months in [(2025, months_2025), (2026, months_2026)]:
        for month in months:
            month_names = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                          'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
            mn = month_names[month - 1]
            
            queries = [
                f'{mn} {year} наследство банк жалоба',
                f'{mn} {year} "вклад умершего" банк',
                f'{mn} {year} свидетельство о праве на наследство',
            ]
            for q in queries:
                results = search_searxng(q, "month" if year < 2026 or (year == 2026 and month < 6) else "week", 1)
                for r in results:
                    url = r.get('url', '')
                    if not url or url in all_results:
                        continue
                    title = r.get('title', '')
                    content = r.get('content', '')
                    
                    text = (url + ' ' + title + ' ' + content).lower()
                    if not any(kw in text for kw in ['наследств', 'вклад умерш', 'свидетельств о прав']):
                        continue
                    
                    if is_complaint(url, title, content):
                        dates = extract_dates(content + ' ' + title)
                        bank = classify_bank(url, title, content)
                        all_results[url] = {
                            'url': url, 'title': title, 'content': content[:300],
                            'dates': dates, 'bank': bank
                        }
                time.sleep(0.3)
    
    # Print summary
    print("\n" + "=" * 80)
    print("ALL COMPLAINTS FOUND")
    print("=" * 80)
    
    # Group by (year, month)
    by_month = {}
    no_date_items = []
    
    for url, info in all_results.items():
        if info['dates']:
            # Take the most relevant date (first found)
            key = (info['dates'][0][0], info['dates'][0][1])
        else:
            # Try to infer from URL content
            text = info['content'] + ' ' + info['title']
            year_2025 = '2025' in text
            year_2026 = '2026' in text
            if year_2025 and not year_2026:
                key = (2025, 0)
            elif year_2026 and not year_2025:
                key = (2026, 0)
            else:
                no_date_items.append(info)
                continue
        
        if key not in by_month:
            by_month[key] = {'sber': 0, 'other': 0, 'total': 0, 'items': []}
        
        by_month[key]['total'] += 1
        if info['bank'] == 'sber':
            by_month[key]['sber'] += 1
        else:
            by_month[key]['other'] += 1
        by_month[key]['items'].append(info)
    
    # Print by month
    for key in sorted(by_month.keys()):
        year, month = key
        month_str = f"{month:02d}" if month > 0 else "??"
        data = by_month[key]
        print(f"{year}-{month_str} | Сбер: {data['sber']} | Другие: {data['other']} | Всего: {data['total']}")
        for item in data['items']:
            bank_label = {'sber': 'СБЕР', 'vtb': 'ВТБ', 'tbank': 'Т-Банк', 'psb': 'ПСБ',
                         'yandex': 'Яндекс', 'alfa': 'Альфа', 'other': 'Другой',
                         'sovcombank': 'Совкомбанк', 'pochta': 'Почта', 'otkritie': 'Открытие',
                         'rosbank': 'Росбанк', 'raiffeisen': 'Райффайзен',
                         'gazprom': 'Газпромбанк', 'rshb': 'РСХБ', 'mts': 'МТС'}.get(item['bank'], item['bank'])
            dates_str = ', '.join([f"{d[0]}-{d[1]:02d}" for d in item['dates']])
            print(f"  [{bank_label}] {item['url'][:80]}")
            print(f"  Date: {dates_str}")
            print(f"  {item['title'][:120]}")
        print()
    
    # Items without clear date
    if no_date_items:
        print(f"\n--- ITEMS WITHOUT CLEAR DATE ({len(no_date_items)}) ---")
        for item in no_date_items:
            bank_label = item['bank']
            print(f"  [{bank_label}] {item['url'][:80]}")
            print(f"  {item['title'][:120]}")
    
    # Save raw data
    os.makedirs('/home/user1/.openclaw/workspace/search_results/parsed', exist_ok=True)
    with open('/home/user1/.openclaw/workspace/search_results/parsed/all_data.json', 'w') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\nTotal unique complaints: {len(all_results)}")
    total_sber = sum(1 for v in all_results.values() if v['bank'] == 'sber')
    total_other = sum(1 for v in all_results.values() if v['bank'] != 'sber')
    print(f"Sberbank: {total_sber}, Other: {total_other}")

if __name__ == '__main__':
    main()
