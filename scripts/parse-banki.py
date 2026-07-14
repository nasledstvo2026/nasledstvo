#!/usr/bin/env python3
"""Парсинг отзывов с banki.ru для search-agent (Катя)
Поиск жалоб по наследству за указанную дату (вчера/сегодня),
сохранение в /home/user1/.openclaw/agents/shared/katya-raw.json
и обновление katya-data.json / katya-stats-data.md
"""

import json, os, re, sys, urllib.request, urllib.error
from datetime import datetime, timedelta
from html.parser import HTMLParser

SHARED = '/home/user1/.openclaw/agents/shared'
RAW_FILE = os.path.join(SHARED, 'katya-raw.json')
DATA_FILE = os.path.join(SHARED, 'katya-data.json')
STATS_FILE = os.path.join(SHARED, 'katya-stats-data.md')

# Ключевые слова для фильтрации (наследство)
KEYWORDS = [
    'наследств', 'умер', 'умерш', 'наследник', 'наследодател',
    'завещание', 'завещательн', 'свидетельств', 'отказ наслед',
    'вклад умерш', 'вклад наслед', 'счет умерш', 'счет наслед',
    'выплата наслед', 'нотариус', 'наследственн', 'похороны',
    'вступил в наслед', 'отказ в выпалт', 'наслед дела',
    'наслед масса', 'свидетельство о смерти', 'восстановл срок'
]

# Стоп-слова — отсеиваем 115-ФЗ, ипотеку обычную, кредиты без наследства
STOPWORDS = [
    '115-фз', 'антиотмывочн', 'сомнительн опер', 'ркл',
    'обнал', 'терроризм', 'экстремизм', 'мошенническ',
    'похитил', 'украл', 'фишинг', 'сброс парол',
]

class BankiHTMLParser(HTMLParser):
    """Парсит страницу отзывов banki.ru, возвращая отзывы с их данными"""
    def __init__(self):
        super().__init__()
        self.responses = []
        self.current = {}
        self.in_title = False
        self.in_text = False
        self.in_date = False
        self.in_company = False
        self.tags = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.tags.append(tag)
        
        # Ищем теги с data-response-id
        if 'data-response-id' in attrs_dict:
            if self.current:
                self.responses.append(self.current)
            self.current = {'id': attrs_dict['data-response-id'], 'title': '', 'text': '', 'date': '', 'company': ''}
        
        # Ищем дату (time tag)
        if tag == 'time':
            if 'datetime' in attrs_dict:
                self.current['date_raw'] = attrs_dict['datetime']
            self.in_date = True
        
        # Компания
        if tag == 'div' and 'class' in attrs_dict and 'response__company' in attrs_dict.get('class', ''):
            self.in_company = True

    def handle_endtag(self, tag):
        if self.tags:
            self.tags.pop()
        self.in_title = False
        self.in_text = False
        self.in_date = False
        self.in_company = False

    def handle_data(self, data):
        if not self.current:
            return
        data = data.strip()
        if not data:
            return
        
        # Дата
        if self.in_date:
            self.current['date'] = data.strip()
        
        # Компания
        if self.in_company and not self.current.get('company'):
            self.current['company'] = self.current.get('company', '') + data.strip()

def fetch_page(url):
    """Загружает страницу banki.ru"""
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_responses(html):
    """Извлекает отзывы из HTML страницы banki.ru через простой поиск JSON-блоков"""
    # Banki.ru встраивает данные отзывов в JSON-блоки
    # Ищем блоки с данными отзывов (в скриптах или data-атрибутах)
    
    results = []
    
    # Метод 1: Ищем JSON-данные в скриптах (banki.ru использует JSON-LD)
    json_blocks = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL
    )
    for block in json_blocks:
        try:
            data = json.loads(block)
            if isinstance(data, list):
                results.extend(data)
            elif isinstance(data, dict):
                results.append(data)
        except:
            pass
    
    # Метод 2: Ищем data-атрибуты отзывов
    # Banki.ru рендерит отзывы на сервере, ищем их в div'ах
    
    # Метод 3: regex на блоки отзывов
    # Ищем pattern: response__title, response__text, response__date
    
    return results

