#!/usr/bin/env python3
"""
Utility script to identify and clean up orphaned transcription files.

Orphaned transcription files are files in S3 that don't correspond to any
existing video in the system. This can happen if:
1. Video deletion failed partway through
2. Transcription files were created but video was never added to index
3. Manual deletion of videos without proper cleanup

Usage:
    cd backend
    source venv/bin/activate  # or: source .venv/bin/activate
    python cleanup_orphaned_transcriptions.py
"""

import sys
import os
import asyncio
from typing import Set

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from services.index_manager import IndexManager
    from storage.metadata_store import IndexMetadataStore
    from aws.s3_client import S3Client
    from aws.s3_vectors_client import S3VectorsClient
    from aws.bedrock_client import BedrockClient
    from config import load_config
except ModuleNotFoundError as e:
    print("Error: Required modules not found.")
    print("\nMake sure you:")
    print("  1. Are in the backend directory: cd backend")
    print("  2. Have activated the virtual environment:")
    print("     - source venv/bin/activate")
    print("     - OR: source .venv/bin/activate")
    print("  3. Have installed dependencies: pip install -r requirements.txt")
    print(f"\nOriginal error: {e}")
    sys.exit(1)


async def get_all_video_ids(index_manager: IndexManager) -> Set[str]:
    """Get all video IDs from all indexes."""
    video_ids = set()
    
    indexes = await index_manager.list_indexes()
    print(f"Found {len(indexes)} indexes")
    
    for index in indexes:
        videos = await index_manager.list_videos_in_index(index.id)
        print(f"  Index '{index.name}': {len(videos)} videos")
        for video in videos:
            video_ids.add(video.id)
            print(f"    - {video.id}")
    
    return video_ids


def get_transcription_video_ids(s3_client: S3Client) -> Set[str]:
    """Get all video IDs that have transcription files in S3."""
    video_ids = set()
    
    print("\nScanning S3 transcriptions folder...")
    
    # List all objects in transcriptions/ prefix
    try:
        paginator = s3_client.client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=s3_client.bucket_name,
            Prefix='transcriptions/'
        )
        
        file_count = 0
        for page in pages:
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                key = obj['Key']
                file_count += 1
                
                # Extract video_id from different transcription file patterns:
                # - transcriptions/segments/{video_id}.json
                # - transcriptions/transcription-{video_id}.json
                # - transcriptions/transcription-{video_id}.vtt
                # - transcriptions/transcription-{video_id}.srt
                
                if key.startswith('transcriptions/segments/'):
                    # Format: transcriptions/segments/{video_id}.json
                    filename = key.split('/')[-1]
                    video_id = filename.replace('.json', '')
                    video_ids.add(video_id)
                    print(f"  Found segment file: {key} -> video_id: {video_id}")
                    
                elif key.startswith('transcriptions/transcription-'):
                    # Format: transcriptions/transcription-{video_id}.{ext}
                    filename = key.split('/')[-1]
                    # Remove 'transcription-' prefix and extension
                    video_id = filename.replace('transcription-', '').split('.')[0]
                    video_ids.add(video_id)
                    print(f"  Found transcription file: {key} -> video_id: {video_id}")
        
        print(f"\nTotal transcription files: {file_count}")
        print(f"Unique video IDs with transcriptions: {len(video_ids)}")
        
    except Exception as e:
        print(f"Error scanning S3: {e}")
        raise
    
    return video_ids


def find_orphaned_files(s3_client: S3Client, orphaned_video_ids: Set[str]) -> list:
    """Find all S3 keys for orphaned video IDs."""
    orphaned_files = []
    
    try:
        paginator = s3_client.client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=s3_client.bucket_name,
            Prefix='transcriptions/'
        )
        
        for page in pages:
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                key = obj['Key']
                
                # Check if this file belongs to an orphaned video
                for video_id in orphaned_video_ids:
                    if f'/{video_id}.' in key or f'-{video_id}.' in key:
                        orphaned_files.append({
                            'key': key,
                            'size': obj['Size'],
                            'video_id': video_id
                        })
                        break
        
    except Exception as e:
        print(f"Error finding orphaned files: {e}")
        raise
    
    return orphaned_files


