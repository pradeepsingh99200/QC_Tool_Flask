from flask import Flask, request, render_template, jsonify, send_file
import os , re
import pdfplumber
from werkzeug.utils import secure_filename
from spellchecker import SpellChecker
from fpdf import FPDF
from pdf2image import convert_from_path
import pytesseract

app = Flask(__name__)

# Define upload directory
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global variable to hold the PDF and extracted text
pdf_path = ''
extracted_text = []
current_page = 0

spell = SpellChecker()

def convert_pdf_to_txt(pdf_path):
    extracted_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                extracted_text.append(text)
            else:
                # If text extraction fails, use OCR
                images = convert_from_path(pdf_path, first_page=pdf.pages.index(page)+1, last_page=pdf.pages.index(page)+1)
                for img in images:
                    text = pytesseract.image_to_string(img)
                    extracted_text.append(text)
    return extracted_text

def check_spelling(text):
    words = text.split()
    corrections = {}

    for word in words:
        # Ignore words that are numbers, symbols, or already uppercase (proper nouns, acronyms)
        if word.isdigit() or re.match(r'^\W+$', word) or word.isupper():
            continue

        # Check if the word is misspelled
        misspelled = spell.unknown([word])
        if misspelled:
            suggestions = spell.candidates(word)
            if suggestions:
                corrections[word] = list(suggestions)[:3]  # Get top 3 suggestions
    return corrections

def create_pdf(texts):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for text in texts:
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, text)
    
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'corrected_text.pdf')
    pdf.output(output_path)
    return output_path

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    global pdf_path, extracted_text, current_page
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded.'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file uploaded.'})
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(pdf_path) 

        # Convert PDF to text
        extracted_text = convert_pdf_to_txt(pdf_path)
        current_page = 0

        # Return success response with total pages and PDF file name
        return jsonify({'success': True, 'total_pages': len(extracted_text), 'filename': filename})

@app.route('/page/<int:page_number>', methods=['GET'])
def get_page(page_number):
    global current_page
    current_page = page_number
    text = extracted_text[page_number] if page_number < len(extracted_text) else ""
    spelling_errors = check_spelling(text)
    return jsonify({'page_number': page_number, 'text': text, 'spelling_errors': spelling_errors})

@app.route('/pdf/<path:filename>', methods=['GET'])
def serve_pdf(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/correct', methods=['POST'])
def correct_text():
    data = request.json
    text = data['text']
    output_pdf_path = create_pdf([text])  # Create new PDF with corrected text
    return jsonify({'success': True, 'output_pdf_path': output_pdf_path})
    
if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)  # Create upload directory if it doesn't exist
    app.run(debug=True)
