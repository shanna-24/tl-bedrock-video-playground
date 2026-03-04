#!/usr/bin/env python3
"""
Cleanup script for orphaned embedding folders in S3.

This script removes embedding folders that are no longer associated with any
active indexes or videos. It's useful after deleting indexes to clean up
leftover embedding data.

Usage:
    python scripts/cleanup_orphaned_embeddings.py [--dry-run] [--config CONFIG_PATH]

Options:
    --dry-run       Show what would be deleted without actually deleting
    --config PATH   Path to config file (default: config.local.yaml)
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add backend/src to Python path
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

import boto3
from botocore.exceptions import ClientError
from config import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def list_embedding_folders(s3_client, bucket_name: str) -> list:
    """List all embedding folders in S3.
    
    Args:
        s3_client: boto3 S3 client
        bucket_name: Name of the S3 bucket
    
    Returns:
        List of embedding folder prefixes
    """
    folders = []
    paginator = s3_client.get_paginator('list_objects_v2')
    
    try:
        # List all objects under embeddings/ prefix
        pages = paginator.paginate(
            Bucket=bucket_name,
            Prefix='embeddings/',
            Delimiter='/'
        )
        
        for page in pages:
            # Get common prefixes (folders)
            for prefix in page.get('CommonPrefixes', []):
                folder = prefix['Prefix']
                folders.append(folder)
        
        logger.info(f"Found {len(folders)} embedding folders in S3")
        return folders
        
    except ClientError as e:
        logger.error(f"Failed to list embedding folders: {e}")
        return []


def count_files_in_folder(s3_client, bucket_name: str, prefix: str) -> int:
    """Count files in an S3 folder.
    
    Args:
        s3_client: boto3 S3 client
        bucket_name: Name of the S3 bucket
        prefix: Folder prefix
    
    Returns:
        Number of files in the folder
    """
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=prefix
        )
        return response.get('KeyCount', 0)
    except ClientError:
        return 0


def delete_folder(s3_client, bucket_name: str, prefix: str, dry_run: bool = False) -> int:
    """Delete all objects in an S3 folder.
    
    Args:
        s3_client: boto3 S3 client
        bucket_name: Name of the S3 bucket
        prefix: Folder prefix to delete
        dry_run: If True, only show what would be deleted
    
    Returns:
        Number of objects deleted
    """
    try:
        # List all objects in the folder
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        
        deleted_count = 0
        objects_to_delete = []
        
        for page in pages:
            for obj in page.get('Contents', []):
                objects_to_delete.append({'Key': obj['Key']})
        
        if not objects_to_delete:
            return 0
        
        if dry_run:
            logger.info(f"[DRY RUN] Would delete {len(objects_to_delete)} objects from {prefix}")
            return len(objects_to_delete)
        
        # Delete objects in batches of 1000 (S3 limit)
        for i in range(0, len(objects_to_delete), 1000):
            batch = objects_to_delete[i:i + 1000]
            s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': batch}
            )
            deleted_count += len(batch)
        
        logger.info(f"Deleted {deleted_count} objects from {prefix}")
        return deleted_count
        
    except ClientError as e:
        logger.error(f"Failed to delete folder {prefix}: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Clean up orphaned embedding folders from S3'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--config',
        default='config.local.yaml',
        help='Path to config file (default: config.local.yaml)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
        logger.info(f"Loaded configuration from {args.config}")
        logger.info(f"S3 Bucket: {config.s3_bucket_name}")
        logger.info(f"AWS Region: {config.aws_region}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return 1
    
    # Initialize S3 client
    s3_client = boto3.client('s3', region_name=config.aws_region)
    
    # List all embedding folders
    logger.info("Scanning S3 bucket for embedding folders...")
    embedding_folders = list_embedding_folders(s3_client, config.s3_bucket_name)
    
    if not embedding_folders:
        logger.info("No embedding folders found. Nothing to clean up.")
        return 0
    
    # Show what will be deleted
    logger.info("\nEmbedding folders found:")
    total_files = 0
    for folder in embedding_folders:
        file_count = count_files_in_folder(s3_client, config.s3_bucket_name, folder)
        total_files += file_count
        logger.info(f"  - {folder} ({file_count} files)")
    
    logger.info(f"\nTotal: {len(embedding_folders)} folders, {total_files} files")
    
    if args.dry_run:
        logger.info("\n[DRY RUN] No files will be deleted.")
        return 0
    
    # Confirm deletion
    if not args.force:
        print(f"\nThis will delete {len(embedding_folders)} folders ({total_files} files) from S3.")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            logger.info("Cleanup cancelled.")
            return 0
    
    # Delete folders
    logger.info("\nDeleting embedding folders...")
    total_deleted = 0
    for folder in embedding_folders:
        deleted = delete_folder(s3_client, config.s3_bucket_name, folder, dry_run=False)
        total_deleted += deleted
    
    logger.info(f"\nCleanup complete! Deleted {total_deleted} files from {len(embedding_folders)} folders.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
