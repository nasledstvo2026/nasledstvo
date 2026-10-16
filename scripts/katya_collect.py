#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
katya_collect.py — сбор жалоб/кейсов по наследству в банках РФ (FR-17, search-agent).

Источники: banki.ru (лента type=all, встроенный JSON), pravoved.ru (Next.js JSON),
pikabu.ru (тег, cp1251), advgazeta.ru (HTML новости).

Пишет /tmp/raw_complaints.txt (URL | title | date | source) и /tmp/filtered.json.
Дедуп по нормализованному URL (без www и хвостового слеша) + seen-лист.
Никаких LLM здесь — только детерминированные шаги.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
SHARED = "/home/user1/.openclaw/agents/shared"
SEEN_FILE = os.path.join(SHARED, "katya-extra-seen.json")
RAW_TXT = "/tmp/raw_complaints.txt"
FILTERED = "/tmp/filtered.json"
MSK = timezone(timedelta(hours=3))

ALLOWED = ("banki.ru", "pravoved.ru", "pikabu.ru", "advgazeta.ru")

STEMS = ("наследств", "наследник", "наследодател", "завещан",
         "вклад умерш", "смерти вкладчик", "умершего вклад")

stats = {"requests": {}, "blocks": []}


def req(url: str, out: str, ref: str | None = None) -> str | None:
    dom = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    # кэш: недавно скачанный непустой файл — не тратим запрос
    try:
        if os.path.exists(out) and os.path.getsize(out) > 1000 and time.time() - os.path.getmtime(out) < 900:
            return "200"
    except Exception:
        pass
    code = "000"
    for attempt in range(3):
        stats["requests"][dom] = stats["requests"].get(dom, 0) + 1
        cmd = ["curl", "-s", "-A", UA, "-L", "--compressed", "-m", "25", "-o", out, "-w", "%{http_code}", url]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            code = (r.stdout or "").strip()
        except Exception as e:
            stats["blocks"].append(f"{dom}: {e}")
            return None
        if code == "200":
            return code
        stats["blocks"].append(f"{dom}: http={code} {url} (attempt {attempt+1})")
        time.sleep(4)
    return code


def norm(u: str) -> str:
    if not u:
        return ""
    u = u.strip()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.rstrip("/")
    return u.lower()


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def load_seen() -> set:
    try:
        d = json.load(open(SEEN_FILE, encoding="utf-8"))
        return {norm(u) for u in d.get("urls", [])}
    except Exception:
        return set()


def topic_ok(text: str) -> bool:
    t = (text or "").lower()
    return any(s in t for s in STEMS)


# ---------------- banki.ru ----------------
def collect_banki(pages=12):
    out = []
    seen_ids = set()
    for p in range(1, pages + 1):
        f = f"/tmp/bk_all_{p}.html"
        code = req(f"https://www.banki.ru/services/responses/list/?type=all&page={p}", f)
        if code != "200":
            stats["blocks"].append(f"banki: stop at page {p}")
            break
        try:
            h = open(f, encoding="utf-8").read()
        except Exception:
            continue
        blobs = re.findall(r"data-module-options='(.*?)'\s", h, re.S)
        got = 0
        for b in blobs:
            try:
                d = json.loads(html.unescape(b))
            except Exception:
                continue
            r = d.get("responses") if isinstance(d, dict) else None
            if not isinstance(r, dict) or not isinstance(r.get("data"), list):
                continue
            for it in r["data"]:
                iid = it.get("id")
                if not iid or iid in seen_ids:
                    continue
                seen_ids.add(iid)
                title = (it.get("title") or "").strip()
                text = strip_tags(it.get("text") or "")
                bank = ((it.get("company") or {}).get("name") or "").strip() or None
                dt = (it.get("dateCreate") or "")[:10] or None
                out.append({
                    "url": f"https://www.banki.ru/services/responses/bank/response/{iid}/",
                    "title": title,
                    "date": dt,
                    "source": "banki.ru",
                    "text": text,
                    "bank": bank,
                })
                got += 1
        if got == 0:
            break
        time.sleep(2)
    return out


# ---------------- pravoved.ru ----------------
def _pv_search_items(h: str):
    """SSR-страница поиска pravoved.ru (без __NEXT_DATA__)."""
    res = []
    for m in re.finditer(r'<article class="questionBody.*?</article>', h, re.S):
        blk = m.group(0)
        iid = re.search(r'/question/(\d+)/', blk)
        tl = re.search(r'<div class="divH3">\s*<a[^>]*>(.*?)</a>', blk, re.S)
        tx = re.search(r'question__content">(.*?)</div>', blk, re.S)
        if not iid:
            continue
        res.append({
            "url": f"https://pravoved.ru/question/{iid.group(1)}/",
            "title": strip_tags(tl.group(1)) if tl else "",
            "date": None,
            "source": "pravoved.ru",
            "text": strip_tags(tx.group(1)) if tx else "",
            "bank": None,
        })
    return res


def _pv_items(h: str):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    if not m:
        return []
    try:
        d = json.loads(m.group(1))
    except Exception:
        return []
    try:
        items = d["props"]["pageProps"]["reduxState"]["page"]["questions"]["questions"]["items"]
    except Exception:
        return []
    if isinstance(items, dict):
        items = list(items.values())
    res = []
    for it in items:
        iid = it.get("id")
        if not iid:
            continue
        dp = it.get("datePublish")
        try:
            dt = datetime.fromtimestamp(dp, timezone.utc).astimezone(MSK).strftime("%Y-%m-%d") if dp else None
        except Exception:
            dt = None
        res.append({
            "url": f"https://pravoved.ru/question/{iid}/",
            "title": (it.get("title") or "").strip(),
            "date": dt,
            "source": "pravoved.ru",
            "text": strip_tags(it.get("text") or ""),
            "bank": None,
        })
    return res


