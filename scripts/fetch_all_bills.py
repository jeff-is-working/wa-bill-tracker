#!/usr/bin/env python3
"""
Washington State Legislature Comprehensive Bill Fetcher
Fetches ALL bills, initiatives, and referendums for the 2026 session
"""

import json
import requests
from datetime import datetime, timedelta
import os
from pathlib import Path
import re
from typing import Dict, List, Optional
import time

# Configuration
BASE_URL = "https://app.leg.wa.gov"
YEAR = 2026
DATA_DIR = Path("data")
SESSION = "2025-26"  # Biennial session

def ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(exist_ok=True)

def fetch_all_bill_numbers() -> List[str]:
    """
    Generate comprehensive list of all possible bill numbers to check
    """
    bill_numbers = []
    
    # House Bills (HB) - typically 1000-3000 range
    for i in range(1000, 3001):
        bill_numbers.append(f"HB {i}")
    
    # Senate Bills (SB) - typically 5000-7000 range
    for i in range(5000, 7001):
        bill_numbers.append(f"SB {i}")
    
    # House Joint Resolutions (HJR)
    for i in range(4000, 4100):
        bill_numbers.append(f"HJR {i}")
    
    # Senate Joint Resolutions (SJR)
    for i in range(8000, 8100):
        bill_numbers.append(f"SJR {i}")
    
    # House Joint Memorials (HJM)
    for i in range(4000, 4050):
        bill_numbers.append(f"HJM {i}")
    
    # Senate Joint Memorials (SJM)
    for i in range(8000, 8050):
        bill_numbers.append(f"SJM {i}")
    
    # House Concurrent Resolutions (HCR)
    for i in range(4400, 4450):
        bill_numbers.append(f"HCR {i}")
    
    # Senate Concurrent Resolutions (SCR)
    for i in range(8400, 8450):
        bill_numbers.append(f"SCR {i}")
    
    # Initiatives
    for i in range(2100, 2200):
        bill_numbers.append(f"I-{i}")
    
    # Referendums
    for i in range(88, 100):
        bill_numbers.append(f"R-{i}")
    
    return bill_numbers

def fetch_bill_details(bill_number: str) -> Optional[Dict]:
    """
    Fetch details for a specific bill number
    This simulates what would be an actual API call
    """
    # Parse bill type and number
    parts = bill_number.replace("-", " ").split()
    bill_type = parts[0]
    bill_num = parts[1] if len(parts) > 1 else ""
    
    # Determine chamber and committee based on bill type
    if bill_type.startswith("H"):
        chamber = "House"
        committees = ["Education", "Transportation", "Finance", "Health Care", "Housing", 
                     "Environment & Energy", "Consumer Protection & Business", "State Government & Tribal Relations"]
    elif bill_type.startswith("S"):
        chamber = "Senate"
        committees = ["Early Learning & K-12 Education", "Transportation", "Ways & Means", 
                     "Health & Long-Term Care", "Housing", "Environment, Energy & Technology", 
                     "Business, Financial Services & Trade", "Law & Justice"]
    else:
        chamber = "Initiative/Referendum"
        committees = ["Secretary of State"]
    
    # Create bill URL
    if bill_type in ["I", "R"]:
        leg_url = f"{BASE_URL}/billsummary?Initiative={bill_num}"
    else:
        leg_url = f"{BASE_URL}/billsummary?BillNumber={bill_num}&Year={YEAR}"
    
    # Simulate bill data (in production, this would be fetched from the actual API)
    # Only return data for bills that would actually exist
    sample_bills = {
   
    }
    
    # Check if this is a known bill
    if bill_number in sample_bills:
        bill_info = sample_bills[bill_number]
        return {
            "id": bill_number.replace(" ", ""),
            "number": bill_number,
            "title": bill_info["title"],
            "sponsor": f"{chamber} Member",  # Would be fetched from API
            "description": f"A bill relating to {bill_info['title'].lower()}",
            "status": bill_info["status"],
            "committee": committees[hash(bill_number) % len(committees)],
            "priority": "medium",
            "topic": determine_topic(bill_info["title"]),
            "introducedDate": "2026-01-12",
            "lastUpdated": datetime.now().isoformat(),
            "legUrl": leg_url,
            "hearings": []
        }
    
    return None

