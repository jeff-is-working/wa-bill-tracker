# Operational Runbooks

> Step-by-step procedures for common operational tasks

---

## Table of Contents

1. [Data Refresh Procedures](#data-refresh-procedures)
2. [Deployment Procedures](#deployment-procedures)
3. [Incident Response](#incident-response)
4. [Session Transition](#session-transition)
5. [Monitoring Checks](#monitoring-checks)
6. [Legislative Cutoff Dates](#legislative-cutoff-dates)

---

## Data Refresh Procedures

### Runbook: Manual Incremental Sync

**When to use:** Regular data updates, troubleshooting stale data

**Steps:**

1. Navigate to GitHub Actions:
   ```
   https://github.com/jeff-is-working/wa-bill-tracker/actions/workflows/fetch-data.yml
   ```

2. Click "Run workflow" dropdown

3. Select options:
   - Branch: `main`
   - Mode: `incremental`

4. Click "Run workflow"

5. Monitor execution:
   - Watch for green checkmark
   - Review logs if red X appears

6. Verify update:
   ```bash
   curl -s https://wa-bill-tracker.org/data/sync-log.json | jq '.logs[0]'
   ```

**Expected duration:** 5-10 minutes

---

### Runbook: Manual Full Refresh

**When to use:** Weekly maintenance, data corruption recovery, session start

**Steps:**

1. Navigate to GitHub Actions:
   ```
   https://github.com/jeff-is-working/wa-bill-tracker/actions/workflows/fetch-data.yml
   ```

2. Click "Run workflow" dropdown

3. Select options:
   - Branch: `main`
   - Mode: `full`

4. Click "Run workflow"

5. Monitor execution (longer than incremental)

6. Verify results:
   ```bash
   # Check bill count
   curl -s https://wa-bill-tracker.org/data/bills.json | jq '.totalBills'

   # Check sync status
   curl -s https://wa-bill-tracker.org/data/sync-log.json | jq '.logs[0]'
   ```

**Expected duration:** 30-60 minutes

---

### Runbook: Local Data Fetch

**When to use:** Development, debugging, testing changes

**Steps:**

1. Clone repository:
   ```bash
   git clone https://github.com/jeff-is-working/wa-bill-tracker.git
   cd wa-bill-tracker
   ```

2. Install dependencies:
   ```bash
   pip install requests
   ```

3. Create data directory:
   ```bash
   mkdir -p data debug
   ```

4. Run fetch script:
   ```bash
   # Full fetch
   python scripts/fetch_all_bills.py

   # OR incremental
   python scripts/fetch_bills_incremental.py
   ```

5. Validate output:
   ```bash
   python scripts/validate_bills_json.py
   ```

6. Review results:
   ```bash
   cat data/bills.json | jq '.totalBills'
   cat data/sync-log.json | jq '.logs[0]'
   ```

---

## Deployment Procedures

### Runbook: Standard Deployment

**When to use:** After code changes, regular updates

**Steps:**

1. Make changes locally

2. Test locally:
   ```bash
   python -m pytest tests/ -v
   python -m http.server 8000
   # Test in browser
   ```

3. Commit changes:
   ```bash
   git add .
   git commit -m "feat: description of changes"
   ```

4. Push to main:
   ```bash
   git push origin main
   ```

5. Monitor deployment:
   - Go to Actions tab
   - Watch "Deploy to GitHub Pages" workflow

6. Verify deployment:
   ```bash
   curl -I https://wa-bill-tracker.org
   ```

**Expected duration:** 2-5 minutes

---

### Runbook: Rollback Deployment

**When to use:** Bad deployment, broken functionality

**Steps:**

1. Identify last good commit:
   ```bash
   git log --oneline -10
   ```

2. Revert changes:
   ```bash
   # Revert last commit
   git revert HEAD

   # OR revert to specific commit
   git revert <bad-commit-hash>
   ```

3. Push revert:
   ```bash
   git push origin main
   ```

4. Monitor automatic deployment

5. Verify site is working:
   ```bash
   curl -s https://wa-bill-tracker.org | head -20
   ```

---

### Runbook: Emergency Data Restore

**When to use:** Corrupted bills.json, data loss

**Steps:**

1. Check sync log for last good state:
   ```bash
   cat data/sync-log.json | jq '.logs'
   ```

2. Find last good commit:
   ```bash
   git log --oneline data/bills.json
   ```

3. Restore from git history:
   ```bash
   git checkout <commit-hash> -- data/bills.json
   git checkout <commit-hash> -- data/manifest.json
   git checkout <commit-hash> -- data/stats.json
   ```

4. Commit restore:
   ```bash
   git add data/
   git commit -m "fix: restore data from <commit-hash>"
   git push origin main
   ```

5. Verify restoration:
   ```bash
   python scripts/validate_bills_json.py
   ```

---

## Incident Response

### Runbook: Site Down

**Severity:** High

**Steps:**

1. **Assess** (1 min):
   ```bash
   curl -I https://wa-bill-tracker.org
   curl -I https://jeff-is-working.github.io/wa-bill-tracker/
   ```

2. **Identify cause:**
   - GitHub Pages issue → Check [GitHub Status](https://githubstatus.com)
   - DNS issue → Check Cloudflare dashboard
   - Deployment issue → Check GitHub Actions

3. **Mitigate:**
   - If GitHub down: Wait for GitHub resolution
   - If DNS issue: Verify Cloudflare records
   - If deployment failed: Rollback to last good commit

4. **Verify resolution:**
   ```bash
   curl -I https://wa-bill-tracker.org
   ```

5. **Document:** Note incident in sync log or issue

---

### Runbook: Data Sync Failure

**Severity:** Medium

**Steps:**

1. **Check workflow status:**
   ```bash
   gh run list --workflow=fetch-data.yml --limit 5
   ```

2. **Review logs:**
   ```bash
   gh run view <failed-run-id> --log
   ```

3. **Identify cause:**
   - API timeout → Retry
   - Parse error → Check API response
   - Validation failure → Check data integrity

4. **Resolve:**
   - Retry workflow manually
   - Fix script if bug found
   - Run full refresh if needed

5. **Verify:**
   ```bash
   curl -s https://wa-bill-tracker.org/data/sync-log.json | jq '.logs[0]'
   ```

---

### Runbook: API Unavailable

**Severity:** Medium (temporary)

**Steps:**

1. **Verify API status:**
   ```bash
   curl -I https://wslwebservices.leg.wa.gov
   ```

2. **Check for maintenance:**
   - Visit WA Legislature website
   - Check for announcements

3. **Wait and retry:**
   - API outages usually temporary
   - Retry after 1 hour

4. **If prolonged:**
   - Site continues serving cached data
   - Monitor for API restoration
   - Document in sync log

---

## Session Transition

### Runbook: New Legislative Session Setup

**When to use:** Start of new biennium or session year

**Steps:**

1. **Update configuration** in `scripts/fetch_all_bills.py`:
   ```python
   BIENNIUM = "2027-28"  # Update
   YEAR = 2027           # Update
   ```

2. **Update frontend** in `app.js`:
   ```javascript
   APP_CONFIG.sessionStart = '2027-01-13';  // Update
   APP_CONFIG.sessionEnd = '2027-04-25';    // Update
   APP_CONFIG.biennium = '2027-28';         // Update
   ```

3. **Update cutoff dates** in `app.js`:
   ```javascript
   APP_CONFIG.cutoffDates = [
       { date: '2027-02-XX', name: 'Policy Committee', ... },
       // Update all dates
   ];
   ```

4. **Clear old data** (optional):
   ```bash
   rm data/bills.json data/manifest.json data/stats.json
   ```

5. **Run full fetch:**
   ```bash
   python scripts/fetch_all_bills.py
   ```

6. **Test locally:**
   ```bash
   python -m http.server 8000
   # Verify in browser
   ```

7. **Commit and deploy:**
   ```bash
   git add .
   git commit -m "chore: update for 2027 session"
   git push origin main
   ```

---

### Runbook: Cutoff Date Updates

**When to use:** Legislative calendar changes, date corrections

**Steps:**

1. **Get official dates** from WA Legislature website

2. **Update** `APP_CONFIG.cutoffDates` in `app.js`:
   ```javascript
   cutoffDates: [
       {
           date: '2026-02-04',
           name: 'Policy Committee (Origin)',
           description: 'Bills must pass policy committee in house of origin',
           failsStatuses: ['prefiled', 'introduced']
       },
       // ... continue for all cutoffs
   ]
   ```

3. **Test cutoff logic locally:**
   - Verify bills show correct cutoff status
   - Check cutoff banner displays correctly

4. **Commit and deploy**

---

## Monitoring Checks

### Daily Health Check

**Schedule:** Daily (manual or automated)

```bash
#!/bin/bash
# daily_health_check.sh

echo "=== WA Bill Tracker Health Check ==="
echo "Date: $(date)"

# 1. Site accessibility
echo -n "Site status: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://wa-bill-tracker.org)
if [ "$HTTP_CODE" = "200" ]; then
    echo "OK ($HTTP_CODE)"
else
    echo "FAIL ($HTTP_CODE)"
fi

# 2. Data freshness
echo -n "Last sync: "
LAST_SYNC=$(curl -s https://wa-bill-tracker.org/data/sync-log.json | jq -r '.logs[0].timestamp')
echo "$LAST_SYNC"

# 3. Bill count
echo -n "Bill count: "
BILL_COUNT=$(curl -s https://wa-bill-tracker.org/data/bills.json | jq '.totalBills')
echo "$BILL_COUNT"

# 4. Recent workflow status
echo "Recent workflows:"
gh run list --repo jeff-is-working/wa-bill-tracker --limit 3

echo "=== Health Check Complete ==="
```

### Weekly Review Checklist

- [ ] Review sync log for errors
- [ ] Check bill count is reasonable
- [ ] Verify cutoff dates are correct
- [ ] Review GitHub Actions for failures
- [ ] Check SSL certificate status
- [ ] Monitor data file sizes

---

## Legislative Cutoff Dates

### 2026 Regular Session (60-day)

| Date | Cutoff | Bills Affected |
|------|--------|----------------|
| **Feb 4** | Policy committee (origin) | Prefiled, introduced |
| **Feb 9** | Fiscal committee (origin) | + committee |
| **Feb 17** | House of origin | + floor |
| **Feb 25** | Policy committee (opposite) | + passed_origin |
| **Mar 4** | Fiscal committee (opposite) | + opposite_committee |
| **Mar 6** | Opposite house | + opposite_floor |
| **Mar 12** | Sine die (session end) | All remaining |

### Cutoff Status Mapping

```javascript
// Bills that miss cutoff are marked with status
const cutoffMapping = {
    'Policy Committee (Origin)': ['prefiled', 'introduced'],
    'Fiscal Committee (Origin)': ['prefiled', 'introduced', 'committee'],
    'House of Origin': ['prefiled', 'introduced', 'committee', 'floor'],
    // ...
};
```

### Verifying Cutoff Logic

```javascript
// In browser console
const bill = APP_STATE.bills.find(b => b.id === 'HB1001');
console.log('Status:', bill.status);
console.log('Cutoff status:', getBillCutoffStatus(bill));
```

---

## Command Reference

### GitHub CLI Commands

```bash
# List workflows
gh workflow list

# Run workflow
gh workflow run fetch-data.yml -f mode=full

# View run
gh run view <run-id>

# View logs
gh run view <run-id> --log

# List runs
gh run list --workflow=fetch-data.yml --limit 10
```

### Data Validation Commands

```bash
# Validate JSON structure
python scripts/validate_bills_json.py

# Check bill count
cat data/bills.json | jq '.totalBills'

# Check last sync
cat data/sync-log.json | jq '.logs[0]'

# Find specific bill
cat data/bills.json | jq '.bills[] | select(.id=="HB1001")'
```

### Local Server Commands

```bash
# Python server
python -m http.server 8000

# Node server (if installed)
npx serve .
```

---

## Related Documentation

- [Deployment](DEPLOYMENT.md) - CI/CD details
- [Troubleshooting](TROUBLESHOOTING.md) - Issue resolution
- [API Integration](API_INTEGRATION.md) - API operations

---

*Last updated: February 2026*
