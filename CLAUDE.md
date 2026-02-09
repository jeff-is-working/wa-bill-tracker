# WA Legislative Tracker 2026

Free, open-source bill tracking app for the Washington State Legislature 2025-26 biennium. Zero-cost serverless architecture running entirely on GitHub Pages with automated data sync.

**Live site**: https://wa-bill-tracker.org
**License**: MIT (Copyright 2026 Jeff Records)
**Session**: 2025-26 Biennium (2026 session: Jan 12 - Mar 12)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vanilla JavaScript, HTML5, CSS3 (no frameworks) |
| Data Collection | Python 3.11 |
| API Source | WA Legislature SOAP API (`wslwebservices.leg.wa.gov`) |
| Hosting | GitHub Pages |
| CI/CD | GitHub Actions |
| Storage | Browser cookies (primary) + localStorage (backup) |

## Project Structure

```
wa-bill-tracker/
├── app.js                          # Complete client-side app (1,881 lines)
├── index.html                      # Single-page HTML + embedded CSS (2,055 lines)
├── CNAME                           # Custom domain: wa-bill-tracker.org
├── sbom.json                       # CycloneDX 1.5 software bill of materials
├── scripts/
│   ├── fetch_all_bills.py          # Full data collection pipeline (1,099 lines)
│   ├── fetch_bills_incremental.py  # Efficient daily sync (405 lines)
│   └── validate_bills_json.py      # Pre-deploy data validation (110 lines)
├── data/
│   ├── bills.json                  # 3,600+ bills (main data file)
│   ├── stats.json                  # Aggregated statistics
│   ├── manifest.json               # Per-bill state for incremental fetching
│   └── sync-log.json               # Last 100 sync attempts
├── tests/
│   ├── test_fetch_all_bills.py     # Unit tests for full fetcher
│   ├── test_incremental_fetch.py   # Incremental fetch tests
│   ├── test_regression.py          # Regression tests
│   └── test_validate_bills.py      # Validation logic tests
├── docs/                           # Project documentation
├── .github/workflows/
│   ├── fetch-data.yml              # Scheduled data sync (2x daily + weekly full)
│   └── deploy.yml                  # Test + deploy to GitHub Pages
└── deploy-custom-domain.md         # Domain setup guide
```

## Commands

```bash
# Python data scripts
pip install requests               # Only runtime dependency
python scripts/fetch_all_bills.py  # Full fetch of all bills from SOAP API
python scripts/fetch_bills_incremental.py  # Incremental sync (daily use)
python scripts/validate_bills_json.py      # Validate data/bills.json

# Testing
pip install pytest                 # Test dependency
pytest tests/                      # Run all tests

# Local development
# Open index.html in a browser (or use any static file server)
python -m http.server 8000         # Simple local server at localhost:8000
```

## Data Flow

```
WA Legislature SOAP API
  → fetch_all_bills.py / fetch_bills_incremental.py
  → XML parsing & normalization
  → data/bills.json + stats.json + manifest.json
  → GitHub Actions auto-commits to main
  → GitHub Pages serves static files
  → Browser loads bills.json from raw.githubusercontent.com
  → app.js renders UI, user data stays in cookies/localStorage
```

### Sync Schedule (GitHub Actions)

- **Incremental**: 6 AM & 6 PM Pacific (twice daily) — re-fetches new + stale active bills
- **Full refresh**: Sundays 2 AM Pacific — re-fetches all 3,600+ bills from scratch
- **Manual**: Via workflow_dispatch with mode selection

### Client-side Refresh

- 1-hour staleness check if page stays open
- Data cached in localStorage as fallback if fetch fails

## Key Architecture Decisions

### Frontend (app.js)

