
#!/usr/bin/env python3
"""
WA Legislature - Current Bills & Status (2026)
Standard-library-only client for Washington State Legislative Web Services.

Data sources:
- GetLegislationByYear(2026): enumerate bills active in 2026
- GetCurrentStatus( biennium="2025-26", billNumber=<int> ): current status for each bill

Writes:
- data/bills.json (canonical)
- data/sync/<YYYYMMDD-HHMMSS>_bills.json (timestamped snapshot)

Environment (optional):
- WALEG_THROTTLE_SECONDS: politeness delay between HTTP calls (default: 0.10)
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET

# -----------------------------
# Configuration
# -----------------------------
YEAR = 2026
BIENNIUM = "2025-26"
SERVICE_BASE = "https://wslwebservices.leg.wa.gov/LegislationService.asmx"
LEG_SUMMARY_URL = "https://app.leg.wa.gov/billsummary?BillNumber={num}&Year={year}"

DATA_DIR = Path("data")
SNAPSHOT_DIR = DATA_DIR / "sync"

THROTTLE_SECONDS = float(os.getenv("WALEG_THROTTLE_SECONDS", "0.10"))
HTTP_TIMEOUT = 60  # seconds

# -----------------------------
# HTTP helpers (standard lib)
# -----------------------------
def http_get_xml(endpoint: str, params: Dict[str, Any]) -> ET.Element:
    """
    Perform an HTTP GET to an LWS endpoint with query params and parse the XML response.
    Uses standard library only (urllib + xml.etree).
    """
    qs = urlencode(params)
    url = f"{endpoint}?{qs}"
    req = Request(url, headers={"User-Agent": "wa-leg-status-bot/1.0"})
    with urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        content = resp.read()
    try:
        return ET.fromstring(content)
    except ET.ParseError as e:
        # For troubleshooting, you might want to log content to a temp file
        raise RuntimeError(f"XML parse error at {endpoint} with params {params}: {e}") from e

def sleep_throttle():
    if THROTTLE_SECONDS > 0:
        time.sleep(THROTTLE_SECONDS)

# -----------------------------
# XML utilities (namespace-agnostic)
# -----------------------------
def xml_find_text(elem: ET.Element, tag_suffix: str, default: Optional[str] = None) -> Optional[str]:
    """
    Find direct child text where child's tag endswith(tag_suffix).
    """
    for child in list(elem):
        if child.tag.endswith(tag_suffix):
            return (child.text or "").strip() if child.text else default
    return default

def xml_iter_children(elem: ET.Element, tag_suffix: str) -> List[ET.Element]:
    """
    Return all descendant elements whose tag ends with tag_suffix.
    """
    matches = []
    for e in elem.iter():
        if e.tag.endswith(tag_suffix):
            matches.append(e)
    return matches

# -----------------------------
# LWS calls (no external libs)
# -----------------------------
def get_legislation_by_year(year: int) -> List[ET.Element]:
    """
    Call GetLegislationByYear and return a list of <Legislation> elements (namespace-agnostic).
    Endpoint (HTTP GET returns XML):
      https://wslwebservices.leg.wa.gov/LegislationService.asmx/GetLegislationByYear?year=YYYY
    """
    root = http_get_xml(f"{SERVICE_BASE}/GetLegislationByYear", {"year": year})
    # Expect an array root wrapping multiple <Legislation> items, but be flexible.
    items = xml_iter_children(root, "Legislation")
    return items

def get_current_status(biennium: str, bill_number: int) -> Dict[str, Optional[str]]:
    """
    Call GetCurrentStatus and return a dict with 'Status' and 'ActionDate' (best effort).
    Endpoint (HTTP GET returns XML):
      https://wslwebservices.leg.wa.gov/LegislationService.asmx/GetCurrentStatus?biennium=2005-06&billNumber=1234
    """
    root = http_get_xml(f"{SERVICE_BASE}/GetCurrentStatus", {"biennium": biennium, "billNumber": bill_number})
    # Shape (root): <LegislativeStatus> with children: Status, ActionDate, etc.
    status = xml_find_text(root, "Status", default="unknown")
    action_date = xml_find_text(root, "ActionDate", default=None)
    return {"Status": status, "ActionDate": action_date}

# -----------------------------
# Transform/normalize
# -----------------------------
def build_bill_record(item: ET.Element) -> Optional[Dict[str, Any]]:
    """
    Convert a <Legislation> element to our canonical record and enrich with current status.
    """
    # Prefer DisplayNumber (e.g., "HB 1001"); otherwise compose from ShortLegislationType + BillNumber.
    display_number = xml_find_text(item, "DisplayNumber")
    bill_number_text = xml_find_text(item, "BillNumber")
    bill_number_int = None
    if bill_number_text and bill_number_text.isdigit():
        bill_number_int = int(bill_number_text)

    short_type = xml_find_text(item, "ShortLegislationType")
    bill_id = xml_find_text(item, "BillId")  # Sometimes includes "HB 1001"
    title = (
        xml_find_text(item, "Title")
        or xml_find_text(item, "LongTitle")
        or xml_find_text(item, "ShortTitle")
        or xml_find_text(item, "Description")
        or ""
    )

    if display_number:
        number = display_number
    elif short_type and bill_number_int is not None:
        number = f"{short_type} {bill_number_int}"
    elif bill_id:
        number = bill_id
    else:
        # If we truly cannot derive a number, skip the record
        return None

    # Enrich with current status (best effort)
    status = "unknown"
    try:
        if bill_number_int is not None:
            sleep_throttle()
            sdata = get_current_status(BIENNIUM, bill_number_int)
            status = (sdata.get("Status") or "unknown").strip()
    except Exception:
        status = "unknown"

    record: Dict[str, Any] = {
        "id": number.replace(" ", ""),
        "number": number,
        "title": title,
        "status": status,
        "lastUpdated": datetime.now().isoformat(),
        "legUrl": LEG_SUMMARY_URL.format(num=bill_number_int if bill_number_int is not None else "", year=YEAR),
    }
    return record

# -----------------------------
# Persistence (atomic)
# -----------------------------
def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

def write_json_atomic(path: Path, payload: Dict[str, Any]):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def save_outputs(bills: List[Dict[str, Any]]):
    data = {
        "lastSync": datetime.now().isoformat(),
        "sessionYear": YEAR,
        "biennium": BIENNIUM,
        "totalBills": len(bills),
        "bills": bills,
        "metadata": {
            "source": "Washington State Legislative Web Services",
            "endpoint": SERVICE_BASE,
        },
    }
    ensure_dirs()
    canonical = DATA_DIR / "bills.json"
    write_json_atomic(canonical, data)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot = SNAPSHOT_DIR / f"{ts}_bills.json"
    write_json_atomic(snapshot, data)

    print(f"✅ Wrote {len(bills)} bills")
    print(f"  - Canonical: {canonical}")
    print(f"  - Snapshot : {snapshot}")

# -----------------------------
# Main
# -----------------------------
def main():
    print(f"🚀 Fetching WA bills for {YEAR} and current status (biennium {BIENNIUM})")
    try:
        items = get_legislation_by_year(YEAR)
    except Exception as e:
        raise SystemExit(f"Failed to fetch legislation list for {YEAR}: {e}")

    bills: List[Dict[str, Any]] = []
    for i, item in enumerate(items, 1):
        try:
            rec = build_bill_record(item)
            if rec:
                bills.append(rec)
        except Exception as e:
            # Continue on individual failures
            print(f"⚠️  Skipping item {i} due to error: {e}")

    # Sort for stability: by prefix (HB/SB/…) then number (if available)
    def sort_key(b: Dict[str, Any]) -> Tuple[str, int]:
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
    save_outputs(bills)

if __name__ == "__main__":
    main()
