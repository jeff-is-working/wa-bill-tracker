#!/usr/bin/env python3
"""TDD Red Phase -- Tests that JS modules exist and export expected functions.
Verifies by grepping source files for export/function names.

After the monolithic app.js is split into ES modules under js/, each module
must export specific functions that the rest of the application depends on.
These tests read JS source files as text and check for the presence of expected
export names. All tests should FAIL until the modules are created with the
correct exports.

Run with: python -m pytest tests/test_js_module_exports.py -v
"""

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestConfigModuleExports(unittest.TestCase):
    """Verify js/config.js exports configuration loading functionality."""

    @classmethod
    def setUpClass(cls):
        config_path = PROJECT_ROOT / "js" / "config.js"
        if not config_path.exists():
            raise unittest.SkipTest("js/config.js does not exist yet")
        cls.content = config_path.read_text()

    def test_exports_load_config(self):
        """config.js must export a loadConfig function that fetches and parses
        session.json at runtime."""
        self.assertIn("export", self.content, "config.js has no export statements")
        self.assertIn(
            "loadConfig",
            self.content,
            "config.js does not define or export loadConfig",
        )

    def test_loads_session_json(self):
        """config.js must reference session.json to load session configuration
        dynamically instead of hardcoding values."""
        self.assertIn(
            "session.json",
            self.content,
            "config.js does not reference session.json -- "
            "configuration may still be hardcoded",
        )

    def test_no_hardcoded_2026(self):
        """config.js must not contain the literal '2026' since all session
        year values should come from session.json."""
        self.assertNotIn(
            "2026",
            self.content,
            "config.js contains hardcoded '2026' -- "
            "year values should come from session.json",
        )


class TestStateModuleExports(unittest.TestCase):
    """Verify js/state.js exports state management functionality."""

    @classmethod
    def setUpClass(cls):
        state_path = PROJECT_ROOT / "js" / "state.js"
        if not state_path.exists():
            raise unittest.SkipTest("js/state.js does not exist yet")
        cls.content = state_path.read_text()

    def test_exports_app_state(self):
        """state.js must export an APP_STATE object that holds the shared
        application state across modules."""
        self.assertIn(
            "APP_STATE",
            self.content,
            "state.js does not define APP_STATE",
        )

    def test_exports_cookie_manager(self):
        """state.js must export a CookieManager that handles reading and
        writing session-namespaced cookies."""
        self.assertIn(
            "CookieManager",
            self.content,
            "state.js does not define CookieManager",
        )

    def test_has_dynamic_year_in_keys(self):
        """state.js must use dynamic year values in cookie keys via template
        literals (e.g., ${year} or ${config.year}) rather than hardcoding
        the year into key names."""
        has_template = "${" in self.content and "wa_tracker" in self.content
        self.assertTrue(
            has_template,
            "state.js does not appear to use template literals for dynamic "
            "year in cookie keys -- keys may be hardcoded",
        )

    def test_no_hardcoded_cookie_keys(self):
        """state.js must not contain the literal string 'wa_tracker_tracked'
        as a hardcoded cookie key. Cookie keys should be dynamically
        generated with the session year."""
        self.assertNotIn(
            "'wa_tracker_tracked'",
            self.content,
            "state.js contains hardcoded cookie key 'wa_tracker_tracked' -- "
            "keys should include dynamic year",
        )


class TestDataModuleExports(unittest.TestCase):
    """Verify js/data.js exports data transformation functions."""

    @classmethod
    def setUpClass(cls):
        data_path = PROJECT_ROOT / "js" / "data.js"
        if not data_path.exists():
            raise unittest.SkipTest("js/data.js does not exist yet")
        cls.content = data_path.read_text()

    def test_exports_filter_bills(self):
        """data.js must export a filterBills function for applying search
        and filter criteria to the bill list."""
        self.assertIn(
            "filterBills",
            self.content,
            "data.js does not define filterBills",
        )

    def test_exports_get_bill_cutoff_status(self):
        """data.js must export a getBillCutoffStatus function that determines
        where a bill stands relative to legislative cutoff dates."""
        self.assertIn(
            "getBillCutoffStatus",
            self.content,
            "data.js does not define getBillCutoffStatus",
        )


