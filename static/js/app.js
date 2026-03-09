/* ReceiptVault — Frontend SPA Logic */

const CATEGORY_COLORS = {
    'Food & Dining': '#f59e0b',
    'Transport': '#3b82f6',
    'Software & Tech': '#8b5cf6',
    'Office Supplies': '#6b7280',
    'Utilities': '#10b981',
    'Entertainment': '#ec4899',
    'Healthcare': '#ef4444',
    'Other': '#9ca3af',
};

const CATEGORY_BADGES = {
    'Food & Dining': 'badge-food',
    'Transport': 'badge-transport',
    'Software & Tech': 'badge-software',
    'Office Supplies': 'badge-office',
    'Utilities': 'badge-utilities',
    'Entertainment': 'badge-entertainment',
    'Healthcare': 'badge-healthcare',
    'Other': 'badge-other',
};

/* === State === */
const state = {
    currentView: 'dashboard',
    receipts: [],
    categories: [],
    dashboardData: null,
    sortBy: 'receipt_date',
    sortDir: 'desc',
    uploadQueue: [],
    isUploading: false,
};

/* === API Layer === */
const api = {
    async uploadReceipt(file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch('/api/receipts/upload', { method: 'POST', body: formData });
        return res.json();
    },
    async getReceipts(filters = {}) {
        const params = new URLSearchParams();
        Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });
        const res = await fetch(`/api/receipts?${params}`);
        return res.json();
    },
    async getReceipt(id) {
        const res = await fetch(`/api/receipts/${id}`);
        return res.json();
    },
    async updateReceipt(id, data) {
        const res = await fetch(`/api/receipts/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },
    async deleteReceipt(id) {
        const res = await fetch(`/api/receipts/${id}`, { method: 'DELETE' });
        return res.json();
    },
    async getDashboard(year, month) {
        const params = new URLSearchParams();
        if (year) params.set('year', year);
        if (month) params.set('month', month);
        const res = await fetch(`/api/dashboard/summary?${params}`);
        return res.json();
    },
    async getCategories() {
        const res = await fetch('/api/categories');
        return res.json();
    },
};

/* === Initialization === */
document.addEventListener('DOMContentLoaded', async () => {
    // Load categories
    try {
        const catData = await api.getCategories();
        state.categories = catData.categories || [];
    } catch (e) {
        state.categories = Object.keys(CATEGORY_COLORS);
    }

    populateCategorySelects();
    bindNavigation();
    bindUploadZone();
    bindFilters();
    bindSorting();
    bindModalEvents();
    bindWelcome();

    showView('dashboard');
});

/* === Welcome / First-Run === */
function bindWelcome() {
    const welcomed = localStorage.getItem('receiptvault_welcomed');
    if (!welcomed) {
        document.getElementById('welcome-overlay').classList.remove('hidden');
    }
    document.getElementById('welcome-start').addEventListener('click', () => {
        localStorage.setItem('receiptvault_welcomed', '1');
        document.getElementById('welcome-overlay').classList.add('hidden');
        showView('receipts');
    });
}

/* === Navigation === */
function bindNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => showView(btn.dataset.view));
    });
}

function showView(viewName) {
    state.currentView = viewName;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    const view = document.getElementById(`view-${viewName}`);
    const btn = document.querySelector(`.nav-btn[data-view="${viewName}"]`);
    if (view) view.classList.add('active');
    if (btn) btn.classList.add('active');

    if (viewName === 'dashboard') loadDashboard();
    if (viewName === 'receipts') loadReceipts();
}

/* === Dashboard === */
async function loadDashboard() {
    try {
        const data = await api.getDashboard();
        state.dashboardData = data;

        document.getElementById('stat-monthly').textContent = formatCurrency(data.monthly_total);
        document.getElementById('stat-yearly').textContent = formatCurrency(data.yearly_total);
        document.getElementById('stat-count').textContent = data.total_count;
        document.getElementById('stat-top-cat').textContent = data.top_category || 'None';

        renderRecentReceipts();
    } catch (e) {
        console.error('Dashboard load failed:', e);
    }
}

async function renderRecentReceipts() {
    try {
        const data = await api.getReceipts({ sort_by: 'created_at', sort_dir: 'desc' });
        const recent = (data.receipts || []).slice(0, 5);
        const container = document.getElementById('recent-list');

        if (recent.length === 0) {
            container.innerHTML = '<p style="color:var(--text-muted);font-size:0.9rem;">No receipts yet.</p>';
            return;
        }

        container.innerHTML = recent.map(r => `
            <div class="recent-item" data-id="${r.id}">
                <div class="recent-item-left">
                    <span class="recent-vendor">${esc(r.vendor_name || 'Unknown')}</span>
                    <span class="recent-date">${r.receipt_date || 'No date'}</span>
                </div>
                <span class="recent-amount">${formatAmount(r.amount, r.currency)}</span>
            </div>
        `).join('');

        container.querySelectorAll('.recent-item').forEach(el => {
            el.addEventListener('click', () => openModal(parseInt(el.dataset.id)));
        });
    } catch (e) {
        console.error('Recent receipts load failed:', e);
    }
}

/* === Upload === */
function bindUploadZone() {
    const zone = document.getElementById('upload-zone');
    const fileInput = document.getElementById('file-input');
    let dragCounter = 0;

    zone.addEventListener('click', () => fileInput.click());

    zone.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        zone.classList.add('drag-over');
    });
    zone.addEventListener('dragover', (e) => e.preventDefault());
    zone.addEventListener('dragleave', () => {
        dragCounter--;
        if (dragCounter === 0) zone.classList.remove('drag-over');
    });
    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        zone.classList.remove('drag-over');
        const files = Array.from(e.dataTransfer.files);
        queueUploads(files);
    });

    fileInput.addEventListener('change', () => {
        const files = Array.from(fileInput.files);
        queueUploads(files);
        fileInput.value = '';
    });
}

function queueUploads(files) {
    state.uploadQueue.push(...files);
    if (!state.isUploading) processUploadQueue();
}

async function processUploadQueue() {
    if (state.uploadQueue.length === 0) {
        state.isUploading = false;
        document.getElementById('upload-progress').classList.add('hidden');
        loadReceipts();
        return;
    }

    state.isUploading = true;
    const progressEl = document.getElementById('upload-progress');
    const fillEl = document.getElementById('progress-fill');
    const textEl = document.getElementById('progress-text');
    progressEl.classList.remove('hidden');

    const total = state.uploadQueue.length;
    let processed = 0;

    while (state.uploadQueue.length > 0) {
        const file = state.uploadQueue.shift();
        processed++;
        const pct = Math.round((processed / (processed + state.uploadQueue.length)) * 100);
        fillEl.style.width = pct + '%';
        textEl.textContent = `Processing ${file.name} (${processed}/${processed + state.uploadQueue.length})...`;

        try {
            const result = await api.uploadReceipt(file);
            if (result.error) {
                if (result.existing_id) {
                    showToast(`Duplicate: ${file.name} already exists`, 'info');
                } else {
                    showToast(`Error: ${result.error}`, 'error');
                }
            } else {
                const confidence = result.ocr_confidence || 100;
                if (confidence < 40) {
                    showToast(`Uploaded ${file.name} (low OCR confidence - please verify)`, 'info');
                } else {
                    showToast(`Uploaded ${file.name}`, 'success');
                }
            }
        } catch (e) {
            showToast(`Failed to upload ${file.name}`, 'error');
        }
    }

    fillEl.style.width = '100%';
    textEl.textContent = 'All done!';
    setTimeout(() => {
        progressEl.classList.add('hidden');
        fillEl.style.width = '0%';
    }, 1500);

    state.isUploading = false;
    loadReceipts();
}

/* === Receipt Table === */
function bindFilters() {
    const search = document.getElementById('filter-search');
    const category = document.getElementById('filter-category');
    const start = document.getElementById('filter-start');
    const end = document.getElementById('filter-end');
    const clear = document.getElementById('filter-clear');

    let debounceTimer;
    search.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(loadReceipts, 300);
    });
    category.addEventListener('change', loadReceipts);
    start.addEventListener('change', loadReceipts);
    end.addEventListener('change', loadReceipts);
    clear.addEventListener('click', () => {
        search.value = '';
        category.value = '';
        start.value = '';
        end.value = '';
        loadReceipts();
    });
}

function bindSorting() {
    document.querySelectorAll('.receipt-table th.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const field = th.dataset.sort;
            if (state.sortBy === field) {
                state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc';
            } else {
                state.sortBy = field;
                state.sortDir = 'desc';
            }
            // Update visual indicator
            document.querySelectorAll('.receipt-table th').forEach(t => {
                t.classList.remove('sort-asc', 'sort-desc');
            });
            th.classList.add(state.sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
            loadReceipts();
        });
    });
}

async function loadReceipts() {
    const filters = {
        search: document.getElementById('filter-search').value,
        category: document.getElementById('filter-category').value,
        start_date: document.getElementById('filter-start').value,
        end_date: document.getElementById('filter-end').value,
        sort_by: state.sortBy,
        sort_dir: state.sortDir,
    };

    try {
        const data = await api.getReceipts(filters);
        state.receipts = data.receipts || [];
        renderReceiptTable(state.receipts);
    } catch (e) {
        console.error('Load receipts failed:', e);
    }
}

function renderReceiptTable(receipts) {
    const tbody = document.getElementById('receipt-tbody');
    const emptyState = document.getElementById('empty-state');
    const table = document.getElementById('receipt-table');

    if (receipts.length === 0) {
        tbody.innerHTML = '';
        table.style.display = 'none';
        emptyState.classList.remove('hidden');
        return;
    }

    table.style.display = '';
    emptyState.classList.add('hidden');

    tbody.innerHTML = receipts.map(r => `
        <tr data-id="${r.id}">
            <td>${r.receipt_date || 'No date'}</td>
            <td>${esc(r.vendor_name || 'Unknown')}</td>
            <td style="font-weight:600;">${formatAmount(r.amount, r.currency)}</td>
            <td><span class="badge ${CATEGORY_BADGES[r.category] || 'badge-other'}">${esc(r.category)}</span></td>
            <td>
                <button class="btn-icon" title="View details" onclick="event.stopPropagation(); openModal(${r.id})">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
            </td>
        </tr>
    `).join('');

    tbody.querySelectorAll('tr').forEach(row => {
        row.addEventListener('click', () => openModal(parseInt(row.dataset.id)));
    });
}

/* === Modal === */
function bindModalEvents() {
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.querySelector('.modal-overlay').addEventListener('click', closeModal);
    document.getElementById('modal-save').addEventListener('click', saveModal);
    document.getElementById('modal-delete').addEventListener('click', deleteFromModal);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });
}

async function openModal(receiptId) {
    try {
        const data = await api.getReceipt(receiptId);
        const r = data.receipt;
        if (!r) return;

        document.getElementById('modal-id').value = r.id;
        document.getElementById('modal-vendor').value = r.vendor_name || '';
        document.getElementById('modal-amount').value = r.amount || 0;
        document.getElementById('modal-date').value = r.receipt_date || '';
        document.getElementById('modal-notes').value = r.notes || '';
        document.getElementById('modal-ocr-text').textContent = r.raw_ocr_text || '(no OCR text)';

        // Set currency
        const currSelect = document.getElementById('modal-currency');
        if (currSelect) {
            currSelect.value = r.currency || 'USD';
        }

        // Populate category dropdown
        const catSelect = document.getElementById('modal-category');
        catSelect.innerHTML = state.categories.map(c =>
            `<option value="${c}" ${c === r.category ? 'selected' : ''}>${c}</option>`
        ).join('');

        // Show image
        const imageContainer = document.getElementById('modal-image');
        if (r.file_type === 'pdf') {
            imageContainer.innerHTML = `<embed src="/uploads/${r.stored_filename}" type="application/pdf" width="100%" height="500px">`;
        } else {
            imageContainer.innerHTML = `<img src="/uploads/${r.stored_filename}" alt="Receipt image">`;
        }

        document.getElementById('receipt-modal').classList.remove('hidden');
    } catch (e) {
        showToast('Failed to load receipt details', 'error');
    }
}

function closeModal() {
    document.getElementById('receipt-modal').classList.add('hidden');
}

async function saveModal() {
    const id = document.getElementById('modal-id').value;
    const data = {
        vendor_name: document.getElementById('modal-vendor').value,
        amount: parseFloat(document.getElementById('modal-amount').value) || 0,
        currency: document.getElementById('modal-currency').value || 'USD',
        receipt_date: document.getElementById('modal-date').value,
        category: document.getElementById('modal-category').value,
        notes: document.getElementById('modal-notes').value,
    };

    try {
        const result = await api.updateReceipt(id, data);
        if (result.success) {
            showToast('Receipt updated', 'success');
            closeModal();
            if (state.currentView === 'dashboard') loadDashboard();
            else loadReceipts();
        } else {
            showToast(result.error || 'Update failed', 'error');
        }
    } catch (e) {
        showToast('Failed to save changes', 'error');
    }
}

async function deleteFromModal() {
    const id = document.getElementById('modal-id').value;
    if (!confirm('Delete this receipt permanently?')) return;

    try {
        const result = await api.deleteReceipt(id);
        if (result.success) {
            showToast('Receipt deleted', 'success');
            closeModal();
            if (state.currentView === 'dashboard') loadDashboard();
            else loadReceipts();
        } else {
            showToast(result.error || 'Delete failed', 'error');
        }
    } catch (e) {
        showToast('Failed to delete receipt', 'error');
    }
}

/* === Toast === */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

/* === Utility === */
const CURRENCY_SYMBOLS = {
    USD: '$', EUR: '€', GBP: '£', CHF: 'CHF ', CAD: 'CA$', AUD: 'A$',
    JPY: '¥', CNY: '¥', INR: '₹', MXN: 'MX$', SEK: 'kr ', NOK: 'kr ', DKK: 'kr ',
};

function formatCurrency(amount) {
    return '$' + (amount || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

function formatAmount(amount, currency) {
    const sym = CURRENCY_SYMBOLS[currency] || '$';
    const val = (amount || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return sym + val;
}

function esc(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

function populateCategorySelects() {
    const selects = [
        document.getElementById('filter-category'),
    ];
    selects.forEach(sel => {
        if (!sel) return;
        const current = sel.innerHTML;
        sel.innerHTML = '<option value="">All Categories</option>' +
            state.categories.map(c => `<option value="${c}">${c}</option>`).join('');
    });
}
