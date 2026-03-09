import os
import re
import cv2
import numpy as np
from PIL import Image
from datetime import datetime

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None


def convert_pdf_to_images(pdf_path):
    """Convert PDF to list of PIL Images at 300 DPI."""
    if convert_from_path is None:
        raise RuntimeError("pdf2image is not installed")
    return convert_from_path(pdf_path, dpi=300)


def preprocess_image(pil_image):
    """Preprocess PIL Image for optimal OCR accuracy. Returns preprocessed PIL Image."""
    img_array = np.array(pil_image)

    # Convert to grayscale
    if len(img_array.shape) == 3:
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_array

    # Resize if too small — Tesseract needs decent resolution
    height, width = gray.shape
    if width < 1000:
        scale = 1000 / width
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Limit very large images to save memory and time
    height, width = gray.shape
    if max(height, width) > 3000:
        scale = 3000 / max(height, width)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    # Noise reduction — bilateral filter preserves text edges
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)

    # Adaptive threshold — handles uneven lighting on receipts
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
    )

    return Image.fromarray(thresh)


def extract_text(pil_image):
    """Run Tesseract OCR on a preprocessed PIL Image. Returns raw text."""
    if pytesseract is None:
        raise RuntimeError("pytesseract is not installed")

    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(pil_image, config=custom_config, lang='eng')
    return text


def extract_amount(text):
    """Extract the total amount from receipt text."""
    lines = text.strip().split('\n')

    # Patterns specifically for "total" lines
    total_patterns = [
        r'(?i)(?:grand\s+)?total\s*[:\s$]*(\d+[.,]\d{2})',
        r'(?i)(?:grand\s+)?total\s*[:\s]*\$?\s*(\d+[.,]\d{2})',
        r'(?i)amount\s+due\s*[:\s$]*(\d+[.,]\d{2})',
        r'(?i)balance\s+due\s*[:\s$]*(\d+[.,]\d{2})',
        r'(?i)total\s+charged?\s*[:\s$]*(\d+[.,]\d{2})',
        r'(?i)you\s+(?:paid|owe)\s*[:\s$]*(\d+[.,]\d{2})',
    ]

    # Search from bottom up — totals are at the bottom of receipts
    for pattern in total_patterns:
        for line in reversed(lines):
            if re.search(r'(?i)sub\s*total', line):
                continue
            match = re.search(pattern, line)
            if match:
                amount_str = match.group(1).replace(',', '.')
                try:
                    return float(amount_str)
                except ValueError:
                    continue

    # Fallback: find all dollar amounts, take the largest
    all_amounts = re.findall(r'\$\s*(\d+[.,]\d{2})', text)
    if not all_amounts:
        all_amounts = re.findall(r'(\d+\.\d{2})', text)

    if all_amounts:
        amounts = []
        for a in all_amounts:
            try:
                amounts.append(float(a.replace(',', '.')))
            except ValueError:
                continue
        if amounts:
            return max(amounts)

    return 0.0


def extract_date(text):
    """Extract date from receipt text. Returns ISO 8601 string or empty string."""
    # OCR often drops slashes in dates: "03/09/2026" → "0309/2026" or "03092026"
    # Try to fix common OCR date mangling near "Date:" keyword
    date_line_match = re.search(r'(?i)date[:\s]*(\d{4})[/-]?(\d{4})', text)
    if date_line_match:
        digits = date_line_match.group(1) + date_line_match.group(2)
        if len(digits) == 8:
            m, d, y = int(digits[0:2]), int(digits[2:4]), int(digits[4:8])
            if 1 <= m <= 12 and 1 <= d <= 31 and 2000 <= y <= 2099:
                try:
                    from datetime import datetime as dt
                    dt(y, m, d)
                    return f"{y:04d}-{m:02d}-{d:02d}"
                except ValueError:
                    pass

    # Pattern list ordered by specificity
    patterns = [
        # YYYY-MM-DD (ISO)
        (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'ymd'),
        # MM/DD/YYYY or MM-DD-YYYY
        (r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', 'mdy4'),
        # MM/DD/YY
        (r'(\d{1,2})[/-](\d{1,2})[/-](\d{2})\b', 'mdy2'),
        # Month DD, YYYY (e.g., "January 15, 2024")
        (r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})', 'named_mdy'),
        # DD Month YYYY (e.g., "15 January 2024")
        (r'(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})', 'named_dmy'),
    ]

    month_map = {
        'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
        'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
        'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
        'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12,
    }

    for pattern, fmt in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                if fmt == 'ymd':
                    y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                elif fmt == 'mdy4':
                    m, d, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
                elif fmt == 'mdy2':
                    m, d = int(match.group(1)), int(match.group(2))
                    y = 2000 + int(match.group(3))
                elif fmt == 'named_mdy':
                    m = month_map.get(match.group(1).lower()[:3], 0)
                    d, y = int(match.group(2)), int(match.group(3))
                elif fmt == 'named_dmy':
                    d = int(match.group(1))
                    m = month_map.get(match.group(2).lower()[:3], 0)
                    y = int(match.group(3))
                else:
                    continue

                if 1 <= m <= 12 and 1 <= d <= 31 and 2000 <= y <= 2099:
                    dt = datetime(y, m, d)
                    return dt.strftime('%Y-%m-%d')
            except (ValueError, OverflowError):
                continue

    return ''


