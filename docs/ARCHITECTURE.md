# System Architecture

> WA Bill Tracker - Technical Architecture Documentation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Overview](#component-overview)
4. [Technology Stack](#technology-stack)
5. [System Interactions](#system-interactions)
6. [Design Decisions](#design-decisions)
7. [Scalability Considerations](#scalability-considerations)

---

## Executive Summary

The WA Bill Tracker is a **serverless, static web application** that tracks Washington State legislative bills. The architecture emphasizes:

- **Zero operational cost** via GitHub Pages hosting
- **No backend servers** - all processing happens client-side or in CI/CD
- **Automated data synchronization** via GitHub Actions
- **Privacy-first design** - user data never leaves the browser

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
        API[("WA Legislature<br/>SOAP API")]
        GH["GitHub<br/>Repository"]
        CF["Cloudflare<br/>DNS"]
    end

    subgraph CICD["GitHub Actions CI/CD"]
        FETCH["fetch-data.yml<br/>(Scheduled)"]
        DEPLOY["deploy.yml<br/>(On Push)"]
    end

    subgraph Scripts["Python Scripts"]
        FULL["fetch_all_bills.py"]
        INCR["fetch_bills_incremental.py"]
        VAL["validate_bills_json.py"]
    end

    subgraph Data["Data Layer"]
        BILLS[("bills.json<br/>3,600+ bills")]
        STATS[("stats.json")]
        MANIFEST[("manifest.json")]
    end

    subgraph Frontend["Client Application"]
        HTML["index.html"]
        JS["app.js"]
        STORE[("localStorage<br/>cookies")]
    end

    subgraph User["End User"]
        BROWSER["Web Browser"]
    end

    API -->|SOAP/XML| FULL
    API -->|SOAP/XML| INCR

    FETCH -->|Triggers| FULL
    FETCH -->|Triggers| INCR
    FULL --> VAL
    INCR --> VAL

    VAL -->|Writes| BILLS
    VAL -->|Writes| STATS
    VAL -->|Writes| MANIFEST

    BILLS -->|Commit| GH
    GH -->|Triggers| DEPLOY
    DEPLOY -->|Publishes| CF

    CF -->|Serves| HTML
    CF -->|Serves| JS
    CF -->|Serves| BILLS

    HTML --> BROWSER
    JS --> BROWSER
    BILLS --> BROWSER
    BROWSER <-->|Persists| STORE
```

---

## Component Overview

### 1. Data Collection Layer

Python scripts that interface with the Washington State Legislature SOAP API.

```mermaid
flowchart LR
    subgraph Collection["Data Collection Scripts"]
        direction TB
        A["fetch_all_bills.py<br/>1,098 lines"]
        B["fetch_bills_incremental.py<br/>404 lines"]
        C["validate_bills_json.py<br/>109 lines"]
    end

    subgraph Functions["Key Functions"]
        direction TB
        F1["SOAP Envelope Building"]
        F2["XML Response Parsing"]
        F3["Bill Classification"]
        F4["Status Normalization"]
        F5["Change Detection"]
    end

    A --> F1
    A --> F2
    A --> F3
    A --> F4
    B --> F5
    B --> F2
```

| Script | Purpose | Execution |
|--------|---------|-----------|
| `fetch_all_bills.py` | Complete bill data refresh | Weekly (Sundays) |
| `fetch_bills_incremental.py` | Delta updates for active bills | Every 6 hours |
| `validate_bills_json.py` | Data integrity validation | After every fetch |

### 2. Data Storage Layer

JSON files stored in the repository and served via GitHub Pages.

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

### 3. Frontend Application Layer

Single-page application built with vanilla JavaScript.

```mermaid
flowchart TB
    subgraph HTML["index.html Structure"]
        HEAD["Head<br/>Meta, CSP, Fonts"]
        HEADER["Header<br/>Navigation Tabs"]
        MAIN["Main Content<br/>Stats, Filters, Grid"]
        PANEL["User Panel<br/>Tracked Bills, Notes"]
        MODAL["Modals<br/>Note Editor"]
    end

    subgraph JS["app.js Modules"]
        CONFIG["APP_CONFIG<br/>Constants"]
        STATE["APP_STATE<br/>Runtime State"]
        COOKIE["CookieManager"]
        STORAGE["StorageManager"]
        RENDER["Render Functions"]
        FILTER["Filter Engine"]
        EVENTS["Event Handlers"]
    end

    HEAD --> CONFIG
    HEADER --> EVENTS
    MAIN --> RENDER
    MAIN --> FILTER
    PANEL --> STATE
    MODAL --> EVENTS

    CONFIG --> STATE
    STATE --> COOKIE
    STATE --> STORAGE
    STORAGE --> RENDER
```

### 4. CI/CD Pipeline

GitHub Actions workflows for automated deployment and data synchronization.

```mermaid
flowchart LR
    subgraph Triggers["Workflow Triggers"]
        CRON["Cron Schedule<br/>6 AM, 6 PM, Sunday"]
        PUSH["Push to main"]
        MANUAL["Manual Dispatch"]
    end

    subgraph FetchWorkflow["fetch-data.yml"]
        CHECKOUT1["Checkout"]
        PYTHON["Setup Python"]
        FETCH["Run Fetch Script"]
        VALIDATE["Validate JSON"]
        COMMIT["Commit & Push"]
    end

    subgraph DeployWorkflow["deploy.yml"]
        CHECKOUT2["Checkout"]
        TEST["Run Tests"]
        VALIDATE2["Validate Data"]
        CONFIGURE["Configure Pages"]
        UPLOAD["Upload Artifact"]
        DEPLOY["Deploy to Pages"]
    end

    CRON --> CHECKOUT1
    MANUAL --> CHECKOUT1
    CHECKOUT1 --> PYTHON --> FETCH --> VALIDATE --> COMMIT

    PUSH --> CHECKOUT2
    COMMIT -->|Triggers| CHECKOUT2
    CHECKOUT2 --> TEST --> VALIDATE2 --> CONFIGURE --> UPLOAD --> DEPLOY
```

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

### Browser APIs Used

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

---

## System Interactions

### Data Synchronization Flow

```mermaid
sequenceDiagram
    participant GHA as GitHub Actions
    participant PY as Python Scripts
    participant API as WA Legislature API
    participant GH as GitHub Repository
    participant GP as GitHub Pages

    Note over GHA: Cron trigger (6-hourly)
    GHA->>PY: Execute fetch_bills_incremental.py

    PY->>API: GetLegislationByYear(2026)
    API-->>PY: Bill roster XML

    loop For each stale bill
        PY->>API: GetLegislation(biennium, billNumber)
        API-->>PY: Bill details XML
    end

    PY->>API: GetCommitteeMeetings(dateRange)
    API-->>PY: Hearing schedule XML

    PY->>PY: Transform & Validate
    PY->>GH: Commit bills.json, stats.json

    GH-->>GHA: Push event
    GHA->>GHA: Trigger deploy.yml
    GHA->>GP: Deploy to Pages
```

### User Interaction Flow

```mermaid
sequenceDiagram
    participant U as User
    participant B as Browser
    participant JS as app.js
    participant S as Storage
    participant GP as GitHub Pages

    U->>B: Navigate to site
    B->>GP: Request index.html, app.js
    GP-->>B: Static files

    B->>JS: Initialize application
    JS->>GP: Fetch bills.json
    GP-->>JS: Bill data (3,600+ bills)

    JS->>S: Load user preferences
    S-->>JS: Tracked bills, notes, filters

    JS->>B: Render UI

    U->>B: Track a bill
    B->>JS: toggleTrack(billId)
    JS->>S: Save tracked bills
    JS->>B: Update UI

    U->>B: Add note
    B->>JS: saveNote(billId, text)
    JS->>S: Save notes
    JS->>B: Update UI
```

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

## Scalability Considerations

### Current Scale

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
        A["Single JSON file<br/>All bills in memory"]
    end

    subgraph Option1["Option 1: Pagination"]
        B["Split JSON by type<br/>Load on demand"]
    end

    subgraph Option2["Option 2: Compression"]
        C["Gzip compression<br/>~80% reduction"]
    end

    subgraph Option3["Option 3: Backend"]
        D["Add API server<br/>Query on demand"]
    end

    Current -->|More bills| Option1
    Current -->|Larger data| Option2
    Current -->|Real-time needs| Option3
```

### Performance Optimization Points

1. **Infinite Scroll**: Only renders 25 bills at a time
2. **Debounced Search**: 250ms delay prevents excessive updates
3. **Event Delegation**: Single listener for bill card actions
4. **Skeleton Loading**: Perceived performance during data fetch
5. **Content Hash**: Avoids unnecessary data writes

---

## Architecture Diagrams Reference

| Diagram | Location | Purpose |
|---------|----------|---------|
| System Overview | This document | High-level component interaction |
| Data Flow | [DATA_FLOW.md](DATA_FLOW.md) | Detailed data pipeline |
| API Sequence | [API_INTEGRATION.md](API_INTEGRATION.md) | SOAP request/response |
| Frontend Components | [FRONTEND.md](FRONTEND.md) | UI architecture |
| CI/CD Pipeline | [DEPLOYMENT.md](DEPLOYMENT.md) | Workflow details |

---

## Related Documentation

- [Data Flow](DATA_FLOW.md) - Detailed data pipeline documentation
- [API Integration](API_INTEGRATION.md) - SOAP API integration details
- [Frontend](FRONTEND.md) - Client-side architecture
- [Deployment](DEPLOYMENT.md) - Infrastructure and CI/CD

---

*Last updated: February 2026*
