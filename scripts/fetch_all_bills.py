
#!/usr/bin/env python3
"""
Washington State Legislature Bill Fetcher (2026 session via wa-leg-api)

- Sources bill data from the official Washington State Legislative Web Services,
  using the 'wa-leg-api' Python wrapper around the SOAP endpoints.
- Fetches all bills active in YEAR (2026), then enriches with status, sponsors,
  and hearings where available.
- Writes:
    1) Canonical dataset: data/bills.json
    2) Timestamped snapshot: data/sync/<YYYYMMDD-HHMMSS>_bills.json
    3) data/stats.json
    4) data/sync-log.json (rolling)

Security & resilience:
- No secrets required.
- Atomic file writes to prevent partial/corrupt files on failures.
- Light request throttling to be considerate of the public web service.

Install dependency once:
    pip install wa-leg-api
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# --- External API wrapper (official WA Legislature web services client) ---
# Docs: https://pypi.org/project/wa-leg-api/ and https://wa-leg-api.readthedocs.io/
from wa_leg_api import WaLegApiException
from wa_leg_api.legislation import (
    get_legislation_by_year,
    get_legislation,
    get_current_status,
    get_hearings,
    get_sponsors,
)

# -----------------------------------
# Configuration
# -----------------------------------
BASE_URL = "https://app.leg.wa.gov"        # For building legUrl
YEAR = 2026                                 # Session year to fetch
BIENNIUM = "2025-26"                        # Required by many endpoints
DATA_DIR = Path("data")
SNAPSHOT_DIR = DATA_DIR / "sync"

# Light politeness throttling between HTTP calls to the service (seconds)
THROTTLE_SECONDS = float(os.getenv("WALEG_THROTTLE_SECONDS", "0.10"))

# -----------------------------------
# Directory helpers
# -----------------------------------
def ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(exist_ok=True)

def ensure_sync_dir():
    """Ensure data/sync directory exists (for timestamped snapshots)"""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------
# Safe write helper (atomic)
# -----------------------------------
def write_json_atomic(target_path: Path, obj: dict):
    """
    Write JSON atomically: write to a temporary file in the same directory,
    then os.replace() to the target (atomic on POSIX and Windows).
    """
    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, target_path)

# -----------------------------------
# Utilities
# -----------------------------------
def to_list(maybe_list_or_item: Any, item_key: Optional[str] = None) -> List[Any]:
    """
    Normalize SOAP-ish structures (dict vs list vs None) into a list.
    Optionally pull a nested list under `item_key` if present.
    """
    if maybe_list_or_item is None:
        return []
    if item_key and isinstance(maybe_list_or_item, dict):
        maybe_list_or_item = maybe_list_or_item.get(item_key, [])
    if isinstance(maybe_list_or_item, list):
        return maybe_list_or_item
    return [maybe_list_or_item]

def safe_int(val: Any) -> Optional[int]:
    try:
        return int(val)
    except Exception:
        return None

def sleep_throttle():
    if THROTTLE_SECONDS > 0:
        time.sleep(THROTTLE_SECONDS)

# -----------------------------------
# Topic / committee / priority helpers (same heuristics as before)
# -----------------------------------
def determine_topic(title: str) -> str:
    title_lower = (title or "").lower()
    if any(w in title_lower for w in ["education", "school", "student", "teacher"]):
        return "Education"
    if any(w in title_lower for w in ["tax", "revenue", "budget", "fiscal"]):
        return "Tax & Revenue"
    if any(w in title_lower for w in ["housing", "rent", "tenant", "landlord"]):
        return "Housing"
    if any(w in title_lower for w in ["health", "medical", "hospital", "mental"]):
        return "Healthcare"
    if any(w in title_lower for w in ["environment", "climate", "energy", "pollution"]):
        return "Environment"
    if any(w in title_lower for w in ["transport", "road", "highway", "transit"]):
        return "Transportation"
    if any(w in title_lower for w in ["crime", "safety", "police", "justice"]):
        return "Public Safety"
    if any(w in title_lower for w in ["business", "commerce", "trade", "economy"]):
        return "Business"
    if any(w in title_lower for w in ["technology", "internet", "data", "privacy"]):
        return "Technology"
    return "General Government"

def determine_priority(title: str) -> str:
    title_lower = (title or "").lower()
    high_priority = [
        "emergency", "budget", "education funding", "public safety",
        "housing crisis", "climate", "healthcare access", "tax relief"
    ]
    low_priority = ["technical", "clarifying", "housekeeping", "minor", "study"]
    for k in high_priority:
        if k in title_lower:
            return "high"
    for k in low_priority:
        if k in title_lower:
            return "low"
    return "medium"

# -----------------------------------
# WA Legislature data fetch (via wa-leg-api)
# -----------------------------------
def fetch_legislation_for_year(year: int) -> List[Dict]:
    """
    Fetch all bills active in the given year (summary list).
    Returns a list of "legislation" summary dicts as provided by wa-leg-api.
    """
    # The wrapper returns a dict; shape depends on the SOAP result.
    # We normalize to a list of items under common keys.
    data = get_legislation_by_year(year)  # may raise WaLegApiException
    # Common shapes seen: {'ArrayOfLegislation': {'Legislation': [ ... ]}}
    # Or {'Legislation': [ ... ]}, or a single dict.
    items = []
    if isinstance(data, dict):
        if "ArrayOfLegislation" in data:
            items = to_list(data.get("ArrayOfLegislation"), "Legislation")
        elif "Legislation" in data:
            items = to_list(data.get("Legislation"))
        else:
            items = to_list(data)
    else:
        items = to_list(data)
    return items

def enrich_bill_with_status(bill_number_int: int) -> Tuple[str, Optional[str]]:
    """
    Fetch current status for bill (string) and a best-effort introduced date (YYYY-MM-DD if derivable).
    Returns (status, introduced_date_str or None).
    """
    try:
        sleep_throttle()
        status_data = get_current_status(BIENNIUM, bill_number_int)  # may be dict with 'Status', 'ActionDate'
        # Shape: { 'BillId': '...', 'Status': '...', 'ActionDate': '...'} (per service docs)
        status = None
        introduced = None
        if isinstance(status_data, dict):
            status = status_data.get("Status")
            # The service returns the *current* action date. Introduced date is not always present here.
            # We'll leave introduced None unless present explicitly in detailed calls.
        return status or "unknown", introduced
    except WaLegApiException:
        return "unknown", None
    except Exception:
        return "unknown", None

def fetch_sponsors_for_bill(bill_id: str) -> List[str]:
    """Return list of sponsor names for a bill ('Primary' first if identifiable)."""
    try:
        sleep_throttle()
        sponsor_data = get_sponsors(BIENNIUM, bill_id)  # list/dict -> normalize
        sponsors = []
        # Common SOAP shape: {'ArrayOfSponsor': {'Sponsor': [{'Name': '...','Title':'Primary'}, ...]}}
        items = []
        if isinstance(sponsor_data, dict):
            if "ArrayOfSponsor" in sponsor_data:
                items = to_list(sponsor_data.get("ArrayOfSponsor"), "Sponsor")
            elif "Sponsor" in sponsor_data:
                items = to_list(sponsor_data.get("Sponsor"))
            else:
                items = to_list(sponsor_data)
        else:
            items = to_list(sponsor_data)

        # Prefer primary sponsor first if we can identify; otherwise preserve order.
        primary = [x.get("Name") for x in items if isinstance(x, dict) and str(x.get("Title", "")).lower() == "primary"]
        others = [x.get("Name") for x in items if isinstance(x, dict) and str(x.get("Title", "")).lower() != "primary"]
        sponsors = [s for s in (primary + others) if s]
        return sponsors
    except WaLegApiException:
        return []
    except Exception:
        return []

def fetch_hearings_for_bill(bill_number_int: int) -> List[Dict]:
    """
    Get hearings for the bill (if any), normalized into:
        {"date": "YYYY-MM-DD", "committee": "...", "type": "...", "location": "..."}
    """
    try:
        sleep_throttle()
        hdata = get_hearings(BIENNIUM, bill_number_int)
        hearings = []
        # Expected shape: {'ArrayOfHearing': {'Hearing': [ { 'CommitteeMeeting': {... 'Date': '...','Room':...}}...]}}
        if isinstance(hdata, dict):
            if "ArrayOfHearing" in hdata:
                items = to_list(hdata.get("ArrayOfHearing"), "Hearing")
            elif "Hearing" in hdata:
                items = to_list(hdata.get("Hearing"))
            else:
                items = to_list(hdata)
        else:
            items = to_list(hdata)

        for h in items:
            if not isinstance(h, dict):
                continue
            cm = h.get("CommitteeMeeting", {}) if isinstance(h.get("CommitteeMeeting", {}), dict) else {}
            dt = cm.get("Date")
            date_str = None
            if dt:
                try:
                    # SOAP often returns "YYYY-MM-DDTHH:MM:SS"
                    date_str = dt.split("T")[0]
                except Exception:
                    date_str = None
            committee = None
            # Some payloads include 'Committees' collection; otherwise 'Agency' + maybe committee name elsewhere.
            committees_field = cm.get("Committees")
            if isinstance(committees_field, dict):
                # Could be {'Committee': [{'Name':'...'}, ...]}
                committee_list = to_list(committees_field.get("Committee"))
                names = [c.get("Name") for c in committee_list if isinstance(c, dict) and c.get("Name")]
                committee = ", ".join(names) if names else None
            # Fallbacks
            committee = committee or cm.get("Agency") or "unknown"
            hearings.append({
                "date": date_str or "",
                "committee": committee,
                "type": h.get("HearingTypeDescription") or h.get("HearingType") or "",
                "location": " ".join(filter(None, [cm.get("Building"), cm.get("Room") or ""])).strip()
            })
        return hearings
    except WaLegApiException:
        return []
    except Exception:
        return []

def normalize_legislation_item(item: Dict) -> Dict:
    """
    Convert a WA Legislation summary item into our internal 'bill' record format.
    We do an additional per-bill enrichment for status, sponsors, and hearings.
    """
    # Heuristics for numbering fields present across different calls
    display_number = item.get("DisplayNumber")
    bill_number_int = safe_int(item.get("BillNumber"))
    short_type = (item.get("ShortLegislationType") or "").strip()  # e.g., 'HB', 'SB', 'HJR'
    bill_id = item.get("BillId")  # Often 'HB 1001' etc.

    # Compose "number" in the canonical style (e.g., "HB 1001")
    if display_number:
        number = display_number
    elif short_type and bill_number_int is not None:
        number = f"{short_type} {bill_number_int}"
    elif bill_id:
        number = bill_id
    else:
        # If we truly cannot form a displayable number, skip this item later
        number = None

    # Basic, conservative fields available in summary
    title = item.get("Title") or item.get("LongTitle") or item.get("ShortTitle") or item.get("Description") or ""
    # `get_legislation` (detailed) often has richer fields; we avoid calling it per-bill unless necessary.

    # Enrichment: status + introduced date (best effort)
    status, introduced_date = ("unknown", None)
    if bill_number_int is not None:
        s, introduced = enrich_bill_with_status(bill_number_int)
        status, introduced_date = s, introduced

    # Enrichment: sponsors
    sponsors = fetch_sponsors_for_bill(bill_id or number or "")
    sponsor_str = sponsors[0] if sponsors else ""

    # Enrichment: hearings
    hearings = fetch_hearings_for_bill(bill_number_int) if bill_number_int is not None else []

    # Topic/Priority
    topic = determine_topic(title)
    priority = determine_priority(title)

    # Committee (if any hearings, take the most recent committee name; else unknown)
    committee = hearings[0]["committee"] if hearings else "unknown"

    # Build record
    record = {
        "id": (number or "").replace(" ", ""),
        "number": number or (bill_id or ""),
        "title": title,
        "sponsor": sponsor_str,
        "description": f"A bill relating to {title.lower()}" if title else "",
        "status": status or "unknown",
        "committee": committee or "unknown",
        "priority": priority,
        "topic": topic,
        "introducedDate": introduced_date or "",   # if unknown, keep empty string to maintain schema
        "lastUpdated": datetime.now().isoformat(),
        "legUrl": f"{BASE_URL}/billsummary?BillNumber={bill_number_int}&Year={YEAR}" if bill_number_int else "",
        "hearings": hearings,
    }
    return record

def fetch_and_build_bills(year: int) -> List[Dict]:
    """
    High-level function that:
      1) Retrieves all legislation summary items for the given year
      2) Normalizes + enriches each into our canonical 'bill' record
    """
    items = fetch_legislation_for_year(year)
    bills: List[Dict] = []
    for item in items:
        try:
            record = normalize_legislation_item(item if isinstance(item, dict) else {})
            # Drop items we could not assign a number/id to (extremely rare)
            if record["number"]:
                bills.append(record)
        except Exception:
            # Continue on individual item failures
            continue
    return bills

# -----------------------------------
# Persistence (same as your previous version)
# -----------------------------------
def save_bills_data(bills: List[Dict]) -> Dict:
    """
    Save bills data to JSON file and a timestamped snapshot for quick restore.
    - Canonical: data/bills.json
    - Snapshot:  data/sync/<YYYYMMDD-HHMMSS>_bills.json
    Uses atomic writes for both.
    """
    # Sort bills by number (type + numeric)
    def sort_key(b: Dict) -> Tuple[str, int]:
        parts = (b.get("number") or "").split()
        t = parts[0] if parts else ""
        n = 0
        if len(parts) > 1:
            try:
                n = int(parts[1])
            except Exception:
                n = 0
        return (t, n)

    bills.sort(key=sort_key)

    data = {
        "lastSync": datetime.now().isoformat(),
        "sessionYear": YEAR,
        "sessionStart": "2026-01-12",   # Adjust if you prefer to compute dynamically
        "sessionEnd":   "2026-03-12",   # Adjust as above
        "totalBills": len(bills),
        "bills": bills,
        "metadata": {
            "source": "Washington State Legislature",
            "updateFrequency": "daily",
            "dataVersion": "2.0.0",
            "includesRevived": True,
            "billTypes": ["HB", "SB", "HJR", "SJR", "HJM", "SJM", "HCR", "SCR", "I", "R"],
            "biennium": BIENNIUM,
        },
    }

    ensure_data_dir()
    ensure_sync_dir()

    # 1) Canonical file
    data_file = DATA_DIR / "bills.json"
    write_json_atomic(data_file, data)

    # 2) Timestamped snapshot
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot_file = SNAPSHOT_DIR / f"{ts}_bills.json"
    write_json_atomic(snapshot_file, data)

    print(f"✅ Saved {len(bills)} bills to {data_file}")
    print(f"🗂️ Snapshot created at {snapshot_file}")
    return data

def create_sync_log(bills_count: int, new_count: int = 0, status: str = "success"):
    """Create sync log for monitoring"""
    log = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "billsCount": bills_count,
        "newBillsAdded": new_count,
        "nextSync": (datetime.now() + timedelta(hours=6)).isoformat()
    }
    log_file = DATA_DIR / "sync-log.json"

    # Load existing logs
    logs = []
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            logs = data.get('logs', [])

    # Add new log entry (keep last 100 entries)
    logs.insert(0, log)
    logs = logs[:100]

    write_json_atomic(log_file, {"logs": logs})
    print(f"📝 Sync log updated: {status} - {bills_count} bills, {new_count} new")

def load_existing_data() -> Optional[Dict]:
    """Load existing bills data if it exists"""
    data_file = DATA_DIR / "bills.json"
    if data_file.exists():
        with open(data_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def restore_latest_snapshot() -> Optional[Path]:
    """
    Restore the most recent snapshot into data/bills.json.
    Call this manually if you need to roll back to the last good state.
    """
    ensure_sync_dir()
    snapshots = sorted(SNAPSHOT_DIR.glob("*_bills.json"))
    if not snapshots:
        print("ℹ️ No snapshots found; nothing to restore.")
        return None

    latest = snapshots[-1]
    target = DATA_DIR / "bills.json"

    with open(latest, 'r', encoding='utf-8') as src:
        data = json.load(src)
    write_json_atomic(target, data)

    print(f"♻️ Restored {latest.name} → {target}")
    return latest

# -----------------------------------
# Stats (same as your previous version)
# -----------------------------------
def create_stats_file(bills: List[Dict]):
    """Create comprehensive statistics file"""
    stats = {
        "generated": datetime.now().isoformat(),
        "totalBills": len(bills),
        "byStatus": {},
        "byCommittee": {},
        "byPriority": {},
        "byTopic": {},
        "bySponsor": {},
        "byType": {},
        "recentlyUpdated": 0,
        "updatedToday": 0,
        "upcomingHearings": 0,
        "billsWithHearings": 0
    }

    today = datetime.now().date()
    for bill in bills:
        stats['byStatus'][bill.get('status', 'unknown')] = stats['byStatus'].get(bill.get('status', 'unknown'), 0) + 1
        stats['byCommittee'][bill.get('committee', 'unknown')] = stats['byCommittee'].get(bill.get('committee', 'unknown'), 0) + 1
        stats['byPriority'][bill.get('priority', 'unknown')] = stats['byPriority'].get(bill.get('priority', 'unknown'), 0) + 1
        stats['byTopic'][bill.get('topic', 'unknown')] = stats['byTopic'].get(bill.get('topic', 'unknown'), 0) + 1
        stats['bySponsor'][bill.get('sponsor', 'unknown')] = stats['bySponsor'].get(bill.get('sponsor', 'unknown'), 0) + 1

        bill_type = (bill.get('number') or 'unknown').split()[0] if ' ' in (bill.get('number') or '') else 'unknown'
        stats['byType'][bill_type] = stats['byType'].get(bill_type, 0) + 1

        try:
            last_updated = datetime.fromisoformat(bill.get('lastUpdated', ''))
            days_diff = (datetime.now() - last_updated).days
            if days_diff < 1:
                stats['recentlyUpdated'] += 1
            if last_updated.date() == today:
                stats['updatedToday'] += 1
        except Exception:
            pass

        hearings = bill.get('hearings', [])
        if hearings:
            stats['billsWithHearings'] += 1
        for hearing in hearings:
            try:
                hdate = hearing.get('date')
                if not hdate:
                    continue
                d = datetime.strptime(hdate, '%Y-%m-%d').date()
                if 0 <= (d - today).days <= 7:
                    stats['upcomingHearings'] += 1
            except Exception:
                pass

    # Top sponsors by count
    stats['topSponsors'] = sorted(stats['bySponsor'].items(), key=lambda x: x[1], reverse=True)[:10]

    stats_file = DATA_DIR / "stats.json"
    write_json_atomic(stats_file, stats)
    print(f"📊 Statistics file updated with {len(stats['byStatus'])} statuses, {len(stats['byCommittee'])} committees")

# -----------------------------------
# Main
# -----------------------------------
def main():
    print(f"🚀 WA Legislature Bill Fetcher (wa-leg-api) - {datetime.now()}")
    print("=" * 60)

    ensure_data_dir()
    ensure_sync_dir()

    # Load existing data for merge (if you want to preserve between runs)
    existing_data = load_existing_data()
    existing_bills: Dict[str, Dict] = {}
    if existing_data:
        existing_bills = {bill['id']: bill for bill in existing_data.get('bills', [])}
        print(f"📚 Loaded {len(existing_bills)} existing bills")

    # 1) Fetch bills for YEAR via official service wrapper
    print(f"📥 Fetching legislation active in {YEAR} from WA Legislative Web Services...")
    try:
        summary_items = fetch_legislation_for_year(YEAR)
    except WaLegApiException as e:
        print(f"❌ Error fetching legislation list: {e}")
        create_sync_log(0, 0, status="failed")
        return

    # 2) Normalize + enrich each bill
    print("🔎 Enriching items with status, sponsors, and hearings...")
    all_bills = fetch_and_build_bills(YEAR)

    # 3) Track new/updated vs existing
    new_bills: List[Dict] = []
    updated_bills: List[Dict] = []
    for bill in all_bills:
        if bill['id'] not in existing_bills:
            new_bills.append(bill)
        elif bill != existing_bills[bill['id']]:
            updated_bills.append(bill)

    print(f" ✨ Found {len(new_bills)} new bills")
    print(f" 🔄 Updated {len(updated_bills)} existing bills")

    # 4) Merge & save
    for bill in all_bills:
        existing_bills[bill['id']] = bill
    final_bills = list(existing_bills.values())

    save_bills_data(final_bills)
    create_stats_file(final_bills)
    create_sync_log(len(final_bills), len(new_bills), "success")

    print("=" * 60)
    print("✅ Successfully updated database:")
    print(f" - Total bills: {len(final_bills)}")
    print(f" - New bills: {len(new_bills)}")
    print(f" - Updated bills: {len(updated_bills)}")
    print(f"🏁 Update complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
