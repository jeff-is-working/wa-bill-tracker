# WA Bill Tracker -- Lessons Learned

**Project:** wa-bill-tracker (wa-bill-tracker.org)
**Period:** January 2026 -- March 2026 (2026 WA Legislative Short Session)
**Audience:** Human and AI development staff working with the WA Legislature API
**Last Updated:** 2026-03-22

---

## Table of Contents

1. [The WA Legislature SOAP API](#1-the-wa-legislature-soap-api)
2. [Bill Status Detection Is the Hardest Problem](#2-bill-status-detection-is-the-hardest-problem)
3. [Session Lifecycle and Cutoff Dates](#3-session-lifecycle-and-cutoff-dates)
4. [Data Pipeline Architecture](#4-data-pipeline-architecture)
5. [Frontend Performance at Scale](#5-frontend-performance-at-scale)
6. [Operational Pitfalls](#6-operational-pitfalls)
7. [What Worked Well](#7-what-worked-well)
8. [Recommendations for Future Sessions](#8-recommendations-for-future-sessions)

---

## 1. The WA Legislature SOAP API

### Overview

The Washington State Legislature exposes legislative data through a SOAP 1.1 API at `wslwebservices.leg.wa.gov`. There is no REST API, no GraphQL, no JSON -- only XML over SOAP. There is no official API documentation beyond the WSDL definitions.

**Base URL:** `https://wslwebservices.leg.wa.gov`

**Key services:**

| Service | Endpoint | Purpose |
|---------|----------|---------|
| LegislationService | `/LegislationService.asmx` | Bill details, status, history |
| SponsorService | `/SponsorService.asmx` | Legislator / sponsor info |
| CommitteeService | `/CommitteeService.asmx` | Committee definitions |
| CommitteeMeetingService | `/CommitteeMeetingService.asmx` | Hearings, agendas |

### Key API Methods

- `GetLegislationByYear` -- Returns a roster of all bills for a session year. This is the cheapest call and returns enough metadata to detect changes (last action date, status, bill ID).
- `GetPreFiledLegislationInfo` -- Returns bills filed before the session formally opens.
- `GetLegislation` -- Returns full details for a single bill: sponsors, history, status, committee assignments. This is the expensive call -- one request per bill.

### Gotchas and Undocumented Behaviors

**1. No batch endpoint for bill details.**
There is no way to fetch multiple bills in a single request. To get full details for 3,756 bills, you must make 3,756 individual `GetLegislation` calls. With a polite rate-limit delay of 0.1s per request, this takes 6-8 minutes minimum, and 15-30 minutes with real-world API latency.

**2. The `status` field uses undocumented chamber prefixes.**
The API `status` field for a bill includes a chamber prefix that is not documented anywhere but is critical for cross-chamber detection:
- `"H Approps"` -- House Appropriations committee
- `"S Ways & Means"` -- Senate Ways & Means committee
- `"S Rules 2"` -- Senate Rules (floor stage)
- `"H 2nd Reading"` -- House second reading (floor)

The prefix convention is: `"H "` for House, `"S "` for Senate. This is the most reliable way to determine which chamber a bill is currently in. See Section 2 for why this matters.

**3. History lines omit the chamber name for cross-chamber referrals.**
When a House bill is referred to a Senate committee, the `history_line` field says:
```
First reading, referred to Ways & Means.
```
Not:
```
First reading, referred to Senate Ways & Means.
```
This makes history-line-based chamber detection unreliable. The `status` field prefix (above) is the correct signal.

**4. The biennium parameter uses the first year.**
WA operates on a two-year biennium. The 2025-2026 biennium parameter is `"2025-26"`. Both the 2025 long session and 2026 short session share this biennium. Filtering by session year requires checking the `introducedDate` or explicitly tracking which session each bill belongs to.

**5. `GetLegislationByYear` returns both session years.**
Despite the method name suggesting a single year, calling `GetLegislationByYear(2026)` can return bills from the prior session year that are technically still part of the biennium. Our tracker initially displayed 2025-session enacted laws alongside 2026 bills, confusing users (Issue #27).

**6. No webhook or push notification mechanism.**
There is no way to subscribe to bill status changes. You must poll. We settled on twice-daily polling during session, reduced to once per weekday post-session.

**7. XML namespaces vary across services.**
The namespace `http://WSLWebServices.leg.wa.gov/` is used in SOAPAction headers and response parsing. Element names in responses are prefixed with this namespace. Forgetting to handle the namespace when parsing XML is a common source of empty results.

**8. Rate limiting is implicit, not documented.**
There is no published rate limit. However, sending requests too quickly (under ~50ms apart) occasionally produces HTTP 500 errors or empty responses. A 100ms delay between requests has been reliable. During high-traffic periods (session start, cutoff dates), the API can slow to 1-2 second response times.

**9. Substitute bill IDs are non-obvious.**
Bills can be substituted (amended in committee) and get new prefixes:
- `HB 1234` becomes `SHB 1234` (Substitute House Bill)
- Can escalate to `2SHB 1234` (Second Substitute) or `ESHB 1234` (Engrossed Substitute)
- The bill number (1234) stays the same, but the ID prefix changes

This means a single bill can appear under multiple IDs across its lifecycle. The data pipeline must handle ID collisions when merging.

**10. Committee assignment is not a first-class field.**
The API does not return a clean "current committee" field. Committee information must be derived from either:
- The `status` field (e.g., `"S Ways & Means"`)
- The `history_line` entries mentioning referrals
- The `CommitteeMeetingService` hearing data

Our initial release shipped with an empty `committee` field for all 3,577 bills because the data pipeline did not populate it (Issue #35). The committee filter showed zero results for weeks.

---

## 2. Bill Status Detection Is the Hardest Problem

### The Lifecycle

A WA state bill follows this progression:

```
prefiled -> introduced -> committee -> floor -> passed_origin
  -> opposite_committee -> opposite_floor -> passed_legislature
    -> governor -> enacted (or vetoed/failed)
```

The API does not return a normalized lifecycle stage. You must derive it from a combination of the `status` field, the `history_line` text, and the bill's `originalAgency` (originating chamber).

### The Cross-Chamber Detection Failure (Issue #58)

**This was the most impactful bug in the project.** 257 of 276 active bills were hidden from the site for approximately 6 days.

**What happened:** After the House of Origin cutoff (Feb 17), bills that crossed to the opposite chamber were mapped to plain `committee` status instead of `opposite_committee`. The cutoff filter then hid them as failed bills.

**Why:** The `normalize_status()` function tried to detect cross-chamber activity from history lines like `"First reading, referred to Ways & Means."` But the API omits the chamber name (it does not say "Senate Ways & Means"), so the detection failed silently. Bills fell through to the generic `"referred to"` match, which returned `committee`.

**Why it wasn't caught:**
- No cross-chamber bills existed before the Feb 17 cutoff -- the bug could not manifest earlier
- Bills crossed over individually, so the count decreased gradually (not all at once)
- 18 Senate Governor Appointments (SGAs) always remained visible, masking the drop
- Tests validated that status values were in the allowed set, but did not test that specific API inputs mapped to the correct status

**The fix:** Use the API `status` field's chamber prefix (`"H "` / `"S "`) to detect which chamber the bill is in. Compare against the bill's `originalAgency` to determine if it has crossed chambers. This is 100% reliable and does not depend on ambiguous history text.

```python
# A House bill with status "S ..." is in the Senate (opposite chamber)
if opposite_prefix and status_lower.startswith(opposite_prefix):
    if any(kw in status_lower for kw in ["rules", "2nd reading", "3rd reading"]):
        return "opposite_floor"
    return "opposite_committee"
```

**Lesson:** Never rely solely on history line text for status detection. The `status` field prefix is the authoritative signal for chamber location. Test your status mapping against real API outputs, not just the set of allowed values.

### Governor and Post-Session Statuses (Issue #62)

After the session ended (March 12), bills with `passed_legislature` status were hidden because they were included in the Sine Die cutoff's `failsBefore` list. Bills that successfully passed both chambers are not failures -- they are awaiting governor action. The `governor` and `passed_legislature` statuses needed to be treated as terminal (not subject to cutoff filtering).

**Lesson:** The bill lifecycle does not end when the session ends. Post-session statuses (governor action, signing, vetoing) continue for weeks or months. Design your status model and filtering to account for the full lifecycle, not just the session window.

### Status Detection Decision Tree

After multiple iterations, here is the correct priority order for status detection:

1. **History line keywords (post-legislature):** "effective date", "governor signed", "C ### L 20##" pattern, "delivered to governor", "veto", "died/failed" -- these are the highest-confidence signals
2. **API status prefix (cross-chamber):** Compare `status` field prefix against `originalAgency` to detect opposite-chamber activity
3. **History line keywords (cross-chamber fallback):** "passed" with both chamber names, "third reading, passed", "referred to {opposite chamber}"
4. **Status field keywords (origin chamber):** "passed", "committee", "introduced", "prefiled"
5. **History line keywords (origin chamber):** "referred to", "first reading", "second reading", "rules committee"
6. **Default:** prefiled

---

## 3. Session Lifecycle and Cutoff Dates

### Cutoff Calendar

The WA Legislature publishes a cutoff calendar for each session. These dates are hard deadlines after which bills that have not reached a certain stage are effectively dead.

**2026 Short Session Cutoffs:**

| Date | Cutoff | Bills That Fail |
|------|--------|----------------|
| Feb 4 | Policy Committee (Origin) | prefiled, introduced |
| Feb 9 | Fiscal Committee (Origin) | + committee |
| Feb 17 | House of Origin | + floor |
| Feb 25 | Policy Committee (Opposite) | + passed_origin |
| Mar 4 | Fiscal Committee (Opposite) | + opposite_committee |
| Mar 6 | Opposite House | + opposite_floor |
| Mar 12 | Sine Die | Session ends |

### Cutoff Date Pitfalls

**1. Cutoffs expire at end of day, not beginning.**
The cutoff on "February 4" means bills must pass by 11:59 PM on February 4th, not midnight of February 3rd. Our initial implementation treated the cutoff date as the start of the day, causing bills to be hidden one day early (Issue #43). The fix was to use end-of-day comparison.

**2. Sine Die does not kill passed bills.**
Bills with `passed_legislature`, `governor`, or `enacted` status should NOT be treated as Sine Die failures. They successfully completed the legislative process and are now in the executive branch pipeline. Only bills still in legislative stages (committee, floor, etc.) fail at Sine Die.

**3. The cutoff calendar is a PDF, not structured data.**
The official source is a PDF at `leg.wa.gov/media/b2akn2nz/2026-cutoff-calendar-short.pdf`. There is no API endpoint for cutoff dates. These must be manually coded into the application configuration each session.

**4. Cutoff dates differ between long and short sessions.**
The 2025 long session and 2026 short session have entirely different cutoff calendars. Do not reuse dates across sessions.

---

## 4. Data Pipeline Architecture

### The Monolith Problem

The initial architecture used a single script (`fetch_all_bills.py`) that fetched ALL 3,756 bills on every run. This created cascading problems:

- **15-30 minute pipeline runs** -- every code push waited for a full data refetch before deploying
- **7,200+ API calls per day** -- twice daily, fetching every bill regardless of changes
- **Fragile deployments** -- a slow API day or timeout could fail the entire deploy
- **Developer frustration** -- CSS changes took 30 minutes to go live

### The Incremental Solution (Issue #42)

**Architecture change:** Split into two decoupled workflows:

1. **`fetch-data.yml`** -- Scheduled data fetching only (no deployment)
2. **`deploy.yml`** -- Triggered by any push to main (instant, no data fetching)

**Incremental fetching strategy:**
- Maintain a `data/manifest.json` tracking each bill's last-fetched timestamp and content hash
- On each run, call `GetLegislationByYear` (cheap, returns all bill metadata)
- Compare each bill's action date against the manifest
- Only call `GetLegislation` for bills that are new or changed
- Skip bills in terminal statuses (enacted, vetoed, failed) unless forced
- Full refresh once per week (or on manual trigger)

**Results:**

| Metric | Before | After |
|--------|--------|-------|
| API calls per run | ~3,600 | ~50-200 |
| Fetch runtime | 15-30 min | 1-3 min |
| Deploy on code push | 15-30 min | ~30 sec |
| GitHub Actions minutes/day | ~40-60 min | ~5-10 min |

**Lesson:** Always design for incremental updates when working with large datasets from slow APIs. The manifest-based approach (track what you have, fetch only what changed) is the right pattern.

### Content Hash for Change Detection

A bill's "changed" state is determined by hashing four fields:
```python
content = f"{status}|{history_line}|{action_date}|{sponsor}"
hash = md5(content.encode()).hexdigest()[:8]
```

This catches status changes, new history entries, and sponsor updates without deep comparison. The 8-character truncated MD5 is sufficient for change detection (not security).

---

## 5. Frontend Performance at Scale

### The 3,500-Bill Problem (Issue #1)

The initial release crashed mobile browsers. Loading all 3,564 bills as a single 2.5 MB JSON payload and rendering them all into the DOM simultaneously created ~200,000 DOM nodes.

**Impact:** Mobile browsers (especially mid-range Android) would freeze, crash, or show a white screen for 6-8 seconds on 3G connections.

### Fixes Applied (Issues #2-#26)

The mobile performance overhaul touched 14 distinct issues across four categories:

**CSS Rendering:**
- Disabled `backdrop-filter: blur()` on mobile (one of the most expensive CSS properties)
- Disabled the animated gradient background on mobile and `prefers-reduced-motion`
- Scoped `transition: all` to specific properties only
- Wrapped `:hover` effects in `@media (hover: hover)`

**JavaScript Performance:**
- Added 250ms debounce to search input (eliminated 9x re-renders per search)
- Pre-computed lowercase search fields at load time
- Cached `filterBills()` result (was being called twice per UI update)
- Implemented pagination (25 bills per page instead of 3,500)
- Added dirty-flag auto-save (was serializing to JSON every 30s unconditionally)
- Replaced inline `onclick` handlers with event delegation

**Network/Loading:**
- Added `defer` attribute to script tag
- Added loading skeleton for progressive rendering
- Reduced Google Fonts weight variants

**Mobile UX:**
- Collapsed user panel by default on mobile
- Increased touch target sizes to 48px minimum
- Added `touch-action: pan-x` on horizontal scroll containers

**Lesson:** A legislative tracker will always have thousands of bills. Design for pagination/virtual scrolling from day one. Never render the full dataset into the DOM.

---

## 6. Operational Pitfalls

### Mixed Session Years

The API returns bills from both years of the biennium. Without explicit session year filtering, the tracker displayed 2025-enacted laws alongside 2026 active bills. Users clicked through to leg.wa.gov and found laws from last year, causing confusion (Issue #27).

**Fix:** Tag each bill with its session year at fetch time based on `introducedDate`. Filter 2025 bills from the default view.

### Committee Filter With No Committee Data

The committee filter was shipped with six filter tags (Education, Transportation, etc.) but the `committee` field in `bills.json` was empty for all bills. Clicking any committee filter showed zero results (Issue #35).

**Root cause:** The data pipeline did not populate the top-level `committee` field. Committee data existed in the `hearings` array but was never promoted to the bill-level field.

**Lesson:** Always verify that filter UI elements actually match the data they filter against. Integration tests should confirm that at least some bills match each filter option.

### Cutoff Banner Timing

The cutoff date banner displayed "Cutoff: February 4" but bills were being hidden starting at midnight on February 4 (beginning of day). The actual cutoff is end of day on February 4 (Issue #43).

**Lesson:** Legislative cutoff dates mean end-of-business on that date. Use `endOfDay()` comparisons, not `startOfDay()`.

### Post-Session Schedule Waste

After the session ended (March 12), the data pipeline continued fetching twice daily, including weekends. Governor actions only happen on business days, so weekend and evening fetches were wasted API calls and Actions minutes.

**Fix:** Reduced to once per weekday (Mon-Fri, 6 AM Pacific) post-session.

---

## 7. What Worked Well

### Structured Issue Tracking

Every code change was mapped to a GitHub issue with a remediation plan before implementation. This created a complete audit trail and made it possible to write this document months later. The issue-first workflow prevented scope creep and kept changes focused.

### Debug Artifacts in CI

The GitHub Actions workflow saves raw API request/response XML as debug artifacts (7-day retention). When the cross-chamber bug was discovered, we could inspect the actual API responses to understand the data format without making new requests.

### Incremental Fetch with Full-Refresh Fallback

The manifest-based incremental fetcher handles 95% of runs efficiently, but the weekly full refresh (and manual `workflow_dispatch` trigger) provides a safety net for any drift between incremental and full state.

### Content Security Policy

The site ships with a strict CSP header that limits script sources, prevents framing, and restricts connections to the data source. This was low effort to implement and provides meaningful protection for a site that stores user data (tracked bills, notes) in cookies.

---

## 8. Recommendations for Future Sessions

### Before the Next Session Starts

1. **Update cutoff dates** -- The cutoff calendar changes every session. Update `APP_CONFIG.cutoffDates` in `app.js` and verify end-of-day semantics.
2. **Update session dates** -- Change `sessionStart`, `sessionEnd`, and `YEAR` constants.
3. **Restore full fetch schedule** -- During active session, restore twice-daily fetching (6 AM/6 PM) and the Sunday full refresh.
4. **Clear the manifest** -- Delete `data/manifest.json` to force a full initial fetch of all new session bills.
5. **Review status mapping** -- The API may change field formats between sessions. Test `normalize_status()` against fresh API data before go-live.

### Technical Debt to Address

1. **Add integration tests with real API payloads** -- Test `normalize_status()` against captured API responses for known bills at each lifecycle stage. The cross-chamber bug existed because tests only validated the set of allowed statuses, not the correctness of the mapping.
2. **Add bill count sanity checks** -- If visible bill count drops by more than 50% between syncs, flag it. The cross-chamber bug caused a gradual drop from ~276 to ~19 bills without any alert.
3. **Document the API status field format** -- The `"H "` / `"S "` prefix convention is not in any official documentation. Preserve this knowledge in code comments and this document.
4. **Consider a REST/JSON proxy** -- If this project scales beyond a single static site, consider building a lightweight proxy that wraps the SOAP API and serves JSON. The XML parsing overhead and SOAP boilerplate add unnecessary complexity to every consumer.
5. **Add monitoring for governor action period** -- Post-session, the governor has 20 days to act on bills. Add countdown tracking per bill showing days remaining before pocket veto.

### API Reliability Notes

- The API is generally available but has no published SLA
- Outages of 30-60 minutes have been observed during high-traffic periods (session start, cutoff days)
- The 60-second timeout in our SOAP client has been sufficient; increase if you see timeout errors
- Weekend response times are noticeably faster than weekday
- The API does not version its endpoints; breaking changes could arrive without notice

---

## Appendix: Key Files Reference

| File | Purpose |
|------|---------|
| `scripts/fetch_all_bills.py` | Full bill fetcher, SOAP client, status normalization |
| `scripts/fetch_bills_incremental.py` | Incremental fetcher with manifest-based change detection |
| `scripts/validate_bills_json.py` | JSON validation for CI |
| `app.js` | Frontend application, filtering, cutoff logic, stats |
| `index.html` | UI layout, CSS, filter tags |
| `data/bills.json` | Complete bill dataset |
| `data/manifest.json` | Incremental fetch state tracking |
| `.github/workflows/fetch-data.yml` | Scheduled data fetching |
| `.github/workflows/deploy.yml` | Site deployment on push |

---

## Appendix: Issue Index

Issues most relevant to understanding API and architecture decisions:

| Issue | Title | Category |
|-------|-------|----------|
| #58 | Cross-chamber bill status detection failure | API / Status Bug |
| #42 | Decouple data fetching from deployment | Architecture |
| #43 | Cutoff date logic is bad | Cutoff / Timing |
| #35 | Committee filter breaks search | Data Pipeline |
| #27 | 2025 session bills present in 2026 view | API / Session Years |
| #62 | Post-session bill status visibility | Cutoff / Lifecycle |
| #1 | Mobile devices struggle to load page | Frontend Performance |
| #34 | Sine Die cutoff | Session Lifecycle |

---

*This document was compiled from GitHub Issues #1-#64, git history (100+ commits), and operational experience from the 2026 WA Legislative Short Session.*
