// WA Legislative Tracker 2026 - Enhanced JavaScript Application
// With persistent cookies, note management, stats views, proper sharing, and bill type navigation

// Utility: Debounce
function debounce(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

// Application Configuration
const APP_CONFIG = {
    siteName: 'WA Bill Tracker',
    siteUrl: 'https://wa-bill-tracker.org',
    cookieDuration: 90, // days
    autoSaveInterval: 30000, // 30 seconds
    dataRefreshInterval: 3600000, // 1 hour
    githubDataUrl: 'https://raw.githubusercontent.com/jeff-is-working/wa-bill-tracker/main/data/bills.json',
    sessionEnd: new Date('2026-03-12'),
    sessionStart: new Date('2026-01-12'),
    cutoffDates: [
        { date: '2026-02-04', label: 'Policy Committee (Origin)', failsBefore: ['prefiled', 'introduced'] },
        { date: '2026-02-09', label: 'Fiscal Committee (Origin)', failsBefore: ['prefiled', 'introduced', 'committee'] },
        { date: '2026-02-17', label: 'House of Origin', failsBefore: ['prefiled', 'introduced', 'committee', 'floor'] },
        { date: '2026-02-25', label: 'Policy Committee (Opposite)', failsBefore: ['prefiled', 'introduced', 'committee', 'floor', 'passed_origin'] },
        { date: '2026-03-04', label: 'Fiscal Committee (Opposite)', failsBefore: ['prefiled', 'introduced', 'committee', 'floor', 'passed_origin', 'opposite_chamber'] },
        { date: '2026-03-06', label: 'Opposite House', failsBefore: ['prefiled', 'introduced', 'committee', 'floor', 'passed_origin', 'opposite_chamber'] },
        { date: '2026-03-12', label: 'Sine Die', failsBefore: ['prefiled', 'introduced', 'committee', 'floor', 'passed_origin', 'opposite_chamber', 'passed_both', 'passed_legislature'] },
    ],
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
        status: [],
        priority: [],
        committee: [],
        type: '',
        trackedOnly: false,
        showInactiveBills: false
    },
    currentBillType: 'all', // Track current bill type page
    lastSync: null,
    userData: {
        name: 'Guest User',
        avatar: '?',
        id: null
    },
    currentView: 'main',
    currentNoteBillId: null,
    pagination: {
        page: 1,
        pageSize: 25
    },
    _dirty: false
};

// HTML Sanitization — escape user-controlled strings before inserting into innerHTML
function escapeHTML(str) {
    if (typeof str !== 'string') return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
              .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Input sanitization — strip control chars and limit length for text stored in state
function sanitizeInput(str, maxLength = 2000) {
    if (typeof str !== 'string') return '';
    // Strip null bytes and non-printable control chars (keep newlines/tabs)
    return str.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '').substring(0, maxLength);
}

// Cookie Management with Long-term Persistence
const CookieManager = {
    // Set a cookie with proper SameSite and long expiration
    set(name, value, days = APP_CONFIG.cookieDuration) {
        const expires = new Date();
        expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
        const cookieValue = typeof value === 'object' ? JSON.stringify(value) : value;
        document.cookie = `${name}=${encodeURIComponent(cookieValue)};expires=${expires.toUTCString()};path=/;SameSite=Lax;Secure`;
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

// Domain Migration — transfer user data from old github.io domain to new custom domain
const DomainMigration = {
    OLD_DOMAIN: 'jeff-is-working.github.io',
    NEW_DOMAIN: 'wa-bill-tracker.org',
    COOKIE_KEYS: ['wa_tracker_tracked', 'wa_tracker_notes', 'wa_tracker_user',
                  'wa_tracker_filters', 'wa_tracker_bill_type', 'wa_tracker_user_id',
                  'wa_tracker_user_name', 'wa_tracker_panel_collapsed'],

    // On old domain: collect all user data and redirect to new domain with data in hash
    exportAndRedirect() {
        if (location.hostname !== this.OLD_DOMAIN) return false;

        // Collect data from cookies and localStorage
        const data = {};
        let hasData = false;
        for (const key of this.COOKIE_KEYS) {
            const val = CookieManager.get(key);
            if (val !== null && val !== undefined) {
                data[key] = val;
                hasData = true;
            }
        }
        // Also grab localStorage backup
        const lsState = localStorage.getItem('wa_tracker_state');
        if (lsState) {
            data._ls_state = lsState;
            hasData = true;
        }

        if (hasData) {
            const encoded = encodeURIComponent(JSON.stringify(data));
            location.replace(`https://${this.NEW_DOMAIN}/#migrate=${encoded}`);
            return true;
        }
        // No data to migrate — don't redirect, let them use the old domain until CNAME is set
        return false;
    },

    // On new domain: check for migration data in URL hash and import it
    importFromHash() {
        if (!location.hash.startsWith('#migrate=')) return false;

        try {
            const encoded = location.hash.substring('#migrate='.length);
            const data = JSON.parse(decodeURIComponent(encoded));

            // Restore cookies
            for (const key of this.COOKIE_KEYS) {
                if (data[key] !== undefined) {
                    CookieManager.set(key, data[key], key.includes('panel') || key.includes('user_id') ? 365 : APP_CONFIG.cookieDuration);
                }
            }
            // Restore localStorage backup
            if (data._ls_state) {
                localStorage.setItem('wa_tracker_state', data._ls_state);
            }

            // Clean URL hash
            history.replaceState(null, '', location.pathname + location.search);
            console.log('Migration complete — user data imported from previous domain');
            return true;
        } catch (e) {
            console.error('Migration import failed:', e);
            history.replaceState(null, '', location.pathname + location.search);
            return false;
        }
    }
};

// Run migration checks immediately
DomainMigration.exportAndRedirect();  // On old domain: redirects with data in hash, page unloads
DomainMigration.importFromHash();     // On new domain: imports data from hash if present

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
                migrateFiltersToArrays();
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
                migrateFiltersToArrays();

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

// Migrate old single-string filter values to arrays
function migrateFiltersToArrays() {
    ['status', 'priority', 'committee'].forEach(key => {
        const val = APP_STATE.filters[key];
        if (typeof val === 'string') {
            APP_STATE.filters[key] = val ? [val] : [];
        } else if (!Array.isArray(val)) {
            APP_STATE.filters[key] = [];
        }
    });
}

// Sync filter tag UI (active class) with loaded APP_STATE.filters
function syncFilterTagUI() {
    document.querySelectorAll('.filter-tag').forEach(tag => {
        const filter = tag.dataset.filter;
        const value = tag.dataset.value;
        const filterVal = APP_STATE.filters[filter];
        if (Array.isArray(filterVal) && filterVal.includes(value)) {
            tag.classList.add('active');
        } else {
            tag.classList.remove('active');
        }
    });
}

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
    console.log('App initializing...');
    StorageManager.load();
    initializeUser();
    await loadBillsData();
    setupEventListeners();
    syncFilterTagUI(); // Restore active state on filter tags from saved filters
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
            setUserName(savedName);
        } else {
            promptUserName();
        }
    }
}

