# Backend Scripts

This directory contains utility scripts for testing, deployment, and maintenance.

## Manual Testing Helper

The `manual_test_helper.sh` script provides utilities to assist with manual validation of the embedding job processor.

### Prerequisites

- Backend server running (`python -m src.main`)
- `jq` installed for JSON parsing (`brew install jq` on macOS)
- `curl` available (pre-installed on most systems)
- AWS CLI configured (for S3 Vectors verification)

### Quick Start

```bash
# Make script executable (if not already)
chmod +x scripts/manual_test_helper.sh

# Check backend and processor status
./scripts/manual_test_helper.sh check

# Create a test index
./scripts/manual_test_helper.sh create-index

# Upload a test video
./scripts/manual_test_helper.sh upload /path/to/video.mp4

# Watch job progress until completion
./scripts/manual_test_helper.sh watch-job

# Test search functionality
./scripts/manual_test_helper.sh search
```

### Available Commands

#### `check`
Check if backend is running and processor is healthy.

```bash
./scripts/manual_test_helper.sh check
```

#### `processor`
Get detailed processor health information including metrics.

```bash
./scripts/manual_test_helper.sh processor
```

#### `indexes`
List all video indexes.

```bash
./scripts/manual_test_helper.sh indexes
```

#### `create-index`
Create a new test index. The index ID is cached for subsequent commands.

```bash
./scripts/manual_test_helper.sh create-index
```

#### `upload <file> [index_id]`
Upload a test video to an index. If index_id is not provided, uses the last created index.

```bash
# Upload to last created index
./scripts/manual_test_helper.sh upload test-video.mp4

# Upload to specific index
./scripts/manual_test_helper.sh upload test-video.mp4 abc-123
```

#### `job-status [job_id]`
Check the status of a job. If job_id is not provided, uses the last created job.

```bash
# Check last job
./scripts/manual_test_helper.sh job-status

# Check specific job
./scripts/manual_test_helper.sh job-status abc-123
```

#### `watch-job [job_id]`
Watch job progress in real-time until completion. Checks status every 10 seconds.

```bash
# Watch last job
./scripts/manual_test_helper.sh watch-job

# Watch specific job
./scripts/manual_test_helper.sh watch-job abc-123
```

#### `search [index_id] [query]`
Test search functionality. If parameters are not provided, uses defaults.

```bash
# Search last index with default query
./scripts/manual_test_helper.sh search

# Search specific index with custom query
./scripts/manual_test_helper.sh search abc-123 "people walking"
```

#### `logs`
View recent job-related logs.

```bash
./scripts/manual_test_helper.sh logs
```

#### `help`
Show usage information.

```bash
./scripts/manual_test_helper.sh help
```

### Environment Variables

The script supports the following environment variables:

- `API_BASE_URL`: Backend API URL (default: `http://localhost:8000`)
- `CONFIG_FILE`: Config file path (default: `config.local.yaml`)

Example:

```bash
API_BASE_URL=http://localhost:8080 ./scripts/manual_test_helper.sh check
```

### Cached State

The script caches IDs in hidden files for convenience:

- `.last_test_index_id`: Last created index ID
- `.last_test_video_id`: Last uploaded video ID
- `.last_test_job_id`: Last created job ID

These files are created in the current working directory and allow you to run commands without specifying IDs repeatedly.

### Example Workflow

Complete manual testing workflow:

```bash
# 1. Check system status
./scripts/manual_test_helper.sh check

# 2. Create test index
./scripts/manual_test_helper.sh create-index

# 3. Upload test video
./scripts/manual_test_helper.sh upload ~/Videos/test-video.mp4

# 4. Watch job progress (will exit when complete)
./scripts/manual_test_helper.sh watch-job

# 5. Test search
./scripts/manual_test_helper.sh search

# 6. Check processor metrics
./scripts/manual_test_helper.sh processor

# 7. View logs
./scripts/manual_test_helper.sh logs
```

### Troubleshooting

#### "Backend is not running"
- Ensure backend server is started: `python -m src.main`
- Check if port 8000 is available
- Verify `API_BASE_URL` environment variable if using custom port

#### "jq: command not found"
- Install jq: `brew install jq` (macOS) or `apt-get install jq` (Linux)

#### "Job store file not found"
- Ensure backend has been started at least once
- Check that `.kiro/data/` directory exists
- Verify file path in error message

#### "No results found" in search
- Wait for job to complete (check with `watch-job`)
- Verify embeddings are stored (check logs)
- Try different search queries
- Check S3 Vectors with AWS CLI

### Related Documentation

- [Manual Testing Guide](../MANUAL_TESTING_GUIDE.md): Comprehensive testing scenarios
- [Manual Test Checklist](../MANUAL_TEST_CHECKLIST.md): Quick reference checklist
- [Configuration Guide](../CONFIG.md): Configuration options
- [Structured Logging Guide](../STRUCTURED_LOGGING.md): Log format and queries

## Other Scripts

(Add documentation for other scripts as they are created)
