# WA Bill Tracker Documentation

> **Enterprise Documentation Package**
> Version 1.0 | February 2026

Welcome to the comprehensive documentation for the Washington State Legislative Bill Tracker. This documentation is designed for developers, operations teams, and technical stakeholders who need to understand, maintain, or extend the application.

---

## Quick Navigation

| Document | Description | Audience |
|----------|-------------|----------|
| [Architecture](ARCHITECTURE.md) | System design, components, and technology stack | Architects, Developers |
| [Data Flow](DATA_FLOW.md) | Data pipeline from API to user interface | Developers, Data Engineers |
| [API Integration](API_INTEGRATION.md) | WA Legislature SOAP API integration details | Backend Developers |
| [Frontend](FRONTEND.md) | Client-side architecture and components | Frontend Developers |
| [Deployment](DEPLOYMENT.md) | GitHub Pages and CI/CD configuration | DevOps, Operations |
| [Developer Guide](DEVELOPER_GUIDE.md) | Development setup and contribution guidelines | New Developers |
| [Testing](TESTING.md) | Test suite documentation and practices | QA, Developers |
| [Security](SECURITY.md) | Security model and best practices | Security, Architects |
| [Troubleshooting](TROUBLESHOOTING.md) | Common issues and solutions | Operations, Support |
| [Runbooks](RUNBOOKS.md) | Operational procedures and incident response | Operations |
| [Lessons Learned](LESSONS_LEARNED.md) | Project insights and development standards | All Teams |

---

## Project Overview

### What is WA Bill Tracker?

The WA Bill Tracker is a web application that provides real-time monitoring of Washington State legislative activity during the 2025-26 biennium. It enables users to:

- **Track Bills**: Monitor the status of 3,600+ bills across the legislative session
- **Personal Lists**: Create tracked bill lists with custom notes
- **Search & Filter**: Find bills by type, status, committee, priority, or keyword
- **Stay Informed**: View upcoming hearings and recent status changes
- **Share**: Generate shareable links to specific bills

### Key Characteristics

| Aspect | Implementation |
|--------|----------------|
| **Architecture** | Static single-page application (SPA) |
| **Frontend** | Vanilla JavaScript, HTML5, CSS3 |
| **Backend** | Python data collection scripts |
| **Data Source** | WA Legislature SOAP API |
| **Hosting** | GitHub Pages with custom domain |
| **Updates** | Automated via GitHub Actions (6-hourly) |
| **Storage** | JSON files (server), cookies/localStorage (client) |

### Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT BROWSER                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ index.html  │  │   app.js    │  │ localStorage/Cookies│  │
│  │   (63 KB)   │  │   (70 KB)   │  │   (User Data)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     GITHUB PAGES CDN                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ bills.json  │  │ stats.json  │  │   manifest.json     │  │
│  │  (~5 MB)    │  │   (50 KB)   │  │     (200 KB)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    GITHUB ACTIONS CI/CD                      │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │   fetch-data.yml    │  │       deploy.yml            │   │
│  │ (6-hourly + weekly) │  │    (on push to main)        │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              PYTHON DATA COLLECTION SCRIPTS                  │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │ fetch_all_bills.py  │  │ fetch_bills_incremental.py  │   │
│  │   (Full Refresh)    │  │    (Delta Updates)          │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           WASHINGTON STATE LEGISLATURE API                   │
│            https://wslwebservices.leg.wa.gov                │
│                      (SOAP 1.1)                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Getting Started