function setUserName(name) {
    const clean = sanitizeInput(name, 50);
    APP_STATE.userData.name = clean || 'Guest User';
    APP_STATE.userData.avatar = APP_STATE.userData.name.charAt(0).toUpperCase();
    CookieManager.set('wa_tracker_user_name', APP_STATE.userData.name, 365);
}

function promptUserName() {
    const name = prompt('Welcome to WA Bill Tracker! What name would you like to use?', '');
    if (name && name.trim()) {
        setUserName(name.trim());
    } else {
        setUserName('Guest User');
    }
}

function changeUserName() {
    const current = APP_STATE.userData.name === 'Guest User' ? '' : APP_STATE.userData.name;
    const name = prompt('Enter your name:', current);
    if (name !== null) {
        setUserName(name.trim() || 'Guest User');
        updateUserPanel();
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

    // Reset pagination and save state
    APP_STATE.pagination.page = 1;
    StorageManager.save();
    updateUI();
}

// Load Bills Data
async function loadBillsData() {
    try {
        const response = await fetch(APP_CONFIG.githubDataUrl);
        
        if (response.ok) {
            const data = await response.json();
            APP_STATE.bills = (data.bills || []).map(bill => ({
                ...bill,
                committee: bill.committee ||
                    (bill.hearings && bill.hearings.length > 0
                        ? bill.hearings[bill.hearings.length - 1].committee
                        : ''),
                _searchText: [bill.number, bill.title, bill.description, bill.sponsor].join(' ').toLowerCase()
            }));
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
            APP_STATE.bills = (data.bills || []).map(bill => ({
                ...bill,
                committee: bill.committee ||
                    (bill.hearings && bill.hearings.length > 0
                        ? bill.hearings[bill.hearings.length - 1].committee
                        : ''),
                _searchText: [bill.number, bill.title, bill.description, bill.sponsor].join(' ').toLowerCase()
            }));
            APP_STATE.lastSync = data.lastSync || null;
            showToast('📦 Using cached data');
        } else {
            // No data available
            APP_STATE.bills = [];
            showToast('⚠️ No bill data available');
        }
    }
    
    updateSyncStatus();
    populateCommitteeFilters();
}

// Dynamically generate committee filter tags from loaded bill data
function populateCommitteeFilters() {
    const container = document.getElementById('committeeFilters');
    if (!container) return;

    const committees = new Set();
    APP_STATE.bills.forEach(bill => {
        if (bill.committee) committees.add(bill.committee);
    });

    if (committees.size === 0) {
        container.innerHTML = '<span style="color: var(--text-muted); font-size: 0.8rem;">No committee data available</span>';
        return;
    }

    const sorted = [...committees].sort();
    const house = sorted.filter(c => c.startsWith('House'));
    const senate = sorted.filter(c => c.startsWith('Senate'));

    let html = '';

    if (house.length > 0) {
        html += '<span class="filter-group-label">House</span>';
        house.forEach(c => {
            const value = c.toLowerCase();
            const label = c.replace('House ', '');
            html += '<span class="filter-tag" data-filter="committee" data-value="' + value + '">' + label + '</span>';
        });
    }
    if (senate.length > 0) {
        html += '<span class="filter-group-label">Senate</span>';
        senate.forEach(c => {
            const value = c.toLowerCase();
            const label = c.replace('Senate ', '');
            html += '<span class="filter-tag" data-filter="committee" data-value="' + value + '">' + label + '</span>';
        });
    }

    container.innerHTML = html;

    // Attach click listeners to the dynamically generated filter tags
    container.querySelectorAll('.filter-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const filterType = tag.dataset.filter;
            const value = tag.dataset.value;

            if (tag.classList.contains('active')) {
                tag.classList.remove('active');
                APP_STATE.filters[filterType] = APP_STATE.filters[filterType].filter(v => v !== value);
            } else {
                tag.classList.add('active');
                if (!Array.isArray(APP_STATE.filters[filterType])) {
                    APP_STATE.filters[filterType] = [];
                }
                APP_STATE.filters[filterType].push(value);
            }

            APP_STATE.pagination.page = 1;
            APP_STATE._dirty = true;
            updateUI();
            StorageManager.save();
            APP_STATE._dirty = false;
        });
    });

    // Restore active state from saved filters
    if (APP_STATE.filters.committee && APP_STATE.filters.committee.length > 0) {
        container.querySelectorAll('.filter-tag').forEach(tag => {
            if (APP_STATE.filters.committee.includes(tag.dataset.value)) {
                tag.classList.add('active');
            }
        });
    }
}

