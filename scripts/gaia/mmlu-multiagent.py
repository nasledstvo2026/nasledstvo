#!/usr/bin/env python3
"""
MMLU Multi-Agent Runner.
Router → Fact Collector → Solver

Для MMLU multi-agent: модель не просто отвечает из знания, а имеет
возможность проверить факты перед ответом.
"""

import sys, os, json, re, time, argparse, requests, urllib.parse, random
from datetime import datetime

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
WIKI_UA = "Mozilla/5.0 (compatible; MMLU-Benchmark/1.0)"

def llm(prompt, system="", max_tokens=300, temp=0.0, timeout=30):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    for a in range(3):
        try:
            auth_header = ("Bearer " + DEEPSEEK_API_KEY).encode('ascii', 'ignore').decode('ascii')
    r = requests.post(DEEPSEEK_URL,
                headers={"Authorization": auth_header},
                json={"model": "deepseek-chat",
                      "messages": msgs,
                      "max_tokens": max_tokens,
                      "temperature": temp},
                timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"  ⚠️ LLM: {e}", flush=True)
        time.sleep(2)
    return ""

ROUTER_SYSTEM = """You are an MMLU Router. Classify a question by subject and determine if fact-checking is needed.

Return:
SUBJECT: [subject category]
NEEDS_FACT_CHECK: [YES/NO]
FACT_CHECK_QUERY: [search query if needed, or NONE]
CONFIDENCE: [HIGH/MEDIUM/LOW]"""

COLLECTOR_SYSTEM = """You are a Fact Collector. From search results, extract relevant information to answer the question.

Return:
FACTS:
• [key facts]
ANSWER_CLUES: [specific clues that point to an answer]"""

