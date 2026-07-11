#!/usr/bin/env python3
"""
GAIA Structured Agent v4 — пошаговый pipeline.
1. Извлекает ключевые факты через API (Wikipedia, Google, URL)
2. Подставляет факты в LLM для получения ответа
3. Верифицирует ответ

Ключевое улучшение: факты ИЗВЛЕКАЮТСЯ ДО ответа.
"""

import sys, os, json, re, time, argparse, requests, urllib.parse, subprocess
from datetime import datetime

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

WIKI_UA = "Mozilla/5.0 (compatible; GAIA-Benchmark/1.0)"

def llm(prompt, max_tokens=500, temp=0.0):
    for a in range(3):
        try:
            r = requests.post(DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={"model": "deepseek-chat",
                      "messages": [{"role": "user", "content": prompt}],
                      "max_tokens": max_tokens, "temperature": temp},
                timeout=60)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
        except:
            time.sleep(2)
    return ""

# ── Tool: Wikipedia search + read ──────────────────────────────────

def wiki_search(query):
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": 5
        }, timeout=10, headers={"User-Agent": WIKI_UA})
        return [s["title"] for s in r.json().get("query",{}).get("search",[])]
    except:
        return []

def wiki_read(title):
    try:
        r = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title.replace(' ','_'))}",
                         timeout=10, headers={"User-Agent": WIKI_UA})
        if r.status_code == 200:
            d = r.json()
            return f"Title: {d.get('title','')}\nExtract: {d.get('extract','')[:5000]}"
    except:
        pass
    return ""

def wiki_extract_tables(title, section_title):
    """Get section content from Wikipedia."""
    r = requests.get("https://en.wikipedia.org/w/api.php", params={
        "action": "parse", "page": title, "prop": "text",
        "section": "", "format": "json"
    }, timeout=10, headers={"User-Agent": WIKI_UA})
    try:
        html = r.json()["parse"]["text"]["*"]
        # Simple extraction
        text = re.sub(r'<[^>]+>', '\n', html)
        text = '\n'.join(l for l in text.split('\n') if l.strip())
        return text[:8000]
    except:
        return ""

# ── Tool: Google search ────────────────────────────────────────────

def google_search(query):
    try:
        r = requests.get("https://www.google.com/search", 
            params={"q": query, "num": 5},
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
            timeout=15)
        # Extract result urls
        urls = []
        for m in re.finditer(r'href="(/url\?q=[^"]+)"', r.text):
            url = urllib.parse.parse_qs(urllib.parse.urlparse(m.group(1)).query).get("q", [None])[0]
            if url and url.startswith("http"):
                urls.append(url)
        return urls[:5]
    except:
        return []

def read_url(url):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        text = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = ' '.join(text.split())
        return text[:10000]
    except:
        return ""

# ── Tool: YouTube ──────────────────────────────────────────────────

def youtube_caption(url):
    """Get YouTube captions via yt-dlp."""
    try:
        r = subprocess.run(["yt-dlp", "--print", "title", "--print", "description", 
                           "--skip-download", url],
                          capture_output=True, text=True, timeout=30)
        return r.stdout[:5000]
    except:
        return ""

# ── Tool: PDF ──────────────────────────────────────────────────────

def extract_pdf(path):
    """Extract text from PDF file."""
    text = ""
    try:
        r = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True, timeout=15)
        text = r.stdout[:10000]
    except:
        pass
    if not text:
        try:
            r = subprocess.run(["python3", "-c", f"""
import PyPDF2; 
f=open('{path}','rb');
r=PyPDF2.PdfReader(f);
print(' '.join(p.extract_text() for p in r.pages[:15]))
"""], capture_output=True, text=True, timeout=15)
            text = r.stdout[:10000]
        except:
            pass
    return text

# ── Main solver ────────────────────────────────────────────────────

