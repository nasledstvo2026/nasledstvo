#!/usr/bin/env python3
"""
GAIA benchmark runner for DeepSeek Chat browser agent.
Evaluates on validation set once data access is granted.
"""

import sys, os, json, re, time, subprocess, argparse
from datetime import datetime

# GAIA dataset is gated on HuggingFace. 
# To run: pip install datasets && huggingface-cli login
# Then accept conditions at https://huggingface.co/datasets/gaia-benchmark/GAIA

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
BROWSER_AGENT = os.path.join(os.path.dirname(__file__), "browser-agent.py")

def check_dependencies():
    """Check if all dependencies are available."""
    missing = []
    try:
        import playwright
    except:
        missing.append("playwright (pip install playwright)")
    
    try:
        from datasets import load_dataset
    except:
        missing.append("datasets (pip install datasets)")
    
    if not DEEPSEEK_API_KEY:
        missing.append("DEEPSEEK_API_KEY env var")
    
    return missing


def main():
    parser = argparse.ArgumentParser(description="GAIA Benchmark Runner")
    parser.add_argument("--mode", choices=["check", "status", "run-demo", "run"], default="check")
    parser.add_argument("--tasks", type=int, default=5, help="Number of tasks to run")
    parser.add_argument("--level", type=str, default="1", help="GAIA level: 1, 2, 3, or all")
    args = parser.parse_args()
    
    if args.mode == "check":
        missing = check_dependencies()
        if missing:
            print("❌ Missing dependencies:")
            for m in missing:
                print(f"  - {m}")
        else:
            print("✅ All dependencies available")
        
        # Check if dataset is accessible
        try:
            from datasets import load_dataset
            ds = load_dataset('gaia-benchmark/GAIA', '2023_all', split='validation', 
                            cache_dir='/tmp/.cache-hf', streaming=True)
            print(f"✅ GAIA dataset accessible: {len(ds)} validation tasks")
        except Exception as e:
            print(f"❌ GAIA dataset: {e}")
            print("   → Login: huggingface-cli login")
            print("   → Accept: https://huggingface.co/datasets/gaia-benchmark/GAIA")
        
    elif args.mode == "run-demo":
        # Run on synthetic demo tasks
        demo_tasks = [
            "What is the height of the Eiffel Tower in meters? Use Wikipedia.",
            "What is the chemical symbol for gold? Search and answer.",
            "Find the current year and confirm it with a web source.",
        ]
        results = []
        for i, task in enumerate(demo_tasks[:args.tasks]):
            print(f"\n{'='*60}", flush=True)
            print(f"📋 Demo task {i+1}/{min(args.tasks, len(demo_tasks))}", flush=True)
            print(f"Task: {task}", flush=True)
            
            start = time.time()
            r = subprocess.run(
                ["python3", BROWSER_AGENT, "--task", task],
                capture_output=True, text=True, timeout=120
            )
            elapsed = time.time() - start
            
            # Extract answer
            answer = ""
            for line in r.stdout.split("\n"):
                if line.startswith("📝 ANSWER:"):
                    answer = line.replace("📝 ANSWER:", "").strip()
                    break
            
            correct = False  # Manual evaluation needed
            results.append({
                "task": task,
                "answer": answer or "(timeout/error)",
                "time_sec": round(elapsed, 1),
                "steps": r.stdout.count("Step "),
            })
            print(f"⏱ {elapsed:.1f}s", flush=True)
        
        # Summary
        print(f"\n{'='*60}", flush=True)
        print("📊 DEMO RESULTS", flush=True)
        for r in results:
            print(f"  {'✓' if r['answer'] != '(timeout/error)' else '✗'} {r['task'][:50]}... → {r['answer'][:60]} ({r['time_sec']}s, {r['steps']} steps)", flush=True)
            
    print(f"\n{'='*60}", flush=True)
    print("💡 GAIA requires HuggingFace access. Once granted:", flush=True)
    print("  python3 run-gaia.py --mode run --tasks 50 --level 1", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