// Render Functions
function updateUI() {
    if (APP_STATE.currentView === 'main') {
        const filtered = filterBills();
        renderBills(filtered);
        updateStats(filtered);
        updateCutoffBanner();
        renderCutoffFailedBills();
    }
    updateUserPanel();
}

// Infinite scroll state
let scrollObserver = null;
let currentFilteredBills = [];

function renderBills(filteredBills) {
    const grid = document.getElementById('billsGrid');
    if (!filteredBills) filteredBills = filterBills();

    // Store for infinite scroll appending
    currentFilteredBills = filteredBills;
    APP_STATE.pagination.page = 1;

    if (filteredBills.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 3rem; color: var(--text-muted);">
                <h3 style="font-size: 1.5rem; margin-bottom: 1rem;">No bills found</h3>
                <p>Try adjusting your filters or search terms</p>
            </div>
        `;
        updatePageInfo(0, 0);
        return;
    }

    const { pageSize } = APP_STATE.pagination;
    const paginated = filteredBills.slice(0, pageSize);

    grid.innerHTML = paginated.map(bill => createBillCard(bill)).join('');
    updatePageInfo(paginated.length, filteredBills.length);
    setupInfiniteScroll();
}

function loadNextPage() {
    const { page, pageSize } = APP_STATE.pagination;
    const totalItems = currentFilteredBills.length;
    const totalPages = Math.ceil(totalItems / pageSize);

    if (page >= totalPages) return;

    APP_STATE.pagination.page++;
    const start = (APP_STATE.pagination.page - 1) * pageSize;
    const nextBills = currentFilteredBills.slice(start, start + pageSize);

    const grid = document.getElementById('billsGrid');
    grid.insertAdjacentHTML('beforeend', nextBills.map(createBillCard).join(''));

    const displayed = Math.min(APP_STATE.pagination.page * pageSize, totalItems);
    updatePageInfo(displayed, totalItems);
}

function setupInfiniteScroll() {
    const sentinel = document.getElementById('scrollSentinel');
    if (!sentinel) return;

    if (scrollObserver) scrollObserver.disconnect();

    // Hide old pagination buttons when IntersectionObserver is available
    const paginationControls = document.getElementById('paginationControls');
    if (paginationControls) paginationControls.innerHTML = '';

    scrollObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            loadNextPage();
        }
    }, { rootMargin: '300px' });

    scrollObserver.observe(sentinel);
}

function updatePageInfo(displayed, total) {
    const container = document.getElementById('paginationControls');
    if (!container) return;

    if (total === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = '<span class="page-info">Showing ' + displayed + ' of ' + total + ' bills</span>';
}

// Render cutoff-failed bills in their own section
function renderCutoffFailedBills() {
    const section = document.getElementById('cutoffFailedSection');
    const countEl = document.getElementById('cutoffFailedCount');
    const container = document.getElementById('cutoffFailedBills');

    if (!section || !container) return;

    // Get all 2026 session bills that missed a cutoff
    const cutoffFailedBills = APP_STATE.bills.filter(bill => {
        if (bill.session === '2025') return false;
        return getBillCutoffStatus(bill) !== null;
    });

    // Update count display
    countEl.textContent = `(${cutoffFailedBills.length})`;

    // Hide section if no cutoff-failed bills
    if (cutoffFailedBills.length === 0) {
        section.style.display = 'none';
        return;
    }
    section.style.display = 'block';

    // Group bills by which cutoff they missed
    const groupedBills = {};
    cutoffFailedBills.forEach(bill => {
        const cutoffLabel = getBillCutoffStatus(bill);
        if (!groupedBills[cutoffLabel]) {
            groupedBills[cutoffLabel] = [];
        }
        groupedBills[cutoffLabel].push(bill);
    });

    // Build grouped HTML
    let html = '';

    // Sort groups by cutoff date order (use config order)
    const cutoffOrder = APP_CONFIG.cutoffDates.map(c => c.label);
    const sortedGroups = Object.keys(groupedBills).sort((a, b) => {
        return cutoffOrder.indexOf(a) - cutoffOrder.indexOf(b);
    });

    sortedGroups.forEach(cutoffLabel => {
        const bills = groupedBills[cutoffLabel];
        const cutoffInfo = APP_CONFIG.cutoffDates.find(c => c.label === cutoffLabel);
        const dateStr = cutoffInfo ? new Date(cutoffInfo.date + 'T00:00:00').toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        }) : '';

        html += `
            <div class="cutoff-group">
                <div class="cutoff-group-header">
                    <span class="cutoff-group-label">${escapeHTML(cutoffLabel)}</span>
                    <span class="cutoff-group-date">${dateStr}</span>
                    <span class="cutoff-group-count">${bills.length} bill${bills.length !== 1 ? 's' : ''}</span>
                </div>
                <div class="cutoff-failed-bills-grid">
                    ${bills.map(bill => createBillCard(bill)).join('')}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function updateCutoffBanner() {
    const banner = document.getElementById('cutoffBanner');
    if (!banner) return;

    const next = getNextCutoff();
    if (!next) {
        banner.style.display = 'none';
        return;
    }

    const dateStr = next.dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const daysText = next.daysUntil === 0 ? 'Today' : next.daysUntil + ' day' + (next.daysUntil !== 1 ? 's' : '') + ' away';
    banner.style.display = 'flex';
    banner.innerHTML =
        '<span>📅</span>' +
        '<span class="cutoff-label">Next cutoff: ' + next.label + ' — ' + dateStr + '</span>' +
        '<span class="cutoff-days">' + daysText + '</span>';

    // Show/hide the cutoff explainer banner based on whether any cutoff has passed
    updateCutoffExplainerVisibility();
}

// Show cutoff explainer banner on cutoff day or after
function updateCutoffExplainerVisibility() {
    const explainerBanner = document.getElementById('cutoffExplainerBanner');
    if (!explainerBanner) return;

    // Check if today is a cutoff day OR any cutoff has already passed
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    const isCutoffDayOrAfter = APP_CONFIG.cutoffDates.some(cutoff => {
        const cutoffDate = new Date(cutoff.date + 'T00:00:00');
        const cutoffDay = new Date(cutoffDate.getFullYear(), cutoffDate.getMonth(), cutoffDate.getDate());
        return today >= cutoffDay;
    });

    // Also check if there are any bills that would miss cutoff (status still in failing state)
    const hasBillsAtRisk = APP_STATE.bills.some(bill => {
        if (bill.session === '2025') return false;
        // Check if bill status is in a "failing" category for any passed/current cutoff
        const status = bill.status;
        return APP_CONFIG.cutoffDates.some(cutoff => {
            const cutoffDate = new Date(cutoff.date + 'T00:00:00');
            const cutoffDay = new Date(cutoffDate.getFullYear(), cutoffDate.getMonth(), cutoffDate.getDate());
            return today >= cutoffDay && cutoff.failsBefore.includes(status);
        });
    });

    // Show banner on cutoff day or after if there are bills at risk or already failed
    if (isCutoffDayOrAfter && hasBillsAtRisk) {
        // Don't override if already dismissed
        if (!explainerBanner.classList.contains('dismissed')) {
            explainerBanner.style.display = 'block';
        }
    } else {
        explainerBanner.style.display = 'none';
    }
}

function goToPage(page) {
    // Legacy — kept for compatibility. Infinite scroll handles navigation now.
    updateUI();
}

// Human-readable status labels
const STATUS_LABELS = {
    'prefiled': 'Pre-filed',
    'introduced': 'Introduced',
    'committee': 'In Committee',
    'floor': 'Floor Vote',
    'passed_origin': 'Passed Chamber',
    'passed': 'Passed Chamber',
    'opposite_committee': 'Opposite Committee',
    'opposite_floor': 'Opposite Floor',
    'passed_legislature': 'Passed Legislature',
    'governor': 'Governor',
    'enacted': 'Enacted',
    'vetoed': 'Vetoed',
    'failed': 'Failed'
};

// Map bill status to a numeric stage index across the full legislative lifecycle.
// Origin chamber:     0=Prefiled  1=Introduced  2=Committee  3=Floor  4=Passed
// Opposite chamber:   5=Committee  6=Floor
// Final:              7=Governor   8=Enacted
// Special:            -1=Failed, -2=Vetoed
function getBillStageIndex(bill) {
    const status = (bill.status || '').toLowerCase();
    const history = (bill.historyLine || '').toLowerCase();

    // New granular statuses (from updated fetch script)
    if (status === 'enacted')               return 8;
    if (status === 'governor')              return 7;
    if (status === 'passed_legislature')    return 7; // awaiting governor
    if (status === 'opposite_floor')        return 6;
    if (status === 'opposite_committee')    return 5;
    if (status === 'passed_origin')         return 4;
    if (status === 'floor')                 return 3;
    if (status === 'vetoed')                return -2;
    if (status === 'failed')                return -1;

    // Legacy statuses (from existing bills.json before next fetch)
    if (status === 'passed')                return 4;
    if (status === 'committee')             return 2;
    if (status === 'introduced')            return 1;

    // Fallback: infer from historyLine
    if (history.includes('effective date') || history.includes('governor signed'))   return 8;
    if (history.includes('delivered to governor'))                                    return 7;
    if (history.includes('third reading') && history.includes('passed'))             return 4;
    if (history.includes('second reading') || history.includes('third reading'))     return 3;
    if (history.includes('rules committee') || history.includes('placed on'))        return 3;
    if (history.includes('referred to'))                                             return 2;
    if (history.includes('first reading'))                                           return 1;

    return 0; // prefiled
}

// Build a leg.wa.gov-style two-section status progress tracker
function buildProgressTracker(bill) {
    const agency = (bill.originalAgency || '').toLowerCase();
    const originLabel  = agency === 'senate' ? 'Senate' : 'House';
    const oppositeLabel = agency === 'senate' ? 'House' : 'Senate';

    const stageIndex = getBillStageIndex(bill);
    const isFailed = stageIndex === -1;
    const isVetoed = stageIndex === -2;
    // For failed/vetoed, infer how far the bill got from historyLine
    let failedAt = 0;
    if (isFailed || isVetoed) {
        const history = (bill.historyLine || '').toLowerCase();
        if (isVetoed)                                                    failedAt = 7;
        else if (history.includes('third reading') || history.includes('floor')) failedAt = 3;
        else if (history.includes('committee') || history.includes('referred'))  failedAt = 2;
        else if (history.includes('first reading'))                              failedAt = 1;
        else                                                                     failedAt = 1;
    }
    const effectiveIndex = (isFailed || isVetoed) ? failedAt : stageIndex;

    // Section 1: Origin chamber
    const originStages = [
        { idx: 0, label: 'Prefiled' },
        { idx: 1, label: 'Introduced' },
        { idx: 2, label: 'Committee' },
        { idx: 3, label: 'Floor' },
        { idx: 4, label: 'Passed' }
    ];

    // Section 2: Opposite chamber + Final
    const finalStages = [
        { idx: 5, label: 'Committee' },
        { idx: 6, label: 'Floor' },
        { idx: 7, label: 'Governor' },
        { idx: 8, label: 'Enacted' }
    ];

    function renderSection(stages, sectionLabel) {
        let html = `<div class="bill-progress-section">`;
        html += `<span class="bill-progress-section-label">${sectionLabel}</span>`;
        html += `<div class="bill-progress-row">`;

        stages.forEach((stage, i) => {
            if (i > 0) {
                const lineOn = effectiveIndex >= stage.idx && !(isFailed || isVetoed);
                html += `<div class="bill-progress-line${lineOn ? ' completed' : ''}"></div>`;
            }

            let cls = '';
            if ((isFailed || isVetoed) && stage.idx === failedAt) {
                cls = isFailed ? 'failed' : 'vetoed';
            } else if (effectiveIndex > stage.idx) {
                cls = 'completed';
            } else if (effectiveIndex === stage.idx && !(isFailed || isVetoed)) {
                cls = stage.idx === 8 ? 'enacted' : 'active';
            }

            html += `<div class="bill-progress-step ${cls}" title="${stage.label}">`;
            html += `<div class="bill-progress-dot"></div>`;
            html += `<span class="bill-progress-label">${stage.label}</span>`;
            html += `</div>`;
        });

        html += `</div></div>`;
        return html;
    }

    let html = '<div class="bill-progress-tracker">';
    html += renderSection(originStages, originLabel);
    html += renderSection(finalStages, oppositeLabel);
    html += '</div>';
    return html;
}

function createBillCard(bill) {
    const isTracked = APP_STATE.trackedBills.has(bill.id);
    const hasNotes = APP_STATE.userNotes[bill.id] && APP_STATE.userNotes[bill.id].length > 0;
    const hasHearings = bill.hearings && bill.hearings.length > 0;
    const isFrom2025 = bill.session === '2025';
    const cutoffStatus = getBillCutoffStatus(bill);
    const isInactive = isFrom2025 || cutoffStatus;

    let latestNote = '';
    if (hasNotes) {
        const notes = APP_STATE.userNotes[bill.id];
        latestNote = escapeHTML(notes[notes.length - 1].text);
        if (latestNote.length > 100) {
            latestNote = latestNote.substring(0, 100) + '...';
        }
    }

    return `
        <div class="bill-card ${isTracked ? 'tracked' : ''} ${isInactive ? 'inactive-bill' : ''}" data-bill-id="${escapeHTML(bill.id)}">
            <div class="bill-header">
                <a href="https://app.leg.wa.gov/billsummary?BillNumber=${encodeURIComponent(bill.number.split(' ').pop())}&Year=2026"
                   target="_blank" rel="noopener noreferrer" class="bill-number">${escapeHTML(bill.number)}</a>
                <div class="bill-title">${escapeHTML(bill.title)}</div>
            </div>

            ${buildProgressTracker(bill)}

            <div class="bill-body">
                <div class="bill-meta">
                    <span class="meta-item">👤 ${escapeHTML(bill.sponsor)}</span>
                    <span class="meta-item">🏛️ ${escapeHTML(bill.committee)}</span>
                    ${hasHearings ? `<span class="meta-item" style="color: var(--warning);">📅 ${escapeHTML(bill.hearings[0].date)}</span>` : ''}
                </div>

                <div class="bill-description">${escapeHTML(bill.description)}</div>

                ${hasNotes ? `<div class="bill-notes-preview">📝 "${latestNote}"</div>` : ''}

                <div class="bill-tags">
                    <span class="tag status-${escapeHTML(bill.status)}">${escapeHTML(STATUS_LABELS[bill.status] || bill.status)}</span>
                    <span class="tag priority-${escapeHTML(bill.priority)}">${escapeHTML(bill.priority)} priority</span>
                    <span class="tag">${escapeHTML(bill.topic)}</span>
                    ${isFrom2025 ? '<span class="tag session-2025">2025 Session</span>' : ''}
                    ${cutoffStatus ? '<span class="tag cutoff-failed">Missed: ' + escapeHTML(cutoffStatus) + '</span>' : ''}
                </div>
            </div>

            <div class="bill-actions">
                <button class="action-btn ${isTracked ? 'active' : ''}" data-action="track" data-bill-id="${escapeHTML(bill.id)}">
                    ${isTracked ? '⭐ Tracked' : '☆ Track'}
                </button>
                <button class="action-btn" data-action="note" data-bill-id="${escapeHTML(bill.id)}">
                    📝 ${hasNotes ? 'Notes (' + APP_STATE.userNotes[bill.id].length + ')' : 'Add Note'}
                </button>
                <button class="action-btn" data-action="share" data-bill-id="${escapeHTML(bill.id)}">
                    🔗 Share
                </button>
                <a href="https://app.leg.wa.gov/pbc/bill/${encodeURIComponent(bill.number.split(' ').pop())}"
                   target="_blank" rel="noopener noreferrer" class="action-btn" title="Contact your legislator about this bill">
                    ✉ Contact
                </a>
                <a href="https://app.leg.wa.gov/billsummary/Home/GetEmailNotifications?billTitle=${encodeURIComponent(bill.number.replace(' ', ' ') + '-' + bill.biennium)}&billNumber=${encodeURIComponent(bill.number.split(' ').pop())}&year=${encodeURIComponent(bill.biennium.split('-')[0])}&agency=${encodeURIComponent(bill.originalAgency)}&initiative=False"
                   target="_blank" rel="noopener noreferrer" class="action-btn" title="Follow this bill by email on leg.wa.gov">
                    📧 Follow
                </a>
            </div>
        </div>
    `;
}

// Filter Bills
// Parse a YYYY-MM-DD date string as end-of-day in local time (11:59:59 PM).
// Cutoff dates represent the LAST day for action, so the cutoff doesn't pass
// until the day is over.
function endOfDayLocal(dateStr) {
    const [y, m, d] = dateStr.split('-').map(Number);
    return new Date(y, m - 1, d, 23, 59, 59);
}

// Determine if a bill has effectively failed based on legislative cutoff dates.
// Returns the cutoff label if the bill missed a deadline, or null if still active.
function getBillCutoffStatus(bill) {
    // Only applies to 2026 session bills
    if (bill.session === '2025') return null;
    // Already terminal — not a cutoff failure
    if (['enacted', 'vetoed', 'failed', 'partial_veto'].includes(bill.status)) return null;

    const now = new Date();
    let cutoffLabel = null;

    for (const cutoff of APP_CONFIG.cutoffDates) {
        if (now <= endOfDayLocal(cutoff.date)) break; // cutoff day hasn't ended yet
        if (cutoff.failsBefore.includes(bill.status)) {
            cutoffLabel = cutoff.label;
            // Don't break — later cutoffs may also apply
        }
    }
    return cutoffLabel;
}

// Get the next upcoming cutoff date
function getNextCutoff() {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    for (const cutoff of APP_CONFIG.cutoffDates) {
        const cutoffEnd = endOfDayLocal(cutoff.date);
        if (cutoffEnd > now) {
            const cutoffDay = new Date(cutoffEnd.getFullYear(), cutoffEnd.getMonth(), cutoffEnd.getDate());
            const daysUntil = Math.round((cutoffDay - today) / (1000 * 60 * 60 * 24));
            return { ...cutoff, daysUntil, dateObj: cutoffEnd };
        }
    }
    return null; // all cutoffs passed
}

function filterBills() {
    let filtered = [...APP_STATE.bills];

    console.log('filterBills called:', {
        currentBillType: APP_STATE.currentBillType,
        totalBills: APP_STATE.bills.length
    });

    // Filter out inactive bills (2025 session + cutoff failures) unless toggle is on
    if (!APP_STATE.filters.showInactiveBills) {
        filtered = filtered.filter(bill => {
            // Hide 2025 session bills
            if (bill.session === '2025') return false;
            // Hide bills that missed a cutoff deadline
            if (getBillCutoffStatus(bill)) return false;
            return true;
        });
    }
    
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
        filtered = filtered.filter(bill => bill._searchText.includes(search));
    }
    
    if (APP_STATE.filters.status && APP_STATE.filters.status.length > 0) {
        // Expand selected filters to also match related statuses
        // (handles backward compatibility and logical grouping)
        const statusAliases = {
            'prefiled':      ['prefiled'],
            'introduced':    ['introduced'],
            'committee':     ['committee', 'opposite_committee'],
            'floor':         ['floor', 'opposite_floor'],
            'passed_origin': ['passed_origin', 'passed', 'passed_legislature'],
            'passed':        ['passed', 'passed_origin', 'passed_legislature'],
            'governor':      ['governor'],
            'enacted':       ['enacted'],
            'vetoed':        ['vetoed'],
            'failed':        ['failed']
        };
        const expandedStatuses = new Set();
        APP_STATE.filters.status.forEach(s => {
            (statusAliases[s] || [s]).forEach(v => expandedStatuses.add(v));
        });
        filtered = filtered.filter(bill => expandedStatuses.has(bill.status));
    }

    if (APP_STATE.filters.priority && APP_STATE.filters.priority.length > 0) {
        filtered = filtered.filter(bill => APP_STATE.filters.priority.includes(bill.priority));
    }

    if (APP_STATE.filters.committee && APP_STATE.filters.committee.length > 0) {
        filtered = filtered.filter(bill =>
            bill.committee && APP_STATE.filters.committee.some(c => bill.committee.toLowerCase() === c)
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

    APP_STATE._dirty = true;
    StorageManager.save();
    APP_STATE._dirty = false;
    updateUI();
}

// Note Management
function formatNoteDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
        hour: 'numeric', minute: '2-digit'
    });
}

