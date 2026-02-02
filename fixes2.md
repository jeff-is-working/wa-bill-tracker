# WA Bill Tracker — Comprehensive Fix Plan (Phase 2)

> Updated: 2026-01-31
> Covers: All open GitHub issues (#26–#44)
> Predecessor: `fixes.md` (Phases 1–5 mobile performance plan)

---

## Status Summary

| Phase | Issues | Status |
|-------|--------|--------|
| Phase 6 — Mobile Layout | #24, #25, #41 | **COMPLETED** (merged to main) |
| Phase 9 — Committee Filter | #35, #36 | **COMPLETED** (merged to main) |
| Pipeline Refactor | #42 | **COMPLETED** (merged to main) |
| Phase 8 — Session & Cutoffs | #27, #28–#34 | **COMPLETED** (merged to main) |
| Phase 8 Hotfix — Cutoff Date Logic | #43 | Open |
| Phase 7 — Infinite Scroll | #26 | Open |
| Phase 10 — Priority Logic | #37 | Open |
| Phase 11 — Bill Card Actions | #38, #39, #40 | Open |
| Phase 12 — User Stats Panel | #44 | Open |

---

## Remaining Open Issues

| # | Title | Label | Phase | Priority |
|---|-------|-------|-------|----------|
| 43 | Cutoff date logic is bad (end-of-day, not start) | bug | 8 hotfix | **High** |
| 44 | User stats panel — collapsible for all browsers | enhancement | 12 | Medium |
| 26 | Auto scroll pagination | enhancement | 7 | Medium |
| 37 | Priority logic report for developers | documentation | 10 | Medium |
| 38 | Contact your legislator button | enhancement | 11 | Medium |
| 39 | Follow bill by email button | enhancement | 11 | Medium |
| 40 | Export/email bill notes | enhancement | 11 | Medium |

---

## Recommended Implementation Order

| Order | Phase | Issues | Rationale |
|-------|-------|--------|-----------|
| ~~1~~ | ~~8A~~ | ~~#27~~ | ~~COMPLETED~~ |
| ~~2~~ | ~~8B~~ | ~~#28–#34~~ | ~~COMPLETED~~ |
| 3 | 8 hotfix | #43 | **High** — bug: cutoffs trigger a day early; Feb 4 cutoff already affected |
| 4 | 11 | #38, #39, #40 | Medium — quick wins, independent, high user value |
| 5 | 7 | #26 | Medium — UX improvement, independent |
| 6 | 12 | #44 | Medium — UX polish, collapsible user stats panel for all browsers |
| 7 | 10 | #37 | Medium — documentation task, can be done anytime |

---

## Phase 8 Hotfix — Cutoff Date Logic (#43)

**Issue:** #43
**Branch:** `dev/phase8-hotfix-cutoff-logic`
**Files:** `app.js` (lines 23–31, 761–778, 781–791)
**Complexity:** Low

### Problem
Cutoff dates in the [official calendar](https://leg.wa.gov/media/b2akn2nz/2026-cutoff-calendar-short.pdf) represent the **last day** for action — i.e., the cutoff occurs at the **end** of that day (11:59 PM), not the beginning. The current code uses `new Date('2026-02-04')` which resolves to midnight UTC on Feb 4, effectively triggering the cutoff ~16 hours early (midnight UTC = 4 PM Pacific on Feb 3).

This causes two bugs:
1. **Banner shows wrong countdown** — on Feb 3 the banner might say "0 days" or skip to the next cutoff when the Policy Committee cutoff hasn't actually passed yet.
2. **Bills incorrectly marked as failed** — `getBillCutoffStatus()` marks bills as cutoff failures before the day is actually over.

The user has manually changed the Feb 4 date to Feb 5 as a temporary workaround.

### Root Cause
`new Date('2026-02-04')` → midnight UTC → 4:00 PM PST on Feb 3. Comparisons like `now < new Date(cutoff.date)` treat the cutoff as starting at midnight UTC, not ending at midnight Pacific.

### Fix

#### Step 1 — Shift cutoff comparison to end-of-day Pacific time
In `getBillCutoffStatus()` and `getNextCutoff()`, add end-of-day handling:

```javascript
// Helper: returns a Date representing 11:59 PM Pacific on the given date string
function endOfDayPacific(dateStr) {
    // Parse as local date (YYYY-MM-DD), set to end of day
    const [y, m, d] = dateStr.split('-').map(Number);
    const dt = new Date(y, m - 1, d, 23, 59, 59);
    return dt;
}
```

Then replace `new Date(cutoff.date)` with `endOfDayPacific(cutoff.date)` in:
- `getBillCutoffStatus()` line 771: `if (now < endOfDayPacific(cutoff.date)) break;`
- `getNextCutoff()` line 784: `const cutoffDate = endOfDayPacific(cutoff.date);`
- `getNextCutoff()` daysUntil calculation: use the date portion only for day counting

#### Step 2 — Fix daysUntil calculation
The days-until countdown should show "1 day" on the day before the cutoff, and "Today" or "0 days" on the cutoff day itself:

```javascript
function getNextCutoff() {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    for (const cutoff of APP_CONFIG.cutoffDates) {
        const cutoffEnd = endOfDayPacific(cutoff.date);
        if (cutoffEnd > now) {
            const cutoffDay = new Date(cutoffEnd.getFullYear(), cutoffEnd.getMonth(), cutoffEnd.getDate());
            const daysUntil = Math.round((cutoffDay - today) / (1000 * 60 * 60 * 24));
            return { ...cutoff, daysUntil, dateObj: cutoffEnd };
        }
    }
    return null;
}
```

#### Step 3 — Update banner to handle "Today" case
```javascript
// In updateCutoffBanner():
if (next.daysUntil === 0) {
    daysText = 'Today';
} else {
    daysText = next.daysUntil + ' day' + (next.daysUntil !== 1 ? 's' : '') + ' away';
}
```

#### Step 4 — Revert manual workaround
Change the date back from `'2026-02-05'` to `'2026-02-04'` in `APP_CONFIG.cutoffDates` (if the user's manual edit is still present).

### Acceptance Criteria
- [ ] On Feb 4, the Policy Committee cutoff banner shows "Today" (not already past)
- [ ] On Feb 3, the banner shows "1 day away" for Policy Committee
- [ ] Bills are not marked as cutoff failures until after end-of-day on the cutoff date
- [ ] `getNextCutoff()` correctly identifies the current/next cutoff at any point during the day
- [ ] Cutoff dates in `APP_CONFIG` match the official calendar (not shifted by +1 day)
- [ ] All 7 cutoff dates work correctly across the session

---

## Phase 7 — Infinite Scroll Pagination

**Issue:** #26
**Branch:** `dev/phase7-infinite-scroll`
**Files:** `app.js` (lines 500–535, pagination system), `index.html` (pagination controls CSS)
**Complexity:** Medium

### Problem
Phase 2 introduced paginated bill display (25 bills/page) to solve DOM overload. Community feedback requests continuous scrolling with performance safeguards.

### Current State
- `APP_STATE.pagination` tracks `page` and `pageSize` (25)
- `renderPaginationControls()` (line 510) renders First/Prev/Next/Last buttons
- `goToPage()` (line 530) navigates and smooth-scrolls to grid top
- Pagination resets to page 1 on any filter/search change

### Approach: Intersection Observer infinite scroll

#### Step 7.1 — Add scroll sentinel element
In `index.html`, after the `#billsGrid` div and before `#paginationControls`:
```html
<div id="scrollSentinel" style="height: 1px;"></div>
```

#### Step 7.2 — Implement Intersection Observer in `app.js`
```javascript
let scrollObserver = null;

function setupInfiniteScroll() {
    const sentinel = document.getElementById('scrollSentinel');
    if (!sentinel) return;

    if (scrollObserver) scrollObserver.disconnect();

    scrollObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            loadNextPage();
        }
    }, { rootMargin: '200px' });

    scrollObserver.observe(sentinel);
}

function loadNextPage() {
    const { page, pageSize } = APP_STATE.pagination;
    const filtered = filterBills();
    const totalPages = Math.ceil(filtered.length / pageSize);

    if (page >= totalPages) return;

    APP_STATE.pagination.page++;
    const start = (APP_STATE.pagination.page - 1) * pageSize;
    const nextBills = filtered.slice(start, start + pageSize);

    const grid = document.getElementById('billsGrid');
    grid.insertAdjacentHTML('beforeend', nextBills.map(createBillCard).join(''));
    updatePageInfo(filtered.length);
}
```

#### Step 7.3 — Modify `renderBills()` to support append mode
Initial render loads page 1 into the grid. Subsequent pages append via `loadNextPage()`. On filter/search change, clear grid and reset to page 1.

#### Step 7.4 — Replace page info with running count
Change "Page X of Y" to: `Showing ${displayed} of ${total} bills`

#### Step 7.5 — Keep pagination as fallback
Hide pagination buttons when IntersectionObserver is supported. Users on very old browsers still get button navigation.

### Acceptance Criteria
- [ ] Scrolling down automatically loads the next batch of 25 bills
- [ ] No button click required to see more bills
- [ ] Changing filters/search/bill type resets to the beginning
- [ ] Running count updates as more bills load (e.g., "Showing 75 of 3,564 bills")
- [ ] Performance remains smooth
- [ ] Back-to-top button works correctly
- [ ] Fallback pagination for browsers without IntersectionObserver

---

## Phase 8 — Session & Cutoff Date Management — COMPLETED

**Issues:** #27, #28, #29, #30, #31, #32, #33, #34 (all closed)
**Branch:** `dev/phase8-session-cutoffs` (merged to main)
**Commits:** `63e4656`, `b784c3e` (banner color fix)
**Files:** `scripts/fetch_all_bills.py`, `app.js`, `index.html`
**Complexity:** High

### Problem
1. **#27:** Bills from the 2025 long session appear alongside 2026 bills. Bills marked "enacted" were passed in 2025, confusing users.
2. **#28–#34:** Legislative cutoff dates define when bills die if they haven't progressed. Users want failed bills hidden or marked as dead.

### Context
Washington uses a biennial session (2025-26). The scraper fetches the full `2025-26` biennium, which includes both the 2025 long session and 2026 short session. The `GetLegislationByYear` API is called for both years (2025 and 2026). Bills enacted in 2025 are part of the same biennium but are no longer active.

### 2026 Legislative Cutoff Calendar
| Date | Cutoff | Description |
|------|--------|-------------|
| Feb 4 | Policy Committee (Origin) | Last day for policy committee reports in house of origin |
| Feb 9 | Fiscal Committee (Origin) | Last day for fiscal committee reports in house of origin |
| Feb 17 | House of Origin | Last day to consider bills in house of origin (5 PM) |
| Feb 25 | Policy Committee (Opposite) | Last day for policy committee reports from opposite house |
| Mar 4 | Fiscal Committee (Opposite) | Last day for fiscal committee reports from opposite house |
| Mar 6 | Opposite House | Last day to consider opposite house bills (exceptions apply) |
| Mar 12 | Sine Die | Last day of regular session |

### Step 8.1 — Filter out 2025-enacted bills (#27)

**File:** `scripts/fetch_all_bills.py`

Add logic to detect bills whose action completed in the 2025 session. Indicators:
- `history_line` containing `C xxx L 2025` (chapter law reference for 2025)
- `action_date` in 2025 combined with terminal status (`enacted`, `vetoed`, `failed`)
- `history_line` containing "reintroduced and retained" means it IS a 2026 bill

Add a `session` field to each bill:
```python
# In build_bill_dict():
action_date = details.get("action_date", "")
history = details.get("history_line", "")

if "L 2025" in history or (action_date and action_date[:4] == "2025"
    and status in ("enacted", "vetoed", "failed")
    and "reintroduced" not in history.lower()):
    session = "2025"
else:
    session = "2026"

bill["session"] = session
```

**Client-side guard in `app.js`** — In `filterBills()`, default to showing only 2026 session bills:
```javascript
// Unless user explicitly enables "show all sessions"
if (!APP_STATE.filters.showAllSessions) {
    filtered = filtered.filter(bill => bill.session !== '2025');
}
```

### Step 8.2 — Add cutoff date configuration (#28–#34)

**File:** `app.js` (APP_CONFIG)

```javascript
cutoffDates: [
    { date: '2026-02-04', label: 'Policy Committee Cutoff (Origin)', scope: 'origin_policy' },
    { date: '2026-02-09', label: 'Fiscal Committee Cutoff (Origin)', scope: 'origin_fiscal' },
    { date: '2026-02-17', label: 'House of Origin Cutoff', scope: 'origin' },
    { date: '2026-02-25', label: 'Policy Committee Cutoff (Opposite)', scope: 'opposite_policy' },
    { date: '2026-03-04', label: 'Fiscal Committee Cutoff (Opposite)', scope: 'opposite_fiscal' },
    { date: '2026-03-06', label: 'Opposite House Cutoff', scope: 'opposite' },
    { date: '2026-03-12', label: 'Sine Die', scope: 'session' },
],
```

### Step 8.3 — Implement cutoff-aware bill filtering

**File:** `app.js`

Add a function that determines if a bill has effectively failed based on cutoff dates:

```javascript
function isBillCutoff(bill) {
    const now = new Date();
    const cutoffs = APP_CONFIG.cutoffDates;

    for (const cutoff of cutoffs) {
        if (now < new Date(cutoff.date)) continue; // cutoff hasn't passed

        // Check if bill should have progressed past this cutoff
        switch (cutoff.scope) {
            case 'origin_policy':
                // Bills still prefiled/introduced in origin policy committee
                if (['prefiled', 'introduced'].includes(bill.status)) return true;
                break;
            case 'origin_fiscal':
                if (['prefiled', 'introduced', 'committee'].includes(bill.status)) return true;
                break;
            case 'origin':
                if (!['passed_origin', 'opposite_chamber', 'passed_both',
                      'passed_legislature', 'governor', 'enacted',
                      'partial_veto', 'vetoed', 'failed'].includes(bill.status)) return true;
                break;
            // ... opposite house cutoffs check opposite_chamber status
            case 'session':
                if (!['enacted', 'partial_veto', 'vetoed', 'failed', 'governor'].includes(bill.status))
                    return true;
                break;
        }
    }
    return false;
}
```

**Note:** Some bills are exempt from cutoffs (budgets, revenue bills, initiatives). The logic should be conservative — only mark clearly-failed bills, not edge cases.

### Step 8.4 — Add "Show inactive bills" toggle

**File:** `index.html`, `app.js`

Add a toggle near the filter section:
```html
<label class="toggle-label">
    <input type="checkbox" id="showInactiveBills"> Show inactive/failed bills
</label>
```

Default: unchecked (hide cutoff-failed and 2025 bills). When checked, show all bills with a visual indicator for their inactive status.

### Step 8.5 — Add cutoff date banner

**File:** `app.js` (`renderSessionStats()`)

In the session stats section, display the next upcoming cutoff:
```javascript
function getNextCutoff() {
    const now = new Date();
    for (const cutoff of APP_CONFIG.cutoffDates) {
        const cutoffDate = new Date(cutoff.date);
        if (cutoffDate > now) {
            const daysUntil = Math.ceil((cutoffDate - now) / (1000 * 60 * 60 * 24));
            return { ...cutoff, daysUntil };
        }
    }
    return null;
}
```

Display as a stats item or banner: "Next cutoff: Policy Committee (Feb 4) — 5 days away"

### Step 8.6 — Update session stats display

Update `renderSessionStats()` to include cutoff milestones on the session timeline and show active vs. inactive bill counts.

### Acceptance Criteria
- [x] No 2025-enacted bills appear in the default view (#27)
- [x] `session` field added to each bill in `bills.json`
- [x] "Show inactive bills" toggle reveals 2025 and cutoff-failed bills
- [x] After each cutoff date, bills that didn't progress are visually marked
- [x] Cutoff banner shows next upcoming cutoff date with countdown
- [x] Total bill count in stats reflects active bills only
- [x] Bills exempt from cutoffs are not incorrectly marked failed
- [x] Filter counts update correctly when inactive bills are hidden
- [x] Cutoff dates listed in `APP_CONFIG` for easy future updates

---

## Phase 10 — Priority Logic Documentation & Improvement

**Issue:** #37
**Branch:** `dev/phase10-priority-logic`
**Files:** `scripts/fetch_all_bills.py` (`determine_priority()` line 397)
**Complexity:** Low–Medium

### Current State
```python
def determine_priority(title, requested_by_governor=False):
    # High: "emergency", "budget", "funding", "safety", "crisis", "urgent"
    # Low:  "technical", "clarifying", "housekeeping", "minor", "study", "report"
    # Default: "medium"
```

Distribution: 95.4% medium, 3.5% high, 1.1% low — effectively useless.

### Step 10.1 — Expand keyword lists
Add more differentiating keywords:

**High priority additions:**
- `"appropriation"`, `"revenue"`, `"public safety"`, `"health care"`,
  `"education funding"`, `"housing"`, `"transportation"`

**Low priority additions:**
- `"commemorat"`, `"proclaim"`, `"memorializ"`, `"designat"`, `"renam"`,
  `"recogni"` (recognizing/recognition)

### Step 10.2 — Add bill-type-based priority
```python
# Joint memorials and concurrent resolutions → low by default
bill_type = prefix[-3:] if len(prefix) >= 3 else prefix
if bill_type in ("HJM", "SJM", "HCR", "SCR"):
    return "low"
```

### Step 10.3 — Add multi-signal priority (optional enhancement)
Consider incorporating:
- Bills with upcoming hearings → boost priority
- Bills that have progressed beyond committee → boost priority
- Number of sponsors (companion bills) → boost priority

### Step 10.4 — Document the logic
Add inline comments to `determine_priority()` and a brief section in the project README.

### Acceptance Criteria
- [ ] Priority distribution improved (target: ~70% medium, ~20% high, ~10% low)
- [ ] `determine_priority()` has clear inline documentation
- [ ] Bill types like memorials/resolutions default to low
- [ ] No regressions in existing bill processing
- [ ] Priority keyword lists are maintained in a clear, editable format

---

## Phase 11 — Bill Card Action Buttons & Notes Export

**Issues:** #38, #39, #40
**Branch:** `dev/phase11-action-buttons`
**Files:** `app.js` (`createBillCard()` line 666, `updateUserNotesList()` line 1156), `index.html` (CSS)
**Complexity:** Low–Medium

### Current Bill Card Actions
```
[⭐ Track] [📝 Notes] [🔗 Share]
```

### Step 11.1 — Contact Your Legislator Button (#38)

**File:** `app.js` (`createBillCard()` line 715)

Add after the Share button:
```javascript
<a href="https://app.leg.wa.gov/billsummary?BillNumber=${bill.number.split(' ').pop()}&Year=${APP_CONFIG.sessionYear || 2026}#commentForm"
   target="_blank" rel="noopener"
   class="action-btn" title="Contact your legislator about this bill">
    ✉ Contact
</a>
```

This is an `<a>` tag — it navigates directly, no event delegation needed.

### Step 11.2 — Follow Bill by Email Button (#39)

**File:** `app.js` (`createBillCard()`)

Add after the Contact button:
```javascript
<a href="https://app.leg.wa.gov/billsummary?BillNumber=${bill.number.split(' ').pop()}&Year=${APP_CONFIG.sessionYear || 2026}"
   target="_blank" rel="noopener"
   class="action-btn" title="Follow this bill by email on leg.wa.gov">
    📧 Follow
</a>
```

**Design consideration:** Both Contact and Follow link to `app.leg.wa.gov/billsummary`. Consider combining them into a single "View on leg.wa.gov" link that opens the bill page where both the comment form and email signup live. This avoids two buttons going to the same domain. Decision should be validated by trying the actual URLs.

### Step 11.3 — Export/Email Bill Notes (#40)

#### 11.3.1 — Add export buttons to user notes section

**File:** `index.html` (user notes section, around line 1427)

Add "Copy" and "Email" buttons in the notes section header.

#### 11.3.2 — Implement `formatNotesForExport()`

**File:** `app.js`

```javascript
function formatNotesForExport() {
    const lines = [];
    Object.entries(APP_STATE.userNotes).forEach(([billId, notes]) => {
        const bill = APP_STATE.bills.find(b => b.id === billId);
        const billLabel = bill ? `${bill.number} — ${bill.title}` : billId;
        notes.forEach(note => {
            lines.push(`Bill: ${billLabel}`);
            lines.push(`Note: ${note.text}`);
            lines.push(`Date: ${new Date(note.date).toLocaleDateString()}`);
            lines.push('');
        });
    });
    lines.push('---');
    lines.push('Exported from WA Bill Tracker');
    return lines.join('\n');
}
```

#### 11.3.3 — Copy to clipboard (Clipboard API with fallback)

```javascript
async function copyAllNotes() {
    const text = formatNotesForExport();
    if (!text.includes('Bill:')) { showToast('No notes to copy'); return; }
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta);
        ta.select(); document.execCommand('copy');
        document.body.removeChild(ta);
    }
    showToast('Notes copied to clipboard');
}
```

#### 11.3.4 — Email notes via `mailto:`

```javascript
function emailAllNotes() {
    const text = formatNotesForExport();
    if (!text.includes('Bill:')) { showToast('No notes to email'); return; }
    const subject = encodeURIComponent('My WA Bill Tracker Notes');
    const body = encodeURIComponent(text);
    window.open(`mailto:?subject=${subject}&body=${body}`);
}
```

#### 11.3.5 — Individual note copy button
Add a small copy icon to each note card in `updateUserNotesList()`.

### CSS Updates

With 5 action buttons on mobile, ensure proper wrapping:
```css
.bill-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}

@media (max-width: 480px) {
    .bill-actions .action-btn {
        font-size: 0.75rem;
        padding: 0.4rem 0.6rem;
    }
}
```

### Updated Bill Card Actions
```
[⭐ Track] [📝 Notes] [🔗 Share] [✉ Contact] [📧 Follow]
```

### Acceptance Criteria
- [ ] Contact button links to correct comment form URL for each bill (#38)
- [ ] Follow button links to bill summary page on leg.wa.gov (#39)
- [ ] Both external links open in new tabs with `rel="noopener"`
- [ ] "Copy All Notes" copies formatted text to clipboard (#40)
- [ ] "Email Notes" opens email client with pre-filled content (#40)
- [ ] Individual note copy works (#40)
- [ ] Toast notifications confirm actions
- [ ] All buttons accessible on mobile (min 48px touch targets)
- [ ] Button layout wraps cleanly on narrow screens
- [ ] Empty notes state handled (buttons disabled or hidden when no notes)

---

## Phase 12 — Collapsible User Stats Panel (#44)

**Issue:** #44
**Branch:** `dev/phase12-user-panel`
**Files:** `app.js` (lines 1242–1287, 1378–1432), `index.html` (user panel HTML/CSS)
**Complexity:** Medium

### Problem
The user stats/info panel currently only collapses to an avatar on mobile (`window.innerWidth <= 768`). On desktop browsers, the panel is always fully expanded, taking up vertical space. The user requests the same collapsible behavior across all screen sizes.

### Current State
- `updateUserPanel()` (line 1242) populates name, avatar, tracked count, notes count
- Mobile toggle (line 1378): clicking the avatar toggles `mobile-expanded` class, but only when `window.innerWidth <= 768`
- `toggleUserPanel()` (line 1424): toggles `expanded` class on the panel and `active` on the notes section
- The panel shows: avatar, user name, tracked bill count, notes count, and up to 5 recent notes

### Approach

#### Step 12.1 — Remove the mobile-only guard from avatar click
In the avatar click listener (line 1382), remove the `if (window.innerWidth > 768) return;` check so the toggle works at all viewport widths.

#### Step 12.2 — Add collapsed state CSS for desktop
Add CSS that keeps the panel minimized by default (or remembers the user's preference via cookie/localStorage), showing only the avatar. On click, expand to show full stats.

```css
/* Default: collapsed on all screens */
#userPanel {
    /* Collapsed state: show avatar only */
}

#userPanel.expanded {
    /* Full panel with stats and notes */
}
```

#### Step 12.3 — Persist panel state
Save the expanded/collapsed preference in a cookie so it persists across page loads:
```javascript
CookieManager.set('wa_tracker_panel_expanded', isExpanded ? '1' : '0', 365);
```

#### Step 12.4 — Smooth transition
Add CSS transition for the expand/collapse animation (height or max-height transition).

### Acceptance Criteria
- [ ] Clicking the avatar collapses/expands the user stats panel on all screen sizes
- [ ] Collapsed state shows only the avatar (or avatar + minimal info)
- [ ] Expanded state shows full user stats and recent notes
- [ ] Panel state persists across page reloads (cookie/localStorage)
- [ ] Smooth expand/collapse animation
- [ ] No regression on mobile behavior
- [ ] Click-outside-to-close still works on mobile

---

## Branch Strategy

| Phase | Branch | Issues Closed |
|-------|--------|---------------|
| ~~8A+8B~~ | ~~`dev/phase8-session-cutoffs`~~ | ~~#27, #28, #29, #30, #31, #32, #33, #34~~ |
| 8 hotfix | `dev/phase8-hotfix-cutoff-logic` | #43 |
| 11 | `dev/phase11-action-buttons` | #38, #39, #40 |
| 7 | `dev/phase7-infinite-scroll` | #26 |
| 12 | `dev/phase12-user-panel` | #44 |
| 10 | `dev/phase10-priority-logic` | #37 |

---

## Completed Phases (for reference)

| Phase | Issues | Commit |
|-------|--------|--------|
| Phase 6 — Mobile Layout | #24, #25, #41 | `18de78e` |
| Phase 9 — Committee Filter | #35, #36 | `7763219` |
| Pipeline Refactor | #42 | `2827ca3` |
| Phase 8 — Session & Cutoffs | #27, #28–#34 | `63e4656`, `b784c3e` |
