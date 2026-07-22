#!/usr/bin/env python3
"""
Сборщик данных со всех источников для Кати.
Источники: banki.ru (прямой парсинг), pikabu.ru, otzovik.com, findozor.net, 2gis.ru (через SearXNG API).

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


def run_script(name, timeout=90):
    """Запускает Python-скрипт и возвращает JSON-результат"""
    script = os.path.join(SCRIPTS, name)
    try:
        result = subprocess.run(
            ['/usr/bin/python3', script],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            print(f"[collect] {name} stderr: {result.stderr[:200]}", file=sys.stderr)
            return []
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"[collect] {name} JSON error: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[collect] {name} error: {e}", file=sys.stderr)
        return []


def merge(all_data):
    """Сливает данные из источников, убирая дубли по URL"""
    seen = set()
    merged = []
    for item in all_data:
        url = item.get('url', '')
        if url and url not in seen:
            seen.add(url)
            merged.append(item)
    merged.sort(key=lambda x: x.get('date', ''), reverse=True)
    return merged


def main():
    print(f"[collect] Запуск сбора: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", file=sys.stderr)

    # 1. banki.ru — основной источник, прямой парсинг
    print("[collect] --- banki.ru ---", file=sys.stderr)
    banki_data = run_script('parse-banki-v5.py')
    print(f"[collect] banki.ru: {len(banki_data)} результатов", file=sys.stderr)

    # 2. pikabu.ru, otzovik.com, findozor.net, 2gis.ru — через SearXNG API
    print("[collect] --- pikabu/otzovik/findozor/2gis (SearXNG) ---", file=sys.stderr)
    extra_data = run_script('parse-extra-sources.py', timeout=120)
    print(f"[collect] extra (SearXNG): {len(extra_data)} результатов", file=sys.stderr)

    # 3. Сливаем
    new_data = merge(banki_data + extra_data)

    # 4. Статистика по источникам
    source_counts = {}
    for d in new_data:
        s = d.get('source', 'banki.ru')
        source_counts[s] = source_counts.get(s, 0) + 1

    # 5. katya-raw.json — сохраняем историю + добавляем новые
    existing_raw = read_json(os.path.join(SHARED, 'katya-raw.json')) or []
    seen_raw = {item.get('url', '') for item in existing_raw if item.get('url')}
    for item in new_data:
        if item.get('url', '') not in seen_raw:
            seen_raw.add(item.get('url', ''))
            existing_raw.append(item)
    existing_raw.sort(key=lambda x: x.get('date', ''), reverse=True)
    write_json(os.path.join(SHARED, 'katya-raw.json'), existing_raw)

    # 6. katya-data.json — добавляем новые записи
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

    # 7. Статистика
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    total_count = len(existing_data)
    recent_count = sum(1 for item in existing_data if item.get('date', '') >= week_ago)

    stats = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_unique': total_count,
        'recent_new': recent_count,
        'sources': source_counts,
    }

    with open(os.path.join(SHARED, 'katya-stats-data.md'), 'w', encoding='utf-8') as f:
        f.write("# Статистика жалоб по наследству\n\n")
        f.write(f"**Обновлено:** {stats['last_updated']}\n\n")
        f.write("| Параметр | Значение |\n")
        f.write("|----------|--------|\n")
        f.write(f"| Всего в базе | {stats['total_unique']} |\n")
        f.write(f"| Новых (7 дней) | {stats['recent_new']} |\n")
        for src, cnt in sorted(source_counts.items()):
            f.write(f"| Из {src} | {cnt} |\n")

    print(f"[collect] ✓ Готово! Всего: {len(existing_raw)} (+{added} новых) | Источники: {source_counts}", file=sys.stderr)


if __name__ == '__main__':
    main()
