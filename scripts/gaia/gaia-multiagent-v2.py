#!/usr/bin/env python3
"""
GAIA Multi-Agent Runner — архитектура: Router → Collector → Solver → Verifier (с ретрай-циклом).

Каждый агент — отдельный LLM-вызов со своим system prompt.
Verifier проверяет ответ по фактам. Если не прошёл → уточняющий поиск → до 3 циклов.

Использование:
  python3 gaia-multiagent.py --tasks 10 --level 1

Результат: gaia_results_<timestamp>_multiagent.json
"""

import sys, os, json, re, time, argparse, requests, urllib.parse, subprocess, textwrap
from datetime import datetime

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
WIKI_UA = "Mozilla/5.0 (compatible; GAIA-Benchmark-MultiAgent/1.0)"

DEBUG = True

# ── LLM helper с system prompt ────────────────────────────────────

def llm(prompt, system="", max_tokens=500, temp=0.0, timeout=60):
    """Call DeepSeek Chat with optional system prompt."""
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    
    for attempt in range(3):
        try:
            r = requests.post(DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={"model": "deepseek-chat",
                      "messages": msgs,
                      "max_tokens": max_tokens,
                      "temperature": temp},
                timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            print(f"  ⚠️ LLM returned {r.status_code}: {r.text[:200]}", flush=True)
        except requests.exceptions.Timeout:
            print(f"  ⚠️ LLM timeout (attempt {attempt+1}/3)", flush=True)
        except Exception as e:
            print(f"  ⚠️ LLM error: {e}", flush=True)
        time.sleep(2)
    return ""

# ── Agent System Prompts ──────────────────────────────────────────

ROUTER_SYSTEM = """You are a GAIA Task Router. Your job is to analyze a GAIA benchmark task and determine:
1. What type of information is needed
2. What tools should be used
3. What the expected answer format is

First, classify the task into one of these categories:

### KNOWLEDGE_ONLY — НЕ ИСПОЛЬЗУЙ ИНСТРУМЕНТЫ
Task meets ANY of:
- Academic/historical fact: dates, events, people, terms
- Conceptual/theoretical question: definition, explanation of a phenomenon
- Objective fact from common knowledge (school/university curriculum)
- Question does NOT reference current date, laws, documents, prices
→ Answer goes directly to Solver from model knowledge. NO search needed.

### TOOL_REQUIRED — ИСПОЛЬЗУЙ ИНСТРУМЕНТЫ
Task meets ANY of:
- Requires current data: news, rates, weather, recent events
- References a specific law/regulation/statute
- Contains "check", "find", "look up", "verify", "search"
- Requires a document/extract/report
→ Must use Collector for search.

### HYBRID — ИСПОЛЬЗУЙ ИНСТРУМЕНТЫ
Task meets ALL:
- Contains facts model can recall from training
- AND requires verification or comparison with external data
→ Must use Collector for verification.

### BORDERLINE (uncertain)
Default to TOOL_REQUIRED (safe side).

Return your analysis in this exact format:
CLASS: [KNOWLEDGE_ONLY | TOOL_REQUIRED | HYBRID]
TYPE: [fact_lookup | calculation | riddle | hybrid | complex]
WIKI_TOPICS: [comma-separated Wikipedia article names to search, or NONE]
SEARCH_QUERIES: [comma-separated Google search queries, or NONE]
HAS_URL: [YouTube URL or specific URL if mentioned, or NONE]
HAS_FILE: [YES if task mentions an attachment, NO if not]
NUMERIC: [YES if answer is a number, NO if text]
ANSWER_FORMAT: [short description of expected format]
PLAN: [1-2 sentence plan of attack]
CONFIDENCE: [HIGH | MEDIUM | LOW] how confident you are in the plan"""

COLLECTOR_SYSTEM = """You are a GAIA Fact Collector. Your job is to extract RELEVANT facts from the provided raw data sources to answer the specific question.

You will receive:
- The original task
- Raw data from searches (Wikipedia, web, etc.)

Rules:
1. Extract ONLY facts that are directly relevant to answering the question
2. Include exact numbers, dates, names
3. If data is missing, say "NO_DATA: <what's missing>"
4. Be concise — facts only, no commentary
5. If multiple sources contradict, note the discrepancy

Return format:
FACTS:
• [fact 1]
• [fact 2]
...
MISSING: [what information is still needed, or NONE]
SOURCES: [sources used]"""

SOLVER_SYSTEM = """You are a GAIA Task Solver. Your job is to answer the question using ONLY the facts provided.

You will receive:
- The original task
- Facts collected by the Collector agent

Rules:
1. Answer ONLY from the provided facts — do NOT use your internal knowledge
2. If the facts contain the exact answer, use it directly
3. If calculation is needed, do it step by step
4. Output ONLY the final answer — a number, word, or short phrase
5. NO explanations, NO step-by-step in the output
6. If you cannot answer from facts, write "INSUFFICIENT: <what's missing>"

Return format:
ANSWER: [exact answer, or INSUFFICIENT: reason]"""

VERIFIER_SYSTEM = """You are a GAIA Answer Verifier. Your job is to check if the proposed answer is CORRECT based on the collected facts.

You will receive:
- The original task
- The collected facts
- The proposed answer

Rules:
1. Check if the answer is directly supported by the facts
2. Check if the answer matches the expected format
3. Check if the answer is precise enough (partial matches are failures)
4. If the answer is WRONG or INSUFFICIENT, say what specific fact is missing

Return format:
VERDICT: [PASS | FAIL | UNCERTAIN]
REASON: [why it passed/failed]
MISSING_INFO: [what specific fact would confirm the answer, or NONE]
NEXT_STEP: [APPROVED | RERUN_SEARCH: <new search query> | RERUN_SOLVE]"""

# ── Tools ─────────────────────────────────────────────────────────

def wiki_search(query, top_n=5):
    """Search Wikipedia by title."""
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": top_n
        }, timeout=10, headers={"User-Agent": WIKI_UA})
        return [s["title"] for s in r.json().get("query",{}).get("search",[])]
    except:
        return []

