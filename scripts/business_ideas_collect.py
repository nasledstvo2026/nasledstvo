#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборщик сигналов для разведки бизнес-идей. Без LLM.
Вход: открытые RSS/API. Выход: /tmp/ideas_raw.json
"""
import json, os, re, hashlib, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

WS = "/home/user1/.openclaw/workspace"
STATE = os.path.join(WS, "knowledge/business-ideas/seen.json")
OUT = "/tmp/ideas_raw.json"
LOOKBACK_H = int(os.environ.get("LOOKBACK_H", "48"))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

SOURCES = [
  ("HN: Show HN", "https://hn.algolia.com/api/v1/search_by_date?query=Show%20HN&tags=story&hitsPerPage=40", "hn", 5),
  ("HN: AI agents", "https://hn.algolia.com/api/v1/search_by_date?query=AI%20agent&tags=story&hitsPerPage=30", "hn", 4),
  ("HN: SaaS", "https://hn.algolia.com/api/v1/search_by_date?query=SaaS&tags=story&hitsPerPage=25", "hn", 4),
  ("Product Hunt", "https://www.producthunt.com/feed", "rss", 5),
  ("TechCrunch startups", "https://techcrunch.com/category/startups/feed/", "rss", 5),
  ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "rss", 4),
  ("Y Combinator blog", "https://www.ycombinator.com/blog/rss", "rss", 4),
  ("Reddit: SaaS", "https://www.reddit.com/r/SaaS/top/.rss?t=day", "rss", 4),
  ("Reddit: smallbusiness", "https://www.reddit.com/r/smallbusiness/top/.rss?t=day", "rss", 4),
  ("Reddit: Entrepreneur", "https://www.reddit.com/r/Entrepreneur/top/.rss?t=day", "rss", 4),
  ("Reddit: AI_Agents", "https://www.reddit.com/r/AI_Agents/top/.rss?t=day", "rss", 3),
  ("vc.ru", "https://vc.ru/rss", "rss", 5),
  ("Habr news", "https://habr.com/ru/rss/news/", "rss", 4),
  ("CNews", "https://www.cnews.ru/inc/rss/news.xml", "rss", 4),
  ("OpenAI news", "https://openai.com/news/rss.xml", "rss", 2),
  ("AWS ML blog", "https://aws.amazon.com/blogs/machine-learning/feed/", "rss", 3),
  ("NVIDIA blog", "https://blogs.nvidia.com/feed/", "rss", 3),
]

IDEA_KW = ["agent","agentic","mcp","copilot","autonomous","saas","startup","launch","revenue","pricing",
           "subscription","marketplace","запустил","запуск","стартап","сервис","бизнес","заработ","выручк",
           "подписк","тариф","цена","кейс","внедр","нейросет","ии-","искусственн","автоматизац"]
MONEY_KW = ["revenue","arr","funding","raised","valuation","pricing","price","customers","subscribers",
            "profit","margin","acquisition","contract","выручк","раунд","оценк","цена","клиент",
            "подписчик","контракт","внедрен","доход","окупаем"]
DROP_KW = ["benchmark","leaderboard","we are hiring","job opening","webinar","podcast episode","birthday"]

def norm(t):
    t = re.sub(r"\s+", " ", (t or "")).strip().lower()
    return re.sub(r"[^\wа-яё ]+", "", t)[:160]

def hid(t): return hashlib.sha1(norm(t).encode("utf-8")).hexdigest()[:16]

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"&[a-z]+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_date(v):
    if not v: return None
    try: return parsedate_to_datetime(v.strip())
    except Exception: pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%SZ","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
        try: return datetime.strptime(v.replace("Z","+0000") if fmt.endswith("%z") else v, fmt)
        except Exception: continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v)
    return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)),tzinfo=timezone.utc) if m else None

def localname(tag): return tag.split("}")[-1].lower()

def parse_feed(data):
    items = []
    try: root = ET.fromstring(data)
    except Exception: return items
    for el in root.iter():
        if localname(el.tag) not in ("item","entry"): continue
        rec = {"title":"","url":"","date":None,"summary":""}
        for ch in el:
            n = localname(ch.tag); txt = (ch.text or "").strip()
            if n == "title": rec["title"] = strip_html(txt)
            elif n == "link":
                href = ch.attrib.get("href")
                rec["url"] = href or (txt if txt else rec["url"])
            elif n in ("pubdate","published","updated","date"):
                rec["date"] = rec["date"] or parse_date(txt)
            elif n in ("description","summary","content"):
                rec["summary"] = strip_html(txt)[:400]
        if rec["title"] and rec["url"]: items.append(rec)
    return items

def parse_hn(data):
    out = []
    try: js = json.loads(data.decode("utf-8","ignore"))
    except Exception: return out
    for h in js.get("hits", []):
        ts = h.get("created_at_i")
        out.append({"title": h.get("title") or "",
                    "url": h.get("url") or ("https://news.ycombinator.com/item?id=" + str(h.get("objectID"))),
                    "date": datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None,
                    "summary": "HN %s points, %s comments" % (h.get("points"), h.get("num_comments"))})
    return out

def load_seen():
    try:
        with open(STATE) as f: return json.load(f)
    except Exception: return {"ids": {}}

def main():
    seen = load_seen(); seen_ids = set(seen.get("ids", {}).keys())
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_H)
    results, stats = [], []
    for name, url, kind, weight in SOURCES:
        try:
            data = fetch(url)
            items = parse_hn(data) if kind == "hn" else parse_feed(data)
        except Exception as e:
            stats.append({"source":name,"ok":False,"err":str(e)[:110],"got":0}); continue
        kept = 0
        for it in items:
            title = it["title"]; low = title.lower()
            if len(title) < 25 or any(k in low for k in DROP_KW): continue
            d = it.get("date")
            if d is not None:
                if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
                if d < cutoff: continue
            if not any(k in low for k in IDEA_KW): continue
            iid = hid(title)
            if iid in seen_ids: continue
            blob = low + " " + (it.get("summary") or "").lower()
            money = any(k in blob for k in MONEY_KW)
            results.append({"id":iid,"source":name,"title":title,"url":it["url"],
                            "date": d.isoformat() if d else None,
                            "summary": it.get("summary","")[:300],
                            "score": weight + (3 if money else 0), "money": money})
            kept += 1
        stats.append({"source":name,"ok":True,"got":len(items),"kept":kept})
    results.sort(key=lambda x: (-x["score"], x["date"] or ""))
    with open(OUT,"w") as f:
        json.dump({"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(results[:150]),
                   "items":results[:150],"stats":stats}, f, ensure_ascii=False, indent=1)
    print("sources ok=%d/%d candidates=%d" % (len([s for s in stats if s.get("ok")]), len(stats), len(results[:150])))
    for s in stats:
        print("  %-22s %s got=%s kept=%s %s" % (s["source"], "OK " if s.get("ok") else "ERR", s.get("got"), s.get("kept",0), s.get("err","")))

if __name__ == "__main__":
    main()
