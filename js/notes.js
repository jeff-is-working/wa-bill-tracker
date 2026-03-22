// notes.js -- Bill tracking, note management, sharing, import/export

import { APP_CONFIG, escapeHTML, sanitizeInput } from './config.js';
import { APP_STATE, StorageManager } from './state.js';
import { filterBills } from './data.js';
import { STATUS_LABELS, updateUI } from './render.js';

// --- Bill tracking ---
export function toggleTrack(billId, showToast) {
    if (APP_STATE.trackedBills.has(billId)) {
        APP_STATE.trackedBills.delete(billId);
        showToast('Bill removed from tracking');
    } else {
        APP_STATE.trackedBills.add(billId);
        showToast('Bill added to tracking');
    }

    APP_STATE._dirty = true;
    StorageManager.save();
    APP_STATE._dirty = false;
    updateUI();
}

// --- Note management ---
function formatNoteDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: 'numeric', minute: '2-digit'
    });
}

export function openNoteModal(billId) {
    APP_STATE.currentNoteBillId = billId;
    const bill = APP_STATE.bills.find(b => b.id === billId);

    document.getElementById('noteModalTitle').textContent = `Notes for ${bill.number}`;

    const existingNotes = APP_STATE.userNotes[billId] || [];
    const container = document.getElementById('existingNotes');
    if (existingNotes.length > 0) {
        container.innerHTML = existingNotes.map((note, i) => `
            <div class="existing-note-item" data-note-index="${i}">
                <div class="existing-note-header">
                    <div class="existing-note-date">${formatNoteDateTime(note.date)}</div>
                    <button class="note-delete-btn" data-delete-index="${i}" title="Delete this note">x</button>
                </div>
                <textarea class="existing-note-textarea" data-note-index="${i}">${escapeHTML(note.text)}</textarea>
            </div>
        `).join('');
        // Wire per-note delete buttons
        container.querySelectorAll('.note-delete-btn').forEach(btn => {
            btn.addEventListener('click', () => deleteOneNote(parseInt(btn.dataset.deleteIndex)));
        });
    } else {
        container.innerHTML = '';
    }
    document.getElementById('noteTextarea').value = '';

    // Show/hide Delete All button
    document.getElementById('noteModalDeleteAll').style.display = existingNotes.length > 0 ? '' : 'none';

    document.getElementById('noteModal').classList.add('active');
}

export function closeNoteModal() {
    document.getElementById('noteModal').classList.remove('active');
    APP_STATE.currentNoteBillId = null;
}

export function deleteOneNote(index) {
    const billId = APP_STATE.currentNoteBillId;
    const notes = APP_STATE.userNotes[billId];
    if (!notes || index >= notes.length) return;

    if (!confirm('Delete this note?')) return;

    notes.splice(index, 1);
    if (notes.length === 0) {
        delete APP_STATE.userNotes[billId];
    }
    APP_STATE._dirty = true;
    StorageManager.save();
    APP_STATE._dirty = false;
    updateUI();
    // Re-open modal to refresh the notes list
    openNoteModal(billId);
    showToastGlobal('Note deleted');
}

export function deleteAllNotes() {
    const billId = APP_STATE.currentNoteBillId;
    const notes = APP_STATE.userNotes[billId];
    if (!notes || notes.length === 0) return;

    if (!confirm(`Delete all ${notes.length} note${notes.length !== 1 ? 's' : ''} on this bill?`)) return;

    delete APP_STATE.userNotes[billId];
    APP_STATE._dirty = true;
    StorageManager.save();
    APP_STATE._dirty = false;
    updateUI();
    openNoteModal(billId);
    showToastGlobal('All notes deleted');
}

