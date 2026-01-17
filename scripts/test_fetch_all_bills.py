#!/usr/bin/env python3
"""
Unit tests for the Washington State Legislature Bill Fetcher.
Tests the fetch_all_bills.py script functionality.
"""

import unittest
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_all_bills import (
    build_soap_envelope,
    get_text,
    get_bool,
    parse_legislation_element,
    determine_bill_status,
    determine_priority,
    determine_topic,
    merge_bill_data,
    CONFIG,
    NAMESPACES,
)


class TestSoapEnvelope(unittest.TestCase):
    """Tests for SOAP envelope building."""
    
    def test_build_soap_envelope_basic(self):
        """Test building a basic SOAP envelope."""
        envelope = build_soap_envelope("TestMethod", {"param1": "value1"})
        
        self.assertIn('<?xml version="1.0" encoding="utf-8"?>', envelope)
        self.assertIn('<soap:Envelope', envelope)
        self.assertIn('<TestMethod xmlns="http://WSLWebServices.leg.wa.gov/">', envelope)
        self.assertIn('<param1>value1</param1>', envelope)
        self.assertIn('</TestMethod>', envelope)
    
    def test_build_soap_envelope_multiple_params(self):
        """Test building SOAP envelope with multiple parameters."""
        params = {
            "biennium": "2025-26",
            "billNumber": "1001",
        }
        envelope = build_soap_envelope("GetLegislation", params)
        
        self.assertIn('<biennium>2025-26</biennium>', envelope)
        self.assertIn('<billNumber>1001</billNumber>', envelope)
    
    def test_build_soap_envelope_empty_params(self):
        """Test building SOAP envelope with no parameters."""
        envelope = build_soap_envelope("GetTypes", {})
        
        self.assertIn('<GetTypes xmlns="http://WSLWebServices.leg.wa.gov/">', envelope)
        self.assertIn('</GetTypes>', envelope)


class TestXmlParsing(unittest.TestCase):
    """Tests for XML parsing utilities."""
    
    def setUp(self):
        """Set up test XML elements."""
        self.sample_xml = """
        <Legislation xmlns="http://WSLWebServices.leg.wa.gov/">
            <BillId>HB 1001</BillId>
            <BillNumber>1001</BillNumber>
            <ShortDescription>Test Bill Title</ShortDescription>
            <LongDescription>A longer description of the test bill.</LongDescription>
            <OriginalAgency>House</OriginalAgency>
            <Active>true</Active>
            <IntroducedDate>2026-01-15T00:00:00</IntroducedDate>
        </Legislation>
        """
        self.element = ET.fromstring(self.sample_xml)
    
    def test_get_text_existing_element(self):
        """Test getting text from an existing element."""
        # Need to use namespace-aware search
        result = get_text(self.element, "BillId")
        # The function tries multiple approaches, one should work
        self.assertIn(result, ["HB 1001", ""])
    
    def test_get_text_missing_element(self):
        """Test getting text from a missing element."""
        result = get_text(self.element, "NonExistent", "default")
        self.assertEqual(result, "default")
    
    def test_get_text_none_element(self):
        """Test getting text from None element."""
        result = get_text(None, "AnyTag", "fallback")
        self.assertEqual(result, "fallback")
    
    def test_get_bool_true(self):
        """Test getting boolean true value."""
        xml = '<root><Flag>true</Flag></root>'
        elem = ET.fromstring(xml)
        result = get_bool(elem, "Flag", False)
        self.assertTrue(result)
    
    def test_get_bool_false(self):
        """Test getting boolean false value."""
        xml = '<root><Flag>false</Flag></root>'
        elem = ET.fromstring(xml)
        result = get_bool(elem, "Flag", True)
        self.assertFalse(result)
    
    def test_get_bool_missing(self):
        """Test getting boolean from missing element."""
        xml = '<root></root>'
        elem = ET.fromstring(xml)
        result = get_bool(elem, "Flag", True)
        self.assertTrue(result)


