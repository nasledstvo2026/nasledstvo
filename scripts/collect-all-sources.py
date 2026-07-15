#!/usr/bin/env python3
"""
Сборщик данных со всех источников для Кати.
Совместим с текущей архитектурой: парсеры пишут в shared-файлы.
Дополнительно собирает vc.ru.

Запуск: python3 scripts/collect-all-sources.py
"""

import json, sys, os, subprocess
from datetime import datetime, timezone, timedelta

SHARED = '/home/user1/.openclaw/agents/shared'
SCRIPTS = '/home/user1/.openclaw/workspace/scripts'


def read_json(path):
    """Читает JSON-файл"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def write_json(path, data):
    """Пишет JSON-файл"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def run_vcru():
    """Запускает vc.ru парсер (/timeline, Приёмная) и возвращает результаты"""
    script = os.path.join(SCRIPTS, 'parse-vcru.py')
    try:
        result = subprocess.run(
            ['/usr/bin/python3', script],
            capture_output=True, text=True, timeout=45
        )
        if result.returncode != 0:
            return []
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[collect] vcru error: {e}", file=sys.stderr)
        return []


def run_banki():
    """Запускает banki.ru парсер, читает результат из temp-файла"""
    script = os.path.join(SCRIPTS, 'parse-banki-v5.py')
    banki_raw_file = os.path.join(SHARED, 'katya-banki-raw.json')
    try:
        result = subprocess.run(
            ['/usr/bin/python3', script],
            capture_output=True, text=True, timeout=60
        )
    except Exception as e:
        print(f"[collect] banki run error: {e}", file=sys.stderr)
    
    # Читаем результат из отдельного temp-файла (не трогает katya-raw.json)
    raw = read_json(banki_raw_file)
    return raw if raw else []


def merge(banki_data, vcru_data):
    """Сливает данные из источников, убирая дубли"""
    seen = set()
    merged = []
    
    for item in banki_data + vcru_data:
        url = item.get('url', '')
        if url and url not in seen:
            seen.add(url)
            merged.append(item)
    
    merged.sort(key=lambda x: x.get('date', ''), reverse=True)
    return merged


def main():
    print(f"[collect] Запуск сбора: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)
    
    # 1. Banki.ru (основной источник)
    print("[collect] --- banki.ru ---", file=sys.stderr)
    banki_data = run_banki()
    print(f"[collect] banki.ru: {len(banki_data)} результатов", file=sys.stderr)
    
    # 2. VC.ru (дополнительный источник)
    print("[collect] --- vc.ru ---", file=sys.stderr)
    vcru_data = run_vcru()
    print(f"[collect] vc.ru: {len(vcru_data)} результатов", file=sys.stderr)
    
    # 3. Сливаем новые данные
    new_data = merge(banki_data, vcru_data)
    
    # 4. katya-raw.json — сохраняем историю + добавляем новые
    existing_raw = read_json(os.path.join(SHARED, 'katya-raw.json')) or []
    seen_raw = {item.get('url', '') for item in existing_raw if item.get('url')}
    for item in new_data:
        if item.get('url', '') not in seen_raw:
            seen_raw.add(item.get('url', ''))
            existing_raw.append(item)
    existing_raw.sort(key=lambda x: x.get('date', ''), reverse=True)
    write_json(os.path.join(SHARED, 'katya-raw.json'), existing_raw)
    
    # 5. katya-data.json — добавляем новые записи, сохраняем историю
    existing_data = read_json(os.path.join(SHARED, 'katya-data.json')) or []
    if not isinstance(existing_data, list):
        existing_data = []
    seen_data = {item.get('url', '') for item in existing_data if item.get('url')}
    added = 0
    for r in new_data:
        url = r.get('url', '')
        if url not in seen_data:
            seen_data.add(url)
            existing_data.append({
                'date': r['date'], 'bank': r.get('bank', 'Неизвестно'),
                'title': r['title'], 'description': r.get('text', r.get('description', ''))[:300],
                'url': url, 'source': r.get('source', 'banki.ru')
            })
            added += 1
    existing_data.sort(key=lambda x: x.get('date', ''), reverse=True)
    write_json(os.path.join(SHARED, 'katya-data.json'), existing_data)
    
    # 6. Считаем статистику по katya-data.json (полная история)
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    data_for_stats = existing_data  # из katya-data.json
    total_count = len(data_for_stats)
    recent_count = sum(1 for item in data_for_stats if item.get('date', '') >= week_ago)
    
    # 7. Обновляем статистику
    stats = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_unique': total_count,
        'recent_new': recent_count,
        'sources': {
            'banki.ru': len(banki_data),
            'vc.ru': len(vcru_data),
        }
    }
    
    with open(os.path.join(SHARED, 'katya-stats-data.md'), 'w', encoding='utf-8') as f:
        f.write("# Статистика жалоб по наследству\n\n")
        f.write(f"**Обновлено:** {stats['last_updated']}\n\n")
        f.write("| Параметр | Значение |\n")
        f.write("|----------|--------|\n")
        f.write(f"| Всего в базе | {stats['total_unique']} |\n")
        f.write(f"| Новых (7 дней) | {stats['recent_new']} |\n")
        f.write(f"| Из banki.ru | {stats['sources']['banki.ru']} |\n")
        f.write(f"| Из vc.ru | {stats['sources']['vc.ru']} |\n")
    
    print(f"[collect] ✓ Готово! Всего: {len(existing_raw)} (+{added} новых) (banki: {len(banki_data)}, vc: {len(vcru_data)})", file=sys.stderr)


if __name__ == '__main__':
    main()
