# Data Flow Documentation

> Complete data pipeline from Washington State Legislature API to user interface

---

## Table of Contents

1. [Data Flow Overview](#data-flow-overview)
2. [Data Sources](#data-sources)
3. [Collection Pipeline](#collection-pipeline)
4. [Data Transformation](#data-transformation)
5. [Storage Architecture](#storage-architecture)
6. [Frontend Consumption](#frontend-consumption)
7. [User Data Persistence](#user-data-persistence)
8. [Data Lifecycle](#data-lifecycle)

---

## Data Flow Overview

```mermaid
flowchart TB
    subgraph Source["Data Source"]
        API[("WA Legislature<br/>SOAP API")]
    end

    subgraph Collection["Collection Layer"]
        FULL["Full Fetch<br/>(Weekly)"]
        INCR["Incremental Fetch<br/>(6-hourly)"]
    end

    subgraph Transform["Transformation"]
        PARSE["XML Parsing"]
        NORM["Normalization"]
        ENRICH["Enrichment"]
        VALID["Validation"]
    end

    subgraph Storage["Storage Layer"]
        BILLS[("bills.json")]
        STATS[("stats.json")]
        MANIFEST[("manifest.json")]
        SYNC[("sync-log.json")]
    end

    subgraph Delivery["Delivery"]
        PAGES["GitHub Pages<br/>CDN"]
    end

    subgraph Client["Client Layer"]
        FETCH2["Fetch API"]
        CACHE["localStorage<br/>Cache"]
        STATE["APP_STATE"]
        UI["User Interface"]
    end

    subgraph UserData["User Data"]
        COOKIE["Cookies"]
        LOCAL["localStorage"]
    end

    API -->|SOAP/XML| FULL
    API -->|SOAP/XML| INCR

    FULL --> PARSE
    INCR --> PARSE

    PARSE --> NORM --> ENRICH --> VALID

    VALID --> BILLS
    VALID --> STATS
    VALID --> MANIFEST
    VALID --> SYNC

    BILLS --> PAGES
    STATS --> PAGES

    PAGES --> FETCH2
    FETCH2 --> CACHE
    CACHE --> STATE
    STATE --> UI

    UI <--> COOKIE
    UI <--> LOCAL
```

---

## Data Sources

### Washington State Legislature Web Services

The primary data source is the official WA Legislature SOAP API.

| Endpoint | URL |
|----------|-----|
| **Legislation Service** | `https://wslwebservices.leg.wa.gov/LegislationService.asmx` |
| **Committee Service** | `https://wslwebservices.leg.wa.gov/CommitteeService.asmx` |
| **Committee Meeting Service** | `https://wslwebservices.leg.wa.gov/CommitteeMeetingService.asmx` |
| **Sponsor Service** | `https://wslwebservices.leg.wa.gov/SponsorService.asmx` |

### API Methods Used

```mermaid
flowchart LR
    subgraph BillData["Bill Data Methods"]
        M1["GetLegislationByYear"]
        M2["GetPreFiledLegislationInfo"]
        M3["GetLegislation"]
    end

    subgraph HearingData["Hearing Data Methods"]
        M4["GetCommitteeMeetings"]
        M5["GetCommitteeMeetingItems"]
    end

    M1 -->|"Bill roster"| OUTPUT[("bills.json")]
    M2 -->|"Pre-filed bills"| OUTPUT
    M3 -->|"Bill details"| OUTPUT
    M4 -->|"Hearings"| OUTPUT
    M5 -->|"Agenda items"| OUTPUT
```

| Method | Purpose | Returns |
|--------|---------|---------|
| `GetLegislationByYear` | List all bills for a year | Bill IDs, numbers, basic info |
| `GetPreFiledLegislationInfo` | Pre-filed legislation before session | Pre-filed bill list |
| `GetLegislation` | Full details for one bill | Complete bill record |
| `GetCommitteeMeetings` | Committee hearing schedule | Meeting dates, committees |
| `GetCommitteeMeetingItems` | Bills on meeting agenda | Agenda bill list |

---

## Collection Pipeline

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

    S->>S: Identify new bills<br/>(not in manifest)

    S->>S: Select stale active bills<br/>(max 400, oldest first)

    Note over S: Skip terminal statuses:<br/>enacted, vetoed, failed

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
    HASH["Compute content hash<br/>MD5(status|history|date|sponsor)"]
    COMPARE{"Hash matches<br/>manifest?"}
    SKIP["Skip update<br/>(refresh timestamp only)"]
    UPDATE["Full update<br/>(replace bill record)"]
    END["Next bill"]

    START --> HASH
    HASH --> COMPARE
    COMPARE -->|Yes| SKIP
    COMPARE -->|No| UPDATE
    SKIP --> END
    UPDATE --> END
```

**Content Hash Formula:**
```python
content = f"{status}|{history_line}|{action_date}|{sponsor}"
hash = hashlib.md5(content.encode()).hexdigest()[:8]
```

---

## Data Transformation

### Transformation Pipeline

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

### Field Transformations

| API Field | Transformed Field | Transformation |
|-----------|------------------|----------------|
| `BillId` | `id` | Remove spaces: "HB 1001" → "HB1001" |
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

### Status Normalization

```mermaid
flowchart TD
    INPUT["Raw Status + HistoryLine"]

    subgraph Checks["Status Detection Priority"]
        C1{"Contains 'effective date'<br/>or 'chapter law'?"}
        C2{"Contains 'vetoed'?"}
        C3{"Contains 'died' or<br/>'indefinitely postponed'?"}
        C4{"Contains 'governor'?"}
        C5{"Both chambers<br/>mentioned?"}
        C6{"Third reading?"}
        C7{"Committee reference?"}
        C8{"First reading?"}
    end

    subgraph Outputs["Normalized Status"]
        S1["enacted"]
        S2["vetoed"]
        S3["failed"]
        S4["governor"]
        S5["passed_legislature"]
        S6["passed_origin / floor"]
        S7["committee"]
        S8["introduced"]
        S9["prefiled"]
    end

    INPUT --> C1
    C1 -->|Yes| S1
    C1 -->|No| C2
    C2 -->|Yes| S2
    C2 -->|No| C3
    C3 -->|Yes| S3
    C3 -->|No| C4
    C4 -->|Yes| S4
    C4 -->|No| C5
    C5 -->|Yes| S5
    C5 -->|No| C6
    C6 -->|Yes| S6
    C6 -->|No| C7
    C7 -->|Yes| S7
    C7 -->|No| C8
    C8 -->|Yes| S8
    C8 -->|No| S9
```

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

```mermaid
flowchart TD
    INPUT["Bill Title + Metadata"]

    GOV{"Governor<br/>requested?"}
    TYPE{"Bill type<br/>JM or CR?"}
    HIGH{"High priority<br/>keywords?"}
    LOW{"Low priority<br/>keywords?"}

    P_HIGH["priority: high"]
    P_LOW["priority: low"]
    P_MED["priority: medium"]

    INPUT --> GOV
    GOV -->|Yes| P_HIGH
    GOV -->|No| TYPE
    TYPE -->|Yes| P_LOW
    TYPE -->|No| HIGH
    HIGH -->|Yes| P_HIGH
    HIGH -->|No| LOW
    LOW -->|Yes| P_LOW
    LOW -->|No| P_MED
```

**High Priority Keywords:** emergency, budget, funding, crisis, fentanyl, urgent
**Low Priority Keywords:** technical, housekeeping, commemorat, study, clarifying

---

## Storage Architecture

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

---

## Frontend Consumption

### Data Loading Flow

```mermaid
sequenceDiagram
    participant U as User
    participant B as Browser
    participant JS as app.js
    participant GP as GitHub Pages
    participant LS as localStorage

    U->>B: Navigate to site
    B->>JS: Initialize app

    JS->>LS: Check cached data
    alt Cache exists and fresh
        LS-->>JS: Cached bills.json
        JS->>B: Render from cache
    else No cache or stale
        JS->>GP: Fetch bills.json
        GP-->>JS: Bill data (~5 MB)
        JS->>LS: Cache response
        JS->>B: Render bills
    end

    Note over JS: Cache validity: 1 hour
```

### Data Processing in Frontend

```mermaid
flowchart TB
    subgraph Load["Data Loading"]
        FETCH["fetch(bills.json)"]
        PARSE["JSON.parse()"]
        ENRICH2["Add _searchText"]
        CACHE2["Cache to localStorage"]
    end

    subgraph State["State Management"]
        APPSTATE["APP_STATE.bills"]
        TRACKED["APP_STATE.trackedBills"]
        NOTES["APP_STATE.userNotes"]
        FILTERS["APP_STATE.filters"]
    end

    subgraph Filter["Filtering Pipeline"]
        F1["Filter inactive bills"]
        F2["Filter by type"]
        F3["Filter by search"]
        F4["Filter by status"]
        F5["Filter by priority"]
        F6["Filter by committee"]
        F7["Filter tracked only"]
    end

    subgraph Render["Rendering"]
        PAGINATE["Paginate (25/page)"]
        CARDS["Generate bill cards"]
        INFINITE["Infinite scroll"]
    end

    FETCH --> PARSE --> ENRICH2 --> CACHE2
    CACHE2 --> APPSTATE

    APPSTATE --> F1 --> F2 --> F3 --> F4 --> F5 --> F6 --> F7
    F7 --> PAGINATE --> CARDS --> INFINITE

    TRACKED --> F7
    NOTES --> CARDS
    FILTERS --> F1
```

### Search Index Enhancement

Each bill receives an enhanced `_searchText` field for fast filtering:

```javascript
bill._searchText = [
  bill.number,      // "HB 1001"
  bill.title,       // "Fire protection projects"
  bill.description, // Full description
  bill.sponsor      // "(Abbarno)"
].join(' ').toLowerCase();
```

---

## User Data Persistence

### Dual Storage Strategy

```mermaid
flowchart TB
    subgraph UserActions["User Actions"]
        TRACK["Track Bill"]
        NOTE["Add Note"]
        FILTER["Set Filter"]
    end

    subgraph State["APP_STATE"]
        TB["trackedBills (Set)"]
        UN["userNotes (Object)"]
        FL["filters (Object)"]
    end

    subgraph Primary["Primary Storage (Cookies)"]
        C1["wa_tracked_bills"]
        C2["wa_user_notes"]
        C3["wa_filters"]
    end

    subgraph Backup["Backup Storage (localStorage)"]
        L1["wa_tracked_bills"]
        L2["wa_user_notes"]
        L3["wa_filters"]
    end

    TRACK --> TB --> C1 & L1
    NOTE --> UN --> C2 & L2
    FILTER --> FL --> C3 & L3
```

### Cookie Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| **Path** | `/` | Site-wide access |
| **SameSite** | `Lax` | CSRF protection |
| **Secure** | `true` | HTTPS only |
| **Expires** | 90 days | Persistence duration |

### Data Synchronization

```mermaid
sequenceDiagram
    participant UI as User Interface
    participant SM as StorageManager
    participant C as Cookies
    participant LS as localStorage

    Note over UI: User tracks a bill

    UI->>SM: save()

    SM->>C: Set wa_tracked_bills
    SM->>LS: Set wa_tracked_bills (backup)

    Note over SM: Auto-save every 30 seconds<br/>if APP_STATE._dirty

    Note over UI: Page reload

    UI->>SM: load()

    SM->>C: Get wa_tracked_bills
    alt Cookie exists
        C-->>SM: Tracked bill IDs
    else Cookie missing
        SM->>LS: Get wa_tracked_bills (fallback)
        LS-->>SM: Tracked bill IDs
    end

    SM-->>UI: Restore state
```

---

## Data Lifecycle

### Bill Data Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Prefiled: Pre-session filing

    Prefiled --> Introduced: Session starts
    Introduced --> Committee: Referred

    Committee --> Floor: Reported out
    Committee --> Failed: Died in committee

    Floor --> PassedOrigin: Passed
    Floor --> Failed: Failed vote

    PassedOrigin --> OppositeCommittee: Sent to other chamber
    OppositeCommittee --> OppositeFloor: Reported out
    OppositeFloor --> PassedLegislature: Passed

    PassedLegislature --> Governor: Sent to governor

    Governor --> Enacted: Signed
    Governor --> Vetoed: Vetoed
    Governor --> PartialVeto: Partial veto

    Enacted --> [*]
    Vetoed --> [*]
    PartialVeto --> [*]
    Failed --> [*]
```

### Sync Schedule

```mermaid
gantt
    title Weekly Sync Schedule
    dateFormat  YYYY-MM-DD
    axisFormat  %a

    section Incremental
    6 AM Sync     :active, 2026-02-02, 1h
    6 PM Sync     :active, 2026-02-02, 1h
    6 AM Sync     :active, 2026-02-03, 1h
    6 PM Sync     :active, 2026-02-03, 1h
    6 AM Sync     :active, 2026-02-04, 1h
    6 PM Sync     :active, 2026-02-04, 1h
    6 AM Sync     :active, 2026-02-05, 1h
    6 PM Sync     :active, 2026-02-05, 1h
    6 AM Sync     :active, 2026-02-06, 1h
    6 PM Sync     :active, 2026-02-06, 1h
    6 AM Sync     :active, 2026-02-07, 1h
    6 PM Sync     :active, 2026-02-07, 1h

    section Full Refresh
    Sunday Full   :crit, 2026-02-08, 4h
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

## Related Documentation

- [API Integration](API_INTEGRATION.md) - Detailed SOAP API documentation
- [Architecture](ARCHITECTURE.md) - System architecture overview
- [Frontend](FRONTEND.md) - Client-side data handling
- [Runbooks](RUNBOOKS.md) - Data sync procedures

---

*Last updated: February 2026*
