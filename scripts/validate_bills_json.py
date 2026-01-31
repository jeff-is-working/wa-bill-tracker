#!/usr/bin/env python3
"""
Validate data/bills.json for structural integrity.

Checks:
- File exists and is valid JSON
- totalBills matches len(bills)
- All bills have required fields
- No duplicate IDs
- Bill count hasn't dropped >10% from manifest (data loss guard)
- Status values are in the valid set

Exit 0 = pass, exit 1 = fail.
"""

import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

REQUIRED_FIELDS = {"id", "number", "title", "status", "priority", "topic", "session"}

VALID_STATUSES = {
    "prefiled", "introduced", "committee", "floor",
    "passed_origin", "opposite_chamber", "passed_both",
    "governor", "enacted", "partial_veto", "vetoed", "failed"
}


def validate(bills_path: Path = None, manifest_path: Path = None) -> list:
    """Validate bills.json and return a list of error strings (empty = pass)."""
    if bills_path is None:
        bills_path = DATA_DIR / "bills.json"
    if manifest_path is None:
        manifest_path = DATA_DIR / "manifest.json"

    errors = []

    # 1. File exists and is valid JSON
    if not bills_path.exists():
        return [f"bills.json not found at {bills_path}"]

    try:
        with open(bills_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"bills.json is not valid JSON: {e}"]

    bills = data.get("bills", [])
    total_bills = data.get("totalBills", 0)

    # 2. totalBills matches actual count
    if total_bills != len(bills):
        errors.append(
            f"totalBills ({total_bills}) does not match actual bill count ({len(bills)})"
        )

    # 3. Required fields present
    for i, bill in enumerate(bills):
        missing = REQUIRED_FIELDS - set(bill.keys())
        if missing:
            errors.append(f"Bill index {i} ({bill.get('id', '?')}) missing fields: {missing}")

    # 4. No duplicate IDs
    ids = [b.get("id") for b in bills]
    seen = set()
    for bill_id in ids:
        if bill_id in seen:
            errors.append(f"Duplicate bill ID: {bill_id}")
        seen.add(bill_id)

    # 5. Status values valid
    for bill in bills:
        status = bill.get("status", "")
        if status and status not in VALID_STATUSES:
            errors.append(f"Bill {bill.get('id', '?')} has invalid status: {status}")

    # 6. Data loss guard: compare against manifest bill count
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            manifest_count = manifest.get("billCount", 0)
            if manifest_count > 0 and len(bills) < manifest_count * 0.9:
                errors.append(
                    f"Bill count dropped >10%: manifest has {manifest_count}, "
                    f"bills.json has {len(bills)}"
                )
        except (json.JSONDecodeError, KeyError):
            pass  # Manifest unreadable — skip this check

    return errors


def main():
    errors = validate()
    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("Validation passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
