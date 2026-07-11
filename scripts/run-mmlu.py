#!/usr/bin/env python3
"""Run MMLU (0-shot) on DeepSeek Chat. Stratified subset — 25 per subject."""

import sys, json, os, time, re, subprocess, random
from collections import defaultdict
from datasets import load_dataset

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

RESULTS_FILE = "/home/user1/.openclaw/workspace/mmlu_results.json"
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
    
    for attempt in range(5):
        try:
            r = subprocess.run(
                ["curl", "-s", "-w", "\n%{http_code}", 
                 "-H", f"Authorization: Bearer {DEEPSEEK_API_KEY}",
                 "-H", "Content-Type: application/json",
                 "-d", payload,
                 "-m", "45",
                 DEEPSEEK_URL],
                capture_output=True, text=True, timeout=50
            )
            parts = r.stdout.strip().rsplit("\n", 1)
            if len(parts) != 2:
                time.sleep(3)
                continue
            body, code = parts
            if code != "200":
                time.sleep(3)
                continue
            data = json.loads(body)
            answer = data["choices"][0]["message"]["content"].strip().upper()
            match = re.search(r'\b([A-D])\b', answer)
            if match:
                return match.group(1)
            if answer and answer[0] in 'ABCD':
                return answer[0]
            return None
        except Exception as e:
            time.sleep(3)
    return None


def main():
    print("Loading MMLU test set...", flush=True)
    ds = load_dataset('cais/mmlu', 'all', split='test', cache_dir='/tmp/.cache-hf')
    
    # Group by subject
    subjects = defaultdict(list)
    for item in ds:
        s = item.get("subject", "unknown")
        subjects[s].append(item)
    
    print(f"Total subjects: {len(subjects)}", flush=True)
    for s, items in sorted(subjects.items()):
        print(f"  {s}: {len(items)} questions", flush=True)
    
    # Stratified sample: SUBSET_SIZE per subject, or all if less
    sampled = []
    for s, items in sorted(subjects.items()):
        k = min(SUBSET_SIZE, len(items))
        sampled.extend(random.sample(items, k))
    
    random.shuffle(sampled)
    total = len(sampled)
    print(f"\nSampled {total} questions ({SUBSET_SIZE}/subject)", flush=True)
    
    # Load progress
    results = {}
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            results = json.load(f)
    
    # Build index from sampled questions
    # Use question text as key for resume
    done_keys = set(results.keys())
    
    results = {}  # fresh run
    correct = 0
    total_done = 0
    
    last_request_time = time.time()
    
    for i, item in enumerate(sampled):
        question = item["question"]
        choices = [f"{chr(65+j)}. {item['choices'][j]}" for j in range(len(item['choices']))]
        correct_letter = chr(65 + item["answer"])
        
        qid = str(i)
        
        pred = query_model(question, choices)
        is_correct = pred == correct_letter if pred else False
        if is_correct:
            correct += 1
        total_done += 1
        
        results[qid] = {
            "q": question[:80],
            "subject": item.get("subject", ""),
            "correct": correct_letter,
            "pred": pred,
            "ok": is_correct,
        }
        
        now = time.time()
        elapsed = now - last_request_time
        if elapsed < 0.3:
            time.sleep(0.3 - elapsed)
        last_request_time = now
        
        if (i + 1) % 50 == 0 or i == total - 1:
            pct = round(correct / total_done * 100, 2)
            print(f"[{i+1}/{total}] correct: {correct}/{total_done} ({pct}%)", flush=True)
            # Save intermediate
            final = {
                "benchmark": "MMLU",
                "model": "deepseek-chat",
                "mode": "0-shot",
                "sample_size": total_done,
                "subjects": len(subjects),
                "per_subject": SUBSET_SIZE,
                "accuracy": round(correct / total_done * 100, 2),
                "correct": correct,
                "total": total,
                "results": results,
            }
            with open(RESULTS_FILE, "w") as f:
                json.dump(final, f, ensure_ascii=False, indent=2)
    
    pct = round(correct / total * 100, 2) if total else 0
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
    
    print(f"\n{'='*50}")
    print(f"FINAL: {correct}/{total} correct = {pct}%")
    print(f"{'='*50}", flush=True)

if __name__ == "__main__":
    main()