def wiki_read(title):
    """Get Wikipedia page summary."""
    try:
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title.replace(' ','_'))}",
            timeout=10, headers={"User-Agent": WIKI_UA})
        if r.status_code == 200:
            d = r.json()
            return f"Title: {d.get('title','')}\nExtract: {d.get('extract','')[:5000]}"
    except:
        pass
    return ""

def wiki_full_section(title, section_title=None):
    """Get full section text from Wikipedia."""
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "parse", "page": title, "prop": "text",
            "format": "json"
        }, timeout=10, headers={"User-Agent": WIKI_UA})
        if r.status_code == 200:
            html = r.json()["parse"]["text"]["*"]
            text = re.sub(r'<[^>]+>', '\n', html)
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            return '\n'.join(lines)[:8000]
    except:
        pass
    return ""

def google_search(query):
    """Search via Google HTML (no API). Falls back to Wikipedia if blocked."""
    try:
        r = requests.get("https://www.google.com/search",
            params={"q": query, "num": 3},
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=15)
        urls = []
        for m in re.finditer(r'href="(/url\?q=[^"]+)"', r.text):
            url = urllib.parse.parse_qs(urllib.parse.urlparse(m.group(1)).query).get("q", [None])[0]
            if url and url.startswith("http"):
                urls.append(url)
        return urls[:3]
    except:
        return []

def fetch_url(url):
    """Fetch and extract text from a URL."""
    try:
        r = requests.get(url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            timeout=15)
        text = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = ' '.join(text.split())
        return text[:8000]
    except:
        return ""

def youtube_info(url):
    """Get YouTube metadata."""
    try:
        r = subprocess.run(["yt-dlp", "--print", "title", "--print", "description",
                           "--skip-download", url],
                          capture_output=True, text=True, timeout=30)
        return r.stdout[:5000]
    except:
        return ""

