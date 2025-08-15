import re
from collections import Counter, defaultdict
from nltk.tokenize import word_tokenize
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime
import os
from transformers import pipeline

# -------------------- CONFIG --------------------
PRODUCTS = ["CocaCola", "Fanta", "Sprite", "Pepsi"]
LOW_STOCK_THRESHOLD = 5
TMP_DIR = "tmp_images"
PDF_FILE = f"WebPOS_Report_{datetime.now().strftime('%Y%m%d')}.pdf"

os.makedirs(TMP_DIR, exist_ok=True)

# -------------------- FETCH LOGS --------------------
def fetch_logs():
    return [
        "Sold 3 bottles of CocaCola on 15/08/2025",
        "Customer complained: Product was expired",
        "Sold 10 Pepsi bottles",
        "Customer said the service was excellent",
        "Sold 5 Fanta bottles",
        "Stock of Sprite is 2 units",
        "Sold 2 CocaCola bottles",
        "Customer complained: Late delivery of Pepsi",
        "New shipment: 50 units of Sprite arrived"
    ]

# -------------------- TOKENIZATION --------------------
def tokenize_logs(logs):
    return [word_tokenize(log) for log in logs]

# -------------------- RULE-BASED NLP --------------------
def extract_rule_based(tokenized_logs):
    product_sales = defaultdict(int)
    low_stock_alerts = []
    feedback_texts = []

    for tokens in tokenized_logs:
        log_lower = [t.lower() for t in tokens]
        products_in_log = [p for p in PRODUCTS if p.lower() in log_lower]
        numbers = [int(t) for t in tokens if t.isdigit()]

        for product in products_in_log:
            if "sold" in log_lower and numbers:
                product_sales[product] += numbers[0]

        if "stock" in log_lower and any(n < LOW_STOCK_THRESHOLD for n in numbers):
            low_stock_alerts.append(" ".join(tokens))

        if any(word in log_lower for word in ["complained", "excellent", "late", "expired"]):
            feedback_texts.append(" ".join(tokens))

    return product_sales, low_stock_alerts, feedback_texts

# -------------------- STATISTICS-BASED NLP --------------------
def extract_statistics(tokenized_logs):
    all_tokens = [t.lower() for tokens in tokenized_logs for t in tokens if t.isalpha()]
    return Counter(all_tokens)

# -------------------- DEEP LEARNING NLP --------------------
def extract_sentiment(feedback_texts):
    sentiment_analyzer = pipeline("sentiment-analysis")
    results = []
    for feedback in feedback_texts:
        result = sentiment_analyzer(feedback)[0]
        results.append({
            "feedback": feedback,
            "label": result['label'],
            "score": round(result['score'], 2)
        })
    return results

# -------------------- VISUALS --------------------
def generate_wordcloud(feedback_texts):
    text = " ".join(feedback_texts) if feedback_texts else "No feedback"
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text)
    wc_path = os.path.join(TMP_DIR, "wordcloud.png")
    wordcloud.to_file(wc_path)
    return wc_path

def generate_sales_chart(product_sales):
    plt.figure(figsize=(6,4))
    plt.bar(product_sales.keys(), product_sales.values(), color='skyblue')
    plt.title("Product Sales Count")
    plt.ylabel("Units Sold")
    plt.xlabel("Products")
    path = os.path.join(TMP_DIR, "sales_chart.png")
    plt.tight_layout()
    plt.savefig(path)
    plt.close()
    return path

# -------------------- PDF REPORT --------------------
def generate_pdf(product_sales, low_stock_alerts, feedback_sentiment, word_freq, wc_path, bar_chart_path):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Cover Page
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.multi_cell(0,10,"WebPOS Automated Report")
    pdf.set_font("Arial", '', 14)
    pdf.multi_cell(0,8,f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

    # Product Sales
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.multi_cell(0,10,"1. Product Sales Summary")
    pdf.set_font("Arial", '', 12)
    for product, qty in product_sales.items():
        pdf.multi_cell(0,8,f"{product}: {qty} units sold")
    pdf.ln(5)
    pdf.image(bar_chart_path, x=30, w=150)

    # Low Stock Alerts
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.multi_cell(0,10,"2. Low Stock Alerts")
    pdf.set_font("Arial", '', 12)
    if low_stock_alerts:
        for alert in low_stock_alerts:
            pdf.multi_cell(0,8,alert)
    else:
        pdf.multi_cell(0,8,"No low stock alerts detected.")

    # Customer Feedback & Sentiment
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.multi_cell(0,10,"3. Customer Feedback & Sentiment")
    pdf.set_font("Arial", '', 12)
    if feedback_sentiment:
        for res in feedback_sentiment:
            pdf.multi_cell(0,8,f"{res['feedback']}  =>  Sentiment: {res['label']} (score: {res['score']})")
    else:
        pdf.multi_cell(0,8,"No feedback detected.")
    pdf.ln(5)
    pdf.image(wc_path, x=20, w=170)

    # Word Frequency
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.multi_cell(0,10,"4. Most Common Words in Logs")
    pdf.set_font("Arial", '', 12)
    for word, freq in word_freq.most_common(10):
        pdf.multi_cell(0,8,f"{word}: {freq}")

    # Save PDF
    pdf.output(PDF_FILE)
    print(f"✅ PDF report generated: {PDF_FILE}")

# -------------------- MAIN --------------------
def main():
    logs = fetch_logs()
    tokenized_logs = tokenize_logs(logs)

    product_sales, low_stock_alerts, feedback_texts = extract_rule_based(tokenized_logs)
    word_freq = extract_statistics(tokenized_logs)
    feedback_sentiment = extract_sentiment(feedback_texts)

    wc_path = generate_wordcloud(feedback_texts)
    bar_chart_path = generate_sales_chart(product_sales)

    generate_pdf(product_sales, low_stock_alerts, feedback_sentiment, word_freq, wc_path, bar_chart_path)

if __name__ == "__main__":
    main()