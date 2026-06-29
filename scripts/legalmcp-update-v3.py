#!/usr/bin/env python3
"""Обновление анализа изменений 44-ФЗ / 224-ФЗ.

Без LegalMCP — только верификация через consultant.ru + pravo.gov.ru.
Скрипт не делает web-запросы самостоятельно (это делает агент через web_fetch).
Скрипт только публикует готовые данные.
"""

import json, os, subprocess, re, sys
from datetime import datetime, timezone, timedelta

WORKSPACE = "/home/user1/.openclaw/workspace"
RESULT_FILE = os.path.join(WORKSPACE, "zakupki-result.json")
STATS_FILE = os.path.join(WORKSPACE, "zakupki-stats.json")

MSK = timezone(timedelta(hours=3))
NOW_MSK = datetime.now(MSK)


def parse_consultant_laws(html):
    """Парсит блок (в ред. Федеральных законов от ДД.ММ.ГГГГ N ФЗ-№, ...)
    Возвращает список (дата, номер_закона) от старых к новым.
    """
    block = re.search(
        r'\(в\s+ред\.?\s*Федеральных\s+законов\s+от\s+([^)]+)\)',
        html, re.DOTALL
    )
    if not block:
        return []

    text = re.sub(r'\s+', ' ', block.group(1))
    laws = re.findall(r'от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s+([^,\s)]+)', text)
    return laws


def build_result(consultant_44, consultant_224, pravo_44, pravo_224, errors):
    """Формирует текст результата."""
    lines = []

    if errors:
        lines.append(f"⚠️ Ошибки при получении данных: {', '.join(errors)}")

    lines.append("")
    lines.append("🔍 consultant.ru (последние редакции):")

    def fmt_laws(laws, label):
        if not laws:
            lines.append(f"  • {label}: данные не получены")
            return
        lines.append(f"  • {label}: {len(laws)} редакций")
        for dt, num in laws[-5:]:
            lines.append(f"      от {dt} N {num}")

    fmt_laws(consultant_44, "44-ФЗ")
    fmt_laws(consultant_224, "224-ФЗ")

    lines.append("")
    lines.append("🔍 pravo.gov.ru (официальный портал):")
    lines.append(f"  • 44-ФЗ: {'🟢 совпадает' if pravo_44 else '🟡 не проверен'}")
    lines.append(f"  • 224-ФЗ: {'🟢 совпадает' if pravo_224 else '🟡 не проверен'}")

    lines.append("")
    if consultant_44:
        latest = consultant_44[-1]
        lines.append(f"⚡ Последняя редакция 44-ФЗ: от {latest[0]} N {latest[1]}")
    if consultant_224:
        latest = consultant_224[-1]
        lines.append(f"⚡ Последняя редакция 224-ФЗ: от {latest[0]} N {latest[1]}")

    return "\n".join(lines)


def publish(result_text, consultant_44, consultant_224, errors):
    lmcp_used = len(consultant_44) + len(consultant_224)
    meta = f"consultant.ru: {lmcp_used} редакций"
    if errors:
        meta += f" · ошибки: {', '.join(errors)}"

    result_data = {
        "title": f"✅ Верификация — {NOW_MSK.strftime('%d.%m.%Y %H:%M')}",
        "meta": meta,
        "text": result_text
    }
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    # stats
    stats_data = {
        "status_codex": "🟢" if consultant_44 else "🟡",
        "status_pp": "🟢" if consultant_224 else "🟡",
        "calls_today_display": str(lmcp_used),
        "monthly_display": "0 (без LegalMCP)",
        "last_update": NOW_MSK.strftime('%d.%m.%Y %H:%M')
    }
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, ensure_ascii=False, indent=2)

    os.chdir(WORKSPACE)
    subprocess.run(["git", "add", "zakupki-result.json", "zakupki-stats.json"], capture_output=True)
    subprocess.run(["git", "commit", "-m", f"zakupki: верификация {NOW_MSK.strftime('%d.%m')}"], capture_output=True)
    subprocess.run(["git", "push"], capture_output=True)
    print("✅ Опубликовано")
    print(result_text)


if __name__ == "__main__":
    print("▶ Чтение данных...")

    # Данные приходят извне (агент записывает в stdin или файл)
    # Скрипт читает из аргументов: --consultant-44 'json' --consultant-224 'json'
    # Или через файлы
    consultant_44 = json.loads(sys.argv[sys.argv.index("--c44") + 1]) if "--c44" in sys.argv else []
    consultant_224 = json.loads(sys.argv[sys.argv.index("--c224") + 1]) if "--c224" in sys.argv else []
    pravo_44 = "--p44" in sys.argv
    pravo_224 = "--p224" in sys.argv
    errors = json.loads(sys.argv[sys.argv.index("--errors") + 1]) if "--errors" in sys.argv else []

    print(f"  44-ФЗ: {len(consultant_44)} редакций")
    print(f"  224-ФЗ: {len(consultant_224)} редакций")
    print(f"  pravo 44: {pravo_44}, pravo 224: {pravo_224}")
    print(f"  ошибки: {errors}")

    result_text = build_result(consultant_44, consultant_224, pravo_44, pravo_224, errors)
    publish(result_text, consultant_44, consultant_224, errors)
    print("✅ Готово")
