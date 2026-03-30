#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "praetorian-cli",
# ]
# [tool.uv]
# find-links = [".."]
# ///

"""
End-to-end test script for bulk upsert SDK methods.

Exercises happy-path, negative, and edge-case scenarios against the bulk
asset/risk/attribute APIs and prints per-item results.

Usage:
    uv run scripts/test_bulk_upsert.py --account user@example.com
"""

import argparse
import json
import sys
import traceback

from praetorian_cli.sdk.chariot import Chariot
from praetorian_cli.sdk.keychain import Keychain


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run_test(sdk, test_num, description, entity, items, expect_api_error=False, raw_post=None):
    """Execute a single bulk-upsert test case and print results.

    Args:
        sdk: Chariot SDK instance.
        test_num: Test number for display.
        description: Human-readable test description.
        entity: One of 'asset', 'risk', 'attribute'.
        items: List of dicts to send to bulk_add.
        expect_api_error: If True, expect an exception and print it.
        raw_post: If set, a tuple (endpoint, body) to POST directly instead
                  of calling entity.bulk_add.  Used for edge-case tests.
    """
    print(f"\n=== Test {test_num}: {description} ===")
    print(f"Entity: {entity}")
    print(f"Items submitted: {len(items)}")

    try:
        if raw_post:
            endpoint, body = raw_post
            job = sdk.post(endpoint, body)
        elif entity == "asset":
            job = sdk.assets.bulk_add(items)
        elif entity == "risk":
            job = sdk.risks.bulk_add(items)
        elif entity == "attribute":
            job = sdk.attributes.bulk_add(items)
        else:
            print(f"  Unknown entity type: {entity}")
            print("---")
            return
    except KeyError as exc:
        # bulk_add accesses dict keys directly; malformed items raise KeyError
        if expect_api_error:
            print(f"Expected client-side error (KeyError): {exc}")
            print("---")
            return
        print(f"Unexpected KeyError in bulk_add: {exc}")
        traceback.print_exc()
        print("---")
        return
    except Exception as exc:
        if expect_api_error:
            print(f"Expected API error: {exc}")
            print("---")
            return
        print(f"Unexpected error: {exc}")
        traceback.print_exc()
        print("---")
        return

    job_key = job.get("key", "N/A")
    print(f"Job key: {job_key}")

    if job_key == "N/A":
        print("  No job key returned — cannot poll for results.")
        print(f"  Raw response: {json.dumps(job, indent=2)}")
        print("---")
        return

    # Wait for completion
    try:
        completed_job = sdk.jobs.wait(job_key, poll_interval=2, timeout=300)
    except TimeoutError as exc:
        print(f"  Timed out waiting for job: {exc}")
        print("---")
        return

    passed = sdk.jobs.is_passed(completed_job)
    failed = sdk.jobs.is_failed(completed_job)
    status_label = "PASSED" if passed else ("FAILED" if failed else completed_job.get("status", "UNKNOWN"))
    print(f"Job status: {status_label}")

    # Get results
    results = sdk.jobs.bulk_results(completed_job)
    if results:
        s = results.get("summary", {})
        print("Results:")
        print(
            f"  Summary: total={s.get('total', '?')}, "
            f"created={s.get('created', '?')}, "
            f"updated={s.get('updated', '?')}, "
            f"failed={s.get('failed', '?')}"
        )
        for r in results.get("results", []):
            if r.get("status") == "failed":
                print(f"  [FAILED]  {r.get('error', 'unknown error')}")
                print(f"            Input: {r.get('input', 'N/A')}")
            else:
                print(f"  [{r.get('status', '?').upper()}] {r.get('key', 'N/A')}")
    else:
        print("  No structured results available.")
        print(f"  Job config: {json.dumps(completed_job.get('config', {}), indent=2)}")
    print("---")


# ---------------------------------------------------------------------------
# Test definitions
# ---------------------------------------------------------------------------

