#!/usr/bin/env bash
set -euo pipefail
: "${API_302API_KEY:?Set API_302API_KEY first}"
: "${MODEL_ID:?Set MODEL_ID to an enabled Chat Completions model}"
export MODEL_ID
api_base="${API_302API_BASE_URL:-https://api.302api.com/v1}"
python3 - <<'PY' | curl --fail-with-body --silent --show-error --max-time 120 \
  "${api_base%/}/chat/completions" \
  --header "Authorization: Bearer ${API_302API_KEY}" \
  --header 'Content-Type: application/json' --data-binary @-
import json, os
print(json.dumps({"model": os.environ["MODEL_ID"], "messages": [{"role": "user", "content": "请用一句话解释 API。"}]}, ensure_ascii=False))
PY
