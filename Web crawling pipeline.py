# ----------------------------- IMPORTS -----------------------------
import os
import re
import csv
import time
import random
from collections import deque, Counter
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import nltk
from nltk.corpus import stopwords
import spacy
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from gensim import corpora, models, summarization
from fpdf import FPDF

# ----------------------------- SETTINGS -----------------------------
START_URL = "https://en.wikipedia.org/wiki/Machine_learning"
LIMIT = 20
MAX_DEPTH = 2
OUTPUT_DIR = "wiki_articles"
SUMMARY_DIR = "wiki_summaries"
WORD_FREQ_CSV = "word_frequency.csv"
PDF_FILE = "wiki_mini_encyclopedia_toc.pdf"
DELAY = 1.0
JITTER = 0.5
TOPIC_COUNT = 5
SUMMARY_RATIO = 0.2
# --------------------------------------------------------------------

# -------------------------- SETUP --------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)
visited = set()
queue = deque([(START_URL, 0)])

# Download NLP resources
nltk.download('punkt')
nltk.download('stopwords')
stop_words = set(stopwords.words('english'))
nlp = spacy.load("en_core_web_sm")

# ----------------------- CRAWLING -----------------------
def clean_text(text):
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def scrape_page(url):
    try:
        time.sleep(DELAY + random.random() * JITTER)
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        content = soup.find("div", class_="mw-parser-output")
        if not content:
            return None, []

        paragraphs = [clean_text(p.get_text()) for p in content.find_all("p") if clean_text(p.get_text())]
        text_body = "\n\n".join(paragraphs)

        links = [a.get("href") for a in content.find_all("a", href=True)]
        links = [urljoin(url, l) for l in links if l.startswith("/wiki/") and ":" not in l]

        title_tag = soup.find("h1", id="firstHeading")
        title = title_tag.get_text(strip=True) if title_tag else "untitled"
        return (title, text_body), links
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
        return None, []

def save_article(title, body):
    filename = re.sub(r"[^\w\-]", "_", title)[:150] + ".txt"
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return filename, len(body.split())

# BFS Crawl
all_texts = {}
documents = []
count = 0
while queue and count < LIMIT:
    url, depth = queue.popleft()
    if url in visited or depth > MAX_DEPTH:
        continue

    article, links = scrape_page(url)
    if article:
        title, body = article
        filename, word_count = save_article(title, body)
        all_texts[filename] = body
        tokens = [w for w in nltk.word_tokenize(re.sub(r'[^a-z\s]', '', body.lower())) if w not in stop_words and len(w)>2]
        documents.append(tokens)
        visited.add(url)
        count += 1
        print(f"[{count}/{LIMIT}] Saved: {title}")

        if depth < MAX_DEPTH:
            for link in links:
                if link not in visited and len(visited) + len(queue) < LIMIT:
                    queue.append((link, depth + 1))

print(f"\n✅ Crawled {count} articles into '{OUTPUT_DIR}'")

# ---------------------- WORD FREQUENCY ----------------------
all_tokens = [token for doc in documents for token in doc]
word_freq = Counter(all_tokens)
with open(WORD_FREQ_CSV, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["Word", "Frequency"])
    for word, freq in word_freq.most_common():
        writer.writerow([word, freq])
print(f"✅ Word frequencies saved to '{WORD_FREQ_CSV}'")

# ---------------------- NAMED ENTITIES ----------------------
print("\n🔹 Sample Named Entities from first document:")
if documents:
    sample_text = " ".join(documents[0])
    doc_spacy = nlp(sample_text)
    for ent in doc_spacy.ents[:20]:
        print(ent.text, ent.label_)

# ---------------------- WORD CLOUD ----------------------
wordcloud = WordCloud(width=800, height=400, background_color='white').generate_from_frequencies(word_freq)
plt.figure(figsize=(15, 7))
plt.imshow(wordcloud, interpolation='bilinear')
plt.axis("off")
plt.show()

# ---------------------- TOPIC MODELING ----------------------
dictionary = corpora.Dictionary(documents)
corpus = [dictionary.doc2bow(doc) for doc in documents]
lda_model = models.LdaModel(corpus, num_topics=TOPIC_COUNT, id2word=dictionary, passes=10)
topic_words = {}
print("\n🔹 Topics detected:")
for i, topic in lda_model.print_topics(num_words=8):
    print(f"Topic {i+1}: {topic}")
    topic_words[i] = [w.split('*')[1].replace('"','') for w in topic.split('+')]

# ---------------------- SUMMARIZATION ----------------------
print("\n🔹 Generating summaries:")
for filename, text in all_texts.items():
    try:
        summary = summarization.summarize(text, ratio=SUMMARY_RATIO)
        if not summary.strip():
            summary = text[:500] + "..."
        with open(os.path.join(SUMMARY_DIR, filename), 'w', encoding='utf-8') as f:
            f.write(summary)
        print(f"Saved summary: {filename}")
    except Exception as e:
        print(f"Failed summarizing {filename}: {e}")

# ---------------------- CREATE PDF WITH TOC ----------------------
summary_files = sorted([f for f in os.listdir(SUMMARY_DIR) if f.endswith(".txt")])
toc = []

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.set_font("Arial", size=12)

# Cover page
pdf.add_page()
pdf.set_font("Arial", 'B', 20)
pdf.multi_cell(0, 10, "Mini-Encyclopedia of Crawled Wikipedia Articles")
pdf.ln(10)
pdf.set_font("Arial", '', 14)
pdf.multi_cell(0, 8, "Generated with Python NLP Pipeline\n\nContents below will show page numbers.")
pdf.add_page()

# Placeholder for TOC
toc_page_index = pdf.page_no()
pdf.set_font("Arial", 'B', 16)
pdf.multi_cell(0, 10, "Table of Contents\n")
toc_start_y = pdf.get_y()

for idx, filename in enumerate(summary_files, 1):
    with open(os.path.join(SUMMARY_DIR, filename), 'r', encoding='utf-8') as f:
        summary_text = f.read()

    pdf.add_page()
    page_number = pdf.page_no()
    title = filename.replace("_", " ").replace(".txt", "")
    toc.append((title, page_number))

    # Article Title
    pdf.set_font("Arial", 'B', 16)
    pdf.multi_cell(0, 10, f"{idx}. {title}")
    pdf.ln(3)

    # Topic highlight (top words from LDA)
    topic_idx = idx % TOPIC_COUNT
    top_words = ", ".join(topic_words.get(topic_idx, []))
    pdf.set_font("Arial", 'I', 12)
    pdf.multi_cell(0, 8, f"Topics: {top_words}")
    pdf.ln(3)

    # Summary
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 8, summary_text)

# Fill TOC
pdf.page = toc_page_index
pdf.set_y(toc_start_y)
pdf.set_font("Arial", '', 12)
for idx, (title, page_num) in enumerate(toc, 1):
    line = f"{idx}. {title} ........ {page_num}"
    pdf.multi_cell(0, 8, line)

pdf.output(PDF_FILE)
print(f"\n✅ Mini-encyclopedia PDF with TOC and topic highlights saved as '{PDF_FILE}'")