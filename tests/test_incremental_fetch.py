#!/usr/bin/env python3
"""Tests for the incremental bill fetcher."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fetch_all_bills import compute_content_hash
from scripts.fetch_bills_incremental import (
    TERMINAL_STATUSES,
    load_manifest,
    merge_bills,
    select_bills_for_refresh,
)


class TestComputeContentHash(unittest.TestCase):
    """Tests for compute_content_hash()."""

    def test_deterministic(self):
        """Same inputs always produce the same hash."""
        h1 = compute_content_hash("committee", "Referred to Finance", "2026-01-20", "Smith")
        h2 = compute_content_hash("committee", "Referred to Finance", "2026-01-20", "Smith")
        self.assertEqual(h1, h2)

    def test_different_inputs(self):
        """Different inputs produce different hashes."""
        h1 = compute_content_hash("committee", "Referred to Finance", "2026-01-20", "Smith")
        h2 = compute_content_hash("floor", "Referred to Finance", "2026-01-20", "Smith")
        self.assertNotEqual(h1, h2)

    def test_hash_length(self):
        """Hash should be 8 hex characters."""
        h = compute_content_hash("committee", "line", "2026-01-01", "Jones")
        self.assertEqual(len(h), 8)
        # Should be valid hex
        int(h, 16)


class TestSelectBillsForRefresh(unittest.TestCase):
    """Tests for select_bills_for_refresh()."""

    def _make_manifest(self, bills_meta):
        return {"bills": bills_meta}

    def test_excludes_terminal(self):
        """Bills in terminal status should be excluded."""
        manifest = self._make_manifest({
            "HB1001": {"status": "enacted", "lastFetched": "2026-01-01T00:00:00"},
            "HB1002": {"status": "committee", "lastFetched": "2026-01-01T00:00:00"},
            "HB1003": {"status": "vetoed", "lastFetched": "2026-01-01T00:00:00"},
        })
        result = select_bills_for_refresh(manifest, max_batch=10)
        self.assertEqual(result, ["HB1002"])

    def test_sorts_by_age(self):
        """Most stale bills should be selected first."""
        manifest = self._make_manifest({
            "HB1001": {"status": "committee", "lastFetched": "2026-01-03T00:00:00"},
            "HB1002": {"status": "floor", "lastFetched": "2026-01-01T00:00:00"},
            "HB1003": {"status": "introduced", "lastFetched": "2026-01-02T00:00:00"},
        })
        result = select_bills_for_refresh(manifest, max_batch=10)
        self.assertEqual(result, ["HB1002", "HB1003", "HB1001"])

    def test_respects_max_batch(self):
        """Should not return more bills than max_batch."""
        bills_meta = {}
        for i in range(100):
            bills_meta[f"HB{1000+i}"] = {
                "status": "committee",
                "lastFetched": f"2026-01-{(i % 28)+1:02d}T00:00:00",
            }
        manifest = self._make_manifest(bills_meta)
        result = select_bills_for_refresh(manifest, max_batch=5)
        self.assertEqual(len(result), 5)

    def test_empty_manifest(self):
        """Empty manifest should return empty list."""
        result = select_bills_for_refresh({}, max_batch=10)
        self.assertEqual(result, [])


class TestLoadManifest(unittest.TestCase):
    """Tests for load_manifest()."""

    def test_missing_file(self):
        """Should return empty dict if manifest does not exist."""
        with patch("scripts.fetch_bills_incremental.DATA_DIR", Path("/nonexistent/path")):
            result = load_manifest()
            self.assertEqual(result, {})


class TestMergeBills(unittest.TestCase):
    """Tests for merge_bills()."""

    def test_update_existing(self):
        """Updated bills should replace existing ones by ID."""
        existing = [
            {"id": "HB1001", "title": "Old title", "status": "committee"},
            {"id": "HB1002", "title": "Unchanged", "status": "floor"},
        ]
        updated = {
            "HB1001": {"id": "HB1001", "title": "New title", "status": "floor"},
        }
        result = merge_bills(existing, updated)
        self.assertEqual(len(result), 2)
        hb1001 = next(b for b in result if b["id"] == "HB1001")
        self.assertEqual(hb1001["title"], "New title")

    def test_add_new(self):
        """New bills should be appended."""
        existing = [{"id": "HB1001", "title": "Existing"}]
        updated = {"HB1002": {"id": "HB1002", "title": "Brand new"}}
        result = merge_bills(existing, updated)
        self.assertEqual(len(result), 2)

    def test_no_duplicates(self):
        """Merge should not create duplicate bill IDs."""
        existing = [{"id": "HB1001", "title": "A"}]
        updated = {"HB1001": {"id": "HB1001", "title": "B"}}
        result = merge_bills(existing, updated)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "B")

    def test_manifest_roundtrip(self):
        """Write and read a manifest through a temp file."""
        manifest = {
            "lastFullSync": "2026-01-30T00:00:00",
            "billCount": 1,
            "bills": {
                "HB1001": {"status": "committee", "contentHash": "abc12345", "lastFetched": "2026-01-30T00:00:00"}
            },
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(manifest, f)
            tmp_path = f.name
        try:
            with open(tmp_path, "r") as f:
                loaded = json.load(f)
            self.assertEqual(loaded["bills"]["HB1001"]["contentHash"], "abc12345")
            self.assertEqual(loaded["billCount"], 1)
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
