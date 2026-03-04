#!/bin/bash
# Manual Testing Helper Script for Embedding Job Processor
# This script provides utilities to assist with manual validation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
CONFIG_FILE="${CONFIG_FILE:-config.local.yaml}"

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

# Check if backend is running
check_backend() {
    print_header "Checking Backend Status"
    
    if curl -s "${API_BASE_URL}/health" > /dev/null 2>&1; then
        print_success "Backend is running at ${API_BASE_URL}"
        
        # Get health status
        HEALTH=$(curl -s "${API_BASE_URL}/health" | jq -r '.status')
        print_info "Health status: ${HEALTH}"
        
        return 0
    else
        print_error "Backend is not running at ${API_BASE_URL}"
        print_info "Start the backend with: python -m src.main"
        return 1
    fi
}

# Check processor health
check_processor() {
    print_header "Checking Processor Health"
    
    PROCESSOR_HEALTH=$(curl -s "${API_BASE_URL}/health/processor")
    
    if [ $? -eq 0 ]; then
        STATUS=$(echo "$PROCESSOR_HEALTH" | jq -r '.status')
        RUNNING=$(echo "$PROCESSOR_HEALTH" | jq -r '.processor_running')
        PENDING=$(echo "$PROCESSOR_HEALTH" | jq -r '.pending_jobs')
        PROCESSING=$(echo "$PROCESSOR_HEALTH" | jq -r '.processing_jobs')
        COMPLETED=$(echo "$PROCESSOR_HEALTH" | jq -r '.jobs_completed')
        FAILED=$(echo "$PROCESSOR_HEALTH" | jq -r '.jobs_failed')
        EMBEDDINGS=$(echo "$PROCESSOR_HEALTH" | jq -r '.embeddings_stored')
        
        print_info "Status: ${STATUS}"
        print_info "Running: ${RUNNING}"
        print_info "Pending jobs: ${PENDING}"
        print_info "Processing jobs: ${PROCESSING}"
        print_info "Completed jobs: ${COMPLETED}"
        print_info "Failed jobs: ${FAILED}"
        print_info "Embeddings stored: ${EMBEDDINGS}"
        
        if [ "$STATUS" = "healthy" ]; then
            print_success "Processor is healthy"
        else
            print_error "Processor status: ${STATUS}"
        fi
        
        return 0
    else
        print_error "Failed to get processor health"
        return 1
    fi
}

# List indexes
list_indexes() {
    print_header "Listing Indexes"
    
    INDEXES=$(curl -s "${API_BASE_URL}/api/indexes")
    
    if [ $? -eq 0 ]; then
        echo "$INDEXES" | jq -r '.[] | "\(.id) - \(.name) (\(.video_count) videos)"'
        print_success "Found $(echo "$INDEXES" | jq '. | length') indexes"
        return 0
    else
        print_error "Failed to list indexes"
        return 1
    fi
}

# Create test index
create_test_index() {
    print_header "Creating Test Index"
    
    INDEX_NAME="manual-test-$(date +%s)"
    
    RESPONSE=$(curl -s -X POST "${API_BASE_URL}/api/indexes" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"${INDEX_NAME}\",
            \"description\": \"Test index for manual validation\"
        }")
    
    if [ $? -eq 0 ]; then
        INDEX_ID=$(echo "$RESPONSE" | jq -r '.id')
        print_success "Created index: ${INDEX_ID}"
        print_info "Index name: ${INDEX_NAME}"
        echo "$INDEX_ID" > .last_test_index_id
        return 0
    else
        print_error "Failed to create index"
        return 1
    fi
}

