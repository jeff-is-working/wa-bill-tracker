// WA Legislative Tracker 2026 - Enhanced JavaScript Application
// With persistent cookies, note management, stats views, proper sharing, and bill type navigation

// Application Configuration
const APP_CONFIG = {
    siteName: 'WA Bill Tracker',
    siteUrl: 'https://jeff-is-working.github.io/wa-bill-tracker',
    cookieDuration: 90, // days
    autoSaveInterval: 30000, // 30 seconds
    dataRefreshInterval: 3600000, // 1 hour
    githubDataUrl: 'https://raw.githubusercontent.com/jeff-is-working/wa-bill-tracker/main/data/bills.json',
    sessionEnd: new Date('2026-03-12'),
    billTypes: {
        'all': { name: 'All Bills', description: 'Showing all Washington State legislative bills for the 2026 session' },
        'SB': { name: 'Senate Bills', description: 'Bills introduced in the Washington State Senate' },
        'HB': { name: 'House Bills', description: 'Bills introduced in the Washington State House of Representatives' },
        'SJR': { name: 'Senate Joint Resolutions', description: 'Joint resolutions from the Washington State Senate' },
        'HJR': { name: 'House Joint Resolutions', description: 'Joint resolutions from the Washington State House' },
        'SJM': { name: 'Senate Joint Memorials', description: 'Joint memorials from the Washington State Senate' },
        'HJM': { name: 'House Joint Memorials', description: 'Joint memorials from the Washington State House' },
        'SCR': { name: 'Senate Concurrent Resolutions', description: 'Concurrent resolutions from the Washington State Senate' },
        'HCR': { name: 'House Concurrent Resolutions', description: 'Concurrent resolutions from the Washington State House' }
    }
};

// Application State
const APP_STATE = {
    bills: [],
    trackedBills: new Set(),
    userNotes: {},
    filters: {
        search: '',
        status: '',
        priority: '',
        committee: '',
        type: '',
        trackedOnly: false
    },
    currentBillType: 'all', // Track current bill type page
    lastSync: null,
    userData: {
        name: 'Guest User',
        avatar: '?',
        id: null
    },
    currentView: 'main',
    currentNoteBillId: null
};