# Known store/brand names to search for in full OCR text
# When Tesseract can't read a stylized logo, these patterns catch the name
# from elsewhere in the receipt (e.g. footer, URL, address line)
KNOWN_VENDORS = [
    # Grocery / General
    ('walmart', 'Walmart'), ('wal-mart', 'Walmart'), ('wal mart', 'Walmart'),
    ('almart', 'Walmart'),  # common OCR error: drops leading "W"
    ('target', 'Target'), ('costco', 'Costco'), ('sam\'s club', 'Sam\'s Club'),
    ('whole foods', 'Whole Foods'), ('trader joe', 'Trader Joe\'s'),
    ('kroger', 'Kroger'), ('safeway', 'Safeway'), ('publix', 'Publix'),
    ('aldi', 'Aldi'), ('lidl', 'Lidl'), ('meijer', 'Meijer'),
    ('wegmans', 'Wegmans'), ('sprouts', 'Sprouts'),
    # Fast food / Coffee
    ('starbucks', 'Starbucks'), ('tarbucks', 'Starbucks'),
    ('mcdonald', 'McDonald\'s'),
    ('chick-fil-a', 'Chick-fil-A'), ('chipotle', 'Chipotle'),
    ('subway', 'Subway'), ('wendy', 'Wendy\'s'), ('burger king', 'Burger King'),
    ('taco bell', 'Taco Bell'), ('popeyes', 'Popeyes'), ('five guys', 'Five Guys'),
    ('panera', 'Panera Bread'), ('dunkin', 'Dunkin\''),
    ('domino', 'Domino\'s'), ('papa john', 'Papa John\'s'),
    ('pizza hut', 'Pizza Hut'), ('kfc ', 'KFC'), ('shake shack', 'Shake Shack'),
    ('peet', 'Peet\'s Coffee'), ('tim horton', 'Tim Hortons'),
    # Transport
    ('uber', 'Uber'), ('lyft', 'Lyft'),
    ('shell', 'Shell'), ('chevron', 'Chevron'), ('exxon', 'ExxonMobil'),
    ('mobil', 'Mobil'),
    # Retail / Tech
    ('amazon', 'Amazon'), ('best buy', 'Best Buy'), ('bestbuy', 'Best Buy'),
    ('apple store', 'Apple Store'), ('home depot', 'Home Depot'),
    ('lowe\'s', 'Lowe\'s'), ('ikea', 'IKEA'),
    ('staples', 'Staples'), ('office depot', 'Office Depot'),
    # Pharmacy / Health
    ('cvs pharmacy', 'CVS'), ('cvs/', 'CVS'), ('walgreens', 'Walgreens'),
    ('rite aid', 'Rite Aid'),
    # Convenience
    ('7-eleven', '7-Eleven'), ('7 eleven', '7-Eleven'),
    ('wawa', 'Wawa'), ('sheetz', 'Sheetz'),
    # Department stores
    ('nordstrom', 'Nordstrom'), ('macy\'s', 'Macy\'s'), ('jcpenney', 'JCPenney'),
    ('marshalls', 'Marshalls'), ('tjmaxx', 'TJ Maxx'), ('tj maxx', 'TJ Maxx'),
    ('dollar tree', 'Dollar Tree'), ('dollar general', 'Dollar General'),
]


