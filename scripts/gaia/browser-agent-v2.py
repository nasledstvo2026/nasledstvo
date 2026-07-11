#!/usr/bin/env python3
"""
GAIA Browser Agent v2 — improved for GAIA benchmark.
Key improvements:
 - Full page text extraction (not truncated to 5k)
 - Better planning prompts with Wikipedia-specific strategy
 - Readability-mode: extract article content, skip navigation
 - Step limit and anti-loop logic
"""

import sys, os, json, re, time, argparse, subprocess, requests
from urllib.parse import urlparse

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

class BrowserAgentV2:
    MAX_STEPS = 20
    
    def __init__(self, headless=True, model="deepseek-chat"):
        self.headless = headless
        self.model = model
        self.browser = None
        self.page = None
        self.context = None
        self.history = []
        self._seen_urls = set()
        
    def _llm(self, prompt, max_tokens=800, temp=0.0):
        for a in range(3):
            try:
                r = requests.post(DEEPSEEK_URL,
                    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                    json={"model": self.model, "messages": [{"role":"user","content":prompt}],
                          "max_tokens": max_tokens, "temperature": temp},
                    timeout=60)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"].strip()
            except:
                time.sleep(2)
        return ""

    def start(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)
        
    def close(self):
        if self.browser:
            self.browser.close()
        if self._pw:
            self._pw.stop()

    def extract_content_full(self):
        """Extract full readable content from current page."""
        try:
            title = self.page.title()
            url = self.page.url
            
            # Get all visible text — first more selective, but more
            text = self.page.inner_text("body")
            # Remove excessive whitespace
            text = ' '.join(text.split())
            
            # Get all links with text
            links = self.page.eval_on_selector_all("a[href]", 
                "els => els.map(e => ({text: e.innerText.trim().slice(0,80), href: e.href})).filter(l => l.text).slice(0,40)")
            
            # Get key article content sections (for Wikipedia, etc.)
            article_text = ""
            for sel in ["article", "[role=main]", "main", ".mw-parser-output", "#mw-content-text", ".post-content", ".entry-content"]:
                try:
                    el = self.page.query_selector(sel)
                    if el:
                        article_text = el.inner_text()
                        break
                except:
                    pass
            
            # Smart truncation: keep article if available, else body
            if article_text and len(article_text) > 200:
                display_text = article_text[:10000]
            else:
                display_text = text[:12000]
                
            return {"url": url, "title": title, "text": display_text, "links": links, "article_found": bool(article_text)}
        except Exception as e:
            return {"url": "", "title": "", "text": f"Error: {e}", "links": [], "article_found": False}

    def plan(self, task, context=""):
        """Plan next action with anti-loop protection."""
        # Detect loops: same URL visited 3+ times
        urls_visited = [h.get('url','') for h in self.history if h.get('url')]
        recent_urls = urls_visited[-8:]
        loop_warning = ""
        if len(set(recent_urls)) <= 2 and len(recent_urls) >= 4:
            loop_warning = "\n\n⚠️ You are looping between the same URLs. Try a COMPLETELY DIFFERENT approach or answer with current info."

        prompt = f"""You are a web browsing agent being benchmarked on GAIA. Complete the task accurately.

TASK: {task}

CURRENT PAGE:
Title: {context.get('title','?')}
URL: {context.get('url','?')}

CONTENT (first 6000 chars):
{context.get('text','')[:6000]}

AVAILABLE ACTIONS:
1. navigate(url) - Go to a URL (for Wikipedia: use en.wikipedia.org/wiki/ARTICLE_NAME)
2. click(selector) - Click an element (use visible link text like "Demographics", "Population")
3. search(query) - Search Google for specific info
4. scroll(down/up) - Scroll to see more content
5. extract() - Re-read full page content (use when you scrolled)
6. answer(text) - FINAL ANSWER — short, precise{loop_warning}

STRATEGY:
- For numerical answers: find the exact number on the page
- For Wikipedia: navigate directly to the article, scroll to find the relevant section, extract the number
- If stuck after 5 steps, answer with best guess

PREVIOUS ACTIONS:
{self._last_actions(8)}

Respond with JSON:
{{"action": "navigate", "url": "https://..."}}
{{"action": "click", "selector": "link text"}}
{{"action": "search", "query": "search terms"}}
{{"action": "scroll", "direction": "down"}}
{{"action": "extract"}}
{{"action": "answer", "text": "your precise answer"}}"""
        
        resp = self._llm(prompt, max_tokens=300, temp=0.1)
        try:
            match = re.search(r'\{[^}]+\}', resp, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        return {"action": "extract"}

    def _last_actions(self, n=8):
        lines = []
        for h in self.history[-n:]:
            a = h.get('action','?')
            r = h.get('result','')[:80]
            u = h.get('url','')
            lines.append(f"  {a}: {r}")
        return "\n".join(lines)

    def execute_action(self, action):
        action_type = action.get("action", "")
        
        if action_type == "navigate":
            url = action.get("url", "")
            if not url.startswith("http"):
                url = "https://" + url
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
                self._seen_urls.add(self.page.url)
                return f"Navigated to {url}", self.page.url
            except Exception as e:
                return f"Navigate error: {str(e)[:80]}", url
                
        elif action_type == "search":
            query = action.get("query", "")
            try:
                self.page.goto(f"https://www.google.com/search?q={query.replace(' ', '+')}", 
                              wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
                self._seen_urls.add(self.page.url)
                
                # Extract search results
                results = self.page.inner_text("body")[:3000]
                return f"Searched: {query}\nResults: {results[:200]}...", self.page.url
            except Exception as e:
                return f"Search error: {e}", "https://google.com"
                
        elif action_type == "click":
            selector = action.get("selector", "")
            try:
                link = self.page.get_by_role("link", name=selector)
                if link.count() > 0:
                    link.first.click(timeout=5000)
                else:
                    self.page.click(f"text={selector}", timeout=5000)
                time.sleep(2)
                return f"Clicked: {selector}", self.page.url
            except:
                return f"Could not click: {selector}", self.page.url
                
        elif action_type == "scroll":
            direction = action.get("direction", "down")
            dy = 600 if direction == "down" else -600
            self.page.evaluate(f"window.scrollBy(0, {dy})")
            time.sleep(1)
            
            # Check if more content loaded
            visible = self.page.evaluate("window.innerHeight + window.scrollY")
            total = self.page.evaluate("document.body.scrollHeight")
            at_bottom = visible >= total - 50
            
            state = "at bottom" if at_bottom else f"scrolled {direction}"
            return state, self.page.url
            
        elif action_type == "extract":
            content = self.extract_content_full()
            text = content["text"]
            word_count = len(text.split())
            return f"Extracted: {word_count} words, title: {content['title']}", self.page.url
            
        elif action_type == "answer":
            return f"ANSWER: {action.get('text', '')}", self.page.url
            
        return f"Unknown: {action_type}", ""

    def solve(self, task, file_path=None):
        self.start()
        self.history = []
        
        try:
            for step in range(self.MAX_STEPS):
                context = self.extract_content_full()
                
                action = self.plan(task, context)
                result, url = self.execute_action(action)
                
                self.history.append({
                    "step": step + 1,
                    "action": action.get("action", "?"),
                    "url": url,
                    "result": result[:200],
                })
                
                if action.get("action") == "answer":
                    answer = action.get("text", "")
                    print(f"\n✅ Step {step+1}: {action.get('action')} → {answer[:200]}", flush=True)
                    return answer
                    
                print(f"  {step+1}/{self.MAX_STEPS}: {action.get('action')} → {result[:100]}", flush=True)
            
            content = self.extract_content_full()
            return f"Could not find answer.\nPage: {content['url']}\nContent:\n{content['text'][:2000]}"
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=str, required=True)
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()
    
    agent = BrowserAgentV2(headless=args.headless)
    print(f"🤖 BrowserAgent V2 starting...", flush=True)
    print(f"📋 {args.task[:200]}", flush=True)
    
    result = agent.solve(args.task)
    
    print(f"\n{'='*60}", flush=True)
    print(f"📝 ANSWER: {result}", flush=True)


if __name__ == "__main__":
    main()
