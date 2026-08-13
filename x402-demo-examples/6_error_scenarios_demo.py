"""
Demo 6 -- Error / rejection scenarios.

No on-chain payment required -- this demo only exercises paths
that the API rejects before ever touching the Algorand indexer
for a valid payment. Good for showing the negative-path behavior
without spending any TestNet ALGO.

Usage:
    python 6_error_scenarios_demo.py
"""

import uuid

import requests

from _demo_helpers import API_BASE, hr


def scenario_no_payment():
    hr("Scenario A: request with no X-PAYMENT header")
    resource_id = f"error-demo-{uuid.uuid4().hex[:8]}"
    resp = requests.get(f"{API_BASE}/resource/{resource_id}", timeout=30)
    print(f"HTTP {resp.status_code} (expected 402)")
    print(resp.json())


def scenario_garbage_payment_header():
    hr("Scenario B: X-PAYMENT set to a made-up/garbage transaction id")
    resource_id = f"error-demo-{uuid.uuid4().hex[:8]}"
    resp = requests.get(
        f"{API_BASE}/resource/{resource_id}",
        headers={"X-PAYMENT": "NOTAREALALGORANDTXID000000000000000000000000000000000000000"},
        timeout=30,
    )
    print(f"HTTP {resp.status_code} (expected 402, payment not found by indexer)")
    print(resp.json())


def scenario_verify_unknown_txn():
    hr("Scenario C: /verify on a payment_txn_id the API has never seen")
    fake_txn = "UNKNOWNTXN" + uuid.uuid4().hex[:20].upper()
    resp = requests.get(f"{API_BASE}/verify/{fake_txn}", timeout=30)
    print(f"HTTP {resp.status_code} (expected 200, found=false)")
    print(resp.json())


def main():
    scenario_no_payment()
    scenario_garbage_payment_header()
    scenario_verify_unknown_txn()
    hr("DONE -- no ALGO was spent in this demo")


if __name__ == "__main__":
    main()