// Cookie Management with Long-term Persistence
const CookieManager = {
    // Set a cookie with proper SameSite and long expiration
    set(name, value, days = APP_CONFIG.cookieDuration) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
        const cookieValue = typeof value === 'object' ? JSON.stringify(value) : value;
        document.cookie = `${name}=${encodeURIComponent(cookieValue)};expires=${expires.toUTCString()};path=/;SameSite=Lax`;
    },

    // Get a cookie value
    get(name) {
        const nameEQ = name + "=";
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.indexOf(nameEQ) === 0) {
                const value = decodeURIComponent(cookie.substring(nameEQ.length));
                try {
                    return JSON.parse(value);
                } catch {
                    return value;
                }
            }
        }
        return null;
    },

    // Delete a cookie
    delete(name) {
        document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:01 GMT;path=/;`;
    }
};

// LocalStorage Backup for Additional Persistence
const StorageManager = {
    save() {
        try {
            // Save to cookies (primary)
            CookieManager.set('wa_tracker_tracked', Array.from(APP_STATE.trackedBills));
            CookieManager.set('wa_tracker_notes', APP_STATE.userNotes);
            CookieManager.set('wa_tracker_user', APP_STATE.userData);
            CookieManager.set('wa_tracker_filters', APP_STATE.filters);
            CookieManager.set('wa_tracker_bill_type', APP_STATE.currentBillType);
            
            // Save to localStorage (backup)
            localStorage.setItem('wa_tracker_state', JSON.stringify({
                trackedBills: Array.from(APP_STATE.trackedBills),
                userNotes: APP_STATE.userNotes,
                userData: APP_STATE.userData,
                filters: APP_STATE.filters,
                currentBillType: APP_STATE.currentBillType,
                lastSaved: new Date().toISOString()
            }));
            
            return true;
        } catch (error) {
            console.error('Error saving state:', error);
            return false;
        }
    },

    load() {
        try {
            // Try cookies first (primary)
            const trackedFromCookie = CookieManager.get('wa_tracker_tracked');
            const notesFromCookie = CookieManager.get('wa_tracker_notes');
            const userFromCookie = CookieManager.get('wa_tracker_user');
            const filtersFromCookie = CookieManager.get('wa_tracker_filters');
            const billTypeFromCookie = CookieManager.get('wa_tracker_bill_type');
            
            if (trackedFromCookie || notesFromCookie || userFromCookie) {
                APP_STATE.trackedBills = new Set(trackedFromCookie || []);
                APP_STATE.userNotes = notesFromCookie || {};
                APP_STATE.userData = userFromCookie || APP_STATE.userData;
                APP_STATE.filters = filtersFromCookie || APP_STATE.filters;
                APP_STATE.currentBillType = billTypeFromCookie || 'all';
                return true;
            }
            
            // Fallback to localStorage
            const saved = localStorage.getItem('wa_tracker_state');
            if (saved) {
                const data = JSON.parse(saved);
                APP_STATE.trackedBills = new Set(data.trackedBills || []);
                APP_STATE.userNotes = data.userNotes || {};
                APP_STATE.userData = data.userData || APP_STATE.userData;
                APP_STATE.filters = data.filters || APP_STATE.filters;
                APP_STATE.currentBillType = data.currentBillType || 'all';
                
                // Migrate to cookies
                StorageManager.save();
                return true;
            }
            
            return false;
        } catch (error) {
            console.error('Error loading state:', error);
            return false;
        }
    }
};

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
    console.log('App initializing...');
    initializeUser();
    StorageManager.load();
    await loadBillsData();
    setupEventListeners();
    setupAutoSave();
    setupNavigationListeners();
    
    // Ensure we have a valid bill type set
    if (!APP_STATE.currentBillType) {
        APP_STATE.currentBillType = 'all';
    }

    // Force initial render by temporarily clearing currentBillType so
    // navigateToBillType's early-return guard doesn't skip the first render
    const initialType = APP_STATE.currentBillType;
    APP_STATE.currentBillType = null;
    handleHashChange(); // Handle initial hash (calls navigateToBillType -> updateUI)
    // If handleHashChange didn't set a type (e.g. shared bill hash), restore it
    if (!APP_STATE.currentBillType) {
        APP_STATE.currentBillType = initialType;
        updateUI();
    }
    checkForSharedBill();
});

// User Initialization
function initializeUser() {
    // Check for existing user ID
    let userId = CookieManager.get('wa_tracker_user_id');
    
    if (!userId) {
        // Generate unique user ID
        userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        CookieManager.set('wa_tracker_user_id', userId, 365); // 1 year
    }
    
    APP_STATE.userData.id = userId;
    
    // Check for saved user data
    if (!APP_STATE.userData.name || APP_STATE.userData.name === 'Guest User') {
        const savedName = CookieManager.get('wa_tracker_user_name');
        if (savedName) {
            APP_STATE.userData.name = savedName;
            APP_STATE.userData.avatar = savedName.charAt(0).toUpperCase();
        }
    }
}

// Navigation Listeners
function setupNavigationListeners() {
    // Handle hash changes (browser back/forward)
    window.addEventListener('hashchange', handleHashChange);
    
    // Handle navigation tab clicks
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            const type = tab.dataset.type;
            navigateToBillType(type);
        });
    });
}

// Handle hash changes
function handleHashChange() {
    const hash = window.location.hash.slice(1); // Remove '#'
    
    // Check if it's a bill reference
    if (hash.startsWith('bill-')) {
        const billId = hash.replace('bill-', '');
        setTimeout(() => {
            highlightBill(billId);
        }, 1000);
        return;
    }
    
    // Check if it's a bill type
    // Default to 'all' if no hash
    const billType = hash ? (hash.toLowerCase() === 'all' ? 'all' : hash.toUpperCase()) : 'all';
    
    if (APP_CONFIG.billTypes[billType]) {
        navigateToBillType(billType);
    } else {
        // Invalid bill type, default to all
        navigateToBillType('all');
    }
}

// Navigate to a specific bill type
function navigateToBillType(type) {
    // Normalize the type - convert to uppercase except for 'all'
    const normalizedType = type.toLowerCase() === 'all' ? 'all' : type.toUpperCase();

    // Validate the type exists in config
    if (!APP_CONFIG.billTypes[normalizedType]) {
        console.warn(`Invalid bill type: ${type}, defaulting to 'all'`);
        type = 'all';
    } else {
        type = normalizedType;
    }

    // Skip if already on this bill type (prevents circular calls from hashchange)
    if (APP_STATE.currentBillType === type && APP_STATE.currentView === 'main') {
        return;
    }

    APP_STATE.currentBillType = type;

    // Ensure we switch back to the main view (e.g. if user was in stats view)
    APP_STATE.currentView = 'main';
    document.getElementById('statsView').classList.remove('active');
    document.getElementById('mainView').classList.add('active');

    // Update active nav tab
    document.querySelectorAll('.nav-tab').forEach(tab => {
        const tabType = tab.dataset.type.toLowerCase() === 'all' ? 'all' : tab.dataset.type.toUpperCase();
        if (tabType === type) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // Update page title and description
    const typeInfo = APP_CONFIG.billTypes[type];
    document.getElementById('pageTitle').textContent = typeInfo.name;
    document.getElementById('pageDescription').textContent = typeInfo.description;

    // Update the URL hash without re-triggering handleHashChange
    const newHash = type.toLowerCase();
    if (window.location.hash.slice(1) !== newHash) {
        window.location.hash = newHash;
    }

    // Update filters - clear type filter when switching pages
    if (type !== 'all') {
        APP_STATE.filters.type = '';
        document.querySelectorAll('.filter-tag[data-filter="type"]').forEach(tag => {
            tag.classList.remove('active');
        });
    }

    // Save state and update UI
    StorageManager.save();
    updateUI();
}

// Load Bills Data
async function loadBillsData() {
    try {
        const response = await fetch(APP_CONFIG.githubDataUrl);
        
        if (response.ok) {
            const data = await response.json();
            APP_STATE.bills = data.bills || [];
            APP_STATE.lastSync = data.lastSync || new Date().toISOString();
            
            // Cache in localStorage
            localStorage.setItem('billsData', JSON.stringify(data));
            localStorage.setItem('lastDataFetch', new Date().toISOString());
            
            showToast(`✅ Loaded ${APP_STATE.bills.length} bills`);
        } else {
            throw new Error('Failed to fetch from GitHub');
        }
    } catch (error) {
        console.error('Error loading from GitHub:', error);
        
        // Fall back to cached data
        const cachedData = localStorage.getItem('billsData');
        if (cachedData) {
            const data = JSON.parse(cachedData);
            APP_STATE.bills = data.bills || [];
            APP_STATE.lastSync = data.lastSync || null;
            showToast('📦 Using cached data');
        } else {
            // No data available
            APP_STATE.bills = [];
            showToast('⚠️ No bill data available');
        }
    }
    
    updateSyncStatus();
}

// Render Functions
function updateUI() {
    if (APP_STATE.currentView === 'main') {
        renderBills();
        updateStats();
    }
    updateUserPanel();
}

function renderBills() {
    const grid = document.getElementById('billsGrid');
    const filteredBills = filterBills();
    
    if (filteredBills.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-muted);">
                <h3 style="font-size: 1.5rem; margin-bottom: 1rem;">No bills found</h3>
                <p>Try adjusting your filters or search terms</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = filteredBills.map(bill => createBillCard(bill)).join('');
}

function createBillCard(bill) {
    const isTracked = APP_STATE.trackedBills.has(bill.id);
    const hasNotes = APP_STATE.userNotes[bill.id] && APP_STATE.userNotes[bill.id].length > 0;
    const hasHearings = bill.hearings && bill.hearings.length > 0;
    
    let latestNote = '';
    if (hasNotes) {
        const notes = APP_STATE.userNotes[bill.id];
        latestNote = notes[notes.length - 1].text;
        if (latestNote.length > 100) {
            latestNote = latestNote.substring(0, 100) + '...';
        }
    }
    
    return `
        <div class="bill-card ${isTracked ? 'tracked' : ''}" data-bill-id="${bill.id}">
            <div class="bill-header">
                <a href="https://app.leg.wa.gov/billsummary?BillNumber=${bill.number.split(' ')[1]}&Year=2026" 
                   target="_blank" class="bill-number">${bill.number}</a>
                <div class="bill-title">${bill.title}</div>
            </div>
            
            <div class="bill-body">
                <div class="bill-meta">
                    <span class="meta-item">👤 ${bill.sponsor}</span>
                    <span class="meta-item">🏛️ ${bill.committee}</span>
                    ${hasHearings ? `<span class="meta-item" style="color: var(--warning);">📅 ${bill.hearings[0].date}</span>` : ''}
                </div>
                
                <div class="bill-description">${bill.description}</div>
                
                ${hasNotes ? `<div class="bill-notes-preview">📝 "${latestNote}"</div>` : ''}
                
                <div class="bill-tags">
                    <span class="tag status-${bill.status}">${bill.status}</span>
                    <span class="tag priority-${bill.priority}">${bill.priority} priority</span>
                    <span class="tag">${bill.topic}</span>
                </div>
            </div>
            
            <div class="bill-actions">
                <button class="action-btn ${isTracked ? 'active' : ''}" onclick="toggleTrack('${bill.id}')">
                    ${isTracked ? '⭐ Tracked' : '☆ Track'}
                </button>
                <button class="action-btn" onclick="openNoteModal('${bill.id}')">
                    📝 ${hasNotes ? 'Notes (' + APP_STATE.userNotes[bill.id].length + ')' : 'Add Note'}
                </button>
                <button class="action-btn" onclick="shareBill('${bill.id}')">
                    🔗 Share
                </button>
            </div>
        </div>
    `;
}

// Filter Bills
function filterBills() {
    let filtered = [...APP_STATE.bills];
    
    console.log('filterBills called:', {
        currentBillType: APP_STATE.currentBillType,
        totalBills: APP_STATE.bills.length
    });
    
    // Filter by current bill type page
    if (APP_STATE.currentBillType && APP_STATE.currentBillType.toLowerCase() !== 'all') {
        console.log('Filtering by type:', APP_STATE.currentBillType);
        filtered = filtered.filter(bill => {
            const billType = bill.number.split(' ')[0];
            return billType.toUpperCase() === APP_STATE.currentBillType.toUpperCase();
        });
        console.log('After type filter:', filtered.length);
    } else {
        console.log('Not filtering by type (showing all)');
    }
    
    if (APP_STATE.filters.search) {
        const search = APP_STATE.filters.search.toLowerCase();
        filtered = filtered.filter(bill => 
            bill.number.toLowerCase().includes(search) ||
            bill.title.toLowerCase().includes(search) ||
            bill.description.toLowerCase().includes(search) ||
            bill.sponsor.toLowerCase().includes(search)
        );
    }
    
    if (APP_STATE.filters.status) {
        filtered = filtered.filter(bill => bill.status === APP_STATE.filters.status);
    }
    
    if (APP_STATE.filters.priority) {
        filtered = filtered.filter(bill => bill.priority === APP_STATE.filters.priority);
    }
    
    if (APP_STATE.filters.committee) {
        filtered = filtered.filter(bill => 
            bill.committee.toLowerCase().includes(APP_STATE.filters.committee)
        );
    }
    
    if (APP_STATE.filters.type) {
        filtered = filtered.filter(bill => {
            const billType = bill.number.split(' ')[0];
            return billType === APP_STATE.filters.type;
        });
    }
    
    if (APP_STATE.filters.trackedOnly) {
        filtered = filtered.filter(bill => APP_STATE.trackedBills.has(bill.id));
    }
    
    return filtered;
}

// Bill Actions
function toggleTrack(billId) {
    if (APP_STATE.trackedBills.has(billId)) {
        APP_STATE.trackedBills.delete(billId);
        showToast('✖️ Bill removed from tracking');
    } else {
        APP_STATE.trackedBills.add(billId);
        showToast('⭐ Bill added to tracking');
    }
    
    StorageManager.save();
    updateUI();
}

// Note Management
function openNoteModal(billId) {
    APP_STATE.currentNoteBillId = billId;
    const bill = APP_STATE.bills.find(b => b.id === billId);
    
    document.getElementById('noteModalTitle').textContent = `Notes for ${bill.number}`;
    
    const existingNotes = APP_STATE.userNotes[billId] || [];
    let notesText = existingNotes.map(note => note.text).join('\n\n---\n\n');
    document.getElementById('noteTextarea').value = notesText;
    
    document.getElementById('noteModal').classList.add('active');
}

function closeNoteModal() {
    document.getElementById('noteModal').classList.remove('active');
    APP_STATE.currentNoteBillId = null;
}

function saveNote() {
    const billId = APP_STATE.currentNoteBillId;
    const noteText = document.getElementById('noteTextarea').value.trim();
    
    if (!noteText) {
        delete APP_STATE.userNotes[billId];
    } else {
        if (!APP_STATE.userNotes[billId]) {
            APP_STATE.userNotes[billId] = [];
        }
        
        APP_STATE.userNotes[billId] = [{
            id: Date.now().toString(),
            text: noteText,
            date: new Date().toISOString(),
            user: APP_STATE.userData.name
        }];
    }
    
    StorageManager.save();
    closeNoteModal();
    showToast('📝 Note saved');
    updateUI();
}

// Share Bill - Uses wa-bill-tracker URL
function shareBill(billId) {
    const bill = APP_STATE.bills.find(b => b.id === billId);
    const shareUrl = `${APP_CONFIG.siteUrl}#bill-${billId}`;
    const shareText = `Check out ${bill.number}: ${bill.title}`;
    
    if (navigator.share) {
        navigator.share({
            title: `${bill.number} - WA Bill Tracker`,
            text: shareText,
            url: shareUrl
        }).catch(err => {
            navigator.clipboard.writeText(shareUrl);
            showToast('🔗 Link copied to clipboard');
        });
    } else {
        navigator.clipboard.writeText(shareUrl);
        showToast('🔗 Link copied to clipboard');
    }
}

