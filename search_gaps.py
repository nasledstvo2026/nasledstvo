#!/usr/bin/env python3
"""Fill gaps in inheritance complaint data - focus on missing months"""

import json
import urllib.request
import urllib.parse
import time
import re

# SearXNG удалён (14.07.2026) — поиск через web_search не реализован
# Скрипт сохранён для истории, не используется

MONTH_MAP = {
    'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'мая': 5,
    'июн': 6, 'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12,
}

def search_searxng(query, time_range="year", pageno=1):
    print(f"  [SearXNG удалён] Пропускаю запрос: {query[:50]}")
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
    if any(x in text for x in ['почта банк', 'почтабанк']):
        return 'pochta'
    return 'other'

def extract_dates(text):
    dates = []
    for m in re.finditer(r'(янв|фев|мар|апр|май|мая|июн|июл|авг|сен|окт|ноя|дек)\w*\s*\.?\s*(\d{4})', text, re.IGNORECASE):
        month = MONTH_MAP.get(m.group(1).lower()[:3])
        year = int(m.group(2))
        if month and year in [2024, 2025, 2026]:
            dates.append((year, month))
    for m in re.finditer(r'(\d{2})[./](\d{2})[./](\d{4})', text):
        d, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12 and year in [2024, 2025, 2026]:
            dates.append((year, month))
    return dates

def is_inheritance_complaint(url, title, content):
    """Check if result is about inheritance and is a complaint"""
    text = (title + ' ' + content).lower()
    
    # Must be about inheritance
    inheritance_kw = ['наследств', 'вклад умерш', 'свидетельств о прав', 'наслед']
    if not any(k in text for k in inheritance_kw):
        return False
    
    # banki.ru responses
    if '/responses/' in url:
        if any(k in text for k in inheritance_kw):
            rating_low = 'оценка 1' in text[:200] or 'оценка 2' in text[:200]
            problem_kw = ['не выплач', 'отказ', 'не отда', 'не могу', 'проблем', 'игнорир',
                         'превыша', 'затягив', 'морозят']
            has_problem = any(k in text for k in problem_kw)
            return rating_low or has_problem
    
    # pikabu
    if 'pikabu' in url:
        problem_kw = ['наследств', 'вклад умерш', 'не выплач', 'отказ', 'проблем', 'скрыва']
        return any(k in text for k in problem_kw)
    
    # otzovik
    if 'otzovik' in url:
        return any(k in text for k in inheritance_kw)
    
    # General
    problem_kw = ['жалоб', 'не выплач', 'отказ выплат', 'отказывается', 'не отда', 'не могу получить',
                 'не выдают', 'отказали', 'проблем']
    info_kw = ['как получить', 'как оформить', 'инструкция', 'совет', 'нюансы']
    
    if any(k in text for k in inheritance_kw):
        c_count = sum(1 for i in problem_kw if i in text)
        i_count = sum(1 for i in info_kw if i in text)
        return c_count > 0 and c_count >= i_count
    
    return False

