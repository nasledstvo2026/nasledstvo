#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_katya_merge.py — тест-кейсы для katya_merge.py (без LLM, без сети).
Запуск: python3 /home/user1/.openclaw/workspace/scripts/test_katya_merge.py
Каждый кейс работает в собственном временном каталоге, реальные данные не трогаются.
"""

import glob
import io
import json
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import katya_merge as km  # noqa: E402

RESULTS = []
TODAY = date.today()


def d(offset):
    return (TODAY - timedelta(days=offset)).isoformat()


def run(args):
    """Запускает merge, возвращает (rc, report_dict)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = km.main(args)
    out = buf.getvalue().strip()
    rep = json.loads(out) if out.startswith("{") else {}
    return rc, rep


def write(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        if isinstance(data, str):
            fh.write(data)
        else:
            json.dump(data, fh, ensure_ascii=False, indent=2)


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def case(name, fn):
    tmp = tempfile.mkdtemp(prefix="katya-test-")
    try:
        fn(tmp)
        RESULTS.append((name, True, ""))
        print(f"✅ {name}")
    except AssertionError as e:
        RESULTS.append((name, False, str(e)))
        print(f"❌ {name}: {e}")
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"💥 {name}: {type(e).__name__}: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def rec(url, dt=None, bank=None, ver="verified", title="t", desc="d", source="banki.ru"):
    return {"url": url, "date": dt, "bank": bank, "title": title, "complaint": desc,
            "source": source, "verification": ver, "reject_reason": None}


# ── TC-01: пустая/отсутствующая база → создаётся накопительный список ─────────
def tc01(tmp):
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/1", d(1), "Сбербанк")])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0, f"rc={rc}"
    base = load(f"{tmp}/katya-data.json")
    assert isinstance(base, list), "база должна быть списком"
    assert len(base) == 1 and base[0]["url"] == "https://a.ru/1", base
    assert base[0]["description"] == "d", "complaint → description не смапился"
    assert rep["added"] == 1 and rep["baseBefore"] == 0 and rep["baseAfter"] == 1, rep


# ── TC-02: дедуп по URL (в т.ч. www / trailing slash / utm) ───────────────────
def tc02(tmp):
    write(f"{tmp}/katya-data.json", [{"url": "https://www.a.ru/1/", "date": d(3), "title": "old",
                                     "description": "x", "source": "a.ru", "bank": "Сбербанк"}])
    write(f"{tmp}/katya-verified.json", [
        rec("https://a.ru/1?utm_source=tg", d(1), "Сбербанк"),
        rec("http://www.a.ru/1", d(1), "Сбербанк"),
        rec("https://a.ru/2", d(1), "ВТБ"),
    ])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0
    base = load(f"{tmp}/katya-data.json")
    assert len(base) == 2, f"ожидалось 2 записи, получено {len(base)}: {[r['url'] for r in base]}"
    assert rep["added"] == 1, rep
    assert rep["duplicates"] + rep["enriched"] == 2, rep


# ── TC-03: старые записи не теряются (append-only) ───────────────────────────
def tc03(tmp):
    old = [{"url": f"https://a.ru/old{i}", "date": "2025-01-%02d" % (i + 1), "title": f"o{i}",
            "description": "x", "source": "a.ru", "bank": "Сбербанк"} for i in range(82)]
    write(f"{tmp}/katya-data.json", old)
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/new1", d(1)), rec("https://a.ru/new2", d(2))])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0
    base = load(f"{tmp}/katya-data.json")
    assert len(base) == 84, f"было 82 + 2 новых, получено {len(base)}"
    urls = {r["url"] for r in base}
    assert all(o["url"] in urls for o in old), "часть старых записей исчезла"


# ── TC-04: бэкап создаётся перед записью и совпадает с прежним содержимым ────
def tc04(tmp):
    old = [{"url": "https://a.ru/1", "date": d(9), "title": "o", "description": "x", "source": "a.ru", "bank": None}]
    write(f"{tmp}/katya-data.json", old)
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/2", d(1))])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0
    baks = glob.glob(f"{tmp}/katya-data.json.bak-*")
    assert len(baks) == 1, f"бэкапов: {len(baks)}"
    assert rep["backup"] and os.path.basename(rep["backup"]) == os.path.basename(baks[0]), rep
    assert load(baks[0])[0]["url"] == "https://a.ru/1", "бэкап не содержит прежних данных"


# ── TC-05: идемпотентность (повторный прогон не добавляет записей) ───────────
def tc05(tmp):
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/1", d(1)), rec("https://a.ru/2", d(2))])
    run(["--data-dir", tmp])
    first = load(f"{tmp}/katya-data.json")
    rc, rep = run(["--data-dir", tmp])
    second = load(f"{tmp}/katya-data.json")
    assert rc == 0 and rep["added"] == 0, rep
    assert len(first) == len(second) == 2, (len(first), len(second))
    assert [r["url"] for r in first] == [r["url"] for r in second], "порядок записей нестабилен"


# ── TC-06: сводка за 7 дней — отдельный файл, окно и byBank корректны ────────
def tc06(tmp):
    write(f"{tmp}/katya-verified.json", [
        rec("https://a.ru/in1", d(1), "Сбербанк"),
        rec("https://a.ru/in2", d(6), "Сбербанк"),
        rec("https://a.ru/in3", d(3), "ВТБ", ver="needs_review"),
        rec("https://a.ru/out1", d(30), "Альфа-Банк"),
        rec("https://a.ru/out2", None, None),
    ])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0
    s = load(f"{tmp}/katya-summary-7d.json")
    base = load(f"{tmp}/katya-data.json")
    assert len(base) == 5, f"в базе должны быть все 5, а не {len(base)}"
    assert s["window"]["total"] == 3, f"в окне 7 дней ожидалось 3, получено {s['window']['total']}"
    assert s["window"]["totalVerified"] == 2 and s["window"]["totalNeedsReview"] == 1, s["window"]
    assert s["window"]["byBank"]["Сбербанк"] == 2, s["window"]["byBank"]
    assert s["base"]["total"] == 5 and s["base"]["withoutDate"] == 1, s["base"]
    assert s["base"]["byBank"]["Альфа-Банк"] == 1, s["base"]["byBank"]
    assert s["base"]["byMonth"], "byMonth пуст"


# ── TC-07: seen-лист дополняется (raw + verified + база), без дублей ────────
def tc07(tmp):
    write(f"{tmp}/katya-extra-seen.json", {"urls": ["https://a.ru/old"], "updated": "2026-08-20T07:49:00+03:00"})
    write(f"{tmp}/katya-raw.json", [{"url": "https://a.ru/raw1", "title": "r"}, {"url": "https://www.a.ru/old/"}])
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/v1", d(1)), rec("https://a.ru/rej", d(1), ver="rejected")])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0
    seen = load(f"{tmp}/katya-extra-seen.json")
    urls = set(seen["urls"])
    assert "https://a.ru/raw1" in urls, "raw-URL не попал в seen"
    assert "https://a.ru/v1" in urls, "verified-URL не попал в seen"
    assert "https://a.ru/rej" in urls, "rejected должен попадать в seen (чтобы не искать снова)"
    assert len(seen["urls"]) == 4, f"дубль old не схлопнулся: {seen['urls']}"
    assert seen["updated"] != "2026-08-20T07:49:00+03:00", "updated не обновился"
    assert rep["seenBefore"] == 1 and rep["seenAfter"] == 4, rep


# ── TC-08: rejected не попадают в базу ──────────────────────────────────────
def tc08(tmp):
    write(f"{tmp}/katya-verified.json", [
        rec("https://a.ru/1", d(1)),
        rec("https://a.ru/2", d(1), ver="rejected"),
        rec("https://a.ru/3", d(1), ver="needs_review"),
    ])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0
    base = load(f"{tmp}/katya-data.json")
    assert len(base) == 2, [r["url"] for r in base]
    assert rep["skipped_rejected"] == 1, rep


# ── TC-09: битый JSON базы → запись отменяется, файл не портится ─────────────
def tc09(tmp):
    write(f"{tmp}/katya-data.json", '{"broken": [')
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/1", d(1))])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 4, f"ожидался rc=4, получено {rc}"
    with open(f"{tmp}/katya-data.json", encoding="utf-8") as fh:
        assert fh.read() == '{"broken": [', "битый файл был перезаписан"
    assert not glob.glob(f"{tmp}/katya-data.json.bak-*"), "не должно быть бэкапа при отказе"


# ── TC-10: dict-агрегат (текущий сломанный формат) конвертируется в список ───
def tc10(tmp):
    write(f"{tmp}/katya-data.json", {
        "generatedAt": "2026-08-27T07:55:00+03:00", "period": "7days", "totalVerified": 2,
        "byBank": {"Сбербанк": 1},
        "entries": [{"date": d(6), "bank": "Сбербанк", "title": "a", "description": "x",
                     "url": "https://a.ru/agg1", "source": "banki.ru"}],
    })
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/new", d(1))])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0
    base = load(f"{tmp}/katya-data.json")
    assert isinstance(base, list) and len(base) == 2, base
    assert any("dict-агрегата" in w for w in rep["warnings"]), rep["warnings"]


# ── TC-11: --dry-run ничего не пишет ────────────────────────────────────────
def tc11(tmp):
    write(f"{tmp}/katya-data.json", [{"url": "https://a.ru/1", "date": d(5), "title": "o",
                                     "description": "x", "source": "a.ru", "bank": None}])
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/2", d(1))])
    before = open(f"{tmp}/katya-data.json", encoding="utf-8").read()
    rc, rep = run(["--data-dir", tmp, "--dry-run"])
    assert rc == 0 and rep["added"] == 1 and rep["dryRun"] is True, rep
    assert open(f"{tmp}/katya-data.json", encoding="utf-8").read() == before, "база изменена в dry-run"
    assert not os.path.exists(f"{tmp}/katya-summary-7d.json"), "сводка записана в dry-run"
    assert not glob.glob(f"{tmp}/katya-data.json.bak-*"), "бэкап создан в dry-run"


# ── TC-12: битый/пустой verified.json → база не пострадала ──────────────────
def tc12(tmp):
    old = [{"url": "https://a.ru/1", "date": d(4), "title": "o", "description": "x", "source": "a.ru", "bank": "ВТБ"}]
    write(f"{tmp}/katya-data.json", old)
    write(f"{tmp}/katya-verified.json", "{не json")
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0, rc
    base = load(f"{tmp}/katya-data.json")
    assert len(base) == 1 and base[0]["url"] == "https://a.ru/1", base
    assert any("битый JSON" in w for w in rep["warnings"]), rep["warnings"]
    # и пустой файл
    write(f"{tmp}/katya-verified.json", [])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0 and len(load(f"{tmp}/katya-data.json")) == 1, rep


# ── TC-13: записи без url отбрасываются, база не ломается ───────────────────
def tc13(tmp):
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/1", d(1)), {"title": "без url", "date": d(1)},
                                        {"url": "   "}, "мусор"])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0
    assert len(load(f"{tmp}/katya-data.json")) == 1, load(f"{tmp}/katya-data.json")
    assert rep["skipped_invalid"] == 3, rep