# ── Multi-Agent Pipeline ──────────────────────────────────────────

def router_agent(task):
    """Agent 1: Router — classify task and create plan."""
    result = llm(task, system=ROUTER_SYSTEM, max_tokens=400, temp=0.0)
    if DEBUG:
        print(f"  🔀 Router: {result[:200]}", flush=True)
    return result

def collector_agent(task, raw_data):
    """Agent 2: Collector — extract relevant facts from raw data."""
    prompt = f"TASK:\n{task}\n\nRAW DATA:\n{raw_data[:15000]}"
    result = llm(prompt, system=COLLECTOR_SYSTEM, max_tokens=600, temp=0.0)
    return result

def solver_agent(task, facts):
    """Agent 3: Solver — answer from facts."""
    prompt = f"TASK:\n{task}\n\nFACTS:\n{facts[:8000]}"
    result = llm(prompt, system=SOLVER_SYSTEM, max_tokens=200, temp=0.0)
    if DEBUG:
        print(f"  🧠 Solver: {result[:100]}", flush=True)
    return result

def verifier_agent(task, facts, answer):
    """Agent 4: Verifier — check answer against facts."""
    prompt = f"TASK:\n{task}\n\nFACTS:\n{facts[:8000]}\n\nPROPOSED ANSWER:\n{answer}"
    result = llm(prompt, system=VERIFIER_SYSTEM, max_tokens=300, temp=0.0)
    if DEBUG:
        print(f"  🔍 Verifier: {result[:150]}", flush=True)
    return result

# ── Tool executor ─────────────────────────────────────────────────

def execute_tool_plan(wiki_topics, search_queries, youtube_url):
    """Execute the tool plan from router and collect raw data."""
    raw_data = []
    
    # Wikipedia lookups
    for topic in wiki_topics[:3]:
        if topic.upper() == "NONE":
            continue
        summary = wiki_read(topic)
        if summary:
            raw_data.append(f"[Wikipedia: {topic}]\n{summary}")
        else:
            # Try searching
            titles = wiki_search(topic)
            if titles:
                summary = wiki_read(titles[0])
                if summary:
                    raw_data.append(f"[Wikipedia: {titles[0]}]\n{summary}")
    
    # Google searches
    for q in search_queries[:2]:
        if q.upper() == "NONE":
            continue
        urls = google_search(q)
        for url in urls[:2]:
            content = fetch_url(url)
            if content:
                raw_data.append(f"[Web: {q}]\n{content[:3000]}")
    
    # YouTube
    if youtube_url and youtube_url.upper() != "NONE":
        info = youtube_info(youtube_url)
        if info:
            raw_data.append(f"[YouTube]\n{info[:3000]}")
    
    return "\n\n===\n\n".join(raw_data) if raw_data else "(no data collected)"

def execute_refined_search(query):
    """Execute a single refined search query from verifier."""
    results = []
    
    # Try Wikipedia
    titles = wiki_search(query)
    if titles:
        summary = wiki_read(titles[0])
        if summary:
            results.append(f"[Wikipedia: {titles[0]}]\n{summary}")
    
    # Try web search
    urls = google_search(query)
    for url in urls[:1]:
        content = fetch_url(url)
        if content:
            results.append(f"[Web: {query}]\n{content[:3000]}")
    
    return "\n\n===\n\n".join(results) if results else "(no additional data)"

# ── Solve one GAIA task (multi-agent) ────────────────────────────

