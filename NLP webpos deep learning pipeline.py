import re
from collections import Counter, defaultdict
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime
import os
import smtplib
from email.message import EmailMessage

# --------- Deep Learning NLP ---------
from transformers import pipeline

# -------------------- CONFIG --------------------
PRODUCTS = ["CocaCola", "Fanta", "Sprite", "Pepsi"]
LOW_STOCK_THRESHOLD = 5
TMP_DIR = "tmp_images"
PDF_FILE = f"WebPOS_Report_{datetime.now().strftime('%Y%m%d')}.pdf"

EMAIL_SENDER = "youremail@example.com"
EMAIL_PASSWORD = "your_app_password"
EMAIL_RECEIVER = "manager@example.com"
SMTP_SERVER = "smtp.example.com"
SMTP_PORT = 587

# Ensure tmp directory exists
os.makedirs(TMP_DIR, exist_ok=True)

# -------------------- FETCH LOGS --------------------
def fetch_logs():
    """
    Replace this function with your database connection
    and query to fetch POS logs for the week.
    """
    logs = [
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
    return logs

# -------------------- RULE-BASED NLP --------------------
def extract_rule_based(logs):
    structured_logs = []
    low_stock_alerts = []
    feedback_texts = []
    product_sales = defaultdict(int)
    
    for log in logs:
        info = {}
        info['products'] = [p for p in PRODUCTS if p in log]
        qty_match = re.findall(r'\b\d+\b', log)
        info['numbers'] = [int(q) for q in qty_match]
        # Low stock
        if "stock" in log.lower():
            if any(int(n) < LOW_STOCK_THRESHOLD for n in qty_match):
                low_stock_alerts.append(log)
        # Feedback detection
        if any(word in log.lower() for word in ['complain', 'excellent', 'late', 'expired']):
            feedback_texts.append(log)
        # Product sales
        for product in info['products']:
            if "sold" in log.lower() and info['numbers']:
                product_sales[product] += info['numbers'][0]
        structured_logs.append(info)
    return structured_logs, low_stock_alerts, feedback_texts, product_sales

# -------------------- STATISTICS-BASED NLP --------------------
def extract_statistics_based(logs):
    tokens = []
    for log in logs:
        tokens.extend(re.findall(r'\b\w+\b', log.lower()))
    word_freq = Counter(tokens)
    return word_freq

# -------------------- DEEP LEARNING NLP --------------------
def extract_sentiment(feedbacks):
    sentiment_analyzer = pipeline("sentiment-analysis")
    results = []
    for feedback in feedbacks:
        result = sentiment_analyzer(feedback)[0]
        results.append({
            "feedback": feedback,
            "label": result['label'],
            "score": round(result['score'], 2)
        })
    return results

# -------------------- GENERATE VISUALS --------------------
def generate_wordcloud(feedback_texts):
    feedback_combined = " ".join(feedback_texts) if feedback_texts else "No customer feedback"
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(feedback_combined)
    wc_path = os.path.join(TMP_DIR, "feedback_wordcloud.png")
    wordcloud.to_file(wc_path)
    return wc_path

def generate_sales_chart(product_sales):
    plt.figure(figsize=(6,4))
    plt.bar(product_sales.keys(), product_sales.values(), color='skyblue')
    plt.title("Product Sales Count")
    plt.ylabel("Units Sold")
    plt.xlabel("Products")
    bar_chart_path = os.path.join(TMP_DIR, "bar_chart.png")
    plt.tight_layout()
    plt.savefig(bar_chart_path)
    plt.close()
    return bar_chart_path

# -------------------- GENERATE PDF --------------------
def generate_pdf(product_sales, low_stock_alerts, feedback_sentiment, word_freq, wc_path, bar_chart_path):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    # Cover
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
    # Low Stock
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.multi_cell(0,10,"2. Low Stock Alerts")
    pdf.set_font("Arial", '', 12)
    if low_stock_alerts:
        for alert in low_stock_alerts:
            pdf.multi_cell(0,8,alert)
    else:
        pdf.multi_cell(0,8,"No low stock alerts detected.")
    # Feedback + Sentiment
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
    return PDF_FILE

# -------------------- SEND EMAIL --------------------
def send_email(pdf_file):
    msg = EmailMessage()
    msg['Subject'] = "Weekly WebPOS Report"
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg.set_content("Attached is the weekly WebPOS report including sales, low stock alerts, and customer feedback analysis.")
    # Attach PDF
    with open(pdf_file, 'rb') as f:
        msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename=os.path.basename(pdf_file))
    # Send
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        smtp.send_message(msg)
    print(f"✅ Email sent to {EMAIL_RECEIVER}")

# -------------------- MAIN FUNCTION --------------------
def main():
    logs = fetch_logs()
    _, low_stock_alerts, feedback_texts, product_sales = extract_rule_based(logs)
    word_freq = extract_statistics_based(logs)
    feedback_sentiment = extract_sentiment(feedback_texts)
    wc_path = generate_wordcloud(feedback_texts)
    bar_chart_path = generate_sales_chart(product_sales)
    pdf_file = generate_pdf(product_sales, low_stock_alerts, feedback_sentiment, word_freq, wc_path, bar_chart_path)
    print(f"✅ PDF report generated: {pdf_file}")
    send_email(pdf_file)

if __name__ == "__main__":
    main()