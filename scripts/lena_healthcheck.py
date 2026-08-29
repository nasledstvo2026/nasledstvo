#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lena_healthcheck.py — сверка raw по доменам с эталоном.

Запускает детерминированный сбор (lena_collect.collect), считает записи по
доменам и сравнивает с порогами из knowledge/lena/raw-baseline.json.

Exit code: 0 — все источники в норме; 1 — есть просевшие (ниже порога).
"""
import json, sys

sys.path.insert(0, "/home/user1/.openclaw/workspace/scripts")
from lena_collect import collect  # noqa: E402

BASE = "/home/user1/.openclaw/workspace/knowledge/lena/raw-baseline.json"


def main():
    with open(BASE, encoding="utf-8") as f:
        baseline = json.load(f)

    raw, _domains = collect()

    per = {}
    for r in raw:
        per[r["source"]] = per.get(r["source"], 0) + 1

    problems = []
    print("=== HEALTHCHECK ===")
    print(f"total_raw={len(raw)}")
    for dom in sorted(set(list(per.keys()) + list(baseline.keys()))):
        if dom.startswith("_"):
            continue
        got = per.get(dom, 0)
        thr = baseline.get(dom, 0) or 0
        mark = ""
        if thr > 0 and got < thr:
            mark = "  <-- LOW"
            problems.append((dom, thr, got))
        print(f"  {dom}={got}{mark}")

    if problems:
        print("PROBLEMS:")
        for dom, thr, got in problems:
            print(f"  {dom}: got {got} < threshold {thr}")
        sys.exit(1)
    print("OK: all sources within baseline")
    sys.exit(0)


if __name__ == "__main__":
    main()
