#!/usr/bin/env python3
"""
FEVER Multi-Agent: Router → Collector → Solver → Verifier
Проверяет способность системы подтверждать/опровергать факты по Wikipedia.
"""

import sys, os, json, re, time, argparse, requests, urllib.parse, random
from datetime import datetime
from collections import Counter

_raw_key = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_KEY = _raw_key.encode("utf-8", "replace").decode("utf-8")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
WIKI_UA = "Mozilla/5.0 (compatible; FEVER-Benchmark/1.0)"

def llm(prompt, system="", max_tokens=400, temp=0.0, timeout=30):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    for a in range(3):
        try:
            safe_key = DEEPSEEK_API_KEY.encode("ascii", "replace").decode("ascii")
            r = requests.post(DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {safe_key}"},
                json={"model": "deepseek-chat",
                      "messages": msgs,
                      "max_tokens": max_tokens,
                      "temperature": temp},
                timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            print(f"  ⚠️ LLM {r.status_code}: {r.text[:100]}", flush=True)
        except Exception as e:
            print(f"  ⚠️ LLM error: {e}", flush=True)
        time.sleep(2)
    return ""

# ── System prompts ──

ROUTER_SYSTEM = """You are a FEVER Router. Classify the claim about what verification is needed.

A claim is a factual assertion that may be true (SUPPORTS), false (REFUTES), or unverifiable (NEI).

Return:
CLASSIFICATION: [KNOWLEDGE_ONLY | TOOL_REQUIRED | BORDERLINE]
KNOWLEDGE_ONLY = the claim uses common general knowledge that any educated person would know
TOOL_REQUIRED = the claim requires searching Wikipedia or the web to verify
BORDERLINE = uncertain, treat as TOOL_REQUIRED
REASON: [brief justification for the classification]"""

COLLECTOR_SYSTEM = """You are a Fact Collector. You receive a claim and search results or Wikipedia data. Extract ONLY facts directly relevant to verifying the claim.

FACTS:
• [fact 1]
• [fact 2]
...
VERIFICATION: [SUPPORTS | REFUTES | NOT ENOUGH INFO]
CONFIDENCE: [HIGH | MEDIUM | LOW]
EVIDENCE: [the specific text that supports/refutes the claim, or empty for NEI]"""

SOLVER_SYSTEM = """You are a FEVER Solver. Given a claim and supporting facts, determine the label.

Rules:
1. If facts clearly support the claim → SUPPORTS
2. If facts clearly contradict the claim → REFUTES
3. If facts don't address the claim or are insufficient → NOT ENOUGH INFO
4. Return ONLY: LABEL: [SUPPORTS | REFUTES | NOT ENOUGH INFO]

LABEL:"""

VERIFIER_SYSTEM = """You are a FEVER Verifier. Review the label assignment against the evidence. You must be strict.

Evidence that explicitly confirms → SUPPORTS
Evidence that explicitly contradicts → REFUTES
Ambiguous, missing, or insufficient evidence → NOT ENOUGH INFO

Do NOT use your own knowledge. Judge ONLY based on the evidence provided.

Return:
REVIEW: [CORRECT | INCORRECT | AMBIGUOUS]
CORRECTED_LABEL: [SUPPORTS | REFUTES | NOT ENOUGH INFO]
REASON: [1 sentence explanation]"""

BASELINE_SYSTEM = """Given a claim, determine: SUPPORTS (true), REFUTES (false), or NOT ENOUGH INFO (cannot verify).
Use your own knowledge. Return ONLY: LABEL: [SUPPORTS | REFUTES | NOT ENOUGH INFO]"""

# ── Tools ──

def wiki_search(query, top=3):
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": top
        }, timeout=10, headers={"User-Agent": WIKI_UA})
        return [s["title"] for s in r.json().get("query",{}).get("search",[])]
    except:
        return []

def wiki_read(title):
    try:
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title.replace(' ','_'))}",
            timeout=10, headers={"User-Agent": WIKI_UA})
        if r.status_code == 200:
            d = r.json()
            return f"Title: {d.get('title','')}\nExtract: {d.get('extract','')[:4000]}"
    except:
        pass
    return ""