// Check for shared bill in URL
function checkForSharedBill() {
    if (window.location.hash && window.location.hash.startsWith('#bill-')) {
        const billId = window.location.hash.replace('#bill-', '');
        setTimeout(() => {
            highlightBill(billId);
        }, 1000);
    }
}

// Highlight a specific bill
function highlightBill(billId) {
    // Find the bill to determine its type
    const bill = APP_STATE.bills.find(b => b.id === billId);
    if (bill) {
        const billType = bill.number.split(' ')[0];
        // Navigate to the appropriate bill type page
        navigateToBillType(billType);
    }
    
    // Reset filters
    APP_STATE.filters = {
        search: '',
        status: '',
        priority: '',
        committee: '',
        type: '',
        trackedOnly: false
    };
    
    showMainView();
    
    setTimeout(() => {
        const billCard = document.querySelector(`[data-bill-id="${billId}"]`);
        if (billCard) {
            billCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            billCard.style.animation = 'highlight 2s ease';
        }
    }, 100);
}

// Stats Detail Views
function showStatsDetail(type) {
    APP_STATE.currentView = 'stats';
    document.getElementById('mainView').classList.remove('active');
    document.getElementById('statsView').classList.add('active');
    
    const detailContainer = document.getElementById('statsDetail');
    let content = '';
    
    switch(type) {
        case 'total':
            content = renderTotalBillsStats();
            break;
        case 'tracked':
            content = renderTrackedBillsStats();
            break;
        case 'today':
            content = renderTodayStats();
            break;
        case 'hearings':
            content = renderHearingsStats();
            break;
        case 'remaining':
            content = renderSessionStats();
            break;
    }
    
    detailContainer.innerHTML = content;
}

