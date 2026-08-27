#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
katya_source_probe.py — проверка парсируемости источников жалоб по наследству.

Что делает: по каждому источнику дёргает набор кандидатных URL (лента / поиск / карточка /
rss / sitemap), измеряет код, размер, наличие тематических стемов, число ссылок на материалы,
наличие дат, признаки JS-заглушки. Запросы к одному домену — последовательно с троттлингом
(banki.ru банит за пачку запросов), домены — параллельно.

Запуск:
  python3 scripts/katya_source_probe.py                # все источники
  python3 scripts/katya_source_probe.py banki pravoved # только выбранные
Результат: таблица в stdout + JSON в /tmp/katya_source_probe.json
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import re
import subprocess
import sys
import time
from urllib.parse import quote

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
THROTTLE = 2.5          # сек между запросами к одному домену
TIMEOUT = 20
STEMS = ("наследств", "наследник", "наследодател", "завещан", "вклад умерш", "умершего")
Q = quote("наследство банк")
QN = quote("наследство")

# домен → [(метка, url, регэксп ссылок на материалы)]
SOURCES: dict[str, list[tuple[str, str, str]]] = {
    "banki.ru": [
        ("лента отзывов стр.1", "https://www.banki.ru/services/responses/list/?page=1", r"/services/responses/bank/response/\d+/"),
        ("лента отзывов стр.4", "https://www.banki.ru/services/responses/list/?page=4", r"/services/responses/bank/response/\d+/"),
        ("карточка отзыва", "https://www.banki.ru/services/responses/bank/response/13316680/", r"/services/responses/bank/response/\d+/"),
        ("новости RSS", "https://www.banki.ru/xml/news.rss", r"<link>([^<]+)</link>"),
        ("sitemap", "https://www.banki.ru/sitemap.xml", r"<loc>([^<]+)</loc>"),
    ],
    "pravoved.ru": [
        ("поиск", f"https://pravoved.ru/search/?q={Q}", r"/question/\d+/"),
        ("лента вопросов", "https://pravoved.ru/questions/", r"/question/\d+/"),
        ("карточка вопроса", "https://pravoved.ru/question/5026251/", r"/question/\d+/"),
    ],
    "pikabu.ru": [
        ("поиск", f"https://pikabu.ru/search?q={Q}&d=30", r"/story/[\w\-]+_\d+"),
        ("тег Наследство", f"https://pikabu.ru/tag/{quote('Наследство')}", r"/story/[\w\-]+_\d+"),
        ("RSS тега", f"https://pikabu.ru/xmlrss/tag/{quote('Наследство')}", r"<link>([^<]+)</link>"),
        ("карточка story", "https://pikabu.ru/story/nasledovanie_14203561", r"/story/[\w\-]+_\d+"),
    ],
    "otzovik.com": [
        ("лента банков", "https://otzovik.com/reviews/banki/", r"/review_\d+\.html"),
        ("поиск", f"https://otzovik.com/search/?text={QN}", r"/review_\d+\.html"),
        ("sitemap", "https://otzovik.com/sitemap.xml", r"<loc>([^<]+)</loc>"),
    ],
    "sravni.ru": [
        ("новости", "https://www.sravni.ru/novosti/", r"/novosti/[\w\-]+/"),
        ("вопросы-ответы", "https://www.sravni.ru/q/", r"/q/[\w\-]+/"),
        ("поиск", f"https://www.sravni.ru/search/?q={QN}", r"/(novosti|q)/[\w\-]+/"),
    ],
    "9111.ru": [
        ("лента вопросов", "https://www.9111.ru/questions/", r"/questions/[\w\-]+/"),
        ("поиск", f"https://www.9111.ru/search/?q={QN}", r"/questions/[\w\-]+/"),
    ],
    "asn-news.ru": [
        ("лента новостей", "https://www.asn-news.ru/news", r"/news/\d+"),
        ("поиск", f"https://www.asn-news.ru/search?q={QN}", r"/news/\d+"),
    ],
    "advgazeta.ru": [
        ("новости", "https://www.advgazeta.ru/novosti/", r"/novosti/[\w\-]+/"),
        ("RSS", "https://www.advgazeta.ru/rss/news.xml", r"<link>([^<]+)</link>"),
    ],
    "kp.ru": [
        ("поиск", f"https://www.kp.ru/search/?q={QN}", r"/(daily|online)/\d+"),
        ("RSS экономика", "https://www.kp.ru/rss/economics.xml", r"<link>([^<]+)</link>"),
    ],
}