def solve_multiagent(claim):
    """Solve one FEVER claim with multi-agent pipeline."""
    start = time.time()
    
    # Router: classify
    route = llm(f"Claim: {claim}", system=ROUTER_SYSTEM, max_tokens=200, temp=0.0)
    classification = "KNOWLEDGE_ONLY"
    m = re.search(r'CLASSIFICATION:\s*(KNOWLEDGE_ONLY|TOOL_REQUIRED|BORDERLINE)', route, re.IGNORECASE)
    if m:
        classification = m.group(1).upper()
    
    raw_data = ""
    if classification in ("TOOL_REQUIRED", "BORDERLINE"):
        # Collect facts from Wikipedia
        titles = wiki_search(claim, top=3)
        for t in titles[:2]:
            s = wiki_read(t)
            if s:
                raw_data += f"\n\n[Wikipedia: {t}]\n{s}"
        
        # Additional search with key terms from claim
        words = [w for w in claim.split() if w[0].isupper() and len(w) > 2][:2]
        for word in words:
            if len(raw_data) < 2000:
                titles2 = wiki_search(word, top=2)
                for t in titles2:
                    if raw_data.find(f"[Wikipedia: {t}]") == -1:
                        s = wiki_read(t)
                        if s:
                            raw_data += f"\n\n[Wikipedia: {t}]\n{s}"
    
    if raw_data:
        # Collector: extract facts
        facts = llm(f"Claim: {claim}\n\nEvidence:\n{raw_data[:8000]}",
                    system=COLLECTOR_SYSTEM, max_tokens=400, temp=0.0)
        
        # Solver: determine label
        label_raw = llm(f"Claim: {claim}\n\nFacts:\n{facts[:6000]}",
                        system=SOLVER_SYSTEM, max_tokens=100, temp=0.0)
        
        # Verifier: check the label
        label = extract_label(label_raw)
        verification = llm(f"Claim: {claim}\nLabel: {label}\nEvidence:\n{facts[:6000]}",
                          system=VERIFIER_SYSTEM, max_tokens=200, temp=0.0)
        
        # Apply verification correction
        m = re.search(r'CORRECTED_LABEL:\s*(SUPPORTS|REFUTES|NOT ENOUGH INFO)', verification, re.IGNORECASE)
        review = re.search(r'REVIEW:\s*(CORRECT|INCORRECT|AMBIGUOUS)', verification, re.IGNORECASE)
        if m and review:
            review_tag = review.group(1).upper()
            if review_tag == "INCORRECT":
                final_label = m.group(1).upper()
            else:
                final_label = label
        else:
            final_label = label
    else:
        # KNOWLEDGE_ONLY: answer directly
        raw = llm(f"Claim: {claim}", system=BASELINE_SYSTEM, max_tokens=100, temp=0.0)
        final_label = extract_label(raw)
        facts = ""
        verification = "KNOWLEDGE_ONLY: direct answer"
    
    elapsed = time.time() - start
    return final_label, elapsed, classification, facts[:200] if facts else "", raw_data[:200] if raw_data else "", verification[:200] if verification else ""

