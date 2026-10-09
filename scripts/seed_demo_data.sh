#!/usr/bin/env bash
#
# GATES Platform — Demo Data Seeding Script
# ==========================================
# Seeds the platform with realistic customs brokerage test data for demos.
#
# Usage:
#   ./scripts/seed_demo_data.sh [--api-url URL] [--email EMAIL] [--password PASSWORD] [--scenario N]
#
# Options:
#   --api-url      API base URL (default: http://localhost:8000)
#   --email        Admin email (default: admin@gate.local)
#   --password     Admin password (default: GatesAdmin2024!)
#   --scenario     Upload only a specific scenario (1, 2, or 3). Default: all
#   --skip-upload  Skip document upload (only check status)
#   --wait         Wait for pipeline completion (default: true)
#   --timeout      Max seconds to wait for pipeline (default: 300)
#
# This script:
#   1. Authenticates with the API
#   2. Uploads all test documents from customs_test_documents/
#   3. Waits for the extraction pipeline to complete
#   4. Verifies extracted data against ground truth
#   5. Reports results
#

set -euo pipefail

# ──────────────────── Defaults ────────────────────
API_URL="${API_URL:-http://localhost:8000}"
ADMIN_EMAIL="admin@gate.local"
ADMIN_PASSWORD="GatesAdmin2024!"
SCENARIO="all"
SKIP_UPLOAD=false
WAIT_FOR_PIPELINE=true
TIMEOUT=300

# ──────────────────── Parse Args ────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-url)     API_URL="$2"; shift 2 ;;
        --email)       ADMIN_EMAIL="$2"; shift 2 ;;
        --password)    ADMIN_PASSWORD="$2"; shift 2 ;;
        --scenario)    SCENARIO="$2"; shift 2 ;;
        --skip-upload) SKIP_UPLOAD=true; shift ;;
        --no-wait)     WAIT_FOR_PIPELINE=false; shift ;;
        --timeout)     TIMEOUT="$2"; shift 2 ;;
        *)             echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ──────────────────── Colors ────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# ──────────────────── Helpers ────────────────────
