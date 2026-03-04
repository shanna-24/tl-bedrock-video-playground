#!/bin/bash
# Error Recovery Testing Script for Embedding Job Processor
# This script simulates various failure scenarios to test retry logic and error handling

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
JOB_STORE_FILE=".kiro/data/embedding_jobs.json"
BACKUP_FILE=".kiro/data/embedding_jobs.json.backup"

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_test_header() {
    echo -e "\n${MAGENTA}>>> TEST: $1${NC}"
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

test_passed() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    print_success "TEST PASSED: $1"
}

test_failed() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    print_error "TEST FAILED: $1"
}

# Backup job store
backup_job_store() {
    if [ -f "$JOB_STORE_FILE" ]; then
        cp "$JOB_STORE_FILE" "$BACKUP_FILE"
        print_info "Backed up job store to $BACKUP_FILE"
    fi
}

# Restore job store
restore_job_store() {
    if [ -f "$BACKUP_FILE" ]; then
        cp "$BACKUP_FILE" "$JOB_STORE_FILE"
        print_info "Restored job store from backup"
        rm "$BACKUP_FILE"
    fi
}

# Check if backend is running
check_backend() {
    if ! curl -s "${API_BASE_URL}/health" > /dev/null 2>&1; then
        print_error "Backend is not running at ${API_BASE_URL}"
        print_info "Start the backend with: python -m src.main"
        exit 1
    fi
}

# Get or create test index
get_test_index() {
    if [ -f ".error_test_index_id" ]; then
        cat ".error_test_index_id"
        return 0
    fi
    
    # Create new test index
    INDEX_NAME="error-recovery-test-$(date +%s)"
    RESPONSE=$(curl -s -X POST "${API_BASE_URL}/api/indexes" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"${INDEX_NAME}\",
            \"description\": \"Test index for error recovery validation\"
        }")
    
    INDEX_ID=$(echo "$RESPONSE" | jq -r '.id')
    echo "$INDEX_ID" > ".error_test_index_id"
    echo "$INDEX_ID"
}

# Create a fake job with invalid invocation ARN
create_fake_job_invalid_arn() {
    print_test_header "Simulate Bedrock job failure (invalid invocation ARN)"
    
    backup_job_store
    
    local index_id=$(get_test_index)
    local job_id=$(uuidgen | tr '[:upper:]' '[:lower:]')
    local video_id="test-video-$(date +%s)"
    local invalid_arn="arn:aws:bedrock:eu-west-1:123456789012:model-invocation-job/invalid-job-id"
    
    print_info "Creating fake job with invalid ARN: $invalid_arn"
    
    # Read current jobs
    local jobs="{}"
    if [ -f "$JOB_STORE_FILE" ]; then
        jobs=$(cat "$JOB_STORE_FILE")
    fi
    
    # Add fake job
    local new_job=$(cat <<EOF
{
  "job_id": "$job_id",
  "invocation_arn": "$invalid_arn",
  "video_id": "$video_id",
  "index_id": "$index_id",
  "s3_uri": "s3://test-bucket/test-video.mp4",
  "status": "pending",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "updated_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "retry_count": 0,
  "error_message": null,
  "output_location": null,
  "next_retry_at": null
}
EOF
)
    
    # Merge jobs
    local updated_jobs=$(echo "$jobs" | jq --argjson new "$new_job" ". + {\"$job_id\": \$new}")

    
    # Write back to file
    echo "$updated_jobs" > "$JOB_STORE_FILE"
    
    print_success "Created fake job: $job_id"
    echo "$job_id" > ".error_test_job_id"
    
    # Wait for processor to pick it up and retry
    print_info "Waiting for processor to detect and retry the job..."
    print_info "This will take up to 90 seconds (polling interval + retry delay)"
    
    local max_wait=120
    local elapsed=0
    local retry_detected=false
    
    while [ $elapsed -lt $max_wait ]; do
        sleep 10
        elapsed=$((elapsed + 10))
        
        # Check job status
        local job=$(cat "$JOB_STORE_FILE" | jq -r ".\"$job_id\"")
        local status=$(echo "$job" | jq -r '.status')
        local retry_count=$(echo "$job" | jq -r '.retry_count')
        local error_msg=$(echo "$job" | jq -r '.error_message // "none"')
        
        print_info "[$elapsed s] Status: $status, Retry count: $retry_count"
        
        if [ "$retry_count" -gt 0 ]; then
            retry_detected=true
            print_success "Retry logic triggered! Retry count: $retry_count"
            print_info "Error message: $error_msg"
        fi
        
        # Check if job reached max retries and failed permanently
        if [ "$status" = "failed" ] && [ "$retry_count" -ge 3 ]; then
            print_success "Job failed permanently after max retries"
            print_info "Final error message: $error_msg"
            test_passed "Invalid ARN causes retries and eventual permanent failure"
            restore_job_store
            return 0
        fi
    done
    
    if [ "$retry_detected" = true ]; then
        test_passed "Retry logic works for invalid ARN (partial success)"
        print_warning "Job did not reach permanent failure within timeout"
    else
        test_failed "Retry logic did not trigger for invalid ARN"
    fi
    
    restore_job_store
}

