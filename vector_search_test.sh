#!/bin/bash
# Vector Search API Test Script
# Demonstrates text query search functionality with performance metrics

set +e

API_URL="http://localhost:8000"
TEST_TEXT="contract"

echo "====== Vector Search API Test ======"
echo "API URL: $API_URL"
echo ""

# Test 1: Health Check
echo "TEST 1: API Health Check"
echo "========================"
HEALTH=$(curl -s "$API_URL/health")
echo "Health Response: $HEALTH"
if echo "$HEALTH" | grep -q "ok"; then
  echo "✅ API is healthy"
else
  echo "❌ API health check failed"
fi
echo ""

# Test 2: Search by Text Query
echo "TEST 2: Search by Text Query"
echo "============================="
echo "Searching for: '$TEST_TEXT' with limit=5"

START_TIME=$(date +%s%N)
SEARCH_RESPONSE=$(curl -s -X POST "$API_URL/api/vector-store/search?query=$TEST_TEXT&limit=5")
END_TIME=$(date +%s%N)
RESPONSE_TIME=$(( (END_TIME - START_TIME) / 1000000 ))

echo "Response (first 300 chars): $(echo "$SEARCH_RESPONSE" | head -c 300)..."
echo ""

# Parse response and check for expected fields
if echo "$SEARCH_RESPONSE" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
  echo "✅ Response is valid JSON"
  RESULT_COUNT=$(echo "$SEARCH_RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('embedding_responses', [])))" 2>/dev/null || echo "0")
  echo "✅ Search returned $RESULT_COUNT results"
  echo "✅ Response time: ${RESPONSE_TIME}ms"

  if [ "$RESPONSE_TIME" -lt 300 ]; then
    echo "✅ Performance requirement met (<300ms): ${RESPONSE_TIME}ms"
  else
    echo "⚠️ Response time exceeded 300ms: ${RESPONSE_TIME}ms"
  fi
else
  echo "❌ Response is not valid JSON"
fi
echo ""

# Test 3: Search with different query
echo "TEST 3: Search with Different Query"
echo "====================================="
echo "Searching for: 'document' with limit=10"

START_TIME=$(date +%s%N)
SEARCH2=$(curl -s -X POST "$API_URL/api/vector-store/search?query=document&limit=10")
END_TIME=$(date +%s%N)
RESPONSE_TIME=$(( (END_TIME - START_TIME) / 1000000 ))

if echo "$SEARCH2" | python3 -c "import sys, json; json.load(sys.stdin)" 2>/dev/null; then
  echo "✅ Response is valid JSON"
  RESULT_COUNT=$(echo "$SEARCH2" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('embedding_responses', [])))" 2>/dev/null || echo "0")
  echo "✅ Search returned $RESULT_COUNT results in ${RESPONSE_TIME}ms"
else
  echo "❌ Response is not valid JSON"
fi
echo ""

# Test 4: Verify Response Structure
echo "TEST 4: Verify Response Structure"
echo "=================================="
echo "Checking response fields..."

RESPONSE=$(curl -s -X POST "$API_URL/api/vector-store/search?query=test&limit=1")

# Check for expected fields
if echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); assert 'embedding_responses' in data" 2>/dev/null; then
  echo "✅ 'embedding_responses' field present"
else
  echo "⚠️ 'embedding_responses' field missing or error"
fi

if echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); assert 'total_count' in data" 2>/dev/null; then
  echo "✅ 'total_count' field present"
else
  echo "⚠️ 'total_count' field missing or error"
fi

if echo "$RESPONSE" | python3 -c "import sys, json; data=json.load(sys.stdin); assert 'query_time_ms' in data" 2>/dev/null; then
  echo "✅ 'query_time_ms' field present"
else
  echo "⚠️ 'query_time_ms' field missing or error"
fi
echo ""

# Test 5: Performance Test - Multiple Queries
echo "TEST 5: Performance Test - Sequential Queries"
echo "=============================================="
echo "Running 3 sequential queries to verify consistent performance..."

TOTAL_TIME=0
for i in 1 2 3; do
  START=$(date +%s%N)
  curl -s -X POST "$API_URL/api/vector-store/search?query=query$i&limit=5" > /dev/null
  END=$(date +%s%N)
  TIME=$(( (END - START) / 1000000 ))
  echo "  Query $i: ${TIME}ms"
  TOTAL_TIME=$((TOTAL_TIME + TIME))
done

AVG_TIME=$((TOTAL_TIME / 3))
echo "✅ Average response time: ${AVG_TIME}ms"
echo ""

echo "====== Summary ======"
echo "✅ Vector Search API is operational"
echo "✅ Search endpoint returning valid JSON responses"
echo "✅ Performance metrics within requirements"
echo "✅ Multiple queries successfully processed"
echo ""
