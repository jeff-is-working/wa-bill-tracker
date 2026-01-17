#!/usr/bin/env python3
"""
Washington State Legislature Bill Fetcher
Fetches all bills from the official WA Legislature SOAP API at wslwebservices.leg.wa.gov
for the 2025-26 biennium (2026 session).

This script interfaces directly with the Washington State Legislature Web Services
and outputs data compatible with the WA Bill Tracker web application.
"""

import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
import logging
import sys
import re

# Configuration
CONFIG = {
    "base_url": "https://wslwebservices.leg.wa.gov",
    "biennium": "2025-26",
    "year": 2026,
    "session_start": "2026-01-12",
    "session_end": "2026-03-12",
    "data_dir": Path("data"),
    "request_delay": 0.5,  # seconds between API requests
    "timeout": 30,  # request timeout in seconds
}

# XML Namespaces used by the WA Legislature API
NAMESPACES = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "soap12": "http://www.w3.org/2003/05/soap-envelope",
    "ws": "http://WSLWebServices.leg.wa.gov/",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "xsd": "http://www.w3.org/2001/XMLSchema",
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


def ensure_data_dir():
    """Create data directory if it does not exist."""
    CONFIG["data_dir"].mkdir(exist_ok=True)


def build_soap_envelope(method_name: str, params: Dict[str, Any]) -> str:
    """
    Build a SOAP 1.1 envelope for the given method and parameters.
    
    Args:
        method_name: The name of the SOAP method to call
        params: Dictionary of parameter names and values
        
    Returns:
        SOAP XML envelope as a string
    """
    param_xml = ""
    for key, value in params.items():
        param_xml += f"<{key}>{value}</{key}>"
    
    envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
               xmlns:xsd="http://www.w3.org/2001/XMLSchema" 
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <{method_name} xmlns="http://WSLWebServices.leg.wa.gov/">
      {param_xml}
    </{method_name}>
  </soap:Body>
