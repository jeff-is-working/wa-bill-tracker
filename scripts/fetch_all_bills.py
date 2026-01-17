#!/usr/bin/env python3
"""
Washington State Legislature Bill Fetcher
Uses ACTUAL documented API methods from the WA Legislature Web Services
Based on https://wslwebservices.leg.wa.gov/LegislationService.asmx?WSDL
Fixed version using correct method names and XML parsing
"""

import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os
from pathlib import Path
import time
from typing import Dict, List, Optional
import re

# Configuration
BASE_API_URL = "https://wslwebservices.leg.wa.gov"
BASE_WEB_URL = "https://app.leg.wa.gov"
BIENNIUM = "2025-26"
YEAR = 2025
DATA_DIR = Path("data")

# SOAP Service Endpoints
LEGISLATION_SERVICE = f"{BASE_API_URL}/LegislationService.asmx"

def ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(exist_ok=True)

def make_soap_request(soap_body: str, soap_action: str, debug: bool = False) -> Optional[ET.Element]:
    """Make SOAP request to WA Legislature API"""
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': f'"{soap_action}"'  # SOAPAction must be quoted
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
        print(f"SOAP Action: {soap_action}")
        with open('debug_request.xml', 'w') as f:
            f.write(soap_envelope)
        print("Request saved to debug_request.xml")
    
    try:
        response = requests.post(LEGISLATION_SERVICE, 
                                data=soap_envelope, 
                                headers=headers, 
                                timeout=120)
        
        if debug:
            print(f"Response Status: {response.status_code}")
            with open('debug_response.xml', 'w') as f:
                f.write(response.text)
            print("Response saved to debug_response.xml")
        
        if response.status_code == 200:
            # Check for SOAP faults
            if 'soap:Fault' in response.text:
                print("SOAP Fault detected:")
                try:
                    fault_root = ET.fromstring(response.text)
                    fault_string = fault_root.find('.//faultstring')
                    if fault_string is not None:
                        print(f"Fault: {fault_string.text}")
                except:
                    print(response.text[:500])
                return None
            
            try:
                root = ET.fromstring(response.text)
                return root
            except ET.ParseError as e:
                print(f"XML Parse Error: {e}")
                return None
        else:
            print(f"HTTP Error {response.status_code}")
            print(response.text[:500])
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None

def fetch_prefiled_legislation() -> List[Dict]:
    """Fetch prefiled legislation using GetPrefiledLegislation method"""
    print(f"Fetching prefiled legislation for biennium {BIENNIUM}")
    
    soap_body = f"""
    <GetPrefiledLegislation xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
    </GetPrefiledLegislation>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetPrefiledLegislation",
        debug=True
    )
    
    if root is None:
        return []
    
    return parse_legislation_response(root, "GetPrefiledLegislationResult")

def fetch_legislation_introduced_since(date: str) -> List[Dict]:
    """Fetch legislation introduced since a date using GetLegislationIntroducedSince"""
    print(f"Fetching legislation introduced since {date}")
    
    soap_body = f"""
    <GetLegislationIntroducedSince xmlns="http://WSLWebServices.leg.wa.gov/">
      <sinceDate>{date}</sinceDate>
    </GetLegislationIntroducedSince>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislationIntroducedSince",
        debug=True
    )
    
    if root is None:
        return []
    
    return parse_legislation_response(root, "GetLegislationIntroducedSinceResult")

def fetch_legislation_by_year() -> List[Dict]:
    """Fetch legislation by year using GetLegislationByYear"""
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
    
    return parse_legislation_response(root, "GetLegislationByYearResult")

def fetch_legislation_by_request_number(request_number: str) -> List[Dict]:
    """Fetch specific legislation by request number using GetLegislationByRequestNumber"""
    print(f"Fetching legislation by request number {request_number}")
    
    soap_body = f"""
    <GetLegislationByRequestNumber xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
      <requestNumber>{request_number}</requestNumber>
    </GetLegislationByRequestNumber>"""
    
    root = make_soap_request(
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislationByRequestNumber",
        debug=True
    )
    
    if root is None:
        return []
    
    return parse_legislation_response(root, "GetLegislationByRequestNumberResult")