# ── TC-14: обогащение пустых полей существующей записи ─────────────────────
def tc14(tmp):
    write(f"{tmp}/katya-data.json", [{"url": "https://a.ru/1", "date": None, "title": None,
                                     "description": None, "source": None, "bank": None,
                                     "verification": "needs_review"}])
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/1", d(2), "Сбербанк", title="полный", desc="описание")])
    rc, rep = run(["--data-dir", tmp])
    assert rc == 0 and rep["enriched"] == 1 and rep["added"] == 0, rep
    r = load(f"{tmp}/katya-data.json")[0]
    assert r["bank"] == "Сбербанк" and r["date"] == d(2) and r["title"] == "полный", r
    assert r["verification"] == "verified", r


# ── TC-15: guard — база не уменьшается (эмуляция сбоя merge) ────────────────
def tc15(tmp):
    write(f"{tmp}/katya-data.json", [{"url": f"https://a.ru/{i}", "date": d(i + 1), "title": "o",
                                     "description": "x", "source": "a.ru", "bank": None} for i in range(5)])
    write(f"{tmp}/katya-verified.json", [])
    orig = km.merge_into

    def sabotage(base, incoming, index, added_at, stats):
        base.clear()  # имитируем баг, «съедающий» базу
    km.merge_into = sabotage
    try:
        rc, rep = run(["--data-dir", tmp])
    finally:
        km.merge_into = orig
    assert rc == 3, f"ожидался rc=3 (guard), получено {rc}"
    assert len(load(f"{tmp}/katya-data.json")) == 5, "guard не защитил базу"
    assert not glob.glob(f"{tmp}/katya-data.json.bak-*"), "бэкап создан при отказе"


