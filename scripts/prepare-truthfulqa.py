"""
TruthfulQA benchmark — prepare questions for DeepSeek Chat.
Simple approach: ask model each question, score answers.
"""
import json, os, random, pandas as pd

df = pd.read_parquet("/tmp/truthfulqa_mc.parquet")
print(f"Loaded {len(df)} questions")
print(f"Columns: {list(df.columns)}")
print(df.iloc[0].to_dict())

questions = []
for i, row in df.iterrows():
    q = str(row["question"])
    choices = row["mc1_targets"]["choices"]
    labels = row["mc1_targets"]["labels"]
    labels_list = labels.tolist() if hasattr(labels, 'tolist') else list(labels)
    correct_idx = labels_list.index(1)
    correct = str(choices[correct_idx])
    choices_list = [str(c) for c in choices]
    
    questions.append({
        "qid": int(i),
        "question": q,
        "choices": choices_list,
        "correct_idx": int(correct_idx),
        "correct": correct
    })

with open("/tmp/truthfulqa_questions.json", "w") as f:
    json.dump(questions, f, ensure_ascii=False, indent=2)

# Save a smaller sample (50) for quick test
random.seed(42)
import random
sample = random.sample(questions, min(50, len(questions)))
with open("/tmp/truthfulqa_questions_50.json", "w") as f:
    json.dump(sample, f, ensure_ascii=False, indent=2)

print(f"Saved {len(questions)} questions, {len(sample)} sample")
print(f"First question: {questions[0]['question'][:80]}")
print(f"Choices: {questions[0]['choices'][:4]}...")
print(f"Correct: {questions[0]['correct']}")
