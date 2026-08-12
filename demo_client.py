"""
End-to-end demo of the x402 Payment Logging & Audit Infrastructure.

Flow:

1. Request protected resource
2. Receive HTTP 402
3. Read payment instructions
4. Pay the Service account on Algorand TestNet
5. Wait for payment confirmation
6. Retry API with X-PAYMENT transaction ID
7. API verifies the payment
8. API creates permanent audit transaction
9. Verify the audit record from the blockchain

Usage:

    python demo_client.py

Requirements:

- FastAPI server running locally
- Funded TestNet Payer account
- PAYER_MNEMONIC in .env
"""

import os
import sys

import requests
from dotenv import load_dotenv

from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod


# ============================================================
# Load .env
# ============================================================

load_dotenv()


# ============================================================
# Configuration
# ============================================================

API_BASE = os.getenv(
    "API_BASE",
    "http://127.0.0.1:8000",
)

ALGOD_ADDRESS = os.getenv(
    "ALGOD_ADDRESS",
    "https://testnet-api.algonode.cloud",
)

ALGOD_TOKEN = os.getenv(
    "ALGOD_TOKEN",
    "",
)

PAYER_MNEMONIC = os.getenv(
    "PAYER_MNEMONIC",
    "",
)

RESOURCE_ID = "agent-task-42"


# ============================================================
# Main demo
# ============================================================