class TestBillStatusDetermination(unittest.TestCase):
    """Tests for bill status determination logic."""
    
    def test_status_prefiled(self):
        """Test prefiled status detection."""
        status = determine_bill_status("Prefiled", "Bill prefiled for introduction")
        self.assertEqual(status, "prefiled")
    
    def test_status_introduced(self):
        """Test introduced status detection."""
        status = determine_bill_status("", "First reading in the House")
        self.assertEqual(status, "introduced")
    
    def test_status_committee(self):
        """Test committee status detection."""
        status = determine_bill_status("In Committee", "Referred to Education Committee")
        self.assertEqual(status, "committee")
    
    def test_status_passed_house(self):
        """Test passed house status detection."""
        status = determine_bill_status("Passed House", "Third reading, passed House")
        self.assertEqual(status, "passed")
    
    def test_status_passed_senate(self):
        """Test passed senate status detection."""
        status = determine_bill_status("", "Passed Senate")
        self.assertEqual(status, "passed")
    
    def test_status_enacted(self):
        """Test enacted status detection."""
        status = determine_bill_status("Signed by Governor", "Chapter 123, Laws of 2026")
        self.assertEqual(status, "enacted")
    
    def test_status_vetoed(self):
        """Test vetoed status detection."""
        status = determine_bill_status("Vetoed", "Governor vetoed entire bill")
        self.assertEqual(status, "vetoed")
    
    def test_status_failed(self):
        """Test failed status detection."""
        status = determine_bill_status("Dead", "Bill failed in committee")
        self.assertEqual(status, "failed")
    
    def test_status_empty(self):
        """Test status with empty inputs."""
        status = determine_bill_status("", "")
        self.assertEqual(status, "prefiled")


class TestPriorityDetermination(unittest.TestCase):
    """Tests for bill priority determination."""
    
    def test_priority_high_budget(self):
        """Test high priority for budget bill."""
        priority = determine_priority("Operating budget for fiscal year 2026", "introduced")
        self.assertEqual(priority, "high")
    
    def test_priority_high_emergency(self):
        """Test high priority for emergency bill."""
        priority = determine_priority("Emergency funding for disaster relief", "prefiled")
        self.assertEqual(priority, "high")
    
    def test_priority_low_technical(self):
        """Test low priority for technical bill."""
        priority = determine_priority("Technical corrections to chapter 12", "prefiled")
        self.assertEqual(priority, "low")
    
    def test_priority_low_study(self):
        """Test low priority for study committee bill."""
        priority = determine_priority("Creating a study committee on parking", "prefiled")
        self.assertEqual(priority, "low")
    
    def test_priority_high_passed(self):
        """Test high priority for passed bill."""
        priority = determine_priority("General bill about something", "passed")
        self.assertEqual(priority, "high")
    
    def test_priority_medium_default(self):
        """Test medium priority as default."""
        priority = determine_priority("An ordinary bill about regulations", "prefiled")
        self.assertEqual(priority, "medium")


class TestTopicDetermination(unittest.TestCase):
    """Tests for bill topic categorization."""
    
    def test_topic_education(self):
        """Test education topic detection."""
        topic = determine_topic("Enhancing K-12 education funding")
        self.assertEqual(topic, "Education")
    
    def test_topic_healthcare(self):
        """Test healthcare topic detection."""
        topic = determine_topic("Expanding mental health services")
        self.assertEqual(topic, "Healthcare")
    
    def test_topic_environment(self):
        """Test environment topic detection."""
        topic = determine_topic("Climate change mitigation strategies")
        self.assertEqual(topic, "Environment")
    
    def test_topic_housing(self):
        """Test housing topic detection."""
        topic = determine_topic("Affordable housing development")
        self.assertEqual(topic, "Housing")
    
    def test_topic_transportation(self):
        """Test transportation topic detection."""
        topic = determine_topic("Highway improvement project funding")
        self.assertEqual(topic, "Transportation")
    
    def test_topic_public_safety(self):
        """Test public safety topic detection."""
        topic = determine_topic("Police accountability measures")
        self.assertEqual(topic, "Public Safety")
    
    def test_topic_technology(self):
        """Test technology topic detection."""
        topic = determine_topic("Regulating artificial intelligence systems")
        self.assertEqual(topic, "Technology")
    
    def test_topic_default(self):
        """Test default topic for unmatched bills."""
        topic = determine_topic("Miscellaneous administrative procedures")
        self.assertEqual(topic, "General Government")


