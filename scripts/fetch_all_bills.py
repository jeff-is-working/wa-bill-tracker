#!/usr/bin/env python3
"""
Washington State Legislature Bill Fetcher
Fetches bills from the official WA Legislature Web Services API
Compliant with https://wslwebservices.leg.wa.gov/
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
YEAR = 2026
DATA_DIR = Path("data")

# SOAP Service Endpoint
LEGISLATION_SERVICE = f"{BASE_API_URL}/LegislationService.asmx"

def ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(exist_ok=True)
    
def clean_text(text: str) -> str:
    """Clean text by removing extra whitespace and special characters"""
    if not text:
        return ""
    # Remove extra whitespace
    text = ' '.join(text.split())
    # Remove control characters but keep normal text
    text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
    return text.strip()

def make_soap_request(soap_body: str, soap_action: str, debug: bool = False) -> Optional[ET.Element]:
    """Make SOAP request to WA Legislature API with proper headers"""
    
    # SOAPAction must be quoted
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': f'"{soap_action}"'  # Note the quotes around the action
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
        print(f"Making request with SOAPAction: {headers['SOAPAction']}")
        with open('request_debug.xml', 'w') as f:
            f.write(soap_envelope)
    
    try:
        response = requests.post(LEGISLATION_SERVICE, 
                                data=soap_envelope, 
                                headers=headers, 
                                timeout=60)
        
        if debug:
            with open('response_debug.xml', 'w') as f:
                f.write(response.text)
            print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            return root
        else:
            print(f"API Error {response.status_code}")
            if debug:
                print(response.text[:500])
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        return None

def fetch_legislation_introduced_since(date: str) -> List[Dict]:
    """Fetch legislation introduced since a specific date"""
    print(f"Fetching legislation introduced since {date}")
    
    soap_body = f"""
    <GetLegislationIntroducedSince xmlns="http://WSLWebServices.leg.wa.gov/">
      <sinceDate>{date}</sinceDate>
    </GetLegislationIntroducedSince>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislationIntroducedSince"
    )
    
    if root is None:
        return []
    
    return parse_legislation_response(root)

def fetch_legislation_by_year() -> List[Dict]:
    """Fetch all legislation for the current year"""
    print(f"Fetching legislation for year {YEAR}")
    
    soap_body = f"""
    <GetLegislationByYear xmlns="http://WSLWebServices.leg.wa.gov/">
      <year>{YEAR}</year>
    </GetLegislationByYear>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislationByYear"
    )
    
    if root is None:
        return []
    
    return parse_legislation_response(root)

def fetch_legislation_info_by_biennium() -> List[Dict]:
    """Fetch all legislation info for the biennium"""
    print(f"Fetching all legislation for biennium {BIENNIUM}")
    
    soap_body = f"""
    <GetLegislationInfoByBiennium xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
    </GetLegislationInfoByBiennium>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislationInfoByBiennium"
    )
    
    if root is None:
        return []
    
    return parse_legislation_response(root)

