"""
Church website scraper.

Produces JSONL records: {"source": url, "content": markdown_text}
Used by the updater to build per-church knowledge bundles.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse

import html2text
from bs4 import BeautifulSoup

from context_manager import is_useful_page
from logging_config import setup_logging

logger = setup_logging()

DEFAULT_MAX_PAGES = 400
FETCH_TIMEOUT_SECONDS = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

SEED_EXPANSIONS = [
    "/locations",
    "/campuses",
    "/visit",
    "/times",
    "/connect",
    "/about",
    "/new",
    "/give",
    "/giving",
    "/donate",
]

IGNORE_KEYWORDS = [
    "login", "signin", "signup", "register", "cart", "checkout", "auth",
    "account", "password", "reset", "privacy", "terms", "policy",
    "facebook", "twitter", "instagram", "linkedin", "tiktok", "share",
    "mailto:", "javascript:", "#", "unsubscribe", "feed", "rss",
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
    "share event", "register", "learn more", "watch now",
    "watch replay", "attend online", "watch live in", "00h : 00m",
    "ccli", "streaming license", "copyright", "all rights reserved",
    "powered by", "site by", "website by",
]


def clean_url(url: str) -> str:
    parsed = urlparse(url)
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    return clean.rstrip("/")


def clean_extracted_text(text: str, url: str = "") -> str:
    if not text:
        return ""
    lines = text.split("\n")
    cleaned_lines = []

    is_location_page = False
    if url:
        u = url.lower()
        if any(p in u for p in ("/locations", "/campuses", "/visit", "/contact")):
            is_location_page = True

    for line in lines:
        line = line.strip()
        line_lower = line.lower()
        if len(line) < 3:
            continue
        if any(phrase in line_lower for phrase in BOILERPLATE_PHRASES):
            continue
        if ":" in line and "d :" in line:
            continue
        if line_lower in [
            "give", "i'm new", "kids", "youth", "adults", "families",
            "classes", "events", "featured", "view all", "share event",
        ]:
            continue
        cleaned_lines.append(line)

    seen: Set[str] = set()
    deduped = []
    for line in cleaned_lines:
        if line not in seen:
            deduped.append(line)
            seen.add(line)

    final_lines = []
    for i, line in enumerate(deduped):
        if "## Locations" in line and not is_location_page:
            is_generic_footer = False
            for forward_line in deduped[i + 1 : i + 6]:
                lower_f = forward_line.lower()
                if "campus" in lower_f or "location" in lower_f or "service time" in lower_f:
                    is_generic_footer = True
                    break
            if is_generic_footer:
                break
        final_lines.append(line)

    return "\n".join(final_lines)


def fetch_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def page_from_html(url: str, html: str) -> Dict[str, object]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href")
        if href:
            links.append(urljoin(url, href))

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.extract()

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.skip_internal_links = True
    converter.body_width = 0
    text = clean_extracted_text(converter.handle(str(soup)), url)
    return {"content": text, "links": links}


def scrape_pages(seed_url: str, max_pages: int = DEFAULT_MAX_PAGES) -> List[Dict[str, str]]:
    """Download church pages as HTML. The site text is already in the response."""
    results: List[Dict[str, str]] = []
    visited: Set[str] = set()
    queued: Set[str] = set()
    queue: List[str] = []

    def enqueue(url: str) -> None:
        clean = clean_url(url)
        if clean and clean not in visited and clean not in queued:
            queue.append(url)
            queued.add(clean)

    enqueue(seed_url)
    parsed = urlparse(seed_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in SEED_EXPANSIONS:
        enqueue(base + path)

    logger.info("scrape_start", extra={"extra_fields": {"seed_url": seed_url, "max_pages": max_pages}})
    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        clean = clean_url(url)
        queued.discard(clean)
        if clean in visited:
            continue
        visited.add(clean)
        logger.info("crawl_page", extra={"extra_fields": {"url": url}})
        try:
            html = fetch_html(url)
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            logger.warning("crawl_page_failed", extra={"extra_fields": {"url": url, "error": str(error)}})
            continue

        page = page_from_html(url, html)
        content = str(page["content"])
        if is_useful_page(content):
            results.append({"source": clean_url(url), "content": content})
        for link in page["links"]:
            if isinstance(link, str) and is_useful_link(seed_url, link):
                enqueue(link)

    if not results:
        raise RuntimeError(f"Scrape produced no pages from {seed_url}")
    logger.info("scrape_complete", extra={"extra_fields": {"pages": len(results)}})
    return results


def is_useful_link(base_url: str, link: str) -> bool:
    if not link or not link.startswith("http"):
        return False
    if urlparse(base_url).netloc != urlparse(link).netloc:
        return False
    link_lower = link.lower()
    if link_lower.endswith((".pdf", ".jpg", ".png", ".css", ".js", ".zip", ".xml", ".mp3", ".mp4")):
        return False
    if any(bad in link_lower for bad in IGNORE_KEYWORDS):
        return False
    return True


def write_jsonl(records: List[Dict[str, str]], output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in records:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return output_path


def scrape_site(
    start_url: str,
    output_file: Optional[str | Path] = None,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> List[Dict[str, str]]:
    if not start_url.startswith("http"):
        start_url = "https://" + start_url
    records = scrape_pages(start_url, max_pages=max_pages)
    if output_file:
        write_jsonl(records, Path(output_file))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape a church website into JSONL")
    parser.add_argument("url", nargs="?", help="Base URL to scrape")
    parser.add_argument("--base_url", help="Alias for positional URL")
    parser.add_argument("--output_file", default="scraped_data.jsonl")
    parser.add_argument("--max_pages", type=int, default=DEFAULT_MAX_PAGES)
    args = parser.parse_args()

    start_url = args.base_url or args.url
    if not start_url:
        if sys.stdin.isatty():
            start_url = input("Enter church website URL: ").strip()
        else:
            print("ERROR: URL required in non-interactive mode. Pass url or --base_url.", file=sys.stderr)
            sys.exit(2)

    output_path = Path(args.output_file)
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path

    records = scrape_site(start_url, output_file=output_path, max_pages=args.max_pages)
    if not records:
        print("ERROR: No useful pages scraped.", file=sys.stderr)
        sys.exit(1)
    print(f"Saved {len(records)} pages to {output_path}")


if __name__ == "__main__":
    main()
