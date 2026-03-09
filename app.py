import os
import uuid
import hashlib
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
from database import (
    init_db, insert_receipt, get_receipt, get_all_receipts, get_receipt_count,
    update_receipt, delete_receipt, get_monthly_summary, get_yearly_summary,
    get_category_totals, add_category_correction, get_category_corrections,
    find_by_hash,
)
from ocr_engine import process_receipt
from categorizer import categorize_receipt, CATEGORIES

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def compute_file_hash(file_path):
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


# --- Page Routes ---

@app.route('/')
def index():
    return render_template('index.html')


# --- Upload ---

@app.route('/api/receipts/upload', methods=['POST'])
def upload_receipt():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: JPG, PNG, PDF'}), 400

    # Save file
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext == 'jpeg':
        ext = 'jpg'
    stored_filename = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(UPLOAD_FOLDER, stored_filename)
    file.save(file_path)

    # Check file size
    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        os.remove(file_path)
        return jsonify({'error': 'File too large. Maximum 20 MB.'}), 400

    # Check for duplicate
    file_hash = compute_file_hash(file_path)
    existing = find_by_hash(file_hash)
    if existing:
        os.remove(file_path)
        return jsonify({
            'error': 'Duplicate receipt detected',
            'existing_id': existing['id'],
            'existing_vendor': existing['vendor_name'],
        }), 409

    # Run OCR
    try:
        ocr_data = process_receipt(file_path)
    except Exception as e:
        ocr_data = {
            'vendor_name': '',
            'amount': 0.0,
            'receipt_date': '',
            'raw_ocr_text': f'OCR Error: {str(e)}',
            'ocr_confidence': 0,
        }

    # Auto-categorize
    corrections = get_category_corrections()
    category = categorize_receipt(
        ocr_data.get('vendor_name', ''),
        ocr_data.get('raw_ocr_text', ''),
        corrections
    )

    # If no date found, use today
    receipt_date = ocr_data.get('receipt_date', '')
    if not receipt_date:
        from datetime import datetime
        receipt_date = datetime.now().strftime('%Y-%m-%d')

    # Insert
    receipt_data = {
        'filename': secure_filename(file.filename),
        'stored_filename': stored_filename,
        'file_type': ext,
        'raw_ocr_text': ocr_data.get('raw_ocr_text', ''),
        'vendor_name': ocr_data.get('vendor_name', ''),
        'amount': ocr_data.get('amount', 0.0),
        'currency': ocr_data.get('currency', 'USD'),
        'receipt_date': receipt_date,
        'category': category,
        'file_hash': file_hash,
    }

    receipt_id = insert_receipt(receipt_data)
    receipt = get_receipt(receipt_id)

    return jsonify({
        'success': True,
        'receipt': receipt,
        'ocr_confidence': ocr_data.get('ocr_confidence', 100),
    }), 201


# --- CRUD ---

@app.route('/api/receipts', methods=['GET'])
def list_receipts():
    filters = {
        'search': request.args.get('search', ''),
        'category': request.args.get('category', ''),
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'sort_by': request.args.get('sort_by', 'receipt_date'),
        'sort_dir': request.args.get('sort_dir', 'desc'),
    }
    receipts = get_all_receipts(filters)
    return jsonify({'receipts': receipts, 'total': len(receipts)})


@app.route('/api/receipts/<int:receipt_id>', methods=['GET'])
def get_receipt_route(receipt_id):
    receipt = get_receipt(receipt_id)
    if not receipt:
        return jsonify({'error': 'Receipt not found'}), 404
    return jsonify({'receipt': receipt})


@app.route('/api/receipts/<int:receipt_id>', methods=['PUT'])
def update_receipt_route(receipt_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Learn from category corrections
    if 'category' in data:
        existing = get_receipt(receipt_id)
        if existing and data['category'] != existing['category']:
            vendor = existing['vendor_name']
            if vendor:
                add_category_correction(vendor.lower().strip(), data['category'])
            data['is_manual_category'] = 1

    success = update_receipt(receipt_id, data)
    if not success:
        return jsonify({'error': 'Receipt not found or no valid fields'}), 404

    receipt = get_receipt(receipt_id)
    return jsonify({'success': True, 'receipt': receipt})


@app.route('/api/receipts/<int:receipt_id>', methods=['DELETE'])
def delete_receipt_route(receipt_id):
    receipt = get_receipt(receipt_id)
    if not receipt:
        return jsonify({'error': 'Receipt not found'}), 404

    # Delete file
    file_path = os.path.join(UPLOAD_FOLDER, receipt['stored_filename'])
    if os.path.exists(file_path):
        os.remove(file_path)

    delete_receipt(receipt_id)
    return jsonify({'success': True})


# --- Dashboard ---

@app.route('/api/dashboard/summary', methods=['GET'])
def dashboard_summary():
    from datetime import datetime

    now = datetime.now()
    year = request.args.get('year', now.year, type=int)
    month = request.args.get('month', now.month, type=int)

    monthly = get_monthly_summary(year, month)
    yearly = get_yearly_summary(year)
    category_totals = get_category_totals(f"{year}-01-01", f"{year}-12-31")
    total_count = get_receipt_count()

    # Find top category
    top_category = 'None'
    if category_totals:
        top_category = category_totals[0]['category']

    return jsonify({
        'monthly_total': monthly.get('total', 0),
        'monthly_by_category': monthly.get('by_category', {}),
        'yearly_total': yearly.get('total', 0),
        'yearly_by_month': yearly.get('by_month', []),
        'category_totals': category_totals,
        'total_count': total_count,
        'top_category': top_category,
        'current_year': year,
        'current_month': month,
    })


# --- Categories ---

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify({'categories': CATEGORIES})


# --- Serve uploaded files ---

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# --- Startup ---

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=False)