def main():

    print("=" * 70)
    print("PS0405 - x402 Payment Logging & Audit Demo")
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # Check payer mnemonic
    # --------------------------------------------------------

    if not PAYER_MNEMONIC:
        raise SystemExit(
            "ERROR: PAYER_MNEMONIC was not found.\n\n"
            "Make sure your .env contains:\n\n"
            'PAYER_MNEMONIC="your 25 words"\n'
        )

    # --------------------------------------------------------
    # Convert mnemonic to private key
    # --------------------------------------------------------

    try:
        payer_key = mnemonic.to_private_key(
            PAYER_MNEMONIC
        )

        payer_addr = account.address_from_private_key(
            payer_key
        )

    except Exception as exc:
        raise SystemExit(
            f"ERROR: Invalid PAYER_MNEMONIC: {exc}"
        )

    print(f"Payer address:")
    print(payer_addr)
    print()

    # --------------------------------------------------------
    # Connect to Algorand TestNet
    # --------------------------------------------------------

    algod_client = algod.AlgodClient(
        ALGOD_TOKEN,
        ALGOD_ADDRESS,
    )

    # --------------------------------------------------------
    # Check payer balance
    # --------------------------------------------------------

    try:
        account_info = algod_client.account_info(
            payer_addr
        )

        balance = account_info.get(
            "amount",
            0,
        )

        print(
            f"Payer balance: "
            f"{balance / 1_000_000:.6f} ALGO"
        )
        print()

        if balance <= 0:
            raise SystemExit(
                "ERROR: Payer account has no TestNet ALGO.\n"
                "Fund the payer address using the Algorand "
                "TestNet dispenser."
            )

    except Exception as exc:

        raise SystemExit(
            f"ERROR: Could not read payer account: {exc}"
        )

    # ========================================================
    # STEP 1
    # Request resource without payment
    # ========================================================

    print("-" * 70)
    print("STEP 1: Requesting protected resource")
    print("-" * 70)

    resource_url = (
        f"{API_BASE}/resource/{RESOURCE_ID}"
    )

    try:

        response = requests.get(
            resource_url,
            timeout=30,
        )

    except requests.RequestException as exc:

        raise SystemExit(
            f"ERROR: Could not connect to API:\n{exc}\n\n"
            "Make sure the FastAPI server is running:\n"
            "uvicorn app.main:app --reload"
        )

    print(
        f"HTTP status: {response.status_code}"
    )

    if response.status_code != 402:

        print("Unexpected response:")
        print(response.text)

        raise SystemExit(
            "ERROR: Expected HTTP 402 Payment Required."
        )

    challenge = response.json()

    print()
    print("402 Payment Required")
    print()
    print("Payment instructions:")
    print(
        f"  Pay to: "
        f"{challenge.get('pay_to')}"
    )
    print(
        f"  Amount: "
        f"{challenge.get('amount_microalgos')} microALGO"
    )
    print(
        f"  Amount: "
        f"{challenge.get('amount_microalgos', 0) / 1_000_000} ALGO"
    )
    print(
        f"  Nonce: "
        f"{challenge.get('nonce')}"
    )
    print()

    # --------------------------------------------------------
    # Validate challenge
    # --------------------------------------------------------

    pay_to = challenge.get(
        "pay_to"
    )

    amount = challenge.get(
        "amount_microalgos"
    )

    nonce = challenge.get(
        "nonce"
    )

    if not pay_to:
        raise SystemExit(
            "ERROR: API did not provide pay_to."
        )

    if not amount:
        raise SystemExit(
            "ERROR: API did not provide amount_microalgos."
        )

    if not nonce:
        raise SystemExit(
            "ERROR: API did not provide nonce."
        )

    # ========================================================
    # STEP 2
    # Create Algorand payment
    # ========================================================

    print("-" * 70)
    print("STEP 2: Paying on Algorand TestNet")
    print("-" * 70)

    print(
        f"Sending {amount / 1_000_000} ALGO"
    )

    print(
        f"From: {payer_addr}"
    )

    print(
        f"To:   {pay_to}"
    )

    print()

    try:

        params = algod_client.suggested_params()

        txn = transaction.PaymentTxn(
            sender=payer_addr,
            sp=params,
            receiver=pay_to,
            amt=amount,
            note=nonce.encode("utf-8"),
        )

        signed_txn = txn.sign(
            payer_key
        )

        txid = algod_client.send_transaction(
            signed_txn
        )

    except Exception as exc:

        raise SystemExit(
            f"ERROR: Failed to send payment:\n{exc}"
        )

    print(
        f"Payment transaction ID:\n{txid}"
    )

    print()
    print(
        "Waiting for Algorand confirmation..."
    )

    try:

        confirmation = transaction.wait_for_confirmation(
            algod_client,
            txid,
            10,
        )

    except Exception as exc:

        raise SystemExit(
            f"ERROR: Payment confirmation failed:\n{exc}"
        )

    confirmed_round = confirmation.get(
        "confirmed-round"
    )

    print(
        f"Payment confirmed in round: "
        f"{confirmed_round}"
    )

    print()

    # ========================================================
    # STEP 3
    # Redeem payment with X-PAYMENT
    # ========================================================

    print("-" * 70)
    print("STEP 3: Redeeming payment")
    print("-" * 70)

    print(
        "Sending X-PAYMENT header..."
    )

    try:

        response = requests.get(
            resource_url,
            headers={
                "X-PAYMENT": txid
            },
            timeout=60,
        )

    except requests.RequestException as exc:

        raise SystemExit(
            f"ERROR: Could not contact API:\n{exc}"
        )

    print(
        f"HTTP status: {response.status_code}"
    )

    if response.status_code != 200:

        print()
        print("API response:")
        print(response.text)

        raise SystemExit(
            "ERROR: Payment was not successfully redeemed."
        )

    result = response.json()

    print()
    print("Payment successfully redeemed!")
    print()

    print("Resource response:")
    print(result)

    print()

    # --------------------------------------------------------
    # Extract audit information
    # --------------------------------------------------------

    payload_hash = result.get(
        "payload_hash"
    )

    payment_txn_id = result.get(
        "payment_txn_id"
    )

    audit_txn_id = result.get(
        "audit_txn_id"
    )

    audit_explorer_url = result.get(
        "audit_explorer_url"
    )

    print(
        f"Payment transaction ID:"
    )
    print(
        payment_txn_id
    )

    print()

    print(
        f"Payload SHA-256:"
    )
    print(
        payload_hash
    )

    print()

    print(
        f"Audit transaction ID:"
    )
    print(
        audit_txn_id
    )

    print()

    if audit_explorer_url:

        print(
            "Audit transaction explorer:"
        )

        print(
            audit_explorer_url
        )

        print()

    # ========================================================
    # STEP 4
    # Independently verify audit
    # ========================================================

    print("-" * 70)
    print("STEP 4: Independent on-chain verification")
    print("-" * 70)

    verify_url = (
        f"{API_BASE}/verify/{txid}"
    )

    try:

        response = requests.get(
            verify_url,
            timeout=60,
        )

    except requests.RequestException as exc:

        raise SystemExit(
            f"ERROR: Verification request failed:\n{exc}"
        )

    print(
        f"HTTP status: {response.status_code}"
    )

    if response.status_code != 200:

        print(
            response.text
        )

        raise SystemExit(
            "ERROR: Verification endpoint failed."
        )

    verification = response.json()

    print()
    print("Verification result:")
    print(verification)

    print()

    # ========================================================
    # Final result
    # ========================================================

    print("=" * 70)
    print("FINAL RESULT")
    print("=" * 70)

    found = verification.get(
        "found"
    )

    verified = verification.get(
        "note_verified_on_chain"
    )

    print(
        f"402 challenge:       PASS"
    )

    print(
        f"Algorand payment:    PASS"
    )

    print(
        f"Payment redemption:  PASS"
    )

    print(
        f"Audit transaction:   "
        f"{'PASS' if audit_txn_id else 'FAIL'}"
    )

    print(
        f"On-chain verification: "
        f"{'PASS' if verified else 'FAIL'}"
    )

    print()

    if found and verified:

        print(
            "SUCCESS!"
        )

        print(
            "The complete x402 payment + "
            "on-chain audit flow worked."
        )

    else:

        print(
            "WARNING: The payment worked, "
            "but on-chain verification did not."
        )

    print("=" * 70)


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()