#!/bin/bash
# Concurrent Upload Testing Script for Embedding Job Processor
# Tests the system's ability to handle multiple simultaneous video uploads

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
NUM_VIDEOS="${NUM_VIDEOS:-3}"  # Number of videos to upload concurrently
TEST_VIDEO_DIR="${TEST_VIDEO_DIR:-./test_videos}"
RESULTS_DIR=".concurrent_test_results"

# Helper functions
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
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

print_step() {
    echo -e "${CYAN}→ $1${NC}"
}

# Cleanup function
cleanup() {
    print_info "Cleaning up test artifacts..."
    rm -rf "$RESULTS_DIR"
}

# Setup test environment
setup_test_env() {
    print_header "Setting Up Test Environment"
    
    # Create results directory
    mkdir -p "$RESULTS_DIR"
    
    # Check if backend is running
    print_step "Checking backend status..."
    if ! curl -s "${API_BASE_URL}/health" > /dev/null 2>&1; then
        print_error "Backend is not running at ${API_BASE_URL}"
        print_info "Start the backend with: python -m src.main"
        exit 1
    fi
    print_success "Backend is running"
    
    # Check processor health
    print_step "Checking processor health..."
    PROCESSOR_STATUS=$(curl -s "${API_BASE_URL}/health/processor" | jq -r '.status')
    if [ "$PROCESSOR_STATUS" != "healthy" ]; then
        print_error "Processor is not healthy: ${PROCESSOR_STATUS}"
        exit 1
    fi
    print_success "Processor is healthy"
    
    # Create test index
    print_step "Creating test index..."
    INDEX_NAME="concurrent-test-$(date +%s)"
    INDEX_RESPONSE=$(curl -s -X POST "${API_BASE_URL}/api/indexes" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"${INDEX_NAME}\",
            \"description\": \"Concurrent upload test index\"
        }")
    
    INDEX_ID=$(echo "$INDEX_RESPONSE" | jq -r '.id')
    if [ -z "$INDEX_ID" ] || [ "$INDEX_ID" = "null" ]; then
        print_error "Failed to create test index"
        exit 1
    fi
    
    echo "$INDEX_ID" > "${RESULTS_DIR}/index_id"
    print_success "Created test index: ${INDEX_ID}"
    
    # Check for test videos
    print_step "Checking for test videos..."
    if [ ! -d "$TEST_VIDEO_DIR" ]; then
        print_info "Test video directory not found: ${TEST_VIDEO_DIR}"
        print_info "Creating directory and instructions..."
        mkdir -p "$TEST_VIDEO_DIR"
        cat > "${TEST_VIDEO_DIR}/README.txt" << EOF
Place ${NUM_VIDEOS} test video files in this directory.
Recommended: Short videos (10-30 seconds) in MP4 format.

You can use any video files for testing. Name them:
- test-video-1.mp4
- test-video-2.mp4
- test-video-3.mp4
etc.

Or use the VIDEO_FILES environment variable to specify custom paths.
EOF
        print_error "Please add test videos to ${TEST_VIDEO_DIR} and run again"
        exit 1
    fi
    
    print_success "Test environment ready"
}

# Upload a single video (runs in background)
upload_video() {
    local video_file="$1"
    local video_num="$2"
    local index_id="$3"
    local result_file="${RESULTS_DIR}/upload_${video_num}.json"
    local timing_file="${RESULTS_DIR}/timing_${video_num}.txt"
    
    local start_time=$(date +%s)
    
    # Upload video
    local response=$(curl -s -w "\n%{http_code}" -X POST "${API_BASE_URL}/api/indexes/${index_id}/videos" \
        -F "file=@${video_file}" \
        -F "title=Concurrent Test Video ${video_num}" \
        -F "description=Uploaded for concurrent testing")
    
    local http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | head -n-1)
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Save results
    echo "$body" > "$result_file"
    echo "$duration" > "$timing_file"
    echo "$http_code" > "${RESULTS_DIR}/status_${video_num}.txt"
    
    # Extract video_id and job_id
    local video_id=$(echo "$body" | jq -r '.id // empty')
    local job_id=$(echo "$body" | jq -r '.job_id // empty')
    
    if [ -n "$video_id" ]; then
        echo "$video_id" > "${RESULTS_DIR}/video_id_${video_num}.txt"
    fi
    
    if [ -n "$job_id" ]; then
        echo "$job_id" > "${RESULTS_DIR}/job_id_${video_num}.txt"
    fi
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
        print_success "Video ${video_num} uploaded (${duration}s) - Video ID: ${video_id}, Job ID: ${job_id}"
    else
        print_error "Video ${video_num} upload failed (HTTP ${http_code})"
    fi
}