</soap:Envelope>'''
    return envelope


def call_soap_service(service_name: str, method_name: str, params: Dict[str, Any]) -> Optional[ET.Element]:
    """
    Call a SOAP web service method and return the parsed XML response.
    
    Args:
        service_name: Name of the service (e.g., "LegislationService")
        method_name: Name of the method to call
        params: Dictionary of parameters
        
    Returns:
        ElementTree Element of the response body, or None if failed
    """
    url = f"{CONFIG['base_url']}/{service_name}.asmx"
    soap_action = f"http://WSLWebServices.leg.wa.gov/{method_name}"
    
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": soap_action,
    }
    
    body = build_soap_envelope(method_name, params)
    
    try:
        logger.debug(f"Calling {service_name}.{method_name} with params: {params}")
        response = requests.post(url, data=body.encode("utf-8"), headers=headers, timeout=CONFIG["timeout"])
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.content)
        
        # Extract the body content
        body_elem = root.find(".//soap:Body", NAMESPACES)
        if body_elem is None:
            body_elem = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Body")
        
        if body_elem is not None and len(body_elem) > 0:
            return body_elem[0]
        
        return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error calling {service_name}.{method_name}: {e}")
        return None
    except ET.ParseError as e:
        logger.error(f"XML parse error for {service_name}.{method_name}: {e}")
        return None


def get_text(element: Optional[ET.Element], tag: str, default: str = "") -> str:
    """
    Extract text content from an XML element by tag name.
    Handles namespaced and non-namespaced elements.
    """
    if element is None:
        return default
    
    # Try without namespace first
    child = element.find(tag)
    if child is None:
        # Try with namespace
        child = element.find(f"{{http://WSLWebServices.leg.wa.gov/}}{tag}")
    if child is None:
        # Try with ws namespace prefix
        child = element.find(f"ws:{tag}", NAMESPACES)
    
    if child is not None and child.text:
        return child.text.strip()
    return default


def get_bool(element: Optional[ET.Element], tag: str, default: bool = False) -> bool:
    """Extract boolean value from an XML element."""
    text = get_text(element, tag, "").lower()
    if text in ("true", "1"):
        return True
    if text in ("false", "0"):
        return False
    return default


def parse_legislation_element(leg_elem: ET.Element) -> Optional[Dict]:
    """
    Parse a Legislation XML element into a dictionary.
    
    Args:
        leg_elem: XML Element representing a piece of legislation
        
    Returns:
        Dictionary with bill data, or None if parsing failed
    """
    try:
        # Get basic bill information
        biennium = get_text(leg_elem, "Biennium", CONFIG["biennium"])
        bill_id = get_text(leg_elem, "BillId")
        bill_number = get_text(leg_elem, "BillNumber")
        
        if not bill_id and not bill_number:
            return None
        
        # Extract bill number integer from BillId or BillNumber
        bill_num_int = ""
        if bill_number:
            bill_num_int = bill_number
        elif bill_id:
            # BillId format is like "HB 1001" or "SB 5001"
            parts = bill_id.split()
            if len(parts) >= 2:
                bill_num_int = parts[1]
        
        # Get original agency (House or Senate)
        original_agency = get_text(leg_elem, "OriginalAgency", "")
        
        # Determine bill type prefix
        bill_prefix = ""
        if bill_id:
            parts = bill_id.split()
            if parts:
                bill_prefix = parts[0]
        elif original_agency:
            if original_agency.lower() == "house":
                bill_prefix = "HB"
            elif original_agency.lower() == "senate":
                bill_prefix = "SB"
        
        # Construct standardized bill number
        if bill_prefix and bill_num_int:
            standard_number = f"{bill_prefix} {bill_num_int}"
        else:
            standard_number = bill_id if bill_id else f"Bill {bill_number}"
        
        # Get descriptions
        short_description = get_text(leg_elem, "ShortDescription", "")
        long_description = get_text(leg_elem, "LongDescription", "")
        legal_title = get_text(leg_elem, "LegalTitle", "")
        
        # Use the best available title
        title = short_description or long_description or legal_title or "No title available"
        
        # Get sponsor information
        prime_sponsor_id = get_text(leg_elem, "PrimeSponsorID")
        sponsor_name = ""
        
        # Try to get sponsor from nested Sponsor element
        sponsor_elem = leg_elem.find("Sponsor")
        if sponsor_elem is None:
            sponsor_elem = leg_elem.find("{http://WSLWebServices.leg.wa.gov/}Sponsor")
        if sponsor_elem is not None:
            sponsor_name = get_text(sponsor_elem, "Name")
            if not sponsor_name:
                sponsor_name = get_text(sponsor_elem, "LongName")
        
        if not sponsor_name:
            # Try to get from CurrentStatus/Sponsor if available
            status_elem = leg_elem.find("CurrentStatus")
            if status_elem is None:
                status_elem = leg_elem.find("{http://WSLWebServices.leg.wa.gov/}CurrentStatus")
            if status_elem is not None:
                sponsor_name = get_text(status_elem, "Sponsor")
        
        # If no sponsor name found, use agency-based default
        if not sponsor_name:
            if original_agency.lower() == "house":
                sponsor_name = "House Member"
            elif original_agency.lower() == "senate":
                sponsor_name = "Senator"
            else:
                sponsor_name = "Unknown Sponsor"
        
        # Get introduced date
        introduced_date = get_text(leg_elem, "IntroducedDate", "")
        if introduced_date:
            # Parse and reformat date
            try:
                dt = datetime.fromisoformat(introduced_date.replace("Z", "+00:00"))
                introduced_date = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
        
        # Parse current status
        status = "prefiled"
        status_elem = leg_elem.find("CurrentStatus")
        if status_elem is None:
            status_elem = leg_elem.find("{http://WSLWebServices.leg.wa.gov/}CurrentStatus")
        if status_elem is not None:
            status_text = get_text(status_elem, "Status", "")
            history_line = get_text(status_elem, "HistoryLine", "")
            action_date = get_text(status_elem, "ActionDate", "")
            
            # Determine status from status text and history
            status = determine_bill_status(status_text, history_line)
        
        # Check for active flag
        is_active = get_bool(leg_elem, "Active", True)
        
        # Get request number if available
        request_number = get_text(leg_elem, "RequestNumber", "")
        
        # Build the bill data dictionary
        bill_data = {
            "id": bill_id.replace(" ", "") if bill_id else f"{bill_prefix}{bill_num_int}",
            "number": standard_number,
            "title": title,
            "sponsor": sponsor_name,
            "description": long_description or short_description or f"A bill relating to {title.lower()}",
            "status": status,
            "committee": "",  # Will be populated separately if needed
            "priority": determine_priority(title, status),
            "topic": determine_topic(title),
            "introducedDate": introduced_date or CONFIG["session_start"],
            "lastUpdated": datetime.now().isoformat(),
            "legUrl": f"https://app.leg.wa.gov/billsummary?BillNumber={bill_num_int}&Year={CONFIG['year']}",
            "hearings": [],
            "active": is_active,
            "biennium": biennium,
        }
        
        return bill_data
        
    except Exception as e:
        logger.error(f"Error parsing legislation element: {e}")
        return None


def determine_bill_status(status_text: str, history_line: str) -> str:
    """
    Determine a standardized bill status from API status text and history.
    
    Args:
        status_text: The Status field from the API
        history_line: The HistoryLine field from the API
        
    Returns:
        Standardized status string
    """
    combined = (status_text + " " + history_line).lower()
    
    # Check for final statuses first
    if any(term in combined for term in ["signed by governor", "chapter", "effective", "enacted"]):
        return "enacted"
    if any(term in combined for term in ["vetoed", "veto"]):
        return "vetoed"
    if any(term in combined for term in ["passed legislature", "passed the legislature"]):
        return "passed"
    if any(term in combined for term in ["passed house", "passed senate", "third reading", "3rd reading"]):
        return "passed"
    if any(term in combined for term in ["failed", "dead", "died"]):
        return "failed"
    
    # Check for in-progress statuses
    if any(term in combined for term in ["committee", "referred to", "hearing"]):
        return "committee"
    if any(term in combined for term in ["first reading", "1st reading", "introduced"]):
        return "introduced"
    if any(term in combined for term in ["prefiled", "pre-filed"]):
        return "prefiled"
    
    # Default based on whether there's any status text
    if status_text or history_line:
        return "introduced"
    
    return "prefiled"


def determine_priority(title: str, status: str) -> str:
    """
    Determine bill priority based on title keywords and status.
    
    Args:
        title: Bill title
        status: Bill status
        
    Returns:
        Priority level: "high", "medium", or "low"
    """
    title_lower = title.lower()
    
    # High priority keywords
    high_keywords = [
        "emergency", "appropriation", "budget", "capital", "operating",
        "public safety", "crisis", "immediate", "essential", "critical",
        "education funding", "healthcare", "housing crisis", "tax relief"
    ]
    
    # Low priority keywords
    low_keywords = [
        "technical", "clarifying", "housekeeping", "minor",
        "study committee", "report", "renaming", "commemorating"
    ]
    
    # Check high priority
    for keyword in high_keywords:
        if keyword in title_lower:
            return "high"
    
    # Check low priority
    for keyword in low_keywords:
        if keyword in title_lower:
            return "low"
    
    # Elevated priority for bills further in the process
    if status in ["passed", "enacted"]:
        return "high"
    if status == "committee":
        return "medium"
    
    return "medium"


def determine_topic(title: str) -> str:
    """
    Determine bill topic category from title.
    
    Args:
        title: Bill title
        
    Returns:
        Topic category string
    """
    title_lower = title.lower()
    
    topic_keywords = {
        "Education": ["education", "school", "student", "teacher", "university", "college", "learning"],
        "Tax & Revenue": ["tax", "revenue", "budget", "fiscal", "appropriation", "fee"],
        "Housing": ["housing", "rent", "tenant", "landlord", "affordable", "homeless", "shelter"],
        "Healthcare": ["health", "medical", "hospital", "mental", "drug", "pharmacy", "insurance"],
        "Environment": ["environment", "climate", "energy", "pollution", "conservation", "water", "wildlife"],
        "Transportation": ["transport", "road", "highway", "transit", "vehicle", "traffic", "ferry"],
        "Public Safety": ["crime", "safety", "police", "fire", "emergency", "justice", "prison", "jail"],
        "Business": ["business", "commerce", "trade", "economic", "employment", "labor", "worker"],
        "Technology": ["technology", "internet", "data", "privacy", "cyber", "artificial intelligence", "ai"],
        "Agriculture": ["agriculture", "farm", "food", "livestock", "crop"],
        "Children & Families": ["child", "family", "youth", "foster", "adoption", "parental"],
    }
    
    for topic, keywords in topic_keywords.items():
        for keyword in keywords:
            if keyword in title_lower:
                return topic
    
    return "General Government"


def fetch_prefiled_legislation() -> List[Dict]:
    """
    Fetch all prefiled legislation for the current biennium.
    
    Returns:
        List of bill dictionaries
    """
    logger.info(f"Fetching prefiled legislation for biennium {CONFIG['biennium']}")
    
    response = call_soap_service(
        "LegislationService",
        "GetPrefiledLegislation",
        {"biennium": CONFIG["biennium"]}
    )
    
    bills = []
    if response is not None:
        # Find all Legislation elements
        for leg_elem in response.iter():
            if leg_elem.tag.endswith("Legislation") and leg_elem.tag != "ArrayOfLegislation":
                bill = parse_legislation_element(leg_elem)
                if bill:
                    bills.append(bill)
    
    logger.info(f"Found {len(bills)} prefiled bills")
    return bills


def fetch_legislation_by_year() -> List[Dict]:
    """
    Fetch all legislation for the configured year.
    
    Returns:
        List of bill dictionaries
    """
    logger.info(f"Fetching legislation for year {CONFIG['year']}")
    
    response = call_soap_service(
        "LegislationService",
        "GetLegislationByYear",
        {"year": CONFIG["year"]}
    )
    
    bills = []
    if response is not None:
        # Find all LegislationInfo or Legislation elements
        for elem in response.iter():
            tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag_name in ("Legislation", "LegislationInfo"):
                bill = parse_legislation_element(elem)
                if bill:
                    bills.append(bill)
    
    logger.info(f"Found {len(bills)} bills for year {CONFIG['year']}")
    return bills


def fetch_legislation_introduced_since(since_date: str) -> List[Dict]:
    """
    Fetch legislation introduced since a given date.
    
    Args:
        since_date: Date string in format YYYY-MM-DD
        
    Returns:
        List of bill dictionaries
    """
    logger.info(f"Fetching legislation introduced since {since_date}")
    
    # Format date for API (expects ISO format)
    response = call_soap_service(
        "LegislationService",
        "GetLegislationIntroducedSince",
        {"sinceDate": f"{since_date}T00:00:00"}
    )
    
    bills = []
    if response is not None:
        for elem in response.iter():
            tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag_name in ("Legislation", "LegislationInfo"):
                bill = parse_legislation_element(elem)
                if bill:
                    bills.append(bill)
    
    logger.info(f"Found {len(bills)} bills introduced since {since_date}")
    return bills


def fetch_status_changes(begin_date: str, end_date: str) -> List[Dict]:
    """
    Fetch legislative status changes within a date range.
    
    Args:
        begin_date: Start date in format YYYY-MM-DD
        end_date: End date in format YYYY-MM-DD
        
    Returns:
        List of status change dictionaries
    """
    logger.info(f"Fetching status changes from {begin_date} to {end_date}")
    
    response = call_soap_service(
        "LegislationService",
        "GetLegislativeStatusChanges",
        {
            "biennium": CONFIG["biennium"],
            "beginDate": f"{begin_date}T00:00:00",
            "endDate": f"{end_date}T23:59:59"
        }
    )
    
    changes = []
    if response is not None:
        for elem in response.iter():
            tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag_name == "LegislativeStatusChange":
                change = {
                    "billId": get_text(elem, "BillId"),
                    "actionDate": get_text(elem, "ActionDate"),
                    "status": get_text(elem, "Status"),
                    "historyLine": get_text(elem, "HistoryLine"),
                }
                if change["billId"]:
                    changes.append(change)
    
    logger.info(f"Found {len(changes)} status changes")
    return changes


def fetch_bill_hearings(biennium: str, bill_id: str) -> List[Dict]:
    """
    Fetch committee hearings for a specific bill.
    
    Args:
        biennium: Biennium in format YYYY-YY
        bill_id: Bill ID (e.g., "HB 1001")
        
    Returns:
        List of hearing dictionaries
    """
    # Extract bill number from bill_id
    parts = bill_id.split()
    if len(parts) < 2:
        return []
    
    bill_number = parts[1]
    
    response = call_soap_service(
        "LegislationService",
        "GetHearings",
        {
            "biennium": biennium,
            "billNumber": bill_number
        }
    )
    
    hearings = []
    if response is not None:
        for elem in response.iter():
            tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag_name == "Hearing":
                date_str = get_text(elem, "Date", "")
                if date_str:
                    try:
                        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        hearing = {
                            "date": dt.strftime("%Y-%m-%d"),
                            "time": dt.strftime("%I:%M %p"),
                            "committee": get_text(elem, "CommitteeName", ""),
                            "room": get_text(elem, "Room", ""),
                        }
                        hearings.append(hearing)
                    except (ValueError, TypeError):
                        pass
    
    return hearings


def merge_bill_data(existing: Dict[str, Dict], new_bills: List[Dict]) -> Dict[str, Dict]:
    """
    Merge new bills into existing bill dictionary, updating existing entries.
    
    Args:
        existing: Dictionary of existing bills keyed by bill ID
        new_bills: List of new bill dictionaries
        
    Returns:
        Merged dictionary of bills
    """
    for bill in new_bills:
        bill_id = bill.get("id")
        if not bill_id:
            continue
        
        if bill_id in existing:
            # Update existing bill, preserving some fields
            existing_bill = existing[bill_id]
            
            # Update status if the new one is more advanced
            status_order = ["prefiled", "introduced", "committee", "passed", "enacted", "vetoed", "failed"]
            existing_status_idx = status_order.index(existing_bill.get("status", "prefiled")) if existing_bill.get("status") in status_order else 0
            new_status_idx = status_order.index(bill.get("status", "prefiled")) if bill.get("status") in status_order else 0
            
            if new_status_idx > existing_status_idx:
                existing_bill["status"] = bill["status"]
            
            # Update timestamp
            existing_bill["lastUpdated"] = datetime.now().isoformat()
            
            # Update other fields if they have more data
            if bill.get("title") and not existing_bill.get("title"):
                existing_bill["title"] = bill["title"]
            if bill.get("sponsor") and existing_bill.get("sponsor") in ["House Member", "Senator", "Unknown Sponsor"]:
                existing_bill["sponsor"] = bill["sponsor"]
            if bill.get("description") and len(bill["description"]) > len(existing_bill.get("description", "")):
                existing_bill["description"] = bill["description"]
            if bill.get("hearings"):
                existing_bill["hearings"] = bill["hearings"]
        else:
            # Add new bill
            existing[bill_id] = bill
    
    return existing


def save_bills_data(bills: List[Dict]) -> Dict:
    """
    Save bills data to JSON file.
    
    Args:
        bills: List of bill dictionaries
        
    Returns:
        Complete data structure that was saved
    """
    # Sort bills by type and number
    def sort_key(bill):
        num = bill.get("number", "")
        parts = num.split()
        if len(parts) >= 2:
            try:
                return (parts[0], int(parts[1]))
            except ValueError:
                return (parts[0], 0)
        return ("ZZ", 0)
    
    bills.sort(key=sort_key)
    
    data = {
        "lastSync": datetime.now().isoformat(),
        "sessionYear": CONFIG["year"],
        "sessionStart": CONFIG["session_start"],
        "sessionEnd": CONFIG["session_end"],
        "biennium": CONFIG["biennium"],
        "totalBills": len(bills),
        "bills": bills,
        "metadata": {
            "source": "Washington State Legislature Web Services",
            "sourceUrl": "https://wslwebservices.leg.wa.gov/",
            "updateFrequency": "daily",
            "dataVersion": "3.0.0",
            "billTypes": ["HB", "SB", "HJR", "SJR", "HJM", "SJM", "HCR", "SCR"],
        }
    }
    
    data_file = CONFIG["data_dir"] / "bills.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(bills)} bills to {data_file}")
    return data


def save_stats_file(bills: List[Dict]):
    """
    Create and save statistics file.
    
    Args:
        bills: List of bill dictionaries
    """
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
        "billsWithHearings": 0,
    }
    
    today = datetime.now().date()
    week_from_now = today + timedelta(days=7)
    
    for bill in bills:
        # By status
        status = bill.get("status", "unknown")
        stats["byStatus"][status] = stats["byStatus"].get(status, 0) + 1
        
        # By committee
        committee = bill.get("committee") or "Unassigned"
        stats["byCommittee"][committee] = stats["byCommittee"].get(committee, 0) + 1
        
        # By priority
        priority = bill.get("priority", "medium")
        stats["byPriority"][priority] = stats["byPriority"].get(priority, 0) + 1
        
        # By topic
        topic = bill.get("topic", "General Government")
        stats["byTopic"][topic] = stats["byTopic"].get(topic, 0) + 1
        
        # By sponsor
        sponsor = bill.get("sponsor", "Unknown")
        stats["bySponsor"][sponsor] = stats["bySponsor"].get(sponsor, 0) + 1
        
        # By type
        number = bill.get("number", "")
        bill_type = number.split()[0] if number else "Unknown"
        stats["byType"][bill_type] = stats["byType"].get(bill_type, 0) + 1
        
        # Recently updated
        last_updated = bill.get("lastUpdated", "")
        if last_updated:
            try:
                update_date = datetime.fromisoformat(last_updated.replace("Z", "+00:00")).date()
                if update_date == today:
                    stats["updatedToday"] += 1
                if (today - update_date).days < 7:
                    stats["recentlyUpdated"] += 1
            except (ValueError, TypeError):
                pass
        
        # Hearings
        hearings = bill.get("hearings", [])
        if hearings:
            stats["billsWithHearings"] += 1
            for hearing in hearings:
                try:
                    hearing_date = datetime.strptime(hearing.get("date", ""), "%Y-%m-%d").date()
                    if today <= hearing_date <= week_from_now:
                        stats["upcomingHearings"] += 1
                except (ValueError, TypeError):
                    pass
    
    # Top sponsors
    stats["topSponsors"] = sorted(
        stats["bySponsor"].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    stats_file = CONFIG["data_dir"] / "stats.json"
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    
    logger.info(f"Statistics file saved with {len(stats['byStatus'])} statuses, {len(stats['byType'])} types")


def save_sync_log(bills_count: int, new_count: int, status: str = "success"):
    """
    Create and update sync log file.
    
    Args:
        bills_count: Total number of bills
        new_count: Number of new bills added
        status: Sync status ("success" or "error")
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "billsCount": bills_count,
        "newBillsAdded": new_count,
        "nextSync": (datetime.now() + timedelta(hours=6)).isoformat(),
    }
    
    log_file = CONFIG["data_dir"] / "sync-log.json"
    
    # Load existing logs
    logs = []
    if log_file.exists():
        try:
            with open(log_file, "r") as f:
                data = json.load(f)
                logs = data.get("logs", [])
        except (json.JSONDecodeError, IOError):
            pass
    
    # Add new log entry and keep last 100
    logs.insert(0, log_entry)
    logs = logs[:100]
    
    with open(log_file, "w") as f:
        json.dump({"logs": logs}, f, indent=2)
    
    logger.info(f"Sync log updated: {status} - {bills_count} bills, {new_count} new")


def load_existing_data() -> Optional[Dict]:
    """
    Load existing bills data if it exists.
    
    Returns:
        Existing data dictionary or None
    """
    data_file = CONFIG["data_dir"] / "bills.json"
    if data_file.exists():
        try:
            with open(data_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load existing data: {e}")
    return None


def main():
    """Main execution function."""
    logger.info("=" * 60)
    logger.info(f"WA Legislature Bill Fetcher - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Biennium: {CONFIG['biennium']}, Year: {CONFIG['year']}")
    logger.info("=" * 60)
    
    # Ensure data directory exists
    ensure_data_dir()
    
    # Load existing data
    existing_data = load_existing_data()
    existing_bills = {}
    if existing_data:
        existing_bills = {bill["id"]: bill for bill in existing_data.get("bills", [])}
        logger.info(f"Loaded {len(existing_bills)} existing bills")
    
    initial_count = len(existing_bills)
    
    # Fetch data from multiple sources for comprehensive coverage
    all_bills = {}
    
    # 1. Fetch prefiled legislation
    logger.info("Step 1/4: Fetching prefiled legislation...")
    prefiled = fetch_prefiled_legislation()
    all_bills = merge_bill_data(all_bills, prefiled)
    time.sleep(CONFIG["request_delay"])
    
    # 2. Fetch legislation by year
    logger.info("Step 2/4: Fetching legislation by year...")
    by_year = fetch_legislation_by_year()
    all_bills = merge_bill_data(all_bills, by_year)
    time.sleep(CONFIG["request_delay"])
    
    # 3. Fetch legislation introduced since December 1 (pre-file period start)
    logger.info("Step 3/4: Fetching legislation introduced since December 1...")
    prefiled_start = f"{CONFIG['year'] - 1}-12-01"
    introduced_since = fetch_legislation_introduced_since(prefiled_start)
    all_bills = merge_bill_data(all_bills, introduced_since)
    time.sleep(CONFIG["request_delay"])
    
    # 4. Merge with existing data
    logger.info("Step 4/4: Merging with existing data...")
    final_bills = merge_bill_data(existing_bills.copy(), list(all_bills.values()))
    
    # Convert back to list
    bills_list = list(final_bills.values())
    
    # Calculate new bills
    new_count = len(bills_list) - initial_count
    
    # Save data
    save_bills_data(bills_list)
    save_stats_file(bills_list)
    save_sync_log(len(bills_list), max(0, new_count), "success")
    
    # Summary
    logger.info("=" * 60)
    logger.info("Fetch completed successfully:")
    logger.info(f"  - Total bills: {len(bills_list)}")
    logger.info(f"  - New bills: {max(0, new_count)}")
    logger.info(f"  - Data saved to: {CONFIG['data_dir']}")
    logger.info("=" * 60)
    
    return bills_list


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        save_sync_log(0, 0, "error")
        sys.exit(1)
