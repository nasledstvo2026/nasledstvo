#!/usr/bin/env python3
"""
Парсер banki.ru — тихий режим, только JSON в stdout.
Собирает отзывы через data-module-options, фильтрует по наследству.
"""

import json, sys, re, urllib.request
from datetime import datetime, timezone, timedelta

BANKI_URL = "https://www.banki.ru/services/responses/list/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

INCLUDE = [
    'наследств', 'наследник', 'наследница', 'наследодатель',
    'умерш', 'умер', 'умершая', 'умершего', 'умершей',
    'скончал', 'скончалась', 'скончавшегося',
    'завещани', 'завещание', 'завещанию',
    'нотариус', 'нотариуса', 'нотариальн',
    'свидетельство о праве', 'свидетельства о праве',
    'принятие наследств', 'отказ от наследств',
    'вступить в наследств', 'оформить наследств', 'доля в наследств',
    'наследственн', 'наследство',
    'потеря кормильц', 'потерял', 'потеряла',
]

EXCLUDE = [
    '115-фз', '115фз', 'мошенническ', 'мошенник', 'аферист',
    'кредитн', 'ипотек', 'рефинансирован', 'банкротств',
    'кредитная карт', 'кредитка', 'дебетовая карт',
]

BOOST = ['отказ', 'отказал', 'отказали', 'нотариус', 'свидетельств', 'принял']

def fetch_page(page=1):
    """Получает HTML страницы отзывов"""
    url = f"{BANKI_URL}?page={page}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception:
        return None

def parse_data_module(html):
    """Извлекает отзывы из data-module-options JSON"""
    matches = re.findall(r'data-module-options=\'({.+?})\'', html)
    results = []
    
    for match in matches:
        try:
            data = json.loads(match)
            responses = data.get('responses', [])
            for resp in responses:
                bank = resp.get('bankName', '') or ''
                title = resp.get('title', '') or ''
                text = resp.get('text', '') or ''
                date_val = resp.get('date', {}).get('value', '')
                url_suffix = resp.get('url', '') or ''
                url = f"https://www.banki.ru{url_suffix}" if url_suffix else ''
                
                combined = f"{title} {text}"
                
                if is_relevant(combined):
                    results.append({
                        'date': date_val,
                        'bank': bank,
                        'title': title.strip(),
                        'description': text.strip()[:200],
                        'url': url,
                        'source': 'banki.ru',
                        '_score': score_relevance(combined),
                    })
        except:
            pass
    
    return results

def is_relevant(text):
    """Проверяет релевантность"""
    tl = text.lower()
    
    # Должно содержать хотя бы одно include-слово
    if not any(kw in tl for kw in INCLUDE):
        return False
    
    # Не должно содержать exclude-слова
    if any(kw in tl for kw in EXCLUDE):
        return False
    
    return True

def score_relevance(text):
    """Оценка релевантности (выше = лучше)"""
    tl = text.lower()
    score = 0
    for kw in BOOST:
        if kw in tl:
            score += 2
    return score

def main():
    results = []
    
    for page in [1, 2, 3, 4]:
        html = fetch_page(page)
        if html:
            items = parse_data_module(html)
            results.extend(items)
    
    # Сортируем: сначала по оценке, потом по дате
    results.sort(key=lambda x: (-x.get('_score', 0), x.get('date', '')))
    
    # Убираем служебные поля
    for r in results:
        r.pop('_score', None)
    
    print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
