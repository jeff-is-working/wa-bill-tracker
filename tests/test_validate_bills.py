#!/usr/bin/env python3
"""Tests for the bills.json validation script."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.validate_bills_json import validate


def _write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


class TestValidateBillsJson(unittest.TestCase):
    """Tests for validate()."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bills_path = Path(self.tmpdir) / "bills.json"
        self.manifest_path = Path(self.tmpdir) / "manifest.json"

    def tearDown(self):
        for p in [self.bills_path, self.manifest_path]:
            if p.exists():
                os.unlink(p)
        os.rmdir(self.tmpdir)

    def _valid_bill(self, bill_id="HB1001"):
        return {
            "id": bill_id,
            "number": "HB 1001",
            "title": "Test bill",
            "status": "committee",
            "priority": "medium",
            "topic": "Education",
            "session": "2026",
        }

    def test_valid_data_passes(self):
        """Validation should pass with correct data."""
        _write_json(self.bills_path, {
            "totalBills": 1,
            "bills": [self._valid_bill()],
        })
        errors = validate(self.bills_path, self.manifest_path)
        self.assertEqual(errors, [])

    def test_missing_file(self):
        """Should report error if bills.json does not exist."""
        errors = validate(
            Path(self.tmpdir) / "nonexistent.json",
            self.manifest_path,
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("not found", errors[0])

    def test_invalid_json(self):
        """Should report error for malformed JSON."""
        with open(self.bills_path, "w") as f:
            f.write("not json {{{")
        errors = validate(self.bills_path, self.manifest_path)
        self.assertEqual(len(errors), 1)
        self.assertIn("not valid JSON", errors[0])

    def test_count_mismatch(self):
        """Should report error when totalBills doesn't match actual count."""
        _write_json(self.bills_path, {
            "totalBills": 5,
            "bills": [self._valid_bill()],
        })
        errors = validate(self.bills_path, self.manifest_path)
        self.assertTrue(any("totalBills" in e for e in errors))

    def test_missing_required_fields(self):
        """Should report error for bills missing required fields."""
        bill = {"id": "HB1001"}  # missing title, status, etc.
        _write_json(self.bills_path, {"totalBills": 1, "bills": [bill]})
        errors = validate(self.bills_path, self.manifest_path)
        self.assertTrue(any("missing fields" in e for e in errors))

    def test_duplicate_ids(self):
        """Should report error for duplicate bill IDs."""
        bill = self._valid_bill()
        _write_json(self.bills_path, {"totalBills": 2, "bills": [bill, bill]})
        errors = validate(self.bills_path, self.manifest_path)
        self.assertTrue(any("Duplicate" in e for e in errors))

    def test_invalid_status(self):
        """Should report error for unrecognized status values."""
        bill = self._valid_bill()
        bill["status"] = "banana"
        _write_json(self.bills_path, {"totalBills": 1, "bills": [bill]})
        errors = validate(self.bills_path, self.manifest_path)
        self.assertTrue(any("invalid status" in e for e in errors))

    def test_data_loss_guard(self):
        """Should flag if bill count drops >10% from manifest."""
        _write_json(self.manifest_path, {"billCount": 100, "bills": {}})
        _write_json(self.bills_path, {
            "totalBills": 50,
            "bills": [self._valid_bill(f"HB{i}") for i in range(50)],
        })
        errors = validate(self.bills_path, self.manifest_path)
        self.assertTrue(any("dropped" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
