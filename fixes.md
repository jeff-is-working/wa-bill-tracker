# Mobile Performance Fixes - Implementation Plan

**GitHub Issue:** #1 - Mobile devices struggle to load and navigate the page
**Date:** 2026-01-29

This document provides a step-by-step implementation plan for all 14 issues identified in the mobile performance analysis. Fixes are grouped into phases by dependency and impact.

---

## Phase 1: Quick CSS Wins (index.html only)

These changes are isolated to `index.html` CSS, have no JS dependencies, and deliver immediate scroll/render improvements on mobile.

### Fix 1.1: Disable background animation on mobile and for reduced-motion users
**Issue:** #6 - Full-screen animated gradient background
**File:** `index.html` (lines 50-71)

**Changes:**
- Add `@media (prefers-reduced-motion: reduce)` rule to disable the `float` animation on `body::before` and set a static background instead
- Add `@media (max-width: 768px)` rule to disable the animation and simplify to a single `radial-gradient` or static color on mobile
- Example:
```css
@media (prefers-reduced-motion: reduce) {
    body::before {
        animation: none;
        transform: none;
    }
}
@media (max-width: 768px) {
    body::before {
        animation: none;
        transform: none;
        background: radial-gradient(circle at 50% 50%, var(--glow) 0%, transparent 60%);
    }
}
```

### Fix 1.2: Replace `backdrop-filter` with solid background on mobile
**Issue:** #5 - `backdrop-filter: blur()` on sticky header
**File:** `index.html` (lines 74-82)

**Changes:**
- Keep `backdrop-filter` for desktop (it looks good and desktop GPUs handle it)
- In the `@media (max-width: 768px)` block, override the header background to a fully opaque color and remove the blur:
```css
@media (max-width: 768px) {
    header {
        background: rgba(30, 41, 59, 1);
        -webkit-backdrop-filter: none;
        backdrop-filter: none;
    }
}
```

### Fix 1.3: Scope `transition: all` to specific properties
**Issue:** #7 - `transition: all 0.3s` on 10+ element types
**File:** `index.html` (lines ~121, 181, 247, 312, 338, 363, 455, 613, 736, 899)

**Changes for each element:**

| Selector | Current | Replace With |
|----------|---------|-------------|
| `.sync-status` (line 121) | `transition: all 0.3s` | `transition: opacity 0.3s, background-color 0.3s` |
| `.nav-tab` (line 181) | `transition: all 0.3s` | `transition: color 0.3s, border-color 0.3s, background-color 0.3s` |
| `.stat-card` (line 247) | `transition: all 0.3s` | `transition: transform 0.3s, box-shadow 0.3s, border-color 0.3s` |
| `.search-input` (line 312) | `transition: all 0.3s` | `transition: border-color 0.3s, box-shadow 0.3s` |
| `.filter-btn` (line 338) | `transition: all 0.3s` | `transition: background-color 0.3s, border-color 0.3s, color 0.3s` |
| `.btn-primary` (line 363) | `transition: all 0.3s` | `transition: transform 0.3s, box-shadow 0.3s, background-color 0.3s` |
| `.bill-card` (line 455) | `transition: all 0.3s` | `transition: transform 0.3s, box-shadow 0.3s, border-color 0.3s` |
| `.bill-progress-dot` (line 613) | `transition: all 0.3s` | `transition: background-color 0.3s, box-shadow 0.3s, transform 0.3s` |
| `.user-panel` (line 736) | `transition: all 0.3s` | `transition: transform 0.3s, opacity 0.3s` |
| `.back-btn` (line 899) | `transition: all 0.3s` | `transition: background-color 0.3s, color 0.3s` |

Review each element's `:hover`/`:active`/`.active` state to confirm which properties actually change, then list only those in the transition.

### Fix 1.4: Wrap `:hover` effects in `@media (hover: hover)`
**Issue:** #9 - `:hover` effects without `@media (hover: hover)`
**File:** `index.html`

**Changes:**
- Identify all `:hover` rules that apply `transform`, `box-shadow`, or visual effects:
  - `.stat-card:hover` (line ~254)
  - `.bill-card:hover` (line ~459)
  - `.btn-primary:hover` (line ~370)
  - `.filter-btn:hover` (line ~345)
  - `.nav-tab:hover` (line ~188)
  - `.back-btn:hover` (line ~904)