def parse_legislation_response(root: ET.Element, result_element: str) -> List[Dict]:
    """Parse XML response and extract legislation info"""
    bills = []
    
    # Remove namespaces by converting to string and back
    xml_str = ET.tostring(root, encoding='unicode')
    # Remove namespace declarations to simplify parsing
    xml_str = re.sub(r'xmlns[^=]*="[^"]*"', '', xml_str)
    
    try:
        clean_root = ET.fromstring(xml_str)
    except ET.ParseError:
        print("Could not parse cleaned XML")
        return []
    
    # Look for the specific result element and then LegislationInfo elements
    result_containers = clean_root.findall(f'.//{result_element}')
    
    legislation_elements = []
    for container in result_containers:
        # Look for LegislationInfo elements within the container
        leg_infos = container.findall('.//LegislationInfo')
        legislation_elements.extend(leg_infos)
    
    # If no containers found, search entire document
    if not legislation_elements:
        legislation_elements = clean_root.findall('.//LegislationInfo')
    
    print(f"Found {len(legislation_elements)} LegislationInfo elements")
    
    # Debug: Show structure of first element
    if legislation_elements and len(legislation_elements) > 0:
        print("\nSample element structure:")
        sample = legislation_elements[0]
        for child in sample:
            if child.text and child.text.strip():
                print(f"  {child.tag}: {child.text.strip()}")
    
    for i, leg_elem in enumerate(legislation_elements):
        bill = parse_legislation_element(leg_elem)
        if bill:
            bills.append(bill)
            if i < 3:  # Show first 3 for debugging
                print(f"  Parsed: {bill['number']} - {bill['title'][:60]}...")
    
    return bills

def parse_legislation_element(elem: ET.Element) -> Optional[Dict]:
    """Parse a single LegislationInfo element"""
    try:
        def get_text(tag: str, default: str = "") -> str:
            """Get text from element safely"""
            child = elem.find(tag)
            if child is not None and child.text:
                return child.text.strip()
            return default
        
        # Extract key identifiers
        biennium = get_text('Biennium', BIENNIUM)
        bill_id = get_text('BillId')
        bill_number = get_text('BillNumber')
        
        if not bill_id and not bill_number:
            return None
        
        # Get title and description
        short_desc = get_text('ShortDescription')
        long_desc = get_text('LongDescription')
        legal_title = get_text('LegalTitle')
        
        title = short_desc or legal_title or long_desc
        if not title or len(title.strip()) == 0:
            return None
        
        # Get bill number formatting info
        substitute_version = get_text('SubstituteVersion', '')
        engrossed_version = get_text('EngrossedVersion', '')
        original_agency = get_text('OriginalAgency', '')
        display_number = get_text('DisplayNumber', '')
        active = get_text('Active', 'true')
        
        # Build proper bill number
        if display_number:
            full_number = display_number
        else:
            full_number = build_bill_number(bill_number, original_agency, substitute_version, engrossed_version)
        
        # Get sponsor information
        prime_sponsor = get_text('PrimeSponsor', '')
        requested_by = get_text('RequestedBy', '')
        sponsor = prime_sponsor or requested_by or "Unknown"
        
        # Get status information
        current_status = get_text('CurrentStatus', '')
        history_line = get_text('HistoryLine', '')
        status = determine_bill_status(current_status, history_line, active)
        
        # Get dates
        introduced_date = get_text('IntroducedDate', '')
        prefiled_date = get_text('PrefiledDate', '')
        
        # Use best available date
        bill_date = introduced_date or prefiled_date or "2025-12-01"
        
        # Format date properly
        try:
            if 'T' in bill_date:
                dt = datetime.fromisoformat(bill_date.replace('Z', '+00:00'))
                formatted_date = dt.date().isoformat()
            else:
                formatted_date = bill_date[:10] if len(bill_date) >= 10 else "2025-12-01"
        except:
            formatted_date = "2025-12-01"
        
        # Build bill object
        bill = {
            "id": bill_id or f"bill_{bill_number}",
            "number": full_number,
            "billNumber": bill_number,
            "title": title,
            "sponsor": sponsor,
            "description": long_desc or f"A bill relating to {title.lower()}",
            "status": status,
            "committee": determine_committee(full_number, title),
            "priority": determine_priority(title),
            "topic": determine_topic(title),
            "introducedDate": formatted_date,
            "lastUpdated": datetime.now().isoformat(),
            "legUrl": f"{BASE_WEB_URL}/billsummary?BillNumber={bill_number}&Year=2026",
            "biennium": biennium,
            "active": active.lower() == 'true',
            "hearings": []
        }
        
        return bill
        
    except Exception as e:
        print(f"Error parsing element: {e}")
        return None

