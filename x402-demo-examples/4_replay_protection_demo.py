"""
Demo 4 -- Replay protection.

Pays for a resource once, redeems it successfully, then
deliberately replays the SAME X-PAYMENT header a second time to
show the API rejects it with HTTP 409 instead of writing a
second audit note (which would double-charge the audit ledger
for a single payment).

Usage:
    python 4_replay_protection_demo.py
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

RESOURCE_ID = "replay-protection-demo"


def main():
    algod_client = get_algod_client()
    payer_addr, payer_key = load_payer()
    check_balance(algod_client, payer_addr)

    url = f"{API_BASE}/resource/{RESOURCE_ID}"

    hr("STEP 1: pay + redeem normally")
    challenge = requests.get(url, timeout=30).json()
    txid = pay_challenge(
        algod_client,
        payer_addr,
        payer_key,
        challenge["pay_to"],
        challenge["amount_microalgos"],
        challenge["nonce"],
    )
    print(f"Payment txn: {txid}")

    first = requests.get(url, headers={"X-PAYMENT": txid}, timeout=60)
    print(f"First redemption -> HTTP {first.status_code}")
    if first.status_code != 200:
        raise SystemExit(f"Expected 200 on first redemption: {first.text}")
    print(f"audit_txn_id: {first.json()['audit_txn_id']}")

    hr("STEP 2: replay the SAME X-PAYMENT header")
    second = requests.get(url, headers={"X-PAYMENT": txid}, timeout=60)
    print(f"Second redemption -> HTTP {second.status_code}")
    print(second.json())

    hr("RESULT")
    if second.status_code == 409:
        print("PASS: replay was rejected with 409 Conflict, as expected.")
    else:
        print("UNEXPECTED: replay protection did not trigger.")


if __name__ == "__main__":
    main()