def extract_label(text):
    m = re.search(r'LABEL:\s*(SUPPORTS|REFUTES|NOT ENOUGH INFO)', text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Fallback: scan for the words
    for label in ["SUPPORTS", "REFUTES", "NOT ENOUGH INFO"]:
        if label in text.upper():
            return label
    return "NOT ENOUGH INFO"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    with open("/home/user1/.openclaw/workspace/benchmark_results/fever_test_50.json") as f:
        claims = json.load(f)
    
    sample = claims[:args.tasks]
    
    print(f"🔬 FEVER Multi-Agent Benchmark", flush=True)
    print(f"   Model: deepseek-chat (Router→Collector→Solver→Verifier)", flush=True)
    print(f"   Tasks: {len(sample)}", flush=True)
    print(f"   Ground truth:", flush=True)
    gt = Counter(c['label'] for c in sample)
    for k, v in gt.items():
        print(f"     {k}: {v}", flush=True)
    
    results = []
    
    # Baseline run: plain LLM (no search, no verification)
    print(f"\n{'='*60}", flush=True)
    print(f"📋 BASELINE (Plain LLM)", flush=True)
    baseline_correct = 0
    for i, item in enumerate(sample):
        raw = llm(f"Claim: {item['claim']}", system=BASELINE_SYSTEM, max_tokens=100, temp=0.0)
        pred = extract_label(raw)
        correct = pred == item['label']
        if correct:
            baseline_correct += 1
        mark = "✅" if correct else "❌"
        # Only print if wrong
        if not correct:
            print(f"  {mark} [{i+1}] gold={item['label']} pred={pred}: {item['claim'][:60]}", flush=True)
    print(f"\n  Baseline accuracy: {baseline_correct}/{len(sample)} = {baseline_correct/len(sample)*100:.1f}%", flush=True)
    
    # Multi-agent run
    print(f"\n{'='*60}", flush=True)
    print(f"📋 MULTI-AGENT (Router→Collector→Solver→Verifier)", flush=True)
    multi_correct = 0
    classified = {"KNOWLEDGE_ONLY": {"total": 0, "correct": 0},
                  "TOOL_REQUIRED": {"total": 0, "correct": 0},
                  "BORDERLINE": {"total": 0, "correct": 0}}
    
    for i, item in enumerate(sample):
        pred, elapsed, classification, facts, evidence, verification = solve_multiagent(item['claim'])
        correct = pred == item['label']
        if correct:
            multi_correct += 1
        classified[classification]["total"] += 1
        if correct:
            classified[classification]["correct"] += 1
        
        mark = "✅" if correct else "❌"
        print(f"{mark} [{i+1}/{len(sample)}] cls={classification[:4]} gold={item['label']} pred={pred} | {item['claim'][:60]}...", flush=True)
        
        results.append({
            "id": item['id'],
            "claim": item['claim'][:150],
            "gold": item['label'],
            "pred": pred,
            "correct": correct,
            "classification": classification,
            "time_sec": round(elapsed, 1),
        })
    
    # Summary
    print(f"\n{'='*60}", flush=True)
    print(f"📊 FEVER RESULTS", flush=True)
    print(f"   Model: deepseek-chat (multi-agent)", flush=True)
    print(f"   Tasks: {len(results)}", flush=True)
    print(f"", flush=True)
    print(f"   Baseline (plain LLM):     {baseline_correct}/{len(sample)} = {baseline_correct/len(sample)*100:.1f}%", flush=True)
    print(f"   Multi-Agent + Verifier:   {multi_correct}/{len(sample)} = {multi_correct/len(sample)*100:.1f}%", flush=True)
    if len(sample) > 0:
        print(f"   Delta:                     {'+' if multi_correct > baseline_correct else ''}{multi_correct - baseline_correct}", flush=True)
    
    print(f"\n   By classification:", flush=True)
    for cls, data in classified.items():
        if data['total'] > 0:
            acc = data['correct'] / data['total'] * 100
            print(f"     {cls}: {data['correct']}/{data['total']} = {acc:.1f}%", flush=True)
    
    os.makedirs("/home/user1/.openclaw/workspace/benchmark_results", exist_ok=True)
    path = f"/home/user1/.openclaw/workspace/benchmark_results/fever_multiagent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, 'w') as f:
        json.dump({
            "date": datetime.now().isoformat(),
            "model": "deepseek-chat (multi-agent: Router→Collector→Solver→Verifier)",
            "sample_size": len(results),
            "baseline_accuracy": round(baseline_correct/len(sample)*100, 1),
            "multiagent_accuracy": round(multi_correct/len(sample)*100, 1),
            "by_classification": {k: f"{v['correct']}/{v['total']}={round(v['correct']/v['total']*100,1) if v['total']>0 else 0}%" for k,v in classified.items()},
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved: {path}", flush=True)

if __name__ == "__main__":
    main()
