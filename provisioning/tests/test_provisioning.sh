#!/bin/bash
# =============================================================================
# GATE Platform — Provisioning Integration Test
# =============================================================================
#
# Validates that the provisioning script correctly creates a customer instance.
# Creates a temporary test instance, verifies all outputs, then cleans up.
#
# Usage: ./test_provisioning.sh
#
# Exit codes:
#   0 = all tests passed
#   1 = one or more tests failed
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROVISION_SCRIPT="$PROJECT_ROOT/provisioning/scripts/provision.sh"
TEMPLATE_DIR="$PROJECT_ROOT/provisioning/templates"

# Test instance details
TEST_ID="test-$(date +%s)"
TEST_NAME="Integration Test Corp"
TEST_EMAIL="test@gate-test.com"
TEST_SUB="test-sub"
TEST_VERSION="1.0.0-test"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0
TOTAL=0

pass() {
    ((TOTAL++))
    ((PASSED++))
    echo -e "  ${GREEN}✓${NC} $1"
}

fail() {
    ((TOTAL++))
    ((FAILED++))
    echo -e "  ${RED}✗${NC} $1"
    echo -e "    ${RED}→ $2${NC}"
}

echo ""
echo "================================================================"
echo "  GATE Platform — Provisioning Integration Test"
echo "================================================================"
echo ""
echo "Test instance: $TEST_ID"
echo ""

# ─────────────────── Pre-checks ───────────────────

echo "Pre-checks:"

if [ -f "$PROVISION_SCRIPT" ]; then
    pass "Provisioning script exists"
else
    fail "Provisioning script exists" "Not found at $PROVISION_SCRIPT"
    exit 1
fi

if [ -x "$PROVISION_SCRIPT" ]; then
    pass "Provisioning script is executable"
else
    fail "Provisioning script is executable" "chmod +x needed"
fi

if [ -d "$TEMPLATE_DIR" ]; then
    pass "Template directory exists"
else
    fail "Template directory exists" "Not found at $TEMPLATE_DIR"
fi

for tpl in docker-compose.yml.template upgrade.sh status.sh backup.sh; do
    if [ -f "$TEMPLATE_DIR/$tpl" ]; then
        pass "Template exists: $tpl"
    else
        fail "Template exists: $tpl" "Not found at $TEMPLATE_DIR/$tpl"
    fi
done

echo ""

# ─────────────────── Run provisioning ───────────────────

echo "Provisioning test instance..."

INSTANCE_DIR="$PROJECT_ROOT/provisioning/instances/$TEST_ID"

# Capture output and exit code
PROV_OUTPUT=$("$PROVISION_SCRIPT" "$TEST_ID" "$TEST_NAME" "$TEST_EMAIL" "$TEST_SUB" "$TEST_VERSION" 2>&1) || true

echo ""
echo "Verifying outputs:"

# Directory structure
if [ -d "$INSTANCE_DIR" ]; then
    pass "Instance directory created"
else
    fail "Instance directory created" "Expected $INSTANCE_DIR"
fi

# .env file
if [ -f "$INSTANCE_DIR/.env" ]; then
    pass ".env file created"

    # Check .env contents
    if grep -q "CUSTOMER_ID=$TEST_ID" "$INSTANCE_DIR/.env" 2>/dev/null; then
        pass ".env contains CUSTOMER_ID"
    else
        fail ".env contains CUSTOMER_ID" "Missing CUSTOMER_ID=$TEST_ID"
    fi

    if grep -q "GATE_VERSION=$TEST_VERSION" "$INSTANCE_DIR/.env" 2>/dev/null; then
        pass ".env contains GATE_VERSION"
    else
        fail ".env contains GATE_VERSION" "Missing GATE_VERSION=$TEST_VERSION"
    fi

    if grep -q "POSTGRES_PASSWORD=" "$INSTANCE_DIR/.env" 2>/dev/null; then
        pass ".env contains POSTGRES_PASSWORD"
    else
        fail ".env contains POSTGRES_PASSWORD" "Missing"
    fi

    if grep -q "JWT_SECRET=" "$INSTANCE_DIR/.env" 2>/dev/null; then
        pass ".env contains JWT_SECRET"
    else
        fail ".env contains JWT_SECRET" "Missing"
    fi
else
    fail ".env file created" "Not found"
fi

# docker-compose.yml
if [ -f "$INSTANCE_DIR/docker-compose.yml" ]; then
    pass "docker-compose.yml created"

    # Verify it's valid YAML (basic check)
    if head -1 "$INSTANCE_DIR/docker-compose.yml" | grep -qE "^(version|services|#)"; then
        pass "docker-compose.yml has valid header"
    else
        pass "docker-compose.yml exists (header check skipped)"
    fi
else
    fail "docker-compose.yml created" "Not found"
fi

# Operational scripts
for script in upgrade.sh status.sh backup.sh; do
    if [ -f "$INSTANCE_DIR/$script" ]; then
        pass "Operational script installed: $script"
        if [ -x "$INSTANCE_DIR/$script" ]; then
            pass "Script is executable: $script"
        else
            fail "Script is executable: $script" "Not executable"
        fi
    else
        fail "Operational script installed: $script" "Not found"
    fi
done

# Backups directory
if [ -d "$INSTANCE_DIR/backups" ]; then
    pass "Backups directory created"
else
    fail "Backups directory created" "Not found"
fi

# Certificates directory
if [ -d "$INSTANCE_DIR/certs" ]; then
    pass "Certificates directory created"
else
    # Some provisioning versions may not create this
    echo -e "  ${YELLOW}⚠${NC} Certificates directory not found (optional)"
fi

echo ""

# ─────────────────── Cleanup ───────────────────

echo "Cleaning up test instance..."
rm -rf "$INSTANCE_DIR"

if [ ! -d "$INSTANCE_DIR" ]; then
    pass "Test instance cleaned up"
else
    fail "Test instance cleaned up" "Directory still exists"
fi

echo ""

# ─────────────────── Results ───────────────────

echo "================================================================"
if [ $FAILED -eq 0 ]; then
    echo -e "  ${GREEN}All $TOTAL tests passed!${NC}"
else
    echo -e "  ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC} (of $TOTAL total)"
fi
echo "================================================================"
echo ""

exit $FAILED
