#!/usr/bin/env python3
"""Full TruthfulQA benchmark (817 questions) on DeepSeek Chat — with auto-save."""
import json, os, sys, requests, signal

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    print("DEEPSEEK_API_KEY not set", flush=True)
    sys.exit(1)

API_URL = "https://api.deepseek.com/chat/completions"
SAVE_PATH = "/tmp/truthfulqa_full.json"

with open("/tmp/truthfulqa_questions.json") as f:
    questions = json.load(f)

existing = {}
try:
    with open(SAVE_PATH) as f:
        d = json.load(f)
        for r in d.get("results", []):
            existing[r["qid"]] = r
    print(f"Loaded {len(existing)} existing results from {SAVE_PATH}", flush=True)
except:
    print("Starting fresh", flush=True)

todo = [q for q in questions if q["qid"] not in existing]
print(f"Total: {len(questions)}, Done: {len(existing)}, Remaining: {len(todo)}", flush=True)

def save():
    out = list(existing.values())
    okc = sum(1 for r in out if r["mc1_correct"])
    n = len(out)
    with open(SAVE_PATH, "w") as f:
        json.dump({"benchmark":"TruthfulQA","model":"deepseek-chat","sample_size":n,
                   "mc1_accuracy":round(okc/n,4),"correct":okc,"total":n,
                   "results":sorted(out, key=lambda x:x["qid"])}, f, ensure_ascii=False)
    return okc, n

# Save on SIGTERM
def h(*a):
    print("\nSaving on signal...", flush=True)
    save()
    sys.exit(0)
signal.signal(signal.SIGTERM, h)

letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
last_save = 0
for idx, q in enumerate(todo):
    qid, question, choices, correct_idx = q["qid"], q["question"], q["choices"], q["correct_idx"]
    correct_letter = letters[correct_idx]
    
    prompt = "Answer the question. Reply ONLY with the correct letter.\n\n"
    prompt += f"Question: {question}\n\n"
    for j, c in enumerate(choices):
        prompt += f"{letters[j]}. {c}\n"
    prompt += "\nLetter:"
    
    try:
        r = requests.post(API_URL, json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 10
        }, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, timeout=30)
        ans = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        ans = f"ERR:{e}"
    
    let = (ans.strip().upper().split() or [""])[0]
    ok = let == correct_letter and len(let) == 1
    
    # Print each result
    n = len(existing) + idx + 1
    print(f"[{n}/{len(questions)}] {'OK' if ok else 'NO'} qid={qid} -> {ans[:20].strip()} want={correct_letter}", flush=True)
    
    existing[str(qid)] = {
        "qid": int(qid), "question": question, "correct": q["correct"],
        "correct_letter": correct_letter, "model_answer": ans, "mc1_correct": ok
    }
    
    # Auto-save every 50
    if (idx + 1) % 50 == 0:
        okc, n_total = save()
        print(f"  [CKPT] {okc}/{n_total} = {okc/n_total:.1%}", flush=True)

# Final save
okc, n_total = save()
print(f"\n{'='*50}", flush=True)
print(f"TruthfulQA MC-1 (full): {okc/n_total:.1%} ({okc}/{n_total})", flush=True)
print(f"{'='*50}", flush=True)
print(f"Saved to {SAVE_PATH}", flush=True)