# Upload test video
upload_test_video() {
    print_header "Uploading Test Video"
    
    if [ -z "$1" ]; then
        print_error "Usage: $0 upload <video_file> [index_id]"
        return 1
    fi
    
    VIDEO_FILE="$1"
    INDEX_ID="${2:-$(cat .last_test_index_id 2>/dev/null)}"
    
    if [ -z "$INDEX_ID" ]; then
        print_error "No index ID provided and no cached index found"
        print_info "Create an index first or provide index_id as second argument"
        return 1
    fi
    
    if [ ! -f "$VIDEO_FILE" ]; then
        print_error "Video file not found: ${VIDEO_FILE}"
        return 1
    fi
    
    print_info "Uploading ${VIDEO_FILE} to index ${INDEX_ID}..."
    
    RESPONSE=$(curl -s -X POST "${API_BASE_URL}/api/indexes/${INDEX_ID}/videos" \
        -F "file=@${VIDEO_FILE}" \
        -F "title=Manual Test Video" \
        -F "description=Uploaded for manual validation")
    
    if [ $? -eq 0 ]; then
        VIDEO_ID=$(echo "$RESPONSE" | jq -r '.id')
        JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id // empty')
        
        print_success "Video uploaded successfully"
        print_info "Video ID: ${VIDEO_ID}"
        
        if [ -n "$JOB_ID" ]; then
            print_info "Job ID: ${JOB_ID}"
            echo "$JOB_ID" > .last_test_job_id
        fi
        
        echo "$VIDEO_ID" > .last_test_video_id
        return 0
    else
        print_error "Failed to upload video"
        return 1
    fi
}

# Check job status
check_job_status() {
    print_header "Checking Job Status"
    
    JOB_ID="${1:-$(cat .last_test_job_id 2>/dev/null)}"
    
    if [ -z "$JOB_ID" ]; then
        print_error "No job ID provided and no cached job found"
        return 1
    fi
    
    # Read job store file
    JOB_STORE_FILE=".kiro/data/embedding_jobs.json"
    
    if [ ! -f "$JOB_STORE_FILE" ]; then
        print_error "Job store file not found: ${JOB_STORE_FILE}"
        return 1
    fi
    
    JOB=$(cat "$JOB_STORE_FILE" | jq -r ".\"${JOB_ID}\"")
    
    if [ "$JOB" = "null" ]; then
        print_error "Job not found: ${JOB_ID}"
        return 1
    fi
    
    STATUS=$(echo "$JOB" | jq -r '.status')
    VIDEO_ID=$(echo "$JOB" | jq -r '.video_id')
    RETRY_COUNT=$(echo "$JOB" | jq -r '.retry_count')
    ERROR_MSG=$(echo "$JOB" | jq -r '.error_message // "none"')
    CREATED_AT=$(echo "$JOB" | jq -r '.created_at')
    UPDATED_AT=$(echo "$JOB" | jq -r '.updated_at')
    
    print_info "Job ID: ${JOB_ID}"
    print_info "Status: ${STATUS}"
    print_info "Video ID: ${VIDEO_ID}"
    print_info "Retry count: ${RETRY_COUNT}"
    print_info "Error: ${ERROR_MSG}"
    print_info "Created: ${CREATED_AT}"
    print_info "Updated: ${UPDATED_AT}"
    
    case "$STATUS" in
        "completed")
            print_success "Job completed successfully"
            ;;
        "failed")
            print_error "Job failed permanently"
            ;;
        "processing")
            print_info "Job is currently processing..."
            ;;
        "pending")
            print_info "Job is pending..."
            ;;
        *)
            print_info "Job status: ${STATUS}"
            ;;
    esac
    
    return 0
}

# Watch job progress
watch_job() {
    print_header "Watching Job Progress"
    
    JOB_ID="${1:-$(cat .last_test_job_id 2>/dev/null)}"
    
    if [ -z "$JOB_ID" ]; then
        print_error "No job ID provided and no cached job found"
        return 1
    fi
    
    print_info "Watching job ${JOB_ID} (press Ctrl+C to stop)..."
    print_info "Checking every 10 seconds..."
    
    while true; do
        check_job_status "$JOB_ID"
        
        # Check if job is completed or failed
        JOB_STORE_FILE=".kiro/data/embedding_jobs.json"
        STATUS=$(cat "$JOB_STORE_FILE" | jq -r ".\"${JOB_ID}\".status")
        
        if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
            break
        fi
        
        sleep 10
    done
    
    print_success "Job finished with status: ${STATUS}"
}

