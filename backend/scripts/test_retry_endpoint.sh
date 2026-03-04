#!/bin/bash
# Manual test script for the job retry endpoint
# This script demonstrates how to use the POST /api/embedding-jobs/{job_id}/retry endpoint

set -e

# Configuration
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_PREFIX="/api/embedding-jobs"

echo "=== Testing Job Retry Endpoint ==="
echo "Base URL: $BASE_URL"
echo ""

# Function to make API calls with proper error handling
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3
    
    if [ -n "$data" ]; then
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$BASE_URL$endpoint"
    else
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            "$BASE_URL$endpoint"
    fi
}

# Test 1: List all failed jobs
echo "1. Listing all failed jobs..."
FAILED_JOBS=$(api_call GET "$API_PREFIX?status=failed")
echo "$FAILED_JOBS" | python3 -m json.tool
echo ""

# Extract first failed job ID if any
FAILED_JOB_ID=$(echo "$FAILED_JOBS" | python3 -c "import sys, json; jobs = json.load(sys.stdin)['jobs']; print(jobs[0]['job_id'] if jobs else '')")

if [ -z "$FAILED_JOB_ID" ]; then
    echo "No failed jobs found. Cannot test retry endpoint."
    echo "To test this endpoint:"
    echo "  1. Upload a video that will fail processing"
    echo "  2. Wait for it to reach 'failed' status"
    echo "  3. Run this script again"
    exit 0
fi

echo "Found failed job: $FAILED_JOB_ID"
echo ""

# Test 2: Get job details before retry
echo "2. Getting job details before retry..."
api_call GET "$API_PREFIX/$FAILED_JOB_ID" | python3 -m json.tool
echo ""

# Test 3: Retry the failed job
echo "3. Retrying failed job..."
RETRY_RESULT=$(api_call POST "$API_PREFIX/$FAILED_JOB_ID/retry")
echo "$RETRY_RESULT" | python3 -m json.tool
echo ""

# Test 4: Verify job status changed to pending
echo "4. Verifying job status after retry..."
UPDATED_JOB=$(api_call GET "$API_PREFIX/$FAILED_JOB_ID")
echo "$UPDATED_JOB" | python3 -m json.tool
echo ""

# Verify status is now pending
NEW_STATUS=$(echo "$UPDATED_JOB" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
RETRY_COUNT=$(echo "$UPDATED_JOB" | python3 -c "import sys, json; print(json.load(sys.stdin)['retry_count'])")

if [ "$NEW_STATUS" = "pending" ] && [ "$RETRY_COUNT" = "0" ]; then
    echo "✅ SUCCESS: Job status reset to pending with retry_count=0"
else
    echo "❌ FAILED: Job status is $NEW_STATUS with retry_count=$RETRY_COUNT"
    exit 1
fi

echo ""
echo "=== Test Complete ==="
echo ""
echo "The job will now be picked up by the background processor."
echo "Monitor the logs to see it being processed:"
echo "  tail -f logs/app.log | grep '$FAILED_JOB_ID'"
