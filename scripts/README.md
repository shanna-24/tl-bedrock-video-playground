# Utility Scripts

This directory contains utility scripts for maintenance and cleanup tasks.

## cleanup_orphaned_embeddings.py

Removes orphaned embedding folders from S3 that are no longer associated with any active indexes or videos.

### When to Use

Run this script after:
- Deleting indexes
- Cleaning up old data
- Encountering orphaned embedding folders in your S3 bucket

### Usage

**Dry run (preview what would be deleted):**
```bash
PYTHONPATH=backend/src python3 scripts/cleanup_orphaned_embeddings.py --dry-run --config config.local.yaml
```

**Delete orphaned folders (with confirmation prompt):**
```bash
PYTHONPATH=backend/src python3 scripts/cleanup_orphaned_embeddings.py --config config.local.yaml
```

**Delete orphaned folders (skip confirmation):**
```bash
PYTHONPATH=backend/src python3 scripts/cleanup_orphaned_embeddings.py --config config.local.yaml --force
```

### Options

- `--dry-run` - Show what would be deleted without actually deleting
- `--config PATH` - Path to config file (default: config.local.yaml)
- `--force` - Skip confirmation prompt

### What It Does

1. Scans the S3 bucket for all folders under `embeddings/`
2. Lists each folder and counts the files inside
3. Optionally deletes all embedding folders and their contents
4. Provides a summary of deleted files

### Example Output

```
2026-02-11 14:33:05,820 - INFO - Found 5 embedding folders in S3

Embedding folders found:
  - embeddings/ajm7rgui2iws/ (1 files)
  - embeddings/l4e5zz6pjthd/ (1 files)
  - embeddings/tfrpctsk90xm/ (1 files)
  - embeddings/tsabwdq2l337/ (1 files)
  - embeddings/wnvcui1gtiy0/ (1 files)

Total: 5 folders, 5 files

Cleanup complete! Deleted 5 files from 5 folders.
```

### Safety Features

- Dry run mode to preview changes
- Confirmation prompt before deletion (unless `--force` is used)
- Detailed logging of all operations
- Graceful error handling

### Requirements

- Python 3.11+
- boto3 (AWS SDK)
- Valid AWS credentials configured
- Access to the S3 bucket specified in config

### Notes

- This script only deletes folders under the `embeddings/` prefix
- It does not affect video files, thumbnails, or transcriptions
- The script is safe to run multiple times
- Deleted files cannot be recovered (ensure you have backups if needed)