function renderTotalBillsStats() {
    const stats = calculateBillStats();
    return `
        <h2>Total Bills: ${APP_STATE.bills.length}</h2>
        <div class="stats-list">
            ${Object.entries(stats.byType).map(([type, count]) => `
                <div class="stats-item">
                    <span class="stats-item-label">${type} Bills</span>
                    <span class="stats-item-value">${count}</span>
                </div>
            `).join('')}
            ${Object.entries(stats.byStatus).map(([status, count]) => `
                <div class="stats-item">
                    <span class="stats-item-label">${status}</span>
                    <span class="stats-item-value">${count}</span>
                </div>
            `).join('')}
        </div>
    `;
}

function renderTrackedBillsStats() {
    const trackedBills = APP_STATE.bills.filter(bill => 
        APP_STATE.trackedBills.has(bill.id)
    );
    
    return `
        <h2>Your Tracked Bills: ${trackedBills.length}</h2>
        <div class="stats-list">
            ${trackedBills.map(bill => `
                <div class="stats-item" onclick="highlightBill('${bill.id}')" style="cursor: pointer;">
                    <span class="stats-item-label">${bill.number}: ${bill.title}</span>
                    <span class="stats-item-value">${bill.status}</span>
                </div>
            `).join('')}
            ${trackedBills.length === 0 ? '<p style="text-align: center; color: var(--text-muted);">No bills tracked yet</p>' : ''}
        </div>
    `;
}

