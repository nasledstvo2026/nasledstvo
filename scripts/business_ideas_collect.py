#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сбор сигналов по агентной экономике и бизнес-идеям. Без LLM.
Профиль: публицистика + новости + исследования. Выход: /tmp/ideas_raw.json
"""
import json, os, re, hashlib, urllib.request, concurrent.futures as cf
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

WS = "/home/user1/.openclaw/workspace"
STATE = os.path.join(WS, "knowledge/business-ideas/seen.json")
OUT = "/tmp/ideas_raw.json"
LOOKBACK_H = int(os.environ.get("LOOKBACK_H", "48"))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

S = [
 # --- исследования / венчурные отчёты ---
 ("Menlo Ventures","https://menlovc.com/feed/","rss",6),
 ("Sequoia","https://www.sequoiacap.com/feed/","rss",5),
 ("Greylock","https://greylock.com/feed/","rss",5),
 ("Battery","https://www.battery.com/feed/","rss",4),
 ("Madrona","https://www.madrona.com/feed/","rss",4),
 ("McKinsey","https://www.mckinsey.com/insights/rss","rss",5),
 ("arXiv cs.MA","https://export.arxiv.org/api/query?search_query=cat:cs.MA&sortBy=submittedDate&sortOrder=descending&max_results=30","rss",3),
 ("arXiv econ.GN","https://export.arxiv.org/api/query?search_query=cat:econ.GN+AND+all:agent&sortBy=submittedDate&sortOrder=descending&max_results=20","rss",4),
 # --- публицистика / аналитика ---
 ("One Useful Thing","https://www.oneusefulthing.org/feed","rss",5),
 ("AI Snake Oil","https://www.aisnakeoil.com/feed","rss",4),
 ("Exponential View","https://www.exponentialview.co/feed","rss",4),
 ("Benedict Evans","https://www.ben-evans.com/benedictevans?format=rss","rss",4),
 ("Interconnects","https://www.interconnects.ai/feed","rss",4),
 ("Simon Willison","https://simonwillison.net/atom/everything/","rss",3),
 ("Platformer","https://www.platformer.news/feed","rss",3),
 ("Not Boring","https://www.notboring.co/feed","rss",3),
 ("Import AI","https://importai.substack.com/feed","rss",4),
 ("TLDR AI","https://tldr.tech/api/rss/ai","rss",4),
 ("Latent Space","https://www.latent.space/feed","rss",4),
 ("Lenny's Newsletter","https://www.lennysnewsletter.com/feed","rss",4),
 ("Towards Data Science","https://towardsdatascience.com/feed","rss",3),
 # --- новости ---
 ("MIT Tech Review","https://www.technologyreview.com/feed/","rss",5),
 ("Wired","https://www.wired.com/feed/rss","rss",4),
 ("Ars Technica","https://feeds.arstechnica.com/arstechnica/index","rss",3),
 ("The Verge","https://www.theverge.com/rss/index.xml","rss",3),
 ("Sifted","https://sifted.eu/feed","rss",4),
 ("Axios","https://api.axios.com/feed/","rss",4),
 ("The Rundown","https://www.therundown.ai/feed","rss",3),
 # --- продукты / релизы ---
 ("Product Hunt","https://www.producthunt.com/feed","rss",5),
 ("YC blog","https://www.ycombinator.com/blog/rss","rss",5),
 ("Hugging Face","https://huggingface.co/blog/feed.xml","rss",3),
 ("n8n","https://n8n.io/blog/rss/","rss",3),
 ("Salesforce","https://www.salesforce.com/blog/feed/","rss",3),
 ("Microsoft AI","https://news.microsoft.com/source/topics/ai/feed/","rss",3),
 ("Stripe","https://stripe.com/blog/feed.rss","rss",3),
 ("Cloudflare","https://blog.cloudflare.com/rss/","rss",3),
 ("Discord","https://discord.com/blog/rss.xml","rss",2),
 # --- РФ ---
 ("CNews","https://www.cnews.ru/inc/rss/news.xml","rss",5),
 ("vc.ru","https://vc.ru/rss","rss",5),
 ("Habr","https://habr.com/ru/rss/news/","rss",4),
 ("Frank Media","https://frankmedia.ru/feed","rss",4),
 ("RB.ru","https://rb.ru/feeds/news/","rss",4),
 ("Vedomosti","https://www.vedomosti.ru/rss/articles","rss",4),
 ("Inc Russia","https://incrussia.ru/feed/","rss",3),
 ("Cossa","https://www.cossa.ru/rss/","rss",3),
 ("Banki.ru","https://www.banki.ru/xml/news.rss","rss",3),
 # --- доп. ---
 ("Hacker News","https://hn.algolia.com/api/v1/search_by_date?query=Show%20HN&tags=story&hitsPerPage=40","hn",5),
]

IDEA_KW = ["agent","agentic","mcp","copilot","saas","startup","launch","revenue","pricing","subscription",
 "marketplace","fund","seed","series","acquisition","valuation","enterprise","adoption","automation",
 "запустил","запуск","стартап","сервис","бизнес","заработ","выручк","подписк","тариф","цена","кейс",
 "внедр","нейросет","ии-","искусственн","автоматизац","агент"]
MONEY_KW = ["revenue","arr","funding","raised","valuation","pricing","price","customers","subscribers",
 "profit","margin","acquisition","contract","adoption","выручк","раунд","оценк","цена","клиент",
 "подписчик","контракт","внедрен","доход","окупаем"]
DROP_KW = ["benchmark","leaderboard","we are hiring","job opening","webinar","podcast episode"]
RESEARCH = {"Menlo Ventures","McKinsey","Sequoia","Greylock","Battery","Madrona","arXiv cs.MA","arXiv econ.GN"}

def norm(t):
    t = re.sub(r"\s+"," ",(t or "")).strip().lower()
    return re.sub(r"[^\wа-яё ]+","",t)[:160]
def hid(t): return hashlib.sha1(norm(t).encode("utf-8")).hexdigest()[:16]
def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent":UA,"Accept":"*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()
def strip_html(s):
    s = re.sub(r"<[^>]+>"," ",s or ""); s = re.sub(r"&[a-z]+;"," ",s)
    return re.sub(r"\s+"," ",s).strip()
def parse_date(v):
    if not v: return None
    try: return parsedate_to_datetime(v.strip())
    except Exception: pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%SZ","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
        try: return datetime.strptime(v.replace("Z","+0000") if fmt.endswith("%z") else v, fmt)
        except Exception: continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v)
    return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)),tzinfo=timezone.utc) if m else None
def localname(t): return t.split("}")[-1].lower()
def parse_feed(data):
    out = []
    try: root = ET.fromstring(data)
    except Exception: return out
    for el in root.iter():
        if localname(el.tag) not in ("item","entry"): continue
        rec = {"title":"","url":"","date":None,"summary":""}
        for ch in el:
            n = localname(ch.tag); txt = (ch.text or "").strip()
            if n == "title": rec["title"] = strip_html(txt)
            elif n == "link": rec["url"] = ch.attrib.get("href") or txt or rec["url"]
            elif n in ("pubdate","published","updated","date"): rec["date"] = rec["date"] or parse_date(txt)
            elif n in ("description","summary","content"): rec["summary"] = strip_html(txt)[:400]
        if rec["title"] and rec["url"]: out.append(rec)
    return out
def parse_hn(data):
    out = []
    try: js = json.loads(data.decode("utf-8","ignore"))
    except Exception: return out
    for h in js.get("hits", []):
        ts = h.get("created_at_i")
        out.append({"title": h.get("title") or "",
                    "url": h.get("url") or ("https://news.ycombinator.com/item?id="+str(h.get("objectID"))),
                    "date": datetime.fromtimestamp(ts,tz=timezone.utc) if ts else None,
                    "summary": "HN %s points, %s comments"%(h.get("points"),h.get("num_comments"))})
    return out
def load_seen():
    try:
        with open(STATE) as f: return json.load(f)
    except Exception: return {"ids":{}}

def main():
    seen = load_seen(); seen_ids = set(seen.get("ids",{}).keys())
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_H)
    results, stats = [], []
    def grab(row):
        name,url,kind,weight = row
        try:
            data = fetch(url, timeout=8)
            items = parse_hn(data) if kind=="hn" else parse_feed(data)
            return (row, items, None)
        except Exception as e:
            return (row, None, str(e)[:90])
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        fetched = list(ex.map(grab, S))
    for row, items, err in fetched:
        name,url,kind,weight = row
        if err is not None:
            stats.append({"source":name,"ok":False,"err":err,"got":0}); continue
        items = items or []
        kept = 0
        for it in items:
            title = it["title"]; low = title.lower()
            if len(title) < 20 or any(k in low for k in DROP_KW): continue
            d = it.get("date")
            if d is not None:
                if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
                if d < cutoff: continue
            if not any(k in low for k in IDEA_KW): continue
            iid = hid(title)
            if iid in seen_ids: continue
            blob = low+" "+(it.get("summary") or "").lower()
            money = any(k in blob for k in MONEY_KW)
            results.append({"id":iid,"source":name,"title":title,"url":it["url"],
                            "date": d.isoformat() if d else None,
                            "summary": it.get("summary","")[:300],
                            "research": name in RESEARCH,
                            "score": weight+(3 if money else 0), "money": money})
            kept += 1
        stats.append({"source":name,"ok":True,"got":len(items),"kept":kept})
    results.sort(key=lambda x:(-x["score"], x["date"] or ""))
    with open(OUT,"w") as f:
        json.dump({"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(results[:200]),
                   "items":results[:200],"stats":stats}, f, ensure_ascii=False, indent=1)
    ok=[s for s in stats if s.get("ok")]
    print("sources ok=%d/%d candidates=%d"%(len(ok),len(stats),len(results[:200])))
    for s in stats:
        print("  %-20s %s got=%s kept=%s %s"%(s["source"],"OK " if s.get("ok") else "ERR",s.get("got"),s.get("kept",0),s.get("err","")))
if __name__=="__main__": main()