# Perform concurrent uploads
concurrent_upload() {
    print_header "Performing Concurrent Uploads"
    
    local index_id=$(cat "${RESULTS_DIR}/index_id")
    
    # Find test videos
    local video_files=()
    if [ -n "$VIDEO_FILES" ]; then
        # Use custom video files from environment variable
        IFS=',' read -ra video_files <<< "$VIDEO_FILES"
    else
        # Auto-discover videos in test directory
        for i in $(seq 1 $NUM_VIDEOS); do
            local video_file="${TEST_VIDEO_DIR}/test-video-${i}.mp4"
            if [ -f "$video_file" ]; then
                video_files+=("$video_file")
            fi
        done
        
        # If not enough videos found, look for any video files
        if [ ${#video_files[@]} -lt $NUM_VIDEOS ]; then
            video_files=()
            for video_file in "${TEST_VIDEO_DIR}"/*.mp4 "${TEST_VIDEO_DIR}"/*.mov "${TEST_VIDEO_DIR}"/*.avi; do
                if [ -f "$video_file" ]; then
                    video_files+=("$video_file")
                    if [ ${#video_files[@]} -ge $NUM_VIDEOS ]; then
                        break
                    fi
                fi
            done
        fi
    fi
    
    if [ ${#video_files[@]} -lt $NUM_VIDEOS ]; then
        print_error "Not enough test videos found (need ${NUM_VIDEOS}, found ${#video_files[@]})"
        print_info "Place test videos in ${TEST_VIDEO_DIR} or set VIDEO_FILES environment variable"
        exit 1
    fi
    
    print_info "Uploading ${NUM_VIDEOS} videos concurrently..."
    print_info "Videos: ${video_files[*]}"
    
    # Record start time
    local test_start=$(date +%s)
    echo "$test_start" > "${RESULTS_DIR}/test_start_time"
    
    # Launch uploads in parallel
    local pids=()
    for i in $(seq 1 $NUM_VIDEOS); do
        local video_file="${video_files[$((i-1))]}"
        print_step "Starting upload ${i}: $(basename "$video_file")"
        upload_video "$video_file" "$i" "$index_id" &
        pids+=($!)
    done
    
    # Wait for all uploads to complete
    print_info "Waiting for all uploads to complete..."
    for pid in "${pids[@]}"; do
        wait $pid
    done
    
    local test_end=$(date +%s)
    local total_duration=$((test_end - test_start))
    echo "$total_duration" > "${RESULTS_DIR}/total_upload_time"
    
    print_success "All uploads completed in ${total_duration} seconds"
}

# Verify upload results
verify_uploads() {
    print_header "Verifying Upload Results"
    
    local success_count=0
    local failed_count=0
    local job_ids=()
    
    for i in $(seq 1 $NUM_VIDEOS); do
        local status_file="${RESULTS_DIR}/status_${i}.txt"
        local job_id_file="${RESULTS_DIR}/job_id_${i}.txt"
        
        if [ -f "$status_file" ]; then
            local status=$(cat "$status_file")
            if [ "$status" = "200" ] || [ "$status" = "201" ]; then
                success_count=$((success_count + 1))
                
                if [ -f "$job_id_file" ]; then
                    local job_id=$(cat "$job_id_file")
                    job_ids+=("$job_id")
                fi
            else
                failed_count=$((failed_count + 1))
            fi
        fi
    done
    
    print_info "Successful uploads: ${success_count}/${NUM_VIDEOS}"
    print_info "Failed uploads: ${failed_count}/${NUM_VIDEOS}"
    
    if [ $failed_count -gt 0 ]; then
        print_error "Some uploads failed"
        return 1
    fi
    
    print_success "All uploads succeeded"
    
    # Save job IDs for monitoring
    printf "%s\n" "${job_ids[@]}" > "${RESULTS_DIR}/all_job_ids.txt"
    
    return 0
}

# Check for race conditions in job store
check_race_conditions() {
    print_header "Checking for Race Conditions"
    
    local job_store_file=".kiro/data/embedding_jobs.json"
    
    if [ ! -f "$job_store_file" ]; then
        print_error "Job store file not found: ${job_store_file}"
        return 1
    fi
    
    print_step "Analyzing job store for data integrity..."
    
    # Check if all jobs are present
    local expected_jobs=$NUM_VIDEOS
    local actual_jobs=$(cat "$job_store_file" | jq 'length')
    
    print_info "Expected jobs: ${expected_jobs}"
    print_info "Actual jobs in store: ${actual_jobs}"
    
    if [ "$actual_jobs" -lt "$expected_jobs" ]; then
        print_error "Missing jobs in store (possible race condition)"
        return 1
    fi
    
    # Check for duplicate job IDs
    local job_ids_file="${RESULTS_DIR}/all_job_ids.txt"
    if [ -f "$job_ids_file" ]; then
        local unique_jobs=$(sort "$job_ids_file" | uniq | wc -l)
        local total_jobs=$(wc -l < "$job_ids_file")
        
        if [ "$unique_jobs" -ne "$total_jobs" ]; then
            print_error "Duplicate job IDs detected (possible race condition)"
            return 1
        fi
        print_success "No duplicate job IDs"
    fi
    
    # Check for corrupted JSON
    if ! jq empty "$job_store_file" 2>/dev/null; then
        print_error "Job store JSON is corrupted (possible race condition)"
        return 1
    fi
    print_success "Job store JSON is valid"
    
    # Check that all jobs have required fields
    local invalid_jobs=$(cat "$job_store_file" | jq '[.[] | select(.job_id == null or .invocation_arn == null or .video_id == null or .status == null)] | length')
    
    if [ "$invalid_jobs" -gt 0 ]; then
        print_error "Found ${invalid_jobs} jobs with missing required fields"
        return 1
    fi
    print_success "All jobs have required fields"
    
    print_success "No race conditions detected in job store"
    return 0
}

# Monitor job processing
monitor_jobs() {
    print_header "Monitoring Job Processing"
    
    local job_ids_file="${RESULTS_DIR}/all_job_ids.txt"
    if [ ! -f "$job_ids_file" ]; then
        print_error "Job IDs file not found"
        return 1
    fi
    
    local job_ids=($(cat "$job_ids_file"))
    local max_wait_time=600  # 10 minutes
    local check_interval=15  # Check every 15 seconds
    local elapsed=0
    
    print_info "Monitoring ${#job_ids[@]} jobs (max wait: ${max_wait_time}s)"
    print_info "Checking every ${check_interval} seconds..."
    
    while [ $elapsed -lt $max_wait_time ]; do
        local completed=0
        local processing=0
        local pending=0
        local failed=0
        
        for job_id in "${job_ids[@]}"; do
            local status=$(cat .kiro/data/embedding_jobs.json | jq -r ".\"${job_id}\".status // \"unknown\"")
            
            case "$status" in
                "completed")
                    completed=$((completed + 1))
                    ;;
                "processing")
                    processing=$((processing + 1))
                    ;;
                "pending")
                    pending=$((pending + 1))
                    ;;
                "failed")
                    failed=$((failed + 1))
                    ;;
            esac
        done
        
        echo -ne "\r${CYAN}Status: Completed=${completed}, Processing=${processing}, Pending=${pending}, Failed=${failed} (${elapsed}s elapsed)${NC}"
        
        # Check if all jobs are done (completed or failed)
        if [ $((completed + failed)) -eq ${#job_ids[@]} ]; then
            echo ""  # New line after status
            break
        fi
        
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
    done
    
    echo ""  # Ensure we're on a new line
    
    # Final status check
    local final_completed=0
    local final_failed=0
    
    for job_id in "${job_ids[@]}"; do
        local status=$(cat .kiro/data/embedding_jobs.json | jq -r ".\"${job_id}\".status // \"unknown\"")
        
        if [ "$status" = "completed" ]; then
            final_completed=$((final_completed + 1))
        elif [ "$status" = "failed" ]; then
            final_failed=$((final_failed + 1))
        fi
    done
    
    print_info "Final results after ${elapsed}s:"
    print_info "  Completed: ${final_completed}/${#job_ids[@]}"
    print_info "  Failed: ${final_failed}/${#job_ids[@]}"
    
    if [ $final_completed -eq ${#job_ids[@]} ]; then
        print_success "All jobs completed successfully"
        return 0
    elif [ $elapsed -ge $max_wait_time ]; then
        print_error "Timeout waiting for jobs to complete"
        return 1
    elif [ $final_failed -gt 0 ]; then
        print_error "Some jobs failed"
        return 1
    else
        print_error "Not all jobs completed"
        return 1
    fi
}

# Check for deadlocks
check_deadlocks() {
    print_header "Checking for Deadlocks"
    
    print_step "Checking processor health..."
    local processor_health=$(curl -s "${API_BASE_URL}/health/processor")
    local processor_running=$(echo "$processor_health" | jq -r '.processor_running')
    
    if [ "$processor_running" != "true" ]; then
        print_error "Processor is not running (possible deadlock)"
        return 1
    fi
    print_success "Processor is still running"
    
    # Check if processor is making progress
    print_step "Checking if processor is making progress..."
    local last_poll_time=$(echo "$processor_health" | jq -r '.last_poll_time // empty')
    
    if [ -z "$last_poll_time" ]; then
        print_error "No last poll time recorded"
        return 1
    fi
    
    # Parse timestamp and check if it's recent (within last 2 minutes)
    local current_time=$(date +%s)
    local poll_time=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${last_poll_time:0:19}" +%s 2>/dev/null || echo "0")
    local time_diff=$((current_time - poll_time))
    
    if [ $time_diff -gt 120 ]; then
        print_error "Processor hasn't polled in ${time_diff}s (possible deadlock)"
        return 1
    fi
    print_success "Processor is actively polling (last poll ${time_diff}s ago)"
    
    print_success "No deadlocks detected"
    return 0
}

# Generate test report
generate_report() {
    print_header "Test Report"
    
    local report_file="${RESULTS_DIR}/test_report.txt"
    
    {
        echo "Concurrent Upload Test Report"
        echo "=============================="
        echo ""
        echo "Test Configuration:"
        echo "  Number of videos: ${NUM_VIDEOS}"
        echo "  API URL: ${API_BASE_URL}"
        echo "  Test time: $(date)"
        echo ""
        
        if [ -f "${RESULTS_DIR}/total_upload_time" ]; then
            echo "Upload Performance:"
            echo "  Total upload time: $(cat "${RESULTS_DIR}/total_upload_time")s"
            
            local total_time=0
            for i in $(seq 1 $NUM_VIDEOS); do
                if [ -f "${RESULTS_DIR}/timing_${i}.txt" ]; then
                    local time=$(cat "${RESULTS_DIR}/timing_${i}.txt")
                    echo "    Video ${i}: ${time}s"
                    total_time=$((total_time + time))
                fi
            done
            
            local avg_time=$((total_time / NUM_VIDEOS))
            echo "  Average upload time: ${avg_time}s"
            echo ""
        fi
        
        echo "Upload Results:"
        local success=0
        local failed=0
        for i in $(seq 1 $NUM_VIDEOS); do
            if [ -f "${RESULTS_DIR}/status_${i}.txt" ]; then
                local status=$(cat "${RESULTS_DIR}/status_${i}.txt")
                if [ "$status" = "200" ] || [ "$status" = "201" ]; then
                    success=$((success + 1))
                else
                    failed=$((failed + 1))
                fi
            fi
        done
        echo "  Successful: ${success}/${NUM_VIDEOS}"
        echo "  Failed: ${failed}/${NUM_VIDEOS}"
        echo ""
        
        echo "Job Processing:"
        if [ -f ".kiro/data/embedding_jobs.json" ]; then
            local completed=$(cat .kiro/data/embedding_jobs.json | jq '[.[] | select(.status == "completed")] | length')
            local failed_jobs=$(cat .kiro/data/embedding_jobs.json | jq '[.[] | select(.status == "failed")] | length')
            local pending=$(cat .kiro/data/embedding_jobs.json | jq '[.[] | select(.status == "pending")] | length')
            local processing=$(cat .kiro/data/embedding_jobs.json | jq '[.[] | select(.status == "processing")] | length')
            
            echo "  Completed: ${completed}"
            echo "  Failed: ${failed_jobs}"
            echo "  Pending: ${pending}"
            echo "  Processing: ${processing}"
        fi
        echo ""
        
        echo "Test Results:"
        echo "  ✓ Concurrent uploads: PASS"
        echo "  ✓ Race condition check: PASS"
        echo "  ✓ Deadlock check: PASS"
        echo "  ✓ Job processing: PASS"
        echo ""
        
    } | tee "$report_file"
    
    print_success "Report saved to: ${report_file}"
}

# Main test execution
main() {
    print_header "Concurrent Upload Test"
    print_info "Testing concurrent upload of ${NUM_VIDEOS} videos"
    
    # Setup
    setup_test_env
    
    # Perform concurrent uploads
    concurrent_upload
    
    # Verify uploads
    if ! verify_uploads; then
        print_error "Upload verification failed"
        exit 1
    fi
    
    # Check for race conditions
    if ! check_race_conditions; then
        print_error "Race condition detected"
        exit 1
    fi
    
    # Monitor job processing
    if ! monitor_jobs; then
        print_error "Job processing failed"
        exit 1
    fi
    
    # Check for deadlocks
    if ! check_deadlocks; then
        print_error "Deadlock detected"
        exit 1
    fi
    
    # Generate report
    generate_report
    
    print_header "Test Complete"
    print_success "All concurrent upload tests passed!"
    print_info "Results saved in: ${RESULTS_DIR}"
    
    # Cleanup option
    read -p "Clean up test artifacts? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cleanup
        print_success "Cleanup complete"
    fi
}

# Run main function
main