# Test search
test_search() {
    print_header "Testing Search"
    
    INDEX_ID="${1:-$(cat .last_test_index_id 2>/dev/null)}"
    QUERY="${2:-what do you see in the video}"
    
    if [ -z "$INDEX_ID" ]; then
        print_error "No index ID provided and no cached index found"
        return 1
    fi
    
    print_info "Searching index ${INDEX_ID} for: ${QUERY}"
    
    RESPONSE=$(curl -s -X POST "${API_BASE_URL}/api/search" \
        -H "Content-Type: application/json" \
        -d "{
            \"index_id\": \"${INDEX_ID}\",
            \"query\": \"${QUERY}\",
            \"limit\": 5
        }")
    
    if [ $? -eq 0 ]; then
        RESULT_COUNT=$(echo "$RESPONSE" | jq '.results | length')
        
        if [ "$RESULT_COUNT" -gt 0 ]; then
            print_success "Found ${RESULT_COUNT} results"
            echo "$RESPONSE" | jq -r '.results[] | "Video: \(.video_id) | Score: \(.score) | Time: \(.start_sec)-\(.end_sec)s"'
        else
            print_error "No results found"
            print_info "This might mean embeddings are not yet stored or query is not relevant"
        fi
        
        return 0
    else
        print_error "Search failed"
        return 1
    fi
}

# View logs
view_logs() {
    print_header "Viewing Recent Logs"
    
    print_info "Showing last 50 log entries related to jobs..."
    
    if [ -f "logs/app.log" ]; then
        tail -n 50 logs/app.log | grep -E "job_id|event_type" || echo "No job-related logs found"
    else
        print_error "Log file not found: logs/app.log"
        print_info "Logs might be in a different location or not configured"
    fi
}

