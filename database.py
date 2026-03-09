import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'receiptvault.db')

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS receipts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    filename        TEXT NOT NULL,
    stored_filename TEXT NOT NULL UNIQUE,
    file_type       TEXT NOT NULL,
    raw_ocr_text    TEXT DEFAULT '',
    vendor_name     TEXT DEFAULT '',
    amount          REAL DEFAULT 0.0,
    currency        TEXT DEFAULT 'USD',
    receipt_date    TEXT DEFAULT '',
    category        TEXT DEFAULT 'Other',
    notes           TEXT DEFAULT '',
    is_manual_category INTEGER DEFAULT 0,
    file_hash       TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS category_corrections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_pattern  TEXT NOT NULL,
    assigned_category TEXT NOT NULL,
    frequency       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_receipts_date ON receipts(receipt_date);
CREATE INDEX IF NOT EXISTS idx_receipts_category ON receipts(category);
CREATE INDEX IF NOT EXISTS idx_receipts_vendor ON receipts(vendor_name);
CREATE INDEX IF NOT EXISTS idx_receipts_hash ON receipts(file_hash);
CREATE INDEX IF NOT EXISTS idx_corrections_vendor ON category_corrections(vendor_pattern);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def insert_receipt(data):
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO receipts
           (filename, stored_filename, file_type, raw_ocr_text, vendor_name,
            amount, currency, receipt_date, category, notes, is_manual_category, file_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.get('filename', ''),
            data['stored_filename'],
            data.get('file_type', ''),
            data.get('raw_ocr_text', ''),
            data.get('vendor_name', ''),
            data.get('amount', 0.0),
            data.get('currency', 'USD'),
            data.get('receipt_date', ''),
            data.get('category', 'Other'),
            data.get('notes', ''),
            data.get('is_manual_category', 0),
            data.get('file_hash', ''),
        )
    )
    receipt_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return receipt_id


def get_receipt(receipt_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_receipts(filters=None):
    filters = filters or {}
    conditions = []
    params = []

    if filters.get('search'):
        conditions.append("(vendor_name LIKE ? OR notes LIKE ? OR raw_ocr_text LIKE ?)")
        term = f"%{filters['search']}%"
        params.extend([term, term, term])

    if filters.get('category'):
        conditions.append("category = ?")
        params.append(filters['category'])

    if filters.get('start_date'):
        conditions.append("receipt_date >= ?")
        params.append(filters['start_date'])

    if filters.get('end_date'):
        conditions.append("receipt_date <= ?")
        params.append(filters['end_date'])

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    sort_by = filters.get('sort_by', 'receipt_date')
    if sort_by not in ('receipt_date', 'amount', 'vendor_name', 'category', 'created_at'):
        sort_by = 'receipt_date'
    sort_dir = 'ASC' if filters.get('sort_dir', 'desc').lower() == 'asc' else 'DESC'

    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM receipts WHERE {where_clause} ORDER BY {sort_by} {sort_dir}",
        params
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_receipt_count():
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM receipts").fetchone()
    conn.close()
    return row['cnt'] if row else 0


def update_receipt(receipt_id, data):
    allowed_fields = ['vendor_name', 'amount', 'currency', 'receipt_date',
                      'category', 'notes', 'is_manual_category']
    updates = []
    params = []
    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field])

    if not updates:
        return False

    updates.append("updated_at = datetime('now')")
    params.append(receipt_id)

    conn = get_connection()
    conn.execute(
        f"UPDATE receipts SET {', '.join(updates)} WHERE id = ?",
        params
    )
    conn.commit()
    conn.close()
    return True


def delete_receipt(receipt_id):
    conn = get_connection()
    conn.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
    conn.commit()
    conn.close()
    return True


def find_by_hash(file_hash):
    if not file_hash:
        return None
    conn = get_connection()
    row = conn.execute("SELECT * FROM receipts WHERE file_hash = ?", (file_hash,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_monthly_summary(year, month):
    conn = get_connection()
    date_prefix = f"{year:04d}-{month:02d}"

    total_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM receipts WHERE receipt_date LIKE ?",
        (f"{date_prefix}%",)
    ).fetchone()

    cat_rows = conn.execute(
        """SELECT category, COALESCE(SUM(amount), 0) as total, COUNT(*) as count
           FROM receipts WHERE receipt_date LIKE ?
           GROUP BY category ORDER BY total DESC""",
        (f"{date_prefix}%",)
    ).fetchall()

    conn.close()
    return {
        'total': total_row['total'],
        'by_category': {row['category']: {'total': row['total'], 'count': row['count']} for row in cat_rows}
    }


def get_yearly_summary(year):
    conn = get_connection()
    year_prefix = f"{year:04d}"

    total_row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM receipts WHERE receipt_date LIKE ?",
        (f"{year_prefix}%",)
    ).fetchone()

    month_rows = conn.execute(
        """SELECT substr(receipt_date, 6, 2) as month,
                  COALESCE(SUM(amount), 0) as total,
                  COUNT(*) as count
           FROM receipts
           WHERE receipt_date LIKE ?
           GROUP BY substr(receipt_date, 6, 2)
           ORDER BY month""",
        (f"{year_prefix}%",)
    ).fetchall()

    conn.close()

    by_month = []
    month_data = {row['month']: {'total': row['total'], 'count': row['count']} for row in month_rows}
    for m in range(1, 13):
        key = f"{m:02d}"
        by_month.append({
            'month': m,
            'total': month_data.get(key, {}).get('total', 0),
            'count': month_data.get(key, {}).get('count', 0),
        })

    return {
        'total': total_row['total'],
        'by_month': by_month
    }


def get_category_totals(start_date, end_date):
    conn = get_connection()
    rows = conn.execute(
        """SELECT category, COALESCE(SUM(amount), 0) as total, COUNT(*) as count
           FROM receipts
           WHERE receipt_date >= ? AND receipt_date <= ?
           GROUP BY category ORDER BY total DESC""",
        (start_date, end_date)
    ).fetchall()
    conn.close()
    return [{'category': row['category'], 'total': row['total'], 'count': row['count']} for row in rows]


def add_category_correction(vendor_pattern, category):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id, frequency FROM category_corrections WHERE vendor_pattern = ?",
        (vendor_pattern,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE category_corrections SET assigned_category = ?, frequency = frequency + 1 WHERE id = ?",
            (category, existing['id'])
        )
    else:
        conn.execute(
            "INSERT INTO category_corrections (vendor_pattern, assigned_category) VALUES (?, ?)",
            (vendor_pattern, category)
        )

    conn.commit()
    conn.close()


def get_category_corrections():
    conn = get_connection()
    rows = conn.execute(
        "SELECT vendor_pattern, assigned_category FROM category_corrections ORDER BY frequency DESC"
    ).fetchall()
    conn.close()
    return {row['vendor_pattern']: row['assigned_category'] for row in rows}