async def main():
    """Main execution function."""
    print("=" * 80)
    print("ORPHANED TRANSCRIPTION FILE CLEANUP UTILITY")
    print("=" * 80)
    
    # Load configuration
    config = load_config("../config.local.yaml")
    
    # Initialize services
    # Use the correct path to indexes.json (in data/)
    bedrock = BedrockClient(config)
    metadata_store = IndexMetadataStore("./data/indexes.json")
    s3_vectors = S3VectorsClient(config)
    s3_client = S3Client(config)
    index_manager = IndexManager(bedrock, s3_vectors, config, metadata_store)
    
    # Step 1: Get all valid video IDs from indexes
    print("\n" + "=" * 80)
    print("STEP 1: Getting all valid video IDs from indexes")
    print("=" * 80)
    valid_video_ids = await get_all_video_ids(index_manager)
    print(f"\nTotal valid videos: {len(valid_video_ids)}")
    
    # Step 2: Get all video IDs that have transcription files
    print("\n" + "=" * 80)
    print("STEP 2: Scanning S3 for transcription files")
    print("=" * 80)
    transcription_video_ids = get_transcription_video_ids(s3_client)
    
    # Step 3: Find orphaned video IDs
    print("\n" + "=" * 80)
    print("STEP 3: Identifying orphaned transcription files")
    print("=" * 80)
    orphaned_video_ids = transcription_video_ids - valid_video_ids
    
    if not orphaned_video_ids:
        print("\n✅ No orphaned transcription files found!")
        return
    
    print(f"\n⚠️  Found {len(orphaned_video_ids)} orphaned video IDs:")
    for video_id in sorted(orphaned_video_ids):
        print(f"  - {video_id}")
    
    # Step 4: Find all files for orphaned videos
    print("\n" + "=" * 80)
    print("STEP 4: Finding all orphaned files")
    print("=" * 80)
    orphaned_files = find_orphaned_files(s3_client, orphaned_video_ids)
    
    if not orphaned_files:
        print("\n✅ No orphaned files to clean up")
        return
    
    print(f"\nFound {len(orphaned_files)} orphaned files:")
    total_size = 0
    for file_info in orphaned_files:
        size_kb = file_info['size'] / 1024
        total_size += file_info['size']
        print(f"  - {file_info['key']} ({size_kb:.2f} KB) [video: {file_info['video_id']}]")
    
    print(f"\nTotal size: {total_size / 1024:.2f} KB ({total_size / (1024*1024):.2f} MB)")
    
    # Step 5: Prompt for deletion
    print("\n" + "=" * 80)
    print("STEP 5: Cleanup confirmation")
    print("=" * 80)
    response = input("\nDo you want to delete these orphaned files? (yes/no): ")
    
    if response.lower() != 'yes':
        print("\n❌ Cleanup cancelled")
        return
    
    # Step 6: Delete orphaned files
    print("\n" + "=" * 80)
    print("STEP 6: Deleting orphaned files")
    print("=" * 80)
    deleted_count = 0
    failed_count = 0
    
    for file_info in orphaned_files:
        try:
            s3_client.delete(file_info['key'])
            deleted_count += 1
            print(f"  ✓ Deleted: {file_info['key']}")
        except Exception as e:
            failed_count += 1
            print(f"  ✗ Failed to delete {file_info['key']}: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("CLEANUP SUMMARY")
    print("=" * 80)
    print(f"Successfully deleted: {deleted_count} files")
    print(f"Failed: {failed_count} files")
    print(f"Total size freed: {total_size / 1024:.2f} KB ({total_size / (1024*1024):.2f} MB)")
    
    if failed_count == 0:
        print("\n✅ Cleanup completed successfully!")
    else:
        print(f"\n⚠️  Cleanup completed with {failed_count} errors")


if __name__ == "__main__":
    asyncio.run(main())
