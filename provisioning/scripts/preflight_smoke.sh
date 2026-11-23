#!/usr/bin/env bash
# Live-test day preflight: health → auth → broker profile → queue depth → upload → ingest complete
# Usage:
#   ./provisioning/scripts/preflight_smoke.sh
#   ./provisioning/scripts/preflight_smoke.sh http://localhost:8000 admin@example.com adminpassword
set -euo pipefail

API_URL="${1:-http://localhost:8000}"
ADMIN_EMAIL="${2:-admin@example.com}"
ADMIN_PASSWORD="${3:-adminpassword}"
REDIS_CONTAINER="${REDIS_CONTAINER:-docingestion_redis}"
TIMEOUT_SEC="${PREFLIGHT_INGEST_TIMEOUT:-180}"

RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; RST=$'\033[0m'
pass() { echo "${GRN}PASS${RST} $*"; }
fail() { echo "${RED}FAIL${RST} $*"; exit 1; }
warn() { echo "${YLW}WARN${RST} $*"; }

echo "=== GATE preflight smoke @ ${API_URL} ==="

# 0) Redis ingest/celery depth (best-effort; docker optional)
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx "${REDIS_CONTAINER}"; then
  CELERY_LEN="$(docker exec "${REDIS_CONTAINER}" redis-cli llen celery 2>/dev/null || echo "?")"
  INGEST_LEN="$(docker exec "${REDIS_CONTAINER}" redis-cli llen ingest 2>/dev/null || echo "?")"
  echo "[0] Queue depth: celery=${CELERY_LEN} ingest=${INGEST_LEN}"
  if [[ "${CELERY_LEN}" =~ ^[0-9]+$ ]] && (( CELERY_LEN > 200 )); then
    warn "celery queue is deep (${CELERY_LEN}). Ingest should still proceed on 'ingest' queue; consider purge if stuck."
  fi
else
  warn "Redis container ${REDIS_CONTAINER} not reachable; skipping queue depth check"
fi

# 1) Health
HEALTH="$(curl -sf "${API_URL}/health")" || fail "API health unreachable"
echo "${HEALTH}" | grep -q '"status":"ok"\|"status": "ok"' || fail "health not ok: ${HEALTH}"
pass "[1] API health"

# 2) Login
LOGIN="$(curl -sf -X POST "${API_URL}/api/portal/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\"}")" \
  || fail "portal login failed"
TOKEN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["session_token"])' <<<"${LOGIN}")"
[[ -n "${TOKEN}" ]] || fail "no session_token"
pass "[2] Portal login (${ADMIN_EMAIL})"

AUTH=( -H "Authorization: Bearer ${TOKEN}" )

# 3) Broker profile
PROFILE="$(curl -sf "${API_URL}/api/reference-data/broker-profile" "${AUTH[@]}")" \
  || fail "broker-profile failed"
python3 - "${PROFILE}" <<'PY' || exit 1
import json, sys
p = json.loads(sys.argv[1])
filer = (p.get("broker_filer_code") or "").strip()
name = p.get("broker_name")
ace = p.get("ace_mode")
print(f"     broker={name!r} filer={filer!r} ace_mode={ace!r} hts={p.get('hts_code_count')}")
if not filer or len(filer) != 3:
    print("FAIL: BROKER_FILER_CODE missing or not 3 chars — set it in .env before live testing")
    sys.exit(1)
if int(p.get("hts_code_count") or 0) < 50:
    print("FAIL: HTS seed too small")
    sys.exit(1)
PY
pass "[3] Broker filer + HTS seed"

# 4) Workbench / queue status
WB_FILE="$(mktemp)"
QS_FILE="$(mktemp)"
curl -sf "${API_URL}/api/workbench/summary" "${AUTH[@]}" -o "${WB_FILE}" || fail "workbench summary failed"
if ! curl -sf "${API_URL}/api/queue/status" "${AUTH[@]}" -o "${QS_FILE}"; then
  echo '{}' > "${QS_FILE}"
  warn "queue status unavailable"
fi
python3 - "${WB_FILE}" "${QS_FILE}" <<'PY'
import json, sys
wb = json.load(open(sys.argv[1]))
qs = json.load(open(sys.argv[2]))
att = wb.get("attention") or {}
print(f"     attention={att}")
print(f"     queue_status={qs}")
ingest_failed = int(att.get("ingest_failed") or 0)
if ingest_failed > 0:
    print(f"WARN: ingest_failed={ingest_failed} — check DLQ before live demo")
PY
rm -f "${WB_FILE}" "${QS_FILE}"
pass "[4] Workbench reachable"

# 5) Tiny upload + wait for ingest complete
TMP="$(mktemp /tmp/gate-preflight.XXXXXX.txt)"
echo "GATE preflight smoke $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${TMP}"
UP="$(curl -sf -X POST "${API_URL}/api/upload" \
  "${AUTH[@]}" \
  -F "file=@${TMP};type=text/plain" \
  -F "source=preflight_smoke")" || fail "upload failed"
rm -f "${TMP}"
JOB_ID="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])' <<<"${UP}")"
pass "[5] Upload accepted job_id=${JOB_ID}"

# 6) Poll ingest
DEADLINE=$((SECONDS + TIMEOUT_SEC))
STATUS="unknown"
while (( SECONDS < DEADLINE )); do
  JOB="$(curl -sf "${API_URL}/api/ingest/jobs/${JOB_ID}" "${AUTH[@]}")" || true
  STATUS="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))' <<<"${JOB}" 2>/dev/null || echo "")"
  if [[ "${STATUS}" == "completed" ]]; then
    pass "[6] Ingest completed (${STATUS})"
    break
  fi
  if [[ "${STATUS}" == "failed" || "${STATUS}" == "dead_letter" || "${STATUS}" == "error" ]]; then
    fail "[6] Ingest ended as ${STATUS}: ${JOB}"
  fi
  sleep 3
done
[[ "${STATUS}" == "completed" ]] || fail "[6] Ingest timed out after ${TIMEOUT_SEC}s (last=${STATUS})"

echo "=== Preflight OK — safe to start live testing ==="