# ── TC-16: ротация бэкапов (не более BACKUP_KEEP) ──────────────────────────
def tc16(tmp):
    write(f"{tmp}/katya-data.json", [{"url": "https://a.ru/1", "date": d(1), "title": "o",
                                     "description": "x", "source": "a.ru", "bank": None}])
    for i in range(35):
        write(f"{tmp}/katya-data.json.bak-2026080{i % 9 + 1}-0{i % 9}0000-{i:03d}", [])
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/2", d(1))])
    rc, _ = run(["--data-dir", tmp])
    assert rc == 0
    baks = glob.glob(f"{tmp}/katya-data.json.bak-*")
    assert len(baks) <= km.BACKUP_KEEP, f"бэкапов {len(baks)} > {km.BACKUP_KEEP}"


# ── TC-17: атомарность — временные файлы не остаются ───────────────────────
def tc17(tmp):
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/1", d(1))])
    rc, _ = run(["--data-dir", tmp])
    assert rc == 0
    assert not glob.glob(f"{tmp}/.katya-tmp-*"), "остались временные файлы"


# ── TC-18: --restore на копии реальных бэкапов ─────────────────────────────
def tc18(tmp):
    src = km.DEFAULT_DATA_DIR
    files = [os.path.basename(p) for p in glob.glob(f"{src}/katya-data.json.backup.*")
             + glob.glob(f"{src}/katya-verified.json.backup.*") + glob.glob(f"{src}/katya-*.json.bak-*")]
    for f in files:
        shutil.copy2(f"{src}/{f}", f"{tmp}/{f}")
    write(f"{tmp}/katya-verified.json", json.load(open(f"{src}/katya-verified.json", encoding="utf-8")))
    write(f"{tmp}/katya-data.json", json.load(open(f"{src}/katya-data.json", encoding="utf-8")))
    rc, rep = run(["--data-dir", tmp, "--restore"])
    assert rc == 0, rep
    base = load(f"{tmp}/katya-data.json")
    assert len(base) >= 100, f"ожидалось ≥100 записей после restore, получено {len(base)}"
    urls = [km.norm_url(r["url"]) for r in base]
    assert len(urls) == len(set(urls)), "в восстановленной базе есть дубли по URL"
    assert all(r.get("url") and r.get("title") for r in base), "есть записи без url/title"
    s = load(f"{tmp}/katya-summary-7d.json")
    assert s["base"]["firstDate"] <= "2025-02-01", f"нет старых записей: firstDate={s['base']['firstDate']}"
    assert len(s["base"]["byBank"]) >= 10, f"банков в базе: {len(s['base']['byBank'])}"
    # повторный restore идемпотентен
    rc2, rep2 = run(["--data-dir", tmp, "--restore"])
    assert rc2 == 0 and rep2["added"] == 0, f"повторный restore добавил {rep2['added']} записей"


