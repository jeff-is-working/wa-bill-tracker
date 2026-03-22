// state.js -- Application state, cookie management, storage, and domain migration

import { APP_CONFIG } from './config.js';

// Session-aware storage key prefix
let _storagePrefix = 'wa_tracker_';

export function setStoragePrefix(year) {
    _storagePrefix = `wa_tracker_${year}_`;
}

export function getStorageKey(name) {
    return `${_storagePrefix}${name}`;
}

// Application State
export const APP_STATE = {
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
    currentBillType: 'all',
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

// Cookie Management with Long-term Persistence
export const CookieManager = {
    // Set a cookie with proper SameSite and long expiration
    set(name, value, days) {
        if (days === undefined) days = APP_CONFIG ? APP_CONFIG.cookieDuration : 90;
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

// Domain Migration -- transfer user data from old github.io domain to new custom domain
export const DomainMigration = {
    OLD_DOMAIN: 'jeff-is-working.github.io',
    NEW_DOMAIN: 'wa-bill-tracker.org',

    _getCookieKeys() {
        return [
            getStorageKey('tracked'), getStorageKey('notes'), getStorageKey('user'),
            getStorageKey('filters'), getStorageKey('bill_type'), getStorageKey('user_id'),
            getStorageKey('user_name'), getStorageKey('panel_collapsed')
        ];
    },

    // On old domain: collect all user data and redirect to new domain with data in hash
    exportAndRedirect() {
        if (location.hostname !== this.OLD_DOMAIN) return false;

        const cookieKeys = this._getCookieKeys();
        const data = {};
        let hasData = false;
        for (const key of cookieKeys) {
            const val = CookieManager.get(key);
            if (val !== null && val !== undefined) {
                data[key] = val;
                hasData = true;
            }
        }
        // Also grab localStorage backup
        const lsState = localStorage.getItem(getStorageKey('state'));
        if (lsState) {
            data._ls_state = lsState;
            hasData = true;
        }

        if (hasData) {
            const encoded = encodeURIComponent(JSON.stringify(data));
            location.replace(`https://${this.NEW_DOMAIN}/#migrate=${encoded}`);
            return true;
        }
        return false;
    },

    // On new domain: check for migration data in URL hash and import it
    importFromHash() {
        if (!location.hash.startsWith('#migrate=')) return false;

        try {
            const encoded = location.hash.substring('#migrate='.length);
            const data = JSON.parse(decodeURIComponent(encoded));

            const cookieKeys = this._getCookieKeys();
            for (const key of cookieKeys) {
                if (data[key] !== undefined) {
                    CookieManager.set(key, data[key], key.includes('panel') || key.includes('user_id') ? 365 : undefined);
                }
            }
            if (data._ls_state) {
                localStorage.setItem(getStorageKey('state'), data._ls_state);
            }

            history.replaceState(null, '', location.pathname + location.search);
            console.log('Migration complete -- user data imported from previous domain');
            return true;
        } catch (e) {
            console.error('Migration import failed:', e);
            history.replaceState(null, '', location.pathname + location.search);
            return false;
        }
    }
};

// LocalStorage Backup for Additional Persistence
export const StorageManager = {
    save() {
        try {
            // Save to cookies (primary)
            CookieManager.set(getStorageKey('tracked'), Array.from(APP_STATE.trackedBills));
            CookieManager.set(getStorageKey('notes'), APP_STATE.userNotes);
            CookieManager.set(getStorageKey('user'), APP_STATE.userData);
            CookieManager.set(getStorageKey('filters'), APP_STATE.filters);
            CookieManager.set(getStorageKey('bill_type'), APP_STATE.currentBillType);

            // Save to localStorage (backup)
            localStorage.setItem(getStorageKey('state'), JSON.stringify({
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
            const trackedFromCookie = CookieManager.get(getStorageKey('tracked'));
            const notesFromCookie = CookieManager.get(getStorageKey('notes'));
            const userFromCookie = CookieManager.get(getStorageKey('user'));
            const filtersFromCookie = CookieManager.get(getStorageKey('filters'));
            const billTypeFromCookie = CookieManager.get(getStorageKey('bill_type'));

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
            const saved = localStorage.getItem(getStorageKey('state'));
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
export function migrateFiltersToArrays() {
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
export function syncFilterTagUI() {
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