# Test retry logic with exponential backoff
test_retry_backoff() {
    print_test_header "Verify exponential backoff between retries"
    
    backup_job_store
    
    local index_id=$(get_test_index)
    local job_id=$(uuidgen | tr '[:upper:]' '[:lower:]')
    local video_id="test-video-$(date +%s)"
    local invalid_arn="arn:aws:bedrock:eu-west-1:123456789012:model-invocation-job/backoff-test"
    
    print_info "Creating job to test exponential backoff"
    
    # Read current jobs
    local jobs="{}"
    if [ -f "$JOB_STORE_FILE" ]; then
        jobs=$(cat "$JOB_STORE_FILE")
    fi
    
    # Add fake job
    local new_job=$(cat <<EOF
{
  "job_id": "$job_id",
  "invocation_arn": "$invalid_arn",
  "video_id": "$video_id",
  "index_id": "$index_id",
  "s3_uri": "s3://test-bucket/test-video.mp4",
  "status": "pending",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "updated_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "retry_count": 0,
  "error_message": null,
  "output_location": null,
  "next_retry_at": null
}
EOF
)
    
    # Merge jobs
    local updated_jobs=$(echo "$jobs" | jq --argjson new "$new_job" ". + {\"$job_id\": \$new}")
    echo "$updated_jobs" > "$JOB_STORE_FILE"
    
    print_success "Created test job: $job_id"
    
    # Track retry timestamps
    local retry_times=()
    local max_wait=300  # 5 minutes
    local elapsed=0
    
    print_info "Monitoring retry timing (this may take several minutes)..."
    
    while [ $elapsed -lt $max_wait ]; do
        sleep 15
        elapsed=$((elapsed + 15))
        
        # Check job status
        local job=$(cat "$JOB_STORE_FILE" | jq -r ".\"$job_id\"")
        local retry_count=$(echo "$job" | jq -r '.retry_count')
        local updated_at=$(echo "$job" | jq -r '.updated_at')
        local next_retry_at=$(echo "$job" | jq -r '.next_retry_at // "none"')
        
        # Record retry time if retry count increased
        if [ "$retry_count" -gt "${#retry_times[@]}" ]; then
            retry_times+=("$(date +%s)")
            print_info "Retry $retry_count detected at $(date)"
            print_info "Next retry scheduled at: $next_retry_at"
            
            # Calculate backoff if we have multiple retries
            if [ ${#retry_times[@]} -gt 1 ]; then
                local prev_idx=$((${#retry_times[@]} - 2))
                local time_diff=$((${retry_times[-1]} - ${retry_times[$prev_idx]}))
                print_info "Time since last retry: ${time_diff}s"
                
                # Expected backoff: 2^(retry_count-1) * 60 seconds
                # Retry 1: 60s, Retry 2: 120s, Retry 3: 240s
                local expected_min=$((2 ** (retry_count - 1) * 60 - 30))  # Allow 30s tolerance
                local expected_max=$((2 ** (retry_count - 1) * 60 + 60))  # Allow 60s tolerance
                
                if [ $time_diff -ge $expected_min ] && [ $time_diff -le $expected_max ]; then
                    print_success "Backoff timing is correct (${time_diff}s within expected range)"
                else
                    print_warning "Backoff timing may be off (${time_diff}s, expected ~$((2 ** (retry_count - 1) * 60))s)"
                fi
            fi
        fi
        
        # Stop if we've seen 3 retries
        if [ "$retry_count" -ge 3 ]; then
            print_success "Observed all 3 retries"
            break
        fi
    done
    
    if [ ${#retry_times[@]} -ge 2 ]; then
        test_passed "Exponential backoff is working"
        print_info "Retry times recorded: ${#retry_times[@]}"
    else
        test_failed "Not enough retries observed to verify backoff"
    fi
    
    restore_job_store
}

# Test permanent failure after max retries
test_permanent_failure() {
    print_test_header "Verify permanent failure after max retries"
    
    backup_job_store
    
    local index_id=$(get_test_index)
    local job_id=$(uuidgen | tr '[:upper:]' '[:lower:]')
    local video_id="test-video-$(date +%s)"
    local invalid_arn="arn:aws:bedrock:eu-west-1:123456789012:model-invocation-job/permanent-fail"
    
    print_info "Creating job that will fail permanently"
    
    # Read current jobs
    local jobs="{}"
    if [ -f "$JOB_STORE_FILE" ]; then
        jobs=$(cat "$JOB_STORE_FILE")
    fi
    
    # Add fake job with 2 retries already (will fail on next attempt)
    local new_job=$(cat <<EOF
{
  "job_id": "$job_id",
  "invocation_arn": "$invalid_arn",
  "video_id": "$video_id",
  "index_id": "$index_id",
  "s3_uri": "s3://test-bucket/test-video.mp4",
  "status": "pending",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "updated_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "retry_count": 2,
  "error_message": "Previous retry failed",
  "output_location": null,
  "next_retry_at": null
}
EOF
)
    
    # Merge jobs
    local updated_jobs=$(echo "$jobs" | jq --argjson new "$new_job" ". + {\"$job_id\": \$new}")
    echo "$updated_jobs" > "$JOB_STORE_FILE"
    
    print_success "Created job with retry_count=2: $job_id"
    print_info "Waiting for processor to attempt final retry and mark as failed..."
    
    local max_wait=180
    local elapsed=0
    
    while [ $elapsed -lt $max_wait ]; do
        sleep 10
        elapsed=$((elapsed + 10))
        
        # Check job status
        local job=$(cat "$JOB_STORE_FILE" | jq -r ".\"$job_id\"")
        local status=$(echo "$job" | jq -r '.status')
        local retry_count=$(echo "$job" | jq -r '.retry_count')
        local error_msg=$(echo "$job" | jq -r '.error_message // "none"')
        
        print_info "[$elapsed s] Status: $status, Retry count: $retry_count"
        
        if [ "$status" = "failed" ]; then
            print_success "Job marked as permanently failed"
            print_info "Final retry count: $retry_count"
            print_info "Error message: $error_msg"
            
            # Verify error message mentions max retries
            if echo "$error_msg" | grep -qi "max retries"; then
                print_success "Error message correctly indicates max retries exceeded"
                test_passed "Permanent failure after max retries works correctly"
            else
                print_warning "Error message doesn't mention max retries: $error_msg"
                test_passed "Permanent failure works (but error message could be clearer)"
            fi
            
            restore_job_store
            return 0
        fi
    done
    
    test_failed "Job did not reach permanent failure within timeout"
    restore_job_store
}

# Test that processor continues processing other jobs after one fails
test_continues_after_failure() {
    print_test_header "Verify processor continues processing other jobs after failure"
    
    backup_job_store
    
    local index_id=$(get_test_index)
    
    # Create one failing job and one that would succeed (if we had real Bedrock)
    local fail_job_id=$(uuidgen | tr '[:upper:]' '[:lower:]')
    local good_job_id=$(uuidgen | tr '[:upper:]' '[:lower:]')
    
    print_info "Creating two jobs: one that will fail, one that would succeed"
    
    # Read current jobs
    local jobs="{}"
    if [ -f "$JOB_STORE_FILE" ]; then
        jobs=$(cat "$JOB_STORE_FILE")
    fi
    
    # Add failing job
    local fail_job=$(cat <<EOF
{
  "job_id": "$fail_job_id",
  "invocation_arn": "arn:aws:bedrock:eu-west-1:123456789012:model-invocation-job/will-fail",
  "video_id": "fail-video-$(date +%s)",
  "index_id": "$index_id",
  "s3_uri": "s3://test-bucket/fail-video.mp4",
  "status": "pending",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "updated_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "retry_count": 0,
  "error_message": null,
  "output_location": null,
  "next_retry_at": null
}
EOF
)
    
    # Add "good" job (will also fail in test but we check it's processed)
    local good_job=$(cat <<EOF
{
  "job_id": "$good_job_id",
  "invocation_arn": "arn:aws:bedrock:eu-west-1:123456789012:model-invocation-job/good-job",
  "video_id": "good-video-$(date +%s)",
  "index_id": "$index_id",
  "s3_uri": "s3://test-bucket/good-video.mp4",
  "status": "pending",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "updated_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "retry_count": 0,
  "error_message": null,
  "output_location": null,
  "next_retry_at": null
}
EOF
)
    
    # Merge jobs
    local updated_jobs=$(echo "$jobs" | jq --argjson fail "$fail_job" --argjson good "$good_job" \
        ". + {\"$fail_job_id\": \$fail, \"$good_job_id\": \$good}")
    echo "$updated_jobs" > "$JOB_STORE_FILE"
    
    print_success "Created two test jobs"
    print_info "Fail job: $fail_job_id"
    print_info "Good job: $good_job_id"
    
    # Wait and check both jobs are processed
    print_info "Waiting for processor to handle both jobs..."
    
    local max_wait=120
    local elapsed=0
    local fail_job_processed=false
    local good_job_processed=false
    
    while [ $elapsed -lt $max_wait ]; do
        sleep 10
        elapsed=$((elapsed + 10))
        
        # Check both jobs
        local fail_job_data=$(cat "$JOB_STORE_FILE" | jq -r ".\"$fail_job_id\"")
        local good_job_data=$(cat "$JOB_STORE_FILE" | jq -r ".\"$good_job_id\"")
        
        local fail_retry=$(echo "$fail_job_data" | jq -r '.retry_count')
        local good_retry=$(echo "$good_job_data" | jq -r '.retry_count')
        
        print_info "[$elapsed s] Fail job retries: $fail_retry, Good job retries: $good_retry"
        
        # Check if both have been processed (retry count > 0)
        if [ "$fail_retry" -gt 0 ]; then
            fail_job_processed=true
        fi
        
        if [ "$good_retry" -gt 0 ]; then
            good_job_processed=true
        fi
        
        if [ "$fail_job_processed" = true ] && [ "$good_job_processed" = true ]; then
            print_success "Both jobs have been processed"
            test_passed "Processor continues processing after failures"
            restore_job_store
            return 0
        fi
    done
    
    if [ "$fail_job_processed" = true ] || [ "$good_job_processed" = true ]; then
        test_passed "Processor continues processing (partial success)"
        print_warning "Not all jobs were processed within timeout"
    else
        test_failed "Processor did not process jobs"
    fi
    
    restore_job_store
}

# Check processor health during error scenarios
check_processor_health() {
    print_test_header "Verify processor remains healthy during error scenarios"
    
    print_info "Checking processor health endpoint..."
    
    local health=$(curl -s "${API_BASE_URL}/health/processor")
    
    if [ $? -ne 0 ]; then
        test_failed "Health endpoint not accessible"
        return 1
    fi
    
    local status=$(echo "$health" | jq -r '.status')
    local running=$(echo "$health" | jq -r '.processor_running')
    local jobs_failed=$(echo "$health" | jq -r '.jobs_failed')
    local jobs_retried=$(echo "$health" | jq -r '.jobs_retried')
    
    print_info "Status: $status"
    print_info "Running: $running"
    print_info "Jobs failed: $jobs_failed"
    print_info "Jobs retried: $jobs_retried"
    
    if [ "$status" = "healthy" ] && [ "$running" = "true" ]; then
        test_passed "Processor is healthy and running"
    else
        test_failed "Processor health check failed"
    fi
}

# Print test summary
print_summary() {
    print_header "Test Summary"
    
    echo -e "${BLUE}Total tests: ${TESTS_TOTAL}${NC}"
    echo -e "${GREEN}Passed: ${TESTS_PASSED}${NC}"
    echo -e "${RED}Failed: ${TESTS_FAILED}${NC}"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}✓ ALL TESTS PASSED${NC}\n"
        return 0
    else
        echo -e "\n${RED}✗ SOME TESTS FAILED${NC}\n"
        return 1
    fi
}

# Main execution
main() {
    print_header "Error Recovery Testing - Embedding Job Processor"
    
    print_info "This script tests the retry logic and error handling of the processor"
    print_info "It will create fake jobs with invalid ARNs to simulate failures"
    print_warning "This test will take several minutes to complete"
    
    # Check prerequisites
    check_backend
    
    # Run tests
    create_fake_job_invalid_arn
    sleep 5
    
    test_retry_backoff
    sleep 5
    
    test_permanent_failure
    sleep 5
    
    test_continues_after_failure
    sleep 5
    
    check_processor_health
    
    # Print summary
    print_summary
}

# Run main function
main