# ── TC-19: права на файл сохраняются (664, а не 600 от mkstemp) ────────────
def tc19(tmp):
    p = f"{tmp}/katya-data.json"
    write(p, [{"url": "https://a.ru/1", "date": d(2), "title": "o", "description": "x",
               "source": "a.ru", "bank": None}])
    os.chmod(p, 0o664)
    write(f"{tmp}/katya-verified.json", [rec("https://a.ru/2", d(1))])
    rc, _ = run(["--data-dir", tmp])
    assert rc == 0
    mode = os.stat(p).st_mode & 0o777
    assert mode == 0o664, f"права изменились: {oct(mode)}"
    new_mode = os.stat(f"{tmp}/katya-summary-7d.json").st_mode & 0o777
    assert new_mode == 0o664, f"новый файл создан с правами {oct(new_mode)}"


# ── TC-20: канонизация названий банков ──────────────────────────────
def tc20(tmp):
    write(f"{tmp}/katya-verified.json", [
        rec("https://a.ru/1", d(1), "Сбер"),
        rec("https://a.ru/2", d(1), "Сбербанк"),
        rec("https://a.ru/3", d(1), "ПАО Сбербанк"),
        rec("https://a.ru/4", d(1), "Сбербанк (Драйв Клик Банк)"),
        rec("https://a.ru/5", d(1), "ВТБ / Почта Банк"),
        rec("https://a.ru/6", d(1), "тинькофф"),
        rec("https://a.ru/7", d(1), "не указан (новый кредитор по цессии)"),
        rec("https://a.ru/8", d(1), "Неизвестно"),
        rec("https://a.ru/9", d(1), "Альфа-банк"),
        rec("https://a.ru/10", d(1), "БСПБ (Банк Санкт-Петербург)"),
    ])
    rc, _ = run(["--data-dir", tmp])
    assert rc == 0
    s = load(f"{tmp}/katya-summary-7d.json")
    bb = s["base"]["byBank"]
    assert bb.get("Сбербанк") == 4, f"Сбер/Сбербанк/ПАО не склеились: {bb}"
    assert "Сбер" not in bb, bb
    assert bb.get("ВТБ") == 1 and bb.get("Т-Банк") == 1, bb
    assert bb.get("Альфа-Банк") == 1 and bb.get("Банк Санкт-Петербург") == 1, bb
    assert bb.get("не определён") == 2, f"«не указан»/«Неизвестно» должны стать null: {bb}"
    base = load(f"{tmp}/katya-data.json")
    raws = {r["url"]: r.get("bankRaw") for r in base}
    assert raws["https://a.ru/1"] == "Сбер", "оригинальное название потеряно (bankRaw)"
    assert raws["https://a.ru/2"] is None, "bankRaw не нужен, когда совпадает"


