import re
import os
import csv
from collections import defaultdict, Counter
from datetime import datetime
from gensim.summarization import summarize
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# -------------------- SETTINGS --------------------
PRODUCTS = ["CocaCola", "Fanta", "Sprite", "Pepsi"]
POS_LOGS = [
    "Sold 3 bottles of CocaCola on 15/08/2025 for $9 each",
    "Customer complained: Product was expired",
    "Stock of Fanta is 2 units",
    "New shipment: 50 units of Sprite arrived",
    "Sold 10 Pepsi bottles on 16/08/2025 for $12 each",
    "Customer said the service was excellent"
]
LOW_STOCK_THRESHOLD = 5
TMP_DIR = "tmp_images"
PDF_FILE = "WebPOS_Weekly_Report.pdf"
EMAIL_RECEIVER = "manager@example.com"
EMAIL_SENDER = "your_email@example.com"
EMAIL_PASSWORD = "your_email_password"
os.makedirs(TMP_DIR, exist_ok=True)
# ---------------------------------------------------

# -------------------- RULE-BASED EXTRACTION --------------------
def extract_info(text):
    info = {}
    info['products'] = [p for p in PRODUCTS if p in text]
    qty_match = re.findall(r'\b\d+\b', text)
    info['numbers'] = [int(q) for q in qty_match]
    date_match = re.findall(r'\b\d{2}/\d{2}/\d{4}\b', text)
    info['dates'] = date_match
    price_match = re.findall(r'\$\d+', text)
    info['prices'] = price_match
    sentiment_keywords = ["bad", "poor", "excellent", "expired", "late"]
    info['sentiment'] = [word for word in sentiment_keywords if word in text.lower()]
    if "stock" in text.lower():
        nums = [int(n) for n in re.findall(r'\d+', text)]
        info['low_stock_alert'] = any(n < LOW_STOCK_THRESHOLD for n in nums)
    else:
        info['low_stock_alert'] = False
    return info

# -------------------- PROCESS LOGS --------------------
structured_logs = []
all_texts_for_summary = []
low_stock_alerts = []
feedback_texts = []
product_sales_over_time = defaultdict(list)

for log in POS_LOGS:
    extracted = extract_info(log)
    structured_logs.append(extracted)
    all_texts_for_summary.append(log)
    if extracted['low_stock_alert']:
        low_stock_alerts.append(log)
    if extracted['sentiment']:
        feedback_texts.append(log)
    # Track sales per date for trend chart
    for date in extracted['dates']:
        for product in extracted['products']:
            product_sales_over_time[product].append((datetime.strptime(date, "%d/%m/%Y"), extracted['numbers'][0] if extracted['numbers'] else 0))

# -------------------- DAILY / WEEKLY SUMMARY --------------------
combined_text = "\n".join(all_texts_for_summary)
try:
    report_summary = summarize(combined_text, ratio=0.3)
    if not report_summary.strip():
        report_summary = combined_text[:500] + "..."
except:
    report_summary = combined_text[:500] + "..."

# -------------------- SALES CHARTS --------------------
# Total product sales
product_counter = Counter()
for log in structured_logs:
    for p in log['products']:
        product_counter[p] += 1

# Bar chart
plt.figure(figsize=(6,4))
plt.bar(product_counter.keys(), product_counter.values(), color='skyblue')
plt.title("Product Sales Count")
plt.ylabel("Units Sold")
plt.xlabel("Products")
bar_chart_path = os.path.join(TMP_DIR, "bar_chart.png")
plt.tight_layout()
plt.savefig(bar_chart_path)
plt.close()

# Trend chart
plt.figure(figsize=(6,4))
for product, data in product_sales_over_time.items():
    dates, qty = zip(*sorted(data)) if data else ([], [])
    plt.plot(dates, qty, marker='o', label=product)
plt.title("Product Sales Over Time")
plt.xlabel("Date")
plt.ylabel("Units Sold")
plt.legend()
trend_chart_path = os.path.join(TMP_DIR, "trend_chart.png")
plt.tight_layout()
plt.savefig(trend_chart_path)
plt.close()

# Word Cloud
feedback_combined = " ".join(feedback_texts) if feedback_texts else "No customer feedback"
wordcloud = WordCloud(width=600, height=300, background_color='white').generate(feedback_combined)
wc_path = os.path.join(TMP_DIR, "feedback_wordcloud.png")
wordcloud.to_file(wc_path)

# -------------------- CREATE PDF --------------------
pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)

pdf.add_page()
pdf.set_font("Arial", 'B', 20)
pdf.multi_cell(0,10,"WebPOS Weekly Sales Report")
pdf.set_font("Arial", '', 14)
pdf.multi_cell(0,8,"Generated automatically using NLP & Analytics\n")

# Summary
pdf.add_page()
pdf.set_font("Arial", 'B', 16)
pdf.multi_cell(0,10,"1. Summary")
pdf.set_font("Arial", '', 12)
pdf.multi_cell(0,8, report_summary)

# Product Sales
pdf.add_page()
pdf.set_font("Arial", 'B', 16)
pdf.multi_cell(0,10,"2. Product Sales Count")
pdf.image(bar_chart_path, x=30, w=150)

# Sales Trends
pdf.add_page()
pdf.set_font("Arial", 'B', 16)
pdf.multi_cell(0,10,"3. Sales Trend Over Time")
pdf.image(trend_chart_path, x=20, w=170)

# Low Stock Alerts
pdf.add_page()
pdf.set_font("Arial", 'B', 16)
pdf.multi_cell(0,10,"4. Low Stock Alerts")
pdf.set_font("Arial", '', 12)
if low_stock_alerts:
    for alert in low_stock_alerts:
        pdf.multi_cell(0,8,alert)
else:
    pdf.multi_cell(0,8,"No low stock alerts this week.")

# Customer Feedback
pdf.add_page()
pdf.set_font("Arial", 'B', 16)
pdf.multi_cell(0,10,"5. Customer Feedback & Word Cloud")
pdf.set_font("Arial", '', 12)
if feedback_texts:
    for feedback in feedback_texts:
        pdf.multi_cell(0,8,feedback)
else:
    pdf.multi_cell(0,8,"No notable feedback.")
pdf.ln(5)
pdf.image(wc_path, x=30, w=150)

pdf.output(PDF_FILE)
print(f"✅ Weekly report PDF saved as '{PDF_FILE}'")

# -------------------- EMAIL REPORT --------------------
def send_email(sender, password, receiver, subject, body, attachment):
    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = subject
    msg.attach(MIMEBase('application', 'octet-stream'))

    # Attach PDF
    with open(attachment, "rb") as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(attachment)}"')
        msg.attach(part)

    # Send email
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

# Uncomment the next line and fill your credentials to send automatically
# send_email(EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER, "WebPOS Weekly Report", "Attached is the weekly report.", PDF_FILE)