function renderTodayStats() {
    const today = new Date().toDateString();
    const todayBills = APP_STATE.bills.filter(bill => {
        const updateDate = new Date(bill.lastUpdated);
        return updateDate.toDateString() === today;
    });
    
    return `
        <h2>Updated Today: ${todayBills.length}</h2>
        <div class="stats-list">
            ${todayBills.map(bill => `
                <div class="stats-item" onclick="highlightBill('${bill.id}')" style="cursor: pointer;">
                    <span class="stats-item-label">${bill.number}: ${bill.title}</span>
                    <span class="stats-item-value">${formatTime(bill.lastUpdated)}</span>
                </div>
            `).join('')}
            ${todayBills.length === 0 ? '<p style="text-align: center; color: var(--text-muted);">No updates today</p>' : ''}
        </div>
    `;
}

function renderHearingsStats() {
    const weekFromNow = new Date();
    weekFromNow.setDate(weekFromNow.getDate() + 7);
    
    const hearingBills = [];
    APP_STATE.bills.forEach(bill => {
        if (bill.hearings) {
            bill.hearings.forEach(hearing => {
                const hearingDate = new Date(hearing.date);
                if (hearingDate >= new Date() && hearingDate <= weekFromNow) {
                    hearingBills.push({
                        bill,
                        hearing,
                        date: hearingDate
                    });
                }
            });
        }
    });
    
    hearingBills.sort((a, b) => a.date - b.date);
    
    return `
        <h2>Hearings This Week: ${hearingBills.length}</h2>
        <div class="stats-list">
            ${hearingBills.map(item => `
                <div class="stats-item" onclick="highlightBill('${item.bill.id}')" style="cursor: pointer;">
                    <span class="stats-item-label">
                        ${item.hearing.date} ${item.hearing.time}<br>
                        ${item.bill.number}: ${item.bill.title}
                    </span>
                    <span class="stats-item-value">${item.hearing.committee}</span>
                </div>
            `).join('')}
            ${hearingBills.length === 0 ? '<p style="text-align: center; color: var(--text-muted);">No hearings scheduled this week</p>' : ''}
        </div>
    `;
}