- Wrap them in `@media (hover: hover) { ... }` so they only apply on devices with a pointing device
- Keep `:active` states (if any) outside the media query for touch feedback

### Fix 1.5: Add `touch-action` to horizontal scroll container
**Issue:** #12 - Missing `touch-action` CSS
**File:** `index.html` (`.bill-type-nav`, line ~147)

**Changes:**
- Add `touch-action: pan-x;` to `.bill-type-nav` to prevent vertical scroll interference when swiping horizontally through bill type tabs

### Fix 1.6: Increase touch target sizes on mobile
**Issue:** #11 - Small touch targets
**File:** `index.html`

**Changes:**
- In the `@media (max-width: 768px)` block, increase padding for:
  - `.filter-tag` / `.filter-btn`: increase to `padding: 0.75rem 1.25rem` (ensures 48px minimum height)
  - `.bill-actions button`: increase to `min-height: 48px; padding: 0.75rem`
  - `.nav-tab`: increase to `padding: 0.75rem 1.25rem`

---

## Phase 2: JavaScript Performance (app.js)

These changes address the core rendering bottleneck and are the highest-impact fixes for mobile.

### Fix 2.1: Add debounce utility and apply to search input
**Issue:** #3 - No debouncing on search input
**File:** `app.js` (lines 1066-1069)

**Changes:**
1. Add a `debounce()` utility function near the top of `app.js`:
```javascript
function debounce(fn, delay) {
    let timer;
    return function(...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}
```
2. Replace the search input event listener:
```javascript
// Before:
document.getElementById('searchInput').addEventListener('input', (e) => {
    APP_STATE.filters.search = e.target.value;
    updateUI();
});

// After:
const debouncedSearch = debounce(() => {
    updateUI();
}, 250);

document.getElementById('searchInput').addEventListener('input', (e) => {
    APP_STATE.filters.search = e.target.value;
    debouncedSearch();
});
```

### Fix 2.2: Cache `filterBills()` result in `updateUI()`
**Issue:** #8 - `filterBills()` called twice per UI update
**File:** `app.js` (lines 371-377)

**Changes:**
1. Modify `updateUI()` to call `filterBills()` once and pass the result:
```javascript
function updateUI() {
    if (APP_STATE.currentView === 'main') {
        const filtered = filterBills();
        renderBills(filtered);
        updateStats(filtered);
    }
    updateUserPanel();
}
```
2. Update `renderBills()` signature to accept a pre-filtered array:
```javascript
function renderBills(filteredBills) {
    const grid = document.getElementById('billsGrid');
    if (!filteredBills) filteredBills = filterBills();
    // ... rest of function
}
```
3. Update `updateStats()` similarly to accept a pre-filtered array parameter.

### Fix 2.3: Pre-compute lowercase search fields
**Issue:** #3 (partial) - Expensive string operations in `filterBills()`
**File:** `app.js` (lines 583-657)

**Changes:**
1. After bills are loaded in `loadBillsData()`, add a pre-processing step:
```javascript
APP_STATE.bills = data.map(bill => ({
    ...bill,
    _searchText: `${bill.number} ${bill.title} ${bill.description} ${bill.sponsor}`.toLowerCase()
}));
```
2. Simplify the search filter in `filterBills()`:
```javascript
if (APP_STATE.filters.search) {
    const search = APP_STATE.filters.search.toLowerCase();
    filtered = filtered.filter(bill => bill._searchText.includes(search));
}
```
This eliminates 14,256 `toLowerCase()` calls per search, replacing them with a single string lookup per bill.

### Fix 2.4: Implement pagination for bill list
**Issue:** #2, #4 - Full DOM rebuild, no virtualization
**File:** `app.js` (lines 379-394) and `index.html`

This is the highest-impact single change. Virtual scrolling is complex to implement; pagination is simpler and nearly as effective.

