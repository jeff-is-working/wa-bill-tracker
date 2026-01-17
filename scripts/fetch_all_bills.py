#!/usr/bin/env python3
"""
Washington State Legislature Bill Fetcher
Fetches bills from the official WA Legislature Web Services API
Uses documented API methods from wslwebservices.leg.wa.gov
"""

import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple
import re

# Configuration
BASE_API_URL = "https://wslwebservices.leg.wa.gov"
BASE_WEB_URL = "https://app.leg.wa.gov"
BIENNIUM = "2025-26"
YEAR = 2025  # Use 2025 as the year for 2025-26 biennium
DATA_DIR = Path("data")

# SOAP Service Endpoints
LEGISLATION_SERVICE = f"{BASE_API_URL}/LegislationService.asmx"

def ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(exist_ok=True)

def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and control characters"""
    if not text:
        return ""
    text = ' '.join(text.split())
    text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
    return text.strip()

def make_soap_request(soap_body: str, soap_action: str, debug: bool = False) -> Optional[ET.Element]:
    """Make SOAP request to WA Legislature API"""
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': f'"{soap_action}"'
    }
    
    soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    {soap_body}
  </soap:Body>
</soap:Envelope>"""
    
    if debug:
        print(f"SOAP Request to {LEGISLATION_SERVICE}")
        print(f"Action: {soap_action}")
        with open('debug_request.xml', 'w') as f:
            f.write(soap_envelope)
    
    try:
        response = requests.post(LEGISLATION_SERVICE, 
                                data=soap_envelope, 
                                headers=headers, 
                                timeout=60)
        
        if debug:
            print(f"Response Status: {response.status_code}")
            with open('debug_response.xml', 'w') as f:
                f.write(response.text)
        
        if response.status_code == 200:
            # Check if response contains a SOAP fault
            if 'soap:Fault' in response.text or 'faultstring' in response.text:
                print("SOAP Fault received:")
                print(response.text[:500])
                return None
            
            root = ET.fromstring(response.content)
            return root
        else:
            print(f"HTTP Error {response.status_code}")
            print(response.text[:500])
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        print("Response content:")
        if 'response' in locals():
            print(response.text[:500])
        return None

def fetch_prefiled_legislation_info() -> List[Dict]:
    """Fetch all prefiled legislation info using GetPreFiledLegislationInfo"""
    print(f"Fetching prefiled legislation for biennium {BIENNIUM}")
    
    soap_body = f"""
    <GetPreFiledLegislationInfo xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
    </GetPreFiledLegislationInfo>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetPreFiledLegislationInfo",
        debug=True
    )
    
    if root is None:
        return []
    
    return parse_legislation_info_response(root)

def fetch_legislation_by_year() -> List[Dict]:
    """Fetch all legislation active during the year using GetLegislationByYear"""
    print(f"Fetching legislation for year {YEAR}")
    
    soap_body = f"""
    <GetLegislationByYear xmlns="http://WSLWebServices.leg.wa.gov/">
      <year>{YEAR}</year>
    </GetLegislationByYear>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislationByYear",
        debug=True
    )
    
    if root is None:
        return []
    
    return parse_legislation_info_response(root)

