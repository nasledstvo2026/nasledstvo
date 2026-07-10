"""
FEVER benchmark — test DeepSeek Chat on fact verification.
We take claims from FEVER dev set and ask the model: SUPPORTS / REFUTES / NOT ENOUGH INFO
"""
import json, os, requests, sys, random

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_KEY:
    DEEPSEEK_KEY = "sk-83e…5381"

API_URL = "https://api.deepseek.com/chat/completions"

# Load first 50 claims from FEVER dev
claims = []
with open("/tmp/fever_dev.jsonl") as f:
    for i, line in enumerate(f):
        if i >= 50:
            break
        claims.append(json.loads(line))

print(f"FEVER benchmark: loaded {len(claims)} claims")

correct = 0
total = len(claims)
results = []

label_map = {"SUPPORTS": "SUPPORTS", "REFUTES": "REFUTES", "NOT ENOUGH INFO": "NOT ENOUGH INFO"}
labels = ["SUPPORTS", "REFUTES", "NOT ENOUGH INFO"]

for idx, c in enumerate(claims):
    claim = c["claim"]
    label = c["label"]
    
    prompt = f"""Verify the following claim against known facts.
Respond with ONLY one word: SUPPORTS, REFUTES, or NOT ENOUGH INFO.

Claim: {claim}

Your verdict (SUPPORTS / REFUTES / NOT ENOUGH INFO):"""
    
    try:
        resp = requests.post(API_URL, json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 10
        }, headers={
            "Authorization": f"Bearer {DEEPSEEK_KEY}",
            "Content-Type": "application/json"
        }, timeout=30)
        
        answer = resp.json()["choices"][0]["message"]["content"].strip().upper()
    except Exception as e:
        answer = f"<ERROR: {e}>"
    
    # Normalize
    ans_clean = answer.split()[0] if answer else ""
    if ans_clean not in labels:
        # Check partial match
        for lbl in labels:
            if lbl in ans_clean:
                ans_clean = lbl
                break
    
    matched = ans_clean == label
    
    if ans_clean in labels:
        correct += 1 if matched else 0
    
    status = "✅" if matched else "❌"
    print(f"[{idx+1}/{total}] {status} {claim[:70]}...")
    print(f"    Expected: {label}, Got: {ans_clean}")
    
    results.append({
        "claim": claim,
        "expected": label,
        "got": ans_clean,
        "correct": matched
    })

acc = correct / total
print(f"\n{'='*50}")
print(f"FEVER Accuracy (sample): {acc:.1%}")
print(f"Correct: {correct}/{total}")
print(f"{'='*50}")

with open("/tmp/fever_results.json", "w") as f:
    json.dump({
        "benchmark": "FEVER",
        "model": "deepseek-chat",
        "sample_size": total,
        "accuracy": round(acc, 4),
        "correct": correct,
        "total": total,
        "results": results
    }, f, ensure_ascii=False, indent=2)

print(f"\nSaved to /tmp/fever_results.json")