def solve(task, file_path=None):
    start = time.time()
    has_file = file_path and os.path.exists(file_path)
    ext = os.path.splitext(file_path)[1] if file_path else ""
    
    # Step 1: Extract entities and questions from task
    analysis_prompt = f"""Analyze this GAIA task and return the key facts to look up.

Task: {task}

Return:
1. WIKI_TOPICS: [comma-separated Wikipedia article names to search, EXACT titles]
2. SEARCH_QUERIES: [comma-separated Google search queries to find data]
3. NUMERIC: [YES if the answer is a number, NO if text]
4. YOUTUBE_URL: [YouTube URL if present, or NONE]
5. MATH_FORMULA: [YES if calculation needed, NO if fact lookup]"""
    
    analysis = llm(analysis_prompt, max_tokens=300, temp=0.0)
    
    # Parse analysis
    wiki_topics = []
    search_queries = []
    youtube_url = ""
    is_numeric = "NUMERIC: YES" in analysis or "NUMERIC: Yes" in analysis or "NUMERIC: yes" in analysis
    needs_math = "MATH_FORMULA: YES" in analysis or "MATH: YES" in analysis
    
    yt_match = re.search(r'YOUTUBE_URL:\s*(\S+)', analysis)
    if yt_match:
        yt_val = yt_match.group(1).strip()
        if yt_val.upper() != "NONE":
            youtube_url = yt_val
    
    wiki_match = re.search(r'WIKI_TOPICS:\s*(.*?)(?:\n|$)', analysis, re.DOTALL)
    if wiki_match:
        topics = wiki_match.group(1).strip()
        wiki_topics = [t.strip() for t in topics.split(',') if t.strip().lower() != 'none']
    
    search_match = re.search(r'SEARCH_QUERIES:\s*(.*?)(?:\n|$)', analysis, re.DOTALL)
    if search_match:
        queries = search_match.group(1).strip()
        search_queries = [q.strip() for q in queries.split(',') if q.strip().lower() != 'none']
    
    print(f"  📊 Analysis done", flush=True)
    
    # Step 2: Execute lookups in parallel
    facts = []
    
    # Wikipedia lookups
    for topic in wiki_topics[:3]:
        summary = wiki_read(topic)
        if summary:
            facts.append(f"[Wikipedia: {topic}]\n{summary[:3000]}")
        else:
            # Try to find by search
            titles = wiki_search(topic)
            if titles:
                summary = wiki_read(titles[0])
                if summary:
                    facts.append(f"[Wikipedia: {titles[0]}]\n{summary[:3000]}")
    
    # Google searches
    for q in search_queries[:2]:
        urls = google_search(q)
        for url in urls[:2]:
            content = read_url(url)
            if content:
                facts.append(f"[URL: {url}]\n{content[:2000]}")
    
    # YouTube
    if youtube_url:
        info = youtube_caption(youtube_url)
        if info:
            facts.append(f"[YouTube: {youtube_url}]\n{info[:3000]}")
    
    # PDF
    if has_file and ext == '.pdf':
        text = extract_pdf(file_path)
        if text:
            facts.append(f"[PDF: {file_path}]\n{text[:5000]}")
    
    if not facts:
        # Fallback: try direct Wikipedia on key terms
        terms = re.findall(r'"([^"]+)"', task)
        for t in terms[:3]:
            titles = wiki_search(t)
            if titles:
                summary = wiki_read(titles[0])
                if summary:
                    facts.append(f"[Wiki: {titles[0]}]\n{summary[:3000]}")
    
    print(f"  📚 Facts gathered: {len(facts)} sources", flush=True)
    for f in facts:
        print(f"    • {f.split(chr(10))[0][:60]}", flush=True)
    
    # Step 3: Synthesize answer
    context = "\n\n===\n\n".join(facts[:5]) if facts else "(no web data available)"
    
    answer_prompt = f"""You are solving a GAIA benchmark task. Use the provided facts and your knowledge.

TASK: {task}

FACTS FROM RESEARCH:
{context[:8000]}

Rules:
1. Extract the exact answer from the facts
2. If calculation needed, provide ONLY the final number
3. Gold answers are always short — a number (like "17", "3", "0.1777") or a few words
4. Do NOT write "The answer is...", "First...", "To solve..." — just the number/word
5. NO explanations, NO step-by-step, NO commentary
6. You MUST provide an answer. If uncertain, provide your best guess.

FINAL ANSWER (just the number or short phrase, no explanation):"""
    
    answer = llm(answer_prompt, max_tokens=100, temp=0.0)
    
    elapsed = time.time() - start
    print(f"  ⏱ {elapsed:.1f}s", flush=True)
    
    return answer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, required=True)
    parser.add_argument("--file", type=str)
    args = parser.parse_args()
    
    print(f"🤖 GAIA v4 Structured Agent", flush=True)
    
    answer = solve(args.task, args.file)
    
    print(f"\n{'='*60}", flush=True)
    print(f"📝 ANSWER: {answer}", flush=True)


if __name__ == "__main__":
    main()