def fetch_legislation_by_status_change(begin_date: str, end_date: str) -> List[Dict]:
    """Fetch legislation with status changes in date range"""
    print(f"Fetching bills with status changes from {begin_date} to {end_date}")
    
    soap_body = f"""
    <GetLegislativeStatusChangesByDateRange xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
      <beginDate>{begin_date}</beginDate>
      <endDate>{end_date}</endDate>
    </GetLegislativeStatusChangesByDateRange>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislativeStatusChangesByDateRange"
    )
    
    if root is None:
        return []
    
    return parse_status_changes_response(root)

def parse_legislation_response(root: ET.Element) -> List[Dict]:
    """Parse the XML response containing legislation info"""
    bills = []
    
    # Remove namespaces for easier parsing
    xml_str = ET.tostring(root, encoding='unicode')
    xml_str = xml_str.replace('xmlns="http://WSLWebServices.leg.wa.gov/"', '')
    root_clean = ET.fromstring(xml_str)
    
    # Find all LegislationInfo elements
    for leg_elem in root_clean.findall('.//LegislationInfo'):
        bill = parse_legislation_element(leg_elem)
        if bill:
            bills.append(bill)
    
    # Also try ArrayOfLegislationInfo pattern
    for leg_elem in root_clean.findall('.//ArrayOfLegislationInfo/LegislationInfo'):
        bill = parse_legislation_element(leg_elem)
        if bill:
            bills.append(bill)
    
    return bills

def parse_status_changes_response(root: ET.Element) -> List[Dict]:
    """Parse the XML response from status changes query"""
    bills = []
    
    # Remove namespaces
    xml_str = ET.tostring(root, encoding='unicode')
    xml_str = xml_str.replace('xmlns="http://WSLWebServices.leg.wa.gov/"', '')
    root_clean = ET.fromstring(xml_str)
    
    # Find all LegislativeStatus elements
    for status_elem in root_clean.findall('.//LegislativeStatus'):
        bill_id = get_element_text(status_elem, 'BillId')
        bill_number = get_element_text(status_elem, 'BillNumber')
        
        if bill_id and bill_number:
            # Fetch full details for this bill
            full_bill = fetch_bill_by_number(bill_number)
            if full_bill:
                bills.append(full_bill)
    
    return bills

def parse_legislation_element(elem: ET.Element) -> Optional[Dict]:
    """Parse a single LegislationInfo element"""
    try:
        # Extract basic information
        biennium = get_element_text(elem, 'Biennium', BIENNIUM)
        bill_id = get_element_text(elem, 'BillId')
        bill_number = get_element_text(elem, 'BillNumber')
        
        if not bill_id or not bill_number:
            return None
        
        # Extract other fields
        substitute_version = get_element_text(elem, 'SubstituteVersion', '')
        engrossed_version = get_element_text(elem, 'EngrossedVersion', '')
        original_agency = get_element_text(elem, 'OriginalAgency', '')
        active = get_element_text(elem, 'Active', 'true')
        
        # Get descriptions
        short_description = clean_text(get_element_text(elem, 'ShortDescription', 'No title available'))
        long_description = clean_text(get_element_text(elem, 'LongDescription', ''))
        legal_title = clean_text(get_element_text(elem, 'LegalTitle', ''))
        
        # Build display bill number
        display_number = build_display_number(bill_number, original_agency, 
                                             substitute_version, engrossed_version)
        
        # Get sponsor information
        prime_sponsor = get_element_text(elem, 'PrimeSponsor', '')
        if not prime_sponsor:
            # Try alternate fields
            prime_sponsor = get_element_text(elem, 'Sponsor', '')
            if not prime_sponsor:
                prime_sponsor = get_element_text(elem, 'RequestedBy', '')
        
        # Get status - try multiple fields
        status = determine_status(elem)
        
        # Get dates
        introduced_date = get_element_text(elem, 'IntroducedDate', '')
        if not introduced_date:
            introduced_date = get_element_text(elem, 'PrefiledDate', '')
        
        # Parse and format date
        if introduced_date:
            try:
                # Handle ISO format with timezone
                if 'T' in introduced_date:
                    dt = datetime.fromisoformat(introduced_date.replace('Z', '+00:00'))
                    introduced_date = dt.date().isoformat()
                else:
                    introduced_date = introduced_date[:10]  # Just take date part
            except:
                introduced_date = "2026-01-12"
        else:
            introduced_date = "2026-01-12"
        
        # Determine committee and other metadata
        committee = determine_committee(display_number, short_description)
        priority = determine_priority(short_description)
        topic = determine_topic(short_description)
        
        # Build the bill dictionary
        bill = {
            "id": bill_id,
            "number": display_number,
            "billNumber": bill_number,  # Keep raw number
            "title": short_description,
            "sponsor": prime_sponsor if prime_sponsor else "Not Available",
            "description": long_description if long_description else legal_title if legal_title else f"A bill relating to {short_description.lower()}",
            "status": status,
            "committee": committee,
            "priority": priority,
            "topic": topic,
            "introducedDate": introduced_date,
            "lastUpdated": datetime.now().isoformat(),
            "legUrl": f"{BASE_WEB_URL}/billsummary?BillNumber={bill_number}&Year={YEAR}",
            "biennium": biennium,
            "active": active.lower() == 'true',
            "hearings": []
        }
        
        return bill
        
    except Exception as e:
        print(f"Error parsing legislation element: {e}")
        return None

def get_element_text(parent: ET.Element, tag: str, default: str = "") -> str:
    """Safely get text from an XML element"""
    elem = parent.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return default

def build_display_number(bill_number: str, original_agency: str, 
                         substitute_version: str, engrossed_version: str) -> str:
    """Build the display bill number with proper prefix"""
    
    # Determine bill type prefix
    if original_agency:
        if 'House' in original_agency:
            prefix = 'HB'
        elif 'Senate' in original_agency:
            prefix = 'SB'
        else:
            # Try to infer from number
            try:
                num = int(bill_number)
                if num >= 5000:
                    prefix = 'SB'
                elif num >= 4000:
                    # Could be HJR, HJM, HCR
                    if num >= 4400:
                        prefix = 'HCR'
                    elif num >= 4100:
                        prefix = 'HJM'
                    else:
                        prefix = 'HJR'
                else:
                    prefix = 'HB'
            except:
                prefix = 'HB'
    else:
        # Default based on number range
        try:
            num = int(bill_number)
            if num >= 8400:
                prefix = 'SCR'
            elif num >= 8100:
                prefix = 'SJM'
            elif num >= 8000:
                prefix = 'SJR'
            elif num >= 5000:
                prefix = 'SB'
            elif num >= 4400:
                prefix = 'HCR'
            elif num >= 4100:
                prefix = 'HJM'
            elif num >= 4000:
                prefix = 'HJR'
            else:
                prefix = 'HB'
        except:
            prefix = 'HB'
    
    # Add version prefixes
    version_prefix = ''
    if substitute_version:
        # Extract number of S's (SSB, 2SSB, etc.)
        s_count = substitute_version.count('S')
        if s_count > 1:
            version_prefix = f"{s_count}S"
        elif s_count == 1:
            version_prefix = "S"
    
    if engrossed_version:
        # Add E for engrossed
        version_prefix += 'E'
    
    # Combine parts
    if version_prefix:
        display_number = f"{version_prefix}{prefix} {bill_number}"
    else:
        display_number = f"{prefix} {bill_number}" 
    
    return display_number

def determine_status(elem: ET.Element) -> str:
    """Determine bill status from various fields"""
    
    # Check CurrentStatus field
    current_status = get_element_text(elem, 'CurrentStatus', '').lower()
    
    # Check for specific status indicators
    if get_element_text(elem, 'Active', 'true').lower() == 'false':
        return 'failed'
    
    if current_status:
        if 'governor' in current_status and 'signed' in current_status:
            return 'enacted'
        elif 'veto' in current_status:
            return 'vetoed'
        elif 'passed' in current_status:
            return 'passed'
        elif 'delivered' in current_status:
            return 'delivered'
        elif 'committee' in current_status:
            return 'committee'
        elif 'first reading' in current_status or 'introduced' in current_status:
            return 'introduced'
        elif 'prefiled' in current_status:
            return 'prefiled'
    
    # Check history line
    history = get_element_text(elem, 'HistoryLine', '').lower()
    if history:
        if 'passed' in history:
            return 'passed'
        elif 'committee' in history:
            return 'committee'
        elif 'introduced' in history:
            return 'introduced'
    
    # Default based on dates
    prefiled_date = get_element_text(elem, 'PrefiledDate', '')
    introduced_date = get_element_text(elem, 'IntroducedDate', '')
    
    if introduced_date:
        return 'introduced'
    elif prefiled_date:
        return 'prefiled'
    
    return 'active'

def fetch_bill_by_number(bill_number: str) -> Optional[Dict]:
    """Fetch a specific bill by its number"""
    soap_body = f"""
    <GetLegislation xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
      <billNumber>{bill_number}</billNumber>
    </GetLegislation>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislation"
    )
    
    if root:
        bills = parse_legislation_response(root)
        if bills:
            return bills[0]
    
    return None

