"""
PS0405 -- Payment Logging & Audit Infrastructure

An x402-style API:
- returns HTTP 402 until payment is made
- verifies Algorand TestNet payment
- hashes the response
- writes the audit linkage into an Algorand transaction note
- allows independent verification
"""

import time
import uuid
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Path
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .algorand_client import (
    client,
    PaymentVerificationError,
)
from .audit_store import store
from .config import settings
from .hashing import sha256_hex
from .models import (
    AuditRecord,
    PaymentRequired,
    ResourceResponse,
    VerifyResponse,
)


app = FastAPI(
    title="x402 Payment Logging & Audit Infrastructure (PS0405)",
    description=(
        "Hashes API response payloads, pairs each hash with its "
        "Algorand payment receipt, and permanently records the "
        "linkage on-chain via a transaction note field."
    ),
    version="1.0.0",
)

# Local console (static/index.html) runs in a browser and calls this API
# directly over fetch, so it needs CORS enabled. Tighten allow_origins
# before deploying anywhere public.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves the ledger console at /console (index.html + assets), without
# shadowing the API routes mounted at "/".
app.mount(
    "/console",
    StaticFiles(directory="static", html=True),
    name="console",
)


TESTNET_EXPLORER = (
    "https://lora.algokit.io/testnet/transaction"
)


def _explorer_url(txn_id: str) -> str:
    return f"{TESTNET_EXPLORER}/{txn_id}"


# ===============================================================
# Health
# ===============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "network": "algorand-testnet",
        "service_address": client.service_address,
    }


# ===============================================================
# Protected resource
# ===============================================================

def _build_agent_action_payload(
    resource_id: str,
) -> dict:
    return {
        "resource_id": resource_id,
        "action": "ai-agent.completed-task",
        "result": (
            f"Processed request for resource "
            f"'{resource_id}' successfully."
        ),
        "generated_at": time.time(),
    }


@app.get(
    "/resource/{resource_id}",
    response_model=None,
)
def get_resource(
    resource_id: str = Path(
        ...,
        description="Identifier of the protected resource/action",
    ),
    x_payment: Optional[str] = Header(
        None,
        alias="X-PAYMENT",
    ),
):
    """
    x402 flow:

    1. No X-PAYMENT -> 402.
    2. X-PAYMENT -> verify payment.
    3. Build response.
    4. Hash response.
    5. Write audit note on Algorand.
    6. Return resource + audit information.
    """

    # -----------------------------------------------------------
    # Step 1: Payment challenge
    # -----------------------------------------------------------

    if not x_payment:
        challenge = PaymentRequired(
            pay_to=(
                client.service_address
                or "SERVICE_ADDRESS_NOT_CONFIGURED"
            ),
            amount_microalgos=settings.price_microalgos,
            nonce=uuid.uuid4().hex,
        )

        return JSONResponse(
            status_code=402,
            content=challenge.model_dump(),
        )

    # -----------------------------------------------------------
    # Step 2: Replay protection
    # -----------------------------------------------------------

    existing = store.get_by_payment_txn(
        x_payment
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Payment {x_payment} was already redeemed "
                f"at {existing.timestamp} "
                f"(audit txn {existing.audit_txn_id})."
            ),
        )

    # -----------------------------------------------------------
    # Step 3: Verify Algorand payment
    # -----------------------------------------------------------

    try:
        payment_info = client.verify_payment(
            x_payment,
            settings.price_microalgos,
        )

    except PaymentVerificationError as exc:
        raise HTTPException(
            status_code=402,
            detail=str(exc),
        )

    # -----------------------------------------------------------
    # Step 4: Build response payload
    # -----------------------------------------------------------

    payload = _build_agent_action_payload(
        resource_id
    )

    # -----------------------------------------------------------
    # Step 5: Hash response
    # -----------------------------------------------------------

    payload_hash = sha256_hex(
        payload
    )

    # -----------------------------------------------------------
    # Step 6: Write audit transaction
    # -----------------------------------------------------------

    try:
        audit_txn_id = client.write_audit_note(
            payload_hash=payload_hash,
            payment_txn_id=x_payment,
            payer_address=payment_info[
                "payer_address"
            ],
            amount=payment_info[
                "amount"
            ],
            resource=resource_id,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Failed to write audit note on-chain: "
                f"{exc}"
            ),
        )

    # -----------------------------------------------------------
    # Step 7: Save local cache
    # -----------------------------------------------------------

    record = AuditRecord(
        payload_hash=payload_hash,
        payment_txn_id=x_payment,
        payer_address=payment_info[
            "payer_address"
        ],
        amount_microalgos=payment_info[
            "amount"
        ],
        resource=resource_id,
        timestamp=store.now_iso(),
        audit_txn_id=audit_txn_id,
    )

    store.save(record)

    # -----------------------------------------------------------
    # Step 8: Return response
    # -----------------------------------------------------------

    return ResourceResponse(
        data=payload,
        payload_hash=payload_hash,
        payment_txn_id=x_payment,
        audit_txn_id=audit_txn_id,
        audit_explorer_url=_explorer_url(
            audit_txn_id
        ),
    )


# ===============================================================
# Verification endpoint
# ===============================================================

@app.get(
    "/verify/{payment_txn_id}",
    response_model=VerifyResponse,
)
def verify(
    payment_txn_id: str,
):
    """
    Independently verify an audit trail.

    The local SQLite database is only a cache.
    The Algorand transaction note is the source of truth.
    """

    record = store.get_by_payment_txn(
        payment_txn_id
    )

    if not record:
        return VerifyResponse(
            found=False
        )

    on_chain = (
        client.read_audit_note(
            record.audit_txn_id
        )
        if record.audit_txn_id
        else None
    )

    note_verified = bool(
        on_chain
        and on_chain.get(
            "payload_hash"
        ) == record.payload_hash
        and on_chain.get(
            "payment_txn_id"
        ) == record.payment_txn_id
    )

    return VerifyResponse(
        found=True,
        record=record,
        payment_explorer_url=_explorer_url(
            payment_txn_id
        ),
        audit_explorer_url=(
            _explorer_url(
                record.audit_txn_id
            )
            if record.audit_txn_id
            else None
        ),
        note_verified_on_chain=note_verified,
    )