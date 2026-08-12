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

## Setup

```bash
cd x402-audit-api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

1. Create a TestNet service account (with AlgoKit: `algokit generate account`,
   or `goal account new` / any algosdk snippet using `account.generate_account()`).
2. Fund it at the TestNet dispenser: https://bank.testnet.algorand.network/
3. Put its 25-word mnemonic into `.env` as `SERVICE_MNEMONIC`.

Run the API:

```bash
uvicorn app.main:app --reload
```

Check it's alive and see the service's receiving address:

```bash
curl http://127.0.0.1:8000/health
```

## Try the full flow

**Option A — automated demo script.** Fund a *second* TestNet account to act
as the payer, then:

```bash
export PAYER_MNEMONIC="word1 word2 ... word25"
python demo_client.py
```

This requests the resource, gets 402'd, pays on TestNet, retries, and prints
the verification result.

**Option B — manual curl walkthrough:**

```bash
# 1. Get the payment challenge
curl http://127.0.0.1:8000/resource/agent-task-42
# -> 402 { "pay_to": "...", "amount_microalgos": 100000, "nonce": "..." }

# 2. Pay that address that amount on TestNet (via any wallet, or
#    algosdk/AlgoKit script), note the resulting txn ID.

# 3. Redeem it
curl -H "X-PAYMENT: <payment_txn_id>" http://127.0.0.1:8000/resource/agent-task-42
# -> 200 { "data": {...}, "payload_hash": "...", "audit_txn_id": "...", ... }

# 4. Verify independently, any time later
curl http://127.0.0.1:8000/verify/<payment_txn_id>
```

Open `audit_explorer_url` from either response in a browser (AlgoKit Lora
TestNet explorer) to see the note field on-chain yourself.

## Files

```
app/
  config.py          settings from environment (.env)
  models.py           Pydantic request/response schemas
  hashing.py          canonical JSON -> sha256 (tamper-evidence primitive)
  algorand_client.py  payment verification + audit note writer/reader (algosdk)
  audit_store.py      local SQLite cache/index (NOT the source of truth)
  main.py             FastAPI routes: /resource, /verify, /health
demo_client.py         scripted end-to-end demo (pay -> redeem -> verify)
requirements.txt
.env.example
```

## Design notes / known simplifications (flagged for judges)

- **Nonce is informational, not cryptographically bound.** The 402 challenge
  includes a `nonce`, but verification currently checks receiver + amount +
  recency, not that the nonce appears in the payer's note. For production,
  require the payer to echo the nonce in their payment's note field and
  check it, closing a race where two concurrent requests could both try to
  redeem against payments meant for different challenges.
- **Replay protection** is enforced by the local SQLite index (a payment txn
  ID can only be redeemed once). The chain itself doesn't prevent someone
  from *trying* to reuse a txn ID against the API — our app layer does.
- **Single service key** signs both received payments and audit notes. In
  production, separate a receiving address (can be a multisig / cold-ish
  wallet) from a hot key that only signs low-value note transactions.
- No network access was available in the environment used to write this
  code, so it's syntax-checked and logic-tested locally (see the
  deterministic-hash check) but not run live against TestNet — run
  `demo_client.py` in your own environment to see it end-to-end.
