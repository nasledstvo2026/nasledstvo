#!/usr/bin/env python3
"""
Парсер vc.ru / Приёмная (claim) — сбор свежих жалоб по банкам + наследству.
API: /v2.6/timeline?subsite_id=199124&sorting=new&count=50&lastId=...

Запуск: python3 scripts/parse-vcru.py
Вывод: JSON в stdout, формат совместим с katya-data.json
"""

import json, sys, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

API_BASE = "https://api.vc.ru/v2.6"
CLAIM_SUBSITE = 199124  # "Приёмная"
USER_AGENT = 'NasledstvoBot/1.0 (+https://nasledstvo2026.github.io/nasledstvo)'

HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'application/json',
}

# Банки (список для фильтрации)
BANKS = {
    'сбербанк': 'сбербанк', 'сбер': 'сбербанк', 'сбёр': 'сбербанк',
    'втб': 'втб',
    'альфа-банк': 'альфа-банк', 'альфа': 'альфа-банк',
    'тинькофф': 'т-банк', 'т-банк': 'т-банк', 'т банк': 'т-банк', 'тбанк': 'т-банк',
    'газпромбанк': 'газпромбанк',
    'открытие': 'банк открытие',
    'почта банк': 'почта банк', 'почтабанк': 'почта банк',
    'россельхозбанк': 'россельхозбанк', 'рсхб': 'россельхозбанк',
    'росбанк': 'росбанк',
    'совкомбанк': 'совкомбанк',
    'промсвязьбанк': 'промсвязьбанк', 'псб': 'промсвязьбанк',
    'московский кредитный': 'мкб', 'мкб': 'мкб',
    'мтс банк': 'мтс банк', 'мтсбанк': 'мтс банк',
}

# Ключевые слова наследства
INHERIT = {
    'наследств', 'наследник', 'наследница', 'наследодател',
    'умерш', 'умер', 'умершая', 'умершего', 'умершей',
    'скончал', 'скончалась', 'скончавшегося',
    'смерт', 'смерти', 'смерть',
    'завещани', 'завещание', 'завещанию', 'завещательн',
    'нотариус', 'нотариуса', 'нотариальн',
    'свидетельство о праве', 'свидетельства о праве',
    'принятие наследств', 'принять наследств',
    'отказ от наследств', 'отказ в наследств',
    'вступить в наследств', 'оформить наследств',
    'доля в наследств', 'долю в наследств',
    'выплат по наследств', 'выплата наследств',
    'потеря кормильц', 'потерял кормильц',
}

# Исключения
EXCLUDE = {
    'миллиардер', 'португал', 'королев', 'тайланд', 'стартап',
    'наследственность', 'наследственный', 'генетическ',
    'old money', 'wasp',
    'продаж квартир', 'купить квартиру',
}


def fetch_timeline(last_id=None, count=50):
    """Получает ленту подсайта Приёмная"""
    params = {
        'subsite_id': CLAIM_SUBSITE,
        'sorting': 'new',
        'count': count,
    }
    if last_id:
        params['lastId'] = last_id
    
    url = f"{API_BASE}/timeline?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
            data = json.loads(raw)
            result = data.get('result', {})
            items = result.get('items', [])
            new_last_id = result.get('lastId')
            print(f"  [vcru] timeline: {len(items)} записей, lastId={new_last_id}", file=sys.stderr)
            return items, new_last_id
    except Exception as e:
        print(f"  [vcru] timeline error: {e}", file=sys.stderr)
        return [], None


def extract_entry(item):
    """Извлекает данные из объекта ленты"""
    entry = item.get('data', {})
    if not entry:
        return None
    
    post_id = entry.get('id')
    title = (entry.get('title') or '').strip()
    text = (entry.get('text') or '').strip()
    subtitle = (entry.get('subtitle') or '').strip()
    url = entry.get('url', '') or f"https://vc.ru/{post_id}"
    date_ts = entry.get('date', 0)
    likes = (entry.get('likes') or {}).get('count', 0)
    comments = (entry.get('comments') or {}).get('count', 0)
    
    # Дата
    date_str = ''
    if date_ts:
        try:
            dt = datetime.fromtimestamp(date_ts, tz=timezone.utc)
            date_str = dt.strftime('%Y-%m-%d')
        except: pass
    
    # intro — необязательное поле
    intro = entry.get('intro', '') or ''
    
    description = (subtitle or text[:300] if text else intro).strip()[:250]
    
    return {
        'id': post_id,
        'title': title,
        'description': description,
        'url': url,
        'date': date_str,
        'date_ts': date_ts,
        'likes': likes,
        'comments': comments,
        'combined': f"{title} {description} {text} {subtitle}".lower(),
    }


def find_bank(text):
    """Ищет банк в тексте"""
    tl = text.lower()
    found = []
    for keyword, bank_name in BANKS.items():
        if keyword in tl:
            found.append(bank_name)
    return list(set(found)) or ['банк']


def is_relevant(entry_data):
    """Проверка: банк + наследство"""
    text = entry_data.get('combined', '')
    
    # Исключения
    if any(e in text for e in EXCLUDE):
        return False
    
    # Должны быть и банк, и наследство
    has_bank = any(kw in text for kw in BANKS)
    has_inherit = any(kw in text for kw in INHERIT)
    
    return has_bank and has_inherit


def main():
    max_pages = 3  # максимум страниц для пагинации
    recent_days = 7  # дней свежести
    
    deadline_ts = (datetime.now() - timedelta(days=recent_days)).timestamp()
    all_results = {}
    
    # Циклическая пагинация
    last_id = None
    for page in range(max_pages):
        items, new_last_id = fetch_timeline(last_id=last_id)
        if not items:
            break
        
        for item in items:
            entry = extract_entry(item)
            if not entry or entry['id'] in all_results:
                continue
            
            # Останавливаемся если записи слишком старые
            if entry['date_ts'] and entry['date_ts'] < deadline_ts:
                print(f"  [vcru] записи старее {recent_days} дней — стоп", file=sys.stderr)
                items.clear()
                break
            
            if is_relevant(entry):
                banks = find_bank(entry['combined'])
                
                all_results[entry['id']] = {
                    'date': entry['date'],
                    'bank': banks[0] if len(banks) == 1 else ', '.join(banks[:2]),
                    'title': entry['title'],
                    'description': entry['description'][:250],
                    'url': entry['url'],
                    'source': 'vc.ru',
                    'likes': entry['likes'],
                    'comments': entry['comments'],
                }
        
        if not new_last_id or new_last_id == last_id:
            break
        last_id = new_last_id
    
    results = list(all_results.values())
    results.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    print(f"  [vcru] Итого: {len(results)} релевантных за {recent_days} дней", file=sys.stderr)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
