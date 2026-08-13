"""
Shared helpers for the PS0405 x402 demo scripts.

Every example script in this folder imports from here so the
Algorand plumbing (loading the payer key, sending a payment,
waiting for confirmation) is written once instead of copy-pasted
into every demo.
"""

import os
import sys

from dotenv import load_dotenv

from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod

load_dotenv()

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")
ALGOD_ADDRESS = os.getenv("ALGOD_ADDRESS", "https://testnet-api.algonode.cloud")
ALGOD_TOKEN = os.getenv("ALGOD_TOKEN", "")
PAYER_MNEMONIC = os.getenv("PAYER_MNEMONIC", "")


def get_algod_client() -> algod.AlgodClient:
    return algod.AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS)


def load_payer():
    """Return (payer_address, payer_private_key), or exit with a clear error."""
    if not PAYER_MNEMONIC:
        raise SystemExit(
            "ERROR: PAYER_MNEMONIC is not set.\n"
            'Add PAYER_MNEMONIC="your 25 words" to your .env file.'
        )
    try:
        payer_key = mnemonic.to_private_key(PAYER_MNEMONIC)
        payer_addr = account.address_from_private_key(payer_key)
    except Exception as exc:
        raise SystemExit(f"ERROR: Invalid PAYER_MNEMONIC: {exc}")
    return payer_addr, payer_key


def check_balance(algod_client, payer_addr) -> int:
    info = algod_client.account_info(payer_addr)
    balance = info.get("amount", 0)
    if balance <= 0:
        raise SystemExit(
            "ERROR: Payer account has no TestNet ALGO.\n"
            "Fund it at https://bank.testnet.algorand.network/"
        )
    return balance


def pay_challenge(algod_client, payer_addr, payer_key, pay_to: str, amount: int, nonce: str) -> str:
    """Send the Algorand payment described by a 402 challenge. Returns the confirmed txn id."""
    params = algod_client.suggested_params()
    txn = transaction.PaymentTxn(
        sender=payer_addr,
        sp=params,
        receiver=pay_to,
        amt=amount,
        note=nonce.encode("utf-8"),
    )
    signed_txn = txn.sign(payer_key)
    txid = algod_client.send_transaction(signed_txn)
    transaction.wait_for_confirmation(algod_client, txid, 10)
    return txid


def hr(title: str = "") -> None:
    print("-" * 70)
    if title:
        print(title)
        print("-" * 70)


def die(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)