### For Users
Visit [wa-bill-tracker.org](https://wa-bill-tracker.org) to start tracking bills.

### For Developers
1. Clone the repository: `git clone https://github.com/jeff-is-working/wa-bill-tracker.git`
2. See the [Developer Guide](DEVELOPER_GUIDE.md) for setup instructions

### For Operations
1. Review [Deployment](DEPLOYMENT.md) for infrastructure details
2. Consult [Runbooks](RUNBOOKS.md) for operational procedures

---

## Repository Structure

```
wa-bill-tracker/
├── index.html              # Main application page
├── app.js                  # Frontend JavaScript application
├── CNAME                   # Custom domain configuration
├── README.md               # Project README
│
├── data/                   # Generated data files
│   ├── bills.json          # Bill data (3,600+ bills)
│   ├── stats.json          # Aggregated statistics
│   ├── manifest.json       # Fetch metadata and hashes
│   └── sync-log.json       # Sync history
│
├── scripts/                # Python data collection
│   ├── fetch_all_bills.py          # Full data refresh
│   ├── fetch_bills_incremental.py  # Incremental updates
│   └── validate_bills_json.py      # Data validation
│
├── tests/                  # Test suite
│   ├── test_fetch_all_bills.py     # SOAP/XML tests
│   ├── test_incremental_fetch.py   # Sync logic tests
│   ├── test_regression.py          # Data integrity tests
│   └── test_validate_bills.py      # Validation tests
│
├── .github/workflows/      # CI/CD automation
│   ├── deploy.yml          # Deployment workflow
│   └── fetch-data.yml      # Data sync workflow
│
└── docs/                   # Documentation (this folder)
    ├── README.md           # Documentation index (this file)
    ├── ARCHITECTURE.md     # System architecture
    ├── DATA_FLOW.md        # Data pipeline documentation
    ├── API_INTEGRATION.md  # API integration guide
    ├── FRONTEND.md         # Frontend architecture
    ├── DEPLOYMENT.md       # Deployment guide
    ├── DEVELOPER_GUIDE.md  # Developer onboarding
    ├── TESTING.md          # Test documentation
    ├── SECURITY.md         # Security practices
    ├── TROUBLESHOOTING.md  # Issue resolution
    ├── RUNBOOKS.md         # Operational procedures
    └── LESSONS_LEARNED.md  # Project insights
```

---

## Key Metrics

| Metric | Value |
|--------|-------|
| **Total Bills Tracked** | 3,628+ |
| **Bill Types** | 8 (HB, SB, HJR, SJR, HJM, SJM, HCR, SCR) |
| **Update Frequency** | Every 6 hours (incremental), Weekly (full) |
| **Test Coverage** | 1,177 lines across 4 test modules |
| **Frontend Size** | ~133 KB (HTML + JS) |
| **Data Size** | ~5 MB (bills.json) |

---

## Session Information

| Parameter | Value |
|-----------|-------|
| **Biennium** | 2025-26 |
| **Current Session** | 2026 Regular Session |
| **Session Start** | January 12, 2026 |
| **Session End** | March 12, 2026 (60 days) |
| **Cutoff Dates** | See [Runbooks](RUNBOOKS.md#legislative-cutoff-dates) |

---

## External Resources

- **Live Application**: [wa-bill-tracker.org](https://wa-bill-tracker.org)
- **GitHub Repository**: [github.com/jeff-is-working/wa-bill-tracker](https://github.com/jeff-is-working/wa-bill-tracker)
- **WA Legislature Official Site**: [leg.wa.gov](https://leg.wa.gov)
- **WA Legislature API Documentation**: [wslwebservices.leg.wa.gov](https://wslwebservices.leg.wa.gov)

---

## Documentation Conventions

Throughout this documentation:

- **Code blocks** show actual configuration or code examples
- **Mermaid diagrams** render automatically on GitHub
- **Tables** provide quick reference information
- **File paths** are relative to repository root unless noted
- **Commands** assume Linux/macOS bash environment

---

## Contributing to Documentation

1. Documentation lives in the `/docs` directory
2. Use Markdown with GitHub-flavored extensions
3. Include Mermaid diagrams where helpful
4. Keep technical depth consistent with target audience
5. Update this index when adding new documents

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | February 2026 | Initial enterprise documentation package |

---

*Last updated: February 2026*
