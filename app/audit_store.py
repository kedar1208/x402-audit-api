"""
Lightweight local index over audit records.

IMPORTANT:
This SQLite table is only a convenience cache for fast lookups
and replay protection.

The Algorand transaction note is the source of truth for the
tamper-evident audit record.
"""

import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from .config import settings
from .models import AuditRecord


# Global lock protects SQLite operations
_lock = threading.Lock()


def _connect():
    """
    Create the SQLite connection.

    check_same_thread=False is required because FastAPI can execute
    synchronous endpoints in different worker threads.
    """

    conn = sqlite3.connect(
        settings.audit_db_path,
        check_same_thread=False,
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_records (
            payment_txn_id TEXT PRIMARY KEY,
            payload_hash TEXT NOT NULL,
            payer_address TEXT NOT NULL,
            amount_microalgos INTEGER NOT NULL,
            resource TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            audit_txn_id TEXT
        )
        """
    )

    conn.commit()

    return conn


class AuditStore:

    def __init__(self):
        self._conn = _connect()

    # ============================================================
    # Get audit record by payment transaction
    # ============================================================

    def get_by_payment_txn(
        self,
        payment_txn_id: str,
    ) -> Optional[AuditRecord]:

        with _lock:

            row = self._conn.execute(
                """
                SELECT
                    payload_hash,
                    payment_txn_id,
                    payer_address,
                    amount_microalgos,
                    resource,
                    timestamp,
                    audit_txn_id
                FROM audit_records
                WHERE payment_txn_id = ?
                LIMIT 1
                """,
                (payment_txn_id,),
            ).fetchone()

        if not row:
            return None

        return AuditRecord(
            payload_hash=row[0],
            payment_txn_id=row[1],
            payer_address=row[2],
            amount_microalgos=row[3],
            resource=row[4],
            timestamp=row[5],
            audit_txn_id=row[6],
        )

    # ============================================================
    # Save audit record
    # ============================================================

    def save(
        self,
        record: AuditRecord,
    ) -> None:

        with _lock:

            self._conn.execute(
                """
                INSERT OR REPLACE INTO audit_records (
                    payment_txn_id,
                    payload_hash,
                    payer_address,
                    amount_microalgos,
                    resource,
                    timestamp,
                    audit_txn_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.payment_txn_id,
                    record.payload_hash,
                    record.payer_address,
                    record.amount_microalgos,
                    record.resource,
                    record.timestamp,
                    record.audit_txn_id,
                ),
            )

            self._conn.commit()

    # ============================================================
    # Current UTC timestamp
    # ============================================================

    @staticmethod
    def now_iso() -> str:

        return datetime.now(
            timezone.utc
        ).isoformat()

    # ============================================================
    # Close database
    # ============================================================

    def close(self) -> None:

        with _lock:
            self._conn.close()


# ================================================================
# Global store
# ================================================================

store = AuditStore()