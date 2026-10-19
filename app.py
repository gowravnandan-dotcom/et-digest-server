import os
import re
from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader
from docx import Document

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

EXCLUDED_PATTERNS = [
    r'\b(cricket|ipl|wicket|batsman|bcci|fifa|goal|messi|ronaldo|tennis|grand slam)\b',
    r'\b(bollywood|hollywood|box office|movie review|trailer|actor|actress|celebrity)\b',
    r'\b(murder|arrested|police custody|robbery|smuggling|bail plea)\b',
    r'\b(horoscope|astrology|zodiac|tarot)\b',
    r'\b(weather update|rainfall forecast|monsoon arrival|temperature dipped)\b'
]

MBA_CATEGORIES = {
    'Finance & Markets': [
        r'\b(rbi|repo rate|inflation|nifty|sensex|ipo|sebi|dividend|yield|capex|pe ratio|ebitda|liquidity|valuation|debt)\b',
        'WACC / Valuation Multiples'
    ],
    'Marketing & Brand Strategy': [
        r'\b(fmcg|brand campaign|ad spend|consumer behavior|cac|market share|e-commerce|d2c|retention|omnichannel)\b',
        'CAC / LTV & Brand Equity'
    ],
    'Operations & Supply Chain': [
        r'\b(logistics|freight|supply chain|inventory|warehousing|procurement|port congestion|semiconductor|chip shortage)\b',
        'Just-In-Time & Working Capital'
    ],
    'HR & Talent Strategy': [
        r'\b(hiring|layoffs|attrition|headcount|esop|campus placement|appraisal|variable pay|talent retention)\b',
        'Human Capital ROI'
    ],
    'Analytics & Tech Strategy': [
        r'\b(genai|artificial intelligence|cloud infrastructure|saas|data center|cybersecurity|enterprise tech|automation)\b',
        'Digital Transformation & Moat'
    ]
}

def extract_text_from_file(file_storage):
    filename = file_storage.filename.lower()
    text = ""
    if filename.endswith('.pdf'):
        reader = PdfReader(file_storage)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    elif filename.endswith('.docx'):
        doc = Document(file_storage)
        text = "\n".join([p.text for p in doc.paragraphs if p.text])
    elif filename.endswith('.txt'):
        text = file_storage.read().decode('utf-8', errors='ignore')
    return text

def is_noise(paragraph):
    for pattern in EXCLUDED_PATTERNS:
        if re.search(pattern, paragraph, re.IGNORECASE):
            return True
    return False

def categorize_and_tag(paragraph):
    for category, (regex, tag) in MBA_CATEGORIES.items():
        if re.search(regex, paragraph, re.IGNORECASE):
            return category, tag
    return 'General Strategy & Macro', 'Competitive Advantage'

def process_corpus(text, source_name):
    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 100]
    articles = []

    for p in paragraphs:
        if is_noise(p):
            continue
        category, tag = categorize_and_tag(p)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', p) if len(s.strip()) > 15]
        if not sentences:
            continue

        headline = sentences[0]
        bullets = sentences[1:4] if len(sentences) > 1 else [headline]

        articles.append({
            'headline': headline,
            'bullets': bullets,
            'category': category,
            'concept_tag': tag,
            'source': source_name
        })
    return articles

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No files provided'}), 400

    if len(files) > 10:
        return jsonify({'error': 'Maximum 10 files permitted per batch'}), 400

    all_articles = []
    processed_count = 0

    for file in files:
        if file.filename:
            raw_text = extract_text_from_file(file)
            if raw_text.strip():
                articles = process_corpus(raw_text, file.filename)
                all_articles.extend(articles)
                processed_count += 1

    return jsonify({
        'status': 'success',
        'files_processed': processed_count,
        'articles': all_articles
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