def collect_pravoved():
    out = []
    f = "/tmp/pv_feed.html"
    if req("https://pravoved.ru/questions/", f) == "200":
        try:
            out += _pv_items(open(f, encoding="utf-8").read())
        except Exception:
            pass
        time.sleep(1.5)
    qs = ["%D0%BD%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE%20%D0%B1%D0%B0%D0%BD%D0%BA",
          "%D0%B2%D0%BA%D0%BB%D0%B0%D0%B4%20%D1%83%D0%BC%D0%B5%D1%80%D1%88%D0%B5%D0%B3%D0%BE",
          "%D0%B7%D0%B0%D0%B2%D0%B5%D1%89%D0%B0%D0%BD%D0%B8%D0%B5%20%D1%81%D1%87%D0%B5%D1%82%20%D0%B1%D0%B0%D0%BD%D0%BA"]
    for q in qs:
        f = f"/tmp/pv_s_{abs(hash(q))%9999}.html"
        code = req(f"https://pravoved.ru/search/?q={q}", f)
        if code != "200":
            break
        try:
            hh = open(f, encoding="utf-8").read()
            got = _pv_items(hh) or _pv_search_items(hh)
            out += got
        except Exception:
            pass
        time.sleep(1.5)
    return out


# ---------------- pikabu.ru ----------------
def collect_pikabu():
    out = []
    urls = ["https://pikabu.ru/tag/%D0%9D%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE",
            "https://pikabu.ru/tag/%D0%9D%D0%B0%D1%81%D0%BB%D0%B5%D0%B4%D1%81%D1%82%D0%B2%D0%BE?page=2"]
    for i, u in enumerate(urls, 1):
        f = f"/tmp/pk_{i}.html"
        code = req(u, f)
        if code != "200":
            break
        try:
            h = open(f, "rb").read().decode("cp1251", errors="replace")
        except Exception:
            continue
        for m in re.finditer(r'<article class="story"(.*?)</article>', h, re.S):
            blk = m.group(1)
            sid = re.search(r'data-story-id="(\d+)"', blk)
            ts = re.search(r'data-timestamp="(\d+)"', blk)
            tl = re.search(r'story__title-link"[^>]*>(.*?)</a>', blk, re.S)
            if not sid:
                continue
            title = re.sub(r"\s+", " ", strip_tags(tl.group(1))) if tl else ""
            dt = None
            if ts:
                try:
                    dt = datetime.fromtimestamp(int(ts.group(1)), timezone.utc).astimezone(MSK).strftime("%Y-%m-%d")
                except Exception:
                    dt = None
            slug = re.search(r'href="https://pikabu\.ru/story/([a-z0-9_\-]+)"', blk)
            slug = slug.group(1) if slug else f"story_{sid.group(1)}"
            out.append({
                "url": f"https://pikabu.ru/story/{slug}",
                "title": title,
                "date": dt,
                "source": "pikabu.ru",
                "text": title,
                "bank": None,
            })
        time.sleep(2)
    return out


# ---------------- advgazeta.ru ----------------
def collect_advg():
    out = []
    f = "/tmp/advg_nov.html"
    if req("https://www.advgazeta.ru/novosti/", f) != "200":
        return out
    try:
        h = open(f, encoding="utf-8").read()
    except Exception:
        return out
    for m in re.finditer(r'<a[^>]+href="(/novosti/[a-z0-9\-]+/)"[^>]*>(.*?)</a>', h, re.S):
        href, inner = m.group(1), strip_tags(m.group(2))
        if len(inner) < 15:
            continue
        out.append({
            "url": "https://www.advgazeta.ru" + href,
            "title": inner[:200],
            "date": None,
            "source": "advgazeta.ru",
            "text": inner[:400],
            "bank": None,
        })
    return out


def main():
    seen = load_seen()
    items = []
    items += collect_banki()
    items += collect_pravoved()
    items += collect_pikabu()
    items += collect_advg()

    total = len(items)
    # домены
    dom = [x for x in items if x["source"] in ALLOWED]
    # тема
    them = [x for x in dom if topic_ok(x["title"] + " " + x.get("text", ""))]
    # dedup + seen
    seen_set = set(seen)
    final = []
    for x in them:
        n = norm(x["url"])
        if n in seen_set:
            continue
        seen_set.add(n)
        final.append(x)

    with open(RAW_TXT, "w", encoding="utf-8") as fh:
        for x in items:
            mark = "SEEN" if norm(x["url"]) in seen else "NEW"
            fh.write(f'{x["url"]} | {x["title"]} | {x["date"] or ""} | {x["source"]} | {mark}\n')
    with open(FILTERED, "w", encoding="utf-8") as fh:
        json.dump(final, fh, ensure_ascii=False, indent=1)

    print("=== COUNTERS ===")
    print("collected:", total)
    print("after domains:", len(dom))
    print("after topic:", len(them))
    print("after seen+dedup (final):", len(final))
    print("per-source collected:", {s: sum(1 for x in items if x["source"] == s) for s in ALLOWED})
    print("requests:", stats["requests"])
    print("blocks:", stats["blocks"] or "none")
    for x in final:
        print(f'  [{x["source"]}] {x["date"]} | {x["title"][:80]}')


if __name__ == "__main__":
    main()