export function saveNote() {
    const billId = APP_STATE.currentNoteBillId;
    if (!APP_STATE.userNotes[billId]) {
        APP_STATE.userNotes[billId] = [];
    }

    const now = new Date().toISOString();
    let changed = false;

    // Update existing notes (edited text gets a new timestamp)
    document.querySelectorAll('.existing-note-textarea').forEach(ta => {
        const idx = parseInt(ta.dataset.noteIndex);
        const newText = sanitizeInput(ta.value.trim());
        if (idx < APP_STATE.userNotes[billId].length) {
            if (!newText) {
                APP_STATE.userNotes[billId][idx] = null; // mark for removal
                changed = true;
            } else if (newText !== APP_STATE.userNotes[billId][idx].text) {
                APP_STATE.userNotes[billId][idx].text = newText;
                APP_STATE.userNotes[billId][idx].date = now;
                changed = true;
            }
        }
    });

    // Remove deleted notes
    APP_STATE.userNotes[billId] = APP_STATE.userNotes[billId].filter(n => n !== null);

    // Append new note from bottom textarea
    const newText = sanitizeInput(document.getElementById('noteTextarea').value.trim());
    if (newText) {
        APP_STATE.userNotes[billId].push({
            id: Date.now().toString(),
            text: newText,
            date: now,
            user: APP_STATE.userData.name
        });
        changed = true;
    }

    // Clean up empty arrays
    if (APP_STATE.userNotes[billId].length === 0) {
        delete APP_STATE.userNotes[billId];
    }

    if (!changed && !newText) {
        closeNoteModal();
        return;
    }

    APP_STATE._dirty = true;
    StorageManager.save();
    APP_STATE._dirty = false;
    closeNoteModal();
    showToastGlobal('Note saved');
    updateUI();
}

// --- Sharing ---
export function shareBill(billId) {
    const bill = APP_STATE.bills.find(b => b.id === billId);
    const shareUrl = `${APP_CONFIG.siteUrl}#bill-${billId}`;
    const statusLabel = STATUS_LABELS[bill.status] || bill.status;
    const notes = APP_STATE.userNotes[billId];

    let shareText;
    if (notes && notes.length > 0) {
        const noteText = notes.map(n => `[${formatNoteDateTime(n.date)}] ${n.text}`).join('\n');
        shareText = `Check out ${bill.number}: ${bill.title}\nStatus: ${statusLabel}\n---\nNotes by ${APP_STATE.userData.name}:\n${noteText}`;
    } else {
        shareText = `Check out ${bill.number}: ${bill.title} (${statusLabel})`;
    }

    const clipboardText = `${shareText}\n\n${shareUrl}`;

    if (navigator.share) {
        navigator.share({
            title: `${bill.number} - WA Bill Tracker`,
            text: shareText,
            url: shareUrl
        }).catch(() => {
            navigator.clipboard.writeText(clipboardText);
            showToastGlobal('Link copied to clipboard');
        });
    } else {
        navigator.clipboard.writeText(clipboardText);
        showToastGlobal('Link copied to clipboard');
    }
}

export function shareNote() {
    const billId = APP_STATE.currentNoteBillId;
    if (!billId) return;
    const bill = APP_STATE.bills.find(b => b.id === billId);
    if (!bill) return;

    const existingNotes = APP_STATE.userNotes[billId] || [];
    const currentText = document.getElementById('noteTextarea').value.trim();
    if (existingNotes.length === 0 && !currentText) {
        showToastGlobal('No notes to share');
        return;
    }

    const noteLines = existingNotes.map(n => `[${formatNoteDateTime(n.date)}] ${n.text}`);
    if (currentText) noteLines.push(`[Draft] ${currentText}`);

    const shareUrl = `${APP_CONFIG.siteUrl}#bill-${billId}`;
    const statusLabel = STATUS_LABELS[bill.status] || bill.status;
    const shareText = `${bill.number}: ${bill.title}\nStatus: ${statusLabel}\n---\nNotes by ${APP_STATE.userData.name}:\n${noteLines.join('\n')}`;
    const clipboardText = `${shareText}\n\n${shareUrl}`;

    if (navigator.share) {
        navigator.share({
            title: `${bill.number} - WA Bill Tracker`,
            text: shareText,
            url: shareUrl
        }).catch(() => {
            navigator.clipboard.writeText(clipboardText);
            showToastGlobal('Note link copied to clipboard');
        });
    } else {
        navigator.clipboard.writeText(clipboardText);
        showToastGlobal('Note link copied to clipboard');
    }
}

// --- Shared bill highlighting ---
export function checkForSharedBill(highlightBill) {
    if (window.location.hash && window.location.hash.startsWith('#bill-')) {
        const billId = window.location.hash.replace('#bill-', '');
        setTimeout(() => {
            highlightBill(billId);
        }, 1000);
    }
}

export function highlightBill(billId, navigateToBillType, showMainView) {
    // Find the bill to determine its type
    const bill = APP_STATE.bills.find(b => b.id === billId);
    if (bill) {
        const billType = bill.number.split(' ')[0];
        navigateToBillType(billType);
    }

    // Reset filters
    APP_STATE.filters = {
        search: '',
        status: [],
        priority: [],
        committee: [],
        type: '',
        trackedOnly: false
    };

    // Find the bill's page in the filtered list
    const filtered = filterBills();
    const index = filtered.findIndex(b => b.id === billId);
    if (index >= 0) {
        APP_STATE.pagination.page = Math.floor(index / APP_STATE.pagination.pageSize) + 1;
    }

    showMainView();

    setTimeout(() => {
        const billCard = document.querySelector(`[data-bill-id="${billId}"]`);
        if (billCard) {
            billCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            billCard.style.animation = 'highlight 2s ease';
        }
    }, 100);
}

