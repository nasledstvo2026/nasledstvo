#!/usr/bin/env python3
"""
GAIA-compatible Browser Agent for DeepSeek Chat.
Solves multi-step web reasoning tasks using Playwright + LLM planning.

Usage:
  python3 browser-agent.py --task "What is the population of Paris according to Wikipedia?"
  python3 browser-agent.py --task "Find the latest GDP data for Russia on worldbank.org"
  python3 browser-agent.py --task "задача из GAIA датасета (с файлом)"

Architecture:
  Task → LLM plans steps → Playwright executes → Extract → LLM reasons → Final answer
"""

import sys, os, json, re, time, argparse, subprocess, tempfile, traceback
from urllib.parse import urlparse

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

class BrowserAgent:
    MAX_STEPS = 15
    MAX_PLAN_LENGTH = 3000
    
    def __init__(self, headless=True, model="deepseek-chat"):
        self.headless = headless
        self.model = model
        self.browser = None
        self.page = None
        self.context = None
        self.history = []
        
    def _llm(self, prompt, max_tokens=500, temp=0.0):
        """Call DeepSeek Chat."""
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temp,
        })
        for attempt in range(3):
            try:
                r = subprocess.run(
                    ["curl", "-s", "-w", "\n%{http_code}",
                     "-H", f"Authorization: Bearer {DEEPSEEK_API_KEY}",
                     "-H", "Content-Type: application/json",
                     "-d", payload, "-m", "60", DEEPSEEK_URL],
                    capture_output=True, text=True, timeout=65
                )
                parts = r.stdout.strip().rsplit("\n", 1)
                if len(parts) != 2 or parts[1] != "200":
                    time.sleep(2)
                    continue
                data = json.loads(parts[0])
                return data["choices"][0]["message"]["content"].strip()
            except:
                time.sleep(3)
        return ""

    def start(self):
        """Launch browser."""
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        self.page = self.context.new_page()
        
    def close(self):
        """Close browser."""
        if self.browser:
            self.browser.close()
        if self._pw:
            self._pw.stop()

    def extract_content(self):
        """Extract readable text from current page."""
        try:
            title = self.page.title()
            url = self.page.url
            text = self.page.inner_text("body")[:5000]
            # Get visible links
            links = self.page.eval_on_selector_all("a[href]", 
                "els => els.map(e => ({text: e.innerText.trim().slice(0,60), href: e.href})).filter(l => l.text).slice(0,30)")
            return {"url": url, "title": title, "text": text, "links": links}
        except:
            return {"url": "", "title": "", "text": "", "links": []}

    def plan(self, task, context=""):
        """Plan next action based on task and current context."""
        last_urls = [h.get('params',{}).get('url','') for h in self.history[-5:] if h.get('action') in ('navigate','search')]
        url_warning = ""
        if len(set(last_urls)) <= 2 and len(last_urls) >= 3:
            url_warning = "\n\n⚠️ You keep visiting the same URLs. STOP revisiting. Try a different approach or use answer() with what you have."
        
        prompt = f"""You are a web browsing agent. Complete the following task by browsing the web.

TASK: {task}

CURRENT CONTEXT (from browser):
{context[:2000]}

RULES:
- Never visit the same URL twice in a row
- If you can't find exact data, answer with your best estimate and note it's approximate
- Prefer Wikipedia, official sources, or reputable news sites
- After 3 failed attempts to find something, answer with what you have

AVAILABLE ACTIONS:
1. navigate(url) - Go to a URL
2. click(selector) - Click an element (use link text or CSS selector)
3. type(selector, text) - Type into an input field
4. search(query) - Search Google
5. extract_text() - Get text from current page
6. scroll(direction) - Scroll "down" or "up"
7. wait(seconds) - Wait for page to load
8. answer(text) - FINAL ANSWER{url_warning}

PREVIOUS ACTIONS:
{self._last_actions(5)}

Respond with EXACTLY ONE action in JSON format:
{{"action": "navigate", "url": "https://..."}}
{{"action": "click", "selector": "link text"}}
{{"action": "type", "selector": "input", "text": "query"}}
{{"action": "search", "query": "search terms"}}
{{"action": "extract_text"}}
{{"action": "scroll", "direction": "down"}}
{{"action": "wait", "seconds": 3}}
{{"action": "answer", "text": "your final answer"}}"""
        
        resp = self._llm(prompt, max_tokens=300)
        # Parse JSON from response
        try:
            # Find JSON object in response
            match = re.search(r'\{[^}]+\}', resp, re.DOTALL)
            if match:
                return json.loads(match.group())
        except:
            pass
        return {"action": "extract_text"}

    def _last_actions(self, n=5):
        lines = []
        for h in self.history[-n:]:
            lines.append(f"{h.get('action','?')}: {h.get('result','')[:100]}")
        return "\n".join(lines)

    def execute_action(self, action):
        """Execute a planned action."""
        action_type = action.get("action", "")
        
        if action_type == "navigate":
            url = action.get("url", "")
            if not url.startswith("http"):
                url = "https://" + url
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
                return f"Navigated to {url}"
            except Exception as e:
                return f"Navigate error: {str(e)[:100]}"
                
        elif action_type == "click":
            selector = action.get("selector", "")
            try:
                # Try by text first
                link = self.page.get_by_role("link", name=selector)
                if link.count() > 0:
                    link.first.click(timeout=5000)
                else:
                    self.page.click(selector, timeout=5000)
                time.sleep(2)
                return f"Clicked: {selector}"
            except:
                try:
                    self.page.click(f"text={selector}", timeout=5000)
                    time.sleep(2)
                    return f"Clicked text: {selector}"
                except Exception as e:
                    return f"Click error: {str(e)[:100]}"
                    
        elif action_type == "type":
            selector = action.get("selector", "input")
            text = action.get("text", "")
            try:
                self.page.fill(selector, text, timeout=5000)
                return f"Typed '{text[:50]}' into {selector}"
            except Exception as e:
                return f"Type error: {str(e)[:100]}"
                
        elif action_type == "search":
            query = action.get("query", "")
            try:
                self.page.goto(f"https://www.google.com/search?q={query.replace(' ', '+')}", 
                              wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
                return f"Searched: {query}"
            except Exception as e:
                return f"Search error: {str(e)[:100]}"
                
        elif action_type == "extract_text":
            content = self.extract_content()
            return f"Page: {content['title']} | Text length: {len(content['text'])}"
            
        elif action_type == "scroll":
            direction = action.get("direction", "down")
            try:
                self.page.evaluate(f"window.scrollBy(0, {500 if direction=='down' else -500})")
                time.sleep(1)
                return f"Scrolled {direction}"
            except:
                return "Scroll error"
                
        elif action_type == "wait":
            sec = action.get("seconds", 2)
            time.sleep(sec)
            return f"Waited {sec}s"
            
        elif action_type == "answer":
            return f"ANSWER: {action.get('text', '')}"
            
        return f"Unknown action: {action_type}"

    def solve(self, task, file_path=None):
        """Solve a task end-to-end."""
        self.start()
        self.history = []
        
        try:
            for step in range(self.MAX_STEPS):
                context = self.extract_content()
                context_str = json.dumps(context, ensure_ascii=False)
                
                action = self.plan(task, context_str)
                
                result = self.execute_action(action)
                
                self.history.append({
                    "step": step + 1,
                    "action": action.get("action", "?"),
                    "params": action,
                    "result": result[:200],
                })
                
                # Check if answer
                if action.get("action") == "answer":
                    answer = action.get("text", "")
                    print(f"\n✅ Step {step+1}: {action.get('action')} → {answer[:200]}", flush=True)
                    return answer
                    
                print(f"  Step {step+1}: {action.get('action')} → {result[:120]}", flush=True)
            
            # If no answer, extract what we have
            content = self.extract_content()
            return f"Could not find answer. Last page: {content['url']}\n\nContent:\n{content['text'][:2000]}"
            
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description="GAIA Browser Agent")
    parser.add_argument("--task", type=str, required=True, help="Task to solve")
    parser.add_argument("--file", type=str, help="Path to attachment file")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()
    
    agent = BrowserAgent(headless=args.headless)
    print(f"🤖 Starting browser agent...", flush=True)
    print(f"📋 Task: {args.task[:200]}", flush=True)
    
    result = agent.solve(args.task, args.file)
    
    print(f"\n{'='*60}", flush=True)
    print(f"📝 ANSWER: {result}", flush=True)
    print(f"{'='*60}", flush=True)


if __name__ == "__main__":
    main()