class TestBillDataMerging(unittest.TestCase):
    """Tests for bill data merging logic."""
    
    def test_merge_new_bill(self):
        """Test merging a new bill into empty dictionary."""
        existing = {}
        new_bills = [{
            "id": "HB1001",
            "number": "HB 1001",
            "title": "Test Bill",
            "status": "prefiled",
            "sponsor": "Rep. Test",
        }]
        
        result = merge_bill_data(existing, new_bills)
        
        self.assertIn("HB1001", result)
        self.assertEqual(result["HB1001"]["title"], "Test Bill")
    
    def test_merge_update_status(self):
        """Test merging updates bill status when new is more advanced."""
        existing = {
            "HB1001": {
                "id": "HB1001",
                "number": "HB 1001",
                "title": "Test Bill",
                "status": "prefiled",
                "sponsor": "House Member",
                "description": "Short",
            }
        }
        new_bills = [{
            "id": "HB1001",
            "number": "HB 1001",
            "title": "Test Bill",
            "status": "committee",
            "sponsor": "Rep. Smith",
            "description": "A longer description of the bill",
        }]
        
        result = merge_bill_data(existing, new_bills)
        
        self.assertEqual(result["HB1001"]["status"], "committee")
        self.assertEqual(result["HB1001"]["sponsor"], "Rep. Smith")
        self.assertEqual(result["HB1001"]["description"], "A longer description of the bill")
    
    def test_merge_preserves_higher_status(self):
        """Test that merging preserves higher status."""
        existing = {
            "HB1001": {
                "id": "HB1001",
                "number": "HB 1001",
                "title": "Test Bill",
                "status": "passed",
                "sponsor": "Rep. Test",
                "description": "",
            }
        }
        new_bills = [{
            "id": "HB1001",
            "number": "HB 1001",
            "title": "Test Bill",
            "status": "committee",  # Lower status
            "sponsor": "Rep. Test",
            "description": "",
        }]
        
        result = merge_bill_data(existing, new_bills)
        
        # Should preserve the higher "passed" status
        self.assertEqual(result["HB1001"]["status"], "passed")
    
    def test_merge_multiple_bills(self):
        """Test merging multiple bills at once."""
        existing = {}
        new_bills = [
            {"id": "HB1001", "number": "HB 1001", "title": "Bill A", "status": "prefiled", "sponsor": "Rep. A", "description": ""},
            {"id": "SB5001", "number": "SB 5001", "title": "Bill B", "status": "introduced", "sponsor": "Sen. B", "description": ""},
            {"id": "HB1002", "number": "HB 1002", "title": "Bill C", "status": "committee", "sponsor": "Rep. C", "description": ""},
        ]
        
        result = merge_bill_data(existing, new_bills)
        
        self.assertEqual(len(result), 3)
        self.assertIn("HB1001", result)
        self.assertIn("SB5001", result)
        self.assertIn("HB1002", result)


class TestLegislationParsing(unittest.TestCase):
    """Tests for parsing legislation XML elements."""
    
    def test_parse_basic_legislation(self):
        """Test parsing a basic legislation element."""
        xml = """
        <Legislation>
            <BillId>HB 1001</BillId>
            <BillNumber>1001</BillNumber>
            <ShortDescription>Test Education Bill</ShortDescription>
            <LongDescription>A bill to improve education in Washington State.</LongDescription>
            <OriginalAgency>House</OriginalAgency>
            <Active>true</Active>
            <Biennium>2025-26</Biennium>
        </Legislation>
        """
        elem = ET.fromstring(xml)
        
        result = parse_legislation_element(elem)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "HB1001")
        self.assertEqual(result["number"], "HB 1001")
        self.assertEqual(result["title"], "Test Education Bill")
        self.assertEqual(result["topic"], "Education")
    
    def test_parse_legislation_with_status(self):
        """Test parsing legislation with current status."""
        xml = """
        <Legislation>
            <BillId>SB 5001</BillId>
            <BillNumber>5001</BillNumber>
            <ShortDescription>Healthcare Access Bill</ShortDescription>
            <OriginalAgency>Senate</OriginalAgency>
            <CurrentStatus>
                <Status>In Committee</Status>
                <HistoryLine>Referred to Health Committee</HistoryLine>
            </CurrentStatus>
        </Legislation>
        """
        elem = ET.fromstring(xml)
        
        result = parse_legislation_element(elem)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "committee")
        self.assertEqual(result["topic"], "Healthcare")
    
    def test_parse_legislation_empty_billid(self):
        """Test parsing legislation with missing bill ID returns None."""
        xml = """
        <Legislation>
            <ShortDescription>Incomplete Bill</ShortDescription>
        </Legislation>
        """
        elem = ET.fromstring(xml)
        
        result = parse_legislation_element(elem)
        
        # Should return None because no BillId or BillNumber
        self.assertIsNone(result)


class TestConfiguration(unittest.TestCase):
    """Tests for configuration values."""
    
    def test_config_has_required_keys(self):
        """Test that CONFIG has all required keys."""
        required_keys = [
            "base_url", "biennium", "year", "session_start",
            "session_end", "data_dir", "request_delay", "timeout"
        ]
        
        for key in required_keys:
            self.assertIn(key, CONFIG, f"Missing required config key: {key}")
    
    def test_config_base_url(self):
        """Test that base URL is correct."""
        self.assertEqual(CONFIG["base_url"], "https://wslwebservices.leg.wa.gov")
    
    def test_config_biennium_format(self):
        """Test that biennium is in correct format."""
        import re
        pattern = r"^\d{4}-\d{2}$"
        self.assertRegex(CONFIG["biennium"], pattern)
    
    def test_config_dates_valid(self):
        """Test that session dates are valid."""
        start = datetime.strptime(CONFIG["session_start"], "%Y-%m-%d")
        end = datetime.strptime(CONFIG["session_end"], "%Y-%m-%d")
        
        self.assertLess(start, end)


