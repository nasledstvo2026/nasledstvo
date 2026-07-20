#!/usr/bin/env python3
"""
Сборщик новостей по наследству для Лены.
Архитектура «Три эшелона»: прямой парсинг новостных разделов сайтов.

Эшелон 1: garant.ru, consultant.ru, nalog.gov.ru, sfr.gov.ru (прямой парсинг)
Эшелон 2: kommersant.ru, rg.ru, vedomosti.ru (с паузами, эмуляция браузера)
Эшелон 3: tass.ru (RSS, фильтрация)

Запуск: python3 scripts/collect-lena-news.py
"""

import json, sys, os, re, time, random
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

SHARED = '/home/user1/.openclaw/agents/shared'
WEEK_AGO = (datetime.now(timezone.utc) - timedelta(days=7))

# Разрешённые домены
ALLOWED_DOMAINS = {
    'tass.ru', 'rbc.ru', 'kommersant.ru', 'vedomosti.ru', 'rg.ru',
    'pravo.gov.ru', 'notariat.ru', 'banki.ru', 'duma.gov.ru',
    'consultant.ru', 'garant.ru', 'nalog.gov.ru', 'sfr.gov.ru',
    'mintrud.gov.ru', 'cbr.ru', 'government.ru'
}

# Ключевые слова (хотя бы одно в заголовке или сниппете)
KEYWORDS = [
    'наслед', 'завеща', 'нотариус', 'вымороч',
    'наследовани', 'наследник', 'наследниц', 'наследодател',
    'депозит нотариуса', 'розыск счет', 'забыты вклад',
    'цифров наследств', 'криптонаследств', 'электрон завещан',
    'свидетельств о праве на наследств', 'вступлен в наследств',
    'оформлен наследств', 'раздел наследств', 'отказ от наследств',
    'обязательн доля', 'недостойн наследник', 'очередь наследников'
]

# Стоп-слова (реклама, вакансии)
STOP_WORDS = [
    'юридическая консультация', 'услуги адвоката', 'вакансия',
    'работа нотариусом', 'юридическая фирма', 'скидка', 'акция',
    'реклама', 'промокод', 'купить', 'заказать'
]

# User-Agent pool (ротация)
UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
]

SESSION = requests.Session()
SESSION.headers.update({
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
})


def rotate_ua():
    SESSION.headers['User-Agent'] = random.choice(UA_POOL)


def pause(tier=1):
    """Пауза: tier 1 — без паузы, tier 2 — 2-5 сек"""
    if tier == 2:
        time.sleep(random.uniform(2, 5))
    elif tier == 3:
        time.sleep(random.uniform(0.5, 1.5))


def fetch(url, encoding=None, timeout=15):
    """GET-запрос с базовой обработкой"""
    rotate_ua()
    try:
        resp = SESSION.get(url, timeout=timeout, allow_redirects=True)
        if resp.status_code != 200:
            return None
        if encoding:
            resp.encoding = encoding
        return resp
    except Exception as e:
        print(f"  [ERR] fetch {url}: {e}", file=sys.stderr)
        return None


def is_allowed_domain(url):
    try:
        domain = urlparse(url).netloc.lower().replace('www.', '')
        return any(domain == d or domain.endswith('.' + d) for d in ALLOWED_DOMAINS)
    except:
        return False


def matches_keywords(text):
    text_lower = (text or '').lower()
    return any(kw in text_lower for kw in KEYWORDS)


def has_stop_words(text):
    text_lower = (text or '').lower()
    return any(sw in text_lower for sw in STOP_WORDS)


