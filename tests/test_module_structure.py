#!/usr/bin/env python3
"""
TDD Red Phase -- Acceptance criteria for the modular file structure

The app currently has a monolithic app.js (2310 lines) and inline CSS in
index.html. These tests define the target structure after the modernization:
JS split into modules under js/, CSS extracted to styles.css, and index.html
cleaned up to use ES module imports with no inline style blocks.

All tests should FAIL until the migration is complete (except
test_old_monolithic_app_js_removed, which will pass while app.js still exists
at the root -- see note on that test).

Run with: python -m pytest tests/test_module_structure.py -v
"""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestJSDirectoryStructure(unittest.TestCase):
    """Verify the js/ module directory and its expected modules exist."""

    def test_js_directory_exists(self):
        """A js/ directory must exist at the project root to hold the
        modularized JavaScript files extracted from the monolithic app.js."""
        self.assertTrue(
            (PROJECT_ROOT / "js").is_dir(),
            "js/ directory does not exist -- modules have not been created yet",
        )

    def test_js_config_module_exists(self):
        """js/config.js should hold session configuration, API endpoints,
        and constants extracted from the top of app.js."""
        self.assertTrue(
            (PROJECT_ROOT / "js" / "config.js").exists(),
            "js/config.js does not exist",
        )

    def test_js_state_module_exists(self):
        """js/state.js should manage application state including tracked
        bills, notes, and cookie persistence with session-namespaced keys."""
        self.assertTrue(
            (PROJECT_ROOT / "js" / "state.js").exists(),
            "js/state.js does not exist",
        )

    def test_js_data_module_exists(self):
        """js/data.js should handle fetching and transforming bill data
        from bills.json and session.json."""
        self.assertTrue(
            (PROJECT_ROOT / "js" / "data.js").exists(),
            "js/data.js does not exist",
        )

    def test_js_render_module_exists(self):
        """js/render.js should contain all DOM rendering logic: bill cards,
        filter panels, status badges, and timeline visualization."""
        self.assertTrue(
            (PROJECT_ROOT / "js" / "render.js").exists(),
            "js/render.js does not exist",
        )

    def test_js_notes_module_exists(self):
        """js/notes.js should encapsulate the user notes feature: adding,
        editing, deleting, and persisting notes per bill."""
        self.assertTrue(
            (PROJECT_ROOT / "js" / "notes.js").exists(),
            "js/notes.js does not exist",
        )

    def test_js_app_module_exists(self):
        """js/app.js is the entry-point module that wires together config,
        state, data, render, and notes modules."""
        self.assertTrue(
            (PROJECT_ROOT / "js" / "app.js").exists(),
            "js/app.js does not exist",
        )


class TestCSSExtraction(unittest.TestCase):
    """Verify CSS has been extracted from index.html into styles.css."""

    def test_styles_css_exists(self):
        """styles.css must exist at the project root, containing all CSS
        previously inlined in index.html's <style> blocks."""
        self.assertTrue(
            (PROJECT_ROOT / "styles.css").exists(),
            "styles.css does not exist -- CSS has not been extracted from index.html",
        )


class TestIndexHTMLModernization(unittest.TestCase):
    """Verify index.html has been updated for the modular architecture."""

    @classmethod
    def setUpClass(cls):
        index_path = PROJECT_ROOT / "index.html"
        if not index_path.exists():
            raise unittest.SkipTest("index.html not found")
        cls.content = index_path.read_text()

    def test_index_no_inline_style_blocks(self):
        """index.html must not contain <style> blocks after CSS extraction.
        All styles should be in the external styles.css file."""
        self.assertNotIn(
            "<style>",
            self.content,
            "index.html still contains inline <style> blocks -- "
            "CSS should be extracted to styles.css",
        )

    def test_index_uses_module_script(self):
        """index.html must use type='module' script tags to load the new
        ES module entry point instead of the old monolithic app.js."""
        self.assertIn(
            'type="module"',
            self.content,
            "index.html does not use type=\"module\" -- "
            "still loading scripts the old way",
        )


class TestMonolithicAppRemoval(unittest.TestCase):
    """Verify the old monolithic app.js has been removed after migration."""

    def test_old_monolithic_app_js_removed(self):
        """After migration, the root-level app.js should be removed since
        its functionality has been split into js/ modules.

        NOTE: This test will PASS while app.js still exists at the root
        during the pre-migration phase. It is included here to document the
        acceptance criterion that app.js must eventually be removed. The
        assertion is inverted on purpose -- it asserts app.js does NOT exist,
        which currently fails (app.js exists), meaning this test correctly
        fails during the Red phase."""
        self.assertFalse(
            (PROJECT_ROOT / "app.js").exists(),
            "app.js still exists at the project root -- "
            "it should be removed after migration to js/ modules",
        )


if __name__ == "__main__":
    unittest.main()
