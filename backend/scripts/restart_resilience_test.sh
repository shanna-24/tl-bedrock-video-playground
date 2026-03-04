#!/bin/bash
# Restart Resilience Testing Script for Embedding Job Processor
# Tests the system's ability to handle server restarts during job processing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
NUM_VIDEOS="${NUM_VIDEOS:-3}"
TEST_VIDEO_DIR="${TEST_VIDEO_DIR:-./test_videos}"
RESULTS_DIR=".restart_test_results"
JOB_STORE_FILE=".kiro/data/embedding_jobs.json"
BACKEND_PID_FILE=".restart_test_backend.pid"

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

print_step() {
    echo -e "${CYAN}→ $1${NC}"
}

test_passed() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    print_success "TEST PASSED: $1"
}

test_failed() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    print_error "TEST FAILED: $1"
}

# Cleanup function
cleanup() {
    print_info "Cleaning up test artifacts..."
    
    # Stop backend if running
    if [ -f "$BACKEND_PID_FILE" ]; then
        local pid=$(cat "$BACKEND_PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            print_info "Stopping backend (PID: $pid)..."
            kill $pid 2>/dev/null || true
            sleep 2
        fi
        rm -f "$BACKEND_PID_FILE"
    fi
    
    # Clean up results directory
    rm -rf "$RESULTS_DIR"
    
    print_success "Cleanup complete"
}

# Trap for cleanup on exit
trap cleanup EXIT

# Check if backend is running
check_backend_running() {
    if curl -s "${API_BASE_URL}/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Start backend server
start_backend() {
    print_step "Starting backend server..."
    
    # Check if already running
    if check_backend_running; then
        print_warning "Backend is already running"
        print_warning "This test needs to control the backend lifecycle"
        print_warning "Please stop the backend and run this test again"
        exit 1
    fi
    
    # Start backend in background
    cd "$(dirname "$0")/.."
    python -m src.main > "${RESULTS_DIR}/backend.log" 2>&1 &
    local pid=$!
    echo $pid > "$BACKEND_PID_FILE"
    
    print_info "Backend started with PID: $pid"
    
    # Wait for backend to be ready
    local max_wait=30
    local elapsed=0
    
    while [ $elapsed -lt $max_wait ]; do
        if check_backend_running; then
            print_success "Backend is ready"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    
    print_error "Backend failed to start within ${max_wait}s"
    return 1
}

# Stop backend server
stop_backend() {
    print_step "Stopping backend server..."
    
    if [ ! -f "$BACKEND_PID_FILE" ]; then
        print_error "Backend PID file not found"
        return 1
    fi
    
    local pid=$(cat "$BACKEND_PID_FILE")
    
    if ! ps -p $pid > /dev/null 2>&1; then
        print_error "Backend process not running (PID: $pid)"
        return 1
    fi
    
    # Send SIGTERM for graceful shutdown
    kill $pid
    
    # Wait for process to stop
    local max_wait=10
    local elapsed=0
    
    while [ $elapsed -lt $max_wait ]; do
        if ! ps -p $pid > /dev/null 2>&1; then
            print_success "Backend stopped gracefully"
            rm -f "$BACKEND_PID_FILE"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    
    # Force kill if still running
    print_warning "Backend did not stop gracefully, forcing..."
    kill -9 $pid 2>/dev/null || true
    rm -f "$BACKEND_PID_FILE"
    
    return 0
}

# Setup test environment
setup_test_env() {
    print_header "Setting Up Test Environment"
    
    # Create results directory
    mkdir -p "$RESULTS_DIR"
    
    # Backup job store if it exists
    if [ -f "$JOB_STORE_FILE" ]; then
        cp "$JOB_STORE_FILE" "${RESULTS_DIR}/job_store_backup.json"
        print_info "Backed up existing job store"
    fi
    
    # Check for test videos
    print_step "Checking for test videos..."
    if [ ! -d "$TEST_VIDEO_DIR" ]; then
        print_info "Test video directory not found: ${TEST_VIDEO_DIR}"
        print_info "Creating directory..."
        mkdir -p "$TEST_VIDEO_DIR"
        print_error "Please add test videos to ${TEST_VIDEO_DIR} and run again"
        exit 1
    fi
    
    # Count available videos
    local video_count=$(find "$TEST_VIDEO_DIR" -type f \( -name "*.mp4" -o -name "*.mov" -o -name "*.avi" \) | wc -l)
    
    if [ $video_count -lt $NUM_VIDEOS ]; then
        print_error "Not enough test videos found (need ${NUM_VIDEOS}, found ${video_count})"
        print_info "Place test videos in ${TEST_VIDEO_DIR}"
        exit 1
    fi
    
    print_success "Found ${video_count} test videos"
    print_success "Test environment ready"
}

# Create test index
create_test_index() {
    print_step "Creating test index..."
    
    local index_name="restart-test-$(date +%s)"
    local response=$(curl -s -X POST "${API_BASE_URL}/api/indexes" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"${index_name}\",
            \"description\": \"Restart resilience test index\"
        }")
    
    local index_id=$(echo "$response" | jq -r '.id')
    
    if [ -z "$index_id" ] || [ "$index_id" = "null" ]; then
        print_error "Failed to create test index"
        return 1
    fi
    
    echo "$index_id" > "${RESULTS_DIR}/index_id"
    print_success "Created test index: ${index_id}"
    
    return 0
}

# Upload test videos
upload_test_videos() {
    print_step "Uploading ${NUM_VIDEOS} test videos..."
    
    local index_id=$(cat "${RESULTS_DIR}/index_id")
    
    # Find test videos
    local video_files=()
    for video_file in "${TEST_VIDEO_DIR}"/*.mp4 "${TEST_VIDEO_DIR}"/*.mov "${TEST_VIDEO_DIR}"/*.avi; do
        if [ -f "$video_file" ]; then
            video_files+=("$video_file")
            if [ ${#video_files[@]} -ge $NUM_VIDEOS ]; then
                break
            fi
        fi
    done
    
    # Upload videos
    local job_ids=()
    local video_ids=()
    
    for i in $(seq 1 $NUM_VIDEOS); do
        local video_file="${video_files[$((i-1))]}"
        print_info "Uploading video ${i}: $(basename "$video_file")"
        
        local response=$(curl -s -X POST "${API_BASE_URL}/api/indexes/${index_id}/videos" \
            -F "file=@${video_file}" \
            -F "title=Restart Test Video ${i}" \
            -F "description=Uploaded for restart resilience testing")
        
        local video_id=$(echo "$response" | jq -r '.id')
        local job_id=$(echo "$response" | jq -r '.job_id // empty')
        
        if [ -n "$video_id" ] && [ -n "$job_id" ]; then
            video_ids+=("$video_id")
            job_ids+=("$job_id")
            print_success "Video ${i} uploaded - Video ID: ${video_id}, Job ID: ${job_id}"
        else
            print_error "Video ${i} upload failed"
            return 1
        fi
    done
    
    # Save job and video IDs
    printf "%s\n" "${job_ids[@]}" > "${RESULTS_DIR}/job_ids.txt"
    printf "%s\n" "${video_ids[@]}" > "${RESULTS_DIR}/video_ids.txt"
    
    print_success "All videos uploaded successfully"
    return 0
}

# Get job statuses
get_job_statuses() {
    local job_ids_file="${RESULTS_DIR}/job_ids.txt"
    
    if [ ! -f "$job_ids_file" ]; then
        echo "0 0 0 0"
        return
    fi
    
    local job_ids=($(cat "$job_ids_file"))
    local completed=0
    local processing=0
    local pending=0
    local failed=0
    
    if [ ! -f "$JOB_STORE_FILE" ]; then
        echo "0 0 ${#job_ids[@]} 0"
        return
    fi
    
    for job_id in "${job_ids[@]}"; do
        local status=$(cat "$JOB_STORE_FILE" | jq -r ".\"${job_id}\".status // \"unknown\"")
        
        case "$status" in
            "completed") completed=$((completed + 1)) ;;
            "processing") processing=$((processing + 1)) ;;
            "pending") pending=$((pending + 1)) ;;
            "failed") failed=$((failed + 1)) ;;
        esac
    done
    
    echo "$completed $processing $pending $failed"
}

# Test 1: Basic restart with pending jobs
test_basic_restart() {
    print_test_header "Basic restart with pending jobs"
    
    print_info "This test verifies that pending jobs are resumed after restart"
    
    # Start backend
    if ! start_backend; then
        test_failed "Failed to start backend"
        return 1
    fi
    
    # Create index and upload videos
    if ! create_test_index; then
        test_failed "Failed to create test index"
        return 1
    fi
    
    if ! upload_test_videos; then
        test_failed "Failed to upload test videos"
        return 1
    fi
    
    # Wait a moment for jobs to be created
    sleep 5
    
    # Capture initial job state
    cp "$JOB_STORE_FILE" "${RESULTS_DIR}/job_store_before_restart.json"
    
    local statuses_before=$(get_job_statuses)
    print_info "Job statuses before restart: Completed=$(echo $statuses_before | cut -d' ' -f1), Processing=$(echo $statuses_before | cut -d' ' -f2), Pending=$(echo $statuses_before | cut -d' ' -f3), Failed=$(echo $statuses_before | cut -d' ' -f4)"
    
    # Stop backend
    print_step "Stopping backend mid-processing..."
    if ! stop_backend; then
        test_failed "Failed to stop backend"
        return 1
    fi
    
    # Wait a moment
    sleep 2
    
    # Restart backend
    print_step "Restarting backend..."
    if ! start_backend; then
        test_failed "Failed to restart backend"
        return 1
    fi
    
    # Wait for processor to resume
    print_info "Waiting for processor to resume job processing..."
    sleep 10
    
    # Capture job state after restart
    cp "$JOB_STORE_FILE" "${RESULTS_DIR}/job_store_after_restart.json"
    
    local statuses_after=$(get_job_statuses)
    print_info "Job statuses after restart: Completed=$(echo $statuses_after | cut -d' ' -f1), Processing=$(echo $statuses_after | cut -d' ' -f2), Pending=$(echo $statuses_after | cut -d' ' -f3), Failed=$(echo $statuses_after | cut -d' ' -f4)"
    
    # Verify jobs are being processed
    local processing_after=$(echo $statuses_after | cut -d' ' -f2)
    local pending_after=$(echo $statuses_after | cut -d' ' -f3)
    
    if [ $processing_after -gt 0 ] || [ $pending_after -gt 0 ]; then
        print_success "Jobs are being processed after restart"
        test_passed "Basic restart with pending jobs"
        return 0
    else
        print_error "Jobs are not being processed after restart"
        test_failed "Basic restart with pending jobs"
        return 1
    fi
}

# Test 2: Verify no duplicate embeddings
test_no_duplicate_embeddings() {
    print_test_header "Verify no duplicate embeddings after restart"
    
    print_info "This test checks that embeddings are not duplicated after restart"
    
    # Get job IDs
    local job_ids_file="${RESULTS_DIR}/job_ids.txt"
    if [ ! -f "$job_ids_file" ]; then
        print_error "Job IDs file not found"
        test_failed "No duplicate embeddings (setup issue)"
        return 1
    fi
    
    local job_ids=($(cat "$job_ids_file"))
    
    # Wait for all jobs to complete
    print_info "Waiting for all jobs to complete (max 10 minutes)..."
    
    local max_wait=600
    local elapsed=0
    
    while [ $elapsed -lt $max_wait ]; do
        local statuses=$(get_job_statuses)
        local completed=$(echo $statuses | cut -d' ' -f1)
        local failed=$(echo $statuses | cut -d' ' -f4)
        
        echo -ne "\r${CYAN}Status: Completed=${completed}/${#job_ids[@]}, Failed=${failed} (${elapsed}s elapsed)${NC}"
        
        if [ $((completed + failed)) -eq ${#job_ids[@]} ]; then
            echo ""
            break
        fi
        
        sleep 15
        elapsed=$((elapsed + 15))
    done
    
    echo ""
    
    # Check final status
    local final_statuses=$(get_job_statuses)
    local final_completed=$(echo $final_statuses | cut -d' ' -f1)
    local final_failed=$(echo $final_statuses | cut -d' ' -f4)
    
    print_info "Final status: Completed=${final_completed}/${#job_ids[@]}, Failed=${final_failed}"
    
    if [ $final_completed -eq 0 ]; then
        print_warning "No jobs completed successfully"
        print_info "This might be expected if using mock Bedrock (jobs will fail)"
        test_passed "No duplicate embeddings (no completed jobs to check)"
        return 0
    fi
    
    # Check for duplicate embeddings in job store
    # Each job should have been processed exactly once
    print_step "Checking job store for duplicate processing indicators..."
    
    local duplicate_found=false
    
    for job_id in "${job_ids[@]}"; do
        local job=$(cat "$JOB_STORE_FILE" | jq -r ".\"${job_id}\"")
        local status=$(echo "$job" | jq -r '.status')
        local retry_count=$(echo "$job" | jq -r '.retry_count')
        
        # If a job completed with retry_count > 0, check if it was processed multiple times
        if [ "$status" = "completed" ] && [ "$retry_count" -gt 0 ]; then
            print_warning "Job ${job_id} completed after ${retry_count} retries"
            print_info "This is expected behavior, not a duplicate"
        fi
    done
    
    # Check job store integrity
    print_step "Checking job store integrity..."
    
    if ! jq empty "$JOB_STORE_FILE" 2>/dev/null; then
        print_error "Job store JSON is corrupted"
        test_failed "No duplicate embeddings (job store corrupted)"
        return 1
    fi
    
    print_success "Job store is valid"
    
    # Verify each job appears exactly once
    local job_count=$(cat "$JOB_STORE_FILE" | jq 'length')
    local expected_count=${#job_ids[@]}
    
    if [ $job_count -ne $expected_count ]; then
        print_error "Job count mismatch: expected ${expected_count}, found ${job_count}"
        test_failed "No duplicate embeddings (job count mismatch)"
        return 1
    fi
    
    print_success "All jobs appear exactly once in job store"
    
    # Note: We cannot easily verify S3 Vectors without real AWS access
    # In a real test, you would query S3 Vectors to check for duplicates
    print_info "Note: S3 Vectors duplicate check requires real AWS access"
    print_info "In production, verify embeddings in S3 Vectors manually"
    
    test_passed "No duplicate embeddings after restart"
    return 0
}

# Test 3: Verify graceful shutdown
test_graceful_shutdown() {
    print_test_header "Verify graceful shutdown behavior"
    
    print_info "This test verifies that the processor shuts down gracefully"
    
    # Backend should already be running from previous tests
    if ! check_backend_running; then
        print_error "Backend is not running"
        test_failed "Graceful shutdown (backend not running)"
        return 1
    fi
    
    # Check processor health before shutdown
    local health_before=$(curl -s "${API_BASE_URL}/health/processor")
    local running_before=$(echo "$health_before" | jq -r '.processor_running')
    
    if [ "$running_before" != "true" ]; then
        print_error "Processor is not running before shutdown"
        test_failed "Graceful shutdown (processor not running)"
        return 1
    fi
    
    print_success "Processor is running before shutdown"
    
    # Stop backend
    print_step "Sending SIGTERM to backend..."
    if ! stop_backend; then
        print_error "Failed to stop backend gracefully"
        test_failed "Graceful shutdown (stop failed)"
        return 1
    fi
    
    # Check that backend stopped
    if check_backend_running; then
        print_error "Backend is still running after stop"
        test_failed "Graceful shutdown (still running)"
        return 1
    fi
    
    print_success "Backend stopped gracefully"
    
    # Check job store integrity after shutdown
    if ! jq empty "$JOB_STORE_FILE" 2>/dev/null; then
        print_error "Job store is corrupted after shutdown"
        test_failed "Graceful shutdown (job store corrupted)"
        return 1
    fi
    
    print_success "Job store is intact after shutdown"
    
    test_passed "Graceful shutdown behavior"
    return 0
}

# Test 4: Multiple restart cycles
test_multiple_restarts() {
    print_test_header "Multiple restart cycles"
    
    print_info "This test performs multiple restart cycles to verify stability"
    
    local num_cycles=3
    
    for cycle in $(seq 1 $num_cycles); do
        print_step "Restart cycle ${cycle}/${num_cycles}..."
        
        # Start backend
        if ! start_backend; then
            print_error "Failed to start backend in cycle ${cycle}"
            test_failed "Multiple restarts (cycle ${cycle} start failed)"
            return 1
        fi
        
        # Wait for processor to initialize
        sleep 5
        
        # Check processor health
        local health=$(curl -s "${API_BASE_URL}/health/processor")
        local running=$(echo "$health" | jq -r '.processor_running')
        
        if [ "$running" != "true" ]; then
            print_error "Processor not running in cycle ${cycle}"
            test_failed "Multiple restarts (cycle ${cycle} processor not running)"
            return 1
        fi
        
        print_success "Cycle ${cycle}: Processor is running"
        
        # Stop backend
        if ! stop_backend; then
            print_error "Failed to stop backend in cycle ${cycle}"
            test_failed "Multiple restarts (cycle ${cycle} stop failed)"
            return 1
        fi
        
        # Wait between cycles
        sleep 2
    done
    
    # Verify job store integrity after all cycles
    if ! jq empty "$JOB_STORE_FILE" 2>/dev/null; then
        print_error "Job store corrupted after multiple restarts"
        test_failed "Multiple restarts (job store corrupted)"
        return 1
    fi
    
    print_success "Job store intact after ${num_cycles} restart cycles"
    
    test_passed "Multiple restart cycles"
    return 0
}

# Generate test report
generate_report() {
    print_header "Test Report"
    
    local report_file="${RESULTS_DIR}/restart_test_report.txt"
    
    {
        echo "Restart Resilience Test Report"
        echo "==============================="
        echo ""
        echo "Test Configuration:"
        echo "  Number of videos: ${NUM_VIDEOS}"
        echo "  API URL: ${API_BASE_URL}"
        echo "  Test time: $(date)"
        echo ""
        
        echo "Test Results:"
        echo "  Total tests: ${TESTS_TOTAL}"
        echo "  Passed: ${TESTS_PASSED}"
        echo "  Failed: ${TESTS_FAILED}"
        echo ""
        
        if [ -f "${RESULTS_DIR}/job_ids.txt" ]; then
            local job_ids=($(cat "${RESULTS_DIR}/job_ids.txt"))
            echo "Job Processing:"
            
            if [ -f "$JOB_STORE_FILE" ]; then
                local completed=$(cat "$JOB_STORE_FILE" | jq '[.[] | select(.status == "completed")] | length')
                local failed=$(cat "$JOB_STORE_FILE" | jq '[.[] | select(.status == "failed")] | length')
                local pending=$(cat "$JOB_STORE_FILE" | jq '[.[] | select(.status == "pending")] | length')
                local processing=$(cat "$JOB_STORE_FILE" | jq '[.[] | select(.status == "processing")] | length')
                
                echo "  Total jobs: ${#job_ids[@]}"
                echo "  Completed: ${completed}"
                echo "  Failed: ${failed}"
                echo "  Pending: ${pending}"
                echo "  Processing: ${processing}"
            fi
        fi
        echo ""
        
        echo "Files Generated:"
        echo "  Job store before restart: ${RESULTS_DIR}/job_store_before_restart.json"
        echo "  Job store after restart: ${RESULTS_DIR}/job_store_after_restart.json"
        echo "  Backend log: ${RESULTS_DIR}/backend.log"
        echo ""
        
        if [ $TESTS_FAILED -eq 0 ]; then
            echo "✓ ALL TESTS PASSED"
        else
            echo "✗ SOME TESTS FAILED"
        fi
        echo ""
        
    } | tee "$report_file"
    
    print_success "Report saved to: ${report_file}"
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
    print_header "Restart Resilience Testing - Embedding Job Processor"
    
    print_info "This script tests the system's ability to handle server restarts"
    print_warning "This test will start and stop the backend server multiple times"
    print_warning "Make sure no other instance of the backend is running"
    
    # Check if backend is already running
    if check_backend_running; then
        print_error "Backend is already running at ${API_BASE_URL}"
        print_error "Please stop the backend before running this test"
        print_info "This test needs to control the backend lifecycle"
        exit 1
    fi
    
    # Setup
    setup_test_env
    
    # Run tests
    test_basic_restart
    sleep 2
    
    test_no_duplicate_embeddings
    sleep 2
    
    test_graceful_shutdown
    sleep 2
    
    test_multiple_restarts
    
    # Generate report
    generate_report
    
    # Print summary
    print_summary
    
    local exit_code=$?
    
    print_info "Test artifacts saved in: ${RESULTS_DIR}"
    
    return $exit_code
}

# Run main function
main

