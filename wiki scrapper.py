#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import csv
import os
import random
import re
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup

WIKI_BASE = "https://en.wikipedia.org"
ARTICLE_PREFIX = "/wiki/"
BAD_PREFIXES = (
    "Category:", "File:", "Help:", "Portal:", "Special:", "Template:",
    "Template_talk:", "Talk:", "Wikipedia:", "Module:", "Draft:",
    "Book:", "TimedText:", "MediaWiki:", "Gadget:", "Gadget_definition:"
)

# -------- Utilities -------- #

def sanitize_filename(name: str) -> str:
    name = unquote(name)
    name = name.replace(" ", "_")
    name = re.sub(r"[^\w\-\.]+", "_", name, flags=re.UNICODE)
    return name[:180]  # keep file names reasonable

def clean_text(text: str) -> str:
    # Remove bracketed citation numbers [1], [12], [a], [note 1]
    text = re.sub(r"\[\s*([0-9]+|[a-zA-Z]+|note\s*\d+)\s*\]", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_article_href(href: str) -> bool:
    if not href or not href.startswith(ARTICLE_PREFIX):
        return False
    # filter out fragments and query
    if "#" in href or "?" in href:
        return False
    topic = href.split(ARTICLE_PREFIX, 1)[-1]
    # Skip non-article namespaces
    for bad in BAD_PREFIXES:
        if topic.startswith(bad):
            return False
    return True

def extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1", id="firstHeading")
    return h1.get_text(strip=True) if h1 else ""

# -------- HTTP session with politeness -------- #

class PoliteSession:
    """
    A polite HTTP session with:
      - custom UA
      - max retries (simple)
      - global rate limit (semaphore + sleep)
    """
    def __init__(self, delay: float, jitter: float, max_retries: int, timeout: float, max_parallel: int):
        self.sess = requests.Session()
        self.sess.headers.update({
            "User-Agent": "RespectfulWikiScraper/1.0 (+non-malicious; for learning) "
                          "Python-requests"
        })
        self.delay = delay
        self.jitter = jitter
        self.max_retries = max_retries
        self.timeout = timeout
        self.lock = threading.Lock()
        self.sema = threading.Semaphore(max_parallel)

    def get(self, url: str):
        # Rate limit: one token per request, sleep after release to spread load
        for attempt in range(1, self.max_retries + 1):
            self.sema.acquire()
            try:
                resp = self.sess.get(url, timeout=self.timeout)
                if resp.status_code in (429, 500, 502, 503, 504):
                    # Backoff on transient errors
                    back = self.delay * attempt + random.random() * self.jitter
                    time.sleep(back)
                else:
                    return resp
            except requests.RequestException:
                back = self.delay * attempt + random.random() * self.jitter
                time.sleep(back)
            finally:
                self.sema.release()
            # small spacing even after release to keep average RPS lower
            time.sleep(self.delay + random.random() * self.jitter)
        return None

# -------- Scrape logic -------- #

def parse_article_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    content = soup.find("div", class_="mw-parser-output")
    if not content:
        return "", [], soup
    # Collect paragraphs (skip empty)
    paragraphs = []
    for p in content.find_all("p"):
        txt = clean_text(p.get_text())
        if txt:
            paragraphs.append(txt)
    body = "\n\n".join(paragraphs)

    # Collect outgoing article links
    links = []
    for a in content.select("a[href]"):
        href = a.get("href")
        if is_article_href(href):
            links.append(href)
    return body, links, soup

def save_article(out_dir: str, title: str, url: str, body: str) -> str:
    if not title:
        # derive from URL
        title = url.split("/wiki/", 1)[-1].replace("_", " ")
    fname = sanitize_filename(title) + ".txt"
    fpath = os.path.join(out_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(body)
    return fpath

def scrape_single(session: PoliteSession, url: str):
    resp = session.get(url)
    if not resp or resp.status_code != 200 or not resp.text:
        return None, None, None, None  # body, links, title, status
    body, links, soup = parse_article_html(resp.text)
    title = extract_title(soup)
    return body, links, title, resp.status_code

# -------- Crawler -------- #

def crawl(start_topic: str, out_dir: str, limit: int, max_depth: int, workers: int,
          delay: float, jitter: float, timeout: float, retries: int):
    os.makedirs(out_dir, exist_ok=True)

    index_path = os.path.join(out_dir, "index.csv")
    index_fp = open(index_path, "w", encoding="utf-8", newline="")
    index = csv.writer(index_fp)
    index.writerow(["title", "url", "file", "bytes", "status", "depth", "out_links"])

    start_url = f"{WIKI_BASE}{ARTICLE_PREFIX}{start_topic.replace(' ', '_')}"
    seen = set()
    q = deque([(start_url, 0)])
    seen.add(start_url)

    session = PoliteSession(delay=delay, jitter=jitter, max_retries=retries, timeout=timeout,
                            max_parallel=workers)

    saved = 0
    futures_map = {}
    page_depth = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        while q and saved < limit:
            # Schedule up to remaining slots
            while q and len(futures_map) < workers and saved + len(futures_map) < limit:
                url, depth = q.popleft()
                page_depth[url] = depth
                futures_map[executor.submit(scrape_single, session, url)] = url

            if not futures_map:
                break

            done, _pending = as_completed(list(futures_map.keys()), timeout=None), None
            for fut in done:
                url = futures_map.pop(fut)
                depth = page_depth.get(url, 0)
                try:
                    body, links, title, status = fut.result()
                except Exception:
                    body, links, title, status = None, None, None, None

                if body and status == 200:
                    fpath = save_article(out_dir, title, url, body)
                    saved += 1
                    index.writerow([
                        title or "",
                        url,
                        os.path.basename(fpath),
                        os.path.getsize(fpath),
                        status,
                        depth,
                        len(links or [])
                    ])

                    # Enqueue children if within depth and limit
                    if depth < max_depth:
                        for href in links or []:
                            full = urljoin(WIKI_BASE, href)
                            # Keep within enwiki host
                            if urlparse(full).netloc != urlparse(WIKI_BASE).netloc:
                                continue
                            if full not in seen and saved + len(futures_map) < limit:
                                seen.add(full)
                                q.append((full, depth + 1))
                else:
                    index.writerow(["", url, "", 0, status or "ERR", depth, 0])

                if saved >= limit:
                    break

    index_fp.close()
    return saved, index_path

# -------- CLI -------- #

def main():
    parser = argparse.ArgumentParser(
        description="Polite, multi-threaded Wikipedia scraper for educational use."
    )
    parser.add_argument("--topic", required=True, help='Start topic, e.g. "Machine learning"')
    parser.add_argument("--out", default=None, help="Output directory (default: <topic>_wiki_articles)")
    parser.add_argument("--limit", type=int, default=30, help="Max pages to save (default: 30)")
    parser.add_argument("--depth", type=int, default=1, help="Max crawl depth (default: 1)")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent workers (default: 4)")
    parser.add_argument("--delay", type=float, default=1.0, help="Base delay between requests (default: 1.0s)")
    parser.add_argument("--jitter", type=float, default=0.5, help="Random jitter added to delay (default: 0.5s)")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout seconds (default: 15)")
    parser.add_argument("--retries", type=int, default=3, help="Max retries on transient errors (default: 3)")
    args = parser.parse_args()

    topic = args.topic.strip()
    out_dir = args.out or f"{topic.replace(' ', '_').lower()}_wiki_articles"

    print(f"▶ Starting crawl from: {topic}")
    print(f"   limit={args.limit}, depth={args.depth}, workers={args.workers}")
    print(f"   out_dir={out_dir}")

    saved, index_path = crawl(
        start_topic=topic,
        out_dir=out_dir,
        limit=args.limit,
        max_depth=args.depth,
        workers=args.workers,
        delay=args.delay,
        jitter=args.jitter,
        timeout=args.timeout,
        retries=args.retries,
    )

    print(f"✅ Done. Saved {saved} page(s).")
    print(f"📄 Index: {index_path}")

if __name__ == "__main__":
    main()