def fetch_legislative_status_changes() -> List[Dict]:
    """Fetch legislation with status changes using GetLegislativeStatusChanges"""
    print(f"Fetching legislation with status changes for biennium {BIENNIUM}")
    
    # Get changes from December 1, 2025 to now
    begin_date = "2025-12-01T00:00:00"
    end_date = datetime.now().isoformat()
    
    soap_body = f"""
    <GetLegislativeStatusChanges xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
      <beginDate>{begin_date}</beginDate>
      <endDate>{end_date}</endDate>
    </GetLegislativeStatusChanges>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislativeStatusChanges",
        debug=True
    )
    
    if root is None:
        return []
    
    return parse_legislation_info_response(root)

def parse_legislation_info_response(root: ET.Element) -> List[Dict]:
    """Parse the XML response containing LegislationInfo elements"""
    bills = []
    
    # Remove namespaces for easier parsing
    xml_str = ET.tostring(root, encoding='unicode')
    # Remove the namespace declaration to simplify XPath
    xml_str = re.sub(r'xmlns="[^"]*"', '', xml_str)
    root_clean = ET.fromstring(xml_str)
    
    # Find all LegislationInfo elements at any level
    legislation_infos = root_clean.findall('.//LegislationInfo')
    
    print(f"Found {len(legislation_infos)} LegislationInfo elements")
    
    for leg_elem in legislation_infos:
        bill = parse_single_legislation_info(leg_elem)
        if bill:
            bills.append(bill)
            print(f"  Parsed: {bill['number']} - {bill['title'][:50]}...")
    
    return bills

def parse_single_legislation_info(elem: ET.Element) -> Optional[Dict]:
    """Parse a single LegislationInfo XML element"""
    try:
        # Helper function to get element text safely
        def get_text(tag: str, default: str = "") -> str:
            child = elem.find(tag)
            return child.text.strip() if child is not None and child.text else default
        
        # Extract basic fields
        biennium = get_text('Biennium', BIENNIUM)
        bill_id = get_text('BillId')
        bill_number = get_text('BillNumber')
        
        if not bill_id or not bill_number:
            return None
        
        # Get bill details
        substitute_version = get_text('SubstituteVersion', '')
        engrossed_version = get_text('EngrossedVersion', '')
        original_agency = get_text('OriginalAgency', '')
        active = get_text('Active', 'true')
        display_number = get_text('DisplayNumber', '')
        
        # Get descriptions
        short_description = clean_text(get_text('ShortDescription', 'No title available'))
        long_description = clean_text(get_text('LongDescription', ''))
        legal_title = clean_text(get_text('LegalTitle', ''))
        
        # Use DisplayNumber if available, otherwise construct it
        if display_number:
            bill_display = display_number
        else:
            bill_display = construct_bill_number(bill_number, original_agency, substitute_version, engrossed_version)
        
        # Get sponsor/requester information
        prime_sponsor = get_text('PrimeSponsor', '')
        requested_by = get_text('RequestedBy', '')
        sponsor = prime_sponsor if prime_sponsor else requested_by if requested_by else "Unknown"
        
        # Get status information
        current_status = get_text('CurrentStatus', '')
        history_line = get_text('HistoryLine', '')
        status = determine_bill_status(current_status, history_line, active)
        
        # Get dates
        introduced_date = get_text('IntroducedDate', '')
        prefiled_date = get_text('PrefiledDate', '')
        
        # Use the earliest date available
        bill_date = introduced_date if introduced_date else prefiled_date if prefiled_date else "2025-12-01"
        
        # Parse and format date
        try:
            if 'T' in bill_date:
                dt = datetime.fromisoformat(bill_date.replace('Z', '+00:00'))
                bill_date = dt.date().isoformat()
            else:
                # Take just the date part if it's a date string
                bill_date = bill_date[:10]
        except:
            bill_date = "2025-12-01"
        
        # Determine other attributes
        committee = determine_committee(bill_display, short_description)
        priority = determine_priority(short_description)
        topic = determine_topic(short_description)
        
        # Create the bill dictionary
        bill = {
            "id": bill_id,
            "number": bill_display,
            "billNumber": bill_number,
            "title": short_description,
            "sponsor": sponsor,
            "description": long_description if long_description else f"A bill relating to {short_description.lower()}",
            "status": status,
            "committee": committee,
            "priority": priority,
            "topic": topic,
            "introducedDate": bill_date,
            "lastUpdated": datetime.now().isoformat(),
            "legUrl": f"{BASE_WEB_URL}/billsummary?BillNumber={bill_number}&Year=2026",
            "biennium": biennium,
            "active": active.lower() == 'true',
            "hearings": []
        }
        
        return bill
        
    except Exception as e:
        print(f"Error parsing legislation element: {e}")
        return None

def construct_bill_number(bill_number: str, original_agency: str, substitute_version: str, engrossed_version: str) -> str:
    """Construct the display bill number from components"""
    
    # Determine prefix based on agency and number range
    if original_agency and 'House' in original_agency:
        prefix = 'HB'
    elif original_agency and 'Senate' in original_agency:
        prefix = 'SB'
    else:
        # Guess based on number range
        try:
            num = int(bill_number)
            if num >= 5000:
                prefix = 'SB'
            elif num >= 4400:
                prefix = 'SCR'  # Senate Concurrent Resolution
            elif num >= 4100:
                prefix = 'SJM'  # Senate Joint Memorial  
            elif num >= 4000:
                prefix = 'SJR'  # Senate Joint Resolution
            elif num >= 8400:
                prefix = 'SCR'
            elif num >= 8100:
                prefix = 'SJM'
            elif num >= 8000:
                prefix = 'SJR'
            else:
                prefix = 'HB'
        except:
            prefix = 'HB'
    
    # Add version prefixes
    version_prefix = ''
    if substitute_version and 'S' in substitute_version:
        s_count = substitute_version.count('S')
        if s_count > 1:
            version_prefix = f"{s_count}S"
        else:
            version_prefix = "S"
    
    if engrossed_version and 'E' in engrossed_version:
        version_prefix += 'E'
    
    # Combine parts
    if version_prefix:
        return f"{version_prefix}{prefix} {bill_number}"
    else:
        return f"{prefix} {bill_number}"

def determine_bill_status(current_status: str, history_line: str, active: str) -> str:
    """Determine standardized bill status"""
    
    status_text = (current_status + " " + history_line).lower()
    
    if active.lower() == 'false':
        return 'failed'
    
    if any(word in status_text for word in ['signed', 'law', 'enacted']):
        return 'enacted'
    elif any(word in status_text for word in ['vetoed', 'veto']):
        return 'vetoed'
    elif any(word in status_text for word in ['passed legislature', 'passed both']):
        return 'passed'
    elif any(word in status_text for word in ['delivered to governor', 'governor']):
        return 'delivered'
    elif any(word in status_text for word in ['passed house', 'passed senate']):
        return 'passed_chamber'
    elif any(word in status_text for word in ['committee', 'referred']):
        return 'committee'
    elif any(word in status_text for word in ['first reading', 'introduced']):
        return 'introduced'
    elif any(word in status_text for word in ['prefiled', 'pre-filed']):
        return 'prefiled'
    else:
        return 'active'

def determine_committee(bill_number: str, title: str) -> str:
    """Determine committee assignment based on bill content"""
    title_lower = title.lower()
    
    # Committee mapping based on subject matter
    committee_keywords = {
        "Education": ["education", "school", "student", "teacher", "learning", "academic"],
        "Transportation": ["transportation", "road", "highway", "transit", "vehicle", "traffic"],
        "Housing": ["housing", "rent", "tenant", "landlord", "homeless", "affordable housing"],
        "Health & Long-Term Care": ["health", "medical", "hospital", "mental", "behavioral", "healthcare"],
        "Environment & Energy": ["environment", "climate", "energy", "pollution", "conservation", "renewable"],
        "Finance": ["tax", "revenue", "fiscal", "budget", "appropriation", "funding"],
        "Ways & Means": ["budget", "fiscal", "appropriation", "revenue", "financial"],
        "Consumer Protection & Business": ["consumer", "business", "commerce", "trade", "regulation"],
        "Law & Justice": ["crime", "criminal", "justice", "police", "court", "legal"],
        "Labor & Commerce": ["labor", "employment", "worker", "wage", "workplace", "union"],
        "Agriculture & Natural Resources": ["agriculture", "farm", "food", "rural", "natural resources"],
        "Local Government": ["local", "city", "county", "municipal", "government"],
        "State Government & Tribal Relations": ["state", "government", "tribal", "election", "records"]
    }
    
    for committee, keywords in committee_keywords.items():
        if any(keyword in title_lower for keyword in keywords):
            # Handle Finance vs Ways & Means based on chamber
            if committee in ["Finance", "Ways & Means"]:
                if bill_number.startswith("HB"):
                    return "Finance"
                else:
                    return "Ways & Means"
            return committee
    
    return "State Government & Tribal Relations"

def determine_topic(title: str) -> str:
    """Determine bill topic from title keywords"""
    title_lower = title.lower()
    
    topic_keywords = {
        "Education": ["education", "school", "student", "teacher", "learning"],
        "Tax & Revenue": ["tax", "revenue", "budget", "fiscal", "fee"],
        "Housing": ["housing", "rent", "tenant", "homeless"],
        "Healthcare": ["health", "medical", "hospital", "mental"],
        "Environment": ["environment", "climate", "energy", "conservation"],
        "Transportation": ["transport", "road", "highway", "transit"],
        "Public Safety": ["crime", "safety", "police", "justice"],
        "Business": ["business", "commerce", "trade", "economy"],
        "Technology": ["technology", "internet", "data", "privacy"],
        "Labor": ["labor", "employment", "worker", "wage"],
        "Agriculture": ["agriculture", "farm", "food", "rural"]
    }
    
    for topic, keywords in topic_keywords.items():
        if any(keyword in title_lower for keyword in keywords):
            return topic
    
    return "General Government"

def determine_priority(title: str) -> str:
    """Determine bill priority based on content"""
    title_lower = title.lower()
    
    high_keywords = ["emergency", "urgent", "budget", "appropriation", "supplemental"]
    low_keywords = ["technical", "clarifying", "housekeeping", "memorial", "study"]
    
    if any(keyword in title_lower for keyword in high_keywords):
        return "high"
    elif any(keyword in title_lower for keyword in low_keywords):
        return "low"
    
    return "medium"

def save_bills_data(bills: List[Dict]) -> Dict:
    """Save bills data to JSON file"""
    # Remove duplicates based on bill ID
    unique_bills = {}
    for bill in bills:
        bill_id = bill.get('id')
        if bill_id and bill_id not in unique_bills:
            unique_bills[bill_id] = bill
    
    bills = list(unique_bills.values())
    
    # Sort bills by type and number
    def sort_key(bill):
        number = bill.get('number', '')
        match = re.match(r'([A-Z]+)\s*(\d+)', number)
        if match:
            bill_type = match.group(1)
            bill_num = int(match.group(2))
            return (bill_type, bill_num)
        return ('ZZ', 99999)
    
    bills.sort(key=sort_key)
    
    data = {
        "lastSync": datetime.now().isoformat(),
        "sessionYear": 2026,  # Display year
        "biennium": BIENNIUM,
        "sessionStart": "2026-01-12",
        "sessionEnd": "2026-03-12",
        "totalBills": len(bills),
        "bills": bills,
        "metadata": {
            "source": "Washington State Legislature Web Services",
            "apiUrl": BASE_API_URL,
            "updateFrequency": "daily",
            "dataVersion": "3.1.0",
            "methods": ["GetPreFiledLegislationInfo", "GetLegislationByYear", "GetLegislativeStatusChanges"]
        }
    }
    
    data_file = DATA_DIR / "bills.json"
    with open(data_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=True)
    
    print(f"Saved {len(bills)} bills to {data_file}")
    return data

def create_sync_log(bills_count: int, methods_used: List[str], status: str = "success"):
    """Create sync log for monitoring"""
    log = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "billsCount": bills_count,
        "methodsUsed": methods_used,
        "apiUrl": BASE_API_URL,
        "nextSync": (datetime.now() + timedelta(hours=6)).isoformat()
    }
    
    log_file = DATA_DIR / "sync-log.json"
    
    # Load existing logs
    logs = []
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                data = json.load(f)
                logs = data.get('logs', [])
        except:
            logs = []
    
    # Add new log (keep last 100)
    logs.insert(0, log)
    logs = logs[:100]
    
    # Save logs
    with open(log_file, 'w') as f:
        json.dump({"logs": logs}, f, indent=2)
    
    print(f"Sync log updated: {status} - {bills_count} bills")

def main():
    """Main execution function"""
    print(f"Starting WA Legislature Bill Fetcher - {datetime.now()}")
    print("Using documented API methods from wslwebservices.leg.wa.gov")
    print("=" * 60)
    
    # Ensure data directory exists
    ensure_data_dir()
    
    all_bills = {}
    methods_used = []
    
    # Method 1: Get prefiled legislation info
    print("\n1. Fetching prefiled legislation...")
    try:
        prefiled_bills = fetch_prefiled_legislation_info()
        for bill in prefiled_bills:
            if bill['id'] not in all_bills:
                all_bills[bill['id']] = bill
        methods_used.append("GetPreFiledLegislationInfo")
        print(f"   Found {len(prefiled_bills)} prefiled bills")
    except Exception as e:
        print(f"   Error in GetPreFiledLegislationInfo: {e}")
    
    # Method 2: Get legislation by year
    print("\n2. Fetching legislation by year...")
    try:
        year_bills = fetch_legislation_by_year()
        new_from_year = 0
        for bill in year_bills:
            if bill['id'] not in all_bills:
                all_bills[bill['id']] = bill
                new_from_year += 1
        methods_used.append("GetLegislationByYear")
        print(f"   Found {len(year_bills)} bills for {YEAR} ({new_from_year} new)")
    except Exception as e:
        print(f"   Error in GetLegislationByYear: {e}")
    
    # Method 3: Get legislative status changes
    print("\n3. Fetching recent status changes...")
    try:
        status_bills = fetch_legislative_status_changes()
        new_from_status = 0
        for bill in status_bills:
            if bill['id'] not in all_bills:
                all_bills[bill['id']] = bill
                new_from_status += 1
        methods_used.append("GetLegislativeStatusChanges")
        print(f"   Found {len(status_bills)} bills with status changes ({new_from_status} new)")
    except Exception as e:
        print(f"   Error in GetLegislativeStatusChanges: {e}")
    
    # Convert to list
    final_bills = list(all_bills.values())
    
    print("\n" + "=" * 60)
    print(f"Total unique bills collected: {len(final_bills)}")
    
    if final_bills:
        print("\nSample bills found:")
        for bill in final_bills[:5]:
            print(f"  - {bill['number']}: {bill['title']}")
    
    # Save data
    if final_bills:
        save_bills_data(final_bills)
        create_sync_log(len(final_bills), methods_used, "success")
    else:
        create_sync_log(0, methods_used, "no_data")
    
    print("=" * 60)
    print(f"Update complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
