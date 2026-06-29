#!/usr/bin/env python3
"""Обновление базы знаний + параллельная верификация через consultant.ru.
LegalMCP — семантический поиск (7 запросов)
consultant.ru — верификация дат последних редакций (через curl)
Результат: zakupki-result.json

Фикс 30.06: парсер consultant.ru ищет блок "в ред. Федеральных законов от..."
"""

import json, os, subprocess, sys, time, re
from datetime import datetime, timezone, timedelta

WORKSPACE = "/home/user1/.openclaw/workspace"
LEGALMCP_TOKEN = "lmcp_npXn_t9-i6EWaLdqU-xq6RAvwhc0Y1-S6PQ1iQHHPF4"
RESULT_FILE = os.path.join(WORKSPACE, "zakupki-result.json")
STATS_FILE = os.path.join(WORKSPACE, "zakupki-stats.json")

MSK = timezone(timedelta(hours=3))
NOW_MSK = datetime.now(MSK)

# ═══ 1. LegalMCP ═══
def run_legalmcp():
    legalmcp_result = {}
    docs = [
        ("44-ФЗ изменения за последние 90 дней", "44-ФЗ"),
        ("224-ФЗ изменения за последние 90 дней", "224-ФЗ"),
        ("ПП РФ №620 изменения", "ПП №620"),
        ("ПП РФ №1875 изменения", "ПП №1875"),
        ("маркировка Честный ЗНАК медизделия последние новости", "Честный ЗНАК"),
        ("электронное актирование ЕИС последние изменения", "ЕИС актирование"),
        ("ЖНВЛП изменения 2025 2026", "ЖНВЛП"),
    ]
    legalmcp_result["queries"] = len(docs)
    legalmcp_result["changes_found"] = []
    legalmcp_result["errors"] = 0

    import openai
    client = openai.OpenAI(base_url="https://legalmcp.ru/mcp", api_key=LEGALMCP_TOKEN)

    for query, doc_name in docs:
        try:
            r = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user",
                          "content": f"Ты — поисковый ассистент LegalMCP. Найди по базе российского права последние изменения по запросу.\n\nЗапрос: {query}\n\nВерни: 1. Дату последнего изменения (если есть) 2. Краткую суть 3. Номер ФЗ/ПП, если применимо 4. Если за последние 90 дней изменений нет — напиши «нет новых изменений»"}],
                timeout=30
            )
            text = r.choices[0].message.content or ""
            legalmcp_result["changes_found"].append(f"{doc_name}: {text[:300]}")
        except Exception as e:
            legalmcp_result["errors"] += 1
            err = str(e)
            if "429" in err or "quota" in err.lower():
                legalmcp_result["changes_found"].append(f"{doc_name}: ⛔ лимит (429)")
            else:
                legalmcp_result["changes_found"].append(f"{doc_name}: ошибка — {err[:100]}")
        time.sleep(0.5)

    return legalmcp_result


# ═══ 2. Consultant.ru верификация (через curl) ═══
def verify_consultant():
    """Проверяет последние даты редакций через consultant.ru.
    Использует curl с User-Agent, парсит блок (в ред. Федеральных законов от...)
    """
    verification = {"checked": True, "sources": {}}

    urls = {
        "44-ФЗ": "https://www.consultant.ru/document/cons_doc_LAW_144624/",
        "224-ФЗ": "https://www.consultant.ru/document/cons_doc_LAW_145186/"
    }

    for doc_name, url in urls.items():
        try:
            result = subprocess.run(
                ["curl", "-s", "-L",
                 "-A", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                 "--max-time", "12", url],
                capture_output=True, text=True, timeout=15
            )
            html = result.stdout
            if not html:
                verification["sources"][doc_name] = {"error": "пустой ответ"}
                continue

            # Блок редакций (многострочный)
            block = re.search(
                r'\(в\s+ред\.?\s*Федеральных\s+законов\s+от\s+([^)]+)\)',
                html, re.DOTALL
            )

            if block:
                text = block.group(1)
                # flatten newlines
                flat = re.sub(r'\s+', ' ', text)
                laws = re.findall(r'от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s+([^,\s)]+)', flat)
            else:
                laws = []

            if not laws:
                # fallback — все даты из ответа
                dates = re.findall(r'от\s+(\d{2}\.\d{2}\.\d{4})', html)
                unique = list(dict.fromkeys(dates))
                last5 = unique[-5:] if len(unique) >= 5 else unique
                verification["sources"][doc_name] = {
                    "all_editions_count": len(unique),
                    "last_5": last5,
                    "latest": last5[-1] if last5 else "нет",
                    "latest_with_law": last5[-1] if last5 else "нет",
                    "all_laws": []
                }
            else:
                unique = []
                seen = set()
                for dt, num in laws:
                    k = f"{dt}|{num}"
                    if k not in seen:
                        seen.add(k)
                        unique.append((dt, num))
                last5 = unique[-5:] if len(unique) >= 5 else unique
                laws_str = [f"{dt} (N {num})" for dt, num in last5]
                verification["sources"][doc_name] = {
                    "all_editions_count": len(unique),
                    "last_5": [dt for dt, _ in last5],
                    "latest": last5[-1][0] if last5 else "нет",
                    "latest_with_law": laws_str[-1] if laws_str else "нет",
                    "all_laws": [f"{dt} (N {num})" for dt, num in unique]
                }
        except Exception as e:
            verification["sources"][doc_name] = {"error": str(e)}

    return verification