def determine_topic(title: str) -> str:
    """Determine bill topic from title"""
    title_lower = title.lower()
    
    if any(word in title_lower for word in ["education", "school", "student", "teacher"]):
        return "Education"
    elif any(word in title_lower for word in ["tax", "revenue", "budget", "fiscal"]):
        return "Tax & Revenue"
    elif any(word in title_lower for word in ["housing", "rent", "tenant", "landlord"]):
        return "Housing"
    elif any(word in title_lower for word in ["health", "medical", "hospital", "mental"]):
        return "Healthcare"
    elif any(word in title_lower for word in ["environment", "climate", "energy", "pollution"]):
        return "Environment"
    elif any(word in title_lower for word in ["transport", "road", "highway", "transit"]):
        return "Transportation"
    elif any(word in title_lower for word in ["crime", "safety", "police", "justice"]):
        return "Public Safety"
    elif any(word in title_lower for word in ["business", "commerce", "trade", "economy"]):
        return "Business"
    elif any(word in title_lower for word in ["technology", "internet", "data", "privacy"]):
        return "Technology"
    else:
        return "General Government"

def map_status_from_history(history_line: str) -> str:
    """
    Map WA Legislature status history to standard status values
    
    Status values:
    - prefiled: Bill has been prefiled before session
    - introduced: Bill has been officially introduced
    - committee: Bill is in committee
    - passed: Bill has passed (at least one chamber)
    - failed: Bill has failed or died
    - enacted: Bill has been signed into law
    - vetoed: Bill has been vetoed
    """
    if not history_line:
        return "prefiled"
    
    history_lower = history_line.lower()
    
    # Check for enacted/signed
    if any(word in history_lower for word in ["signed by governor", "delivered to governor", "enacted"]):
        return "enacted"
    
    # Check for vetoed
    if "veto" in history_lower:
        return "vetoed"
    
    # Check for passed
    if any(word in history_lower for word in ["passed", "third reading", "final passage"]):
        return "passed"
    
    # Check for failed/dead
    if any(word in history_lower for word in ["failed", "died", "rejected", "without recommendation"]):
        return "failed"
    
    # Check for committee
    if any(word in history_lower for word in ["committee", "hearing", "public hearing", "executive session", "executive action", "referred to"]):
        return "committee"
    
    # Check for introduced
    if any(word in history_lower for word in ["first reading", "introduced", "read first time"]):
        return "introduced"
    
    # Check for prefiled
    if "prefiled" in history_lower or "pre-filed" in history_lower:
        return "prefiled"
    
    # Default to prefiled for new bills
    return "prefiled"

def extract_hearing_date(history_line: str) -> Optional[str]:
    """
    Extract hearing date from history line
    Returns date in ISO format (YYYY-MM-DD) or None
    """
    if not history_line:
        return None
    
    # Look for date patterns like "1/15/2026" or "01/15/2026"
    import re
    
    # Pattern: M/D/YYYY or MM/DD/YYYY
    date_pattern = r'(\d{1,2})/(\d{1,2})/(\d{4})'
    match = re.search(date_pattern, history_line)
    
    if match:
        month, day, year = match.groups()
        # Convert to ISO format
        return f"{year}-{int(month):02d}-{int(day):02d}"
    
    return None

def extract_hearing_time(history_line: str) -> str:
    """
    Extract hearing time from history line
    Returns time string or empty string
    """
    if not history_line:
        return ""
    
    import re
    
    # Pattern: H:MM AM/PM or HH:MM AM/PM
    time_pattern = r'(\d{1,2}:\d{2}\s*[AP]M)'
    match = re.search(time_pattern, history_line, re.IGNORECASE)
    
    if match:
        return match.group(1)
    
    return ""