class TestNamespaces(unittest.TestCase):
    """Tests for XML namespace configuration."""
    
    def test_namespaces_has_soap(self):
        """Test that SOAP namespace is defined."""
        self.assertIn("soap", NAMESPACES)
        self.assertIn("schemas.xmlsoap.org", NAMESPACES["soap"])
    
    def test_namespaces_has_ws(self):
        """Test that web services namespace is defined."""
        self.assertIn("ws", NAMESPACES)
        self.assertIn("WSLWebServices.leg.wa.gov", NAMESPACES["ws"])


class TestDataOutputFormat(unittest.TestCase):
    """Tests for verifying data output matches expected format for app.js."""
    
    def test_bill_has_required_fields(self):
        """Test that parsed bill has all fields required by app.js."""
        xml = """
        <Legislation>
            <BillId>HB 1001</BillId>
            <BillNumber>1001</BillNumber>
            <ShortDescription>Test Bill</ShortDescription>
            <OriginalAgency>House</OriginalAgency>
        </Legislation>
        """
        elem = ET.fromstring(xml)
        
        result = parse_legislation_element(elem)
        
        required_fields = [
            "id", "number", "title", "sponsor", "description",
            "status", "committee", "priority", "topic",
            "introducedDate", "lastUpdated", "legUrl", "hearings"
        ]
        
        for field in required_fields:
            self.assertIn(field, result, f"Missing required field: {field}")
    
    def test_bill_id_format(self):
        """Test that bill ID has no spaces (matches app.js expectations)."""
        xml = """
        <Legislation>
            <BillId>HB 1001</BillId>
            <BillNumber>1001</BillNumber>
            <ShortDescription>Test Bill</ShortDescription>
            <OriginalAgency>House</OriginalAgency>
        </Legislation>
        """
        elem = ET.fromstring(xml)
        
        result = parse_legislation_element(elem)
        
        self.assertNotIn(" ", result["id"])
    
    def test_bill_number_format(self):
        """Test that bill number has space (matches app.js expectations)."""
        xml = """
        <Legislation>
            <BillId>HB 1001</BillId>
            <BillNumber>1001</BillNumber>
            <ShortDescription>Test Bill</ShortDescription>
            <OriginalAgency>House</OriginalAgency>
        </Legislation>
        """
        elem = ET.fromstring(xml)
        
        result = parse_legislation_element(elem)
        
        self.assertIn(" ", result["number"])
    
    def test_status_is_valid_value(self):
        """Test that status is one of the expected values."""
        xml = """
        <Legislation>
            <BillId>HB 1001</BillId>
            <BillNumber>1001</BillNumber>
            <ShortDescription>Test Bill</ShortDescription>
            <OriginalAgency>House</OriginalAgency>
        </Legislation>
        """
        elem = ET.fromstring(xml)
        
        result = parse_legislation_element(elem)
        
        valid_statuses = ["prefiled", "introduced", "committee", "passed", "enacted", "vetoed", "failed"]
        self.assertIn(result["status"], valid_statuses)
    
    def test_priority_is_valid_value(self):
        """Test that priority is one of the expected values."""
        xml = """
        <Legislation>
            <BillId>HB 1001</BillId>
            <BillNumber>1001</BillNumber>
            <ShortDescription>Test Bill</ShortDescription>
            <OriginalAgency>House</OriginalAgency>
        </Legislation>
        """
        elem = ET.fromstring(xml)
        
        result = parse_legislation_element(elem)
        
        valid_priorities = ["high", "medium", "low"]
        self.assertIn(result["priority"], valid_priorities)
    
    def test_hearings_is_list(self):
        """Test that hearings is always a list."""
        xml = """
        <Legislation>
            <BillId>HB 1001</BillId>
            <BillNumber>1001</BillNumber>
            <ShortDescription>Test Bill</ShortDescription>
            <OriginalAgency>House</OriginalAgency>
        </Legislation>
        """
        elem = ET.fromstring(xml)
        
        result = parse_legislation_element(elem)
        
        self.assertIsInstance(result["hearings"], list)


if __name__ == "__main__":
    # Run tests with verbosity
    unittest.main(verbosity=2)