def extract_date(text):
    """Извлекает дату из строки вида ДД.ММ.ГГГГ или YYYY-MM-DD"""
    patterns = [
        r'(\d{2})\.(\d{2})\.(\d{4})',
        r'(\d{4})-(\d{2})-(\d{2})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            if len(m.group(1)) == 2:
                d, mo, y = m.group(1), m.group(2), m.group(3)
            else:
                y, mo, d = m.group(1), m.group(2), m.group(3)
            try:
                return f"{y}-{mo}-{d}"
            except:
                pass
    return None


def is_recent(date_str):
    """Проверяет, что дата в пределах 7 дней"""
    if not date_str:
        return True  # без даты — принимаем
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        return dt >= WEEK_AGO
    except:
        return True


# ═══════════════════════════════════════════════════════
# ЭШЕЛОН 1 — Прямой парсинг
# ═══════════════════════════════════════════════════════

def parse_garant():
    """garant.ru — поиск по сайту (windows-1251)"""
    results = []
    urls = [
        'https://www.garant.ru/search/?q=%ED%E0%F1%EB%E5%E4%F1%F2%E2%EE&source=news',
    ]
    source = 'garant.ru'
    print(f"[{source}] searching...", file=sys.stderr)
    
    for url in urls:
        pause(1)
        resp = fetch(url, encoding='windows-1251')
        if not resp:
            continue
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        for block in soup.find_all(['div', 'article', 'li'], class_=re.compile(r'search|result|news|item', re.I)):
            a = block.find('a', href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a['href']
            if not href.startswith('http'):
                href = urljoin(resp.url, href)
            
            if not is_allowed_domain(href):
                continue
            if not matches_keywords(title):
                continue
            if has_stop_words(title):
                continue
            
            date_el = block.find(['time', 'span', 'div'], class_=re.compile(r'date|time', re.I))
            date_str = extract_date(date_el.get_text(strip=True)) if date_el else None
            if date_str and not is_recent(date_str):
                continue
            
            results.append({'title': title, 'date': date_str or datetime.now().strftime('%Y-%m-%d'), 'url': href, 'source': source})
    
    print(f"[{source}] {len(results)} found", file=sys.stderr)
    return results


def parse_consultant():
    """consultant.ru — парсинг новостного раздела (utf-8)"""
    results = []
    source = 'consultant.ru'
    print(f"[{source}] scraping...", file=sys.stderr)
    
    urls = [
        'https://www.consultant.ru/legalnews/',
        'https://www.consultant.ru/news/',
    ]
    for url in urls:
        pause(1)
        resp = fetch(url)
        if not resp:
            continue
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            title = a.get_text(strip=True)
            href = a['href']
            if not href.startswith('http'):
                href = urljoin(resp.url, href)
            
            if not title or len(title) < 15:
                continue
            if not is_allowed_domain(href):
                continue
            if not matches_keywords(title):
                continue
            if has_stop_words(title):
                continue
            
            results.append({'title': title, 'date': datetime.now().strftime('%Y-%m-%d'), 'url': href, 'source': source})
    
    print(f"[{source}] {len(results)} found", file=sys.stderr)
    return results


def parse_nalog():
    """nalog.gov.ru — парсинг новостей (utf-8)"""
    results = []
    source = 'nalog.gov.ru'
    print(f"[{source}] scraping...", file=sys.stderr)
    
    # Прокидываем редирект
    resp = fetch('https://www.nalog.gov.ru/rn77/news/', timeout=20)
    if not resp:
        return results
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        title = a.get_text(strip=True)
        href = a['href']
        if not href.startswith('http'):
            href = urljoin(resp.url, href)
        
        if not title or len(title) < 15:
            continue
        if not is_allowed_domain(href):
            continue
        if not matches_keywords(title):
            continue
        if has_stop_words(title):
            continue
        
        results.append({'title': title, 'date': datetime.now().strftime('%Y-%m-%d'), 'url': href, 'source': source})
    
    print(f"[{source}] {len(results)} found", file=sys.stderr)
    return results


def parse_sfr():
    """sfr.gov.ru — парсинг новостей (utf-8)"""
    results = []
    source = 'sfr.gov.ru'
    print(f"[{source}] scraping...", file=sys.stderr)
    
    resp = fetch('https://sfr.gov.ru/press_center/')
    if not resp:
        return results
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        title = a.get_text(strip=True)
        href = a['href']
        if not href.startswith('http'):
            href = urljoin(resp.url, href)
        
        if not title or len(title) < 15:
            continue
        if not is_allowed_domain(href):
            continue
        if not matches_keywords(title):
            continue
        if has_stop_words(title):
            continue
        
        date_el = a.find_parent(['div', 'li', 'article'])
        date_str = None
        if date_el:
            date_text = date_el.get_text()
            date_str = extract_date(date_text)
        
        results.append({'title': title, 'date': date_str or datetime.now().strftime('%Y-%m-%d'), 'url': href, 'source': source})
    
    print(f"[{source}] {len(results)} found", file=sys.stderr)
    return results


# ═══════════════════════════════════════════════════════
# ЭШЕЛОН 2 — С паузами, эмуляция браузера
# ═══════════════════════════════════════════════════════

def parse_kommersant():
    """kommersant.ru — поиск по сайту"""
    results = []
    source = 'kommersant.ru'
    print(f"[{source}] searching...", file=sys.stderr)
    
    resp = fetch('https://www.kommersant.ru/search/results?search=наследство', timeout=20)
    if not resp:
        return results
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        title = a.get_text(strip=True)
        href = a['href']
        if not href.startswith('http'):
            href = urljoin(resp.url, href)
        
        if not title or len(title) < 15:
            continue
        if not is_allowed_domain(href):
            continue
        if not matches_keywords(title):
            continue
        if has_stop_words(title):
            continue
        
        results.append({'title': title, 'date': datetime.now().strftime('%Y-%m-%d'), 'url': href, 'source': source})
    
    print(f"[{source}] {len(results)} found", file=sys.stderr)
    return results


def parse_rg():
    """rg.ru — поиск по сайту + тематический раздел"""
    results = []
    source = 'rg.ru'
    print(f"[{source}] searching...", file=sys.stderr)
    
    resp = fetch('https://rg.ru/search/?q=наследство', timeout=20)
    if not resp:
        return results
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        title = a.get_text(strip=True)
        href = a['href']
        if not href.startswith('http'):
            href = urljoin(resp.url, href)
        
        if not title or len(title) < 15:
            continue
        if not is_allowed_domain(href):
            continue
        if not matches_keywords(title):
            continue
        if has_stop_words(title):
            continue
        
        results.append({'title': title, 'date': datetime.now().strftime('%Y-%m-%d'), 'url': href, 'source': source})
    
    print(f"[{source}] {len(results)} found", file=sys.stderr)
    return results


def parse_vedomosti():
    """vedomosti.ru — поиск по сайту"""
    results = []
    source = 'vedomosti.ru'
    print(f"[{source}] searching...", file=sys.stderr)
    
    resp = fetch('https://www.vedomosti.ru/search?query=наследство', timeout=20)
    if not resp:
        return results
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    for a in soup.find_all('a', href=True):
        title = a.get_text(strip=True)
        href = a['href']
        if not href.startswith('http'):
            href = urljoin(resp.url, href)
        
        if not title or len(title) < 15:
            continue
        if not is_allowed_domain(href):
            continue
        if not matches_keywords(title):
            continue
        if has_stop_words(title):
            continue
        
        results.append({'title': title, 'date': datetime.now().strftime('%Y-%m-%d'), 'url': href, 'source': source})
    
    print(f"[{source}] {len(results)} found", file=sys.stderr)
    return results


# ═══════════════════════════════════════════════════════
# ЭШЕЛОН 3 — RSS (для сайтов с ботозащитой)
# ═══════════════════════════════════════════════════════

def parse_tass_rss():
    """tass.ru — фильтрация RSS (единственный работающий способ)"""
    results = []
    source = 'tass.ru'
    print(f"[{source}] RSS filtering...", file=sys.stderr)
    
    try:
        import feedparser
        resp = fetch('https://tass.ru/rss/v2.xml')
        if not resp:
            return results
        feed = feedparser.parse(resp.content)
        for entry in feed.entries:
            title = entry.get('title', '').strip()
            link = entry.get('link', '').strip()
            if not title or not link:
                continue
            if not matches_keywords(title):
                continue
            if has_stop_words(title):
                continue
            
            # Извлекаем дату
            date_str = None
            tp = entry.get('published_parsed')
            if tp:
                date_str = datetime(*tp[:6]).strftime('%Y-%m-%d')
            if date_str and not is_recent(date_str):
                continue
            
            results.append({'title': title, 'date': date_str or datetime.now().strftime('%Y-%m-%d'), 'url': link, 'source': source})
    except Exception as e:
        print(f"[{source}] error: {e}", file=sys.stderr)
    
    print(f"[{source}] {len(results)} RSS matches", file=sys.stderr)
    return results


# ═══════════════════════════════════════════════════════
# Общие функции
# ═══════════════════════════════════════════════════════

def read_seen():
    """Читает lena-news-seen.md, возвращает set URL'ов"""
    path = os.path.join(SHARED, 'lena-news-seen.md')
    urls = set()
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.search(r'(https?://\S+)', line)
                if m:
                    urls.add(m.group(1).rstrip(')'))
    except:
        pass
    return urls


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def deduplicate(news_list, seen_urls):
    """Дедупликация по URL и заголовкам (>70% схожести)"""
    result = []
    seen_in_batch = set()
    
    for item in news_list:
        url = item['url']
        title_words = set(item['title'].lower().split())
        
        if url in seen_urls or url in seen_in_batch:
            continue
        if not title_words:
            continue
        
        duplicate = False
        for existing in result:
            ew = set(existing['title'].lower().split())
            if ew:
                overlap = len(title_words & ew) / min(len(title_words), len(ew))
                if overlap > 0.7:
                    duplicate = True
                    break
        
        if not duplicate:
            seen_in_batch.add(url)
            result.append(item)
    
    return result


def main():
    print(f"[collect-lena] START {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)
    
    seen_urls = read_seen()
    print(f"[collect-lena] seen: {len(seen_urls)} URLs", file=sys.stderr)
    
    all_news = []
    errors = []
    
    # ═══ Эшелон 1 ═══
    print("[collect-lena] === TIER 1 ===", file=sys.stderr)
    tier1 = [parse_garant, parse_consultant, parse_nalog, parse_sfr]
    for fn in tier1:
        try:
            all_news.extend(fn())
        except Exception as e:
            src = fn.__name__.replace('parse_', '')
            errors.append(f"T1:{src}:{e}")
            print(f"[collect-lena] T1 ERR {fn.__name__}: {e}", file=sys.stderr)
    
    # ═══ Эшелон 2 ═══
    print("[collect-lena] === TIER 2 ===", file=sys.stderr)
    pause(2)
    tier2 = [parse_kommersant, parse_rg, parse_vedomosti]
    for fn in tier2:
        try:
            pause(2)
            all_news.extend(fn())
        except Exception as e:
            src = fn.__name__.replace('parse_', '')
            errors.append(f"T2:{src}:{e}")
            print(f"[collect-lena] T2 ERR {fn.__name__}: {e}", file=sys.stderr)
    
    # ═══ Эшелон 3 ═══
    print("[collect-lena] === TIER 3 ===", file=sys.stderr)
    try:
        all_news.extend(parse_tass_rss())
    except Exception as e:
        errors.append(f"T3:tass:{e}")
    
    # Дедупликация
    unique = deduplicate(all_news, seen_urls)
    
    # Сохранение
    raw_file = os.path.join(SHARED, 'lena-raw.json')
    write_json(raw_file, unique)
    
    # Обновление seen
    today = datetime.now().strftime('%Y-%m-%d')
    seen_file = os.path.join(SHARED, 'lena-news-seen.md')
    with open(seen_file, 'a', encoding='utf-8') as f:
        for item in unique:
            f.write(f"# {today} | {item['title']} | {item['url']}\n")
    
    # Итог
    print(f"[collect-lena] DONE: {len(unique)} unique of {len(all_news)} total, {len(errors)} errors", file=sys.stderr)
    for e in errors[:5]:
        print(f"[collect-lena]   ERR: {e}", file=sys.stderr)
    
    return unique


if __name__ == '__main__':
    main()