# Show usage
show_usage() {
    cat << EOF
Manual Testing Helper Script for Embedding Job Processor

Usage: $0 <command> [arguments]

Commands:
    check                      Check backend and processor status
    processor                  Check processor health in detail
    indexes                    List all indexes
    create-index               Create a new test index
    upload <file> [id]         Upload a test video to index
    concurrent-upload [n] [id] Upload n videos concurrently (default: 3)
    watch-concurrent           Watch concurrent job progress
    job-status [id]            Check status of a job
    watch-job [id]             Watch job progress until completion
    search [id] [query]        Test search functionality
    logs                       View recent job-related logs
    help                       Show this help message

Examples:
    # Check if everything is running
    $0 check

    # Create a test index
    $0 create-index

    # Upload a video (uses last created index)
    $0 upload /path/to/video.mp4

    # Upload 3 videos concurrently
    $0 concurrent-upload 3

    # Upload 5 videos concurrently to specific index
    $0 concurrent-upload 5 <index_id>

    # Watch concurrent job progress
    $0 watch-concurrent

    # Watch job progress
    $0 watch-job

    # Test search
    $0 search

    # View logs
    $0 logs

Environment Variables:
    API_BASE_URL        Backend API URL (default: http://localhost:8000)
    CONFIG_FILE         Config file path (default: config.local.yaml)

EOF
}

# Upload multiple videos concurrently
concurrent_upload() {
    print_header "Concurrent Upload Test"
    
    local num_videos="${1:-3}"
    local index_id="${2:-$(cat .last_test_index_id 2>/dev/null)}"
    
    if [ -z "$index_id" ]; then
        print_error "No index ID provided and no cached index found"
        print_info "Create an index first or provide index_id as second argument"
        return 1
    fi
    
    print_info "Uploading ${num_videos} videos concurrently to index ${index_id}..."
    
    # Find test videos
    local video_files=()
    for i in $(seq 1 $num_videos); do
        local video_file="test_videos/test-video-${i}.mp4"
        if [ -f "$video_file" ]; then
            video_files+=("$video_file")
        fi
    done
    
    if [ ${#video_files[@]} -lt $num_videos ]; then
        print_error "Not enough test videos found (need ${num_videos}, found ${#video_files[@]})"
        print_info "Place test videos in test_videos/ directory"
        return 1
    fi
    
    # Launch uploads in parallel
    local pids=()
    local job_ids=()
    
    for i in $(seq 1 $num_videos); do
        local video_file="${video_files[$((i-1))]}"
        print_info "Starting upload ${i}: $(basename "$video_file")"
        
        (
            RESPONSE=$(curl -s -X POST "${API_BASE_URL}/api/indexes/${index_id}/videos" \
                -F "file=@${video_file}" \
                -F "title=Concurrent Test Video ${i}" \
                -F "description=Uploaded for concurrent testing")
            
            VIDEO_ID=$(echo "$RESPONSE" | jq -r '.id')
            JOB_ID=$(echo "$RESPONSE" | jq -r '.job_id // empty')
            
            echo "$JOB_ID" > ".concurrent_job_${i}.tmp"
            
            if [ -n "$VIDEO_ID" ]; then
                print_success "Video ${i} uploaded - Video ID: ${VIDEO_ID}, Job ID: ${JOB_ID}"
            else
                print_error "Video ${i} upload failed"
            fi
        ) &
        
        pids+=($!)
    done
    
    # Wait for all uploads
    print_info "Waiting for all uploads to complete..."
    for pid in "${pids[@]}"; do
        wait $pid
    done
    
    # Collect job IDs
    for i in $(seq 1 $num_videos); do
        if [ -f ".concurrent_job_${i}.tmp" ]; then
            job_ids+=($(cat ".concurrent_job_${i}.tmp"))
            rm ".concurrent_job_${i}.tmp"
        fi
    done
    
    print_success "All uploads completed"
    print_info "Job IDs: ${job_ids[*]}"
    
    # Save job IDs for monitoring
    printf "%s\n" "${job_ids[@]}" > .concurrent_job_ids.txt
    
    print_info "Monitor jobs with: $0 watch-concurrent"
}

# Watch concurrent jobs
watch_concurrent_jobs() {
    print_header "Watching Concurrent Jobs"
    
    if [ ! -f ".concurrent_job_ids.txt" ]; then
        print_error "No concurrent job IDs found"
        print_info "Run concurrent upload first: $0 concurrent-upload"
        return 1
    fi
    
    local job_ids=($(cat .concurrent_job_ids.txt))
    print_info "Monitoring ${#job_ids[@]} jobs (press Ctrl+C to stop)..."
    
    while true; do
        local completed=0
        local processing=0
        local pending=0
        local failed=0
        
        for job_id in "${job_ids[@]}"; do
            local status=$(cat .kiro/data/embedding_jobs.json 2>/dev/null | jq -r ".\"${job_id}\".status // \"unknown\"")
            
            case "$status" in
                "completed") completed=$((completed + 1)) ;;
                "processing") processing=$((processing + 1)) ;;
                "pending") pending=$((pending + 1)) ;;
                "failed") failed=$((failed + 1)) ;;
            esac
        done
        
        echo -ne "\r${YELLOW}Status: Completed=${completed}, Processing=${processing}, Pending=${pending}, Failed=${failed}${NC}"
        
        if [ $((completed + failed)) -eq ${#job_ids[@]} ]; then
            echo ""
            break
        fi
        
        sleep 10
    done
    
    print_success "All jobs finished"
}

# Main command dispatcher
case "${1:-help}" in
    check)
        check_backend && check_processor
        ;;
    processor)
        check_processor
        ;;
    indexes)
        list_indexes
        ;;
    create-index)
        create_test_index
        ;;
    upload)
        upload_test_video "$2" "$3"
        ;;
    concurrent-upload)
        concurrent_upload "$2" "$3"
        ;;
    watch-concurrent)
        watch_concurrent_jobs
        ;;
    job-status)
        check_job_status "$2"
        ;;
    watch-job)
        watch_job "$2"
        ;;
    search)
        test_search "$2" "$3"
        ;;
    logs)
        view_logs
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        show_usage
        exit 1
        ;;
esac
