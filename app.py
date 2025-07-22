from flask import Flask, request, render_template, jsonify, send_from_directory
import os, re
import pdfplumber
from werkzeug.utils import secure_filename
from spellchecker import SpellChecker
from pdf2image import convert_from_path
import pytesseract
import language_tool_python
import fitz 
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

user_data = {}
spell = SpellChecker()
# grammar = language_tool_python.LanguageTool('en-US')
grammar = language_tool_python.LanguageToolPublicAPI('en-US')


# def convert_pdf_to_txt(pdf_path):
#     extracted_text = []
#     with pdfplumber.open(pdf_path) as pdf:
#         for page in pdf.pages:
#             text = page.extract_text()
#             if text:
#                 extracted_text.append(text)
#             else:
#                 images = convert_from_path(pdf_path, first_page=pdf.pages.index(page)+1, last_page=pdf.pages.index(page)+1)
#                 for img in images:
#                     text = pytesseract.image_to_string(img)
#                     extracted_text.append(text)
#     return extracted_text


def convert_pdf_to_txt(pdf_path):
    extracted_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                extracted_text.append(text)
            else:
                # OCR fallback
                images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
                for img in images:
                    text = pytesseract.image_to_string(img)
                    extracted_text.append(text)
    return extracted_text

def check_spelling_and_grammar(text):
    words = text.split()
    corrections = {}
    for word in words:
        if word.isdigit() or re.match(r'^[\W_]+$', word) or word.isupper():
            continue
        misspelled = spell.unknown([word])
        if misspelled:
            suggestions = spell.candidates(word)
            if suggestions:
                corrections[word] = list(suggestions)[:3]
    grammar_errors = grammar.check(text)
    grammar_suggestions = [error.message for error in grammar_errors]
    return corrections, grammar_suggestions

def correct_pdf_in_place(pdf_path, edited_texts):
    doc = fitz.open(pdf_path)

    for page_number, page in enumerate(doc):
        if page_number >= len(edited_texts):
            break

        original_page_text = page.get_text().strip().split()
        updated_page_text = edited_texts[page_number].strip().split()

        if len(updated_page_text) == 0:
            continue

        # Full block + span-based layout
        words = page.get_text("dict")["blocks"]
        word_index = 0

        for block in words:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    if word_index >= len(updated_page_text):
                        break
                    old_word = span["text"]
                    new_word = updated_page_text[word_index]

                    if old_word != new_word:
                        rect = fitz.Rect(span["bbox"])
                        font = span["font"]
                        size = span["size"]
                        color = fitz.utils.getColor("black") 

                        page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
                        page.insert_textbox(rect, new_word,
                                            fontsize=size,
                                            fontname="helv",  # Use supported font
                                            color=color,
                                            align=0)


                    word_index += 1

    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'corrected_text.pdf')
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return output_path



def add_comments_to_pdf(pdf_path, comments):
    doc = fitz.open(pdf_path)
    for comment in comments:
        page_num = comment.get("page", 0)
        text = comment.get("text", "")
        comment_text = comment.get("comment", "")
        page = doc[page_num]
        for block in page.search_for(text):
            page.add_highlight_annot(block)
            page.add_text_annot(block.tl, comment_text)
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'commented_text.pdf')
    doc.save(output_path)
    return output_path

@app.route('/')
def index():
    return render_template('index.html')

# @app.route('/upload', methods=['POST'])
# def upload_file():
#     if 'file' not in request.files:
#         return jsonify({'success': False, 'message': 'No file uploaded.'})
#     file = request.files['file']
#     if file.filename == '':
#         return jsonify({'success': False, 'message': 'No file uploaded.'})
#     if file and file.filename.endswith('.pdf'):
#         filename = secure_filename(file.filename)
#         pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#         file.save(pdf_path)

#         extracted_text = convert_pdf_to_txt(pdf_path)
#         session_id = str(os.urandom(16).hex())
#         user_data[session_id] = {
#             'pdf_path': pdf_path,
#             'extracted_text': extracted_text,
#             'edited_texts': extracted_text.copy(),
#             'comments': []
#         }
#         return jsonify({'success': True, 'session_id': session_id, 'total_pages': len(extracted_text), 'filename': filename})
#     return jsonify({'success': False, 'message': 'Invalid file type. Only PDFs are allowed.'})


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded.'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected.'})
    
    if file and file.filename.lower().endswith('.pdf'):
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(pdf_path)

        extracted_text = convert_pdf_to_txt(pdf_path)
        session_id = os.urandom(16).hex()

        user_data[session_id] = {
            'pdf_path': pdf_path,
            'extracted_text': extracted_text,
            'edited_texts': extracted_text.copy(),
            'comments': []
        }

        return jsonify({
            'success': True,
            'session_id': session_id,
            'total_pages': len(extracted_text),
            'filename': filename,
            'extracted_text': extracted_text  
        })

    return jsonify({'success': False, 'message': 'Invalid file type. Only PDFs allowed.'})

@app.route('/page/<session_id>/<int:page_number>', methods=['GET'])
def get_page(session_id, page_number):
    if session_id not in user_data:
        return jsonify({'success': False, 'message': 'Session not found.'})
    data = user_data[session_id]
    text = data['extracted_text'][page_number] if page_number < len(data['extracted_text']) else ""
    spelling_errors, grammar_suggestions = check_spelling_and_grammar(text)
    return jsonify({
        'success': True,
        'page_number': page_number,             
        'text': text,
        'spelling_errors': spelling_errors,
        'grammar_suggestions': grammar_suggestions
    })

@app.route('/correct/<session_id>', methods=['POST'])
def correct_text(session_id):
    if session_id not in user_data:
        return jsonify({'success': False, 'message': 'Session not found.'})
    data = request.json
    new_text = data.get('text', '')
    current_page = user_data[session_id].get('current_page', 0)
    user_data[session_id]['edited_texts'][current_page] = new_text
    output_pdf_path = correct_pdf_in_place(user_data[session_id]['pdf_path'], user_data[session_id]['edited_texts'])
    if os.path.exists(output_pdf_path):
        return jsonify({'success': True, 'output_pdf_path': '/uploads/corrected_text.pdf'})
    return jsonify({'success': False, 'message': 'Failed to create corrected PDF.'})


@app.route('/comment/<session_id>', methods=['POST'])
def add_comment(session_id):
    if session_id not in user_data:
        return jsonify({'success': False, 'message': 'Session not found.'})
    data = request.json
    user_data[session_id]['comments'].append(data)
    output_pdf_path = add_comments_to_pdf(user_data[session_id]['pdf_path'], user_data[session_id]['comments'])
    if os.path.exists(output_pdf_path):
        return jsonify({'success': True, 'output_pdf_path': '/uploads/commented_text.pdf'})
    return jsonify({'success': False, 'message': 'Failed to add comments.'})

@app.route('/uploads/<path:filename>', methods=['GET'])
def serve_uploads(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, mimetype='application/pdf')


@app.errorhandler(404)
def not_found_error(e):
    return jsonify({'success': False, 'message': 'Resource not found.'}), 404

@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({'success': False, 'message': 'An internal error occurred.'}), 500

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(host="0.0.0.0", port=10000)

# app.run(host='0.0.0.0', port=5000, debug=True)