function renderSessionStats() {
    const daysLeft = Math.ceil((APP_CONFIG.sessionEnd - new Date()) / (1000 * 60 * 60 * 24));
    const sessionStart = new Date('2026-01-12');
    const totalDays = Math.ceil((APP_CONFIG.sessionEnd - sessionStart) / (1000 * 60 * 60 * 24));
    const daysPassed = totalDays - daysLeft;
    const percentComplete = Math.round((daysPassed / totalDays) * 100);
    
    return `
        <h2>Session Progress</h2>
        <div class="stats-list">
            <div class="stats-item">
                <span class="stats-item-label">Days Remaining</span>
                <span class="stats-item-value">${Math.max(0, daysLeft)}</span>
            </div>
            <div class="stats-item">
                <span class="stats-item-label">Days Passed</span>
                <span class="stats-item-value">${daysPassed}</span>
            </div>
            <div class="stats-item">
                <span class="stats-item-label">Session Progress</span>
                <span class="stats-item-value">${percentComplete}%</span>
            </div>
            <div class="stats-item">
                <span class="stats-item-label">Session Ends</span>
                <span class="stats-item-value">March 12, 2026</span>
            </div>
        </div>
    `;
}

// Calculate Bill Statistics
function calculateBillStats() {
    const stats = {
        byStatus: {},
        byType: {},
        byTopic: {},
        byCommittee: {}
    };
    
    APP_STATE.bills.forEach(bill => {
        const status = bill.status || 'unknown';
        stats.byStatus[status] = (stats.byStatus[status] || 0) + 1;
        
        const type = bill.number.split(' ')[0];
        stats.byType[type] = (stats.byType[type] || 0) + 1;
        
        const topic = bill.topic || 'General';
        stats.byTopic[topic] = (stats.byTopic[topic] || 0) + 1;
        
        const committee = bill.committee || 'Unknown';
        stats.byCommittee[committee] = (stats.byCommittee[committee] || 0) + 1;
    });
    
    return stats;
}

