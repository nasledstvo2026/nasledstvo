#!/usr/bin/env python3
import sys, os, json, time, argparse

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--max-age-min", type=int, default=180)
    ap.add_argument("--min-items", type=int, default=0)
    a = ap.parse_args()
    problems, info = [], []
    now = time.time()
    for p in a.files:
        if not os.path.isfile(p):
            problems.append("missing: " + p); continue
        age = (now - os.path.getmtime(p)) / 60.0
        if age > a.max_age_min:
            problems.append("stale: %s (%.0f min > %d)" % (p, age, a.max_age_min)); continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            problems.append("invalid json: %s (%s)" % (p, str(e)[:80])); continue
        n = len(data) if isinstance(data, (list, dict)) else 0
        if a.min_items and n < a.min_items:
            problems.append("too few items: %s (%d < %d)" % (p, n, a.min_items)); continue
        info.append("%s age=%.0fmin items=%d" % (p, age, n))
    if problems:
        print("GATE_FAIL")
        for x in problems: print(" - " + x)
        return 2
    print("GATE_OK")
    for x in info: print(" - " + x)
    return 0

sys.exit(main())