def build_bill_number(bill_number: str, original_agency: str, substitute_version: str, engrossed_version: str) -> str:
    """Build full bill number with proper prefix"""
    
    # Determine bill type prefix
    if 'House' in original_agency:
        prefix = 'HB'
    elif 'Senate' in original_agency:
        prefix = 'SB'
    else:
        # Guess from number range
        try:
            num = int(bill_number)
            if num >= 5000:
                prefix = 'SB'
            elif num >= 4000:
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
    
    # Add version prefixes
    version_prefix = ''
    if substitute_version:
        if '2S' in substitute_version:
            version_prefix = '2S'
        elif 'S' in substitute_version:
            version_prefix = 'S'
    
    if engrossed_version and 'E' in engrossed_version:
        version_prefix += 'E'
    
    # Combine parts
    if version_prefix:
        return f"{version_prefix}{prefix} {bill_number}"
    else:
        return f"{prefix} {bill_number}"

def determine_bill_status(current_status: str, history_line: str, active: str) -> str:
    """Determine standardized bill status"""
    status_text = f"{current_status} {history_line}".lower()
    
    if active.lower() == 'false':
        return 'failed'
    elif any(word in status_text for word in ['signed', 'law', 'enacted']):
        return 'enacted'
    elif any(word in status_text for word in ['vetoed', 'veto']):
        return 'vetoed'
    elif any(word in status_text for word in ['passed legislature', 'passed both']):
        return 'passed'
    elif any(word in status_text for word in ['delivered to governor']):
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
    """Determine committee based on bill content"""
    title_lower = title.lower()
    
    committees = {
        "Education": ["education", "school", "student", "teacher", "learning"],
        "Transportation": ["transportation", "road", "highway", "transit", "vehicle"],
        "Housing": ["housing", "rent", "tenant", "landlord", "homeless"],
        "Health & Long-Term Care": ["health", "medical", "hospital", "mental", "behavioral"],
        "Environment & Energy": ["environment", "climate", "energy", "pollution", "conservation"],
        "Finance": ["tax", "revenue", "fiscal", "budget", "appropriation"],
        "Ways & Means": ["budget", "fiscal", "appropriation", "revenue"],
        "Consumer Protection & Business": ["consumer", "business", "commerce", "trade"],
        "Law & Justice": ["crime", "criminal", "justice", "police", "court"],
        "Labor & Commerce": ["labor", "employment", "worker", "wage", "workplace"],
        "Agriculture": ["agriculture", "farm", "food", "rural"],
        "State Government & Tribal Relations": ["state", "government", "tribal", "election"]
    }
    
    for committee, keywords in committees.items():
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
    """Determine topic from title"""
    title_lower = title.lower()
    
    topics = {
        "Education": ["education", "school", "student", "teacher"],
        "Tax & Revenue": ["tax", "revenue", "budget", "fiscal"],
        "Housing": ["housing", "rent", "tenant", "homeless"],
        "Healthcare": ["health", "medical", "hospital", "mental"],
        "Environment": ["environment", "climate", "energy", "conservation"],
        "Transportation": ["transport", "road", "highway", "transit"],
        "Public Safety": ["crime", "safety", "police", "justice"],
        "Business": ["business", "commerce", "trade", "economy"],
        "Technology": ["technology", "internet", "data", "privacy"],
        "Labor": ["labor", "employment", "worker", "wage"]
    }
    
    for topic, keywords in topics.items():
        if any(keyword in title_lower for keyword in keywords):
            return topic
    
    return "General Government"