info()    { echo -e "${BLUE}ℹ${NC}  $1"; }
success() { echo -e "${GREEN}✅${NC} $1"; }
warn()    { echo -e "${YELLOW}⚠️${NC}  $1"; }
error()   { echo -e "${RED}❌${NC} $1"; }
header()  { echo -e "\n${PURPLE}━━━ $1 ━━━${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCS_DIR="$PROJECT_DIR/customs_test_documents"

# ──────────────────── Step 1: Authenticate ────────────────────
header "Step 1: Authentication"
info "Logging in as $ADMIN_EMAIL..."

TOKEN=$(curl -s -X POST "$API_URL/api/portal/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['session_token'])" 2>/dev/null)

if [[ -z "$TOKEN" ]]; then
    error "Login failed! Check credentials and API URL."
    exit 1
fi
success "Authenticated (token: ${TOKEN:0:16}...)"

# ──────────────────── Step 2: Upload Documents ────────────────────
if [[ "$SKIP_UPLOAD" == "false" ]]; then
    header "Step 2: Upload Documents"
    
    UPLOADED=0
    FAILED=0
    TOTAL=0
    
    upload_file() {
        local file="$1"
        local fname
        fname=$(basename "$file")
        
        TOTAL=$((TOTAL + 1))
        
        local result
        result=$(curl -s --max-time 30 -X POST "$API_URL/api/upload" \
            -H "Authorization: Bearer $TOKEN" \
            -F "file=@$file" \
            -F "source=demo_seed" 2>/dev/null)
        
        local status
        status=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','ERROR'))" 2>/dev/null || echo "ERROR")
        
        if [[ "$status" == "uploaded" ]]; then
            UPLOADED=$((UPLOADED + 1))
            echo -e "  ${GREEN}✓${NC} $fname"
        else
            FAILED=$((FAILED + 1))
            echo -e "  ${RED}✗${NC} $fname ($status)"
        fi
    }
    
    upload_scenario() {
        local num="$1"
        info "Uploading Scenario $num documents..."
        
        for f in "$DOCS_DIR"/*scenario_"$num"*; do
            if [[ -f "$f" ]]; then
                upload_file "$f"
            fi
        done
    }
    
    if [[ "$SCENARIO" == "all" ]]; then
        upload_scenario 1
        upload_scenario 2
        upload_scenario 3
    else
        upload_scenario "$SCENARIO"
    fi
    
    echo ""
    info "Upload Summary: $UPLOADED uploaded, $FAILED failed out of $TOTAL total"
    
    if [[ "$FAILED" -gt 0 ]]; then
        warn "Some uploads failed. Pipeline may have incomplete data."
    fi
else
    header "Step 2: Skipped (--skip-upload)"
fi

# ──────────────────── Step 3: Wait for Pipeline ────────────────────
if [[ "$WAIT_FOR_PIPELINE" == "true" ]]; then
    header "Step 3: Wait for Pipeline"
    info "Waiting for extraction pipeline to complete (timeout: ${TIMEOUT}s)..."
    
    ELAPSED=0
    INTERVAL=10
    
    while [[ $ELAPSED -lt $TIMEOUT ]]; do
        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
        
        STATS=$(python3 -c "
import subprocess, json
res = subprocess.run(['curl', '-s', '$API_URL/api/ingest/jobs?limit=500',
    '-H', 'Authorization: Bearer $TOKEN'],
    capture_output=True, text=True, timeout=15)
raw_data = json.loads(res.stdout)
jobs = raw_data.get('jobs', raw_data) if isinstance(raw_data, dict) else raw_data
if not isinstance(jobs, list): jobs = []
completed = sum(1 for j in jobs if j.get('status') == 'completed')
processing = sum(1 for j in jobs if j.get('status') in ('processing', 'queued', 'pending', 'uploaded'))
failed = sum(1 for j in jobs if j.get('status') == 'failed')
print(f'{completed},{processing},{failed},{len(jobs)}')
" 2>/dev/null || echo "0,0,0,0")
        
        IFS=',' read -r COMPLETED PROCESSING FAILED_JOBS TOTAL_JOBS <<< "$STATS"
        
        printf "\r  ⏳ %ds elapsed — %s completed, %s processing, %s failed (of %s total)" \
            "$ELAPSED" "$COMPLETED" "$PROCESSING" "$FAILED_JOBS" "$TOTAL_JOBS"
        
        if [[ "$PROCESSING" == "0" && "$TOTAL_JOBS" -gt 0 ]]; then
            echo ""
            success "Pipeline finished! $COMPLETED jobs completed, $FAILED_JOBS failed."
            break
        fi
    done
    
    if [[ $ELAPSED -ge $TIMEOUT ]]; then
        echo ""
        warn "Timeout reached. $PROCESSING jobs still processing."
    fi
else
    header "Step 3: Skipped (--no-wait)"
fi

# ──────────────────── Step 4: Validate Extraction ────────────────────
header "Step 4: Validate Extracted Data"

python3 - "$API_URL" "$TOKEN" << 'PYEOF'
import subprocess, json, sys

API_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else ""


def api_get(path):
    res = subprocess.run(['curl', '-s', f'{API_URL}{path}',
        '-H', f'Authorization: Bearer {TOKEN}'],
        capture_output=True, text=True, timeout=15)
    try:
        return json.loads(res.stdout)
    except Exception:
        return {}

# Load ground truth
try:
    with open('customs_test_documents/test_data_scenarios.json') as f:
        truth = json.load(f)
except FileNotFoundError:
    print("  ⚠️  Ground truth file not found, skipping validation")
    sys.exit(0)

# Check review queue for our documents
review = api_get('/api/review/items?limit=200')
if isinstance(review, list):
    doc_count = len(review)
elif isinstance(review, dict):
    review_items = review.get('items', review.get('results', []))
    doc_count = len(review_items) if isinstance(review_items, list) else 0
else:
    doc_count = 0

print(f"  📄 Documents in review queue: {doc_count}")

# Check shipments
shipments_data = api_get('/api/shipments?limit=100')
if isinstance(shipments_data, list):
    shipments = shipments_data
elif isinstance(shipments_data, dict):
    shipments = shipments_data.get('shipments', shipments_data.get('items', []))
    if not isinstance(shipments, list):
        shipments = []
else:
    shipments = []

print(f"  🚢 Shipments created: {len(shipments)}")

# Check shipment stats
stats = api_get('/api/shipments/stats')
if not isinstance(stats, dict):
    stats = {}
print(f"  📊 Total linked documents: {stats.get('total_linked_documents', 0)}")
print(f"  📊 Avg docs per shipment: {stats.get('average_documents_per_shipment', 0)}")

# Check entries
entries_data = api_get('/api/entries?limit=100')
if isinstance(entries_data, list):
    entry_count = len(entries_data)
elif isinstance(entries_data, dict):
    entries_items = entries_data.get('items', entries_data.get('entries', []))
    entry_count = len(entries_items) if isinstance(entries_items, list) else 0
else:
    entry_count = 0
print(f"  📋 Customs entries: {entry_count}")

# Validate key identifiers from ground truth
print("\n  Ground Truth Validation:")
for scenario_key, scenario in truth.items():
    mbl = scenario.get('mbl', '')
    name = scenario.get('name', '')
    consignee_count = len(scenario.get('consignees', []))
    
    # Check if MBL appears in shipments
    mbl_found = any(
        isinstance(s, dict) and (
            s.get('bol_number', '') == mbl or 
            s.get('reference_num', '') == mbl or
            (s.get('name') and s.get('name').find(mbl) >= 0)
        )
        for s in shipments
    )
    
    status = "✅" if mbl_found else "⚠️  not found in shipments"
    print(f"    {scenario_key}: {name}")
    print(f"      MBL {mbl} → {status}")
    print(f"      Consignees expected: {consignee_count}")

print("\n  ℹ️  Note: Full field-level validation requires manual review")
print("      of extracted values against ground truth entries.")

PYEOF

# ──────────────────── Step 5: Final Summary ────────────────────
header "Step 5: Summary"

python3 << PYEOF
import subprocess, json

API_URL = "$API_URL"
TOKEN = "$TOKEN"

def api_get(path):
    res = subprocess.run(['curl', '-s', f'{API_URL}{path}',
        '-H', f'Authorization: Bearer {TOKEN}'],
        capture_output=True, text=True, timeout=15)
    try:
        return json.loads(res.stdout)
    except Exception:
        return {}

# Gather final stats
stats = api_get('/api/shipments/stats')
if not isinstance(stats, dict):
    stats = {}

jobs_data = api_get('/api/ingest/jobs?limit=500')
if isinstance(jobs_data, list):
    jobs = jobs_data
elif isinstance(jobs_data, dict):
    jobs = jobs_data.get('jobs', jobs_data.get('items', []))
    if not isinstance(jobs, list):
        jobs = []
else:
    jobs = []

completed = sum(1 for j in jobs if isinstance(j, dict) and j.get('status') == 'completed')
failed = sum(1 for j in jobs if isinstance(j, dict) and j.get('status') == 'failed')

print(f"""
  ┌─────────────────────────────────┐
  │     GATES Demo Data Summary     │
  ├─────────────────────────────────┤
  │  Ingest Jobs Completed: {completed:>5}   │
  │  Ingest Jobs Failed:    {failed:>5}   │
  │  Total Shipments:       {stats.get('total_shipments', 0):>5}   │
  │  Linked Documents:      {stats.get('total_linked_documents', 0):>5}   │
  │  Avg Docs/Shipment:     {stats.get('average_documents_per_shipment', 0):>5.1f}   │
  └─────────────────────────────────┘
""")
PYEOF

success "Demo seeding complete! 🎉"
echo ""
info "Next steps:"
echo "  1. Open http://localhost:3000 to see the platform"
echo "  2. Navigate to Review Queue to see extracted documents"
echo "  3. Check Shipment Assembly for auto-linked shipments"
echo "  4. View Compliance Dashboard for audit scores"
echo ""
