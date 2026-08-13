# PS0405 — x402 Payment Logging & Audit Infrastructure

Tamper-proof audit trails linking API responses to Algorand payment receipts.

An AI agent (or any client) calls a protected resource. It gets HTTP `402
Payment Required` with Algorand TestNet payment instructions. It pays, retries
with the payment's transaction ID, and receives the resource **plus** proof
that `sha256(response) <-> payment_txn_id` was permanently written into a new
Algorand transaction's note field — giving compliance teams a link they can
independently re-verify on-chain, forever.

## How it works

1. `GET /resource/{id}` with no `X-PAYMENT` header → **402** with `pay_to`,
   `amount_microalgos`, and a `nonce`.
2. Client pays that amount to `pay_to` on Algorand TestNet, gets a txn ID.
3. `GET /resource/{id}` again with header `X-PAYMENT: <txn_id>`. The server:
   - Verifies via the Algorand **indexer** that the txn is a confirmed
     payment, to the right address, for at least the right amount, recent
     enough, and not already redeemed (replay protection).
   - Builds the response payload and computes `sha256` over its canonical
     JSON encoding.
   - Sends a new, minimal-fee, 0-ALGO **self-payment transaction** whose
     **note field** contains `{payload_hash, payment_txn_id, payer, amount,
     resource}` — this is the permanent on-chain audit record.
   - Returns the payload along with `payment_txn_id` and `audit_txn_id`.
4. `GET /verify/{payment_txn_id}` re-fetches the audit txn from the indexer
   and re-derives the note contents independently, to prove the local cache
   hasn't drifted from the chain.

### Why the note field (vs. Box Storage)

Per your choice, this build uses the **transaction note field**: cheaper
(~0.001 ALGO/write, no MBR lockup), simpler to implement and verify (any
Algorand explorer or indexer call shows it), and sufficient for the audit
requirement since Algorand transactions are immutable once confirmed. The
tradeoff is a 1024-byte cap (we store hash + pointers, not full payloads) and
no smart-contract-enforced write rules (e.g. rejecting duplicate keys) — Box
Storage would add that if you need it later; `algorand_client.py` is
structured so swapping in a Box-based writer later is a contained change.

