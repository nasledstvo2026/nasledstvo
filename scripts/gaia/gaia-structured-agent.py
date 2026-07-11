#!/usr/bin/env python3
"""
Structured GAIA Agent v3.
Architecture: Router → Tool Executor → Answer Verifier.

Tools:
1. Wikipedia fact retriever (via API, not browser)
2. Web search (via Google HTML + extract)
3. Math solver (via llm + calculator)
4. PDF reader (via PyMuPDF/text extraction)
5. YouTube metadata (via yt-dlp metadata)
6. LLM-only (for riddles, logic)
7. URL reader (via readability-mode extraction)

Strategy:
- Router LLM classifies task → picks tool(s)
- Each tool returns structured data
- Answer LLM synthesizes final answer
"""

import sys, os, json, re, time, argparse, subprocess, requests, urllib.parse, textwrap
from datetime import datetime
from io import BytesIO

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# ── LLM helper ────────────────────────────────────────────────────

def llm(prompt, max_tokens=500, temp=0.0, system=""):
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    for a in range(3):
        try:
            r = requests.post(DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={"model": "deepseek-chat", "messages": msgs,
                      "max_tokens": max_tokens, "temperature": temp},
                timeout=60)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except:
            time.sleep(2)
    return ""

# ── Tool 1: Wikipedia API ─────────────────────────────────────────

def wikipedia_search(query, top_n=3):
    """Search Wikipedia via API."""
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": top_n
        }, timeout=10)
        results = r.json().get("query", {}).get("search", [])
        return [{"title": s["title"], "snippet": s.get("snippet","")} for s in results]
    except:
        return []

def wikipedia_summary(title):
    """Get Wikipedia page summary via API."""
    try:
        r = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/" + 
                        urllib.parse.quote(title.replace(" ", "_")), timeout=10)
        if r.status_code == 200:
            d = r.json()
            return d.get("extract", "")
        return ""
    except:
        return ""

def wikipedia_section_text(title, section=None):
    """Get full text of a Wikipedia page."""
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "parse", "page": title, "prop": "text",
            "format": "json", "section": section or 0
        }, timeout=10)
        data = r.json()
        text = data.get("parse", {}).get("text", {}).get("*", "")
        # Strip HTML
        import html
        from bs4 import BeautifulSoup
        # simple regex-based cleanup
        text = re.sub(r'<[^>]+>', ' ', text)
        text = ' '.join(text.split())
        return text[:8000]
    except:
        return ""

def wikidata_extract(title):
    """Get structured data from Wikidata via Wikipedia."""
    try:
        # Get page ID
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "titles": title, "prop": "pageprops",
            "format": "json"
        }, timeout=10)
        pages = r.json().get("query", {}).get("pages", {})
        for pid, info in pages.items():
            if "pageprops" in info:
                wd_id = info["pageprops"].get("wikibase_item", "")
                if wd_id:
                    # Get Wikidata entity
                    r2 = requests.get(f"https://www.wikidata.org/wiki/Special:EntityData/{wd_id}.json", timeout=10)
                    if r2.status_code == 200:
                        return r2.json()
        return {}
    except:
        return {}

# ── Tool 2: Web Search ─────────────────────────────────────────────

def web_search(query, top_n=3):
    """Search Google via HTML scraping (no API key needed)."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://www.google.com/search", 
                        params={"q": query, "num": top_n},
                        headers=headers, timeout=15)
        if r.status_code == 200:
            # Extract search results
            results = []
            # Try to find result blocks
            text = r.text
            # Find URLs and snippets
            for m in re.finditer(r'<a[^>]*href="(/url\?q=[^"]+)"[^>]*>(.*?)</a>', text):
                href = m.group(1)
                title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                if href.startswith("/url?q="):
                    url = urllib.parse.parse_qs(href[7:].split("&")[0]).get("", [""])[0]
                    results.append({"url": url, "title": title})
            return results[:top_n]
        return [{"url": "", "title": "Search failed"}]
    except:
        return [{"url": "", "title": "Search error"}]

def fetch_url(url, max_chars=10000):
    """Fetch and extract text from a URL."""
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, 
                        timeout=15)
        if r.status_code == 200:
            text = r.text
            # Remove scripts, styles
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = ' '.join(text.split())
            return text[:max_chars]
        return ""
    except:
        return ""

# ── Tool 3: Math / Calculator ──────────────────────────────────────

def math_solve(problem):
    """Solve math problems using LLM reasoning."""
    prompt = f"""Solve this problem step by step and return ONLY the final numeric answer.

Problem: {problem}

Show your work step by step, then on the last line write: FINAL_ANSWER: [number]

Do NOT add any text after the final answer line."""
    
    result = llm(prompt, max_tokens=500, temp=0.0)
    
    # Extract final answer
    m = re.search(r'FINAL_ANSWER:\s*([\d.,\-\s]+)', result)
    if m:
        return m.group(1).strip()
    
    # Fallback: try python eval for simple expressions
    try:
        return str(eval(problem.strip(), {"__builtins__": {}}, {"abs": abs, "round": round, "min": min, "max": max, "pow": pow, "sum": sum}))
    except:
        pass
    
    return result

# ── Tool 4: PDF/document reader ────────────────────────────────────

def read_pdf_or_doc(file_path, max_chars=10000):
    """Extract text from PDF or document file."""
    text = ""
    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:20]:
                text += page.extract_text() + "\n"
    except:
        pass
    
    if not text:
        try:
            import pdfminer
            from pdfminer.high_level import extract_text as pdfminer_extract
            text = pdfminer_extract(file_path)
        except:
            pass
    
    if not text:
        try:
            result = subprocess.run(["pdftotext", file_path, "-"], 
                                  capture_output=True, text=True, timeout=10)
            text = result.stdout
        except:
            pass
    
    return text[:max_chars]

# ── Tool 5: YouTube metadata ───────────────────────────────────────

def youtube_info(url):
    """Get YouTube video metadata via yt-dlp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--print", "%(title)s\n%(description)s\n%(duration)s\n%(view_count)s", url],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout.strip()[:5000]
    except:
        return ""

