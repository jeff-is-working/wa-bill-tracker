#!/usr/bin/env python3
"""
TDD Red Phase -- Integration tests for normalize_status() with real API payloads

Per lessons learned from issue #58, the status normalization logic must handle
the full range of WA legislature API statuses including cross-chamber movement,
governor actions, and edge cases. These tests use realistic status strings and
history lines from the WA SOAP API to verify correct mapping.

Run with: python -m pytest tests/test_status_mapping_integration.py -v
"""

import os
import sys
import unittest
from pathlib import Path

# Add project root to path so scripts package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.fetch_all_bills import normalize_status


class TestCrossChamberStatusMapping(unittest.TestCase):
    """Test status normalization for bills that have crossed to the opposite chamber."""

    def test_house_bill_in_senate_committee(self):
        """A House bill with status 'S Ways & Means' (Senate committee prefix)
        should map to 'opposite_committee' since it has crossed chambers."""
        result = normalize_status(
            status="S Ways & Means",
            history_line="",
            original_agency="House of Representatives",
        )
        self.assertEqual(
            result,
            "opposite_committee",
            "House bill in Senate committee should be 'opposite_committee'",
        )

    def test_senate_bill_on_house_floor(self):
        """A Senate bill with status 'H 2nd Reading' (House floor prefix)
        should map to 'opposite_floor' since it is on the opposite chamber's
        floor."""
        result = normalize_status(
            status="H 2nd Reading",
            history_line="",
            original_agency="Senate",
        )
        self.assertEqual(
            result,
            "opposite_floor",
            "Senate bill on House floor should be 'opposite_floor'",
        )

    def test_cross_chamber_third_reading_passed(self):
        """A House bill in Senate Rules with history 'Third reading, passed.'
        should map to 'opposite_floor' (or 'passed_legislature' if both
        chambers have passed). This tests the interaction between the status
        field and history line for cross-chamber scenarios."""
        result = normalize_status(
            status="S Rules 2",
            history_line="Third reading, passed.",
            original_agency="House of Representatives",
        )
        self.assertIn(
            result,
            ("opposite_floor", "passed_legislature"),
            "House bill passed in Senate should be 'opposite_floor' or 'passed_legislature'",
        )


class TestGovernorActions(unittest.TestCase):
    """Test status normalization for governor-related actions."""

    def test_bill_delivered_to_governor(self):
        """When history contains 'Delivered to Governor.', the bill has
        reached the governor's desk and should map to 'governor'."""
        result = normalize_status(
            status="",
            history_line="Delivered to Governor.",
            original_agency="",
        )
        self.assertEqual(
            result,
            "governor",
            "Bill delivered to governor should be 'governor'",
        )

    def test_bill_signed_by_governor(self):
        """When history contains 'Governor signed.', the bill has been
        enacted into law."""
        result = normalize_status(
            status="",
            history_line="Governor signed.",
            original_agency="",
        )
        self.assertEqual(
            result,
            "enacted",
            "Bill signed by governor should be 'enacted'",
        )

    def test_chapter_law_reference(self):
        """A history line like 'C 123 L 2027' indicates the bill has been
        chaptered as law, meaning it was enacted."""
        result = normalize_status(
            status="",
            history_line="C 123 L 2027",
            original_agency="",
        )
        self.assertEqual(
            result,
            "enacted",
            "Chapter law reference should map to 'enacted'",
        )

    def test_vetoed(self):
        """When history contains 'Governor vetoed.', the bill should map
        to 'vetoed'."""
        result = normalize_status(
            status="",
            history_line="Governor vetoed.",
            original_agency="",
        )
        self.assertEqual(
            result,
            "vetoed",
            "Governor veto should map to 'vetoed'",
        )


class TestBasicStatusMapping(unittest.TestCase):
    """Test basic status normalization cases."""

    def test_basic_committee_status(self):
        """A plain 'committee' status with no agency context should
        normalize to 'committee'."""
        result = normalize_status(
            status="committee",
            history_line="",
            original_agency="",
        )
        self.assertEqual(
            result,
            "committee",
            "Basic committee status should remain 'committee'",
        )

    def test_prefiled_default(self):
        """When status and history are both empty, the bill is in its
        earliest state and should default to 'prefiled'."""
        result = normalize_status(
            status="",
            history_line="",
            original_agency="",
        )
        self.assertEqual(
            result,
            "prefiled",
            "Empty status and history should default to 'prefiled'",
        )

    def test_failed(self):
        """When history indicates the bill died in committee, it should
        map to 'failed'."""
        result = normalize_status(
            status="",
            history_line="Died in committee",
            original_agency="",
        )
        self.assertEqual(
            result,
            "failed",
            "Bill that died in committee should be 'failed'",
        )


if __name__ == "__main__":
    unittest.main()