class TestRenderModuleExports(unittest.TestCase):
    """Verify js/render.js exports DOM rendering functions."""

    @classmethod
    def setUpClass(cls):
        render_path = PROJECT_ROOT / "js" / "render.js"
        if not render_path.exists():
            raise unittest.SkipTest("js/render.js does not exist yet")
        cls.content = render_path.read_text()

    def test_exports_render_bills(self):
        """render.js must export a renderBills function that builds the bill
        card DOM elements."""
        self.assertIn(
            "renderBills",
            self.content,
            "render.js does not define renderBills",
        )

    def test_exports_update_stats(self):
        """render.js must export an updateStats function that refreshes the
        statistics panel."""
        self.assertIn(
            "updateStats",
            self.content,
            "render.js does not define updateStats",
        )

    def test_exports_render_session_stats(self):
        """render.js must export a renderSessionStats function that displays
        session-level statistics including cutoff timeline."""
        self.assertIn(
            "renderSessionStats",
            self.content,
            "render.js does not define renderSessionStats",
        )


class TestNotesModuleExports(unittest.TestCase):
    """Verify js/notes.js exports user notes functionality."""

    @classmethod
    def setUpClass(cls):
        notes_path = PROJECT_ROOT / "js" / "notes.js"
        if not notes_path.exists():
            raise unittest.SkipTest("js/notes.js does not exist yet")
        cls.content = notes_path.read_text()

    def test_exports_open_note_modal(self):
        """notes.js must export an openNoteModal function that opens the
        note editing dialog for a given bill."""
        self.assertIn(
            "openNoteModal",
            self.content,
            "notes.js does not define openNoteModal",
        )

    def test_exports_save_note(self):
        """notes.js must export a saveNote function that persists a user's
        note for a bill."""
        self.assertIn(
            "saveNote",
            self.content,
            "notes.js does not define saveNote",
        )


class TestAppModuleInit(unittest.TestCase):
    """Verify js/app.js imports all modules and initializes the application."""

    @classmethod
    def setUpClass(cls):
        app_path = PROJECT_ROOT / "js" / "app.js"
        if not app_path.exists():
            raise unittest.SkipTest("js/app.js does not exist yet")
        cls.content = app_path.read_text()

        index_path = PROJECT_ROOT / "index.html"
        cls.index_content = None
        if index_path.exists():
            cls.index_content = index_path.read_text()

    def test_imports_config(self):
        """app.js must import from the config module to load session
        configuration at startup."""
        has_import = (
            "from './config" in self.content or 'from "./config' in self.content
        )
        self.assertTrue(
            has_import,
            "app.js does not import from ./config module",
        )

    def test_imports_state(self):
        """app.js must import from the state module to access shared
        application state."""
        has_import = (
            "from './state" in self.content or 'from "./state' in self.content
        )
        self.assertTrue(
            has_import,
            "app.js does not import from ./state module",
        )

    def test_imports_data(self):
        """app.js must import from the data module for bill fetching
        and transformation."""
        has_import = (
            "from './data" in self.content or 'from "./data' in self.content
        )
        self.assertTrue(
            has_import,
            "app.js does not import from ./data module",
        )

    def test_imports_render(self):
        """app.js must import from the render module for DOM rendering."""
        has_import = (
            "from './render" in self.content or 'from "./render' in self.content
        )
        self.assertTrue(
            has_import,
            "app.js does not import from ./render module",
        )

    def test_has_init(self):
        """app.js must define an init function (or equivalent) that
        bootstraps the application."""
        self.assertIn(
            "init",
            self.content,
            "app.js does not contain an init function",
        )

    def test_index_uses_type_module(self):
        """index.html must load JavaScript with type=\"module\" to enable
        ES module imports."""
        if self.index_content is None:
            self.skipTest("index.html not found")
        self.assertIn(
            'type="module"',
            self.index_content,
            "index.html does not use type=\"module\" for script loading -- "
            "ES modules will not work",
        )


if __name__ == "__main__":
    unittest.main()
