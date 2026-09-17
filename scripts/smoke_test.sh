#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
WEB_URL="${WEB_URL:-http://127.0.0.1:5500}"

check_status() {
  local url="$1"
  local expected="$2"
  local actual
  actual="$(curl -sS -o /dev/null -w '%{http_code}' "$url")"
  [[ "$actual" == "$expected" ]] || { echo "FAIL $url: expected $expected, got $actual" >&2; exit 1; }
  echo "OK $url ($actual)"
}

check_status "$API_URL/" 200
check_status "$API_URL/ai/health" 200
check_status "$API_URL/ai/requests?limit=1" 200
check_status "$API_URL/docs" 200
check_status "$WEB_URL/index.html" 200
check_status "$WEB_URL/formula-test.html" 200

stream="$(curl -sS -X POST "$API_URL/ai/ask-stream" -H 'Content-Type: application/json' -d '{"question":""}')"
grep -q '"error_code": "http_error"' <<<"$stream" || { echo 'FAIL stream error contract' >&2; exit 1; }
echo 'OK stream error contract'
echo 'Smoke test passed.'
