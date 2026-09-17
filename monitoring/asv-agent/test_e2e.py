#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end тест check.py: полный путь «данные → детекция → вывод».

Мокает fetch() (без сети), проверяет:
1. свежий конкурс -> KONKURS;
2. свежий страховой случай -> STRAKH;
3. шум («торги», «собрание кредиторов») -> не алертится;
4. старая запись (>30 дней) -> не алертится;
5. дедуп: повторный запуск с теми же данными -> CLEAN.
"""
import io
import os
import sys
import importlib.util
import tempfile
import contextlib
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("check", os.path.join(HERE, "check.py"))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

def d(days_ago=0):
    return (datetime.now() - timedelta(days=days_ago)).strftime("%d.%m.%Y")

def item(id_, title, date):
    return {"id": id_, "title": title, "date": date, "url": f"/news/{id_}/"}

def fake_fetch(q):
    low = q.lower()
    if "банков-агентов" in low:
        items = [
            item(900001, "Конкурс по&nbsp;отбору банков-агентов для&nbsp;выплаты страхового возмещения вкладчикам (ТЕСТ)", d(0)),
            item(900002, "Конкурс по&nbsp;отбору банков-агентов для&nbsp;выплаты возмещения (СТАРАЯ)", d(90)),
        ]
    elif "страхового случая" in low:
        items = [
            item(900003, "О&nbsp;наступлении страхового случая и&nbsp;назначении временной администрации (ТЕСТ)", d(0)),
            item(900004, "Сообщение о&nbsp;созыве собрания кредиторов (ШУМ)", d(0)),
            item(900005, "Сообщение о&nbsp;проведении торгов (ШУМ)", d(0)),
        ]
    else:
        items = []
    return {"sections": [{"code": "novosti", "items": items}]}

check.fetch = fake_fetch
failures = []

def run_once(state_path):
    os.environ["ASV_STATE"] = state_path
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        check.main()
    return buf.getvalue().strip().splitlines()

with tempfile.TemporaryDirectory() as td:
    state = os.path.join(td, "seen.json")

    # первый прогон: ждём 2 алерта (свежие KONKURS и STRAKH), без шума и без старой
    out = run_once(state)
    kinds = [l.split("|")[0] for l in out]
    joined = "\n".join(out)
    assert "KONKURS" in kinds, f"нет KONKURS в: {out}"
    assert "STRAKH" in kinds, f"нет STRAKH в: {out}"
    assert "ШУМ" not in joined, f"шум просочился: {out}"
    assert "СТАРАЯ" not in joined, f"старая запись заалертилась: {out}"
    assert len([k for k in kinds if k in ("KONKURS", "STRAKH")]) == 2, f"ожидали ровно 2 алерта, получили: {kinds}"
    print("PASS: свежие KONKURS+STRAKH заалерчены, шум и старьё отсечены")

    # повторный прогон с теми же данными -> дедуп, CLEAN
    out2 = run_once(state)
    assert out2 == ["CLEAN"], f"дедуп не сработал: {out2}"
    print("PASS: дедуп (повторный прогон -> CLEAN)")

print("\nALL E2E TESTS PASSED")
