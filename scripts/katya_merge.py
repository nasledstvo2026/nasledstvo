#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
katya_merge.py — накопление базы жалоб по наследству в банках (FR-17).

Единственный разрешённый способ записи в katya-data.json.
Гарантии:
  * append-only: старые записи никогда не удаляются;
  * дедуп по нормализованному URL;
  * бэкап базы перед каждой записью;
  * атомарная запись (tmp + os.replace);
  * guard: если после merge записей стало меньше — запись отменяется (exit 3);
  * если katya-data.json битый JSON — запись отменяется (exit 4);
  * сводка за окно N дней пишется в ОТДЕЛЬНЫЙ файл katya-summary-7d.json;
  * seen-лист katya-extra-seen.json дополняется URL из raw/verified/base.

Использование:
  python3 katya_merge.py                     # обычный прогон (verify → база → сводка → seen)
  python3 katya_merge.py --dry-run           # ничего не пишет, печатает отчёт
  python3 katya_merge.py --restore           # разово: склеить базу из бэкапов + обычный прогон
  python3 katya_merge.py --data-dir DIR      # альтернативный каталог (тесты)
  python3 katya_merge.py --window-days 7
Отчёт — JSON в stdout.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_DATA_DIR = "/home/user1/.openclaw/agents/shared"
BASE_NAME = "katya-data.json"
VERIFIED_NAME = "katya-verified.json"
RAW_NAME = "katya-raw.json"
SEEN_NAME = "katya-extra-seen.json"
SUMMARY_NAME = "katya-summary-7d.json"
BACKUP_KEEP = 30
MSK = timezone(timedelta(hours=3))

CORE_FIELDS = ("date", "bank", "title", "description", "url", "source", "verification", "addedAt", "bankRaw")
ACCEPTED = ("verified", "needs_review")

# Канонизация названий банков: разные написания одного банка ломали топ-10 в статистике
BANK_CANON = {
    "сбер": "Сбербанк", "сбербанк": "Сбербанк", "пао сбербанк": "Сбербанк", "сбербанк": "Сбербанк",
    "втб": "ВТБ", "пао втб": "ВТБ", "банк втб": "ВТБ",
    "т-банк": "Т-Банк", "тбанк": "Т-Банк", "тинькофф": "Т-Банк", "тинькофф банк": "Т-Банк",
    "альфа-банк": "Альфа-Банк", "альфа банк": "Альфа-Банк", "альфабанк": "Альфа-Банк", "альфа": "Альфа-Банк",
    "псб": "ПСБ", "промсвязьбанк": "ПСБ",
    "рсхб": "РСХБ", "россельхозбанк": "РСХБ",
    "ozon банк": "Ozon Банк", "озон банк": "Ozon Банк", "ozon bank": "Ozon Банк",
    "бспб": "Банк Санкт-Петербург", "банк санкт-петербург": "Банк Санкт-Петербург",
    "райффайзенбанк": "Райффайзенбанк", "райффайзен": "Райффайзенбанк",
    "банк русский стандарт": "Русский Стандарт", "русский стандарт": "Русский Стандарт",
    "газпромбанк": "Газпромбанк", "совкомбанк": "Совкомбанк", "мтс банк": "МТС Банк",
    "яндекс банк": "Яндекс Банк", "почта банк": "Почта Банк", "почта-банк": "Почта Банк",
    "уралсиб": "Уралсиб", "банк уралсиб": "Уралсиб", "открытие": "Открытие",
    "ренессанс банк": "Ренессанс Банк", "ренессанс кредит": "Ренессанс Банк",
    "дальневосточный банк": "Дальневосточный Банк", "хоум кредит": "Хоум Банк", "хоум банк": "Хоум Банк",
    "драйв клик банк": "Драйв Клик Банк", "росбанк": "Росбанк", "мкб": "МКБ",
}
BANK_UNKNOWN_PREFIX = ("не указан", "неизвест", "нет данных", "н/д", "не определ", "не установлен", "без банка", "-")

