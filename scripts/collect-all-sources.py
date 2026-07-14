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
    """Запускает banki.ru парсер (он сам пишет в файлы), читает результат"""
    script = os.path.join(SCRIPTS, 'parse-banki-v5.py')
    try:
        result = subprocess.run(
            ['/usr/bin/python3', script],
            capture_output=True, text=True, timeout=60
        )
    except Exception as e:
        print(f"[collect] banki run error: {e}", file=sys.stderr)
    
    # Читаем результат из файла
    raw = read_json(os.path.join(SHARED, 'katya-raw.json'))
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
    
    # 3. Сливаем
    all_data = merge(banki_data, vcru_data)
    write_json(os.path.join(SHARED, 'katya-raw.json'), all_data)
    
    # 4. Только новые (за 7 дней) для katya-data.json
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    recent = [item for item in all_data if item.get('date', '') >= week_ago]
    write_json(os.path.join(SHARED, 'katya-data.json'), recent)
    
    # 5. Обновляем статистику
    stats = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_unique': len(all_data),
        'recent_new': len(recent),
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
    
    print(f"[collect] ✓ Готово! Всего: {len(all_data)} (banki: {len(banki_data)}, vc: {len(vcru_data)})", file=sys.stderr)


if __name__ == '__main__':
    main()