// --- User panel ---
export function updateUserPanel(formatDate) {
    document.getElementById('userName').textContent = APP_STATE.userData.name;
    document.getElementById('userAvatar').textContent = APP_STATE.userData.avatar;
    document.getElementById('userTrackedCount').textContent = APP_STATE.trackedBills.size;

    const totalNotes = Object.values(APP_STATE.userNotes).reduce((sum, notes) => sum + notes.length, 0);
    document.getElementById('userNotesCount').textContent = totalNotes;

    updateUserNotesList(formatDate);
}

export function updateUserNotesList(formatDate) {
    const notesList = document.getElementById('userNotesList');
    const allNotes = [];

    Object.entries(APP_STATE.userNotes).forEach(([billId, notes]) => {
        const bill = APP_STATE.bills.find(b => b.id === billId);
        if (bill) {
            notes.forEach(note => {
                allNotes.push({
                    billId,
                    billNumber: bill.number,
                    billTitle: bill.title,
                    ...note
                });
            });
        }
    });

    allNotes.sort((a, b) => new Date(b.date) - new Date(a.date));
    const recentNotes = allNotes.slice(0, 5);

    if (recentNotes.length === 0) {
        notesList.innerHTML = '<p style="color: var(--text-muted); font-size: 0.875rem;">No notes yet</p>';
    } else {
        notesList.innerHTML = recentNotes.map(note => `
            <div class="user-note-item">
                <div class="user-note-bill" data-highlight-bill="${escapeHTML(note.billId)}" style="cursor: pointer;">
                    ${escapeHTML(note.billNumber)}: ${escapeHTML(note.billTitle)}
                </div>
                <div class="user-note-text">${escapeHTML(note.text.substring(0, 100))}${note.text.length > 100 ? '...' : ''}</div>
                <div class="user-note-date">${formatDate(note.date)}</div>
            </div>
        `).join('');
    }
}

// --- Notes export/import ---
function formatNotesForExport() {
    const lines = [];
    Object.entries(APP_STATE.userNotes).forEach(([billId, notes]) => {
        const bill = APP_STATE.bills.find(b => b.id === billId);
        const billLabel = bill ? `${bill.number} -- ${bill.title}` : billId;
        const statusLabel = bill ? (STATUS_LABELS[bill.status] || bill.status) : 'Unknown';
        notes.forEach(note => {
            lines.push(`Bill: ${billLabel}`);
            lines.push(`Status: ${statusLabel}`);
            lines.push(`Note: ${note.text}`);
            lines.push(`Date: ${formatNoteDateTime(note.date)}`);
            lines.push('');
        });
    });
    if (lines.length > 0) {
        lines.push('---');
        lines.push(`Notes by ${APP_STATE.userData.name} -- WA Bill Tracker -- https://wa-bill-tracker.org`);
    }
    return lines.join('\n');
}

export async function copyAllNotes() {
    const text = formatNotesForExport();
    if (!text) { showToastGlobal('No notes to copy'); return; }
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
    }
    showToastGlobal('Notes copied to clipboard');
}

export function emailAllNotes() {
    const text = formatNotesForExport();
    if (!text) { showToastGlobal('No notes to email'); return; }
    const subject = encodeURIComponent('My WA Bill Tracker Notes');
    const body = encodeURIComponent(text);
    window.open(`mailto:?subject=${subject}&body=${body}`);
}