**Changes:**
1. Add pagination state to `APP_STATE`:
```javascript
pagination: {
    page: 1,
    pageSize: 25
}
```
2. Modify `renderBills()` to render only one page of results:
```javascript
function renderBills(filteredBills) {
    const grid = document.getElementById('billsGrid');
    if (!filteredBills) filteredBills = filterBills();

    const { page, pageSize } = APP_STATE.pagination;
    const start = (page - 1) * pageSize;
    const paginated = filteredBills.slice(start, start + pageSize);
    const totalPages = Math.ceil(filteredBills.length / pageSize);

    grid.innerHTML = paginated.map(bill => createBillCard(bill)).join('');

    renderPaginationControls(filteredBills.length, totalPages, page);
}
```
3. Add a `renderPaginationControls()` function that renders prev/next buttons and a page indicator below the grid.
4. Add `nextPage()` and `prevPage()` global functions called by the pagination buttons.
5. Reset `APP_STATE.pagination.page = 1` whenever filters change (in the search and filter event handlers).
6. Add a pagination container `<div id="paginationControls"></div>` in `index.html` after `billsGrid`.

**Alternative:** "Load More" button instead of full pagination. Append cards rather than replace. Simpler UX but accumulates DOM nodes.

### Fix 2.5: Dirty-flag auto-save
**Issue:** #13 - Auto-save runs unconditionally every 30 seconds
**File:** `app.js` (lines 1095-1099 and StorageManager)

**Changes:**
1. Add a dirty flag to `APP_STATE`:
```javascript
_dirty: false
```
2. Set `APP_STATE._dirty = true` in any function that modifies persistent state: `toggleTrack()`, `saveNote()`, filter changes, user data changes.
3. Update `setupAutoSave()`:
```javascript
function setupAutoSave() {
    setInterval(() => {
        if (APP_STATE._dirty) {
            StorageManager.save();
            APP_STATE._dirty = false;
        }
    }, APP_CONFIG.autoSaveInterval);
}
```

### Fix 2.6: Use event delegation instead of inline `onclick`
**Issue:** #14 (partial) - Inline onclick handlers
**File:** `app.js`

**Changes:**
1. Remove all `onclick="toggleTrack(...)"`, `onclick="openNoteModal(...)"`, and `onclick="shareBill(...)"` from `createBillCard()` HTML output.
2. Add `data-action` and `data-bill-id` attributes to action buttons instead:
```html
<button data-action="track" data-bill-id="${bill.id}">...</button>
<button data-action="note" data-bill-id="${bill.id}">...</button>
<button data-action="share" data-bill-id="${bill.id}">...</button>
```
3. Add a single delegated event listener on `billsGrid`:
```javascript
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
```
This replaces ~10,000+ inline handlers with a single listener.

---

## Phase 3: Mobile Layout Fixes (index.html)

### Fix 3.1: Collapse user panel on mobile by default
**Issue:** #10 - Fixed user panel covers mobile content
**File:** `index.html` (lines 724-737, 1046-1051) and `app.js`

**Changes:**
1. Add a `.user-panel-collapsed` state in CSS that shows only a small floating button (e.g., user avatar icon):
```css
@media (max-width: 768px) {
    .user-panel {
        min-width: auto;
        width: 48px;
        height: 48px;
        border-radius: 50%;
        overflow: hidden;
        padding: 0;
    }
    .user-panel.expanded {
        width: auto;
        min-width: unset;
        left: 1rem;
        right: 1rem;
        height: auto;
        border-radius: 1rem;
        padding: 1.25rem;
    }
}
```
2. Add a toggle button/click handler to expand/collapse the panel on mobile.
3. Hide `.user-panel-content`, `.user-notes-section`, and `.user-settings` when collapsed; show only the avatar.

---

## Phase 4: Network & Loading Optimization

### Fix 4.1: Add loading skeleton / progressive rendering
**Issue:** #1 (partial) - 2.5 MB JSON payload
**File:** `index.html` and `app.js`

**Changes:**
1. Add a skeleton loading state in `index.html` inside `billsGrid`:
```html
<div id="billsGrid" class="bills-grid">
    <div class="skeleton-card"></div>
    <div class="skeleton-card"></div>
    <div class="skeleton-card"></div>
</div>
```
2. Add `.skeleton-card` CSS with a pulsing animation.
3. The skeleton is replaced when `renderBills()` runs after data loads.
4. This provides visual feedback during the data fetch instead of a blank screen.

### Fix 4.2: Add `defer` to script tag
**File:** `index.html` (line ~1254)

**Changes:**
```html
<!-- Before -->
<script src="app.js"></script>

<!-- After -->
<script src="app.js" defer></script>
```
Minor improvement; allows HTML parsing to complete before script execution.

