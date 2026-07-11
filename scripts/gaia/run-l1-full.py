#!/usr/bin/env python3
"""
GAIA Level 1 batch runner — параллельный прогон 53 задач.
Сохраняет результаты в JSON и выводит статистику.
"""

import sys, os, json, re, time, subprocess, concurrent.futures, threading
from datetime import datetime

def solve_one(task_data):
    tid, question, gold = task_data
    start = time.time()
    try:
        r = subprocess.run(
            ['python3', 'scripts/gaia/gaia-v4.py', '--task', question],
            capture_output=True, text=True, timeout=120
        )
        elapsed = time.time() - start
        answer = ''
        for line in r.stdout.split('\n'):
            if line.startswith('📝 ANSWER:'):
                answer = line.replace('📝 ANSWER:', '').strip()
                break
        if not answer:
            answer = '(no answer)'
        
        def norm(s):
            s = s.strip().lower().rstrip('.,;!? ')
            s = re.sub(r'[^\w\s]', '', s).strip()
            return s
        
        correct = norm(answer) == norm(gold)
        return {'task_id': tid, 'correct': correct, 'answer': answer[:80], 
                'gold': gold, 'time': round(elapsed)}
    except subprocess.TimeoutExpired:
        return {'task_id': tid, 'correct': False, 'answer': '(timeout)', 
                'gold': gold, 'time': 120}
    except Exception as e:
        return {'task_id': tid, 'correct': False, 'answer': str(e)[:50], 
                'gold': gold, 'time': 0}

def main():
    from datasets import load_dataset
    ds = load_dataset('gaia-benchmark/GAIA', '2023_all', split='validation', cache_dir='/tmp/.cache-hf')
    l1 = [t for t in ds if t['Level'] == '1']
    
    print(f'GAIA Level 1: {len(l1)} tasks', flush=True)
    print(f'Running with 4 parallel workers...', flush=True)
    
    tasks = [(t['task_id'][:8], t['Question'], t['Final answer']) for t in l1]
    
    results = []
    lock = threading.Lock()
    done = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(solve_one, t): t[0] for t in tasks}
        for f in concurrent.futures.as_completed(futures):
            tid = futures[f]
            try:
                r = f.result()
                with lock:
                    results.append(r)
                    done += 1
                print(f'  [{done}/{len(tasks)}] {tid}: {"✅" if r["correct"] else "❌"} {r["answer"][:50]} / {r["gold"][:50]} ({r["time"]}s)', flush=True)
            except Exception as e:
                print(f'  [!] {tid}: {e}', flush=True)
    
    correct = sum(1 for r in results if r['correct'])
    total = len(results)
    accuracy = correct / total * 100 if total else 0
    avg_time = sum(r['time'] for r in results) / total if total else 0
    
    print(f'\n{"="*60}', flush=True)
    print(f'📊 GAIA Level 1 Results', flush=True)
    print(f'Model: deepseek-chat + structured agent v4', flush=True)
    print(f'Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}', flush=True)
    print(f'Accuracy: {correct}/{total} = {accuracy:.1f}%', flush=True)
    print(f'Avg time: {avg_time:.0f}s', flush=True)
    
    # Сравнение с SOTA
    print(f'\nReference: GPT-4 ~30-35%, GPT-4o ~40%, Claude 3.5 ~35%, SOTA ~45%', flush=True)
    
    # Сохранить
    out = {
        'date': datetime.now().isoformat(),
        'model': 'deepseek-chat + v4',
        'total': total,
        'correct': correct,
        'accuracy': round(accuracy, 1),
        'avg_time_s': round(avg_time),
        'results': sorted(results, key=lambda x: x['task_id']),
    }
    
    os.makedirs('/home/user1/.openclaw/workspace/gaia_results', exist_ok=True)
    path = f'/home/user1/.openclaw/workspace/gaia_results/gaia_l1_full.json'
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\nSaved: {path}', flush=True)
    
    # Вывести все результаты
    print(f'\nAll results:', flush=True)
    for r in sorted(results, key=lambda x: x['task_id']):
        print(f'  {"✅" if r["correct"] else "❌"} [{r["task_id"]}] {r["answer"][:50]} | gold: {r["gold"][:40]}', flush=True)

if __name__ == '__main__':
    main()