def run_all_tests(sdk):
    # ------------------------------------------------------------------
    # Group 1: Bulk Assets
    # ------------------------------------------------------------------

    # Test 1 — Happy path: 5 valid assets with different types
    run_test(sdk, 1, "Bulk assets — happy path (5 valid)", "asset", [
        {"group": "testbulk.example.com", "identifier": "10.0.0.1"},
        {"group": "testbulk.example.com", "identifier": "10.0.0.2", "surface": "External"},
        {"group": "testbulk.example.com", "identifier": "10.0.0.3", "type": "asset"},
        {"group": "testbulk.example.com", "identifier": "app.testbulk.example.com"},
        {"group": "testbulk.example.com", "identifier": "10.0.0.4", "resource_type": "webapp"},
    ])

    # Test 2 — Mixed valid + invalid (domain ownership failures)
    run_test(sdk, 2, "Bulk assets — mixed valid + invalid (domain not owned)", "asset", [
        {"group": "testbulk.example.com", "identifier": "10.0.0.10"},
        {"group": "evil-domain-not-owned.com", "identifier": "6.6.6.1"},
        {"group": "evil-domain-not-owned.com", "identifier": "6.6.6.2"},
        {"group": "testbulk.example.com", "identifier": "10.0.0.11"},
    ])

    # Test 3 — All invalid / malformed items
    # NOTE: bulk_add accesses item['group'] and item['identifier'] directly,
    # so empty dicts / missing keys will raise KeyError client-side.
    run_test(sdk, 3, "Bulk assets — all invalid / malformed items", "asset", [
        {},
        {"group": ""},
        {"identifier": "10.0.0.99"},
    ], expect_api_error=True)

    # Test 4 — Duplicate assets in same batch
    run_test(sdk, 4, "Bulk assets — duplicate asset in batch", "asset", [
        {"group": "testbulk.example.com", "identifier": "10.0.0.20"},
        {"group": "testbulk.example.com", "identifier": "10.0.0.20"},
    ])

    # ------------------------------------------------------------------
    # Group 2: Bulk Risks
    # ------------------------------------------------------------------

    # Test 5 — Happy path: risks on assets created in test 1
    run_test(sdk, 5, "Bulk risks — happy path", "risk", [
        {"asset_key": "#asset#testbulk.example.com#10.0.0.1", "name": "CVE-2024-0001", "status": "TI"},
        {
            "asset_key": "#asset#testbulk.example.com#10.0.0.2",
            "name": "CVE-2024-0002",
            "status": "TI",
            "title": "Test Vulnerability",
            "tags": ["test", "bulk"],
        },
    ])

    # Test 6 — Risks on non-existent assets
    run_test(sdk, 6, "Bulk risks — non-existent assets", "risk", [
        {"asset_key": "#asset#nonexistent.example.com#99.99.99.1", "name": "CVE-2024-9901", "status": "TI"},
        {"asset_key": "#asset#nonexistent.example.com#99.99.99.2", "name": "CVE-2024-9902", "status": "TI"},
        {"asset_key": "#asset#testbulk.example.com#10.0.0.1", "name": "CVE-2024-0003", "status": "TI"},
    ])

    # Test 7 — Invalid risk data
    run_test(sdk, 7, "Bulk risks — invalid data", "risk", [
        {"asset_key": "", "name": "CVE-2024-BAD1", "status": "TI"},
        {"asset_key": "#asset#testbulk.example.com#10.0.0.1", "name": "", "status": "TI"},
        {},
    ], expect_api_error=True)

    # ------------------------------------------------------------------
    # Group 3: Bulk Attributes
    # ------------------------------------------------------------------

    # Test 8 — Happy path: attributes on assets from test 1
    run_test(sdk, 8, "Bulk attributes — happy path", "attribute", [
        {"source_key": "#asset#testbulk.example.com#10.0.0.1", "name": "port", "value": "443"},
        {"source_key": "#asset#testbulk.example.com#10.0.0.1", "name": "service", "value": "https"},
        {"source_key": "#asset#testbulk.example.com#10.0.0.2", "name": "port", "value": "80"},
    ])

    # Test 9 — Attributes on non-existent entities
    run_test(sdk, 9, "Bulk attributes — non-existent entities", "attribute", [
        {"source_key": "#asset#nonexistent#99.99.99.99", "name": "port", "value": "443"},
        {"source_key": "#risk#nonexistent#CVE-FAKE", "name": "cvss", "value": "9.8"},
        {"source_key": "#asset#testbulk.example.com#10.0.0.1", "name": "test-attr", "value": "ok"},
    ])

    # Test 10 — Update existing attribute (re-add same from test 8)
    run_test(sdk, 10, "Bulk attributes — update existing (should return updated)", "attribute", [
        {"source_key": "#asset#testbulk.example.com#10.0.0.1", "name": "port", "value": "443"},
    ])

    # ------------------------------------------------------------------
    # Group 4: Edge cases
    # ------------------------------------------------------------------

    # Test 11 — Empty items array (should get 400 from API)
    run_test(
        sdk, 11, "Edge case — empty items array (expect 400)", "asset", [],
        expect_api_error=True,
        raw_post=("bulk/asset", {"action": "upsert", "items": []}),
    )

    # Test 12 — Single item (verify bulk works with 1 item)
    run_test(sdk, 12, "Edge case — single item bulk", "asset", [
        {"group": "testbulk.example.com", "identifier": "10.0.0.99"},
    ])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="End-to-end test script for bulk upsert SDK methods."
    )
    parser.add_argument(
        "--account",
        required=True,
        help="Account email to make uploads to (e.g., user@example.com)",
    )
    args = parser.parse_args()

    print(f"Initializing Chariot SDK for account: {args.account}")
    keychain = Keychain(account=args.account)
    sdk = Chariot(keychain)

    print("Running bulk upsert e2e tests...")
    print("=" * 60)

    run_all_tests(sdk)

    print("\n" + "=" * 60)
    print("All tests completed.")


if __name__ == "__main__":
    main()
