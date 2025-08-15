import requests as rq
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import urljoin

WIKI_BASE = "https://en.wikipedia.org"

def clean_text(text):
    """Remove citation numbers and extra spaces."""
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def scrape_single_article(topic_url, folder):
    """Scrape a single Wikipedia article and save it."""
    res = rq.get(topic_url)
    if res.status_code != 200:
        print(f"❌ Failed to retrieve {topic_url} (Status: {res.status_code})")
        return None

    soup = BeautifulSoup(res.text, 'html.parser')
    content = soup.find('div', {'class': 'mw-parser-output'})
    if not content:
        print(f"⚠️ No main content found for {topic_url}")
        return None

    paragraphs = content.find_all('p')
    clean_paragraphs = [clean_text(p.get_text()) for p in paragraphs if clean_text(p.get_text())]

    article_text = "\n\n".join(clean_paragraphs)
    if not article_text.strip():
        return None

    # Generate filename from URL
    topic_name = topic_url.split("/wiki/")[-1]
    filename = os.path.join(folder, f"{topic_name.lower()}.txt")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(article_text)

    print(f"✅ Saved: {filename}")
    return soup

def scrape_wikipedia_with_links(start_topic, limit=5):
    """Scrape the main topic and related linked Wikipedia articles."""
    folder = start_topic.replace(" ", "_").lower() + "_wiki_articles"
    os.makedirs(folder, exist_ok=True)

    start_url = f"{WIKI_BASE}/wiki/{start_topic.replace(' ', '_')}"
    soup = scrape_single_article(start_url, folder)

    if not soup:
        return

    # Find related article links
    links = soup.select("div.mw-parser-output a[href^='/wiki/']")
    seen = set()
    count = 0

    for link in links:
        href = link.get("href")
        if ":" in href:  # Skip special pages like Category:, File:, etc.
            continue
        full_url = urljoin(WIKI_BASE, href)
        if full_url not in seen:
            seen.add(full_url)
            count += 1
            scrape_single_article(full_url, folder)
            if count >= limit:
                break

# Example usage
scrape_wikipedia_with_links("Machine learning", limit=5)