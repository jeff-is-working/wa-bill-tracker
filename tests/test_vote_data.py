#!/usr/bin/env python3
"""
TDD Red Phase tests for vote tracker feature.

Tests that:
1. A get_roll_calls function exists in fetch_all_bills.py
2. Bill objects in bills.json contain vote data for bills that have progressed
3. Governor action tracking data is present on governor-stage bills
4. Vote data presence correlates with bill status (passed bills have votes,
   prefiled bills do not)

These tests are expected to FAIL until the vote fetching pipeline is implemented.
"""

import json
import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestGetRollCallsFunction(unittest.TestCase):
    """Tests that the get_roll_calls function exists in fetch_all_bills."""

    def test_get_roll_calls_function_exists(self):
        """get_roll_calls should be importable from scripts.fetch_all_bills and callable."""
        import scripts.fetch_all_bills as fab
        self.assertTrue(
            hasattr(fab, "get_roll_calls"),
            "scripts.fetch_all_bills is missing the 'get_roll_calls' function",
        )
        self.assertTrue(
            callable(getattr(fab, "get_roll_calls")),
            "get_roll_calls exists but is not callable",
        )


class TestBillVoteDataStructure(unittest.TestCase):
    """Tests that bill objects in bills.json carry vote data.

    Loads data/bills.json and inspects a bill whose status is 'governor',
    since those bills must have passed both chambers and should have roll-call
    vote records attached.
    """

    bills = None
    governor_bill = None

    @classmethod
    def setUpClass(cls):
        bills_path = PROJECT_ROOT / "data" / "bills.json"
        if not bills_path.exists():
            raise unittest.SkipTest("data/bills.json not found -- skipping vote data structure tests")

        with open(bills_path) as f:
            data = json.load(f)

        cls.bills = data.get("bills", [])
        for bill in cls.bills:
            if bill.get("status") == "governor":
                cls.governor_bill = bill
                break

        if cls.governor_bill is None:
            raise unittest.SkipTest("No bill with status 'governor' found in bills.json")

    def test_governor_bill_has_votes_field(self):
        """A bill at governor status should have a 'votes' key."""
        self.assertIn(
            "votes",
            self.governor_bill,
            f"Bill {self.governor_bill.get('id')} (status=governor) is missing 'votes' key",
        )

    def test_votes_is_list(self):
        """The 'votes' field should be a list of roll-call records."""
        votes = self.governor_bill.get("votes")
        self.assertIsNotNone(votes, "votes field is None")
        self.assertIsInstance(votes, list, "votes field should be a list")

    def test_vote_entry_has_required_fields(self):
        """Each vote entry must contain chamber, date, yeas, nays, absent, excused, motion, passed."""
        votes = self.governor_bill.get("votes", [])
        self.assertTrue(len(votes) > 0, "votes list is empty for a governor-stage bill")

        required_fields = ["chamber", "date", "yeas", "nays", "absent", "excused", "motion", "passed"]
        for i, vote in enumerate(votes):
            for field in required_fields:
                self.assertIn(
                    field,
                    vote,
                    f"Vote entry {i} in bill {self.governor_bill.get('id')} is missing '{field}'",
                )

    def test_vote_yeas_is_integer(self):
        """The yeas count in each vote entry should be an integer."""
        votes = self.governor_bill.get("votes", [])
        self.assertTrue(len(votes) > 0, "votes list is empty")

        for i, vote in enumerate(votes):
            self.assertIsInstance(
                vote.get("yeas"),
                int,
                f"Vote entry {i}: 'yeas' should be int, got {type(vote.get('yeas')).__name__}",
            )

    def test_vote_has_chamber(self):
        """The chamber field should be 'House' or 'Senate'."""
        votes = self.governor_bill.get("votes", [])
        self.assertTrue(len(votes) > 0, "votes list is empty")

        valid_chambers = {"House", "Senate"}
        for i, vote in enumerate(votes):
            self.assertIn(
                vote.get("chamber"),
                valid_chambers,
                f"Vote entry {i}: chamber '{vote.get('chamber')}' not in {valid_chambers}",
            )

    def test_vote_passed_is_boolean(self):
        """The passed field should be a boolean."""
        votes = self.governor_bill.get("votes", [])
        self.assertTrue(len(votes) > 0, "votes list is empty")

        for i, vote in enumerate(votes):
            self.assertIsInstance(
                vote.get("passed"),
                bool,
                f"Vote entry {i}: 'passed' should be bool, got {type(vote.get('passed')).__name__}",
            )