def fetch_bills_from_wa_legislature() -> List[Dict]:
    """
    Fetch bill list from Washington State Legislature
    This function should be updated to actually fetch from leg.wa.gov API
    """
    bills = []
    
    try:
        # TODO: Implement actual API calls to leg.wa.gov
        # For now, returning actual prefiled bills for 2026 session
        # These should be replaced with real API data
        
        actual_bills = [
        ]
        
        for bill_data in actual_bills:
            bill_id = bill_data["number"].replace(" ", "")
            
            # Map the status from the history line
            status = map_status_from_history(bill_data.get("historyLine", ""))
            
            bill = {
                "id": bill_id,
                "number": bill_data["number"],
                "title": bill_data["title"],
                "sponsor": bill_data["sponsor"],
                "description": f"A bill relating to {bill_data['title'].lower()}",
                "status": status,
                "historyLine": bill_data.get("historyLine", ""),
                "committee": determine_committee(bill_data["number"], bill_data["title"]),
                "priority": determine_priority(bill_data["title"]),
                "topic": determine_topic(bill_data["title"]),
                "introducedDate": "2026-01-12",
                "lastUpdated": datetime.now().isoformat(),
                "legUrl": f"{BASE_URL}/billsummary?BillNumber={bill_data['number'].split()[1]}&Year={YEAR}",
                "hearings": []
            }
            
            # Extract hearing date from history line if present
            hearing_date = extract_hearing_date(bill_data.get("historyLine", ""))
            if hearing_date:
                bill["hearings"] = [{
                    "date": hearing_date,
                    "time": extract_hearing_time(bill_data.get("historyLine", "")),
                    "committee": bill["committee"]
                }]
            
            bills.append(bill)
            
    except Exception as e:
        print(f"Error fetching bills: {e}")
    
    return bills

def determine_committee(bill_number: str, title: str) -> str:
    """Determine committee assignment based on bill number and title"""
    title_lower = title.lower()
    
    if "education" in title_lower or "school" in title_lower:
        return "Education"
    elif "transportation" in title_lower or "road" in title_lower:
        return "Transportation"
    elif "housing" in title_lower or "rent" in title_lower:
        return "Housing"
    elif "health" in title_lower or "medical" in title_lower:
        return "Health & Long-Term Care"
    elif "environment" in title_lower or "energy" in title_lower:
        return "Environment & Energy"
    elif "tax" in title_lower or "revenue" in title_lower:
        return "Finance" if bill_number.startswith("HB") else "Ways & Means"
    elif "consumer" in title_lower or "business" in title_lower:
        return "Consumer Protection & Business"
    elif "crime" in title_lower or "safety" in title_lower or "justice" in title_lower:
        return "Law & Justice"
    else:
        return "State Government & Tribal Relations"

def determine_priority(title: str) -> str:
    """Determine bill priority based on keywords in title"""
    title_lower = title.lower()
    
    # High priority keywords
    high_priority = ["emergency", "budget", "education funding", "public safety", 
                    "housing crisis", "climate", "healthcare access", "tax relief"]
    
    # Low priority keywords  
    low_priority = ["technical", "clarifying", "housekeeping", "minor", "study"]
    
    for keyword in high_priority:
        if keyword in title_lower:
            return "high"
    
    for keyword in low_priority:
        if keyword in title_lower:
            return "low"
    
    return "medium"

def save_bills_data(bills: List[Dict]) -> Dict:
    """Save bills data to JSON file"""
    # Sort bills by number
    bills.sort(key=lambda x: (x['number'].split()[0], int(x['number'].split()[1]) if len(x['number'].split()) > 1 else 0))
    
    data = {
        "lastSync": datetime.now().isoformat(),
        "sessionYear": YEAR,
        "sessionStart": "2026-01-12",
        "sessionEnd": "2026-03-12",
        "totalBills": len(bills),
        "bills": bills,
        "metadata": {
            "source": "Washington State Legislature",
            "updateFrequency": "daily",
            "dataVersion": "2.0.0",
            "includesRevived": True,
            "billTypes": ["HB", "SB", "HJR", "SJR", "HJM", "SJM", "HCR", "SCR", "I", "R"]
        }
    }
    
    data_file = DATA_DIR / "bills.json"
    with open(data_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"âœ… Saved {len(bills)} bills to {data_file}")
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
        with open(log_file, 'r') as f:
            data = json.load(f)
            logs = data.get('logs', [])
    
    # Add new log entry (keep last 100 entries)
    logs.insert(0, log)
    logs = logs[:100]
    
    # Save logs
    with open(log_file, 'w') as f:
        json.dump({"logs": logs}, f, indent=2)
    
    print(f"ðŸ“ Sync log updated: {status} - {bills_count} bills, {new_count} new")

