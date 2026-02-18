import sys
import os
import json
import asyncio
import nest_asyncio
import re
import argparse
from urllib.parse import urlparse, urlunparse
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup 
import html2text

nest_asyncio.apply()

# --- CONFIGURATION ---
MAX_PAGES_TO_CRAWL = 1000
TIMEOUT_MS = 15000 
CONCURRENT_BATCH_SIZE = 15

# --- SEED EXPANSIONS ---
SEED_EXPANSIONS = [
    "/locations", "/campuses", "/visit", "/times", "/connect", "/about", "/new", "/give", "/giving", "/donate"
]

# Junk to ignore
IGNORE_KEYWORDS = [
    "login", "signin", "signup", "register", "cart", "checkout", "auth",
    "account", "password", "reset", "privacy", "terms", "policy", 
    "facebook", "twitter", "instagram", "linkedin", "tiktok", "share",
    "mailto:", "javascript:", "#", "unsubscribe", "feed", "rss"
]

BOILERPLATE_PHRASES = [
    "manage consent", "preferences", "rights reserved", "basic website functionality",
    "deliver advertising", "cookie policy", "privacy policy", "terms of use",
    "accept all", "reject all", "save preferences", "always active", "checkbox",
    "marketing", "analytics", "personalization", "essential",
    "view our privacy policy", "stored or retrieved", "impact your experience",
    "data in your browser", "cancel", "decline", "accept",
    "skip to content", "view map", "get directions", "menu", "search",
    "log in", "sign up", "cart", "checkout", "close", "open", "toggle",
    "share event", "register", "learn more", "watch now", "give", "i'm new",
    "watch replay", "attend online", "watch live in", "00h : 00m",
    "ccli", "streaming license", "copyright", "all rights reserved",
    "powered by", "site by", "website by"
]

def clean_url(url):
    parsed = urlparse(url)
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return clean.rstrip("/")

def clean_extracted_text(text, url=""):
    if not text: return ""
    lines = text.split('\n')
    cleaned_lines = []
    
    is_location_page = False
    if url:
        u = url.lower()
        if "/locations" in u or "/campuses" in u or "/visit" in u or "/contact" in u:
            is_location_page = True

    for line in lines:
        line = line.strip()
        line_lower = line.lower()
        
        if len(line) < 3: continue
        if any(phrase in line_lower for phrase in BOILERPLATE_PHRASES): continue
        if ":" in line and "d :" in line: continue
        if line_lower in ["give", "i'm new", "kids", "youth", "adults", "families", "classes", "events", "featured", "view all", "share event"]:
            continue
            
        cleaned_lines.append(line)
    
    seen = set()
    deduped = []
    for line in cleaned_lines:
        if line not in seen:
            deduped.append(line)
            seen.add(line)

    final_lines = []
    footer_detected = False
    
    for i, line in enumerate(deduped):
        if "## Locations" in line:
            is_generic_footer = False
            for forward_line in deduped[i+1:i+6]:
                lower_f = forward_line.lower()
                if "campus" in lower_f or "location" in lower_f or "service time" in lower_f:
                    is_generic_footer = True
                    break
            
            if is_generic_footer and not is_location_page:
                footer_detected = True
                break
        
        final_lines.append(line)

    return "\n".join(final_lines)

def is_useful_link(base_url, link):
    if not link or not link.startswith("http"): return False
    if urlparse(base_url).netloc != urlparse(link).netloc: return False
    
    link_lower = link.lower()
    if link_lower.endswith(('.pdf', '.jpg', '.png', '.css', '.js', '.zip', '.xml', '.mp3', '.mp4')): return False
    if any(bad in link_lower for bad in IGNORE_KEYWORDS): return False
    
    return True

async def process_batch(context, batch_urls):
    tasks = []
    for url in batch_urls:
        tasks.append(scrape_single_page(context, url))
    results = await asyncio.gather(*tasks)
    return results

async def scrape_single_page(context, url):
    print(f"   ...Crawling: {url}")
    try:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_emphasis = False
        h.skip_internal_links = True
        h.body_width = 0
        
        markdown_text = h.handle(html)
        clean_text = clean_extracted_text(markdown_text, url)
        
        links = await page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
        await page.close()
        return {"url": url, "content": clean_text, "links": links}
    except Exception as e:
        return {"url": url, "content": "", "links": []}

async def recursive_scrape(seed_url):
    results = [] 
    print(f"Starting Church Scrape on: {seed_url}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36"
        )
        await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,ico,mp4,avi,mov,css,woff,woff2}", lambda route: route.abort())

        visited = set()
        queue = [seed_url]
        
        parsed = urlparse(seed_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        for ext in SEED_EXPANSIONS:
            full = base + ext
            queue.append(full)
        
        pages_scraped = 0
        
        while queue and pages_scraped < MAX_PAGES_TO_CRAWL:
            batch_urls = []
            while len(batch_urls) < CONCURRENT_BATCH_SIZE and queue:
                url = queue.pop(0)
                clean = clean_url(url)
                if clean in visited: continue
                visited.add(clean)
                batch_urls.append(url)
            
            if not batch_urls: break
                
            print(f"   --- Batch {pages_scraped // CONCURRENT_BATCH_SIZE + 1} ---")
            batch_results = await process_batch(context, batch_urls)
            
            for res in batch_results:
                pages_scraped += 1
                text = res['content']
                found_links = res['links']
                current_url = res['url']
                
                if text and len(text) > 50:
                    results.append({"source": current_url, "content": text})
                
                for link in found_links:
                    c_link = clean_url(link)
                    if is_useful_link(seed_url, link) and c_link not in visited:
                        if c_link not in queue:
                            queue.append(c_link)

        await context.close()
        await browser.close()
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", help="Base URL to scrape")
    parser.add_argument("--base_url", help="Base URL to scrape (optional, alias for positional)")
    parser.add_argument("--output_file", default="scraped_data.jsonl", help="Output JSONL file")
    
    args, unknown = parser.parse_known_args()
    
    start_url = args.base_url or args.url
    if not start_url:
        start_url = input("Enter church website URL (e.g. https://www.examplechurch.org): ").strip()
    
    if not start_url.startswith("http"):
        start_url = "https://" + start_url
        
    data_points = asyncio.run(recursive_scrape(start_url))
    
    if not data_points:
        print("x No data found.")
        return

    # Determine Output Path
    if os.path.isabs(args.output_file):
        output_path = args.output_file
    else:
        # Default to project root for the default filename, or relative to cwd for others?
        # The original logic used project root for default.
        # Let's verify where PROJECT_ROOT is.
        # It's usually one level up from this script.
        base_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.join(base_dir, "..")
        output_path = os.path.join(project_root, args.output_file)
    
    if os.path.exists(output_path): 
        try:
            os.remove(output_path)
        except OSError:
            print(f"Warning: Could not remove existing file {output_path}")
    
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in data_points:
            f.write(json.dumps(entry) + "\n")
            
    print(f"   [DONE] Saved {len(data_points)} pages to {output_path}")

if __name__ == "__main__":
    main()