# ── Router: classify task → plan tools ─────────────────────────────

def router(task, file_path=None):
    """Classify the GAIA task and return a tool plan."""
    has_file = file_path and os.path.exists(file_path)
    ext = os.path.splitext(file_path)[1].lower() if file_path else ""
    
    prompt = f"""Classify this GAIA benchmark task and create a tool execution plan.

Task: {task}
Has attachment: {"yes (" + ext + ")" if has_file else "no"}

TOOLS AVAILABLE:
1. wikipedia — search and read Wikipedia articles (API-based, no browser)
2. web_search — Google search and read web pages
3. math — solve math/calculation problems
4. pdf_reader — extract text from PDF files (use if attachment is PDF)
5. youtube — get YouTube video metadata (use if task involves YouTube)
6. llm_only — answer from model knowledge (for riddles, logic puzzles)
7. fetch_url — read a specific URL

Respond with EXACTLY:
CLASS: [wikipedia|web_search|math|pdf_reader|youtube|llm_only|hybrid]
TOOLS: [comma-separated list of tool names in order]
PLAN: brief 1-sentence plan"""
    
    result = llm(prompt, max_tokens=300, temp=0.0)
    
    cls = "hybrid"
    if "CLASS: wikipedia" in result.lower():
        cls = "wikipedia"
    elif "CLASS: web_search" in result.lower():
        cls = "web_search"
    elif "CLASS: math" in result.lower():
        cls = "math"
    elif "CLASS: pdf_reader" in result.lower():
        cls = "pdf_reader"
    elif "CLASS: youtube" in result.lower():
        cls = "youtube"
    elif "CLASS: llm_only" in result.lower():
        cls = "llm_only"
    elif "CLASS: hybrid" in result.lower():
        cls = "hybrid"
    
    return cls

# ── Solver: orchestrate tools ──────────────────────────────────────

def solve_gaia(task, file_path=None):
    """Solve a GAIA task using structured tools."""
    start = time.time()
    
    # Step 1: Route
    cls = router(task, file_path)
    print(f"  📊 Type: {cls}", flush=True)
    
    # Step 2: Execute tools
    data = []
    
    if cls == "wikipedia":
        # Search Wikipedia
        searches = wikipedia_search(task)
        if searches:
            for s in searches[:2]:
                summary = wikipedia_summary(s["title"])
                data.append(f"[Wikipedia: {s['title']}]\n{summary[:2000]}")
        else:
            # Try direct topic extraction
            prompt = f"Extract the main entity/topic from this question. Return ONLY the name: {task}"
            topic = llm(prompt, max_tokens=50, temp=0.0)
            summary = wikipedia_summary(topic)
            if summary:
                data.append(f"[Wikipedia: {topic}]\n{summary[:3000]}")
    
    elif cls == "web_search":
        results = web_search(task)
        for r in results[:3]:
            url = r.get("url", "")
            title = r.get("title", "")
            content = fetch_url(url) if url else ""
            data.append(f"[{title}]({url})\n{content[:2000]}")
    
    elif cls == "math":
        result = math_solve(task)
        data.append(f"[Math result]\n{result}")
    
    elif cls == "pdf_reader" and file_path:
        text = read_pdf_or_doc(file_path)
        data.append(f"[PDF content]\n{text[:5000]}")
    
    elif cls == "youtube":
        # Extract URL from task
        urls = re.findall(r'https?://(?:www\.)?(?:youtube\.com|youtu\.be)\S+', task)
        if urls:
            info = youtube_info(urls[0])
            data.append(f"[YouTube]\n{info[:3000]}")
    
    elif cls == "llm_only":
        pass  # Will use LLM directly
    
    elif cls == "hybrid":
        # Try web search + wikipedia
        results = web_search(task)
        for r in results[:2]:
            url = r.get("url", "")
            title = r.get("title", "")
            content = fetch_url(url) if url else ""
            data.append(f"[{title}]\n{content[:2000]}")
        # Also try Wikipedia
        searches = wikipedia_search(task)
        if searches:
            summary = wikipedia_summary(searches[0]["title"])
            if summary:
                data.append(f"[Wikipedia: {searches[0]['title']}]\n{summary[:2000]}")
    
    # Step 3: Synthesize answer using LLM
    context = "\n\n---\n\n".join(data) if data else "(no web data available)"
    
    answer_prompt = f"""You are solving a GAIA benchmark task. Use the provided data and your knowledge to answer.

TASK: {task}

CONTEXT FROM TOOLS:
{context[:8000]}

Instructions:
1. If the data contains the exact answer, extract it
2. If calculation is needed, compute step by step
3. If the data is insufficient, reason from general knowledge
4. Return ONLY the final answer — a number, word, or short phrase
5. Be precise — gold answers are specific

FINAL ANSWER:"""
    
    answer = llm(answer_prompt, max_tokens=100, temp=0.0)
    
    elapsed = time.time() - start
    print(f"  ⏱ {elapsed:.1f}s", flush=True)
    
    return answer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, required=True)
    parser.add_argument("--file", type=str)
    args = parser.parse_args()
    
    print(f"🤖 Structured GAIA Agent v3 starting...", flush=True)
    print(f"📋 {args.task[:150]}", flush=True)
    
    answer = solve_gaia(args.task, args.file)
    
    print(f"\n{'='*60}", flush=True)
    print(f"📝 ANSWER: {answer}", flush=True)


if __name__ == "__main__":
    main()