### Fix 4.3: Reduce font weight variants
**Issue:** #3a (partial) - Google Fonts loading
**File:** `index.html` (line 18)

**Changes:**
- Audit actual usage of `Inter` weights. If `700` is unused, remove it.
- Consider dropping `JetBrains Mono` 600 weight if only 400 is used.
- Alternatively, add `&text=0123456789` for JetBrains Mono if it's only used for bill numbers, drastically reducing font file size.

---

## Phase 5: Advanced Optimizations (Future)

These items provide additional gains but are more complex and can be deferred.

### Fix 5.1: Virtual scrolling (alternative to pagination)
Instead of pagination, render only the ~10-15 visible bill cards and recycle DOM nodes as the user scrolls. Libraries like `virtual-scroller` or a custom `IntersectionObserver`-based approach could work. This is significantly more complex than pagination but provides a smoother UX.

### Fix 5.2: Web Worker for JSON parsing
Move the `JSON.parse()` of the 2.5 MB payload to a Web Worker so it doesn't block the main thread. The worker returns the parsed array via `postMessage()`.

### Fix 5.3: Split bills.json by type
Pre-split `bills.json` into per-type files (`sb.json`, `hb.json`, etc.) during the GitHub Actions build step. Load only the active type on initial page load, lazy-load others when the user navigates.

### Fix 5.4: Service Worker for offline caching
Add a service worker to cache `bills.json`, fonts, and `app.js` for offline access and instant repeat loads. Use a stale-while-revalidate strategy.

### Fix 5.5: Replace emoji icons with SVG or icon font
Replace the emoji characters (stars, clipboard, link, person, building, calendar) used in bill cards with inline SVGs or a lightweight icon font. This improves rendering consistency across Android devices and avoids the emoji rendering performance cost.

### Fix 5.6: Use a Map for bill lookups
Replace `APP_STATE.bills.find(b => b.id === billId)` calls with a `Map` keyed by bill ID for O(1) lookups instead of O(n) scans.

---

## Implementation Order Summary

| Order | Fix | Files | Impact | Complexity |
|-------|-----|-------|--------|------------|
| 1 | 2.1 - Debounce search | `app.js` | Critical | Low |
| 2 | 2.2 - Cache filterBills | `app.js` | High | Low |
| 3 | 2.3 - Pre-compute search text | `app.js` | High | Low |
| 4 | 2.4 - Pagination | `app.js`, `index.html` | Critical | Medium |
| 5 | 1.1 - Disable background animation | `index.html` | High | Low |
| 6 | 1.2 - Remove backdrop-filter mobile | `index.html` | High | Low |
| 7 | 1.3 - Scope transitions | `index.html` | Moderate | Low |
| 8 | 1.4 - Hover media query | `index.html` | Moderate | Low |
| 9 | 2.5 - Dirty-flag auto-save | `app.js` | Low | Low |
| 10 | 2.6 - Event delegation | `app.js` | Moderate | Medium |
| 11 | 1.5 - touch-action | `index.html` | Low | Low |
| 12 | 1.6 - Touch target sizes | `index.html` | Moderate | Low |
| 13 | 3.1 - Collapse user panel | `index.html`, `app.js` | Moderate | Medium |
| 14 | 4.1 - Loading skeleton | `index.html`, `app.js` | High | Low |
| 15 | 4.2 - Defer script | `index.html` | Low | Low |
| 16 | 4.3 - Reduce font weights | `index.html` | Low | Low |
| 17+ | Phase 5 items | Various | High | High |

---

## Expected Outcome

After implementing Phases 1-4:

| Metric | Before | After |
|--------|--------|-------|
| DOM nodes (unfiltered view) | ~200,000 | ~1,500 (25 cards x 60 nodes) |
| Search re-renders per query | 1 per keystroke | 1 per 250ms pause |
| filterBills() calls per update | 2 | 1 |
| toLowerCase() calls per search | 14,256 | 0 (pre-computed) |
| Scroll frame budget used | >16ms (jank) | <8ms (smooth) |
| First meaningful paint (3G) | 6-8s blank | ~2s with skeleton |
| Auto-save writes (idle) | Every 30s | Only when changed |
| Inline event handlers | ~10,000+ | 1 delegated listener |