// UI Updates
function updateStats() {
    // Get filtered bills for current page
    const filteredBills = filterBills();
    
    document.getElementById('totalBills').textContent = filteredBills.length;
    
    const trackedOnPage = filteredBills.filter(bill => 
        APP_STATE.trackedBills.has(bill.id)
    ).length;
    document.getElementById('trackedBills').textContent = trackedOnPage;
    
    const today = new Date().toDateString();
    const newToday = filteredBills.filter(bill => 
        new Date(bill.lastUpdated).toDateString() === today
    ).length;
    document.getElementById('newToday').textContent = newToday;
    
    const weekFromNow = new Date();
    weekFromNow.setDate(weekFromNow.getDate() + 7);
    const hearingsThisWeek = filteredBills.reduce((count, bill) => {
        if (!bill.hearings) return count;
        return count + bill.hearings.filter(h => {
            const hearingDate = new Date(h.date);
            return hearingDate >= new Date() && hearingDate <= weekFromNow;
        }).length;
    }, 0);
    document.getElementById('hearingsWeek').textContent = hearingsThisWeek;
    
    const daysLeft = Math.ceil((APP_CONFIG.sessionEnd - new Date()) / (1000 * 60 * 60 * 24));
    document.getElementById('daysLeft').textContent = Math.max(0, daysLeft);
}

