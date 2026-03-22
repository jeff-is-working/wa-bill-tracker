#!/usr/bin/env python3
"""
TDD Red Phase -- Acceptance criteria for session-namespaced cookie keys

Currently cookie keys like 'wa_tracker_tracked' and 'wa_tracker_notes' are
not namespaced by session year. When a new legislative session starts, old
tracked bills and notes from the prior session collide with the new session's
data. These tests verify that the modernized JS modules use dynamic,
year-prefixed cookie keys (e.g. 'wa_tracker_2027_tracked').

Run with: python -m pytest tests/test_cookie_namespacing.py -v
"""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
JS_DIR = PROJECT_ROOT / "js"


class TestCookieNamespacing(unittest.TestCase):
    """Verify cookie keys in JS modules are namespaced by session year."""

    def test_no_legacy_cookie_keys_in_js(self):
        """No JS file in js/ should contain the un-namespaced cookie key
        'wa_tracker_tracked'. All cookie keys must include the session year
        to prevent cross-session data collisions.

        If js/ does not exist yet, this test fails with a clear message
        indicating the modular structure has not been created."""
        if not JS_DIR.is_dir():
            self.fail(
                "js/ directory does not exist yet -- cannot check for legacy "
                "cookie keys. Create the modular JS structure first."
            )

        legacy_key = "wa_tracker_tracked"
        files_with_legacy = []

        for js_file in JS_DIR.glob("*.js"):
            content = js_file.read_text()
            if legacy_key in content:
                files_with_legacy.append(js_file.name)

        self.assertEqual(
            files_with_legacy,
            [],
            f"Legacy un-namespaced cookie key '{legacy_key}' found in: "
            f"{', '.join(files_with_legacy)}. Keys must include session year.",
        )

    def test_cookie_keys_use_year_prefix(self):
        """js/state.js must use dynamic year-based cookie key construction,
        e.g. template literals like `wa_tracker_${{year}}_tracked` or string
        concatenation like 'wa_tracker_' + year + '_tracked'. This ensures
        each session's user data is isolated."""
        state_js = JS_DIR / "state.js"
        if not state_js.exists():
            self.fail(
                "js/state.js does not exist yet -- cannot verify cookie key "
                "namespacing. Create the modular JS structure first."
            )

        content = state_js.read_text()

        # Look for evidence of dynamic key construction with a year variable.
        # Acceptable patterns:
        #   `wa_tracker_${year}_...`   (template literal)
        #   `wa_tracker_${...}_...`    (template literal with expression)
        #   'wa_tracker_' + year       (string concatenation)
        has_template = "wa_tracker_${" in content
        has_concat = "wa_tracker_' +" in content or 'wa_tracker_" +' in content

        self.assertTrue(
            has_template or has_concat,
            "js/state.js does not appear to use dynamic year-based cookie key "
            "construction. Expected template literal (wa_tracker_${...}) or "
            "string concatenation (wa_tracker_' + ...) patterns.",
        )


if __name__ == "__main__":
    unittest.main()
