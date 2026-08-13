"""
Demo 3 -- Verify-only.

Highlights /verify/{payment_txn_id} as a standalone compliance
check: given just a payment transaction id, re-derive the audit
record straight from the Algorand indexer, with no trust placed
in the API's local SQLite cache.

Usage:
    # Verify a specific payment you already redeemed:
    python 3_verify_only_demo.py <payment_txn_id>

    # Or with no argument, this script pays + redeems a fresh
    # resource first, then immediately verifies it:
    python 3_verify_only_demo.py
"""

import sys

import requests

from _demo_helpers import (
    API_BASE,
    get_algod_client,
    load_payer,
    check_balance,
    pay_challenge,
    hr,
)


def redeem_a_fresh_payment() -> str:
    """Pay for a resource so we have a real payment_txn_id to verify."""
    algod_client = get_algod_client()
    payer_addr, payer_key = load_payer()
    check_balance(algod_client, payer_addr)

    resource_id = "verify-demo-resource"
    url = f"{API_BASE}/resource/{resource_id}"

    resp = requests.get(url, timeout=30)
    challenge = resp.json()

    txid = pay_challenge(
        algod_client,
        payer_addr,
        payer_key,
        challenge["pay_to"],
        challenge["amount_microalgos"],
        challenge["nonce"],
    )

    resp = requests.get(url, headers={"X-PAYMENT": txid}, timeout=60)
    resp.raise_for_status()
    print(f"Paid and redeemed. payment_txn_id = {txid}")
    return txid


def verify(payment_txn_id: str):
    hr(f"GET /verify/{payment_txn_id}")

    resp = requests.get(f"{API_BASE}/verify/{payment_txn_id}", timeout=60)
    print(f"HTTP {resp.status_code}")

    verification = resp.json()
    print()
    print(f"found:                   {verification.get('found')}")
    print(f"note_verified_on_chain:  {verification.get('note_verified_on_chain')}")
    print(f"audit_explorer_url:      {verification.get('audit_explorer_url')}")

    record = verification.get("record")
    if record:
        print()
        print("Cached record (SQLite, for comparison only):")
        for k, v in record.items():
            print(f"  {k}: {v}")

    hr()
    if verification.get("note_verified_on_chain"):
        print("PASS: on-chain note matches the local cache.")
    else:
        print("FAIL or NOT FOUND: nothing to compare, or hashes diverged.")


def main():
    if len(sys.argv) > 1:
        payment_txn_id = sys.argv[1]
    else:
        print("No payment_txn_id given -- paying for a fresh resource first...")
        payment_txn_id = redeem_a_fresh_payment()

    verify(payment_txn_id)


if __name__ == "__main__":
    main()
