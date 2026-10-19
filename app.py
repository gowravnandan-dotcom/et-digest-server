import os
import re
import traceback
from flask import Flask, render_template, request, jsonify
from pypdf import PdfReader
from docx import Document

app = Flask(__name__)
# Allow up to 100 MB uploads
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

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
    try:
        if filename.endswith('.pdf'):
            reader = PdfReader(file_storage)
            # Limit to first 25 pages to avoid memory exhaustion on free tier
            pages_to_read = min(len(reader.pages), 25)
            for i in range(pages_to_read):
                page_text = reader.pages[i].extract_text()
                if page_text:
                    text += page_text + "\n"
        elif filename.endswith('.docx'):
            doc = Document(file_storage)
            text = "\n".join([p.text for p in doc.paragraphs if p.text])
        elif filename.endswith('.txt'):
            text = file_storage.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error extracting {filename}: {e}")
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
    # Split paragraphs by double newline or multiple spaces
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if len(p.strip()) > 80]
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
            'headline': headline[:160] + ('...' if len(headline) > 160 else ''),
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
    try:
        if 'files' not in request.files:
            return jsonify({'status': 'error', 'error': 'No file field received'}), 400

        files = request.files.getlist('files')
        if not files or files[0].filename == '':
            return jsonify({'status': 'error', 'error': 'No files selected'}), 400

        if len(files) > 10:
            return jsonify({'status': 'error', 'error': 'Maximum 10 files permitted per batch'}), 400

        all_articles = []
        processed_count = 0

        for file in files:
            if file and file.filename:
                raw_text = extract_text_from_file(file)
                if raw_text.strip():
                    articles = process_corpus(raw_text, file.filename)
                    all_articles.extend(articles)
                    processed_count += 1

        if not all_articles:
            return jsonify({
                'status': 'success',
                'files_processed': processed_count,
                'articles': [],
                'message': 'No text could be extracted. Make sure the PDF contains selectable text (not scanned images).'
            })

        return jsonify({
            'status': 'success',
            'files_processed': processed_count,
            'articles': all_articles[:50]  # Cap response to top 50 briefs for fast load
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'status': 'error', 'error': 'Total file size exceeds 100 MB limit.'}), 413

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