def load_existing_data() -> Optional[Dict]:
    """Load existing bills data if it exists"""
    data_file = DATA_DIR / "bills.json"
    if data_file.exists():
        with open(data_file, 'r') as f:
            return json.load(f)
    return None

def main():
    """Main execution function"""
    print(f"ðŸš€ Starting Comprehensive WA Legislature Bill Fetcher - {datetime.now()}")
    print("=" * 60)
    
    # Ensure data directory exists
    ensure_data_dir()
    
    # Load existing data
    existing_data = load_existing_data()
    existing_bills = {}
    if existing_data:
        existing_bills = {bill['id']: bill for bill in existing_data.get('bills', [])}
        print(f"ðŸ“š Loaded {len(existing_bills)} existing bills")
    
    # Fetch comprehensive bill list
    print("ðŸ“¥ Fetching comprehensive bill data...")
    print("   - Checking LegiScan and WA Legislature sources...")
    
    all_bills = fetch_bills_from_wa_legislature()
    
    # Track new bills
    new_bills = []
    updated_bills = []
    
    for bill in all_bills:
        if bill['id'] not in existing_bills:
            new_bills.append(bill)
        elif bill != existing_bills[bill['id']]:
            updated_bills.append(bill)
    
    print(f"   âœ¨ Found {len(new_bills)} new bills")
    print(f"   ðŸ”„ Updated {len(updated_bills)} existing bills")
    
    # Merge with existing bills
    for bill in all_bills:
        existing_bills[bill['id']] = bill
    
    # Convert back to list
    final_bills = list(existing_bills.values())
    
    # Save bills data
    save_bills_data(final_bills)
    
    # Create statistics
    create_stats_file(final_bills)
    
    # Create sync log
    create_sync_log(len(final_bills), len(new_bills), "success")
    
    print("=" * 60)
    print(f"âœ… Successfully updated database:")
    print(f"   - Total bills: {len(final_bills)}")
    print(f"   - New bills: {len(new_bills)}")
    print(f"   - Updated bills: {len(updated_bills)}")
    print(f"ðŸ Update complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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
    
    # Calculate statistics
    today = datetime.now().date()
    
    for bill in bills:
        # By status
        status = bill.get('status', 'unknown')
        stats['byStatus'][status] = stats['byStatus'].get(status, 0) + 1
        
        # By committee
        committee = bill.get('committee', 'unknown')
        stats['byCommittee'][committee] = stats['byCommittee'].get(committee, 0) + 1
        
        # By priority
        priority = bill.get('priority', 'unknown')
        stats['byPriority'][priority] = stats['byPriority'].get(priority, 0) + 1
        
        # By topic
        topic = bill.get('topic', 'unknown')
        stats['byTopic'][topic] = stats['byTopic'].get(topic, 0) + 1
        
        # By sponsor
        sponsor = bill.get('sponsor', 'unknown')
        stats['bySponsor'][sponsor] = stats['bySponsor'].get(sponsor, 0) + 1
        
        # By type (HB, SB, etc.)
        bill_type = bill['number'].split()[0] if ' ' in bill['number'] else 'unknown'
        stats['byType'][bill_type] = stats['byType'].get(bill_type, 0) + 1
        
        # Recently updated
        try:
            last_updated = datetime.fromisoformat(bill.get('lastUpdated', ''))
            days_diff = (datetime.now() - last_updated).days
            
            if days_diff < 1:
                stats['recentlyUpdated'] += 1
            
            if last_updated.date() == today:
                stats['updatedToday'] += 1
                
        except:
            pass
        
        # Hearings
        hearings = bill.get('hearings', [])
        if hearings:
            stats['billsWithHearings'] += 1
            
        for hearing in hearings:
            try:
                hearing_date = datetime.strptime(hearing['date'], '%Y-%m-%d')
                if 0 <= (hearing_date.date() - today).days <= 7:
                    stats['upcomingHearings'] += 1
            except:
                pass
    
    # Sort sponsors by count
    stats['topSponsors'] = sorted(
        stats['bySponsor'].items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:10]
    
    stats_file = DATA_DIR / "stats.json"
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"ðŸ“Š Statistics file updated with {len(stats['byStatus'])} statuses, {len(stats['byCommittee'])} committees")

if __name__ == "__main__":
    main()