class TestGovernorActionData(unittest.TestCase):
    """Tests that governor-stage bills carry governor action tracking data.

    When a bill reaches the governor, the data pipeline should attach a
    governorAction object with status and (optionally) delivery date.
    """

    bills = None
    governor_bill = None

    @classmethod
    def setUpClass(cls):
        bills_path = PROJECT_ROOT / "data" / "bills.json"
        if not bills_path.exists():
            raise unittest.SkipTest("data/bills.json not found -- skipping governor action tests")

        with open(bills_path) as f:
            data = json.load(f)

        cls.bills = data.get("bills", [])
        for bill in cls.bills:
            if bill.get("status") == "governor":
                cls.governor_bill = bill
                break

        if cls.governor_bill is None:
            raise unittest.SkipTest("No bill with status 'governor' found in bills.json")

    def test_governor_bill_has_governor_action(self):
        """A governor-stage bill should have a 'governorAction' key."""
        self.assertIn(
            "governorAction",
            self.governor_bill,
            f"Bill {self.governor_bill.get('id')} is missing 'governorAction' key",
        )

    def test_governor_action_has_status(self):
        """The governorAction object should have a 'status' field."""
        action = self.governor_bill.get("governorAction", {})
        self.assertIn(
            "status",
            action,
            "governorAction is missing 'status' field",
        )

    def test_governor_action_has_delivered_date(self):
        """If governorAction status is 'awaiting', it should have a 'deliveredDate'."""
        action = self.governor_bill.get("governorAction", {})
        if action.get("status") != "awaiting":
            self.skipTest("governorAction status is not 'awaiting' -- deliveredDate check not applicable")

        self.assertIn(
            "deliveredDate",
            action,
            "governorAction with status 'awaiting' is missing 'deliveredDate'",
        )

    def test_governor_action_status_values(self):
        """The governorAction status should be one of the known values."""
        action = self.governor_bill.get("governorAction", {})
        valid_statuses = {"awaiting", "signed", "vetoed", "partial_veto"}
        status = action.get("status")
        self.assertIn(
            status,
            valid_statuses,
            f"governorAction status '{status}' not in {valid_statuses}",
        )


class TestVoteDataForPassedBills(unittest.TestCase):
    """Tests that vote data presence correlates correctly with bill status.

    Bills that have passed the legislature or been enacted should carry vote
    records, while prefiled bills should not.
    """

    bills = None

    @classmethod
    def setUpClass(cls):
        bills_path = PROJECT_ROOT / "data" / "bills.json"
        if not bills_path.exists():
            raise unittest.SkipTest("data/bills.json not found -- skipping vote-by-status tests")

        with open(bills_path) as f:
            data = json.load(f)

        cls.bills = data.get("bills", [])
        if not cls.bills:
            raise unittest.SkipTest("bills.json contains no bills")

    def _find_bills_by_status(self, status):
        """Return all bills matching the given status."""
        return [b for b in self.bills if b.get("status") == status]

    def test_passed_legislature_bill_has_votes(self):
        """Bills with passed_legislature status should have vote records."""
        passed_bills = self._find_bills_by_status("passed_legislature")
        if not passed_bills:
            self.skipTest("No bills with status 'passed_legislature' found")

        for bill in passed_bills:
            votes = bill.get("votes", [])
            self.assertIsInstance(votes, list, f"Bill {bill.get('id')}: votes should be a list")
            self.assertGreater(
                len(votes),
                0,
                f"Bill {bill.get('id')} has passed_legislature status but no vote records",
            )

    def test_enacted_bill_has_votes(self):
        """Bills with enacted status should have vote records."""
        enacted_bills = self._find_bills_by_status("enacted")
        if not enacted_bills:
            self.skipTest("No bills with status 'enacted' found in current session")

        for bill in enacted_bills:
            votes = bill.get("votes", [])
            self.assertIsInstance(votes, list, f"Bill {bill.get('id')}: votes should be a list")
            self.assertGreater(
                len(votes),
                0,
                f"Bill {bill.get('id')} has enacted status but no vote records",
            )

    def test_prefiled_bill_has_no_votes(self):
        """Bills with prefiled status should not have vote records."""
        prefiled_bills = self._find_bills_by_status("prefiled")
        if not prefiled_bills:
            self.skipTest("No bills with status 'prefiled' found")

        for bill in prefiled_bills:
            votes = bill.get("votes")
            if votes is not None:
                self.assertIsInstance(votes, list, f"Bill {bill.get('id')}: votes should be a list")
                self.assertEqual(
                    len(votes),
                    0,
                    f"Bill {bill.get('id')} is prefiled but has {len(votes)} vote records",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