export function exportNotesCSV() {
    const entries = Object.entries(APP_STATE.userNotes);
    if (entries.length === 0) { showToastGlobal('No notes to export'); return; }

    function csvEscape(val) {
        const str = String(val);
        return '"' + str.replace(/"/g, '""') + '"';
    }

    const rows = ['Bill Number,Bill Title,Status,Note,Date'];
    entries.forEach(([billId, notes]) => {
        const bill = APP_STATE.bills.find(b => b.id === billId);
        const billNumber = bill ? bill.number : billId;
        const billTitle = bill ? bill.title : '';
        const status = bill ? (STATUS_LABELS[bill.status] || bill.status) : 'Unknown';
        notes.forEach(note => {
            rows.push([
                csvEscape(billNumber),
                csvEscape(billTitle),
                csvEscape(status),
                csvEscape(note.text),
                csvEscape(formatNoteDateTime(note.date))
            ].join(','));
        });
    });

    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'wa-bill-tracker-notes.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToastGlobal('Notes exported to CSV');
}

export function parseCSVRow(row) {
    const fields = [];
    let i = 0;
    while (i < row.length) {
        if (row[i] === '"') {
            let val = '';
            i++; // skip opening quote
            while (i < row.length) {
                if (row[i] === '"') {
                    if (i + 1 < row.length && row[i + 1] === '"') {
                        val += '"';
                        i += 2;
                    } else {
                        i++; // skip closing quote
                        break;
                    }
                } else {
                    val += row[i];
                    i++;
                }
            }
            fields.push(val);
            if (i < row.length && row[i] === ',') i++; // skip comma
        } else {
            let val = '';
            while (i < row.length && row[i] !== ',') {
                val += row[i];
                i++;
            }
            fields.push(val);
            if (i < row.length) i++; // skip comma
        }
    }
    return fields;
}

export function importNotesCSV() {
    const fileInput = document.getElementById('csvFileInput');
    const file = fileInput.files[0];
    if (!file) return;
    fileInput.value = ''; // reset so same file can be re-selected

    const reader = new FileReader();
    reader.onload = function(e) {
        const text = e.target.result;
        const lines = text.split(/\r?\n/).filter(line => line.trim());

        if (lines.length < 2) {
            showToastGlobal('CSV file is empty or has no data rows');
            return;
        }

        // Skip header row
        let importedBills = 0;
        let importedNotes = 0;
        let notFound = 0;

        for (let i = 1; i < lines.length; i++) {
            const fields = parseCSVRow(lines[i]);
            if (fields.length < 5) continue;

            const billNumber = sanitizeInput(fields[0].trim(), 50);
            const noteText = sanitizeInput(fields[3].trim());
            const noteDate = sanitizeInput(fields[4].trim(), 50);

            const bill = APP_STATE.bills.find(b => b.number === billNumber);
            if (!bill) {
                notFound++;
                continue;
            }

            // Track the bill
            const wasTracked = APP_STATE.trackedBills.has(bill.id);
            APP_STATE.trackedBills.add(bill.id);
            if (!wasTracked) importedBills++;

            // Import note if non-empty
            if (noteText) {
                if (!APP_STATE.userNotes[bill.id]) {
                    APP_STATE.userNotes[bill.id] = [];
                }
                // Check for duplicate note (same text on same bill)
                const isDuplicate = APP_STATE.userNotes[bill.id].some(n => n.text === noteText);
                if (!isDuplicate) {
                    APP_STATE.userNotes[bill.id].push({
                        text: noteText,
                        date: noteDate ? new Date(noteDate).toISOString() : new Date().toISOString()
                    });
                    importedNotes++;
                }
            }
        }

        APP_STATE._dirty = true;
        StorageManager.save();
        updateUI();

        const parts = [];
        if (importedBills > 0) parts.push(`${importedBills} bill${importedBills !== 1 ? 's' : ''} tracked`);
        if (importedNotes > 0) parts.push(`${importedNotes} note${importedNotes !== 1 ? 's' : ''} added`);
        if (notFound > 0) parts.push(`${notFound} bill${notFound !== 1 ? 's' : ''} not found`);
        showToastGlobal(parts.length > 0 ? 'Imported: ' + parts.join(', ') : 'No new data to import');
    };

    reader.onerror = function() {
        showToastGlobal('Error reading CSV file');
    };

    reader.readAsText(file);
}

// --- Sync status ---
export function updateSyncStatus() {
    const syncText = document.getElementById('syncText');
    if (APP_STATE.lastSync) {
        const syncDate = new Date(APP_STATE.lastSync);
        const hours = Math.floor((Date.now() - syncDate) / (1000 * 60 * 60));

        if (hours < 1) {
            syncText.textContent = 'Last sync: Just now';
        } else if (hours < 24) {
            syncText.textContent = `Last sync: ${hours} hour${hours > 1 ? 's' : ''} ago`;
        } else {
            const days = Math.floor(hours / 24);
            syncText.textContent = `Last sync: ${days} day${days > 1 ? 's' : ''} ago`;
        }
    } else {
        syncText.textContent = 'Last sync: Never';
    }
}

// --- Global showToast reference (set by app.js) ---
let showToastGlobal = (msg) => console.log(msg);

export function setShowToast(fn) {
    showToastGlobal = fn;
}
