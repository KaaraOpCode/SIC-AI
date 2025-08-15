import os
import re
import time
import random
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------- SETTINGS ----------
START_TOPIC = "Machine learning"
LIMIT = 10         # max number of pages to download
MAX_DEPTH = 1      # how far to follow links from the start page
OUTPUT_DIR = START_TOPIC.replace(" ", "_").lower() + "_wiki_articles"
BASE_URL = "https://en.wikipedia.org"
ARTICLE_PREFIX = "/wiki/"
BAD_PREFIXES = (
    "Category:", "File:", "Help:", "Portal:", "Special:", "Template:",
    "Talk:", "Wikipedia:", "Module:", "Draft:", "Book:"
)
DELAY = 1.0        # seconds between requests
JITTER = 0.5       # random delay to be polite
# ------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_text(text):
    text = re.sub(r"\[\d+\]", "", text)  # remove citations like [1]
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_article_link(href):
    if not href or not href.startswith(ARTICLE_PREFIX):
        return False
    if "#" in href or "?" in href:
        return False
    topic = href.split(ARTICLE_PREFIX, 1)[-1]
    for bad in BAD_PREFIXES:
        if topic.startswith(bad):
            return False
    return True

def scrape_article(url):
    """Download and clean a single Wikipedia article."""
    try:
        time.sleep(DELAY + random.random() * JITTER)  # be polite
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None, []
        soup = BeautifulSoup(r.text, "html.parser")
        content = soup.find("div", class_="mw-parser-output")
        if not content:
            return None, []
        paragraphs = [clean_text(p.get_text()) for p in content.find_all("p") if clean_text(p.get_text())]
        body = "\n\n".join(paragraphs)
        links = [a.get("href") for a in content.find_all("a", href=True) if is_article_link(a.get("href"))]
        title_tag = soup.find("h1", id="firstHeading")
        title = title_tag.get_text(strip=True) if title_tag else url
        return (title, body), links
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None, []

def save_article(title, body):
    filename = re.sub(r"[^\w\-]", "_", title)[:150] + ".txt"
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return path

# BFS crawling
start_url = f"{BASE_URL}{ARTICLE_PREFIX}{START_TOPIC.replace(' ', '_')}"
queue = deque([(start_url, 0)])
seen = set([start_url])
count = 0

while queue and count < LIMIT:
    url, depth = queue.popleft()
    print(f"Scraping ({count+1}/{LIMIT}): {url}")
    article, links = scrape_article(url)
    if article:
        title, body = article
        save_article(title, body)
        count += 1
        if depth < MAX_DEPTH:
            for link in links:
                full_url = urljoin(BASE_URL, link)
                if full_url not in seen and count + len(queue) < LIMIT:
                    seen.add(full_url)
                    queue.append((full_url, depth + 1))

print("\n✅ Crawl finished!")
print(f"Saved {count} articles to '{OUTPUT_DIR}'")

# Preview first article
sample_file = next(iter(os.listdir(OUTPUT_DIR)), None)
if sample_file:
    print(f"\n📄 Preview from {sample_file}:")
    with open(os.path.join(OUTPUT_DIR, sample_file), "r", encoding="utf-8") as f:
        print(f.read()[:500], "...")