def determine_committee(bill_number: str, title: str) -> str:
    """Determine committee assignment based on bill number and title"""
    title_lower = title.lower()
    
    committees = {
        "Education": ["education", "school", "student", "teacher", "learning"],
        "Transportation": ["transportation", "road", "highway", "transit", "vehicle"],
        "Housing": ["housing", "rent", "tenant", "landlord", "homeless"],
        "Health & Long-Term Care": ["health", "medical", "hospital", "behavioral", "mental"],
        "Environment & Energy": ["environment", "climate", "energy", "pollution", "conservation"],
        "Finance": ["tax", "revenue", "fiscal", "budget", "appropriation"],
        "Ways & Means": ["budget", "fiscal", "appropriation", "revenue"],
        "Consumer Protection & Business": ["consumer", "business", "commerce", "trade"],
        "Law & Justice": ["crime", "criminal", "justice", "police", "court"],
        "Labor & Commerce": ["labor", "employment", "worker", "wage", "workplace"],
        "Agriculture": ["agriculture", "farm", "food", "rural"],
        "Local Government": ["local", "city", "county", "municipal"],
        "State Government & Tribal Relations": ["state government", "tribal", "election", "public records"]
    }
    
    for committee, keywords in committees.items():
        if any(keyword in title_lower for keyword in keywords):
            # Special handling for Finance vs Ways & Means
            if committee in ["Finance", "Ways & Means"]:
                if bill_number.startswith("HB") or bill_number.startswith("HJR"):
                    return "Finance"
                else:
                    return "Ways & Means"
            return committee
    
    return "State Government & Tribal Relations"

