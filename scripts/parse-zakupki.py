#!/usr/bin/env python3
"""
Парсинг закупок с zakupki.gov.ru по ключевым словам (лекарства, медизделия).
Обновляет zakupki-purchases.json — живые данные на сайте ФармТендеролог.

Запуск: python3 scripts/parse-zakupki.py [--search "лекарственные средства"]
"""

import json
import os
import re
import ssl
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import quote

# zakupki.gov.ru использует российские сертификаты, которых нет в стандартных CA
SSL_CTX = ssl._create_unverified_context()

WORKSPACE = "/home/user1/.openclaw/workspace"
RESULT_FILE = os.path.join(WORKSPACE, "zakupki-purchases.json")
MSK = timezone(timedelta(hours=3))

# Ключевые слова для поиска
PURCHASE_QUERIES = [
    "лекарственные средства",
    "медицинские изделия",
    "лекарственные препараты",
    "медизделия",
    "фармацевтическая продукция",
]

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def fetch_purchases(search_query, page=1):
    """Парсит страницу результатов поиска zakupki.gov.ru"""
    url = (
        f"https://zakupki.gov.ru/epz/order/extendedsearch/results.html"
        f"?searchString={quote(search_query)}"
        f"&fz44=on&fz223=on&pageNumber={page}"
        f"&recordsPerPage=_50"  # 50 записей на страницу
    )
    
    req = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.9",
    })
    
    try:
        with urlopen(req, timeout=30, context=SSL_CTX) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except URLError as e:
        print(f"  ⚠️  Ошибка загрузки: {e}", file=sys.stderr)
        return [], 0

    soup = BeautifulSoup(html, "lxml")
    forms = soup.select(".row.no-gutters.registry-entry__form")
    
    # Общее количество (из заголовка)
    total_text = soup.get_text()
    total_match = re.search(r'более\s+([\d\s\xa0]+)\s*записей', total_text)
    total = 0
    if total_match:
        total_str = total_match.group(1).replace(" ", "").replace("\xa0", "")
        try:
            total = int(total_str)
        except ValueError:
            total = 0
    
    results = []
    for form in forms:
        top = form.select_one(".registry-entry__header-top")
        law = top.get_text(" ", strip=True).split(None, 1)[0] if top else "?"
        
        num_el = form.select_one(".registry-entry__header-mid__number")
        num = num_el.get_text(strip=True).replace("№", "").strip() if num_el else "?"
        
        st_el = form.select_one(".registry-entry__header-mid__title")
        status = st_el.get_text(strip=True) if st_el else "?"
        
        cust_el = form.select_one(".registry-entry__body-href a")
        customer = cust_el.get_text(strip=True) if cust_el else "?"
        
        body_titles = form.select(".registry-entry__body-title")
        obj = "?"
        for bt in body_titles:
            if "Объект закупки" in bt.get_text(strip=True):
                nxt = bt.find_next_sibling()
                if nxt:
                    obj = nxt.get_text(" ", strip=True)
                break
        
        price_el = form.select_one(".price-block__value")
        price = price_el.get_text(strip=True) if price_el else "?"
        
        link_el = form.select_one('a[href*="view.html"]')
        href = ""
        if link_el:
            href = link_el.get("href", "")
            href = "https://zakupki.gov.ru" + href if href.startswith("/") else href
        
        # Даты
        placed = "?"
        updated = "?"
        date_spans = form.select(".row > .col-6")
        for ds in date_spans:
            txt = ds.get_text(" ", strip=True)
            if "Размещено" in txt:
                placed = txt.replace("Размещено", "").strip()
            if "Обновлено" in txt:
                updated = txt.replace("Обновлено", "").strip()
        
        results.append({
            "law": law,
            "number": num,
            "status": status,
            "customer": customer[:150],
            "object": obj[:200],
            "price": price,
            "placed": placed,
            "updated": updated,
            "url": href,
        })
    
    return results, total


def main():
    print(f"🔍 Парсинг закупок с zakupki.gov.ru", file=sys.stderr)
    print(f"📅 {datetime.now(MSK).strftime('%d.%m.%Y %H:%M MSK')}", file=sys.stderr)
    
    seen_numbers = set()
    all_purchases = []
    total_global = 0
    
    for query in PURCHASE_QUERIES:
        print(f"\n  🔎 Поиск: «{query}»", file=sys.stderr)
        try:
            purchases, total = fetch_purchases(query, page=1)
            total_global = max(total_global, total)
            
            new_count = 0
            for p in purchases:
                if p["number"] not in seen_numbers:
                    seen_numbers.add(p["number"])
                    all_purchases.append(p)
                    new_count += 1
            
            print(f"     Новых: {new_count}, всего: {len(purchases)}, в системе: ~{total}", file=sys.stderr)
        except Exception as e:
            print(f"     ❌ Ошибка: {e}", file=sys.stderr)
    
    # Сортировка: сначала новые (по дате размещения)
    all_purchases.sort(key=lambda x: x.get("placed", ""), reverse=True)
    
    # Фильтр: только активные закупки (где ещё можно участвовать)
    active_statuses = ["Подача заявок", "Работа комиссии"]
    all_purchases = [p for p in all_purchases if p.get("status") in active_statuses]
    
    # Ограничим до 100 записей (больше не нужно для показа)
    if len(all_purchases) > 100:
        all_purchases = all_purchases[:100]
    
    now = datetime.now(MSK)
    result = {
        "meta": {
            "updated": now.strftime("%d.%m.%Y %H:%M"),
            "total_display": f"~{total_global:,}".replace(",", " ") if total_global else f"{len(all_purchases)}",
            "total_fetched": len(all_purchases),
            "queries": PURCHASE_QUERIES,
        },
        "purchases": all_purchases,
    }
    
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Сохранено {len(all_purchases)} закупок в {RESULT_FILE}", file=sys.stderr)
    
    # Публикация через git
    os.chdir(WORKSPACE)
    subprocess.run(["git", "add", "zakupki-purchases.json"], capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"zakupki: данные с ЕИС {now.strftime('%d.%m %H:%M')}"],
        capture_output=True,
    )
    subprocess.run(["git", "push"], capture_output=True)
    print("✅ Опубликовано на GitHub Pages", file=sys.stderr)


if __name__ == "__main__":
    main()
