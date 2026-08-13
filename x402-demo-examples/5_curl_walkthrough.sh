#!/usr/bin/env bash
#
# Demo 5 -- Pure curl walkthrough.
#
# Shows the HTTP surface of the API with nothing but curl + jq, for
# audiences who want to see the raw request/response shapes without
# any Python or Algorand SDK in the way. Paying on-chain still
# requires the Algorand SDK (or a wallet), so this script stops
# right before the payment step and tells you what to send.
#
# Usage:
#   ./5_curl_walkthrough.sh [API_BASE] [RESOURCE_ID]
#
# Requires: curl, jq

set -euo pipefail

API_BASE="${1:-http://127.0.0.1:8000}"
RESOURCE_ID="${2:-curl-demo-resource}"

hr() { printf -- '-%.0s' {1..70}; echo; }

echo "=================================================================="
echo "PS0405 x402 API -- curl walkthrough"
echo "=================================================================="
echo

hr; echo "GET /health"; hr
curl -sS "${API_BASE}/health" | jq .
echo

hr; echo "GET /resource/${RESOURCE_ID}  (no payment yet -> expect 402)"; hr
CHALLENGE=$(curl -sS -w '\n%{http_code}' "${API_BASE}/resource/${RESOURCE_ID}")
STATUS=$(echo "${CHALLENGE}" | tail -n1)
BODY=$(echo "${CHALLENGE}" | sed '$d')

echo "HTTP status: ${STATUS}"
echo "${BODY}" | jq .

if [ "${STATUS}" != "402" ]; then
  echo "Unexpected status; is the server already tracking a payment for this resource_id?"
  exit 1
fi

PAY_TO=$(echo "${BODY}" | jq -r '.pay_to')
AMOUNT=$(echo "${BODY}" | jq -r '.amount_microalgos')
NONCE=$(echo "${BODY}" | jq -r '.nonce')

echo
echo "To continue by hand:"
echo "  1. Send exactly ${AMOUNT} microALGO to ${PAY_TO} on Algorand TestNet,"
echo "     with the transaction note set to: ${NONCE}"
echo "  2. Wait for confirmation, then note the resulting txn id (TXID)."
echo "  3. Redeem it:"
echo
echo "     curl -sS \"${API_BASE}/resource/${RESOURCE_ID}\" -H \"X-PAYMENT: TXID\" | jq ."
echo
echo "  4. Independently verify the audit note on-chain:"
echo
echo "     curl -sS \"${API_BASE}/verify/TXID\" | jq ."
echo
echo "(Use 2_multiple_resources_demo.py or demo_client.py to do steps 1-4"
echo " automatically with a funded TestNet payer account.)"
