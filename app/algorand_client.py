"""
Thin wrapper around py-algorand-sdk for two jobs:

1. verify_payment():
   Confirm that a client-supplied transaction ID is a confirmed
   payment of the required amount to our service address.

2. write_audit_note():
   Send a minimal-fee, zero-ALGO self-payment transaction whose
   note field contains the audit linkage record.

The on-chain note contains:

{
    "payload_hash": "...",
    "payment_txn_id": "...",
    "payer": "...",
    "amount_microalgos": 100000,
    "resource": "..."
}
"""

import base64
import json
import time
from typing import Optional

from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod, indexer

from .config import settings


NOTE_PREFIX = b"x402-audit/v1:"


class PaymentVerificationError(Exception):
    """Raised when an Algorand payment cannot be verified."""

    pass


class AlgorandAuditClient:
    def __init__(self):
        # -----------------------------------------------------------
        # Algod client
        # -----------------------------------------------------------
        headers = (
            {"X-API-Key": settings.algod_token}
            if settings.algod_token
            else None
        )

        self.algod_client = algod.AlgodClient(
            settings.algod_token,
            settings.algod_address,
            headers=headers,
        )

        # -----------------------------------------------------------
        # Indexer client
        # -----------------------------------------------------------
        self.indexer_client = indexer.IndexerClient(
            settings.indexer_token,
            settings.indexer_address,
        )

        # -----------------------------------------------------------
        # Service account
        # -----------------------------------------------------------
        self.service_private_key = None
        self.service_address = None

        if settings.service_mnemonic:
            try:
                self.service_private_key = mnemonic.to_private_key(
                    settings.service_mnemonic
                )

                self.service_address = (
                    account.address_from_private_key(
                        self.service_private_key
                    )
                )

            except Exception as exc:
                raise RuntimeError(
                    "SERVICE_MNEMONIC is present but is not a valid "
                    "Algorand mnemonic."
                ) from exc

    # ===============================================================
    # Payment verification
    # ===============================================================

    def verify_payment(
        self,
        payment_txn_id: str,
        expected_amount: int,
    ) -> dict:
        """
        Look up a payment transaction through the Algorand indexer.

        Checks:

        - transaction exists
        - transaction is a payment transaction
        - receiver is our service account
        - amount is sufficient
        - transaction is recent enough

        Returns:

        {
            "payer_address": "...",
            "amount": 100000,
            "confirmed_round": 123456,
            "timestamp": 1234567890
        }
        """

        if not self.service_address:
            raise PaymentVerificationError(
                "Service account is not configured. "
                "Check SERVICE_MNEMONIC in .env."
            )

        try:
            info = self.indexer_client.search_transactions(
                txid=payment_txn_id
            )

        except Exception as exc:
            raise PaymentVerificationError(
                f"Could not query Algorand indexer for "
                f"{payment_txn_id}: {exc}"
            )

        transactions = info.get("transactions", [])

        if not transactions:
            raise PaymentVerificationError(
                f"Transaction {payment_txn_id} was not found "
                "or has not been confirmed by the indexer yet."
            )

        txn = transactions[0]

        # -----------------------------------------------------------
        # Make sure it is a payment transaction
        # -----------------------------------------------------------
        if txn.get("tx-type") != "pay":
            raise PaymentVerificationError(
                "Referenced transaction is not a payment transaction."
            )

        payment = txn.get("payment-transaction", {})

        receiver = payment.get("receiver")
        amount = payment.get("amount", 0)
        sender = txn.get("sender")
        round_time = txn.get("round-time")

        # -----------------------------------------------------------
        # Receiver check
        # -----------------------------------------------------------
        if receiver != self.service_address:
            raise PaymentVerificationError(
                f"Payment receiver {receiver} does not match "
                f"service address {self.service_address}."
            )

        # -----------------------------------------------------------
        # Amount check
        # -----------------------------------------------------------
        if amount < expected_amount:
            raise PaymentVerificationError(
                f"Payment amount {amount} microAlgos is less than "
                f"required {expected_amount} microAlgos."
            )

        # -----------------------------------------------------------
        # Age check
        # -----------------------------------------------------------
        if round_time:
            age = time.time() - round_time

            if age > settings.payment_txn_max_age_seconds:
                raise PaymentVerificationError(
                    "Payment transaction is too old to redeem."
                )

        return {
            "payer_address": sender,
            "amount": amount,
            "confirmed_round": txn.get("confirmed-round"),
            "timestamp": round_time,
        }

    # ===============================================================
    # Replay protection placeholder
    # ===============================================================

    def is_txn_already_used(
        self,
        payment_txn_id: str,
    ) -> bool:
        """
        Replay protection is handled by audit_store.py.

        This method is kept for future on-chain replay protection.
        """

        raise NotImplementedError(
            "Use audit_store.AuditStore.get_by_payment_txn() "
            "for local replay protection."
        )

    # ===============================================================
    # Write audit note
    # ===============================================================

    def write_audit_note(
        self,
        payload_hash: str,
        payment_txn_id: str,
        payer_address: str,
        amount: int,
        resource: str,
    ) -> str:
        """
        Submit a zero-ALGO self-payment.

        Service account:
            sender = service address
            receiver = service address
            amount = 0

        The note contains the audit linkage.
        """

        if not self.service_private_key:
            raise PaymentVerificationError(
                "Service account is not configured. "
                "Check SERVICE_MNEMONIC in .env."
            )

        # -----------------------------------------------------------
        # Create audit record
        # -----------------------------------------------------------
        record = {
            "payload_hash": payload_hash,
            "payment_txn_id": payment_txn_id,
            "payer": payer_address,
            "amount_microalgos": amount,
            "resource": resource,
        }

        # Compact JSON to minimize note size
        note_json = json.dumps(
            record,
            separators=(",", ":"),
        )

        note_bytes = NOTE_PREFIX + note_json.encode("utf-8")

        # Algorand note field maximum
        if len(note_bytes) > 1024:
            raise ValueError(
                "Audit note exceeds Algorand's 1024-byte note limit."
            )

        # -----------------------------------------------------------
        # Suggested transaction parameters
        # -----------------------------------------------------------
        params = self.algod_client.suggested_params()

        # -----------------------------------------------------------
        # Create self-payment
        # -----------------------------------------------------------
        txn = transaction.PaymentTxn(
            sender=self.service_address,
            sp=params,
            receiver=self.service_address,
            amt=0,
            note=note_bytes,
        )

        # -----------------------------------------------------------
        # Sign transaction
        # -----------------------------------------------------------
        signed_txn = txn.sign(
            self.service_private_key
        )

        # -----------------------------------------------------------
        # Submit transaction
        # -----------------------------------------------------------
        txid = self.algod_client.send_transaction(
            signed_txn
        )

        # -----------------------------------------------------------
        # Wait for confirmation
        # -----------------------------------------------------------
        transaction.wait_for_confirmation(
            self.algod_client,
            txid,
            4,
        )

        return txid

    # ===============================================================
    # Read audit note
    # ===============================================================

    def read_audit_note(
        self,
        audit_txn_id: str,
    ) -> Optional[dict]:
        """
        Fetch a confirmed audit transaction from the indexer
        and decode its note field.
        """

        try:
            info = self.indexer_client.search_transactions(
                txid=audit_txn_id
            )

        except Exception:
            return None

        transactions = info.get(
            "transactions",
            [],
        )

        if not transactions:
            return None

        txn = transactions[0]

        # -----------------------------------------------------------
        # Read Base64 note
        # -----------------------------------------------------------
        note_b64 = txn.get("note")

        if not note_b64:
            return None

        try:
            raw_note = base64.b64decode(
                note_b64
            )

        except Exception:
            return None

        # -----------------------------------------------------------
        # Check our prefix
        # -----------------------------------------------------------
        if not raw_note.startswith(
            NOTE_PREFIX
        ):
            return None

        # -----------------------------------------------------------
        # Decode JSON
        # -----------------------------------------------------------
        try:
            json_data = raw_note[
                len(NOTE_PREFIX):
            ].decode("utf-8")

            return json.loads(
                json_data
            )

        except Exception:
            return None


# ===============================================================
# Global client
# ===============================================================

client = AlgorandAuditClient()