def fetch(url: str, follow: bool = True) -> dict:
    args = ["curl", "-s", "-A", UA, "-m", str(TIMEOUT), "--compressed"]
    if follow:
        args += ["-L", "--max-redirs", "3"]
    args += ["-w", "\n__META__%{http_code}|%{time_total}|%{size_download}|%{url_effective}", url]
    p = subprocess.run(args, capture_output=True)
    raw = p.stdout
    meta = {"code": "000", "time": 0.0, "size": 0, "final": url}
    body = raw
    if b"__META__" in raw:
        body, m = raw.rsplit(b"\n__META__", 1)
        parts = m.decode("utf-8", "ignore").split("|")
        if len(parts) >= 4:
            meta = {"code": parts[0], "time": float(parts[1] or 0), "size": int(parts[2] or 0), "final": parts[3]}
    text = body.decode("utf-8", "ignore")
    if text.count("\ufffd") > 50 or "windows-1251" in text[:2000].lower() or "charset=cp1251" in text[:2000].lower():
        try:
            text = body.decode("cp1251", "ignore")
        except Exception:
            pass
    return {**meta, "html": text}


def analyse(label: str, url: str, link_re: str, r: dict) -> dict:
    html = r["html"]
    plain = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    plain = re.sub(r"<style.*?</style>", " ", plain, flags=re.S | re.I)
    plain = re.sub(r"<[^>]+>", " ", plain)
    low = plain.lower()
    stems = {s: low.count(s) for s in STEMS if s in low}
    links = sorted(set(re.findall(link_re, html)))
    dates = set(re.findall(r'"datePublished"\s*:\s*"([^"]{10,25})"', html))
    dates |= set(re.findall(r'datetime="([^"]{10,25})"', html))
    dates |= set(re.findall(r"\b(\d{2}\.\d{2}\.20\d{2})\b", plain))
    words = len(plain.split())
    scripts = html.lower().count("<script")
    js_stub = r["size"] > 0 and words < 400 and scripts > 5
    if r["code"] != "200" or r["size"] < 3000:
        verdict = "❌ недоступно"
    elif js_stub:
        verdict = "❌ JS-заглушка"
    elif stems and links:
        verdict = "✅ парсится"
    elif links and dates:
        verdict = "⚠️ ссылки есть, темы нет"
    elif stems:
        verdict = "⚠️ текст есть, ссылок нет"
    else:
        verdict = "⚠️ пусто по теме"
    return {
        "label": label, "url": url, "code": r["code"], "sec": round(r["time"], 2),
        "kb": round(r["size"] / 1024), "words": words, "links": len(links),
        "stems": stems, "dates": len(dates), "date_sample": sorted(dates)[:3],
        "final": r["final"] if r["final"] != url else None, "verdict": verdict,
    }


def probe_domain(domain: str, items: list) -> list[dict]:
    out = []
    for i, (label, url, link_re) in enumerate(items):
        if i:
            time.sleep(THROTTLE)
        r = fetch(url)
        out.append(analyse(label, url, link_re, r))
    return out


def main(argv):
    picked = {d: v for d, v in SOURCES.items() if not argv or any(a.lower() in d for a in argv)}
    results: dict[str, list] = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(probe_domain, d, items): d for d, items in picked.items()}
        for f in cf.as_completed(futs):
            results[futs[f]] = f.result()
    for d in picked:
        print(f"\n╔═ {d}")
        for r in results.get(d, []):
            st = ", ".join(f"{k}×{v}" for k, v in list(r["stems"].items())[:3]) or "—"
            print(f"║ {r['verdict']:<24} {r['label']:<22} http={r['code']} {r['kb']:>4}КБ "
                  f"{r['sec']:>5.2f}с слов={r['words']:>6} ссылок={r['links']:>3} даты={r['dates']:>3} стемы: {st}")
            if r["final"]:
                print(f"║ {'':24} └─ редирект → {r['final'][:90]}")
            if r["date_sample"]:
                print(f"║ {'':24} └─ примеры дат: {r['date_sample']}")
    json.dump(results, open("/tmp/katya_source_probe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\nвсего {sum(len(v) for v in results.values())} запросов за {time.time()-t0:.1f}с → /tmp/katya_source_probe.json")


if __name__ == "__main__":
    main(sys.argv[1:])