# ── TC-21: канонизация источников ───────────────────────────────
def tc21(tmp):
    write(f"{tmp}/katya-verified.json", [
        rec("https://2gis.ru/1", d(1), source="2GIS"),
        rec("https://2gis.ru/2", d(1), source="2ГИС"),
        rec("https://www.banki.ru/3", d(1), source="www.banki.ru"),
        rec("https://pikabu.ru/4", d(1), source=None),
    ])
    rc, _ = run(["--data-dir", tmp])
    assert rc == 0
    s = load(f"{tmp}/katya-summary-7d.json")["base"]["bySource"]
    assert s.get("2gis.ru") == 2, f"2GIS/2ГИС не склеились: {s}"
    assert s.get("banki.ru") == 1 and s.get("pikabu.ru") == 1, s


CASES = [
    ("TC-01 пустая база → накопительный список", tc01),
    ("TC-02 дедуп по URL (www/slash/utm)", tc02),
    ("TC-03 append-only: старые записи целы", tc03),
    ("TC-04 бэкап перед записью", tc04),
    ("TC-05 идемпотентность повторного прогона", tc05),
    ("TC-06 сводка 7 дней в отдельном файле", tc06),
    ("TC-07 seen-лист дополняется без дублей", tc07),
    ("TC-08 rejected не попадают в базу", tc08),
    ("TC-09 битый JSON базы → отказ, файл цел", tc09),
    ("TC-10 dict-агрегат → конвертация в список", tc10),
    ("TC-11 --dry-run ничего не пишет", tc11),
    ("TC-12 битый/пустой verified → база цела", tc12),
    ("TC-13 записи без url отбрасываются", tc13),
    ("TC-14 обогащение пустых полей", tc14),
    ("TC-15 guard: база не уменьшается", tc15),
    ("TC-16 ротация бэкапов", tc16),
    ("TC-17 атомарность записи", tc17),
    ("TC-18 --restore на копии реальных бэкапов", tc18),
    ("TC-19 права на файлы сохраняются (664)", tc19),
    ("TC-20 канонизация названий банков", tc20),
    ("TC-21 канонизация источников", tc21),
]

if __name__ == "__main__":
    print("=== Тесты katya_merge.py ===")
    for name, fn in CASES:
        case(name, fn)
    ok = sum(1 for _, p, _ in RESULTS if p)
    print(f"\nИтого: {ok}/{len(RESULTS)} passed")
    sys.exit(0 if ok == len(RESULTS) else 1)
