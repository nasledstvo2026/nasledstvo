#!/usr/bin/env python3
"""
GAIA fine-tuning dataset builder.
For each Level 1+2 task:
  1. Run structured agent to gather Wikipedia facts
  2. Build prompt: [facts] + [question] → [gold answer]
  3. Save as JSONL for DeepSeek fine-tuning API
"""

import sys, os, json, re, time, requests, urllib.parse, argparse

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
WIKI_UA = "Mozilla/5.0 (compatible; GAIA-FT/1.0)"
CACHE_DIR = "/home/user1/.openclaw/workspace/gaia_results/ft_cache"

os.makedirs(CACHE_DIR, exist_ok=True)

def llm(prompt, max_tokens=500, temp=0.0):
    for a in range(3):
        try:
            r = requests.post(DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={"model": "deepseek-chat",
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": max_tokens, "temperature": temp},
                timeout=60)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except:
            time.sleep(2)
    return ""

# ── Wikipedia tools (same as agent) ────────────────────────────────

def wiki_search(query):
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": 3
        }, timeout=10, headers={"User-Agent": WIKI_UA})
        return [s["title"] for s in r.json().get("query",{}).get("search",[])]
    except:
        return []

def wiki_read(title):
    try:
        r = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title.replace(' ','_'))}",
                         timeout=10, headers={"User-Agent": WIKI_UA})
        if r.status_code == 200:
            d = r.json()
            return f"Title: {d.get('title','')}\nExtract: {d.get('extract','')[:3000]}"
    except:
        pass
    return ""

def google_search(query):
    try:
        r = requests.get("https://www.google.com/search", 
            params={"q": query, "num": 3},
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            timeout=15)
        urls = []
        for m in re.finditer(r'href="(/url\?q=[^"]+)"', r.text):
            url = urllib.parse.parse_qs(urllib.parse.urlparse(m.group(1)).query).get("q", [None])[0]
            if url and url.startswith("http"):
                urls.append(url)
        return urls[:3]
    except:
        return []

def read_url(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        text = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = ' '.join(text.split())
        return text[:5000]
    except:
        return ""

def gather_facts_for_task(question):
    """Use LLM to extract search topics, gather facts."""
    cache_key = f"facts_{hash(question) % 10000000}.json"
    cache_path = os.path.join(CACHE_DIR, cache_key)
    
    # Check cache
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            # Verify it's ours
            try:
                return json.load(f)
            except:
                pass
    
    # Analyze question
    analysis_prompt = f"""Analyze this GAIA question and extract search topics.

Question: {question}

Return EXACTLY:
TOPICS: [comma-separated Wikipedia article titles to search]
SEARCH: [comma-separated Google queries]"""
    
    analysis = llm(analysis_prompt, max_tokens=200, temp=0.0)
    
    # Parse
    topics = []
    searches = []
    
    m = re.search(r'TOPICS:\s*(.*)', analysis)
    if m:
        pts = [t.strip() for t in m.group(1).split(',') if t.strip().lower() != 'none' and t.strip()]
        topics.extend(pts)
    
    m = re.search(r'SEARCH:\s*(.*)', analysis)
    if m:
        qs = [q.strip() for q in m.group(1).split(',') if q.strip().lower() != 'none' and q.strip()]
        searches.extend(qs)
    
    facts = []
    
    for topic in topics[:3]:
        s = wiki_read(topic)
        if s:
            facts.append({"source": f"Wikipedia: {topic}", "content": s[:3000]})
        else:
            titles = wiki_search(topic)
            for t in titles[:2]:
                s = wiki_read(t)
                if s:
                    facts.append({"source": f"Wikipedia: {t}", "content": s[:3000]})
    
    for q in searches[:2]:
        urls = google_search(q)
        for url in urls[:2]:
            content = read_url(url)
            if content:
                facts.append({"source": f"Web: {url[:80]}", "content": content[:3000]})
    
    # Cache
    with open(cache_path, 'w') as f:
        json.dump(facts, f)
    
    return facts

def build_train_example(task, facts):
    """Build a JSONL training example from task + facts."""
    question = task['Question']
    answer = task['Final answer']
    
    if not facts:
        # No facts gathered — use LLM-only
        system = "You are a GAIA benchmark solver. Answer questions precisely and concisely."
        user = f"Answer the following question with just the exact answer (a number or short phrase).\n\nQuestion: {question}"
    else:
        # Format facts
        context = "\n\n".join([f"[{f['source']}]\n{f['content']}" for f in facts])
        system = "You are a GAIA benchmark solver. Use the provided facts to answer precisely."
        user = f"FACTS:\n{context[:8000]}\n\nQuestion: {question}\n\nAnswer with just the exact value, nothing else."
    
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": answer}
        ]
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--splits", type=str, default="1,2", help="Levels to include: 1,2 or 1 or 2")
    parser.add_argument("--max", type=int, default=999, help="Max tasks to process")
    args = parser.parse_args()
    
    from datasets import load_dataset
    ds = load_dataset('gaia-benchmark/GAIA', '2023_all', split='validation', 
                      cache_dir='/tmp/.cache-hf')
    
    levels = [int(x) for x in args.splits.split(',')]
    tasks = [t for t in ds if int(t['Level']) in levels and not t.get('file_name')]
    tasks = tasks[:args.max]
    
    print(f"Building dataset from {len(tasks)} tasks (no file attachments)", flush=True)
    
    examples = []
    errors = 0
    
    for i, task in enumerate(tasks):
        q = task['Question']
        tid = task['task_id'][:8]
        print(f"  [{i+1}/{len(tasks)}] {tid}: {q[:80]}...", end="", flush=True)
        
        try:
            facts = gather_facts_for_task(q)
            example = build_train_example(task, facts)
            examples.append(example)
            print(f" ✅ ({len(facts)} facts)", flush=True)
        except Exception as e:
            errors += 1
            print(f" ❌ {e}", flush=True)
        
        if (i+1) % 50 == 0:
            print(f"  → Checkpoint: {len(examples)} examples, {errors} errors", flush=True)
    
    # Split: 80% train, 20% val
    import random
    random.seed(42)
    random.shuffle(examples)
    
    split = int(len(examples) * 0.8)
    train = examples[:split]
    val = examples[split:]
    
    out_dir = "/home/user1/.openclaw/workspace/gaia_results/ft_dataset"
    os.makedirs(out_dir, exist_ok=True)
    
    train_path = os.path.join(out_dir, "train.jsonl")
    val_path = os.path.join(out_dir, "val.jsonl")
    
    for path, data in [(train_path, train), (val_path, val)]:
        with open(path, 'w') as f:
            for ex in data:
                f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    
    print(f"\n{'='*60}", flush=True)
    print(f"Dataset ready!", flush=True)
    print(f"Train: {len(train)} examples → {train_path}", flush=True)
    print(f"Val: {len(val)} examples → {val_path}", flush=True)
    print(f"Errors: {errors}", flush=True)
    
    # Estimate tokens
    total_tokens = 0
    for ex in examples:
        for m in ex['messages']:
            total_tokens += len(m['content'].split())
    print(f"Est. train tokens: ~{total_tokens * 1.3:.0f} (×1.3 BPE factor)", flush=True)

if __name__ == '__main__':
    main()
