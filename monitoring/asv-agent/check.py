#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Автомониторинг АСВ: конкурсы банков-агентов + страховые случаи (отзывы лицензий).

Выход (stdout):
  CLEAN                              — новых событий нет
  KONKURS|ДД.ММ.ГГГГ|заголовок|url   — новый конкурс по отбору банков-агентов
  STRAKH |ДД.ММ.ГГГГ|заголовок|url   — новый страховой случай (отзыв лицензии)

Состояние (что уже видели) хранится в seen.json рядом со скриптом.
Первый запуск = базовый срез: всё помечается увиденным, алертов нет.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
STATE = os.environ.get("ASV_STATE", os.path.join(BASE, "seen.json"))
API = os.environ.get("ASV_API", "https://www.asv.org.ru/api/v1/")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

QUERIES = [
    "конкурс по отбору банков-агентов",
    "наступлении страхового случая",
]

def fetch(q):
    data = json.dumps({"action": "search.getList", "q": q, "lang": "ru"}).encode("utf-8")
    req = urllib.request.Request(API, data=data,
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def norm(s):
    return (s or "").replace("&nbsp;", " ").replace("\u00a0", " ").lower()

def classify(title):
    t = norm(title)
    if "конкурс по отбору банков-агентов" in t:
        return "KONKURS"
    if "наступлении страхового случая" in t:
        return "STRAKH"
    return None

def parse_date(s):
    try:
        return datetime.strptime((s or "").strip(), "%d.%m.%Y")
    except Exception:
        return None

def main():
    seen = {}
    if os.path.exists(STATE):
        try:
            loaded = json.load(open(STATE, encoding="utf-8"))
            if isinstance(loaded, dict):
                seen = loaded
        except Exception:
            seen = {}

    items = {}
    for q in QUERIES:
        try:
            d = fetch(q)
        except Exception as e:
            print(f"ERR fetch {q}: {e}", file=sys.stderr)
            continue
        for sec in d.get("sections", []):
            for it in sec.get("items", []):
                key = str(it.get("id")) or it.get("url") or (it.get("title", "")[:40])
                if key:
                    items[key] = it

    cutoff = datetime.now() - timedelta(days=30)
    new_events = []
    for key, it in items.items():
        c = classify(it.get("title", ""))
        if c is None:
            seen[key] = True
            continue
        # новое = id ещё не видели И дата достаточно свежая (защита от ранжировочных хвостов)
        if key not in seen:
            dt = parse_date(it.get("date", ""))
            if dt and dt >= cutoff:
                new_events.append((c, it))
            seen[key] = True

    json.dump(seen, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)

    if not new_events:
        print("CLEAN")
        return

    for c, it in sorted(new_events, key=lambda x: x[1].get("date", "")):
        dt = it.get("date", "")
        title = (it.get("title", "") or "").replace("&nbsp;", " ")
        url = it.get("url", "")
        print(f"{c}|{dt}|{title}|{url}")

if __name__ == "__main__":
    main()
