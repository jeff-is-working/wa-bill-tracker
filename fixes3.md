# WA Bill Tracker — Fix Plan (Phase 3)

> Updated: 2026-01-31
> Covers: Open GitHub issues #38 (reopened), #45
> Predecessor: `fixes2.md` (Phases 6–12)

---

## Status Summary

| Phase | Issues | Status |
|-------|--------|--------|
| Phases 6–10, 12, Pipeline | #24–#44 | **COMPLETED** (see fixes2.md) |
| Phase 13 — Fix Bill Card Links | #38, #45 | Open |

---

## Open Issues

| # | Title | Label | Problem |
|---|-------|-------|---------|
| 38 | Contact your legislator button | enhancement (reopened) | Links to wrong URL — should use `app.leg.wa.gov/pbc/bill/####` not `billsummary#commentForm` |
| 45 | Follow bill by email button | (new) | Should use the direct email notification signup URL, not the generic bill summary page |

---

## Phase 13 — Fix Bill Card Action Links (#38, #45)

**Issues:** #38 (reopened), #45
**Branch:** `dev/fix-bill-card-links`
**File:** `app.js` (lines 787–794, inside `createBillCard()`)
**Complexity:** Low

### Problem

Both the Contact and Follow buttons currently link to the wrong URLs:

**Contact button (#38):**
- Current: `https://app.leg.wa.gov/billsummary?BillNumber=${num}&Year=2026#commentForm`
- Required: `https://app.leg.wa.gov/pbc/bill/${num}`
- The `/pbc/bill/` path is the Public Bill Comment form — a direct one-click route to start commenting on a specific bill. The user confirmed this in the reopened issue comment.

**Follow button (#45):**
- Current: `https://app.leg.wa.gov/billsummary?BillNumber=${num}&Year=2026`
- Required: `https://app.leg.wa.gov/billsummary/Home/GetEmailNotifications?billTitle=${encodedTitle}&billNumber=${num}&year=${year}&agency=${agency}&initiative=False`
- This is the direct email notification signup link. Parameters needed:
  - `billTitle`: e.g. `HB 1015-2025-26` (bill number with biennium, URL-encoded)
  - `billNumber`: numeric part only, e.g. `1015`
  - `year`: first year of biennium, e.g. `2025`
  - `agency`: `House` or `Senate` (from `bill.originalAgency`)
  - `initiative`: `False`

### Available Bill Data

Each bill object in `APP_STATE.bills` has:
```
number: "HB 1000"          → split(' ').pop() gives "1000"
originalAgency: "House"     → needed for Follow URL agency param
biennium: "2025-26"         → needed for Follow URL year and billTitle params
```

### Fix

#### Contact button — change URL to `/pbc/bill/`

```javascript
// Before:
<a href="https://app.leg.wa.gov/billsummary?BillNumber=${bill.number.split(' ').pop()}&Year=2026#commentForm"

// After:
<a href="https://app.leg.wa.gov/pbc/bill/${bill.number.split(' ').pop()}"
```

#### Follow button — construct email notification URL

```javascript
// Before:
<a href="https://app.leg.wa.gov/billsummary?BillNumber=${bill.number.split(' ').pop()}&Year=2026"

// After:
<a href="https://app.leg.wa.gov/billsummary/Home/GetEmailNotifications?billTitle=${encodeURIComponent(bill.number.replace(' ', ' ') + '-' + bill.biennium)}&billNumber=${bill.number.split(' ').pop()}&year=${bill.biennium.split('-')[0]}&agency=${bill.originalAgency}&initiative=False"
```

Both changes are to the `<a href="...">` attributes inside `createBillCard()` at lines 787–794 of `app.js`. No other files need changes.

### Acceptance Criteria

- [ ] Contact button links to `https://app.leg.wa.gov/pbc/bill/{number}` (e.g. `/pbc/bill/1015`)
- [ ] Follow button links to the email notification signup URL with correct parameters
- [ ] Both buttons work for House bills (HB) and Senate bills (SB)
- [ ] Both buttons open in new tabs with `rel="noopener"`
- [ ] URL parameters are correctly encoded (spaces in bill title)
- [ ] No changes to button appearance or other bill card functionality