function updateUserPanel() {
    document.getElementById('userName').textContent = APP_STATE.userData.name;
    document.getElementById('userAvatar').textContent = APP_STATE.userData.avatar;
    document.getElementById('userTrackedCount').textContent = APP_STATE.trackedBills.size;
    
    const totalNotes = Object.values(APP_STATE.userNotes).reduce((sum, notes) => sum + notes.length, 0);
    document.getElementById('userNotesCount').textContent = totalNotes;
    
    updateUserNotesList();
}

function updateUserNotesList() {
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
                <div class="user-note-bill" onclick="highlightBill('${note.billId}')" style="cursor: pointer;">
                    ${note.billNumber}: ${note.billTitle}
                </div>
                <div class="user-note-text">${note.text.substring(0, 100)}${note.text.length > 100 ? '...' : ''}</div>
                <div class="user-note-date">${formatDate(note.date)}</div>
            </div>
        `).join('');
    }
}

function updateSyncStatus() {
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

// Event Listeners
function setupEventListeners() {
    document.getElementById('searchInput').addEventListener('input', (e) => {
        APP_STATE.filters.search = e.target.value;
        updateUI();
    });
    
    document.querySelectorAll('.filter-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const filter = tag.dataset.filter;
            const value = tag.dataset.value;

            if (tag.classList.contains('active')) {
                tag.classList.remove('active');
                APP_STATE.filters[filter] = '';
            } else {
                tag.parentElement.querySelectorAll('.filter-tag').forEach(t =>
                    t.classList.remove('active')
                );
                tag.classList.add('active');
                APP_STATE.filters[filter] = value;
            }

            updateUI();
            StorageManager.save();
        });
    });
}

// Auto-save functionality
function setupAutoSave() {
    setInterval(() => {
        StorageManager.save();
    }, APP_CONFIG.autoSaveInterval);
}

// UI Controls
function toggleFilters() {
    const panel = document.getElementById('filtersPanel');
    const btn = document.getElementById('filterToggle');
    
    panel.classList.toggle('active');
    btn.classList.toggle('active');
}

function toggleTrackedOnly() {
    const btn = document.getElementById('trackedToggle');
    APP_STATE.filters.trackedOnly = !APP_STATE.filters.trackedOnly;
    btn.classList.toggle('active');
    renderBills();
    StorageManager.save();
}

function toggleUserPanel() {
    const panel = document.getElementById('userPanel');
    const notesSection = document.getElementById('userNotesSection');
    const expandBtn = document.getElementById('expandBtn');
    
    panel.classList.toggle('expanded');
    notesSection.classList.toggle('active');
    expandBtn.classList.toggle('expanded');
}

async function refreshData() {
    const syncStatus = document.getElementById('syncStatus');
    syncStatus.classList.add('syncing');
    
    await loadBillsData();
    updateUI();
    
    setTimeout(() => {
        syncStatus.classList.remove('syncing');
    }, 1000);
}

function showMainView() {
    APP_STATE.currentView = 'main';
    document.getElementById('statsView').classList.remove('active');
    document.getElementById('mainView').classList.add('active');
    updateUI();
}

// Utility Functions
function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) {
        const hours = Math.floor(diff / (1000 * 60 * 60));
        if (hours === 0) {
            return 'Just now';
        }
        return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else if (days === 1) {
        return 'Yesterday';
    } else if (days < 7) {
        return `${days} days ago`;
    } else {
        return date.toLocaleDateString();
    }
}

function formatTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

// Toast Notifications
function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Add highlight animation to CSS dynamically
const style = document.createElement('style');
style.textContent = `
    @keyframes highlight {
        0% { box-shadow: 0 0 0 0 var(--accent); }
        50% { box-shadow: 0 0 20px 10px var(--accent); }
        100% { box-shadow: 0 0 0 0 var(--accent); }
    }
`;
document.head.appendChild(style);
