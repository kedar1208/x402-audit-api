from typing import Optional
from pydantic import BaseModel, Field


class PaymentRequired(BaseModel):
    """Body returned with HTTP 402, describing how to pay on Algorand TestNet."""
    x402_version: int = 1
    network: str = "algorand-testnet"
    pay_to: str
    amount_microalgos: int
    asset: str = "ALGO"
    nonce: str
    memo_hint: str = (
        "Send exactly amount_microalgos to pay_to. Include 'nonce' in the "
        "transaction note field. Then retry the request with header "
        "'X-PAYMENT: <payment_txn_id>'."
    )
    expires_in_seconds: int = 3600


class AuditRecord(BaseModel):
    """What gets hashed/stored to link a response payload to its payment."""
    payload_hash: str
    payment_txn_id: str
    payer_address: str
    amount_microalgos: int
    resource: str
    timestamp: str
    audit_txn_id: Optional[str] = None


class ResourceResponse(BaseModel):
    """Successful (post-payment) API response envelope."""
    data: dict
    payload_hash: str = Field(..., description="SHA-256 hash of `data`, canonicalized")
    payment_txn_id: str
    audit_txn_id: str = Field(..., description="Algorand txn ID carrying the audit note")
    audit_explorer_url: str


class VerifyResponse(BaseModel):
    found: bool
    record: Optional[AuditRecord] = None
    payment_explorer_url: Optional[str] = None
    audit_explorer_url: Optional[str] = None
    note_verified_on_chain: Optional[bool] = None
