#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lena_collect.py — детерминированный сбор + фильтр новостей по наследству.

Читает реестр sources.json, собирает со ВСЕХ источников (rss/html/sitemap),
применяет whitelist → дедуп по seen → дата-фильтр (7 дней) → тематический фильтр.
Пишет /tmp/lena_raw_sources.txt и /tmp/lena_filtered.json.
LLM не используется.

Запуск: python3 scripts/lena_collect.py
"""
import json, re, ssl, sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

WORKSPACE = "/home/user1/.openclaw/workspace"
SOURCES_PATH = f"{WORKSPACE}/knowledge/lena/sources.json"
SEEN_PATH = "/home/user1/.openclaw/agents/shared/lena-news-seen.md"
RAW_OUT = "/tmp/lena_raw_sources.txt"
FILTERED_OUT = "/tmp/lena_filtered.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"
TIMEOUT = 25
DAYS = 7

# Тематические подстроки (точное вхождение, lowercase). Без «наслед» как стемы!
THEMES = (
    "наследств", "наследник", "наследодател", "наследован", "наследуем",
    "завещан", "завещател", "выморочн",
)
# Слаги rg.ru (транслитерация)
RG_SLUGS = (
    "nasledstv", "naslednik", "nasledodat", "nasledovan", "nasleduem",
    "zaveshchan", "zaveshchatel", "vymorochn",
)

# Спец-набор разделов для banki.ru (лента + жалобы + вопросы)
BANKI_SECTIONS = [
    "https://www.banki.ru/news/lenta/",
    "https://www.banki.ru/services/responses/",
    "https://www.banki.ru/services/questions-answers/",
]

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def log(msg):
    print(msg, file=sys.stderr)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as r:
        return r.read()


def fetch_text(url):
    """Скачать, декодировать (utf-8 → cp1251 fallback), вернуть строку."""
    data = fetch(url)
    for enc in ("utf-8", "cp1251", "latin-1"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", "replace")


def netloc(url):
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1).lower() if m else ""


def host_matches(url, domains):
    nl = netloc(url)
    for d in domains:
        if nl == d or nl.endswith("." + d):
            return d
    return None


# ---------- даты ----------

def parse_rfc822(s):
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except Exception:
        return None


def parse_iso(s):
    s = s.strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def parse_relative(s):
    s = s.lower()
    m = re.search(r"(\d+)\s*(час|минут|дней|день|минуты|часа|дня)", s)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit.startswith("час"):
            return datetime.now(timezone.utc) - timedelta(hours=n)
        if unit.startswith("минут"):
            return datetime.now(timezone.utc) - timedelta(minutes=n)
        if unit.startswith("дн"):
            return datetime.now(timezone.utc) - timedelta(days=n)
    return None


def normalize_date(s):
    if not s:
        return None
    return parse_rfc822(s) or parse_iso(s) or parse_relative(s)


def fmt_date(d):
    return d.astimezone(timezone.utc).strftime("%Y-%m-%d")


def find_date_in_text(s):
    """Извлечь дату из HTML-фрагмента: <time datetime>, YYYY-MM-DD, DD.MM.YYYY, относительная."""
    m = re.search(r'<time[^>]*datetime=["\']([^"\']+)["\']', s, re.I)
    if m:
        d = parse_iso(m.group(1))
        if d:
            return d
    m = re.search(r"(20\d{2})[-.](\d{2})[-.](\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        except Exception:
            pass
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(20\d{2}|\d{2})", s)
    if m:
        dd, mm = int(m.group(1)), int(m.group(2))
        yy = int(m.group(3))
        if yy < 100:
            yy += 2000
        try:
            return datetime(yy, mm, dd, tzinfo=timezone.utc)
        except Exception:
            pass
    return parse_relative(s)


def parse_ddmm_suffix(url):
    """Дата из URL-суффикса -DDMM (notariat.ru и аналогичные): -2608 → 26.08."""
    m = re.search(r"-(\d{2})(\d{2})(?:[/?#]|$)", url)
    if not m:
        return None
    dd, mm = int(m.group(1)), int(m.group(2))
    if not (1 <= dd <= 31 and 1 <= mm <= 12):
        return None
    year = datetime.now(timezone.utc).year
    d = datetime(year, mm, dd, tzinfo=timezone.utc)
    if d > datetime.now(timezone.utc):
        d = d.replace(year=year - 1)
    return d


# ---------- парсеры источников ----------

def parse_rss(text):
    """Возвращает список (title, url, date_str) из RSS/Atom."""
    out = []
    try:
        root = ET.fromstring(text)
    except Exception:
        return out
    for it in root.iter("item"):
        title = it.findtext("title") or ""
        link = it.findtext("link") or ""
        pub = it.findtext("pubDate") or ""
        if not title or not link:
            continue
        d = normalize_date(pub)
        out.append((title.strip(), link.strip(), fmt_date(d) if d else None))
    return out


def parse_rg_sitemap(entry):
    """Трёхуровневый sitemap rg.ru. Возвращает (title, url, date)."""
    out = []
    try:
        text = fetch_text(entry["url"])
    except Exception as e:
        log(f"  [rg] index fail: {e}")
        return out
    try:
        root = ET.fromstring(text)
    except Exception:
        root = None
    daily = []
    if root is not None:
        for loc in root.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            u = (loc.text or "").strip()
            if u:
                daily.append(u)
        if not daily:
            for loc in root.iter("loc"):
                daily.append((loc.text or "").strip())
    daily = [u for u in daily if u]
    if not daily:
        log("  [rg] нет daily-sitemap")
        return out
    daily = daily[-8:]
    for du in daily:
        try:
            dt = fetch_text(du)
            r = ET.fromstring(dt)
            for url in r.iter("url"):
                loc = url.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
                if loc is None:
                    loc = url.find("loc")
                loc = (loc.text or "") if loc is not None else ""
                slug = loc.lower()
                if not any(s in slug for s in RG_SLUGS):
                    continue
                lastmod = url.find("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")
                if lastmod is None:
                    lastmod = url.find("lastmod")
                lm = (lastmod.text or "") if lastmod is not None else ""
                title = re.sub(r"[-_]+", " ", loc.rstrip("/").split("/")[-1]).strip()
                d = normalize_date(lm)
                out.append((title, loc, fmt_date(d) if d else None))
        except Exception as e:
            log(f"  [rg] daily fail {du}: {e}")
    return out


def extract_links_dated(html, base):
    """Возвращает (title, url, date) — дату ищет в контексте ссылки (120 симв. вокруг)."""
    out = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.S | re.I):
        href, inner = m.group(1), m.group(2)
        text = re.sub(r"<[^>]+>", "", inner)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 18:
            continue
        if href.startswith("http"):
            url = href
        elif href.startswith("/"):
            url = base + href
        else:
            continue
        s = max(0, m.start() - 120)
        e = min(len(html), m.end() + 120)
        d = find_date_in_text(html[s:e])
        out.append((text, url, d))
    return out


def parse_html_source(entry):
    """HTML-источник. Возвращает (title, url, date)."""
    out = []
    urls = [entry["url"]]
    if netloc(entry["url"]) == "banki.ru":
        urls = BANKI_SECTIONS
    for u in urls:
        try:
            text = fetch_text(u)
        except Exception as e:
            log(f"  [html] {u} fail: {e}")
            continue
        base = re.match(r"(https?://[^/]+)", u).group(1)
        # consultant.ru: embedded JSON с publishedAt
        if "consultant.ru" in u:
            for m in re.finditer(r'\{[^{}]*?"(?:title|name)"[^{}]*?\}', text):
                try:
                    j = json.loads(m.group(0))
                except Exception:
                    continue
                t = j.get("title") or j.get("name") or ""
                l = j.get("link") or j.get("url") or ""
                pd = j.get("publishedAt") or j.get("date") or ""
                if t and l:
                    if not l.startswith("http"):
                        l = "https://www.consultant.ru" + (l if l.startswith("/") else "/" + l)
                    d = normalize_date(pd)
                    out.append((t.strip(), l, fmt_date(d) if d else None))
            continue
        # общий случай: ссылки + дата из URL или контекста
        seen_urls = set()
        for title, url, dctx in extract_links_dated(text, base):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            d = None
            dm = re.search(r"/(20\d{2})/(\d{2})/(\d{2})/", url)
            if dm:
                try:
                    d = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)), tzinfo=timezone.utc)
                except Exception:
                    d = None
            if d is None:
                d = parse_ddmm_suffix(url)
            if d is None:
                d = dctx
            out.append((title, url, fmt_date(d) if d else None))
    return out


# ---------- основной сбор ----------

def collect():
    with open(SOURCES_PATH, encoding="utf-8") as f:
        sources = json.load(f)
    domains = list(sources.keys())
    raw = []

    for dom, cfg in sources.items():
        typ = cfg.get("type", "html")
        url = cfg.get("url", "")
        log(f"[{typ}] {dom}")
        try:
            if typ == "rss":
                for title, u, d in parse_rss(fetch_text(url)):
                    raw.append({"title": title, "url": u, "date": d, "source": dom})
            elif typ == "sitemap":
                for title, u, d in parse_rg_sitemap(cfg):
                    raw.append({"title": title, "url": u, "date": d, "source": dom})
            else:
                for title, u, d in parse_html_source(cfg):
                    raw.append({"title": title, "url": u, "date": d, "source": dom})
        except Exception as e:
            log(f"  [!] {dom}: {e}")

    dedup = {}
    for r in raw:
        dedup[r["url"]] = r
    raw = list(dedup.values())

    with open(RAW_OUT, "w", encoding="utf-8") as f:
        for r in raw:
            f.write(f"{r['url']} | {r['title']} | {r['date'] or ''}\n")

    return raw, domains


def filter_stage(raw, domains):
    seen_urls = set()
    try:
        with open(SEEN_PATH, encoding="utf-8") as f:
            for line in f:
                for token in line.split("|"):
                    token = token.strip()
                    if token.startswith("http"):
                        seen_urls.add(token)
    except FileNotFoundError:
        pass

    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=DAYS)

    filtered = []
    for r in raw:
        if not host_matches(r["url"], domains):
            continue
        if r["url"] in seen_urls:
            continue
        if not r["title"] or len(r["title"]) < 3:
            continue
        if not r["date"]:
            continue
        try:
            d = parse_iso(r["date"])
            if d is None or d < cutoff:
                continue
        except Exception:
            continue
        low = r["title"].lower()
        if not any(t in low for t in THEMES):
            continue
        filtered.append({"title": r["title"], "url": r["url"], "date": r["date"], "source": r["source"]})

    filtered.sort(key=lambda x: x["date"], reverse=True)

    with open(FILTERED_OUT, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)
    return filtered


def main():
    raw, domains = collect()
    filtered = filter_stage(raw, domains)
    print("=== COLLECT DONE ===")
    print(f"raw={len(raw)}")
    print(f"whitelist_domains={len(domains)}")
    print(f"filtered={len(filtered)}")
    print(f"raw_file={RAW_OUT}")
    print(f"filtered_file={FILTERED_OUT}")
    per = {}
    for r in raw:
        per[r["source"]] = per.get(r["source"], 0) + 1
    print("--- raw per source ---")
    for dom in sorted(per):
        print(f"  {dom}={per[dom]}")
    for it in filtered[:20]:
        t = it["title"][:70].encode("ascii", "backslashreplace").decode()
        print(f"  [{it['date']}] {t} | {it['url'][:60]}")


if __name__ == "__main__":
    main()
