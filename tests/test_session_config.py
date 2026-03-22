#!/usr/bin/env python3
"""
TDD Red Phase -- Acceptance criteria for data/session.json

The monolithic app currently hardcodes session configuration in app.js and
scripts/fetch_all_bills.py. These tests define the contract for a new
data/session.json file that will be the single source of truth for session
parameters. All tests should FAIL until session.json is created.

Run with: python -m pytest tests/test_session_config.py -v
"""

import json
import re
import unittest
from datetime import datetime
from pathlib import Path


# Resolve project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_JSON = PROJECT_ROOT / "data" / "session.json"


class TestSessionConfigExists(unittest.TestCase):
    """Verify the session config file exists on disk."""

    def test_session_json_exists(self):
        """data/session.json must exist as the single source of truth for
        session configuration, replacing hardcoded values in app.js and
        fetch_all_bills.py."""
        self.assertTrue(
            SESSION_JSON.exists(),
            f"Expected {SESSION_JSON} to exist. Session config is still hardcoded.",
        )


class TestSessionConfigSchema(unittest.TestCase):
    """Verify session.json has the required schema."""

    @classmethod
    def setUpClass(cls):
        if not SESSION_JSON.exists():
            raise unittest.SkipTest(
                "data/session.json does not exist yet -- schema tests cannot run"
            )
        with open(SESSION_JSON, "r") as f:
            cls.data = json.load(f)

    def test_session_json_schema(self):
        """session.json must contain all required keys so that both the
        front-end and Python scripts can read session parameters from one
        place."""
        required_keys = {
            "year",
            "biennium",
            "sessionType",
            "sessionStart",
            "sessionEnd",
            "siteTitle",
            "cutoffDates",
            "priorSession",
        }
        missing = required_keys - set(self.data.keys())
        self.assertFalse(
            missing,
            f"session.json is missing required keys: {sorted(missing)}",
        )

    def test_session_year_is_integer(self):
        """The year field must be an integer (e.g. 2027), not a string, so
        that downstream code can use it for arithmetic without conversion."""
        self.assertIsInstance(
            self.data.get("year"),
            int,
            "year must be an integer",
        )

    def test_biennium_format(self):
        """Biennium must match the WA legislature pattern YYYY-YY
        (e.g. '2027-28') so it can be passed directly to the WA SOAP API."""
        biennium = self.data.get("biennium", "")
        self.assertRegex(
            biennium,
            r"^\d{4}-\d{2}$",
            f"biennium '{biennium}' does not match expected pattern YYYY-YY",
        )


class TestSessionDates(unittest.TestCase):
    """Validate date fields in session.json."""

    @classmethod
    def setUpClass(cls):
        if not SESSION_JSON.exists():
            raise unittest.SkipTest(
                "data/session.json does not exist yet -- date tests cannot run"
            )
        with open(SESSION_JSON, "r") as f:
            cls.data = json.load(f)

    def test_session_dates_valid(self):
        """sessionStart must be before sessionEnd, and both must parse as
        valid ISO dates. This ensures the front-end can correctly display
        the session timeline."""
        start_str = self.data.get("sessionStart", "")
        end_str = self.data.get("sessionEnd", "")

        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)

        self.assertLess(
            start,
            end,
            f"sessionStart ({start_str}) must be before sessionEnd ({end_str})",
        )

    def test_cutoff_dates_ordered(self):
        """If cutoffDates is non-empty, the dates must be in chronological
        order. The front-end uses these to render a timeline, so out-of-order
        dates would produce a broken visualization."""
        cutoffs = self.data.get("cutoffDates", [])
        if not cutoffs:
            self.skipTest("cutoffDates is empty -- ordering check not applicable")

        # Extract date strings; cutoff entries may be dicts with a 'date' key
        # or plain strings -- handle both patterns.
        dates = []
        for entry in cutoffs:
            if isinstance(entry, dict):
                dates.append(datetime.fromisoformat(entry["date"]))
            else:
                dates.append(datetime.fromisoformat(entry))

        for i in range(len(dates) - 1):
            self.assertLessEqual(
                dates[i],
                dates[i + 1],
                f"cutoffDates not in chronological order at index {i}: "
                f"{dates[i]} > {dates[i + 1]}",
            )


if __name__ == "__main__":
    unittest.main()
