# ReceiptVault -- Community Edition

Free, local, offline receipt organizer for freelancers and small businesses. Drop receipt photos, PDFs, or screenshots -- OCR extracts vendor, amount, date, and auto-categorizes.

This is the **Community Edition** (free version). For dashboard charts, CSV/Excel export, standalone EXE builds, and more, check out **ReceiptVault Pro**: [https://gumroad.com/l/Receiptvault](https://gumroad.com/l/receiptvault)

## Quick Start

### Prerequisites

- **Python 3.9+** -- [https://www.python.org/downloads/](https://www.python.org/downloads/)
- **Tesseract OCR** -- needed for receipt text extraction
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt install tesseract-ocr`
  - Windows: [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
- **Poppler** (optional, for PDF receipt support)
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `sudo apt install poppler-utils`

### Install & Run

```bash
pip install -r requirements.txt
python app.py
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080) in your browser.

## Features (Community Edition)

- OCR-powered data extraction from receipt photos and PDFs
- Automatic vendor detection (60+ known stores)
- Smart 3-tier categorization with learning from your corrections
- Multi-currency support (USD, EUR, GBP, CHF, CAD, and more)
- Duplicate detection via file hashing
- Dashboard with spending summary stats (monthly total, yearly total, receipt count, top category)
- Receipt list with search, filter, and sort
- Receipt detail view with inline editing
- Welcome wizard for first-time users
- 100% offline -- your data never leaves your computer

## Pro Version

ReceiptVault Pro adds:

- Dashboard charts (pie chart by category, monthly trend bar chart)
- CSV export
- Formatted Excel export with category breakdown sheet
- Standalone EXE build (no Python install needed for end users)
- One-click launcher scripts (Windows & macOS/Linux)

**Get ReceiptVault Pro:** [https://gumroad.com/l/Receiptvault](https://gumroad.com/l/receiptvault)

## Tech Stack

- Python, Flask, SQLite
- Tesseract OCR, OpenCV, Pillow
- Vanilla HTML/CSS/JS (no frameworks, no npm)

## Project Structure

```
receiptVault-community/
├── app.py              # Flask backend + API routes
├── database.py         # SQLite data access layer
├── ocr_engine.py       # Image preprocessing + Tesseract + parsing
├── categorizer.py      # Keyword-based auto-categorization
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # SPA shell
└── static/
    ├── css/style.css   # UI styles
    ├── js/app.js       # Frontend SPA logic
    └── uploads/        # Stored receipt images (auto-created)
```

## License

ReceiptVault Community Edition is free for personal use.