def main():
    all_results = {}
    
    # Load existing data
    try:
        with open('/home/user1/.openclaw/workspace/search_results/parsed/all_data.json', 'r') as f:
            all_results = json.load(f)
    except:
        pass
    
    already_seen = set(all_results.keys())
    
    # === GAP FILLING: Jan-Jun 2025 ===
    print("=== Filling Jan-Jun 2025 ===")
    gap_months = {
        2025: range(1, 7),
        2026: range(3, 7),
    }
    
    # Very targeted queries for early 2025
    targeted_queries = [
        # Jan 2025
        '"не выплатили наследство" 2025',
        '"не выплачивают наследство" 2025',
        '"вклад умершего" 2025 отказ',
        '"свидетельство о праве на наследство" банк 2025',
        '"наследство вклад" Сбербанк 2025',
        '"отказ в выплате" наследство банк 2025',
        '"наследники" "не могут получить" вклад 2025',
        'судебная практика наследство вклад банк 2025',
        # Without year - current
        '"сбербанк" "наследство" "не выплачивает" жалоба',
        '"сбербанк" "отказался выдавать" наследство',
        '"отказали в выплате" наследства',
        '"не отдают наследство" банк',
        '"получить наследство" "банк отказывается"',
        '"выплата наследства" "отказ" банк',
        '"вклад умершего" "сбербанк" жалоба',
        '"право на наследство" "банк" "выплата"',
    ]
    
    for q in targeted_queries:
        print(f"  Query: {q[:60]}")
        for page in [1, 2]:
            results = search_searxng(q, "year", page)
            if not results:
                break
            for r in results:
                url = r.get('url', '')
                if not url or url in already_seen:
                    continue
                title = r.get('title', '')
                content = r.get('content', '')
                
                if is_inheritance_complaint(url, title, content):
                    dates = extract_dates(content + ' ' + title)
                    bank = classify_bank(url, title, content)
                    all_results[url] = {
                        'url': url, 'title': title, 'content': content[:300],
                        'dates': dates, 'bank': bank
                    }
                    already_seen.add(url)
            time.sleep(0.5)
    
    # === Month-specific searches ===
    print("\n=== Month-specific searches ===")
    month_names = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
                  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
    
    for year in [2025, 2026]:
        months = range(1, 7) if year == 2025 else range(3, 7)
        for month in months:
            mn = month_names[month - 1]
            
            qs = [
                f'{mn} {year} "наследство" банк жалоба',
                f'{mn} {year} "вклад умершего"',
                f'{mn} {year} "свидетельство о праве на наследство" банк',
                f'{mn} {year} "отказ" наследство банк',
            ]
            for q in qs:
                print(f"  {year}-{month:02d}: {q[:50]}")
                results = search_searxng(q, "year", 1)
                for r in results:
                    url = r.get('url', '')
                    if not url or url in already_seen:
                        continue
                    title = r.get('title', '')
                    content = r.get('content', '')
                    
                    if is_inheritance_complaint(url, title, content):
                        dates = extract_dates(content + ' ' + title)
                        bank = classify_bank(url, title, content)
                        all_results[url] = {
                            'url': url, 'title': title, 'content': content[:300],
                            'dates': dates, 'bank': bank
                        }
                        already_seen.add(url)
                time.sleep(0.4)
    
    # === Print ALL results organized by month ===
    by_month = {}
    no_date = []
    
    for url, info in all_results.items():
        if info['dates']:
            # Pick most common date or first
            key = (info['dates'][0][0], info['dates'][0][1])
        else:
            text = info['content'] + ' ' + info['title']
            if '2025' in text and '2026' not in text:
                key = (2025, 0)
            elif '2026' in text and '2025' not in text:
                key = (2026, 0)
            else:
                no_date.append(info)
                continue
        
        if key not in by_month:
            by_month[key] = {'sber': 0, 'other': 0, 'total': 0, 'items': []}
        
        by_month[key]['total'] += 1
        if info['bank'] == 'sber':
            by_month[key]['sber'] += 1
        else:
            by_month[key]['other'] += 1
        by_month[key]['items'].append(info)
    
    print("\n\n")
    print("=" * 80)
    print("INHERITANCE COMPLAINTS BY MONTH")
    print("=" * 80)
    
    for key in sorted(by_month.keys()):
        year, month = key
        month_str = f"{month:02d}" if month > 0 else "??"
        data = by_month[key]
        print(f"\n{year}-{month_str} | Сбер: {data['sber']} | Другие: {data['other']} | Всего: {data['total']}")
        for item in data['items']:
            bank_label = {'sber': 'СБЕР', 'vtb': 'ВТБ', 'tbank': 'Т-Банк', 'psb': 'ПСБ',
                         'yandex': 'Яндекс', 'alfa': 'Альфа', 'other': '??',
                         'sovcombank': 'Совкомбанк', 'pochta': 'Почта', 'otkritie': 'Открытие',
                         'rosbank': 'Росбанк', 'raiffeisen': 'Райффайзен',
                         'gazprom': 'Газпромбанк', 'rshb': 'РСХБ', 'mts': 'МТС'}.get(item['bank'], item['bank'])
            dates_str = ', '.join([f"{d[0]}-{d[1]:02d}" for d in item['dates']]) if item['dates'] else 'нет даты'
            print(f"  [{bank_label}] {dates_str}: {item['title'][:100]}")
            print(f"    {item['url'][:90]}")
    
    if no_date:
        print(f"\n\n=== NO DATE ({len(no_date)}) ===")
        for item in no_date:
            print(f"  [{item['bank']}] {item['title'][:100]}")
            print(f"    {item['url'][:90]}")
    
    print(f"\n\nTOTAL: {len(all_results)} unique complaints")
    sber_count = sum(1 for v in all_results.values() if v['bank'] == 'sber')
    other_count = sum(1 for v in all_results.values() if v['bank'] != 'sber')
    print(f"Sberbank: {sber_count}, Other: {other_count}")
    
    # Save
    with open('/home/user1/.openclaw/workspace/search_results/parsed/all_data_v2.json', 'w') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    main()