def search_banki_responses(target_date_str):
    """Ищет отзывы по наследству на banki.ru за указанную дату"""
    
    # Определяем даты для поиска
    target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    
    all_parsed = []
    
    # Качаем несколько страниц отзывов
    for page in range(1, 6):
        url = f'https://www.banki.ru/services/responses/list/?page={page}'
        print(f"Fetching {url}...")
        html = fetch_page(url)
        if not html:
            continue
        
        # Ищем блоки отзывов через regex
        # Banki.ru использует структуру: article с data-response-id
        
        # Ищем response-id блоки
        response_ids = re.findall(r'data-response-id="(\d+)"', html)
        
        # Для каждого ID ищем контейнер и вытаскиваем данные
        seen_ids = set()
        for rid in response_ids:
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            
            # Ищем блок этого отзыва
            pattern = re.compile(
                r'data-response-id="' + re.escape(rid) + r'".*?</article>',
                re.DOTALL
            )
            match = pattern.search(html)
            if not match:
                continue
            
            block = match.group()
            
            # Тайтл
            title_match = re.search(r'<span[^>]*class="[^"]*response__title[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL)
            title = title_match.group(1).strip() if title_match else ''
            title = re.sub(r'<[^>]+>', '', title).strip()
            
            # Текст
            text_match = re.search(r'class="[^"]*response__text[^"]*"[^>]*>(.*?)(?:</div>|<a)', block, re.DOTALL)
            text = text_match.group(1).strip() if text_match else ''
            text = re.sub(r'<[^>]+>', '', text).strip()
            
            # Дата
            date_match = re.search(r'time[^>]*datetime="([^"]+)"', block)
            if date_match:
                raw_date = date_match.group(1)
            else:
                date_match = re.search(r'\b(\d{1,2}\.\d{1,2}\.\d{4})\b', block)
                raw_date = date_match.group(1) if date_match else ''
            
            # Компания
            company_match = re.search(r'class="[^"]*response__company[^"]*"[^>]*>(.*?)</a>', block, re.DOTALL)
            company = company_match.group(1).strip() if company_match else ''
            company = re.sub(r'<[^>]+>', '', company).strip()
            
            # URL
            url_match = re.search(r'href="(/services/responses/[^"]*)"', block)
            response_url = f'https://www.banki.ru{url_match.group(1)}' if url_match else ''
            
            all_parsed.append({
                'id': rid,
                'title': title,
                'text': text[:500],
                'date_raw': raw_date,
                'company': company,
                'url': response_url,
                'page': page
            })
        
        # Если на странице нет свежих отзывов — останавливаемся
        # Проверяем есть ли отзывы за последние 2 дня
        has_recent = False
        for r in all_parsed[-20:]:
            d = r.get('date_raw', '')
            if any(recent in d for recent in [target_date_str, 
                                                datetime.now().strftime('%Y-%m-%d'),
                                                datetime.now().strftime('%d.%m.%Y'),
                                                target_date.strftime('%d.%m.%Y')]):
                has_recent = True
                break
        if not has_recent and page >= 2:
            print(f"No recent responses on page {page}, stopping")
            break
    
    # Фильтруем по ключевым словам
    matching = []
    for resp in all_parsed:
        text_to_check = (resp.get('title', '') + ' ' + resp.get('text', '')).lower()
        
        # Стоп-слова (если нет ключевых слов наследства — пропускаем)
        has_keyword = any(kw.lower() in text_to_check for kw in KEYWORDS)
        if not has_keyword:
            continue
        
        # Проверяем на стоп-слова
        is_stop = any(stop in text_to_check for stop in STOPWORDS)
        
        # Дата релевантна?
        date_str = resp.get('date_raw', '')
        
        matching.append({
            'date': target_date_str,
            'bank': resp.get('company', 'Неизвестно'),
            'title': resp.get('title', ''),
            'description': resp.get('text', '')[:300],
            'url': resp.get('url', ''),
            'source': 'banki.ru',
            'is_stopword': is_stop,
            'date_raw': date_str
        })
    
    return matching

def update_data_files(results, target_date_str):
    """Обновляет katya-raw.json, katya-data.json, katya-stats-data.md"""
    
    # 1. Сохраняем raw
    with open(RAW_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(results)} results to {RAW_FILE}")
    
    # 2. Обновляем katya-data.json
    all_data = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
    
    seen_urls = {r.get('url', '') for r in all_data if r.get('url')}
    new_count = 0
    for r in results:
        if r.get('url') and r['url'] not in seen_urls and not r.get('is_stopword'):
            all_data.append({
                'date': r['date'],
                'bank': r['bank'],
                'title': r['title'],
                'description': r['description'],
                'url': r['url'],
                'source': r['source']
            })
            seen_urls.add(r['url'])
            new_count += 1
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    print(f"Added {new_count} new entries to {DATA_FILE}")
    
    # 3. Обновляем статистику
    sber_count = sum(1 for r in results if not r.get('is_stopword') and 'сбер' in r.get('bank', '').lower() or 'sber' in r.get('bank', '').lower())
    other_count = sum(1 for r in results if not r.get('is_stopword') and 'сбер' not in r.get('bank', '').lower() and 'sber' not in r.get('bank', '').lower())
    
    # Из katya-data.json считаем сколько всего новых
    stats_line = f"\n{target_date_str} | Сбер: {sber_count} | Другие: {other_count}"
    
    banks_detail = {}
    for r in results:
        if r.get('is_stopword'):
            continue
        b = r.get('bank', 'Неизвестно')
        banks_detail[b] = banks_detail.get(b, 0) + 1
    
    if banks_detail:
        detail_str = ' | ' + ', '.join(f'{b} {c}' for b, c in sorted(banks_detail.items(), key=lambda x: -x[1]))
        stats_line += detail_str
    
    with open(STATS_FILE, 'a', encoding='utf-8') as f:
        f.write(stats_line)
    print(f"Updated {STATS_FILE}")
    
    return sber_count, other_count

def main():
    # Определяем дату: вчера (для cron) или сегодня (для ручного запуска)
    args = sys.argv[1:]
    if args and args[0] == '--today':
        target_date = datetime.now().date()
    elif args and args[0] == '--date':
        target_date = datetime.strptime(args[1], '%Y-%m-%d').date()
    else:
        target_date = (datetime.now() - timedelta(days=1)).date()
    
    target_date_str = target_date.strftime('%Y-%m-%d')
    print(f"Searching for responses on {target_date_str}...")
    
    results = search_banki_responses(target_date_str)
    
    if not results:
        print("No matching responses found.")
        update_data_files([], target_date_str)
        return
    
    # Сортируем по релевантности
    results.sort(key=lambda r: (0 if r['is_stopword'] else 1, r['title']), reverse=True)
    
    print(f"\nFound {len(results)} potential results:")
    for r in results:
        stop = " [STOPWORD]" if r['is_stopword'] else ""
        print(f"  - {r['bank']}: {r['title'][:60]}{stop}")
    
    update_data_files(results, target_date_str)
    
    # Выводим сводку
    real = [r for r in results if not r['is_stopword']]
    print(f"\n=== Summary ===")
    print(f"Total matching: {len(results)}")
    print(f"Real complaints: {len(real)}")
    print(f"Filtered (stop): {len(results) - len(real)}")

if __name__ == '__main__':
    main()