function openNoteModal(billId) {
    APP_STATE.currentNoteBillId = billId;
    const bill = APP_STATE.bills.find(b => b.id === billId);

    document.getElementById('noteModalTitle').textContent = `Notes for ${bill.number}`;

    const existingNotes = APP_STATE.userNotes[billId] || [];
    const container = document.getElementById('existingNotes');
    if (existingNotes.length > 0) {
        container.innerHTML = existingNotes.map((note, i) => `
            <div class="existing-note-item">
                <textarea class="existing-note-textarea" data-note-index="${i}">${escapeHTML(note.text)}</textarea>
                <div class="existing-note-date">${formatNoteDateTime(note.date)}</div>
            </div>
        `).join('');
    } else {
        container.innerHTML = '';
    }
    document.getElementById('noteTextarea').value = '';

    document.getElementById('noteModal').classList.add('active');
}

function closeNoteModal() {
    document.getElementById('noteModal').classList.remove('active');
    APP_STATE.currentNoteBillId = null;
}

function saveNote() {
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
    showToast('📝 Note saved');
    updateUI();
}

// Share Bill - Uses wa-bill-tracker URL
function shareBill(billId) {
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
        }).catch(err => {
            navigator.clipboard.writeText(clipboardText);
            showToast('🔗 Link copied to clipboard');
        });
    } else {
        navigator.clipboard.writeText(clipboardText);
        showToast('🔗 Link copied to clipboard');
    }
}

