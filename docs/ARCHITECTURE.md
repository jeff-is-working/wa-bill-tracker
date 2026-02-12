---
title: Architecture & Data Flow
scope: System design, data pipeline, and SOAP API integration
last_updated: 2026-02
---

# Architecture & Data Flow

## Table of Contents

1. [Overview](#overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Technology Stack](#technology-stack)
4. [Data Pipeline](#data-pipeline)
5. [SOAP API Reference](#soap-api-reference)
6. [Data Storage](#data-storage)
7. [Design Decisions](#design-decisions)
8. [Scalability](#scalability)

---

## Overview

The WA Bill Tracker is a **serverless, static web application** that tracks Washington State legislative bills. The architecture emphasizes:

- **Zero operational cost** via GitHub Pages hosting
- **No backend servers** -- all processing happens client-side or in CI/CD
- **Automated data synchronization** via GitHub Actions
- **Privacy-first design** -- user data never leaves the browser

### Architecture Style

| Pattern | Implementation |
|---------|----------------|
| **Frontend** | Single Page Application (SPA) |
| **Backend** | Serverless (GitHub Actions) |
| **Data Layer** | Static JSON files + Browser Storage |
| **Deployment** | JAMstack (JavaScript, APIs, Markup) |

---

## High-Level Architecture

```mermaid
flowchart TB
    subgraph External["External Services"]
        API[("WA Legislature\nSOAP API")]
        GH["GitHub\nRepository"]
        CF["Cloudflare\nDNS"]
    end

    subgraph CICD["GitHub Actions CI/CD"]
        FETCH["fetch-data.yml\n(Scheduled)"]
        DEPLOY["deploy.yml\n(On Push)"]
    end

    subgraph Scripts["Python Scripts"]
        FULL["fetch_all_bills.py"]
        INCR["fetch_bills_incremental.py"]
        VAL["validate_bills_json.py"]
    end

    subgraph Data["Data Layer"]
        BILLS[("bills.json\n3,600+ bills")]
        STATS[("stats.json")]
        MANIFEST[("manifest.json")]
    end

    subgraph Frontend["Client Application"]
        HTML["index.html"]
        JS["app.js"]
        STORE[("localStorage\ncookies")]
    end

    subgraph User["End User"]
        BROWSER["Web Browser"]
    end

    API -->|"SOAP 1.1 / HTTPS:443"| FULL
    API -->|"SOAP 1.1 / HTTPS:443"| INCR

    FETCH -->|Triggers| FULL
    FETCH -->|Triggers| INCR
    FULL --> VAL
    INCR --> VAL

    VAL -->|Writes| BILLS
    VAL -->|Writes| STATS
    VAL -->|Writes| MANIFEST

    BILLS -->|"git push"| GH
    GH -->|Triggers| DEPLOY
    DEPLOY -->|"HTTPS:443"| CF

    CF -->|"HTTPS:443"| HTML
    CF -->|"HTTPS:443"| JS
    CF -->|"HTTPS:443"| BILLS

    HTML --> BROWSER
    JS --> BROWSER
    BILLS --> BROWSER
    BROWSER <-->|Persists| STORE
```

### Component Summary

| Script | Purpose | Execution |
|--------|---------|-----------|
| `fetch_all_bills.py` | Complete bill data refresh | Weekly (Sundays) |
| `fetch_bills_incremental.py` | Delta updates for active bills | Every 6 hours |
| `validate_bills_json.py` | Data integrity validation | After every fetch |

### CI/CD Pipeline

```mermaid
flowchart LR
    subgraph Triggers["Workflow Triggers"]
        CRON["Cron Schedule\n6 AM, 6 PM, Sunday"]
        PUSH["Push to main"]
        MANUAL["Manual Dispatch"]
    end

    subgraph FetchWorkflow["fetch-data.yml"]
        CHECKOUT1["Checkout"]
        PYTHON["Setup Python"]
        FETCHSTEP["Run Fetch Script"]
        VALIDATE["Validate JSON"]
        COMMIT["Commit & Push"]
    end

    subgraph DeployWorkflow["deploy.yml"]
        CHECKOUT2["Checkout"]
        TEST["Run Tests"]
        VALIDATE2["Validate Data"]
        CONFIGURE["Configure Pages"]
        UPLOAD["Upload Artifact"]
        DEPLOYSTEP["Deploy to Pages"]
    end

    CRON --> CHECKOUT1
    MANUAL --> CHECKOUT1
    CHECKOUT1 --> PYTHON --> FETCHSTEP --> VALIDATE --> COMMIT

    PUSH --> CHECKOUT2
    COMMIT -->|Triggers| CHECKOUT2
    CHECKOUT2 --> TEST --> VALIDATE2 --> CONFIGURE --> UPLOAD --> DEPLOYSTEP
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for full workflow configuration details.

---

## Technology Stack

### Frontend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **HTML5** | - | Application structure |
| **CSS3** | - | Styling with CSS Grid, Flexbox, Custom Properties |
| **JavaScript** | ES6+ | Application logic (vanilla, no frameworks) |
| **Google Fonts** | - | Inter, JetBrains Mono typefaces |

### Backend Technologies

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11 | Data collection scripts |
| **requests** | 2.32.5 | HTTP client for SOAP API |
| **pytest** | 9.0.2 | Test framework |

### Infrastructure

| Service | Purpose |
|---------|---------|
| **GitHub Pages** | Static file hosting |
| **GitHub Actions** | CI/CD automation |
| **Cloudflare** | DNS management, CDN |
| **WA Legislature API** | Legislative data source |

### Browser APIs

The frontend relies on standard browser APIs (no polyfills needed) for storage, networking, scroll observation, sharing, and hash-based routing:

```mermaid
mindmap
    root((Browser APIs))
        Storage
            localStorage
            document.cookie
        Network
            Fetch API
        DOM
            IntersectionObserver
            MutationObserver
        Sharing
            Web Share API
            Clipboard API
        Navigation
            History API
            hashchange event
```

See [FRONTEND.md](FRONTEND.md) for the full client-side architecture.

---

## Data Pipeline

### Data Sources

The primary data source is the Washington State Legislature's public SOAP API.

| Endpoint | URL |
|----------|-----|
| **Legislation Service** | `https://wslwebservices.leg.wa.gov/LegislationService.asmx` |
| **Committee Service** | `https://wslwebservices.leg.wa.gov/CommitteeService.asmx` |
| **Committee Meeting Service** | `https://wslwebservices.leg.wa.gov/CommitteeMeetingService.asmx` |
| **Sponsor Service** | `https://wslwebservices.leg.wa.gov/SponsorService.asmx` |

| Method | Purpose | Returns |
|--------|---------|---------|
| `GetLegislationByYear` | List all bills for a year | Bill IDs, numbers, basic info |
| `GetPreFiledLegislationInfo` | Pre-filed legislation before session | Pre-filed bill list |
| `GetLegislation` | Full details for one bill | Complete bill record |
| `GetCommitteeMeetings` | Committee hearing schedule | Meeting dates, committees |
| `GetCommitteeMeetingItems` | Bills on meeting agenda | Agenda bill list |

### Fetch Mode Comparison

| Aspect | Full Refresh | Incremental Update |
|--------|-------------|-------------------|
| **Script** | `fetch_all_bills.py` | `fetch_bills_incremental.py` |
| **Schedule** | Weekly (Sundays 2 AM Pacific) | Every 12 hours (6 AM / 6 PM Pacific) |
| **API calls** | ~3,600+ (all bills) | ~400 (active bills only) |
| **Duration** | 30-60 minutes | 5-10 minutes |
| **Use case** | Initial setup, weekly refresh, data recovery | Regular updates |

### Full Fetch Process

Used for initial data collection and weekly refreshes.

```mermaid
sequenceDiagram
    participant S as fetch_all_bills.py
    participant API as WA Legislature API
    participant FS as File System

    Note over S: Start Full Fetch

    S->>API: GetLegislationByYear(2026)
    API-->>S: ~3,588 bills (roster)

    S->>API: GetPreFiledLegislationInfo("2025-26")
    API-->>S: ~40 pre-filed bills

    S->>API: GetLegislationByYear(2025)
    API-->>S: Carryover bills

    S->>S: Deduplicate by bill_number

    loop For each unique bill (3,628)
        S->>API: GetLegislation("2025-26", billNumber)
        API-->>S: Full bill details
        Note over S: 100ms delay (rate limiting)
    end

    S->>API: GetCommitteeMeetings(30-day range)
    API-->>S: Committee meetings

    loop For each meeting with agenda
        S->>API: GetCommitteeMeetingItems(agendaId)
        API-->>S: Agenda bills
    end

    S->>S: Transform & Classify
    S->>S: Generate statistics
    S->>S: Validate data

    S->>FS: Write bills.json
    S->>FS: Write stats.json
    S->>FS: Write manifest.json
    S->>FS: Update sync-log.json

    Note over S: Full Fetch Complete
```

### Incremental Fetch Process

Used for 6-hourly updates to minimize API load.

```mermaid
sequenceDiagram
    participant S as fetch_bills_incremental.py
    participant FS as File System
    participant API as WA Legislature API

    Note over S: Start Incremental Fetch

    S->>FS: Load manifest.json
    FS-->>S: Previous fetch metadata

    S->>FS: Load bills.json
    FS-->>S: Existing bill data

    S->>API: GetLegislationByYear(2026)
    API-->>S: Current bill roster

    S->>S: Identify new bills (not in manifest)
    S->>S: Select stale active bills (max 400, oldest first)

    Note over S: Skip terminal statuses: enacted, vetoed, failed

    loop For each bill to refresh
        S->>API: GetLegislation("2025-26", billNumber)
        API-->>S: Bill details
        S->>S: Compute content hash
        alt Hash changed
            S->>S: Update bill record
        else Hash unchanged
            S->>S: Update lastFetched only
        end
    end

    S->>API: GetCommitteeMeetings(30-day range)
    API-->>S: Updated hearings

    S->>S: Merge updates with existing
    S->>S: Validate data

    S->>FS: Write bills.json
    S->>FS: Write manifest.json
    S->>FS: Update sync-log.json

    Note over S: Incremental Fetch Complete
```

### Change Detection Algorithm

```mermaid
flowchart TD
    START["Bill to check"]
    HASH["Compute content hash\nMD5(status|history|date|sponsor)"]
    COMPARE{"Hash matches\nmanifest?"}
    SKIP["Skip update\n(refresh timestamp only)"]
    UPDATE["Full update\n(replace bill record)"]
    END["Next bill"]

    START --> HASH
    HASH --> COMPARE
    COMPARE -->|Yes| SKIP
    COMPARE -->|No| UPDATE
    SKIP --> END
    UPDATE --> END
```

**Content Hash Formula** (see [`scripts/fetch_all_bills.py`](../scripts/fetch_all_bills.py)):

```python
content = f"{status}|{history_line}|{action_date}|{sponsor}"
hash = hashlib.md5(content.encode()).hexdigest()[:8]
```

### Data Transformation Pipeline

```mermaid
flowchart LR
    subgraph Input["Raw API Data"]
        XML["XML Response"]
    end

    subgraph Parse["Parsing"]
        STRIP["Strip Namespaces"]
        EXTRACT["Extract Fields"]
    end

    subgraph Normalize["Normalization"]
        STATUS["Status Mapping"]
        DATE["Date Formatting"]
        ID["ID Standardization"]
    end

    subgraph Enrich["Enrichment"]
        TOPIC["Topic Classification"]
        PRIORITY["Priority Assignment"]
        URL["URL Generation"]
    end

    subgraph Output["Transformed Data"]
        JSON["Bill Object"]
    end

    XML --> STRIP --> EXTRACT
    EXTRACT --> STATUS --> DATE --> ID
    ID --> TOPIC --> PRIORITY --> URL
    URL --> JSON
```

#### Field Transformations

| API Field | Transformed Field | Transformation |
|-----------|------------------|----------------|
| `BillId` | `id` | Remove spaces: "HB 1001" -> "HB1001" |
| `BillId` | `number` | Keep display format: "HB 1001" |
| `ShortDescription` | `title` | Direct copy |
| `LongDescription` | `description` | Direct copy |
| `Sponsor` | `sponsor` | Direct copy with parentheses |
| `Status` + `HistoryLine` | `status` | Normalized to enum value |
| `ActionDate` | `lastUpdated` | ISO 8601 format |
| `IntroducedDate` | `introducedDate` | YYYY-MM-DD format |
| (computed) | `priority` | Keyword-based classification |
| (computed) | `topic` | Keyword-based classification |
| (computed) | `legUrl` | Generated from bill number |
| `OriginalAgency` | `originalAgency` | "House" or "Senate" |

#### Status Normalization

Status is determined by checking `status + historyLine` against these patterns, evaluated in priority order (first match wins):

| Priority | Pattern (in status + historyLine) | Normalized Status |
|----------|----------------------------------|-------------------|
| 1 | "effective date" or "chapter law" | `enacted` |
| 2 | "vetoed" | `vetoed` |
| 3 | "died" or "indefinitely postponed" | `failed` |
| 4 | "governor" | `governor` |
| 5 | Both chambers mentioned | `passed_legislature` |
| 6 | "third reading" | `passed_origin` / `floor` |
| 7 | Committee reference | `committee` |
| 8 | "first reading" | `introduced` |
| 9 | (default) | `prefiled` |

### Topic Classification

| Topic | Keywords |
|-------|----------|
| **Technology** | technology, internet, data, privacy, cyber, artificial intelligence |
| **Education** | education, school, student, teacher, college, university |
| **Tax & Revenue** | tax, revenue, budget, fiscal, levy |
| **Housing** | housing, rent, tenant, landlord, zoning, homeless |
| **Healthcare** | health, medical, hospital, mental, behavioral, pharmacy |
| **Environment** | environment, climate, energy, pollution, water, salmon |
| **Transportation** | transport, road, highway, transit, ferry, vehicle |
| **Public Safety** | crime, police, safety, justice, court, prison |
| **Business** | business, commerce, trade, economy, license, employment |
| **Agriculture** | farm, agriculture, livestock, crop, food |
| **Social Services** | child, family, welfare, benefit, assistance |
| **General Government** | (default if no match) |

### Priority Assignment

Priority is assigned by checking bill metadata against these rules in order (first match wins):

| Rule | Assigned Priority |
|------|-------------------|
| Governor requested (`RequestedByGovernor = true`) | **high** |
| Bill type is Joint Memorial (JM) or Concurrent Resolution (CR) | **low** |
| Title contains: emergency, budget, funding, crisis, fentanyl, urgent | **high** |
| Title contains: technical, housekeeping, commemorat, study, clarifying | **low** |
| Default | **medium** |

---

## SOAP API Reference

### Base URL and Service Endpoints

```
https://wslwebservices.leg.wa.gov
```

| Service | Path | Purpose |
|---------|------|---------|
| **Legislation** | `/LegislationService.asmx` | Bill data and status |
| **Sponsor** | `/SponsorService.asmx` | Legislator information |
| **Committee** | `/CommitteeService.asmx` | Committee information |
| **Committee Meeting** | `/CommitteeMeetingService.asmx` | Hearing schedules |

**Authentication**: None required. All endpoints are publicly accessible.

**Protocol**: SOAP 1.1 over HTTPS. Content-Type: `text/xml; charset=utf-8`. See [`scripts/fetch_all_bills.py`](../scripts/fetch_all_bills.py) for the Python implementation of envelope building, request execution, namespace handling, and retry logic.

### GetLegislationByYear

Returns a list of all bills introduced in a specific year.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `year` | int | Yes | Legislative year (e.g., 2026) |

| Response Field | Type | Description |
|----------------|------|-------------|
| `BillId` | string | Bill identifier (e.g., "HB 1001") |
| `BillNumber` | string | Numeric portion (e.g., "1001") |
| `Biennium` | string | Session period (e.g., "2025-26") |
| `ShortLegislationType` | string | Bill type code |
| `OriginalAgency` | string | "House" or "Senate" |
| `Active` | boolean | Whether bill is active |

### GetPreFiledLegislationInfo

Returns pre-filed legislation before session start.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `biennium` | string | Yes | Biennium (e.g., "2025-26") |

**Response:** Same fields as GetLegislationByYear.

### GetLegislation

Returns full details for a specific bill.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `biennium` | string | Yes | Biennium (e.g., "2025-26") |
| `billNumber` | string | Yes | Bill number without prefix |

| Response Field | Type | Description |
|----------------|------|-------------|
| `BillId` | string | Full bill ID |
| `ShortDescription` | string | Brief title |
| `LongDescription` | string | Full description |
| `Sponsor` | string | Primary sponsor |
| `PrimeSponsorID` | int | Sponsor ID |
| `CurrentStatus/Status` | string | Current status text |
| `CurrentStatus/HistoryLine` | string | Status history |
| `CurrentStatus/ActionDate` | datetime | Last action date |
| `IntroducedDate` | datetime | Introduction date |
| `Active` | boolean | Active status |
| `RequestedByGovernor` | boolean | Governor request flag |
| `LegalTitle` | string | Legal title text |

### GetCommitteeMeetings

Returns committee meeting schedule.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `beginDate` | datetime | Yes | Start date |
| `endDate` | datetime | Yes | End date |

| Response Field | Type | Description |
|----------------|------|-------------|
| `AgendaId` | int | Meeting identifier |
| `Agency` | string | "House" or "Senate" |
| `CommitteeName` | string | Committee name |
| `Date` | datetime | Meeting date |
| `Room` | string | Room location |
| `Cancelled` | boolean | Cancellation status |

### GetCommitteeMeetingItems

Returns bills on a committee meeting agenda.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agendaId` | int | Yes | Meeting agenda ID |

| Response Field | Type | Description |
|----------------|------|-------------|
| `BillId` | string | Bill ID on agenda |
| `HearingType` | string | Type of hearing |
| `HearingTypeDescription` | string | Hearing description |

### Error Handling and Rate Limiting

The fetch scripts implement exponential backoff retry (3 attempts with doubling delay) for transient failures. See [`scripts/fetch_all_bills.py`](../scripts/fetch_all_bills.py) for the implementation.

| Error | Cause | Resolution |
|-------|-------|------------|
| **HTTP 500** | Server error | Retry with backoff |
| **HTTP 503** | Service unavailable | Wait and retry |
| **Timeout** | Slow response | Increase timeout, retry |
| **Invalid XML** | Malformed response | Log and skip |
| **Empty response** | No data found | Handle gracefully |

| Rate Limit Setting | Value | Rationale |
|-------------------|-------|-----------|
| **Request delay** | 100ms | Prevent overwhelming server |
| **Batch checkpoint** | Every 50 bills | Progress tracking |
| **Request timeout** | 60 seconds | Prevent hung connections |

---

## Data Storage

### File Structure

```
data/
├── bills.json      # Primary bill data (3,600+ bills)
├── stats.json      # Aggregated statistics
├── manifest.json   # Fetch tracking metadata
└── sync-log.json   # Sync history (last 100)
```

### bills.json Schema

```json
{
  "lastSync": "2026-02-04T14:55:36.624900",
  "sessionYear": 2026,
  "sessionStart": "2026-01-12",
  "sessionEnd": "2026-03-12",
  "biennium": "2025-26",
  "totalBills": 3628,
  "bills": [
    {
      "id": "HB1001",
      "number": "HB 1001",
      "title": "Fire protection projects",
      "sponsor": "(Abbarno)",
      "description": "Concerning capital projects...",
      "status": "introduced",
      "committee": "House Appropriations",
      "priority": "medium",
      "topic": "Public Safety",
      "introducedDate": "2025-01-13",
      "lastUpdated": "2026-02-04T14:55:36.624900",
      "legUrl": "https://app.leg.wa.gov/billsummary?BillNumber=1001&Year=2026",
      "hearings": [
        {
          "date": "2026-02-15",
          "time": "14:30",
          "committee": "House Appropriations",
          "room": "HCR 120",
          "hearingType": "Work Session"
        }
      ],
      "active": true,
      "biennium": "2025-26",
      "session": "2026",
      "originalAgency": "House",
      "historyLine": "First reading, referred to Appropriations."
    }
  ],
  "metadata": {
    "source": "Washington State Legislature Web Services",
    "apiEndpoint": "https://wslwebservices.leg.wa.gov",
    "updateFrequency": "daily",
    "dataVersion": "3.0.0"
  }
}
```

```mermaid
erDiagram
    BILLS_JSON ||--o{ BILL : contains
    BILLS_JSON {
        string lastSync
        int sessionYear
        string sessionStart
        string sessionEnd
        int totalBills
        array bills
        object metadata
    }

    BILL {
        string id PK
        string number
        string title
        string sponsor
        string description
        string status
        string committee
        string priority
        string topic
        string introducedDate
        string lastUpdated
        string legUrl
        array hearings
        boolean active
        string biennium
        string session
        string originalAgency
        string historyLine
    }

    MANIFEST_JSON ||--o{ BILL_META : tracks
    MANIFEST_JSON {
        string lastFullSync
        string lastIncrementalSync
        int billCount
        object bills
    }

    BILL_META {
        string status
        string contentHash
        string lastFetched
    }
```

### manifest.json Schema

```json
{
  "lastFullSync": "2026-02-01T10:47:49.052366",
  "lastIncrementalSync": "2026-02-04T14:55:36.696735",
  "billCount": 3628,
  "bills": {
    "HB1001": {
      "status": "introduced",
      "contentHash": "5aab42ab",
      "lastFetched": "2026-02-04T14:55:36.052366"
    }
  }
}
```

### stats.json Schema

```json
{
  "generated": "2026-02-04T14:55:36.684495",
  "totalBills": 3628,
  "byStatus": {
    "prefiled": 1927,
    "introduced": 6,
    "committee": 1275,
    "floor": 129,
    "passed_origin": 6,
    "enacted": 285
  },
  "byCommittee": {
    "Unassigned": 3180,
    "House Appropriations": 34
  },
  "byPriority": {
    "high": 267,
    "medium": 3270,
    "low": 91
  },
  "byTopic": {
    "General Government": 2166,
    "Public Safety": 129
  },
  "bySponsor": {
    "(Walsh)": 20
  },
  "topSponsors": [
    ["(Reeves)", 39],
    ["(Couture)", 36]
  ],
  "recentlyUpdated": 145,
  "updatedToday": 23
}
```

### Data Retention

| Data Type | Retention | Location |
|-----------|-----------|----------|
| Bill data | Current session + history | bills.json |
| Sync logs | Last 100 entries | sync-log.json |
| Debug artifacts | 7 days | GitHub Actions |
| User tracked bills | 90 days (cookie) | Browser |
| User notes | 90 days (cookie) | Browser |
| Data cache | 1 hour | localStorage |

---

## Design Decisions

### 1. Static Site Architecture

**Decision**: Use GitHub Pages for hosting instead of a traditional backend server.

**Rationale**:
- Zero hosting costs
- No server maintenance
- High availability via GitHub's CDN
- Automatic SSL certificates
- Simple deployment model

**Trade-offs**:
- No server-side processing
- User data stays in browser only
- No cross-device sync for personal data

### 2. Vanilla JavaScript

**Decision**: Use vanilla JavaScript instead of React, Vue, or other frameworks.

**Rationale**:
- No build step required
- Smaller bundle size (~70 KB vs 100+ KB for frameworks)
- Direct DOM manipulation for performance
- Easier to understand and maintain
- No dependency updates needed

**Trade-offs**:
- More boilerplate code
- Manual state management
- No component lifecycle helpers

### 3. Cookie + localStorage Dual Persistence

**Decision**: Store user data in both cookies and localStorage.

**Rationale**:
- Cookies persist across sessions with expiration control
- localStorage provides larger storage capacity
- Dual storage adds redundancy
- Enables future domain migration

**Trade-offs**:
- Increased storage code complexity
- Data synchronization logic needed

### 4. Incremental Data Sync

**Decision**: Implement incremental fetching instead of always doing full refreshes.

**Rationale**:
- Reduces API load by ~90%
- Faster sync times (minutes vs. hours)
- Minimizes GitHub Actions minutes usage
- Respects rate limits

**Trade-offs**:
- More complex codebase
- Manifest tracking required
- Risk of stale data for edge cases

### 5. JSON Data Format

**Decision**: Store bill data as JSON files rather than a database.

**Rationale**:
- No database hosting required
- Easy to version control
- Human-readable for debugging
- Fast client-side parsing

**Trade-offs**:
- Full file download required
- No query optimization
- Large file size (~5 MB)

---

## Scalability

### Current Scale Metrics

| Metric | Current Value | Capacity |
|--------|---------------|----------|
| Bills tracked | 3,628 | 10,000+ |
| JSON file size | ~5 MB | 100 MB (GitHub limit) |
| API calls/sync | ~400 (incremental) | Rate limit dependent |
| Client memory | ~50 MB | Browser dependent |

### Scaling Strategies

```mermaid
flowchart TB
    subgraph Current["Current Architecture"]
        A["Single JSON file\nAll bills in memory"]
    end

    subgraph Option1["Option 1: Pagination"]
        B["Split JSON by type\nLoad on demand"]
    end

    subgraph Option2["Option 2: Compression"]
        C["Gzip compression\n~80% reduction"]
    end

    subgraph Option3["Option 3: Backend"]
        D["Add API server\nQuery on demand"]
    end

    Current -->|More bills| Option1
    Current -->|Larger data| Option2
    Current -->|Real-time needs| Option3
```

### Performance Optimization Points

1. **Infinite Scroll** -- Only renders 25 bills at a time
2. **Debounced Search** -- 250ms delay prevents excessive updates
3. **Event Delegation** -- Single listener for bill card actions
4. **Skeleton Loading** -- Perceived performance during data fetch
5. **Content Hash** -- Avoids unnecessary data writes