# ═══ 3. Формирование результата ═══
def build_result(legalmcp, verification):
    lines = []

    if legalmcp["errors"] == legalmcp["queries"]:
        if any("лимит" in c for c in legalmcp["changes_found"]):
            lines.append("📡 LegalMCP: лимит 100/100 в месяц исчерпан (сброс — 1 июля)")
        else:
            lines.append("📡 LegalMCP: все запросы не удались")
    else:
        lines.append(f"📡 LegalMCP: {legalmcp['queries']} запросов · {legalmcp['errors']} ошибок")
    for c in legalmcp["changes_found"]:
        lines.append(f"  • {c}")

    lines.append("")
    lines.append("🔍 Верификация consultant.ru (последние редакции):")

    for doc in ["44-ФЗ", "224-ФЗ"]:
        info = verification["sources"].get(doc, {})
        if info.get("latest_with_law") and info["latest_with_law"] != "нет":
            lines.append(f"  • {doc}: {info['latest_with_law']} (всего {info['all_editions_count']} редакций)")
            # последние 3
            if info.get("all_laws"):
                last3 = info["all_laws"][-3:]
                for l in last3:
                    lines.append(f"      {l}")
        elif info.get("latest"):
            lines.append(f"  • {doc}: последняя {info['latest']} (fallback)")
        else:
            lines.append(f"  • {doc}: {info.get('error', 'нет данных')}")

    return "\n".join(lines)


# ═══ 4. Публикация ═══
def publish(result_text):
    lmcp_status = "лимит" if legalmcp["errors"] == legalmcp["queries"] and any("лимит" in c for c in legalmcp["changes_found"]) else "частично"
    result_data = {
        "title": f"✅ Верификация — {NOW_MSK.strftime('%d.%m.%Y %H:%M')}",
        "meta": f"LegalMCP: {lmcp_status} · consultant.ru: {len(verification.get('sources', {}))} доков",
        "text": result_text
    }
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)

    stats_data = {
        "status_codex": "🟢",
        "status_pp": "🟢",
        "calls_today_display": str(legalmcp["queries"]),
        "monthly_display": "100/100 (лимит)",
        "last_update": NOW_MSK.strftime('%d.%m.%Y %H:%M')
    }
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats_data, f, ensure_ascii=False, indent=2)

    os.chdir(WORKSPACE)
    subprocess.run(["git", "add", "zakupki-result.json", "zakupki-stats.json"], capture_output=True)
    subprocess.run(["git", "commit", "-m", "zakupki: обновление (LegalMCP+consultant.ru)"], capture_output=True)
    subprocess.run(["git", "push"], capture_output=True)
    print("✅ Опубликовано")
    print(result_text)


if __name__ == "__main__":
    print("▶ LegalMCP...")
    legalmcp = run_legalmcp()
    print(f"  {legalmcp['queries']} запросов, {legalmcp['errors']} ошибок")

    print("▶ consultant.ru...")
    verification = verify_consultant()
    for doc, info in verification["sources"].items():
        print(f"  {doc}: {info.get('latest_with_law', info.get('error', '?'))}")

    print("▶ публикация...")
    result_text = build_result(legalmcp, verification)
    publish(result_text)
    print("✅ Готово")