SOLVER_SYSTEM = """You are an MMLU Solver. Answer a multiple-choice question using facts and reasoning.

Rules:
1. Use provided facts if available, otherwise use your knowledge
2. Provide ONLY the letter and the answer text
3. Be precise — MMLU covers many subjects

Format:
A. [choice text]
B. [choice text]
C. [choice text]
D. [choice text]

Answer: [letter]. [text]"""

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
            return f"Title: {d.get('title','')}\nExtract: {d.get('extract','')[:3000]}"
    except:
        pass
    return ""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=100, help="Number of tasks")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    with open("/home/user1/.openclaw/workspace/mmlu_results.json") as f:
        data = json.load(f)
    
    results_list = list(data['results'].values())
    random.seed(args.seed)
    random.shuffle(results_list)
    sample = results_list[:args.tasks]
    
    print(f"🔬 MMLU Multi-Agent Benchmark", flush=True)
    print(f"   Model: deepseek-chat (Router→Collector→Solver)", flush=True)
    print(f"   Tasks: {len(sample)}", flush=True)
    
    new_results = []
    old_correct = 0
    multi_correct = 0
    
    for i, item in enumerate(sample):
        q = item['q']
        choices = item.get('choices', {})
        subject = item.get('subject', 'unknown')
        correct_answer = item.get('correct')
        old_ok = item.get('ok', False)
        
        # Show choices nicely
        choices_text = "\n".join([f"{l.upper()}. {t}" for l, t in choices.items()]) if choices else ""
        q_full = f"Subject: {subject}\nQuestion: {q}\n\nChoices:\n{choices_text}"
        
        old_correct += 1 if old_ok else 0
        
        # Router
        route = llm(q_full, system=ROUTER_SYSTEM, max_tokens=200, temp=0.0)
        
        sq = ""
        m = re.search(r'FACT_CHECK_QUERY:\s*(.+?)(?:\n|$)', route)
        if m:
            s = m.group(1).strip()
            if s.upper() not in ("NONE", ""):
                sq = s
        
        # Collect facts if needed
        facts = ""
        if sq:
            titles = wiki_search(sq)
            for t in titles[:2]:
                s = wiki_read(t)
                if s:
                    facts += f"\n\n[Wikipedia: {t}]\n{s[:2000]}"
        
        if facts:
            # LLM collector
            collected = llm(f"Question: {q}\n\nRaw data:\n{facts[:6000]}",
                           system=COLLECTOR_SYSTEM, max_tokens=300, temp=0.0)
            q_full += f"\n\nFACTS:\n{collected}"
        else:
            q_full += "\n\nFACTS: (none — answer from knowledge)"
        
        # Solve
        answer = llm(q_full, system=SOLVER_SYSTEM, max_tokens=200, temp=0.0)
        
        # Extract letter
        letter_match = re.search(r'Answer:\s*([A-D])', answer)
        model_letter = letter_match.group(1) if letter_match else ""
        correct_bool = model_letter.upper() == correct_answer.upper() if model_letter and correct_answer else False
        
        multi_correct += 1 if correct_bool else 0
        
        mark = "✅" if correct_bool else "❌"
        print(f"{mark} [{i+1}/{len(sample)}] {subject[:20]:20s} | {q[:60]}... | letter: {model_letter or '?'} (gold: {correct_answer})", flush=True)
        
        new_results.append({
            "question": q[:150],
            "subject": subject,
            "choices": choices,
            "correct_answer": correct_answer,
            "model_answer": answer[:100],
            "model_letter": model_letter,
            "correct": correct_bool,
            "old_correct": old_ok,
        })
    
    # Stats by subject
    by_subject = {}
    for r in new_results:
        s = r['subject']
        if s not in by_subject:
            by_subject[s] = {'total': 0, 'correct': 0, 'old_correct': 0}
        by_subject[s]['total'] += 1
        by_subject[s]['correct'] += 1 if r['correct'] else 0
        by_subject[s]['old_correct'] += 1 if r['old_correct'] else 0
    
    print(f"\n{'='*60}", flush=True)
    print(f"📊 MMLU MULTI-AGENT RESULTS", flush=True)
    print(f"   Sample: {len(new_results)}/{data['total']} questions, {len(by_subject)} subjects", flush=True)
    print(f"", flush=True)
    print(f"   Baseline (plain): {old_correct}/{len(new_results)} = {old_correct/len(new_results)*100:.1f}%", flush=True)
    print(f"   Multi-Agent:      {multi_correct}/{len(new_results)} = {multi_correct/len(new_results)*100:.1f}%", flush=True)
    print(f"   Delta:            {'+' if multi_correct > old_correct else ''}{multi_correct - old_correct} pts", flush=True)
    
    print(f"\n📋 Per-subject breakdown:", flush=True)
    for s, stats in sorted(by_subject.items(), key=lambda x: x[1]['correct']/x[1]['total']):
        old_acc = stats['old_correct']/stats['total']*100
        new_acc = stats['correct']/stats['total']*100
        delta = new_acc - old_acc
        d_mark = "▲" if delta > 0 else "▼" if delta < 0 else "―"
        print(f"  {s:30s} | old: {old_acc:5.1f}% | new: {new_acc:5.1f}% | {d_mark} {delta:+.1f}%", flush=True)
    
    out = {
        "date": datetime.now().isoformat(),
        "model": "deepseek-chat (multi-agent: Router→Collector→Solver)",
        "sample_size": len(new_results),
        "total": data['total'],
        "baseline_sample_accuracy": round(old_correct/len(new_results)*100, 1),
        "multiagent_sample_accuracy": round(multi_correct/len(new_results)*100, 1),
        "improvement": round(multi_correct/len(new_results)*100 - old_correct/len(new_results)*100, 1),
        "per_subject": {s: {"total": st['total'], "old_acc": round(st['old_correct']/st['total']*100,1),
                            "new_acc": round(st['correct']/st['total']*100,1)} for s, st in by_subject.items()},
        "results": new_results,
    }
    
    os.makedirs("/home/user1/.openclaw/workspace/benchmark_results", exist_ok=True)
    path = f"/home/user1/.openclaw/workspace/benchmark_results/mmlu_multiagent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved: {path}", flush=True)

if __name__ == "__main__":
    main()
