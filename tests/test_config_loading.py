#!/usr/bin/env python3
"""TDD Red Phase -- Tests that Python pipeline reads session config from data/session.json
instead of hardcoded constants.

The fetch_all_bills.py script currently hardcodes BIENNIUM and YEAR as module-level
constants. These tests define the contract for a load_session_config() function that
reads values from data/session.json instead. All tests should FAIL until the pipeline
is refactored.

Run with: python -m pytest tests/test_config_loading.py -v
"""

import json
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_JSON = PROJECT_ROOT / "data" / "session.json"
FETCH_ALL_BILLS = PROJECT_ROOT / "scripts" / "fetch_all_bills.py"


class TestPipelineSessionConfig(unittest.TestCase):
    """Verify that the pipeline module exposes a load_session_config function
    and no longer hardcodes session values."""

    def test_fetch_all_bills_has_load_session_config(self):
        """scripts/fetch_all_bills.py must expose a callable load_session_config()
        function that reads session parameters from data/session.json, replacing
        the hardcoded BIENNIUM and YEAR constants."""
        import scripts.fetch_all_bills as module

        self.assertTrue(
            hasattr(module, "load_session_config"),
            "fetch_all_bills module does not have a 'load_session_config' attribute -- "
            "function has not been created yet",
        )
        self.assertTrue(
            callable(getattr(module, "load_session_config", None)),
            "fetch_all_bills.load_session_config exists but is not callable",
        )

    def test_biennium_not_hardcoded(self):
        """The pipeline must not contain a bare BIENNIUM = \"2025-26\" constant.
        Biennium should be loaded dynamically from session.json."""
        source = FETCH_ALL_BILLS.read_text()
        match = re.search(r'^BIENNIUM\s*=\s*"2025-26"', source, re.MULTILINE)
        self.assertIsNone(
            match,
            "fetch_all_bills.py still contains hardcoded BIENNIUM = \"2025-26\" -- "
            "value should come from session.json",
        )

    def test_year_not_hardcoded(self):
        """The pipeline must not contain a bare YEAR = 2026 constant.
        Year should be loaded dynamically from session.json."""
        source = FETCH_ALL_BILLS.read_text()
        match = re.search(r'^YEAR\s*=\s*2026', source, re.MULTILINE)
        self.assertIsNone(
            match,
            "fetch_all_bills.py still contains hardcoded YEAR = 2026 -- "
            "value should come from session.json",
        )


class TestSessionJsonPipelineContract(unittest.TestCase):
    """Verify that data/session.json provides the fields the pipeline needs."""

    @classmethod
    def setUpClass(cls):
        if not SESSION_JSON.exists():
            raise unittest.SkipTest(
                "data/session.json does not exist yet -- pipeline contract tests cannot run"
            )
        with open(SESSION_JSON, "r") as f:
            cls.data = json.load(f)

    def test_session_json_has_biennium(self):
        """session.json must include a 'biennium' key so the pipeline can pass
        it to the WA legislature SOAP API."""
        self.assertIn(
            "biennium",
            self.data,
            "session.json is missing 'biennium' key",
        )

    def test_session_json_has_year(self):
        """session.json must include a 'year' key as an integer so the pipeline
        can use it for date calculations and API calls."""
        self.assertIn(
            "year",
            self.data,
            "session.json is missing 'year' key",
        )
        self.assertIsInstance(
            self.data["year"],
            int,
            f"session.json 'year' should be an integer, got {type(self.data['year']).__name__}",
        )

    def test_session_json_biennium_matches_year(self):
        """The year must fall within the biennium range. WA bienniums use the
        first year: biennium '2025-26' covers years 2025 and 2026, while
        '2027-28' covers 2027 and 2028."""
        year = self.data.get("year")
        biennium = self.data.get("biennium", "")
        if year is None:
            self.skipTest("year key missing -- cannot validate biennium alignment")
        # Parse biennium "YYYY-YY" into two full years
        parts = biennium.split("-")
        if len(parts) != 2:
            self.fail(f"biennium '{biennium}' does not match YYYY-YY format")
        first_year = int(parts[0])
        second_year = int(parts[0][:2] + parts[1])
        self.assertIn(
            year,
            (first_year, second_year),
            f"year {year} does not fall within biennium '{biennium}' "
            f"(covers {first_year}-{second_year})",
        )


if __name__ == "__main__":
    unittest.main()
