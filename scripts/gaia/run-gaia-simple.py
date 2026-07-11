#!/usr/bin/env python3
"""
GAIA benchmark runner — запускает browser-agent на задачах GAIA.
Прогон: 10 задач Level 1.
"""

import sys, os, json, re, time, subprocess, requests
from datetime import datetime

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

def llm(prompt, max_tokens=800, temp=0.0):
    payload = {"model": "deepseek-chat", "messages": [{"role":"user","content":prompt}],
               "max_tokens": max_tokens, "temperature": temp}
    for a in range(3):
        try:
            r = requests.post(DEEPSEEK_URL, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                              json=payload, timeout=60)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except:
            time.sleep(3)
    return ""

def extract_exact_answer(model_response, question):
    """Extract exact answer from model response."""
    prompt = f"""Question: {question}
    
Model's response: {model_response}

Extract the exact final answer from the response. If the response contains a clear final answer, return ONLY that answer (a number, word, short phrase). If no clear answer, return "NO_ANSWER".

Final answer:"""
    return llm(prompt, max_tokens=50, temp=0.0)

def normalize_answer(answer):
    """Normalize answer for comparison."""
    a = answer.strip().lower().rstrip('.')
    # Remove leading zeros from numbers
    if a.replace(',', '').replace('.', '').replace(' ', '').isdigit():
        try:
            return str(float(a.replace(',', '')))
        except:
            pass
    return a

def main():
    from datasets import load_dataset
    ds = load_dataset('gaia-benchmark/GAIA', '2023_all', split='validation', cache_dir='/tmp/.cache-hf')
    l1 = [t for t in ds if t['Level'] == '1'][:10]
    
    results = []
    for i, task in enumerate(l1):
        q = task['Question']
        gold = task['Final answer']
        tid = task['task_id'][:8]
        
        print(f"\n{'='*60}")
        print(f"[{i+1}/10] Task {tid} (L{task['Level']})")
        print(f"Q: {q[:150]}...")
        print(f"Gold: {gold}")
        
        # Run browser agent with timeout
        agent_script = os.path.join(os.path.dirname(__file__), "browser-agent.py")
        start = time.time()
        
        r = subprocess.run(
            ["python3", agent_script, "--task", q],
            capture_output=True, text=True, timeout=180
        )
        elapsed = time.time() - start
        output = r.stdout
        
        # Extract ANSWER line
        answer = ""
        for line in output.split("\n"):
            if line.startswith("📝 ANSWER:"):
                answer = line.replace("📝 ANSWER:", "").strip()
                break
        
        # Fallback: extract with LLM
        if not answer:
            answer = extract_exact_answer(output, q)
        
        # Compare
        norm_answer = normalize_answer(answer)
        norm_gold = normalize_answer(gold)
        correct = norm_answer == norm_gold
        
        print(f"Model: {answer[:80] or '(no answer)'}")
        print(f"⏱ {elapsed:.0f}s | {'✅' if correct else '❌'}")
        
        results.append({
            "task_id": tid,
            "question": q[:100],
            "gold": gold,
            "answer": answer,
            "correct": correct,
            "time_sec": round(elapsed, 0),
            "level": task['Level'],
        })
    
    # Summary
    correct_count = sum(1 for r in results if r['correct'])
    print(f"\n{'='*60}")
    print(f"📊 GAIA RESULTS (Level 1, {len(results)} tasks)")
    print(f"Accuracy: {correct_count}/{len(results)} = {correct_count/len(results)*100:.1f}%")
    print(f"Avg time: {sum(r['time_sec'] for r in results)/len(results):.0f}s")
    
    # Save results
    out = {
        "date": datetime.now().isoformat(),
        "model": "deepseek-chat + browser-agent",
        "total": len(results),
        "correct": correct_count,
        "accuracy": round(correct_count/len(results)*100, 1),
        "avg_time_sec": round(sum(r['time_sec'] for r in results)/len(results), 0),
        "tasks": results,
    }
    os.makedirs("/home/user1/.openclaw/workspace/gaia_results", exist_ok=True)
    path = f"/home/user1/.openclaw/workspace/gaia_results/gaia_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Saved: {path}")
    
    print(f"\n{'='*60}")
    for r in results:
        mark = "✅" if r['correct'] else "❌"
        print(f"  {mark} [{r['task_id']}] {r['answer'][:60]} (gold: {r['gold'][:40]})")


if __name__ == "__main__":
    # Install requests if needed
    try:
        import requests
    except:
        subprocess.run(["pip3", "install", "requests", "--break-system-packages", "-q"])
        import requests
    main()
