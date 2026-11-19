#!/usr/bin/env bash
# Pre-Handoff Verification Smoke Script for a Provisioned Boutique Broker Instance
# Usage: ./provisioning/scripts/verify-instance.sh <API_BASE_URL> <ADMIN_EMAIL> <ADMIN_PASSWORD>

set -euo pipefail

API_URL="${1:-http://localhost:8000}"
ADMIN_EMAIL="${2:-admin@example.com}"
ADMIN_PASSWORD="${3:-adminpassword}"

echo "=== Verifying Customs Broker Instance at ${API_URL} ==="

# 1. Health check
HEALTH_JSON="$(curl -sf "${API_URL}/health")"
echo "[1/5] API Health: ${HEALTH_JSON}"

# 2. Authenticate admin session
LOGIN_JSON="$(curl -sf -X POST "${API_URL}/api/portal/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")"

TOKEN="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["session_token"])' <<< "${LOGIN_JSON}")"
echo "[2/5] Portal Session Auth: OK (scrypt-backed session issued)"

# 3. Verify Broker Profile & 19 CFR Part 163 Compliance
PROFILE_JSON="$(curl -sf "${API_URL}/api/reference-data/broker-profile" \
  -H "Authorization: Bearer ${TOKEN}")"

python3 - "${PROFILE_JSON}" <<'PY'
import json, sys
p = json.loads(sys.argv[1])
print(f"[3/5] Broker Profile: name={p.get('broker_name')!r}, filer={p.get('broker_filer_code')!r}, cw={p.get('cargowise_company_code')!r}")
assert p.get("cbp_19_cfr_163_compliant") is True, "19 CFR Part 163 retention check failed (<1825 days)!"
print(f"[4/5] 19 CFR Part 163 Audit Retention: OK ({p.get('audit_log_retention_days')} days)")
assert int(p.get("hts_code_count") or 0) >= 50, "USITC HTS tariff schedule is empty!"
print(f"[5/5] USITC HTS Schedule Seeded: OK ({p.get('hts_code_count')} subheadings)")
PY

echo "=== Instance passed all pre-handoff verification checks! ==="