// Share Note from modal
function shareNote() {
    const billId = APP_STATE.currentNoteBillId;
    if (!billId) return;
    const bill = APP_STATE.bills.find(b => b.id === billId);
    if (!bill) return;

    const existingNotes = APP_STATE.userNotes[billId] || [];
    const currentText = document.getElementById('noteTextarea').value.trim();
    if (existingNotes.length === 0 && !currentText) {
        showToast('No notes to share');
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
        }).catch(err => {
            navigator.clipboard.writeText(clipboardText);
            showToast('🔗 Note link copied to clipboard');
        });
    } else {
        navigator.clipboard.writeText(clipboardText);
        showToast('🔗 Note link copied to clipboard');
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
            ${trackedBills.map(bill => {
                const statusLabel = STATUS_LABELS[bill.status] || bill.status;
                const hasHearings = bill.hearings && bill.hearings.length > 0;
                const billNum = bill.number.split(' ').pop();
                return `
                <div class="tracked-bill-card" data-highlight-bill="${bill.id}">
                    <div class="tracked-bill-header">
                        <a href="https://app.leg.wa.gov/billsummary?BillNumber=${billNum}&Year=2026"
                           target="_blank" rel="noopener noreferrer" class="bill-number"
                           onclick="event.stopPropagation();">${escapeHTML(bill.number)}</a>
                        <span class="tracked-bill-title">${escapeHTML(bill.title)}</span>
                    </div>
                    <div class="tracked-bill-meta">
                        <span class="meta-item">👤 ${escapeHTML(bill.sponsor)}</span>
                        <span class="tag status-${bill.status}">${escapeHTML(statusLabel)}</span>
                        ${hasHearings ? `<span class="meta-item" style="color: var(--warning);">📅 ${escapeHTML(bill.hearings[0].date)}${bill.hearings[0].committee ? ' — ' + escapeHTML(bill.hearings[0].committee) : ''}</span>` : ''}
                    </div>
                </div>`;
            }).join('')}
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
                <div class="stats-item" data-highlight-bill="${bill.id}" style="cursor: pointer;">
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
                <div class="stats-item" data-highlight-bill="${item.bill.id}" style="cursor: pointer;">
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
    const totalDays = Math.ceil((APP_CONFIG.sessionEnd - APP_CONFIG.sessionStart) / (1000 * 60 * 60 * 24));
    const daysPassed = totalDays - daysLeft;
    const percentComplete = Math.round((daysPassed / totalDays) * 100);

    const totalBills = APP_STATE.bills.length;
    const session2026 = APP_STATE.bills.filter(b => b.session !== '2025').length;
    const session2025 = totalBills - session2026;
    const activeBills = APP_STATE.bills.filter(b => b.session !== '2025' && !getBillCutoffStatus(b)).length;

    const next = getNextCutoff();
    const nextCutoffHtml = next
        ? `<div class="stats-item">
               <span class="stats-item-label">Next Cutoff: ${next.label}</span>
               <span class="stats-item-value">${next.daysUntil} day${next.daysUntil !== 1 ? 's' : ''}</span>
           </div>`
        : '';

    return `
        <h2>Session Progress</h2>
        <div class="stats-list">
            <div class="stats-item">
                <span class="stats-item-label">Days Remaining</span>
                <span class="stats-item-value">${Math.max(0, daysLeft)}</span>
            </div>
            <div class="stats-item">
                <span class="stats-item-label">Session Progress</span>
                <span class="stats-item-value">${percentComplete}%</span>
            </div>
            ${nextCutoffHtml}
            <div class="stats-item">
                <span class="stats-item-label">Active 2026 Bills</span>
                <span class="stats-item-value">${activeBills}</span>
            </div>
            <div class="stats-item">
                <span class="stats-item-label">2025 Session (enacted)</span>
                <span class="stats-item-value">${session2025}</span>
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
function updateStats(filteredBills) {
    // Get filtered bills for current page
    if (!filteredBills) filteredBills = filterBills();
    
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
                <div class="user-note-bill" data-highlight-bill="${escapeHTML(note.billId)}" style="cursor: pointer;">
                    ${escapeHTML(note.billNumber)}: ${escapeHTML(note.billTitle)}
                </div>
                <div class="user-note-text">${escapeHTML(note.text.substring(0, 100))}${note.text.length > 100 ? '...' : ''}</div>
                <div class="user-note-date">${formatDate(note.date)}</div>
            </div>
        `).join('');
    }
}

