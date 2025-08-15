import requests as rq
from bs4 import BeautifulSoup

# Step 1: Get the page
res = rq.get("https://en.wikipedia.org/wiki/Machine_learning")

# Step 2: Parse HTML
soup = BeautifulSoup(res.text, 'html.parser')

# Step 3: Find the main content area
content = soup.find('div', {'class': 'mw-parser-output'})

# Step 4: Extract paragraphs only
paragraphs = content.find_all('p')

# Step 5: Join paragraph text
article_text = "\n".join([p.get_text() for p in paragraphs])

# Step 6: Print a snippet
print(article_text[:1000])  # Only first 1000 chars for preview