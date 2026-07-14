#!/usr/bin/env python3
"""
Простой парсер vc.ru через публичный API.
Формат вывода совместим с Катиным форматом: [{"date": "...", "bank": "...", "title": "...", ...}]

Запуск: python3 scripts/parse-vcru-simple.py
Вывод: JSON в stdout
"""

import urllib.request, json, sys
from datetime import datetime, timezone
import urllib.parse

API_BASE = "https://api.vc.ru/v2.6"
HEADERS = {
    'User-Agent': 'NasledstvoBot/1.0 (katya-agent)',
    'Accept': 'application/json',
    'Referer': 'https://vc.ru/',
    'Origin': 'https://vc.ru',
}

# Поисковые запросы
QUERIES = [
    'наследство банк',
    'наследство сбербанк',
    'наследство кредит',
    'наследство умерший',
    'завещание банк',
    'банк наследство отказ',
]

# Словари для определения банка
BANK_RULES = [
    (['сбербанк','сбер','сбёр'], 'сбербанк'),
    (['втб'], 'втб'),
    (['альфа-банк','альфа'], 'альфа-банк'),
    (['тинькофф','т-банк','т банк','тбанк'], 'т-банк'),
    (['газпромбанк'], 'газпромбанк'),
    (['открытие'], 'банк открытие'),
    (['почта банк','почтабанк'], 'почта банк'),
    (['россельхозбанк','рсхб'], 'россельхозбанк'),
    (['совкомбанк'], 'совкомбанк'),
    (['промсвязьбанк','псб'], 'промсвязьбанк'),
    (['московский кредитный','мкб'], 'мкб'),
    (['мтс банк'], 'мтс банк'),
    (['росбанк'], 'росбанк'),
    (['диасофт'], 'диасофт'),
]


def detect(text):
    """Определяет банк из текста"""
    tl = text.lower()
    for kws, bn in BANK_RULES:
        for kw in kws:
            if kw in tl:
                return bn
    return 'банк'


def search(query):
    """Поиск постов"""
    q = urllib.parse.quote(query)
    url = f"{API_BASE}/search/posts?q={q}&perPage=30"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            data = json.loads(raw)
            return data.get('result', {}).get('items', [])
    except Exception:
        return []


def extract(item):
    """Извлекает данные поста"""
    entry = item.get('data', {})
    if not entry:
        return None
    
    title = (entry.get('title') or '').strip()
    text = (entry.get('text') or '')[:200]
    subtitle = (entry.get('subtitle') or '')
    url = entry.get('url', '') or f"https://vc.ru/{entry.get('id', '')}"
    date_ts = entry.get('date', 0)
    
    date_str = ''
    if date_ts:
        try:
            dt = datetime.fromtimestamp(date_ts, tz=timezone.utc)
            date_str = dt.strftime('%Y-%m-%d')
        except:
            pass
    
    description = (subtitle or text).strip()[:250]
    combined = f"{title} {description}".lower()
    
    # Фильтр: должно быть о наследстве
    inherit_kw = ['наследств','завещани','нотариус','смерт','умерш','скончал']
    has_inherit = any(kw in combined for kw in inherit_kw)
    if not has_inherit:
        return None
    
    # Банковские слова
    bank_kw = ['банк','банке','банком','вклад','кредит','депозит','счёт','ипотека',
               'сбер','втб','альфа','тинькофф','почта']
    has_bank = any(kw in combined for kw in bank_kw)
    if not has_bank:
        return None
    
    # Исключения
    exclude = ['миллиардер','португал','королев','тайланд','стартап',
               'наследственность','генетическ','астрологи']
    if any(e in combined for e in exclude):
        return None
    
    return {
        'date': date_str,
        'bank': detect(combined),
        'title': title,
        'description': description,
        'url': url,
        'source': 'vc.ru',
    }


def main():
    seen = {}
    
    for query in QUERIES:
        items = search(query)
        for item in items:
            entry = extract(item)
            if entry and entry['url'] not in seen:
                seen[entry['url']] = entry
    
    results = list(seen.values())
    results.sort(key=lambda x: x['date'], reverse=True)
    
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
