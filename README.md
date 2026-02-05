# WA Legislative Tracker 2026

A free, open-source bill tracking application for the Washington State Legislature 2025-26 biennium session. Built for citizens, researchers, lobbyists, and civic organizations who need to monitor legislative activity.

**[Live Demo](https://wa-bill-tracker.org)** | **[Official WA Legislature](https://app.leg.wa.gov/)**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Session](https://img.shields.io/badge/session-2025--26-purple.svg)
![Updates](https://img.shields.io/badge/updates-daily-green.svg)
![Platform](https://img.shields.io/badge/platform-GitHub%20Pages-orange.svg)

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Adapting for Other States](#adapting-for-other-states)
- [Session Updates](#session-updates)
- [API Reference](#api-reference)
- [Development](#development)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Real-Time Bill Tracking** - Monitor bills, resolutions, initiatives, and referendums
- **Personal Tracking Lists** - Mark bills of interest and track their progress
- **Note Taking** - Add private notes to any bill for your reference
- **Advanced Filtering** - Filter by status, priority, committee, bill type, and keywords
- **Session Statistics** - Dashboard showing session progress and bill counts
- **Share Links** - Generate shareable links to specific bills
- **No Account Required** - All data stored locally in your browser
- **Mobile Responsive** - Works on desktop, tablet, and mobile devices
- **Zero Cost Hosting** - Runs entirely on GitHub Pages (free)
- **Automated Updates** - GitHub Actions syncs data every 6 hours

### Bill Types Supported

| Type | Description |
|------|-------------|
| HB | House Bills |
| SB | Senate Bills |
| HJR | House Joint Resolutions |
| SJR | Senate Joint Resolutions |
| HJM | House Joint Memorials |
| SJM | Senate Joint Memorials |
| HCR | House Concurrent Resolutions |
| SCR | Senate Concurrent Resolutions |
| I | Initiatives |
| R | Referendums |

---

## Quick Start

### Option 1: Use the Live Site

Visit [https://wa-bill-tracker.org](https://wa-bill-tracker.org)

### Option 2: Deploy Your Own Instance

```bash
# Clone the repository
git clone https://github.com/jeff-is-working/wa-bill-tracker.git
cd wa-bill-tracker

# Install Python dependencies
pip install -r requirements.txt

# Fetch initial bill data
python scripts/fetch_all_bills.py

# Serve locally for testing
python -m http.server 8000
# Open http://localhost:8000 in your browser
```

### Option 3: Fork and Deploy

1. Fork this repository
2. Enable GitHub Pages in repository settings (Settings > Pages > Source: main branch)
3. Enable GitHub Actions (Actions > Enable workflows)
4. Your site will be live at `https://[username].github.io/wa-bill-tracker`

---

## Architecture

```
wa-bill-tracker/
|
|-- index.html              # Main application page
|-- app.js                  # Application logic (vanilla JavaScript)
|-- data/
|   |-- bills.json          # Bill data (auto-generated)
|   |-- stats.json          # Statistics (auto-generated)
|   |-- sync-log.json       # Sync history (auto-generated)
|
|-- scripts/
|   |-- fetch_all_bills.py  # Data collection script
|
|-- tests/
|   |-- unit/               # Unit tests
|   |-- integration/        # API integration tests
|   |-- fixtures/           # Test data
|
|-- .github/
|   |-- workflows/
|       |-- ci.yml          # Continuous integration
|       |-- deploy.yml      # Deployment with data sync
|       |-- test.yml        # Test suite
|
|-- docs/                   # Additional documentation
|-- README.md
|-- LICENSE
|-- CHANGELOG.md
|-- requirements.txt
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend | Vanilla JavaScript, HTML5, CSS3 | User interface |
| Data Collection | Python 3.10+ | API integration |
| API | WA Legislature SOAP API | Official data source |
| Hosting | GitHub Pages | Static file serving |
| CI/CD | GitHub Actions | Automated testing and deployment |
| Storage | Browser localStorage + Cookies | User preferences and tracking |

### Data Flow

```
WA Legislature API --> fetch_all_bills.py --> data/bills.json --> app.js --> Browser
     (SOAP/XML)           (Python)              (JSON)         (JavaScript)
```

---

## Documentation

Comprehensive enterprise documentation is available in the [`docs/`](docs/) folder:

| Document | Description |
|----------|-------------|
| [Documentation Index](docs/README.md) | Start here - navigation hub for all docs |
| [Architecture](docs/ARCHITECTURE.md) | System design with diagrams |
| [Data Flow](docs/DATA_FLOW.md) | Complete data pipeline documentation |
| [API Integration](docs/API_INTEGRATION.md) | WA Legislature SOAP API guide |
| [Frontend](docs/FRONTEND.md) | Client-side architecture |
| [Deployment](docs/DEPLOYMENT.md) | GitHub Pages + CI/CD setup |
| [Developer Guide](docs/DEVELOPER_GUIDE.md) | Development environment and contribution guide |
| [Testing](docs/TESTING.md) | Test suite documentation |
| [Security](docs/SECURITY.md) | Security model and practices |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [Runbooks](docs/RUNBOOKS.md) | Operational procedures |
| [Lessons Learned](docs/LESSONS_LEARNED.md) | Project insights and standards |

---

## Configuration

### Application Configuration (app.js)

```javascript
const APP_CONFIG = {
    siteName: 'WA Bill Tracker',
    siteUrl: 'https://wa-bill-tracker.org',
    cookieDuration: 90,           // Days to persist user data
    autoSaveInterval: 30000,      // Auto-save interval (ms)
    dataRefreshInterval: 3600000, // Data refresh check (ms)
    githubDataUrl: 'https://raw.githubusercontent.com/jeff-is-working/wa-bill-tracker/main/data/bills.json',
    sessionEnd: new Date('2026-03-12')  // Session end date
};
```

### Data Collection Configuration (fetch_all_bills.py)

```python
# API Configuration
BASE_URL = "https://wslwebservices.leg.wa.gov"
YEAR = 2026
SESSION = "2025-26"  # Biennial session identifier
DATA_DIR = Path("data")

# Request Configuration
TIMEOUT = 30          # Request timeout in seconds
RETRY_COUNT = 3       # Number of retry attempts
RETRY_DELAY = 5       # Delay between retries in seconds
```

### GitHub Actions Schedule

The deployment workflow runs:
- On every push to `main` branch
- Every 6 hours via cron schedule
- Manually via workflow dispatch

To modify the schedule, edit `.github/workflows/deploy.yml`:

```yaml
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
```

---

## Deployment

### GitHub Pages Deployment

1. **Enable GitHub Pages**
   - Go to Settings > Pages
   - Source: Deploy from a branch
   - Branch: main, / (root)

2. **Enable GitHub Actions**
   - Go to Actions tab
   - Click "I understand my workflows, go ahead and enable them"

3. **Verify Deployment**
   - Check Actions tab for workflow runs
   - Visit your GitHub Pages URL

### Custom Domain (Optional)

1. Add a `CNAME` file to the repository root with your domain
2. Configure DNS with your domain provider
3. Enable HTTPS in GitHub Pages settings

### Environment Variables

For enhanced functionality, set these repository secrets:

| Secret | Purpose | Required |
|--------|---------|----------|
| `GITHUB_TOKEN` | Auto-provided for Actions | No (automatic) |

---

## Adapting for Other States

This application can be adapted for any state legislature that provides a public API. Follow these steps:

### Step 1: Research Your State's API

Find your state legislature's data API:

| State | API Documentation |
|-------|-------------------|
| Washington | https://wslwebservices.leg.wa.gov/ |
| California | https://leginfo.legislature.ca.gov/faces/codes.xhtml |
| Texas | https://capitol.texas.gov/Home.aspx |
| New York | https://legislation.nysenate.gov/static/docs/html/ |

Many states use LegiScan as an aggregator: https://legiscan.com/legiscan

### Step 2: Fork and Clone

```bash
# Fork via GitHub UI, then clone your fork
git clone https://github.com/YOUR_USERNAME/wa-bill-tracker.git
cd wa-bill-tracker

# Rename for your state
mv wa-bill-tracker ca-bill-tracker  # Example for California
```

### Step 3: Update Configuration

**app.js** - Update these values:

```javascript
const APP_CONFIG = {
    siteName: 'CA Bill Tracker',  // Your state
    siteUrl: 'https://YOUR_USERNAME.github.io/ca-bill-tracker',
    // ... update session end date for your state
    sessionEnd: new Date('2026-XX-XX')  // Your state's session end
};
```

**fetch_all_bills.py** - Replace API integration:

```python
# Update for your state's API
BASE_URL = "https://your-state-api.gov"
YEAR = 2026
SESSION = "2025-2026"

# Update bill number ranges for your state
def fetch_all_bill_numbers():
    bill_numbers = []
    # Adjust ranges based on your state's numbering
    for i in range(1, 5000):
        bill_numbers.append(f"AB {i}")  # Assembly Bills
        bill_numbers.append(f"SB {i}")  # Senate Bills
    return bill_numbers
```

### Step 4: Update Bill Types

Modify the bill type definitions in both `app.js` and `fetch_all_bills.py`:

```javascript
// Example for California
const BILL_TYPES = {
    'AB': 'Assembly Bills',
    'SB': 'Senate Bills',
    'ACA': 'Assembly Constitutional Amendments',
    'SCA': 'Senate Constitutional Amendments',
    'AJR': 'Assembly Joint Resolutions',
    'SJR': 'Senate Joint Resolutions',
    'ACR': 'Assembly Concurrent Resolutions',
    'SCR': 'Senate Concurrent Resolutions',
    'HR': 'House Resolutions',
    'SR': 'Senate Resolutions'
};
```

### Step 5: Update Status Mapping

Each state uses different status terminology:

```python
# Example status mapping for your state
STATUS_MAP = {
    'prefiled': ['Pre-filed', 'Filed'],
    'introduced': ['Introduced', 'Read first time'],
    'committee': ['In committee', 'Referred to'],
    'passed': ['Passed Assembly', 'Passed Senate', 'Chaptered'],
    'failed': ['Failed', 'Vetoed', 'Dead'],
    'enacted': ['Signed by Governor', 'Effective']
}
```

### Step 6: Update UI Elements

**index.html** - Update branding and filters:

```html
<h1>CA Legislative Tracker 2026</h1>

<!-- Update filter options -->
<div class="filter-options" id="typeFilters">
    <span class="filter-tag" data-filter="type" data-value="AB">Assembly Bills</span>
    <span class="filter-tag" data-filter="type" data-value="SB">Senate Bills</span>
    <!-- Add your state's bill types -->
</div>
```

### Step 7: Test and Deploy

```bash
# Run tests
pytest tests/ -v

# Fetch data
python scripts/fetch_all_bills.py

# Test locally
python -m http.server 8000

# Commit and push
git add .
git commit -m "feat: adapt for California legislature"
git push origin main
```

### State API Resources

| Resource | URL |
|----------|-----|
| LegiScan (All States) | https://legiscan.com/legiscan |
| OpenStates | https://openstates.org/ |
| National Conference of State Legislatures | https://www.ncsl.org/ |

---

## Session Updates

This application is designed for a single legislative session. When a new session begins, create a new instance.

### Starting a New Session

1. **Create New Repository**
   ```bash
   # Clone the template
   git clone https://github.com/jeff-is-working/wa-bill-tracker.git wa-bill-tracker-2027
   cd wa-bill-tracker-2027
   
   # Update remote
   git remote set-url origin https://github.com/YOUR_USERNAME/wa-bill-tracker-2027.git
   ```

2. **Update Session Configuration**
   
   **app.js:**
   ```javascript
   const APP_CONFIG = {
       // Update session end date
       sessionEnd: new Date('2027-04-XX')  // New session end
   };
   ```
   
   **fetch_all_bills.py:**
   ```python
   YEAR = 2027
   SESSION = "2027-28"  # New biennium
   ```

3. **Update UI Text**
   
   **index.html:**
   ```html
   <title>WA Legislative Tracker 2027</title>
   <h1>WA Legislative Tracker 2027</h1>
   ```

4. **Clear Old Data**
   ```bash
   rm -rf data/*.json
   python scripts/fetch_all_bills.py
   ```

5. **Update Documentation**
   - Update README badges
   - Update CHANGELOG
   - Archive previous session link

### Session Timeline (Washington State)

| Event | Typical Date |
|-------|--------------|
| Pre-filing begins | December 1 |
| Session starts | Second Monday in January |
| Session ends (short year) | ~60 days |
| Session ends (long year) | ~105 days |

### Archiving Previous Sessions

Consider keeping previous sessions available:

```
wa-bill-tracker-2024/  # Archived
wa-bill-tracker-2025/  # Archived  
wa-bill-tracker-2026/  # Current
```

---

## API Reference

### Washington State Legislature Web Services

**Base URL:** `https://wslwebservices.leg.wa.gov/`

**Documentation:** https://wslwebservices.leg.wa.gov/

### Key Endpoints

| Service | Endpoint | Description |
|---------|----------|-------------|
| Legislation | `/LegislationService.asmx` | Bill information |
| Sponsors | `/SponsorService.asmx` | Legislator information |
| Committees | `/CommitteeService.asmx` | Committee information |
| Sessions | `/SessionService.asmx` | Session information |

### SOAP Request Example

```xml
<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetLegislationByYear xmlns="http://wslwebservices.leg.wa.gov/">
      <year>2026</year>
    </GetLegislationByYear>
  </soap:Body>
</soap:Envelope>
```

### Response Data Structure

```json
{
  "BillId": "HB 1001",
  "Biennium": "2025-26",
  "BillNumber": 1001,
  "ShortDescription": "Bill title",
  "LongDescription": "Detailed description",
  "IntroducedDate": "2026-01-12T00:00:00",
  "PrimeSponsorID": 12345,
  "CurrentStatus": {
    "Status": "Introduced",
    "ActionDate": "2026-01-12T00:00:00"
  }
}
```

---

## Development

### Prerequisites

- Python 3.10 or higher
- Node.js 18+ (for E2E testing)
- Git

### Local Development Setup

```bash
# Clone repository
git clone https://github.com/jeff-is-working/wa-bill-tracker.git
cd wa-bill-tracker

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Fetch data
python scripts/fetch_all_bills.py

# Start local server
python -m http.server 8000
```

### Code Style

- **Python:** Follow PEP 8, use type hints
- **JavaScript:** Use JSDoc comments, ES6+ features
- **Commits:** Follow conventional commits format

```bash
# Format Python code
black scripts/

# Lint Python code
flake8 scripts/

# Type check
mypy scripts/
```

### Project Structure Guidelines

```
scripts/           # Python data collection
  fetch_all_bills.py
  __init__.py

tests/
  unit/           # Unit tests (pytest)
  integration/    # API tests
  e2e/            # Browser tests (Playwright)
  fixtures/       # Test data

data/             # Generated data (gitignored except bills.json)
docs/             # Additional documentation
```

---

## Testing

### Run All Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# With coverage
pytest tests/ -v --cov=scripts --cov-report=html
```

### Test Categories

| Type | Location | Purpose |
|------|----------|---------|
| Unit | `tests/unit/` | Test individual functions |
| Integration | `tests/integration/` | Test API connectivity |
| E2E | `tests/e2e/` | Test browser functionality |

### Writing Tests

```python
# tests/unit/test_example.py
import pytest
from scripts.fetch_all_bills import determine_topic

class TestDetermineTopic:
    def test_education_topic(self):
        """Test education keyword detection."""
        assert determine_topic("School funding bill") == "Education"
    
    @pytest.mark.parametrize("title,expected", [
        ("Tax reform", "Tax & Revenue"),
        ("Housing act", "Housing"),
    ])
    def test_multiple_topics(self, title, expected):
        """Test various topic classifications."""
        assert determine_topic(title) == expected
```

### Continuous Integration

Tests run automatically on:
- Every push to `main` or `develop`
- Every pull request to `main`

View results in the Actions tab.

---

## Contributing

Contributions are welcome! Please follow these guidelines:

### Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`pytest tests/ -v`)
5. Commit with conventional format (`git commit -m 'feat: add amazing feature'`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** feat, fix, docs, style, refactor, test, chore

### Code Review Checklist

- [ ] Tests pass
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No sample/placeholder data
- [ ] Commit messages follow format

### Reporting Issues

Use GitHub Issues with these labels:
- `bug` - Something isn't working
- `enhancement` - New feature request
- `documentation` - Documentation improvements
- `question` - Questions about usage

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2026 Jeff Records

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

## Acknowledgments

- [Washington State Legislature](https://leg.wa.gov/) for providing public API access
- [GitHub Pages](https://pages.github.com/) for free hosting
- [LegiScan](https://legiscan.com/) for multi-state legislative data resources
- [OpenStates](https://openstates.org/) for open legislative data advocacy

---

## Support

- **Issues:** [GitHub Issues](https://github.com/jeff-is-working/wa-bill-tracker/issues)
- **Discussions:** [GitHub Discussions](https://github.com/jeff-is-working/wa-bill-tracker/discussions)

---

**Built with care for Washington State civic engagement**

*Last updated: January 2026*
