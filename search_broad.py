#!/usr/bin/env python3
"""Broad search without year constraints to catch all inheritance complaints"""

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

def search_searxng(query, pageno=1):
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
    if any(x in text for x in ['открытие']):
        return 'otkritie'
    if any(x in text for x in ['почта банк', 'почтабанк']):
        return 'pochta'
    if any(x in text for x in ['газпромбанк', 'газпром']):
        return 'gazprom'
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
    text = (title + ' ' + content).lower()
    inheritance_kw = ['наследств', 'вклад умерш', 'свидетельств о прав']
    if not any(k in text for k in inheritance_kw):
        return False
    if '/responses/' in url:
        rating_low = 'оценка 1' in text[:200] or 'оценка 2' in text[:200]
        problem_kw = ['не выплач', 'отказ', 'не отда', 'не могу', 'проблем', 'игнорир']
        return rating_low or any(k in text for k in problem_kw)
    if 'pikabu' in url:
        return any(k in text for k in inheritance_kw)
    if 'otzovik' in url:
        return any(k in text for k in inheritance_kw)
    problem_kw = ['жалоб', 'не выплач', 'отказ выплат', 'отказывается', 'не отда',
                  'не могу получ', 'отказали', 'проблем', 'скрыва', 'затяг']
    info_kw = ['как получить', 'как оформить', 'инструкция', 'совет']
    c_count = sum(1 for i in problem_kw if i in text)
    i_count = sum(1 for i in info_kw if i in text)
    return c_count > 0 and c_count >= i_count

def main():
    all_results = {}
    
    # Pure broad queries without year restriction
    queries = [
        '"наследство" "вклад" "банк" жалоба',
        '"вклад умершего" банк',
        '"свидетельство о праве на наследство" отказ',
        '"не выплачивают наследство" банк',
        '"отказались выплачивать" наследство',
        '"не могу получить" "наследство" банк',
        'жалоба "наследство" Сбербанк',
        '"наследство" "Сбербанк" "не выплачивает"',
        '"наследство" ВТБ жалоба',
        '"наследство" "Промсвязьбанк" жалоба',
        '"наследство" "Т-Банк" жалоба',
        '"наследство" "Альфа-банк" жалоба',
        '"наследство" "Совкомбанк" жалоба',
        '"наследство" "Почта банк" жалоба',
        'банк не отдает наследство',
        'банк отказал в наследстве',
        'не выдают наследство в банке',
    ]
    
    for i, q in enumerate(queries):
        print(f"[{i+1}/{len(queries)}] {q[:55]}")
        for page in [1, 2]:
            results = search_searxng(q, page)
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
                if is_inheritance_complaint(url, title, content):
                    dates = extract_dates(content + ' ' + title)
                    bank = classify_bank(url, title, content)
                    all_results[url] = {
                        'url': url, 'title': title, 'content': content[:300],
                        'dates': dates, 'bank': bank
                    }
            time.sleep(0.5)
    
    # Group by month
    by_month = {}
    no_date = []
    
    for url, info in all_results.items():
        if info['dates']:
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
    
    print("\n" + "=" * 80)
    print("BROAD SEARCH RESULTS")
    print("=" * 80)
    
    for key in sorted(by_month.keys()):
        year, month = key
        month_str = f"{month:02d}" if month > 0 else "??"
        data = by_month[key]
        print(f"\n{year}-{month_str} | Сбер: {data['sber']} | Другие: {data['other']} | Всего: {data['total']}")
        for item in data['items']:
            bank_label = {'sber': 'СБЕР'}.get(item['bank'], item['bank'].upper() if len(item['bank']) < 8 else item['bank'])
            dates_str = ', '.join([f"{d[0]}-{d[1]:02d}" for d in item['dates']]) if item['dates'] else 'нет'
            print(f"  [{bank_label}] {dates_str}: {item['title'][:100]}")
    
    if no_date:
        print(f"\n=== NO DATE ({len(no_date)}) ===")
        for item in no_date:
            print(f"  [{item['bank']}] {item['title'][:100]}")
    
    print(f"\n\nNEW items found: {len(all_results)}")

if __name__ == '__main__':
    main()