def determine_priority(title: str) -> str:
    """Determine priority from title"""
    title_lower = title.lower()
    
    if any(word in title_lower for word in ['emergency', 'urgent', 'budget', 'supplemental']):
        return "high"
    elif any(word in title_lower for word in ['technical', 'clarifying', 'housekeeping']):
        return "low"
    
    return "medium"

def save_bills_data(bills: List[Dict]) -> Dict:
    """Save bills to JSON file"""
    # Remove duplicates
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
            return (match.group(1), int(match.group(2)))
        return ('ZZ', 99999)
    
    bills.sort(key=sort_key)
    
    data = {
        "lastSync": datetime.now().isoformat(),
        "sessionYear": 2026,
        "biennium": BIENNIUM,
        "sessionStart": "2026-01-12",
        "sessionEnd": "2026-03-12",
        "totalBills": len(bills),
        "bills": bills,
        "metadata": {
            "source": "Washington State Legislature Web Services",
            "apiUrl": BASE_API_URL,
            "updateFrequency": "daily",
            "dataVersion": "4.0.0",
            "methods": ["GetPrefiledLegislation", "GetLegislationIntroducedSince", "GetLegislationByYear"]
        }
    }
    
    data_file = DATA_DIR / "bills.json"
    with open(data_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Saved {len(bills)} bills to {data_file}")
    return data

def main():
    """Main execution function"""
    print(f"Starting WA Legislature Bill Fetcher - {datetime.now()}")
    print("Using ACTUAL documented API methods")
    print("=" * 60)
    
    ensure_data_dir()
    
    all_bills = {}
    
    # Method 1: Get prefiled legislation
    print("\n1. Fetching prefiled legislation...")
    try:
        prefiled_bills = fetch_prefiled_legislation()
        for bill in prefiled_bills:
            if bill['id'] not in all_bills:
                all_bills[bill['id']] = bill
        print(f"   Found {len(prefiled_bills)} prefiled bills")
    except Exception as e:
        print(f"   Error with GetPrefiledLegislation: {e}")
    
    # Method 2: Get legislation introduced since Dec 1
    print("\n2. Fetching legislation introduced since December 1, 2025...")
    try:
        since_date = "2025-12-01T00:00:00"
        introduced_bills = fetch_legislation_introduced_since(since_date)
        new_introduced = 0
        for bill in introduced_bills:
            if bill['id'] not in all_bills:
                all_bills[bill['id']] = bill
                new_introduced += 1
        print(f"   Found {len(introduced_bills)} introduced bills ({new_introduced} new)")
    except Exception as e:
        print(f"   Error with GetLegislationIntroducedSince: {e}")
    
    # Method 3: Get legislation by year (this worked before)
    print("\n3. Fetching legislation by year...")
    try:
        year_bills = fetch_legislation_by_year()
        new_year = 0
        for bill in year_bills:
            if bill['id'] not in all_bills:
                all_bills[bill['id']] = bill
                new_year += 1
        print(f"   Found {len(year_bills)} year bills ({new_year} new)")
    except Exception as e:
        print(f"   Error with GetLegislationByYear: {e}")
    
    # If still no bills, try a specific request number test
    if len(all_bills) == 0:
        print("\n4. Testing with specific request number...")
        try:
            # Try a more likely request number format
            test_bills = fetch_legislation_by_request_number("25-0001")
            for bill in test_bills:
                all_bills[bill['id']] = bill
            print(f"   Found {len(test_bills)} bills from test request")
        except Exception as e:
            print(f"   Error with test request: {e}")
    
    final_bills = list(all_bills.values())
    
    print(f"\n" + "=" * 60)
    print(f"Total unique bills collected: {len(final_bills)}")
    
    if final_bills:
        print("\nSample bills found:")
        for bill in final_bills[:5]:
            print(f"  {bill['number']}: {bill['title']}")
        
        save_bills_data(final_bills)
    else:
        print("No bills found. The API may not have data for this biennium yet.")
        print("Check debug_response.xml files for API responses.")
    
    print("=" * 60)
    print(f"Complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