def determine_topic(title: str) -> str:
    """Determine bill topic from title"""
    title_lower = title.lower()
    
    topics = {
        "Education": ["education", "school", "student", "teacher", "learning", "academic"],
        "Tax & Revenue": ["tax", "revenue", "budget", "fiscal", "fee"],
        "Housing": ["housing", "rent", "tenant", "landlord", "homeless"],
        "Healthcare": ["health", "medical", "hospital", "mental", "behavioral"],
        "Environment": ["environment", "climate", "energy", "pollution", "conservation"],
        "Transportation": ["transport", "road", "highway", "transit", "vehicle"],
        "Public Safety": ["crime", "safety", "police", "justice", "criminal"],
        "Business": ["business", "commerce", "trade", "economy", "corporation"],
        "Technology": ["technology", "internet", "data", "privacy", "cyber"],
        "Labor": ["labor", "employment", "worker", "wage", "workplace"],
        "Agriculture": ["agriculture", "farm", "food", "rural"]
    }
    
    for topic, keywords in topics.items():
        if any(keyword in title_lower for keyword in keywords):
            return topic
    
    return "General Government"

def determine_priority(title: str) -> str:
    """Determine bill priority based on keywords in title"""
    title_lower = title.lower()
    
    high_keywords = ["emergency", "urgent", "supplemental", "budget", "appropriations"]
    low_keywords = ["technical", "clarifying", "housekeeping", "memorial"]
    
    if any(keyword in title_lower for keyword in high_keywords):
        return "high"
    elif any(keyword in title_lower for keyword in low_keywords):
        return "low"
    
    return "medium"