SOURCE_CANON = {
    "2gis": "2gis.ru", "2гис": "2gis.ru", "банки.ру": "banki.ru", "banki": "banki.ru",
    "пикабу": "pikabu.ru", "pikabu": "pikabu.ru", "отзовик": "otzovik.com", "otzovik": "otzovik.com",
    "pravoved": "pravoved.ru", "9111": "9111.ru", "кп": "kp.ru",
}


def canon_source(value: str | None, url: str = "") -> str | None:
    """Нормализация источника до домена (2GIS/2ГИС → 2gis.ru и т.п.)."""
    s = (value or "").strip()
    if not s:
        host = urlsplit(url).netloc.lower()
        return host[4:] if host.startswith("www.") else (host or None)
    key = s.lower().strip().replace("www.", "")
    if key in SOURCE_CANON:
        return SOURCE_CANON[key]
    if "." in key and " " not in key:
        return key
    return s


def canon_bank(value):
    """Приводит название банка к каноническому виду; мусор/«не указан» → None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    low = s.lower()
    if any(low.startswith(p) for p in BANK_UNKNOWN_PREFIX):
        return None
    # несколько банков в одной строке → берём первый как основной
    primary = re.split(r"\s*[/,;]\s*|\s+и\s+", s)[0].strip()
    primary = re.sub(r"\s*\([^)]*\)\s*", " ", primary).strip()
    if not primary:
        primary = s
    key = re.sub(r"\s+", " ", primary.lower()).strip(" .\"'«»")
    key = re.sub(r"^(пао|ао|оао|зао|ооо|банк)\s+", "", key).strip()
    if any(key.startswith(p) for p in BANK_UNKNOWN_PREFIX):
        return None
    return BANK_CANON.get(key, primary)

# ── утилиты ───────────────────────────────────────────────────────────────────


def now_iso() -> str:
    return datetime.now(MSK).replace(microsecond=0).isoformat()


def norm_url(u: str | None) -> str:
    """Нормализация URL для дедупа: https, без www, без хвостового /, без utm_*, без #."""
    if not u or not isinstance(u, str):
        return ""
    u = u.strip()
    if not u:
        return ""
    if "//" not in u:
        u = "https://" + u
    p = urlsplit(u)
    host = (p.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+$", "", p.path or "")
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    q.sort()
    return urlunsplit(("https", host, path, urlencode(q), ""))


def load_json(path: str, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        txt = fh.read().strip()
    if not txt:
        return default
    return json.loads(txt)


def atomic_write_json(path: str, data) -> None:
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    try:
        mode = os.stat(path).st_mode & 0o777
    except OSError:
        mode = 0o664
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".katya-tmp-", suffix=".json")
    try:
        os.chmod(tmp, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def backup_file(path: str, keep: int = BACKUP_KEEP) -> str | None:
    if not os.path.exists(path):
        return None
    stamp = datetime.now(MSK).strftime("%Y%m%d-%H%M%S")
    dst = f"{path}.bak-{stamp}"
    n = 1
    while os.path.exists(dst):
        n += 1
        dst = f"{path}.bak-{stamp}-{n}"
    with open(path, "rb") as src, open(dst, "wb") as out:
        out.write(src.read())
    baks = sorted(glob.glob(f"{path}.bak-*"))
    for old in baks[:-keep] if len(baks) > keep else []:
        try:
            os.unlink(old)
        except OSError:
            pass
    return dst


# ── нормализация записей ──────────────────────────────────────────────────────


def to_record(src: dict, default_verification: str | None = None) -> dict | None:
    """Приводит запись любого источника (raw/verified/старая база) к формату базы."""
    if not isinstance(src, dict):
        return None
    url = (src.get("url") or "").strip()
    if not url:
        return None
    desc = src.get("description") or src.get("complaint") or src.get("summary") or ""
    ver = src.get("verification") or default_verification
    bank_raw = src.get("bank")
    bank = canon_bank(bank_raw)
    rec = {
        "date": src.get("date") or None,
        "bank": bank,
        "title": (src.get("title") or "").strip() or None,
        "description": (desc or "").strip() or None,
        "url": url,
        "source": canon_source(src.get("source"), url),
        "verification": ver,
        "addedAt": src.get("addedAt") or None,
    }
    if bank_raw and str(bank_raw).strip() != (bank or ""):
        rec["bankRaw"] = str(bank_raw).strip()
    extra = {k: v for k, v in src.items() if k not in CORE_FIELDS and k not in ("complaint", "summary")}
    if "reject_reason" in extra and not extra["reject_reason"]:
        extra.pop("reject_reason")
    rec.update(extra)
    return rec


def is_accepted(rec: dict) -> bool:
    v = rec.get("verification")
    return v is None or v in ACCEPTED


def merge_into(base: list, incoming: list, index: dict, added_at: str | None, stats: dict) -> None:
    """Дописывает incoming в base с дедупом по норм. URL и обогащением пустых полей."""
    for src in incoming:
        rec = to_record(src)
        if rec is None:
            stats["skipped_invalid"] += 1
            continue
        if not is_accepted(rec):
            stats["skipped_rejected"] += 1
            continue
        key = norm_url(rec["url"])
        if key in index:
            cur = index[key]
            enriched = False
            for f in ("date", "bank", "title", "description", "source"):
                if not cur.get(f) and rec.get(f):
                    cur[f] = rec[f]
                    enriched = True
            if cur.get("verification") == "needs_review" and rec.get("verification") == "verified":
                cur["verification"] = "verified"
                enriched = True
            stats["enriched" if enriched else "duplicates"] += 1
            continue
        if rec.get("addedAt") is None:
            rec["addedAt"] = added_at
        base.append(rec)
        index[key] = rec
        stats["added"] += 1
        stats["added_urls"].append(rec["url"])


def sort_base(base: list) -> list:
    """Свежие сверху; записи без даты — в конец (порядок внутри групп стабилен)."""
    with_date = [r for r in base if r.get("date")]
    without_date = [r for r in base if not r.get("date")]
    with_date.sort(key=lambda r: str(r["date"])[:10], reverse=True)
    return with_date + without_date


# ── статистика ────────────────────────────────────────────────────────────────


def build_summary(base: list, window_days: int, generated_at: str) -> dict:
    today = datetime.now(MSK).date()
    date_from = today - timedelta(days=window_days)
    win = [r for r in base if r.get("date") and str(r["date"])[:10] >= date_from.isoformat()]

    def counts(records, field):
        out: dict[str, int] = {}
        for r in records:
            k = r.get(field) or "не определён"
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    by_month: dict[str, int] = {}
    for r in base:
        if r.get("date"):
            m = str(r["date"])[:7]
            by_month[m] = by_month.get(m, 0) + 1
    dates = sorted(str(r["date"])[:10] for r in base if r.get("date"))
    return {
        "generatedAt": generated_at,
        "period": f"{window_days}days",
        "dateFrom": date_from.isoformat(),
        "dateTo": today.isoformat(),
        "window": {
            "total": len(win),
            "totalVerified": sum(1 for r in win if r.get("verification") in (None, "verified")),
            "totalNeedsReview": sum(1 for r in win if r.get("verification") == "needs_review"),
            "byBank": counts(win, "bank"),
            "bySource": counts(win, "source"),
            "byDate": dict(sorted(counts(win, "date").items())),
            "entries": win,
        },
        "base": {
            "total": len(base),
            "totalVerified": sum(1 for r in base if r.get("verification") in (None, "verified")),
            "totalNeedsReview": sum(1 for r in base if r.get("verification") == "needs_review"),
            "firstDate": dates[0] if dates else None,
            "lastDate": dates[-1] if dates else None,
            "withoutDate": sum(1 for r in base if not r.get("date")),
            "byBank": counts(base, "bank"),
            "bySource": counts(base, "source"),
            "byMonth": dict(sorted(by_month.items())),
        },
    }


# ── восстановление из бэкапов ─────────────────────────────────────────────────

RESTORE_SOURCES = [
    ("{data}/katya-data.json.backup.20260725-161524", "verified"),
    ("{data}/katya-data.json.backup.20260725-161423", "verified"),
    ("{data}/katya-data.json.backup.20260725-073825", "verified"),
    ("{data}/katya-data.json.backup.20260714-214118", "verified"),
    ("/home/user1/.openclaw/workspace/katya-data-restored-20260714_211208.json", "verified"),
    ("/home/user1/.openclaw/workspace/memory/katya-data.json", "verified"),
    ("{data}/katya-verified.json.backup.20260813-110203", None),
    ("{data}/katya-verified.json.backup.20260824-075911", None),
    ("{data}/katya-verified.json.backup.20260824-080834", None),
    ("{data}/katya-verified.json.bak-20260825-0801", None),
    ("{data}/katya-data.json.backup.20260813-110203", None),
    ("{data}/katya-data.json.backup.20260824-075911", None),
    ("{data}/katya-data.json.backup.20260824-080834", None),
    ("{data}/katya-data.json.bak-20260825-0801", None),
]


def records_from_any(payload, default_verification: str | None) -> list:
    """Достаёт список записей из list-базы или dict-агрегата {entries: [...]}."""
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("entries") or []
    else:
        return []
    out = []
    for r in rows:
        rec = to_record(r, default_verification)
        if rec:
            out.append(rec)
    return out


# ── основной сценарий ─────────────────────────────────────────────────────────


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Накопление базы жалоб katya-data.json")
    ap.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    ap.add_argument("--base")
    ap.add_argument("--verified")
    ap.add_argument("--raw")
    ap.add_argument("--seen")
    ap.add_argument("--summary")
    ap.add_argument("--window-days", type=int, default=7)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restore", action="store_true", help="разово склеить базу из бэкапов")
    ap.add_argument("--no-seen", action="store_true", help="не обновлять seen-лист")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)

    data = a.data_dir.rstrip("/")
    base_path = a.base or f"{data}/{BASE_NAME}"
    verified_path = a.verified or f"{data}/{VERIFIED_NAME}"
    raw_path = a.raw or f"{data}/{RAW_NAME}"
    seen_path = a.seen or f"{data}/{SEEN_NAME}"
    summary_path = a.summary or f"{data}/{SUMMARY_NAME}"
    generated_at = now_iso()

    report = {
        "ok": False,
        "generatedAt": generated_at,
        "dryRun": bool(a.dry_run),
        "restore": bool(a.restore),
        "basePath": base_path,
        "baseBefore": 0,
        "baseAfter": 0,
        "added": 0,
        "duplicates": 0,
        "enriched": 0,
        "skipped_rejected": 0,
        "skipped_invalid": 0,
        "added_urls": [],
        "backup": None,
        "seenBefore": 0,
        "seenAfter": 0,
        "warnings": [],
        "restoreSources": [],
    }

    # 1. читаем базу
    try:
        raw_base = load_json(base_path, default=[])
    except json.JSONDecodeError as e:
        print(json.dumps({**report, "error": f"битый JSON в базе: {e}"}, ensure_ascii=False, indent=2))
        return 4
    if isinstance(raw_base, dict):
        report["warnings"].append("база была в формате dict-агрегата — конвертирую в накопительный список")
        base = records_from_any(raw_base, "verified")
    elif isinstance(raw_base, list):
        base = [r for r in (to_record(x, "verified") for x in raw_base) if r]
        if len(base) != len(raw_base):
            report["warnings"].append(f"в базе {len(raw_base) - len(base)} записей без url — пропущены")
    else:
        print(json.dumps({**report, "error": "неожиданный тип базы"}, ensure_ascii=False, indent=2))
        return 4
    report["baseBefore"] = len(base)

    index: dict[str, dict] = {}
    dupes_in_base = 0
    deduped: list = []
    for r in base:
        k = norm_url(r["url"])
        if k in index:
            dupes_in_base += 1
            continue
        index[k] = r
        deduped.append(r)
    base = deduped
    if dupes_in_base:
        report["warnings"].append(f"в исходной базе было {dupes_in_base} дублей по URL — схлопнуты")

    stats = {"added": 0, "duplicates": 0, "enriched": 0, "skipped_rejected": 0, "skipped_invalid": 0, "added_urls": []}

    # 2. restore-режим: подмешиваем бэкапы
    if a.restore:
        for tpl, defver in RESTORE_SOURCES:
            path = tpl.format(data=data)
            if not os.path.exists(path):
                report["warnings"].append(f"нет файла для restore: {path}")
                continue
            try:
                payload = load_json(path)
            except json.JSONDecodeError as e:
                report["warnings"].append(f"битый JSON, пропущен: {path} ({e})")
                continue
            recs = records_from_any(payload, defver)
            before = stats["added"]
            merge_into(base, recs, index, None, stats)
            report["restoreSources"].append({"file": os.path.basename(path), "records": len(recs), "added": stats["added"] - before})

    # 3. штатный merge: verified.json
    try:
        verified = load_json(verified_path, default=[]) or []
    except json.JSONDecodeError as e:
        verified = []
        report["warnings"].append(f"битый JSON в {os.path.basename(verified_path)} ({e}) — merge из него пропущен")
    if isinstance(verified, dict):
        verified = verified.get("entries") or []
    if not isinstance(verified, list):
        verified = []
        report["warnings"].append("verified.json не список — merge пропущен")
    merge_into(base, verified, index, generated_at, stats)

    for k in ("added", "duplicates", "enriched", "skipped_rejected", "skipped_invalid", "added_urls"):
        report[k] = stats[k]

    base = sort_base(base)
    report["baseAfter"] = len(base)

    # 4. guard: база не должна уменьшаться
    if report["baseAfter"] < report["baseBefore"]:
        print(json.dumps({**report, "error": "после merge записей стало меньше — запись отменена"}, ensure_ascii=False, indent=2))
        return 3

    summary = build_summary(base, a.window_days, generated_at)
    report["window"] = {k: summary["window"][k] for k in ("total", "totalVerified", "totalNeedsReview", "byBank")}
    report["baseStats"] = {k: summary["base"][k] for k in ("total", "firstDate", "lastDate", "withoutDate")}

    # 5. запись
    if not a.dry_run:
        report["backup"] = backup_file(base_path)
        atomic_write_json(base_path, base)
        atomic_write_json(summary_path, summary)

        if not a.no_seen:
            try:
                seen = load_json(seen_path, default={"urls": [], "updated": None}) or {"urls": [], "updated": None}
            except json.JSONDecodeError:
                seen = {"urls": [], "updated": None}
                report["warnings"].append("битый seen-лист — пересоздан")
            if isinstance(seen, list):
                seen = {"urls": seen, "updated": None}
            urls = [u for u in (seen.get("urls") or []) if isinstance(u, str) and u.strip()]
            report["seenBefore"] = len(urls)
            seen_keys = {norm_url(u) for u in urls}
            pool = [r.get("url") for r in base]
            for src_path in (raw_path, verified_path):
                try:
                    payload = load_json(src_path, default=[]) or []
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    payload = payload.get("entries") or []
                if isinstance(payload, list):
                    pool += [r.get("url") for r in payload if isinstance(r, dict)]
            for u in pool:
                k = norm_url(u)
                if k and k not in seen_keys:
                    seen_keys.add(k)
                    urls.append(u)
            seen = {"urls": urls, "updated": generated_at, "count": len(urls)}
            atomic_write_json(seen_path, seen)
            report["seenAfter"] = len(urls)

    report["ok"] = True
    if not a.quiet:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
