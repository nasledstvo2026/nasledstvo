#!/usr/bin/env python3
"""Run MMLU (0-shot) on DeepSeek Chat with parallel workers."""

import sys, json, os, time, re, subprocess, random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datasets import load_dataset

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
RESULTS_FILE = "/home/user1/.openclaw/workspace/mmlu_results.json"
WORKERS = 5  # parallel requests
SUBSET_SIZE = 10  # per subject

def query_model(question, choices):
    prompt = f"""Answer the following multiple-choice question. Respond with ONLY the letter of the correct answer (A, B, C, or D). Do not explain.

Question: {question}

{chr(10).join(choices)}"""
    
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 10,
        "temperature": 0.0,
    })
    
    for attempt in range(3):
        try:
            r = subprocess.run(
                ["curl", "-s", "-w", "\n%{http_code}", 
                 "-H", f"Authorization: Bearer {DEEPSEEK_API_KEY}",
                 "-H", "Content-Type: application/json",
                 "-d", payload,
                 "-m", "30",
                 DEEPSEEK_URL],
                capture_output=True, text=True, timeout=35
            )
            parts = r.stdout.strip().rsplit("\n", 1)
            if len(parts) != 2:
                time.sleep(1)
                continue
            body, code = parts
            if code != "200":
                time.sleep(1)
                continue
            data = json.loads(body)
            answer = data["choices"][0]["message"]["content"].strip().upper()
            import re
            match = re.search(r'\b([A-D])\b', answer)
            if match:
                return match.group(1)
            if answer and answer[0] in 'ABCD':
                return answer[0]
            return None
        except:
            time.sleep(2)
    return None

def process_one(item):
    question = item["question"]
    choices = [f"{chr(65+j)}. {item['choices'][j]}" for j in range(len(item['choices']))]
    correct_letter = chr(65 + item["answer"])
    pred = query_model(question, choices)
    return {
        "q": question[:80],
        "subject": item.get("subject", ""),
        "correct": correct_letter,
        "pred": pred,
        "ok": (pred == correct_letter if pred else False),
    }

def main():
    print("Loading MMLU test set...", flush=True)
    ds = load_dataset('cais/mmlu', 'all', split='test', cache_dir='/tmp/.cache-hf')
    
    subjects = defaultdict(list)
    for item in ds:
        subjects[item.get("subject", "unknown")].append(item)
    
    print(f"Total subjects: {len(subjects)}", flush=True)
    
    sampled = []
    for s, items in sorted(subjects.items()):
        k = min(SUBSET_SIZE, len(items))
        sampled.extend(random.sample(items, k))
    
    random.shuffle(sampled)
    total = len(sampled)
    print(f"Sampled {total} questions ({SUBSET_SIZE}/subject), workers={WORKERS}", flush=True)
    
    results = {}
    correct = 0
    done = 0
    
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        fut_map = {ex.submit(process_one, item): i for i, item in enumerate(sampled)}
        for fut in as_completed(fut_map):
            i = fut_map[fut]
            try:
                res = fut.result(timeout=40)
            except Exception as e:
                res = {"q": sampled[i]["question"][:80], "subject": sampled[i].get("subject",""), "correct": chr(65+sampled[i]["answer"]), "pred": None, "ok": False}
            results[str(i)] = res
            if res.get("ok"):
                correct += 1
            done += 1
            
            if done % 50 == 0:
                pct = round(correct / done * 100, 2)
                print(f"[{done}/{total}] correct: {correct}/{done} ({pct}%)", flush=True)
                # Save checkpoint
                final = {
                    "benchmark": "MMLU",
                    "model": "deepseek-chat",
                    "mode": "0-shot",
                    "sample_size": done,
                    "subjects": len(subjects),
                    "per_subject": SUBSET_SIZE,
                    "accuracy": round(correct / done * 100, 2),
                    "correct": correct,
                    "total": total,
                    "results": results,
                }
                with open(RESULTS_FILE, "w") as f:
                    json.dump(final, f, ensure_ascii=False, indent=2)
    
    pct = round(correct / total * 100, 2)
    final = {
        "benchmark": "MMLU",
        "model": "deepseek-chat",
        "mode": "0-shot",
        "sample_size": total,
        "subjects": len(subjects),
        "per_subject": SUBSET_SIZE,
        "accuracy": pct,
        "correct": correct,
        "total": total,
        "results": results,
    }
    with open(RESULTS_FILE, "w") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}", flush=True)
    print(f"FINAL: {correct}/{total} correct = {pct}%", flush=True)
    print(f"{'='*50}", flush=True)

if __name__ == "__main__":
    main()