def save_bills_data(bills: List[Dict]) -> Dict:
    """Save bills data to JSON file"""
    # Remove duplicates
    unique_bills = {}
    for bill in bills:
        bill_id = bill.get('id')
        if bill_id and bill_id not in unique_bills:
            unique_bills[bill_id] = bill
    
    bills = list(unique_bills.values())
    
    # Sort bills
    def sort_key(bill):
        number = bill.get('number', '')
        # Extract type and number for sorting
        match = re.match(r'([A-Z]+)\s*(\d+)', number)
        if match:
            bill_type = match.group(1)
            bill_num = int(match.group(2))
            # Remove version indicators for sorting
            bill_type = re.sub(r'[0-9SE]', '', bill_type)
            return (bill_type, bill_num)
        return ('ZZ', 99999)
    
    bills.sort(key=sort_key)
    
    data = {
        "lastSync": datetime.now().isoformat(),
        "sessionYear": YEAR,
        "biennium": BIENNIUM,
        "sessionStart": "2026-01-12",
        "sessionEnd": "2026-03-12",
        "totalBills": len(bills),
        "bills": bills,
        "metadata": {
            "source": "Washington State Legislature Web Services",
            "apiUrl": BASE_API_URL,
            "updateFrequency": "daily",
            "dataVersion": "3.0.0"
        }
    }
    
    data_file = DATA_DIR / "bills.json"
    with open(data_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=True)
    
    print(f"Saved {len(bills)} bills to {data_file}")
    return data

def main():
    """Main execution function"""
    print(f"Starting WA Legislature Bill Fetcher - {datetime.now()}")
    print("=" * 60)
    
    # Ensure data directory exists
    ensure_data_dir()
    
    all_bills = {}
    
    # Method 1: Fetch bills introduced since December 1, 2025 (pre-filing period)
    print("\n1. Fetching bills introduced since December 1, 2025...")
    since_date = "2025-12-01T00:00:00"
    recent_bills = fetch_legislation_introduced_since(since_date)
    for bill in recent_bills:
        if bill['id'] not in all_bills:
            all_bills[bill['id']] = bill
    print(f"   Found {len(recent_bills)} bills introduced since Dec 1")
    
    # Method 2: Fetch all bills for 2026
    print("\n2. Fetching all bills for 2026 session...")
    year_bills = fetch_legislation_by_year()
    new_from_year = 0
    for bill in year_bills:
        if bill['id'] not in all_bills:
            all_bills[bill['id']] = bill
            new_from_year += 1
    print(f"   Found {len(year_bills)} bills for 2026 ({new_from_year} new)")
    
    # Method 3: Fetch all bills for the biennium
    print("\n3. Fetching all bills for biennium 2025-26...")
    biennium_bills = fetch_legislation_info_by_biennium()
    new_from_biennium = 0
    for bill in biennium_bills:
        if bill['id'] not in all_bills:
            all_bills[bill['id']] = bill
            new_from_biennium += 1
    print(f"   Found {len(biennium_bills)} bills for biennium ({new_from_biennium} new)")
    
    # Method 4: Fetch bills with recent status changes
    print("\n4. Fetching bills with recent status changes...")
    begin_date = "2025-12-01T00:00:00"
    end_date = datetime.now().isoformat()
    status_bills = fetch_legislation_by_status_change(begin_date, end_date)
    new_from_status = 0
    for bill in status_bills:
        if bill['id'] not in all_bills:
            all_bills[bill['id']] = bill
            new_from_status += 1
    print(f"   Found {len(status_bills)} bills with status changes ({new_from_status} new)")
    
    # Convert to list
    final_bills = list(all_bills.values())
    
    print("\n" + "=" * 60)
    print(f"Total unique bills collected: {len(final_bills)}")
    
    if final_bills:
        # Show sample bills
        print("\nSample bills found:")
        for bill in final_bills[:5]:
            print(f"  - {bill['number']}: {bill['title']}")
    
    # Save data
    save_bills_data(final_bills)
    
    print("=" * 60)
    print(f"Update complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