function formatNotesForExport() {
    const lines = [];
    Object.entries(APP_STATE.userNotes).forEach(([billId, notes]) => {
        const bill = APP_STATE.bills.find(b => b.id === billId);
        const billLabel = bill ? `${bill.number} — ${bill.title}` : billId;
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
        lines.push(`Notes by ${APP_STATE.userData.name} — WA Bill Tracker — https://wa-bill-tracker.org`);
    }
    return lines.join('\n');
}

async function copyAllNotes() {
    const text = formatNotesForExport();
    if (!text) { showToast('No notes to copy'); return; }
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
    showToast('Notes copied to clipboard');
}

function emailAllNotes() {
    const text = formatNotesForExport();
    if (!text) { showToast('No notes to email'); return; }
    const subject = encodeURIComponent('My WA Bill Tracker Notes');
    const body = encodeURIComponent(text);
    window.open(`mailto:?subject=${subject}&body=${body}`);
}

function exportNotesCSV() {
    const entries = Object.entries(APP_STATE.userNotes);
    if (entries.length === 0) { showToast('No notes to export'); return; }

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
    showToast('Notes exported to CSV');
}

function parseCSVRow(row) {
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

function importNotesCSV() {
    const fileInput = document.getElementById('csvFileInput');
    const file = fileInput.files[0];
    if (!file) return;
    fileInput.value = ''; // reset so same file can be re-selected

    const reader = new FileReader();
    reader.onload = function(e) {
        const text = e.target.result;
        const lines = text.split(/\r?\n/).filter(line => line.trim());

        if (lines.length < 2) {
            showToast('CSV file is empty or has no data rows');
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
        showToast(parts.length > 0 ? 'Imported: ' + parts.join(', ') : 'No new data to import');
    };

    reader.onerror = function() {
        showToast('Error reading CSV file');
    };

    reader.readAsText(file);
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
    const debouncedSearch = debounce(() => {
        updateUI();
    }, 250);

    document.getElementById('searchInput').addEventListener('input', (e) => {
        APP_STATE.filters.search = sanitizeInput(e.target.value, 200);
        APP_STATE.pagination.page = 1;
        debouncedSearch();
    });
    
    document.querySelectorAll('.filter-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const filter = tag.dataset.filter;
            const value = tag.dataset.value;

            // Toggle this tag on or off (multi-select)
            if (tag.classList.contains('active')) {
                tag.classList.remove('active');
                APP_STATE.filters[filter] = APP_STATE.filters[filter].filter(v => v !== value);
            } else {
                tag.classList.add('active');
                if (!Array.isArray(APP_STATE.filters[filter])) {
                    APP_STATE.filters[filter] = [];
                }
                APP_STATE.filters[filter].push(value);
            }

            APP_STATE.pagination.page = 1;
            APP_STATE._dirty = true;
            updateUI();
            StorageManager.save();
            APP_STATE._dirty = false;
        });
    });

    // Inactive bills toggle
    const inactiveToggle = document.getElementById('showInactiveBills');
    if (inactiveToggle) {
        inactiveToggle.addEventListener('change', (e) => {
            APP_STATE.filters.showInactiveBills = e.target.checked;
            APP_STATE.pagination.page = 1;
            updateUI();
        });
    }

    // Bill action button delegation
    document.getElementById('billsGrid').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-action]');
        if (!btn) return;

        const billId = btn.dataset.billId;
        switch (btn.dataset.action) {
            case 'track': toggleTrack(billId); break;
            case 'note': openNoteModal(billId); break;
            case 'share': shareBill(billId); break;
        }
    });

    // User panel toggle (all screen sizes)
    const panel = document.getElementById('userPanel');
    const avatar = document.getElementById('userAvatar');

    // Restore saved panel state
    const savedPanelState = CookieManager.get('wa_tracker_panel_collapsed');
    if (savedPanelState === '1') {
        panel.classList.add('panel-collapsed');
    }

    avatar.addEventListener('click', (e) => {
        e.stopPropagation();
        if (window.innerWidth <= 768) {
            panel.classList.toggle('mobile-expanded');
        } else {
            panel.classList.toggle('panel-collapsed');
            const isCollapsed = panel.classList.contains('panel-collapsed');
            CookieManager.set('wa_tracker_panel_collapsed', isCollapsed ? '1' : '0', 365);
        }
    });

    document.addEventListener('click', (e) => {
        if (window.innerWidth > 768) return;
        if (!panel.contains(e.target)) {
            panel.classList.remove('mobile-expanded');
        }
    });

    // --- Delegated handlers replacing inline onclick attributes ---

    // Stats cards
    document.querySelectorAll('.stat-card[data-stat]').forEach(card => {
        card.addEventListener('click', (e) => {
            e.preventDefault();
            showStatsDetail(card.dataset.stat);
        });
    });

    // Filter toggle, tracked toggle, refresh
    document.getElementById('filterToggle').addEventListener('click', toggleFilters);
    document.getElementById('trackedToggle').addEventListener('click', toggleTrackedOnly);
    document.getElementById('refreshBtn').addEventListener('click', refreshData);

    // Back to main view
    document.getElementById('backToMainBtn').addEventListener('click', (e) => {
        e.preventDefault();
        showMainView();
    });

    // User panel expand
    document.getElementById('expandBtn').addEventListener('click', toggleUserPanel);
    document.getElementById('userName').addEventListener('click', changeUserName);

    // Notes export buttons (safe-bind so one missing element doesn't break the rest)
    const safeBind = (id, event, handler) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener(event, handler);
    };
    safeBind('copyNotesBtn', 'click', copyAllNotes);
    safeBind('emailNotesBtn', 'click', emailAllNotes);
    safeBind('csvNotesBtn', 'click', exportNotesCSV);
    safeBind('importCsvBtn', 'click', () => {
        document.getElementById('csvFileInput').click();
    });
    safeBind('csvFileInput', 'change', importNotesCSV);

    // Note modal buttons
    document.getElementById('noteModalClose').addEventListener('click', closeNoteModal);
    document.getElementById('noteModalCancel').addEventListener('click', closeNoteModal);
    document.getElementById('noteModalShare').addEventListener('click', shareNote);
    document.getElementById('noteModalSave').addEventListener('click', saveNote);

    // Delegated handler for highlight-bill links (stats detail, user notes)
    document.addEventListener('click', (e) => {
        const el = e.target.closest('[data-highlight-bill]');
        if (el) {
            e.preventDefault();
            highlightBill(el.dataset.highlightBill);
        }
    });

    // Cutoff failed section toggle
    const cutoffToggle = document.getElementById('cutoffFailedToggle');
    if (cutoffToggle) {
        cutoffToggle.addEventListener('click', () => {
            const section = document.getElementById('cutoffFailedSection');
            const isExpanded = section.classList.toggle('expanded');
            cutoffToggle.setAttribute('aria-expanded', isExpanded);
        });
    }

    // Cutoff explainer banner toggle and dismiss
    const explainerToggle = document.getElementById('cutoffExplainerToggle');
    const explainerDismiss = document.getElementById('cutoffExplainerDismiss');
    const explainerBanner = document.getElementById('cutoffExplainerBanner');

    if (explainerToggle && explainerBanner) {
        explainerToggle.addEventListener('click', () => {
            const isExpanded = explainerBanner.classList.toggle('expanded');
            explainerToggle.setAttribute('aria-expanded', isExpanded);
        });
    }

    if (explainerDismiss && explainerBanner) {
        explainerDismiss.addEventListener('click', () => {
            explainerBanner.classList.add('dismissed');
            CookieManager.set('wa_tracker_cutoff_banner_dismissed', '1', 7); // Dismiss for 7 days
        });

        // Check if banner was previously dismissed
        if (CookieManager.get('wa_tracker_cutoff_banner_dismissed') === '1') {
            explainerBanner.classList.add('dismissed');
        }
    }

    // Delegated handler for bill actions in cutoff-failed section
    const cutoffContainer = document.getElementById('cutoffFailedBills');
    if (cutoffContainer) {
        cutoffContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;

            const billId = btn.dataset.billId;
            switch (btn.dataset.action) {
                case 'track': toggleTrack(billId); break;
                case 'note': openNoteModal(billId); break;
                case 'share': shareBill(billId); break;
            }
        });
    }
}

// Auto-save functionality
function setupAutoSave() {
    setInterval(() => {
        if (APP_STATE._dirty) {
            StorageManager.save();
            APP_STATE._dirty = false;
        }
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
    APP_STATE.pagination.page = 1;
    updateUI();
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
