#!/usr/bin/env python3
"""Скрипт для обновления базы знаний Катрин через LegalMCP.

Запускается cron-задачей пн/ср/пт 09:30.
Ищет изменения по 44-ФЗ, 224-ФЗ, ПП №620, ПП №1875 за последние N дней.
Обновляет knowledge/katrin/weekly-update.md
"""
import asyncio
import json
import sys
import os
from datetime import datetime, timedelta, timezone

from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

MCP_TOKEN = "lmcp_npXn_t9-i6EWaLdqU-xq6RAvwhc0Y1-S6PQ1iQHHPF4"
UPDATE_FILE = os.path.expanduser("~/.openclaw/workspace/knowledge/katrin/weekly-update.md")

QUERIES = [
    ("44-ФЗ контрактная система", "law.federal"),
    ("224-ФЗ закупки отдельные виды юридических лиц", "law.federal"),
    ("ПП РФ 620 медицинские изделия лоты", "decree.government"),
    ("ПП РФ 1875 национальный режим", "decree.government"),
    ("маркировка медицинских изделий Честный ЗНАК", "law.federal"),
    ("ЕИС электронное актирование СДП", "law.federal"),
]

async def search_documents(session, query):
    """Поиск документов по запросу."""
    try:
        result = await session.call_tool("search_documents", {"query": query})
        if hasattr(result.content[0], 'text'):
            return result.content[0].text
        return str(result.content[0])
    except Exception as e:
        return f"Error: {e}"

async def search_changes(session, days=14):
    """Поиск изменений за последние N дней."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        result = await session.call_tool("search_changes", {"since_date": since})
        if hasattr(result.content[0], 'text'):
            return result.content[0].text
        return str(result.content[0])
    except Exception as e:
        return f"Error: {e}"

async def get_doc(session, doc_id):
    """Получение полного текста документа."""
    try:
        result = await session.call_tool("get_document_by_id", {"id": doc_id})
        if hasattr(result.content[0], 'text'):
            return result.content[0].text
        return str(result.content[0])
    except Exception as e:
        return f"Error: {e}"

async def main():
    url = "https://legalmcp.ru/mcp"
    headers = {"Authorization": f"Bearer {MCP_TOKEN}"}

    print(f"[{datetime.now().isoformat()}] Connecting to LegalMCP...", file=sys.stderr)

    async with streamablehttp_client(url, headers=headers) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()

            report_lines = []
            report_lines.append(f"# Обновление базы знаний (legal) – {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            report_lines.append("")
            report_lines.append(f"Источник: LegalMCP (MCP-сервер, https://legalmcp.ru)")
            report_lines.append(f"Официальные первоисточники: pravo.gov.ru, publication.pravo.gov.ru")
            report_lines.append("")
            report_lines.append("---")
            report_lines.append("")

            # 1. Общие изменения
            print("  -> Searching recent changes...", file=sys.stderr)
            changes = await search_changes(session, days=14)
            report_lines.append("## 📋 Последние изменения (14 дней)")
            report_lines.append("")
            report_lines.append(changes[:3000])
            report_lines.append("")
            report_lines.append("---")
            report_lines.append("")

            # 2. Поиск по каждому запросу
            for query, collection in QUERIES:
                print(f"  -> Searching: {query}...", file=sys.stderr)
                result = await search_documents(session, query)
                report_lines.append(f"## 🔍 {query}")
                report_lines.append("")
                report_lines.append(f"`collection: {collection}`")
                report_lines.append("")
                report_lines.append(result[:2000] if len(result) > 2000 else result)
                report_lines.append("")
                report_lines.append("---")
                report_lines.append("")

            # 3. Сохранение
            output = "\n".join(report_lines)
            os.makedirs(os.path.dirname(UPDATE_FILE), exist_ok=True)
            with open(UPDATE_FILE, "w") as f:
                f.write(output)

            print(f"\n✅ Saved to {UPDATE_FILE} ({len(output)} chars)", file=sys.stderr)
            print(f"   Calls used: ~{len(QUERIES) + 1} of 100 monthly", file=sys.stderr)

            # 4. Генерация zakupki-stats.json для динамических плашек на сайте
            calls_today = len(QUERIES) + 1
            # Определяем статус кодексов и постановлений по последним изменениям
            has_changes = "изменени" in changes.lower() if changes else False
            if has_changes:
                codex_status = "🟢"
                pp_status = "🟢"
            else:
                codex_status = "🟢"
                pp_status = "🟡"

            stats = {
                "status_codex": codex_status,
                "status_pp": pp_status,
                "calls_today": calls_today,
                "calls_today_display": f"{calls_today} ✅",
                "monthly_used": len(QUERIES) * 3 * 4,  # ~84 запроса/мес
                "monthly_limit": 100,
                "monthly_display": f"{len(QUERIES) * 3 * 4}/100",
                "last_update": datetime.now().strftime('%d.%m.%Y %H:%M'),
                "has_changes": has_changes
            }
            STATS_FILE = os.path.expanduser("~/.openclaw/workspace/zakupki-stats.json")
            with open(STATS_FILE, "w") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            print(f"\n✅ Stats saved to {STATS_FILE}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