- **Single vanilla JS file** — no build step, no dependencies, no npm
- **APP_CONFIG**: Session dates, 7 legislative cutoff dates, bill types (SB, HB, SJR, HJR, SJM, HJM, SCR, HCR)
- **APP_STATE**: Bills array, tracked bills (Set), user notes, filters, pagination (25/page)
- **CookieManager / StorageManager**: Dual persistence — cookies (90-day, primary) + localStorage (backup)
- **DomainMigration**: Hash-based data transfer from old github.io domain to custom domain
- **IntersectionObserver**: Infinite scroll, loads 25 more bills when near bottom
- **Debounced search** (250ms): Full-text across number, title, description, sponsor
- **Auto-save**: Every 30 seconds if state changed
- **XSS prevention**: `escapeHTML()` on all user-controlled strings before DOM insertion

### Bill Status Progression

```
prefiled → introduced → committee → floor → passed_origin
  → opposite_committee → opposite_floor → passed_legislature
  → governor → enacted
Terminal: vetoed | failed | partial_veto
```

### Cutoff Deadline Logic

7 legislative cutoff dates hardcoded in APP_CONFIG. At display time, if `today > cutoff.date` AND bill status is in `cutoff.failsBefore`, the bill is marked as having missed that cutoff. Bills that missed cutoffs are grouped in a collapsible section.

### Incremental Fetch Strategy

1. **Tier 1**: New bills not in manifest → full fetch
2. **Tier 2**: Stale active (non-terminal) bills → re-fetch up to 400/run, oldest first
3. **Tier 3**: Hearings refresh for all active bills
4. **Change detection**: MD5 hash of (status | history | actionDate | sponsor)

### Topic & Priority Classification

- **Topics**: Technology, Education, Tax & Revenue, Housing, Healthcare, Environment, Transportation, Public Safety, Business, Agriculture, Social Services, General Government (default)
- **Priority**: Governor-requested → high; ceremonial (JM/CR) → low; keyword matching for high/low; default → medium

### Session Management

- Terminal bills from 2025 → session "2025" (inactive)
- Reintroduced or active bills → session "2026"
- "Show inactive bills" toggle controls visibility of 2025 session + cutoff failures

## SOAP API Integration

**Base URL**: `https://wslwebservices.leg.wa.gov`
**Protocol**: SOAP 1.1 over HTTPS
**Rate limiting**: 0.1s delay between requests (self-imposed, respectful)

Key API calls in fetch_all_bills.py:
- `GetLegislationByYear(2026)` — bill roster
- `GetPreFiledLegislationInfo()` — pre-filed bills
- `GetLegislationByYear(2025)` — carryover bills
- `GetLegislation(biennium, billId)` — full bill details
- `GetCommitteeMeetings()` — upcoming hearings (30-day window)
- `GetAgendaItems()` — bills on each meeting agenda

## Data Validation (validate_bills_json.py)

Pre-deploy checks:
- File exists and is valid JSON
- `totalBills` matches actual count
- Required fields present on all bills (id, number, title, status, priority, topic, session)
- No duplicate bill IDs
- Status values in valid set
- Data loss guard: count hasn't dropped >10% from manifest

## Security

- **CSP headers** in index.html (script-src self + unsafe-inline)
- **X-Frame-Options: DENY**
- **No server-side code** — no attack surface beyond static files
- **No authentication** — all legislative data is public record
- **No analytics/tracking** — no telemetry, no 3rd-party cookies
- **User data never leaves browser** — tracked bills, notes, preferences all local

## Testing

- **Framework**: pytest
- **Coverage**: SOAP envelope building, XML parsing, bill number extraction, topic/priority classification, status normalization, data format compatibility
- **CI**: Runs on every push to main (non-blocking — deploys even if tests fail)

## Code Conventions

- **JavaScript**: Vanilla ES6+, no modules, single file, camelCase functions/variables
- **Python**: Standard library + requests only, snake_case, docstrings on public functions
- **HTML/CSS**: Embedded styles in index.html, CSS custom properties for theming, dark mode default
- **Commits**: Automated syncs use "Update bill data - {timestamp}" format

## Dependencies

### Runtime
- **Python**: requests (2.32.5)
- **Frontend**: None (vanilla JS, Google Fonts via CDN)

### Development
- **pytest** (9.0.2)

### Infrastructure
- GitHub Pages, GitHub Actions, Cloudflare (DNS)