def extract_vendor(text):
    """
    Extract vendor name using 2-tier strategy:
    1. Search full OCR text for known store names (handles mangled logos)
    2. Fall back to first meaningful line of receipt
    """
    text_lower = text.lower()

    # Tier 1: Known vendor search across full text
    for pattern, display_name in KNOWN_VENDORS:
        if pattern in text_lower:
            return display_name

    # Tier 2: First meaningful line heuristic
    lines = text.strip().split('\n')
    for line in lines[:7]:  # check first 7 lines (expanded from 5)
        line = line.strip()
        if not line or len(line) < 3:
            continue
        # Skip lines that are only numbers/symbols
        if re.match(r'^[\d\s.,$#*=\-+/\\|]+$', line):
            continue
        # Skip address-like lines
        if re.match(r'^\d+\s+\w+\s+(st|ave|rd|blvd|dr|ln|way|street|avenue)', line, re.IGNORECASE):
            continue
        # Skip phone numbers
        if re.match(r'^[\d()\s+\-]{7,}$', line):
            continue
        # Skip very long lines (probably noise)
        if len(line) > 60:
            continue
        # Skip lines that are mostly garbage characters
        alpha_ratio = sum(1 for c in line if c.isalpha()) / len(line)
        if alpha_ratio < 0.4:
            continue
        return line.strip()

    return 'Unknown Vendor'


def assess_ocr_quality(raw_text):
    """Return a confidence score 0-100 based on heuristic checks."""
    score = 100

    text = raw_text.strip()
    if len(text) < 20:
        score -= 40

    if len(text) > 0:
        garbage_ratio = sum(1 for c in text if c in '|\\~^{}[]') / len(text)
        if garbage_ratio > 0.1:
            score -= 30

    if not re.search(r'\d+[.,]\d{2}', text):
        score -= 20

    return max(0, score)


def extract_currency(text):
    """Detect currency from receipt text. Returns currency code string."""
    text_lower = text.lower()

    # Explicit currency symbols/codes
    currency_patterns = [
        (r'EUR|euro|€', 'EUR'),
        (r'GBP|£|pound sterling', 'GBP'),
        (r'CHF|swiss franc|franken', 'CHF'),
        (r'CAD|CA\$|canadian', 'CAD'),
        (r'AUD|AU\$|australian', 'AUD'),
        (r'JPY|¥|yen', 'JPY'),
        (r'CNY|RMB|¥|yuan|renminbi', 'CNY'),
        (r'SEK|swedish kr', 'SEK'),
        (r'NOK|norwegian kr', 'NOK'),
        (r'DKK|danish kr', 'DKK'),
        (r'MXN|mexican peso', 'MXN'),
        (r'INR|₹|rupee', 'INR'),
    ]

    for pattern, code in currency_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return code

    # Default to USD
    return 'USD'


def parse_receipt_data(raw_text):
    """Parse raw OCR text to extract vendor, amount, date, currency. Returns dict."""
    return {
        'vendor_name': extract_vendor(raw_text),
        'amount': extract_amount(raw_text),
        'receipt_date': extract_date(raw_text),
        'currency': extract_currency(raw_text),
        'raw_ocr_text': raw_text,
        'ocr_confidence': assess_ocr_quality(raw_text),
    }


def process_receipt(file_path):
    """Main entry point. Takes file path, returns parsed receipt data dict."""
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == '.pdf':
            try:
                images = convert_pdf_to_images(file_path)
            except Exception as e:
                return {
                    'vendor_name': 'Unknown Vendor',
                    'amount': 0.0,
                    'receipt_date': '',
                    'currency': 'USD',
                    'raw_ocr_text': f'PDF conversion failed: {str(e)}',
                    'ocr_confidence': 0,
                }
            all_text = []
            for img in images:
                try:
                    preprocessed = preprocess_image(img)
                    all_text.append(extract_text(preprocessed))
                except Exception:
                    continue
            raw_text = '\n'.join(all_text)
        else:
            try:
                image = Image.open(file_path)
                image.verify()  # Check for corruption
                image = Image.open(file_path)  # Re-open after verify
            except Exception as e:
                return {
                    'vendor_name': 'Unknown Vendor',
                    'amount': 0.0,
                    'receipt_date': '',
                    'currency': 'USD',
                    'raw_ocr_text': f'Image file corrupted or unreadable: {str(e)}',
                    'ocr_confidence': 0,
                }
            preprocessed = preprocess_image(image)
            raw_text = extract_text(preprocessed)

        if not raw_text or len(raw_text.strip()) < 5:
            return {
                'vendor_name': 'Unknown Vendor',
                'amount': 0.0,
                'receipt_date': '',
                'currency': 'USD',
                'raw_ocr_text': raw_text or '(no text detected)',
                'ocr_confidence': 0,
            }

        return parse_receipt_data(raw_text)

    except Exception as e:
        return {
            'vendor_name': 'Unknown Vendor',
            'amount': 0.0,
            'receipt_date': '',
            'currency': 'USD',
            'raw_ocr_text': f'Processing error: {str(e)}',
            'ocr_confidence': 0,
        }
