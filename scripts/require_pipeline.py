#!/usr/bin/env python3
import sys, os, json, time, argparse, subprocess

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--producer", required=True)
    ap.add_argument("--input", nargs="+", required=True)
    ap.add_argument("--max-run-age-min", type=int, default=180)
    ap.add_argument("--max-input-age-min", type=int, default=None)
    ap.add_argument("--fresh-if-nonempty", action="store_true")
    ap.add_argument("--skip-if-stale", action="store_true")
    ap.add_argument("--skip-fresh-if", default=None)
    a = ap.parse_args()
    max_input_age = a.max_input_age_min if a.max_input_age_min is not None else a.max_run_age_min
    problems, info, skips = [], [], []
    try:
        raw = subprocess.run(["openclaw", "cron", "get", a.producer, "--json"], capture_output=True, text=True, timeout=30)
        job = json.loads(raw.stdout)
    except Exception as e:
        print("GATE_FAIL")
        print(" - producer query failed: " + str(e)[:120])
        return 2
    status = job.get("lastRunStatus")
    last = job.get("lastRunAtMs") or 0
    age = (time.time() * 1000 - last) / 60000.0 if last else 10**9
    if status != "ok":
        problems.append("producer %s lastRunStatus=%s" % (job.get("name", a.producer), status))
    if age > a.max_run_age_min:
        problems.append("producer run age %.0f min > %d" % (age, a.max_run_age_min))
    skip_fresh = False
    if a.skip_fresh_if:
        try:
            skip_fresh = len(json.load(open(a.skip_fresh_if, encoding="utf-8"))) == 0
        except Exception:
            skip_fresh = False
    for p in a.input:
        if not os.path.isfile(p):
            problems.append("missing: " + p); continue
        try:
            data = json.load(open(p, encoding="utf-8"))
        except Exception as e:
            problems.append("invalid json: %s (%s)" % (p, str(e)[:60])); continue
        n = len(data) if isinstance(data, (list, dict)) else 0
        mtime_ms = os.path.getmtime(p) * 1000
        if a.skip_if_stale and last and mtime_ms < last - 60000:
            skips.append("no new input: %s (older than producer run)" % p); continue
        if a.fresh_if_nonempty and n > 0 and not skip_fresh:
            fage = (time.time() * 1000 - mtime_ms) / 60000.0
            if fage > max_input_age:
                problems.append("stale non-empty input: %s (%.0f min)" % (p, fage)); continue
        info.append("%s items=%d age=%.0fmin" % (p, n, (time.time() - mtime_ms/1000) / 60.0))
    if problems:
        print("GATE_FAIL")
        for x in problems: print(" - " + x)
        return 2
    if skips and not info:
        print("GATE_SKIP")
        for x in skips: print(" - " + x)
        return 3
    print("GATE_OK")
    print(" - producer ok, run %.0f min ago" % age)
    for x in skips: print(" - skip: " + x)
    for x in info: print(" - " + x)
    return 0

sys.exit(main())
