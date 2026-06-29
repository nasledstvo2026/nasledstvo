#!/usr/bin/env python3
"""Обновление анализа изменений 44-ФЗ / 223-ФЗ.

Без LegalMCP — только верификация через consultant.ru (web_fetch в агенте, публикация здесь).
Скрипт принимает данные из аргументов командной строки.
"""

import json, os, subprocess, re, sys
from datetime import datetime, timezone, timedelta

WORKSPACE = "/home/user1/.openclaw/workspace"
RESULT_FILE = os.path.join(WORKSPACE, "zakupki-result.json")
STATS_FILE = os.path.join(WORKSPACE, "zakupki-stats.json")

MSK = timezone(timedelta(hours=3))
NOW_MSK = datetime.now(MSK)


def parse_consultant_laws(html):
    """Парсит блок (в ред. Федеральных законов от ...)"""
    block = re.search(
        r'\(в\s+ред\.?\s*Федеральных\s+законов\s+от\s+([^)]+)\)',
        html, re.DOTALL
    )
    if not block:
        return []
    text = re.sub(r'\s+', ' ', block.group(1))
    return re.findall(r'от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s+([^,\s)]+)', text)


def build_result(consultant_44, consultant_223, errors):
    lines = []

    if errors:
        lines.append(f"⚠️ Ошибки: {', '.join(errors)}")

    lines.append("🔍 consultant.ru (последние редакции):")

    def fmt(laws, label):
        if not laws:
            lines.append(f"  • {label}: данные не получены")
            return
        lines.append(f"  • {label}: {len(laws)} редакций")
        for dt, num in laws[-5:]:
            lines.append(f"      от {dt} N {num}")

    fmt(consultant_44, "44-ФЗ (контрактная система)")
    fmt(consultant_223, "223-ФЗ (закупки госкомпаний)")

    lines.append("")
    if consultant_44:
        lines.append(f"⚡ Последняя редакция 44-ФЗ: от {consultant_44[-1][0]} N {consultant_44[-1][1]}")
    if consultant_223:
        lines.append(f"⚡ Последняя редакция 223-ФЗ: от {consultant_223[-1][0]} N {consultant_223[-1][1]}")

    return "\n".join(lines)


def publish(result_text, consultant_44, consultant_223, errors):
    total = len(consultant_44) + len(consultant_223)
    meta = f"consultant.ru: {total} редакций"
    if errors:
        meta += f" · ошибки: {', '.join(errors)}"

    result_data = {
        "title": f"✅ Верификация — {NOW_MSK.strftime('%d.%m.%Y %H:%M')}",
        "meta": meta,
        "text": result_text
    }
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    stats_data = {
        "status_codex": "🟢" if consultant_44 else "🟡",
        "status_pp": "🟢" if consultant_223 else "🟡",
        "calls_today_display": str(total),
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
    consultant_44 = json.loads(sys.argv[sys.argv.index("--c44") + 1]) if "--c44" in sys.argv else []
    consultant_223 = json.loads(sys.argv[sys.argv.index("--c223") + 1]) if "--c223" in sys.argv else []
    errors = json.loads(sys.argv[sys.argv.index("--errors") + 1]) if "--errors" in sys.argv else []

    print(f"44-ФЗ: {len(consultant_44)} редакций")
    print(f"223-ФЗ: {len(consultant_223)} редакций")
    print(f"ошибки: {errors}")

    result_text = build_result(consultant_44, consultant_223, errors)
    publish(result_text, consultant_44, consultant_223, errors)
    print("✅ Готово")
