#!/usr/bin/env bash
set -euo pipefail
: "${API_302API_KEY:?Set API_302API_KEY first}"
api_base="${API_302API_BASE_URL:-https://api.302api.com/v1}"
curl --fail-with-body --silent --show-error --max-time 30 \
  "${api_base%/}/models" \
  --header "Authorization: Bearer ${API_302API_KEY}"