def solve_multiagent(task, task_id="unknown"):
    """Solve a GAIA task using multi-agent pipeline with verifier loop."""
    start = time.time()
    print(f"\n{'='*60}", flush=True)
    print(f"📋 [{task_id}] Multi-Agent GAIA Solver", flush=True)
    print(f"Q: {task[:120]}...", flush=True)
    
    # ── Step 1: Route ──
    print(f"\n  ── Agent 1: Router ──", flush=True)
    route_result = router_agent(task)
    
    # Parse router output: CLASS + tools
    task_class = ""
    wiki_topics = []
    search_queries = []
    youtube_url = "NONE"
    
    cm = re.search(r'CLASS:\s*(\S+)', route_result)
    if cm:
        task_class = cm.group(1).strip().upper()
    
    wm = re.search(r'WIKI_TOPICS:\s*(.*?)(?:\n|$)', route_result, re.DOTALL)
    if wm:
        topics = wm.group(1).strip()
        wiki_topics = [t.strip().strip('"[]') for t in re.split(r'[,;]', topics) if t.strip().lower() != 'none' and t.strip()]
    
    sm = re.search(r'SEARCH_QUERIES:\s*(.*?)(?:\n|$)', route_result, re.DOTALL)
    if sm:
        queries = sm.group(1).strip()
        search_queries = [q.strip().strip('"[]') for q in re.split(r'[,;]', queries) if q.strip().lower() != 'none' and q.strip()]
    
    ym = re.search(r'HAS_URL:\s*(\S+)', route_result)
    if ym:
        yt_val = ym.group(1).strip()
        if yt_val.upper() not in ("NONE", "NO", ""):
            youtube_url = yt_val
    
    print(f"    CLASS: {task_class}", flush=True)
    print(f"    Wiki topics: {wiki_topics[:3]}", flush=True)
    print(f"    Search: {search_queries[:2]}", flush=True)
    
    # KNOWLEDGE_ONLY bypass: answer directly from model, skip Collector entirely
    if task_class == "KNOWLEDGE_ONLY":
        print(f"\n  KNOWLEDGE_ONLY detected -> Solver (direct, no Collector)", flush=True)
        # Call solver WITHOUT facts — use model's own knowledge
        solver_mod = SOLVER_SYSTEM.replace(
            "Answer ONLY from the provided facts",
            "Answer from your own knowledge"
        ).replace(
            "ONLY the facts provided",
            "your own knowledge"
        ).replace(
            "do NOT use your internal knowledge",
            "use your internal knowledge"
        )
        prompt = f"TASK:\n{task}\n\n"
        answer = llm(prompt, system=solver_mod, max_tokens=200, temp=0.0)
        final_answer = answer
        elapsed = time.time() - start
        print(f"\n  ⏱ {elapsed:.1f}s | Answer: {final_answer[:80]}", flush=True)
        clean_answer = final_answer
        if clean_answer.startswith("ANSWER:"):
            clean_answer = clean_answer.replace("ANSWER:", "", 1).strip()
        if clean_answer.startswith("INSUFFICIENT:"):
            clean_answer = "(insufficient) " + clean_answer
        return clean_answer, round(elapsed, 1)
    
    # ── Step 2: Collect facts (initial) ──
    print(f"\n  ── Agent 2: Collector (initial search) ──", flush=True)
    raw_data = execute_tool_plan(wiki_topics, search_queries, youtube_url)
    facts = collector_agent(task, raw_data)
    print(f"    Facts collected: {len(facts)} chars", flush=True)

    # ── Step 3-4: Solve + Verify loop (up to 3 cycles) ──
    final_answer = ""
    for cycle in range(3):
        print(f"\n  ── Cycle {cycle+1}/3: Solver → Verifier ──", flush=True)
        
        # Solve
        answer = solver_agent(task, facts)
        final_answer = answer
        
        # Check if solver says insufficient
        if answer.startswith("INSUFFICIENT:"):
            missing = answer.replace("INSUFFICIENT:", "").strip()
            print(f"    ⚠️ Solver says insufficient: {missing}", flush=True)
            # Try a refined search
            more_data = execute_refined_search(missing)
            if more_data and "no additional data" not in more_data:
                raw_data += "\n\n===\n\n" + more_data
                facts = collector_agent(task, raw_data)
                continue
            else:
                break
        
        # Verify
        verdict = verifier_agent(task, facts, answer)
        
        if "VERDICT: PASS" in verdict or "VERDICT:PASS" in verdict:
            print(f"    ✅ Verdict: PASS", flush=True)
            break
        elif "RERUN_SEARCH:" in verdict:
            # Extract new search query
            qm = re.search(r'RERUN_SEARCH:\s*(.+?)(?:\n|$)', verdict)
            if qm:
                new_query = qm.group(1).strip()
                print(f"    🔄 Rerun search: {new_query}", flush=True)
                more_data = execute_refined_search(new_query)
                if more_data and "no additional data" not in more_data:
                    raw_data += "\n\n===\n\n" + more_data
                    facts = collector_agent(task, raw_data)
                    continue
            break
        elif "RERUN_SOLVE" in verdict:
            print(f"    🔄 Rerun solve (same facts)", flush=True)
            # Just loop back to solver
            continue
        else:
            # FAIL or UNCERTAIN — try once more with broader search
            print(f"    ⚠️ Verdict: FAIL. Retrying with broader search...", flush=True)
            if cycle < 2:
                # Broader search
                for topic in wiki_topics[:1]:
                    more = wiki_full_section(topic)
                    if more:
                        raw_data += "\n\n===\n\n" + f"[Wikipedia full: {topic}]\n{more[:5000]}"
                facts = collector_agent(task, raw_data)
            else:
                break
    
    elapsed = time.time() - start
    print(f"\n  ⏱ {elapsed:.1f}s | Answer: {final_answer[:80]}", flush=True)
    
    # Clean up answer
    clean_answer = final_answer
    if clean_answer.startswith("ANSWER:"):
        clean_answer = clean_answer.replace("ANSWER:", "", 1).strip()
    if clean_answer.startswith("INSUFFICIENT:"):
        clean_answer = "(insufficient) " + clean_answer
    
    return clean_answer, round(elapsed, 1)


