#!/bin/bash

# Test script to verify backend is working

echo "Testing backend at http://localhost:8000"
echo "=========================================="
echo ""

# Test 1: Health check
echo "1. Testing health endpoint..."
curl -s http://localhost:8000/api/health | jq '.' || echo "Health check failed"
echo ""

# Test 2: Login (to get token)
echo "2. Testing login..."
if [ -z "$TEST_PASSWORD" ]; then
  echo "   Enter password (or set TEST_PASSWORD env var):"
  read -s TEST_PASSWORD
fi
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"$TEST_PASSWORD\"}" | jq -r '.token')

if [ "$TOKEN" != "null" ] && [ -n "$TOKEN" ]; then
  echo "✓ Login successful, got token"
else
  echo "✗ Login failed"
  exit 1
fi
echo ""

# Test 3: List indexes
echo "3. Testing list indexes..."
curl -s http://localhost:8000/api/indexes \
  -H "Authorization: Bearer $TOKEN" | jq '.indexes | length' || echo "List indexes failed"
echo ""

# Test 4: Analyze index (this should show logs in backend terminal)
echo "4. Testing analyze index endpoint..."
echo "   (Check your backend terminal for logs!)"
curl -s -X POST http://localhost:8000/api/analyze/index \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "index_id": "test-index",
    "query": "test query",
    "verbosity": "concise"
  }' | jq '.metadata.jockey_enabled' || echo "Analyze failed"
echo ""

echo "=========================================="
echo "Check your backend terminal for log output!"
echo "You should see:"
echo "  - ENDPOINT CALLED: /api/analyze/index"
echo "  - ANALYSIS DEBUG INFO"
