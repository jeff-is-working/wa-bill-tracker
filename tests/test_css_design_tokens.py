#!/usr/bin/env python3
"""
TDD Red Phase -- Sprint 2: CSS Extraction + C6S Branding

These tests define acceptance criteria for Sprint 2. They are expected to
FAIL until the implementation work (external stylesheet, design tokens,
status colors, inline-style removal) is complete.

Run with: python -m pytest tests/test_css_design_tokens.py -v
"""

import re
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestStylesheetExists(unittest.TestCase):
    """Verify that an external stylesheet exists and is linked from index.html.

    TDD Red Phase -- these tests fail until styles.css is created and
    index.html is updated to reference it.
    """

    def test_styles_css_exists(self):
        """styles.css must exist at the project root."""
        styles_path = PROJECT_ROOT / "styles.css"
        self.assertTrue(
            styles_path.exists(),
            "styles.css does not exist -- Sprint 2 requires an external stylesheet",
        )

    def test_index_links_stylesheet(self):
        """index.html must contain a <link> to styles.css."""
        index_path = PROJECT_ROOT / "index.html"
        self.assertTrue(index_path.exists(), "index.html not found")
        content = index_path.read_text()
        self.assertIn(
            'rel="stylesheet"',
            content,
            'index.html is missing rel="stylesheet" link',
        )
        self.assertIn(
            'href="styles.css"',
            content,
            'index.html is missing href="styles.css"',
        )


class TestC6SDesignTokens(unittest.TestCase):
    """Verify that styles.css declares C6S brand and semantic CSS custom properties.

    TDD Red Phase -- these tests fail until the design-token variables are
    added to styles.css.
    """

    @classmethod
    def setUpClass(cls):
        css_path = PROJECT_ROOT / "styles.css"
        if not css_path.exists():
            raise unittest.SkipTest("styles.css does not exist yet")
        cls.css = css_path.read_text()

    def test_has_c6s_navy(self):
        """styles.css must define the --c6s-navy custom property."""
        self.assertIn("--c6s-navy", self.css)

    def test_has_c6s_accent(self):
        """styles.css must define the --c6s-accent custom property."""
        self.assertIn("--c6s-accent", self.css)

    def test_has_c6s_white(self):
        """styles.css must define the --c6s-white custom property."""
        self.assertIn("--c6s-white", self.css)

    def test_has_c6s_slate(self):
        """styles.css must define the --c6s-slate custom property."""
        self.assertIn("--c6s-slate", self.css)

    def test_has_semantic_bg_variable(self):
        """styles.css must define a --bg semantic variable."""
        self.assertIn("--bg:", self.css)

    def test_has_semantic_text_variable(self):
        """styles.css must define a --text semantic variable."""
        self.assertIn("--text:", self.css)

    def test_has_semantic_accent_variable(self):
        """styles.css must define an --accent semantic variable."""
        self.assertIn("--accent:", self.css)


class TestStatusColors(unittest.TestCase):
    """Verify that styles.css declares status-specific color tokens.

    TDD Red Phase -- these tests fail until status color variables are added
    to styles.css.
    """

    @classmethod
    def setUpClass(cls):
        css_path = PROJECT_ROOT / "styles.css"
        if not css_path.exists():
            raise unittest.SkipTest("styles.css does not exist yet")
        cls.css = css_path.read_text()

    def test_has_status_enacted_color(self):
        """styles.css must define --status-enacted."""
        self.assertIn("--status-enacted", self.css)

    def test_has_status_governor_color(self):
        """styles.css must define --status-governor."""
        self.assertIn("--status-governor", self.css)

    def test_has_status_active_color(self):
        """styles.css must define --status-active."""
        self.assertIn("--status-active", self.css)

    def test_has_status_failed_color(self):
        """styles.css must define --status-failed."""
        self.assertIn("--status-failed", self.css)

    def test_has_status_prefiled_color(self):
        """styles.css must define --status-prefiled."""
        self.assertIn("--status-prefiled", self.css)

    def test_has_status_passed_color(self):
        """styles.css must define --status-passed."""
        self.assertIn("--status-passed", self.css)


class TestNoInlineColors(unittest.TestCase):
    """Verify that index.html has no hard-coded hex colors in inline style attributes.

    TDD Red Phase -- index.html currently contains inline styles with hex
    color values. This test will fail until those are migrated to the
    external stylesheet.
    """

    def test_no_hardcoded_hex_colors_in_html_style_attrs(self):
        """index.html style= attributes must not contain #hex color literals."""
        index_path = PROJECT_ROOT / "index.html"
        self.assertTrue(index_path.exists(), "index.html not found")
        content = index_path.read_text()

        # Find all style="..." attribute values, then look for hex colors inside them
        style_attrs = re.findall(r'style="([^"]*)"', content)
        hex_in_styles = [
            attr for attr in style_attrs if re.search(r"#[0-9a-fA-F]{3,8}", attr)
        ]
        self.assertEqual(
            len(hex_in_styles),
            0,
            f"Found {len(hex_in_styles)} inline style attribute(s) with hard-coded "
            f"hex colors -- migrate these to styles.css: {hex_in_styles[:5]}",
        )


if __name__ == "__main__":
    unittest.main()
