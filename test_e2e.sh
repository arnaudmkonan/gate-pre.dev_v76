#!/bin/bash
# =============================================================================
# E2E Test Script for Document Ingestion Platform
# =============================================================================
# This script tests the full document ingestion flow using the test documents.
# 
# Prerequisites:
#   - Docker Compose services are running (make up)
#   - API is accessible at http://localhost:8000
#
# Usage:
#   ./test_e2e.sh
# =============================================================================

set -e

API_URL="http://localhost:8000"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DOCS_DIR="${SCRIPT_DIR}/test_documents"

echo "=========================================="
echo "Document Ingestion Platform - E2E Tests"
echo "=========================================="
echo ""

# Check if API is up
echo "🔍 Checking API health..."
HEALTH=$(curl -s "${API_URL}/health" 2>/dev/null || echo "FAILED")
if [[ "$HEALTH" == *"ok"* ]]; then
    echo "✅ API is healthy"
else
    echo "❌ API is not responding. Make sure 'make up' has been run."
    exit 1
fi
echo ""

# Check queue status
echo "📊 Checking queue status..."
QUEUE_STATUS=$(curl -s "${API_URL}/api/queue/status")
echo "   Queue status: $QUEUE_STATUS"
echo ""

# List test documents
echo "📁 Test documents available:"
for file in "${TEST_DOCS_DIR}"/*; do
    filename=$(basename "$file")
    size=$(wc -c < "$file" | tr -d ' ')
    echo "   - ${filename} (${size} bytes)"
done
echo ""

# Test 1: Upload a text file
echo "=========================================="
echo "TEST 1: Upload text file (employee_handbook.txt)"
echo "=========================================="
UPLOAD_RESULT=$(curl -s -X POST "${API_URL}/api/upload" \
    -F "file=@${TEST_DOCS_DIR}/employee_handbook.txt" \
    -F "source=test" \
    -F "customer_id=test-customer" \
    -F "tags=handbook,hr,policies" 2>&1)

if [[ "$UPLOAD_RESULT" == *"job_id"* ]]; then
    echo "✅ Upload successful!"
    echo "   Response: $UPLOAD_RESULT"
else
    echo "⚠️  Upload may have failed:"
    echo "   Response: $UPLOAD_RESULT"
fi
echo ""

# Test 2: Upload a Markdown file
echo "=========================================="
echo "TEST 2: Upload markdown file (api_documentation.md)"
echo "=========================================="
UPLOAD_RESULT=$(curl -s -X POST "${API_URL}/api/upload" \
    -F "file=@${TEST_DOCS_DIR}/api_documentation.md" \
    -F "source=docs" \
    -F "tags=api,documentation,technical" 2>&1)

if [[ "$UPLOAD_RESULT" == *"job_id"* ]]; then
    echo "✅ Upload successful!"
    echo "   Response: $UPLOAD_RESULT"
else
    echo "⚠️  Upload may have failed:"
    echo "   Response: $UPLOAD_RESULT"
fi
echo ""

# Test 3: Upload a JSON file
echo "=========================================="
echo "TEST 3: Upload JSON file (product_catalog.json)"
echo "=========================================="
UPLOAD_RESULT=$(curl -s -X POST "${API_URL}/api/upload" \
    -F "file=@${TEST_DOCS_DIR}/product_catalog.json" \
    -F "source=catalog" \
    -F "tags=products,catalog,inventory" 2>&1)

if [[ "$UPLOAD_RESULT" == *"job_id"* ]]; then
    echo "✅ Upload successful!"
    echo "   Response: $UPLOAD_RESULT"
else
    echo "⚠️  Upload may have failed:"
    echo "   Response: $UPLOAD_RESULT"
fi
echo ""

# Test 4: Upload a CSV file
echo "=========================================="
echo "TEST 4: Upload CSV file (employee_data.csv)"
echo "=========================================="
UPLOAD_RESULT=$(curl -s -X POST "${API_URL}/api/upload" \
    -F "file=@${TEST_DOCS_DIR}/employee_data.csv" \
    -F "source=hr" \
    -F "customer_id=test-customer" \
    -F "tags=employees,hr,data" 2>&1)

if [[ "$UPLOAD_RESULT" == *"job_id"* ]]; then
    echo "✅ Upload successful!"
    echo "   Response: $UPLOAD_RESULT"
else
    echo "⚠️  Upload may have failed:"
    echo "   Response: $UPLOAD_RESULT"
fi
echo ""

# Test 5: Upload an HTML file
echo "=========================================="
echo "TEST 5: Upload HTML file (quarterly_report.html)"
echo "=========================================="
UPLOAD_RESULT=$(curl -s -X POST "${API_URL}/api/upload" \
    -F "file=@${TEST_DOCS_DIR}/quarterly_report.html" \
    -F "source=finance" \
    -F "tags=report,quarterly,finance" 2>&1)

if [[ "$UPLOAD_RESULT" == *"job_id"* ]]; then
    echo "✅ Upload successful!"
    echo "   Response: $UPLOAD_RESULT"
else
    echo "⚠️  Upload may have failed:"
    echo "   Response: $UPLOAD_RESULT"
fi
echo ""

# Test 6: Upload a YAML file
echo "=========================================="
echo "TEST 6: Upload YAML file (app_config.yml)"
echo "=========================================="
UPLOAD_RESULT=$(curl -s -X POST "${API_URL}/api/upload" \
    -F "file=@${TEST_DOCS_DIR}/app_config.yml" \
    -F "source=devops" \
    -F "tags=config,infrastructure,yaml" 2>&1)

if [[ "$UPLOAD_RESULT" == *"job_id"* ]]; then
    echo "✅ Upload successful!"
    echo "   Response: $UPLOAD_RESULT"
else
    echo "⚠️  Upload may have failed:"
    echo "   Response: $UPLOAD_RESULT"
fi
echo ""

# Check final queue status
echo "=========================================="
echo "Final Queue Status"
echo "=========================================="
sleep 2  # Wait for jobs to be queued
QUEUE_STATUS=$(curl -s "${API_URL}/api/queue/status")
echo "Queue: $QUEUE_STATUS"
echo ""

# List ingest jobs
echo "=========================================="
echo "Ingest Jobs Created"
echo "=========================================="
JOBS=$(curl -s "${API_URL}/api/ingest/jobs?page=1&page_size=10")
echo "$JOBS" | head -100
echo ""

echo "=========================================="
echo "E2E Tests Complete!"
echo "=========================================="
echo ""
echo "📍 Check these dashboards for more details:"
echo "   - Frontend:     http://localhost:3000"
echo "   - API Docs:     http://localhost:8000/docs"
echo "   - PGWeb:        http://localhost:8081"
echo "   - Flower:       http://localhost:5555 (admin:admin)"
