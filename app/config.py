"""
Configuration for the x402 Payment Logging & Audit Infrastructure API (PS0405).

All values are loaded from environment variables.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env from the project root
load_dotenv()


@dataclass(frozen=True)
class Settings:
    # ---------------------------------------------------------------
    # Algorand TestNet
    # ---------------------------------------------------------------
    algod_address: str = os.getenv(
        "ALGOD_ADDRESS",
        "https://testnet-api.algonode.cloud",
    )

    algod_token: str = os.getenv(
        "ALGOD_TOKEN",
        "",
    )

    indexer_address: str = os.getenv(
        "INDEXER_ADDRESS",
        "https://testnet-idx.algonode.cloud",
    )

    indexer_token: str = os.getenv(
        "INDEXER_TOKEN",
        "",
    )

    # ---------------------------------------------------------------
    # Service account
    # ---------------------------------------------------------------
    # This account:
    # 1. Receives x402 payments
    # 2. Signs audit-note transactions
    #
    # NEVER expose this mnemonic publicly.
    # ---------------------------------------------------------------
    service_mnemonic: str = os.getenv(
        "SERVICE_MNEMONIC",
        "",
    )

    # ---------------------------------------------------------------
    # x402 pricing
    # ---------------------------------------------------------------
    # 100000 microAlgos = 0.1 ALGO
    # ---------------------------------------------------------------
    price_microalgos: int = int(
        os.getenv(
            "PRICE_MICROALGOS",
            "100000",
        )
    )

    # ---------------------------------------------------------------
    # Local audit database
    # ---------------------------------------------------------------
    audit_db_path: str = os.getenv(
        "AUDIT_DB_PATH",
        "audit.db",
    )

    # ---------------------------------------------------------------
    # Payment expiration
    # ---------------------------------------------------------------
    payment_txn_max_age_seconds: int = int(
        os.getenv(
            "PAYMENT_TXN_MAX_AGE_SECONDS",
            "3600",
        )
    )


settings = Settings()