def normalize_answer(answer):
    """Normalize answer for comparison."""
    a = answer.strip().lower().rstrip('.')
    a = re.sub(r'^(the|a|an)\s+', '', a)
    a = a.strip()
    # Remove leading zeros from numbers
    if a.replace(',', '').replace('.', '').replace(' ', '').replace('-', '').isdigit():
        try:
            return str(float(a.replace(',', '')))
        except:
            pass
    return a


def main():
    parser = argparse.ArgumentParser(description="GAIA Multi-Agent Runner")
    parser.add_argument("--tasks", type=int, default=10, help="Number of tasks to run")
    parser.add_argument("--level", type=str, default="1", help="GAIA level: 1, 2, 3, or all")
    parser.add_argument("--file", type=str, help="Specific task file to load")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument("--no-retry", action="store_true", help="Disable verifier retry loop")
    args = parser.parse_args()
    
    from datasets import load_dataset
    ds = load_dataset('gaia-benchmark/GAIA', '2023_all', split='validation',
                      cache_dir='/tmp/.cache-hf')
    
    # Filter by level
    if args.level and args.level != "all":
        tasks = [t for t in ds if t['Level'] == args.level]
    else:
        tasks = list(ds)
    
    import random
    random.seed(args.seed)
    random.shuffle(tasks)
    tasks = tasks[:args.tasks]
    
    print(f"🔬 GAIA Multi-Agent Benchmark", flush=True)
    print(f"   Model: deepseek-chat (multi-agent: Router → Collector → Solver → Verifier)", flush=True)
    print(f"   Level: {args.level} | Tasks: {len(tasks)} | Retry: {'off' if args.no_retry else 'on'}", flush=True)
    
    results = []
    for i, task in enumerate(tasks):
        q = task['Question']
        gold = task['Final answer']
        tid = task.get('task_id', f"task_{i}")[:8]
        
        if args.no_retry:
            # Simple single-pass multi-agent
            route = router_agent(q)
            wiki_topics = []
            search_queries = []
            youtube_url = "NONE"
            
            wm = re.search(r'WIKI_TOPICS:\s*(.*?)(?:\n|$)', route, re.DOTALL)
            if wm:
                topics = wm.group(1).strip()
                wiki_topics = [t.strip().strip('"[]') for t in re.split(r'[,;]', topics) if t.strip().lower() != 'none' and t.strip()]
            
            sm = re.search(r'SEARCH_QUERIES:\s*(.*?)(?:\n|$)', route, re.DOTALL)
            if sm:
                queries = sm.group(1).strip()
                search_queries = [q.strip().strip('"[]') for q in re.split(r'[,;]', queries) if q.strip().lower() != 'none' and q.strip()]
            
            ym = re.search(r'HAS_URL:\s*(\S+)', route)
            if ym:
                yt_val = ym.group(1).strip()
                if yt_val.upper() not in ("NONE", "NO", ""):
                    youtube_url = yt_val
            
            start = time.time()
            raw_data = execute_tool_plan(wiki_topics, search_queries, youtube_url)
            facts = collector_agent(q, raw_data)
            answer = solver_agent(q, facts)
            elapsed = time.time() - start
            
            clean = answer
            if clean.startswith("ANSWER:"):
                clean = clean.replace("ANSWER:", "", 1).strip()
        else:
            clean, elapsed = solve_multiagent(q, tid)
        
        # Compare
        norm_answer = normalize_answer(clean)
        norm_gold = normalize_answer(gold)
        correct = norm_answer == norm_gold
        partial = norm_gold in norm_answer or norm_answer in norm_gold
        
        mark = "✅" if correct else "🔶" if partial else "❌"
        print(f"{mark} [{tid}] {clean[:60]} (gold: {gold[:40]})", flush=True)
        
        results.append({
            "task_id": tid,
            "question": q[:200],
            "gold": gold,
            "answer": clean,
            "correct": correct,
            "partial": partial,
            "time_sec": elapsed,
            "level": task['Level'],
        })
    
    # Summary
    correct_count = sum(1 for r in results if r['correct'])
    partial_count = sum(1 for r in results if r['partial'] and not r['correct'])
    total_time = sum(r['time_sec'] for r in results)
    
    print(f"\n{'='*60}", flush=True)
    print(f"📊 GAIA MULTI-AGENT RESULTS", flush=True)
    print(f"   Level: {args.level} | Tasks: {len(results)} | Retry: {'off' if args.no_retry else 'on'}", flush=True)
    print(f"   Exact matches: {correct_count}/{len(results)} = {correct_count/len(results)*100:.1f}%", flush=True)
    print(f"   Partial matches: {partial_count}/{len(results)} = {partial_count/len(results)*100:.1f}%", flush=True)
    print(f"   Total/exact accuracy: {correct_count/len(results)*100:.1f}%", flush=True)
    print(f"   Avg time: {total_time/len(results):.0f}s", flush=True)
    
    # Save results
    out = {
        "date": datetime.now().isoformat(),
        "model": "deepseek-chat (multi-agent: Router→Collector→Solver→Verifier)",
        "level": args.level,
        "retry_enabled": not args.no_retry,
        "total": len(results),
        "correct_exact": correct_count,
        "correct_partial": partial_count,
        "accuracy_exact": round(correct_count/len(results)*100, 1),
        "accuracy_partial": round((correct_count+partial_count)/len(results)*100, 1),
        "avg_time_sec": round(total_time/len(results), 0),
        "results": results,
    }
    os.makedirs("/home/user1/.openclaw/workspace/gaia_results", exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f"gaia_results_{timestamp}_multiagent.json"
    path = f"/home/user1/.openclaw/workspace/gaia_results/{fname}"
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved: {path}", flush=True)
    
    print(f"\n{'='*60}", flush=True)
    for r in results:
        mark = "✅" if r['correct'] else "🔶" if r['partial'] else "❌"
        print(f"  {mark} [{r['task_id']}] model: {r['answer'][:60]} | gold: {r['gold'][:40]} | {r['time_sec']}s", flush=True)
    
    return results


if __name__ == "__main__":
    main()
