#!/usr/bin/env python3
"""TDD Red Phase -- Ensures hardcoded session values are removed from codebase.

The monolithic app.js and scripts/fetch_all_bills.py both contain hardcoded
session dates, biennium strings, and year constants. After modernization, all
session values must come from data/session.json. These tests scan source files
for known hardcoded patterns and fail if any are found.

Run with: python -m pytest tests/test_no_hardcoded_sessions.py -v
"""

import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestNoHardcodedSessionValues(unittest.TestCase):
    """Scan source files for hardcoded session values that should be loaded
    from data/session.json instead."""

    def test_js_no_hardcoded_session_dates(self):
        """JavaScript must not contain hardcoded Date constructors with '2026'
        year strings. Session dates should come from session.json."""
        app_js = PROJECT_ROOT / "js" / "app.js"
        if not app_js.exists():
            self.skipTest("js/app.js does not exist yet")
        content = app_js.read_text()
        self.assertNotIn(
            "new Date('2026",
            content,
            "js/app.js contains hardcoded new Date('2026...') -- "
            "session dates should come from session.json",
        )

    def test_js_no_hardcoded_cutoff_dates(self):
        """JavaScript must not contain hardcoded cutoff date strings starting
        with '2026-'. Cutoff dates should come from session.json."""
        app_js = PROJECT_ROOT / "js" / "app.js"
        if not app_js.exists():
            self.skipTest("js/app.js does not exist yet")
        content = app_js.read_text()
        self.assertNotIn(
            "date: '2026-",
            content,
            "js/app.js contains hardcoded cutoff date 'date: \"2026-...' -- "
            "cutoff dates should come from session.json",
        )

    def test_pipeline_no_hardcoded_biennium(self):
        """The Python pipeline must not contain a hardcoded BIENNIUM constant.
        The biennium value should be loaded from session.json at runtime."""
        source = (PROJECT_ROOT / "scripts" / "fetch_all_bills.py").read_text()
        match = re.search(r'^BIENNIUM\s*=\s*"2025-26"', source, re.MULTILINE)
        self.assertIsNone(
            match,
            "scripts/fetch_all_bills.py still contains hardcoded "
            'BIENNIUM = "2025-26" -- value should come from session.json',
        )

    def test_pipeline_no_hardcoded_year(self):
        """The Python pipeline must not contain a hardcoded YEAR constant.
        The year value should be loaded from session.json at runtime."""
        source = (PROJECT_ROOT / "scripts" / "fetch_all_bills.py").read_text()
        match = re.search(r'^YEAR\s*=\s*2026', source, re.MULTILINE)
        self.assertIsNone(
            match,
            "scripts/fetch_all_bills.py still contains hardcoded "
            "YEAR = 2026 -- value should come from session.json",
        )


if __name__ == "__main__":
    unittest.main()
