from flask import Flask, request, render_template, jsonify, send_from_directory
import os, re
import pdfplumber
from werkzeug.utils import secure_filename
from spellchecker import SpellChecker
from fpdf import FPDF
import requests
import traceback

app = Flask(__name__)

# Define upload directory
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global state replaced with a dictionary for user sessions
user_data = {}

spell = SpellChecker()
# grammar = language_tool_python.LanguageTool('en-US')

def convert_pdf_to_txt(pdf_path):
    """Extracts text from a PDF file (No OCR, works on Vercel)."""
    extracted_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                extracted_text.append(text)
    return extracted_text

# Function to check grammar via the LanguageTool API
def check_grammar_with_api(text):
    """Uses the LanguageTool API to check grammar."""
    url = "https://api.languagetool.org/v2/check"
    params = {
        "text": text,
        "language": "en-US",
    }
    response = requests.post(url, data=params)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": "Failed to check grammar"}

def check_spelling_and_grammar(text):
    """Check spelling and grammar using LanguageTool API."""
    spelling_errors = {}  # Your current spell checker logic
    grammar_suggestions = []

    # Check grammar with API
    grammar_response = check_grammar_with_api(text)
    if "error" not in grammar_response:
        for match in grammar_response.get("matches", []):
            grammar_suggestions.append(match["message"])

    return spelling_errors, grammar_suggestions



def create_pdf(texts):
    """Creates a PDF from a list of text pages."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for text in texts:
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, text)

    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'corrected_text.pdf')
    pdf.output(output_path)  # Save the file
    return output_path

@app.route('/')
def index():
    return render_template('index.html')

@app.errorhandler(Exception)
def handle_exception(error):
    """Handles all exceptions and logs them."""
    tb_str = traceback.format_exception(type(error), error, error.__traceback__)
    print("".join(tb_str))  # This will log the error to Vercel logs
    return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded.'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected.'}), 400
    if file and file.filename.endswith('.pdf'):
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(pdf_path)

        # Extract text from PDF
        extracted_text = convert_pdf_to_txt(pdf_path)

        session_id = str(os.urandom(16).hex())
        user_data[session_id] = {
            'pdf_path': pdf_path,
            'extracted_text': extracted_text,
            'current_page': 0
        }

        return jsonify({'success': True, 'session_id': session_id, 'total_pages': len(extracted_text), 'filename': filename})

    return jsonify({'success': False, 'message': 'Invalid file type. Only PDFs are allowed.'}), 400


@app.route('/page/<session_id>/<int:page_number>', methods=['GET'])
def get_page(session_id, page_number):
    if session_id not in user_data:
        return jsonify({'success': False, 'message': 'Session not found.'})

    data = user_data[session_id]
    text = data['extracted_text'][page_number] if page_number < len(data['extracted_text']) else ""
    spelling_errors, grammar_suggestions = check_spelling_and_grammar(text)

    return jsonify({'success': True, 'page_number': page_number, 'text': text, 'spelling_errors': spelling_errors, 'grammar_suggestions': grammar_suggestions})

@app.route('/correct/<session_id>', methods=['POST'])
def correct_text(session_id):
    if session_id not in user_data:
        return jsonify({'success': False, 'message': 'Session not found.'})

    data = request.json
    text = data['text']

    output_pdf_path = create_pdf([text])
    if os.path.exists(output_pdf_path):
        return jsonify({'success': True, 'output_pdf_path': '/uploads/corrected_text.pdf'})
    return jsonify({'success': False, 'message': 'Failed to create corrected PDF.'})

@app.route('/uploads/<path:filename>', methods=['GET'])
def serve_uploads(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.errorhandler(404)
def not_found_error(e):
    return jsonify({'success': False, 'message': 'Resource not found.'}), 404

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app = app