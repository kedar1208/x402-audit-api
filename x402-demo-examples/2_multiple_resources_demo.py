"""
Demo 2 -- Multiple resources in one session.

Shows that every resource_id is independently metered: each one
needs its own 402 -> pay -> redeem cycle, and each produces its
own audit transaction on-chain.

Usage:
    python 2_multiple_resources_demo.py
"""

import requests

from _demo_helpers import (
    API_BASE,
    get_algod_client,
    load_payer,
    check_balance,
    pay_challenge,
    hr,
)

RESOURCE_IDS = [
    "agent-task-42",
    "agent-task-43",
    "report-generation-7",
]


def buy_resource(algod_client, payer_addr, payer_key, resource_id: str) -> dict:
    url = f"{API_BASE}/resource/{resource_id}"

    hr(f"Resource: {resource_id}")

    # Step 1: expect 402
    resp = requests.get(url, timeout=30)
    print(f"Initial request -> HTTP {resp.status_code}")
    if resp.status_code != 402:
        raise SystemExit(f"Expected 402, got {resp.status_code}: {resp.text}")

    challenge = resp.json()
    pay_to = challenge["pay_to"]
    amount = challenge["amount_microalgos"]
    nonce = challenge["nonce"]
    print(f"Pay {amount / 1_000_000} ALGO to {pay_to}")

    # Step 2: pay on-chain
    txid = pay_challenge(algod_client, payer_addr, payer_key, pay_to, amount, nonce)
    print(f"Paid. Payment txn: {txid}")

    # Step 3: redeem
    resp = requests.get(url, headers={"X-PAYMENT": txid}, timeout=60)
    print(f"Redeem -> HTTP {resp.status_code}")
    if resp.status_code != 200:
        raise SystemExit(f"Redemption failed: {resp.text}")

    result = resp.json()
    print(f"audit_txn_id: {result['audit_txn_id']}")
    print(f"payload_hash: {result['payload_hash']}")
    return result


def main():
    algod_client = get_algod_client()
    payer_addr, payer_key = load_payer()
    balance = check_balance(algod_client, payer_addr)
    print(f"Payer: {payer_addr}  (balance {balance / 1_000_000:.6f} ALGO)")

    results = []
    for resource_id in RESOURCE_IDS:
        results.append(buy_resource(algod_client, payer_addr, payer_key, resource_id))

    hr("SUMMARY")
    for resource_id, result in zip(RESOURCE_IDS, results):
        print(f"{resource_id:<24} audit_txn={result['audit_txn_id']}")


if __name__ == "__main__":
    main()
