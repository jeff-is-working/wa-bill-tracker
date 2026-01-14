#!/usr/bin/env python3
"""
Washington State Legislature Bill Fetcher - 2026 Session
Fetches bills for the 2026 legislative session (second year of 2025-26 biennium)
Session runs from January 12, 2026 to March 12, 2026
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
CURRENT_YEAR = 2026  # We want 2026 session bills
SESSION_YEAR = 2026
DATA_DIR = Path("data")

# SOAP Service Endpoints
LEGISLATION_SERVICE = f"{BASE_API_URL}/LegislationService.asmx"
COMMITTEE_MEETING_SERVICE = f"{BASE_API_URL}/CommitteeMeetingService.asmx"
SPONSOR_SERVICE = f"{BASE_API_URL}/SponsorService.asmx"

def ensure_data_dir():
    """Ensure data directory exists"""
    DATA_DIR.mkdir(exist_ok=True)

def make_soap_request(url: str, soap_body: str, soap_action: str, debug: bool = False) -> Optional[ET.Element]:
    """Make SOAP request to WA Legislature API"""
    headers = {
        'Content-Type': 'text/xml; charset=utf-8',
        'SOAPAction': soap_action
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
        print(f"Making request to: {url}")
        print(f"SOAP Action: {soap_action}")
    
    try:
        response = requests.post(url, data=soap_envelope, headers=headers, timeout=60)
        if response.status_code == 200:
            if debug:
                # Save first response for debugging
                debug_file = DATA_DIR / 'debug_response.xml'
                ensure_data_dir()
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print(f"  Debug response saved to {debug_file}")
            
            root = ET.fromstring(response.content)
            return root
        else:
            print(f"API Error {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        return None

def parse_legislation_info(elem: ET.Element) -> Optional[Dict]:
    """Parse a LegislationInfo element from the SOAP response"""
    try:
        # Helper to get text from child element
        def get_text(parent, tag_name: str, default: str = '') -> str:
            """Extract text from child element regardless of namespace"""
            # Try direct child
            for child in parent:
                child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if child_tag == tag_name:
                    if child.text:
                        return child.text.strip()
            
            # Try searching deeper
            for elem in parent.iter():
                elem_tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if elem_tag == tag_name:
                    if elem.text:
                        return elem.text.strip()
            
            return default
        
        # Extract basic fields
        biennium = get_text(elem, 'Biennium', BIENNIUM)
        bill_id = get_text(elem, 'BillId', '')
        bill_number = get_text(elem, 'BillNumber', '')
        
        # Skip if no bill identifier
        if not bill_id and not bill_number:
            return None
        
        # Get title and description
        short_desc = get_text(elem, 'ShortDescription', '')
        long_desc = get_text(elem, 'LongDescription', '')
        
        # Skip bills with no title
        if not short_desc and not long_desc:
            return None
        
        title = short_desc if short_desc else (long_desc[:100] + '...' if len(long_desc) > 100 else long_desc)
        
        # Format bill number
        if bill_id:
            # Handle formats like "HB 1001", "SB 5001", "2SHB 1234", etc.
            # Extract the core bill type and number
            match = re.search(r'([A-Z]+)\s*(\d+)', bill_id)
            if match:
                number = match.group(2)
                
                # Determine core bill type
                if 'HB' in bill_id:
                    bill_type = 'HB'
                elif 'SB' in bill_id:
                    bill_type = 'SB'
                elif 'HJR' in bill_id:
                    bill_type = 'HJR'
                elif 'SJR' in bill_id:
                    bill_type = 'SJR'
                elif 'HJM' in bill_id:
                    bill_type = 'HJM'
                elif 'SJM' in bill_id:
                    bill_type = 'SJM'
                elif 'HCR' in bill_id:
                    bill_type = 'HCR'
                elif 'SCR' in bill_id:
                    bill_type = 'SCR'
                else:
                    bill_type = match.group(1)
                
                formatted_number = f"{bill_type} {number}"
                formatted_id = f"{bill_type}{number}"
            else:
                formatted_number = bill_id
                formatted_id = bill_id.replace(' ', '')
        else:
            formatted_number = f"BILL {bill_number}"
            formatted_id = f"BILL{bill_number}"
        
        # Get sponsor
        prime_sponsor = get_text(elem, 'PrimeSponsor', '')
        if not prime_sponsor:
            prime_sponsor = get_text(elem, 'RequestedBy', 'Unknown')
        
        # Get status
        status = get_text(elem, 'Status', '')
        if not status:
            # Try CurrentStatus child element
            current_status = None
            for child in elem:
                child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if child_tag == 'CurrentStatus':
                    current_status = child
                    break
            
            if current_status is not None:
                status = get_text(current_status, 'Status', 'Introduced')
            else:
                status = 'Introduced'
        
        # Get introduced date
        introduced_date = get_text(elem, 'IntroducedDate', '')
        if introduced_date:
            try:
                # Parse various date formats
                if 'T' in introduced_date:
                    dt = datetime.fromisoformat(introduced_date.replace('Z', '+00:00').split('T')[0])
                else:
                    dt = datetime.strptime(introduced_date, '%Y-%m-%d')
                introduced_date = dt.strftime('%Y-%m-%d')
            except:
                introduced_date = ''
        
        # Get committee
        committee = get_text(elem, 'CurrentCommittee', '')
        if not committee:
            committee = get_text(elem, 'Committee', '')
        if not committee:
            # Assign default committee based on bill type
            if formatted_number.startswith('HB'):
                committee = "House Rules"
            elif formatted_number.startswith('SB'):
                committee = "Senate Rules"
            else:
                committee = "Rules"
        
        # Build bill object matching app.js structure
        bill = {
            "id": formatted_id,
            "number": formatted_number,
            "title": title,
            "sponsor": prime_sponsor,
            "description": long_desc if long_desc else title,
            "status": status,
            "committee": committee,
            "priority": determine_priority(title),
            "topic": determine_topic(title),
            "introducedDate": introduced_date,
            "lastUpdated": datetime.now().isoformat(),
            "legUrl": f"{BASE_WEB_URL}/billsummary?BillNumber={number if 'number' in locals() else bill_number}&Year={SESSION_YEAR}",
            "hearings": [],
            "biennium": biennium
        }
        
        return bill
        
    except Exception as e:
        print(f"Error parsing legislation: {e}")
        return None

def fetch_2026_session_bills() -> List[Dict]:
    """Fetch all bills for the 2026 legislative session including pre-filed bills"""
    all_bills = {}
    
    # Method 1: Get pre-filed bills (filed in late 2025 for 2026 session)
    print(f"\n📋 Fetching pre-filed bills for 2026 session...")
    
    # Get bills introduced since December 1, 2025 (pre-filing period)
    since_date = "2025-12-01T00:00:00"
    
    soap_body = f"""
    <GetLegislationIntroducedSince xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
      <sinceDate>{since_date}</sinceDate>
    </GetLegislationIntroducedSince>"""
    
    root = make_soap_request(
        LEGISLATION_SERVICE,
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislationIntroducedSince",
        debug=True  # Enable debug for first request
    )
    
    if root:
        prefiled_count = 0
        for elem in root.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag_name == 'LegislationInfo':
                bill_data = parse_legislation_info(elem)
                if bill_data:
                    all_bills[bill_data['id']] = bill_data
                    prefiled_count += 1
                    if prefiled_count <= 5:  # Show first few bills
                        print(f"  ✓ Found: {bill_data['number']} - {bill_data['title'][:50]}...")
        
        print(f"  Found {prefiled_count} bills introduced since Dec 1, 2025")
    else:
        print("  ❌ No response from GetLegislationIntroducedSince")
    
    # Method 2: GetLegislationByYear for 2026
    print(f"\n📋 Fetching all bills for {SESSION_YEAR} session...")
    
    soap_body = f"""
    <GetLegislationByYear xmlns="http://WSLWebServices.leg.wa.gov/">
      <year>{SESSION_YEAR}</year>
    </GetLegislationByYear>"""
    
    root = make_soap_request(
        LEGISLATION_SERVICE,
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislationByYear"
    )
    
    if root:
        year_bills_count = 0
        for elem in root.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag_name == 'LegislationInfo':
                bill_data = parse_legislation_info(elem)
                if bill_data and bill_data['id'] not in all_bills:
                    all_bills[bill_data['id']] = bill_data
                    year_bills_count += 1
        
        print(f"  Added {year_bills_count} additional bills from 2026")
    
    # Method 3: GetPrefiledLegislationInfo for the biennium
    print(f"\n📋 Fetching pre-filed legislation for {BIENNIUM} biennium...")
    
    soap_body = f"""
    <GetPrefiledLegislationInfo xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
    </GetPrefiledLegislationInfo>"""
    
    root = make_soap_request(
        LEGISLATION_SERVICE,
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetPrefiledLegislationInfo"
    )
    
    if root:
        biennium_prefiled_count = 0
        for elem in root.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag_name == 'LegislationInfo':
                bill_data = parse_legislation_info(elem)
                if bill_data and bill_data['id'] not in all_bills:
                    all_bills[bill_data['id']] = bill_data
                    biennium_prefiled_count += 1
        
        print(f"  Added {biennium_prefiled_count} additional pre-filed bills")
    
    # Method 4: GetLegislativeStatusChangesByDateRange for recent activity
    print(f"\n📋 Fetching bills with recent status changes...")
    
    # Get bills with status changes from Dec 1, 2025 to today
    begin_date = "2025-12-01"
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    soap_body = f"""
    <GetLegislativeStatusChangesByDateRange xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
      <beginDate>{begin_date}</beginDate>
      <endDate>{end_date}</endDate>
    </GetLegislativeStatusChangesByDateRange>"""
    
    root = make_soap_request(
        LEGISLATION_SERVICE,
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetLegislativeStatusChangesByDateRange"
    )
    
    if root:
        status_changes_count = 0
        for elem in root.iter():
            tag_name = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag_name == 'LegislationInfo':
                bill_data = parse_legislation_info(elem)
                if bill_data and bill_data['id'] not in all_bills:
                    all_bills[bill_data['id']] = bill_data
                    status_changes_count += 1
        
        print(f"  Added {status_changes_count} bills with recent status changes")
    
    # Convert to list
    bills = list(all_bills.values())
    
    print(f"\n📊 Total unique bills found: {len(bills)}")
    
    return bills

def fetch_hearings_for_bills(bills: List[Dict]) -> None:
    """Fetch hearing information for bills"""
    print("\n📅 Fetching committee hearing information...")
    
    soap_body = f"""
    <GetCommitteeMeetings xmlns="http://WSLWebServices.leg.wa.gov/">
      <biennium>{BIENNIUM}</biennium>
    </GetCommitteeMeetings>"""
    
    root = make_soap_request(
        COMMITTEE_MEETING_SERVICE,
        soap_body,
        "http://WSLWebServices.leg.wa.gov/GetCommitteeMeetings"
    )
    
    if root:
        hearings_count = 0
        # Create a map of bill IDs to hearings
        hearings_map = {}
        
        for meeting in root.iter():
            meeting_tag = meeting.tag.split('}')[-1] if '}' in meeting.tag else meeting.tag
            if meeting_tag == 'Meeting':
                # Extract meeting details
                meeting_date = ''
                meeting_time = ''
                committee_name = ''
                
                for child in meeting:
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if child_tag == 'Date' and child.text:
                        meeting_date = child.text.split('T')[0]
                    elif child_tag == 'Time' and child.text:
                        meeting_time = child.text
                    elif child_tag == 'CommitteeName' and child.text:
                        committee_name = child.text
                
                # Look for agenda items with bills
                for agenda in meeting.iter():
                    agenda_tag = agenda.tag.split('}')[-1] if '}' in agenda.tag else agenda.tag
                    if agenda_tag == 'AgendaItem':
                        for item_child in agenda:
                            item_tag = item_child.tag.split('}')[-1] if '}' in item_child.tag else item_child.tag
                            if item_tag == 'BillId' and item_child.text:
                                bill_id = item_child.text.strip()
                                
                                # Create hearing entry
                                hearing = {
                                    "date": meeting_date,
                                    "time": meeting_time,
                                    "committee": committee_name,
                                    "type": "Public Hearing"
                                }
                                
                                # Map hearing to bill
                                if bill_id not in hearings_map:
                                    hearings_map[bill_id] = []
                                hearings_map[bill_id].append(hearing)
                                hearings_count += 1
        
        # Apply hearings to bills
        bills_with_hearings = 0
        for bill in bills:
            # Check various possible bill ID formats
            bill_id_variations = [
                bill['number'].replace(' ', ''),  # "HB1001"
                bill['number'],  # "HB 1001"
                bill['id']  # "HB1001"
            ]
            
            for variant in bill_id_variations:
                if variant in hearings_map:
                    bill['hearings'] = hearings_map[variant]
                    bills_with_hearings += 1
                    break
        
        print(f"  Found {hearings_count} total hearings")
        print(f"  Matched hearings to {bills_with_hearings} bills")

def determine_topic(title: str) -> str:
    """Determine bill topic from title"""
    if not title:
        return "General Government"
    
    title_lower = title.lower()
    
    topic_keywords = {
        "Education": ["education", "school", "student", "teacher", "learning", "academic", "university", "college"],
        "Tax & Revenue": ["tax", "revenue", "budget", "fiscal", "finance", "appropriation", "fee", "levy"],
        "Housing": ["housing", "rent", "tenant", "landlord", "homelessness", "affordable", "eviction", "mortgage"],
        "Healthcare": ["health", "medical", "hospital", "mental", "pharmacy", "insurance", "medicare", "medicaid"],
        "Environment": ["environment", "climate", "energy", "pollution", "conservation", "sustainable", "clean", "emissions"],
        "Transportation": ["transportation", "road", "highway", "transit", "vehicle", "traffic", "driver", "ferry"],
        "Public Safety": ["crime", "safety", "police", "justice", "corrections", "emergency", "fire", "enforcement"],
        "Business": ["business", "commerce", "trade", "economy", "corporation", "employment", "labor", "workforce"],
        "Technology": ["technology", "internet", "data", "privacy", "cyber", "artificial intelligence", "digital", "broadband"],
        "Agriculture": ["agriculture", "farm", "rural", "livestock", "crop", "food", "agricultural", "farming"]
    }
    
    for topic, keywords in topic_keywords.items():
        if any(keyword in title_lower for keyword in keywords):
            return topic
    
    return "General Government"

def determine_priority(title: str) -> str:
    """Determine bill priority from title"""
    if not title:
        return "medium"
    
    title_lower = title.lower()
    
    # High priority keywords
    high_keywords = ["emergency", "budget", "appropriation", "supplemental", "capital", "crisis", "urgent"]
    if any(word in title_lower for word in high_keywords):
        return "high"
    
    # Low priority keywords
    low_keywords = ["technical", "clarifying", "housekeeping", "minor", "memorial", "commemorating", "recognizing"]
    if any(word in title_lower for word in low_keywords):
        return "low"
    
    return "medium"

def save_bills_data(bills: List[Dict]) -> Dict:
    """Save bills data to JSON file matching app.js structure"""
    # Sort bills by type and number
    def sort_key(bill):
        match = re.match(r'([A-Z]+)\s*(\d+)', bill['number'])
        if match:
            bill_type = match.group(1)
            number = int(match.group(2))
            # Sort order
            type_order = {'HB': 1, 'SB': 2, 'HJR': 3, 'SJR': 4, 'HJM': 5, 'SJM': 6, 'HCR': 7, 'SCR': 8}
            return (type_order.get(bill_type, 9), number)
        return (10, 0)
    
    bills.sort(key=sort_key)
    
    # Get unique bill types
    bill_types = []
    for bill in bills:
        match = re.match(r'([A-Z]+)', bill['number'])
        if match and match.group(1) not in bill_types:
            bill_types.append(match.group(1))
    
    data = {
        "lastSync": datetime.now().isoformat(),
        "sessionYear": SESSION_YEAR,
        "sessionStart": "2026-01-12",
        "sessionEnd": "2026-03-12",
        "totalBills": len(bills),
        "bills": bills,
        "metadata": {
            "source": "Washington State Legislature Web Services API",
            "apiVersion": "1.0",
            "updateFrequency": "hourly",
            "dataVersion": "7.0.0",
            "biennium": BIENNIUM,
            "billTypes": sorted(bill_types)
        }
    }
    
    ensure_data_dir()
    data_file = DATA_DIR / "bills.json"
    
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved {len(bills)} bills to {data_file}")
    return data

def create_stats_file(bills: List[Dict]):
    """Create statistics file"""
    stats = {
        "generated": datetime.now().isoformat(),
        "totalBills": len(bills),
        "byStatus": {},
        "byCommittee": {},
        "byPriority": {},
        "byTopic": {},
        "byType": {},
        "bySponsor": {}
    }
    
    for bill in bills:
        # By status
        status = bill.get('status', 'Unknown')
        stats['byStatus'][status] = stats['byStatus'].get(status, 0) + 1
        
        # By committee
        committee = bill.get('committee', 'Unknown')
        stats['byCommittee'][committee] = stats['byCommittee'].get(committee, 0) + 1
        
        # By priority
        priority = bill.get('priority', 'medium')
        stats['byPriority'][priority] = stats['byPriority'].get(priority, 0) + 1
        
        # By topic
        topic = bill.get('topic', 'General Government')
        stats['byTopic'][topic] = stats['byTopic'].get(topic, 0) + 1
        
        # By type
        match = re.match(r'([A-Z]+)', bill['number'])
        if match:
            bill_type = match.group(1)
            stats['byType'][bill_type] = stats['byType'].get(bill_type, 0) + 1
        
        # By sponsor
        sponsor = bill.get('sponsor', 'Unknown')
        if sponsor != 'Unknown':
            stats['bySponsor'][sponsor] = stats['bySponsor'].get(sponsor, 0) + 1
    
    stats_file = DATA_DIR / "stats.json"
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)
    
    print(f"📊 Statistics file created")

def main():
    """Main execution function"""
    print(f"🚀 Washington State Legislature Bill Fetcher - 2026 Session")
    print(f"📅 Session: January 12, 2026 - March 12, 2026")
    print(f"📚 Biennium: {BIENNIUM}")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    try:
        # Fetch all bills for 2026 session
        bills = fetch_2026_session_bills()
        
        # Remove any duplicate bills
        unique_bills = {}
        for bill in bills:
            unique_bills[bill['id']] = bill
        bills = list(unique_bills.values())
        
        # Fetch hearings if we have bills
        if bills:
            fetch_hearings_for_bills(bills)
        
        # Save data
        if bills:
            save_bills_data(bills)
            create_stats_file(bills)
            
            print("\n" + "=" * 60)
            print(f"✅ Successfully processed {len(bills)} bills")
            
            # Show summary
            bill_types = {}
            for bill in bills:
                match = re.match(r'([A-Z]+)', bill['number'])
                if match:
                    bill_type = match.group(1)
                    bill_types[bill_type] = bill_types.get(bill_type, 0) + 1
            
            if bill_types:
                print("\n📊 Bills by type:")
                for bill_type, count in sorted(bill_types.items()):
                    print(f"  {bill_type}: {count}")
            
            # Show sample bills
            print("\n📋 Sample bills:")
            for bill in bills[:5]:
                print(f"  • {bill['number']}: {bill['title'][:60]}...")
        else:
            print("\n⚠️  No bills retrieved from API")
            print("   The 2026 session may not have bills available yet.")
            print("   Session dates: January 12 - March 12, 2026")
            
            # Save empty structure
            save_bills_data([])
            create_stats_file([])
        
        print(f"\n⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
