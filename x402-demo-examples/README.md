# PS0405 demo scripts

Extra example scripts for demoing the x402 Payment Logging & Audit API
beyond the original `demo_client.py` happy-path walkthrough.

All Python scripts share `_demo_helpers.py` and read the same `.env` as the
main project (`API_BASE`, `ALGOD_ADDRESS`, `ALGOD_TOKEN`, `PAYER_MNEMONIC`).
Start the API first: `uvicorn app.main:app --reload`.

| Script | What it shows | Spends TestNet ALGO? |
|---|---|---|
| `demo_client.py` *(original)* | Full happy path: 402 → pay → redeem → verify | Yes |
| `2_multiple_resources_demo.py` | Three different `resource_id`s bought in one run, each independently metered and audited | Yes |
| `3_verify_only_demo.py` | `/verify/{txn_id}` in isolation — pass an existing payment txn id as an argument, or let it mint a fresh one | Yes (only if no argument given) |
| `4_replay_protection_demo.py` | Redeems a payment once, then replays the same `X-PAYMENT` header to show the 409 rejection | Yes |
| `5_curl_walkthrough.sh` | Raw HTTP shapes via `curl` + `jq`, no SDK — stops before the on-chain payment step and prints exactly what to send | No |
| `6_error_scenarios_demo.py` | Negative paths only: missing payment, garbage txn id, verifying an unknown txn | No |

Run any Python script with:

```bash
python 2_multiple_resources_demo.py
```

Run the curl walkthrough with:

```bash
./5_curl_walkthrough.sh
```
