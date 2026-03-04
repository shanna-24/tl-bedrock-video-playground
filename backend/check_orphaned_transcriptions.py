#!/usr/bin/env python3
"""
Quick check script to identify orphaned transcription files (read-only).

Usage:
    cd backend
    source venv/bin/activate  # or: source .venv/bin/activate
    python check_orphaned_transcriptions.py
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


async def main():
    config = load_config("../config.local.yaml")
    
    # Initialize services
    # Use the correct path to indexes.json (in data/)
    bedrock = BedrockClient(config)
    metadata_store = IndexMetadataStore("./data/indexes.json")
    s3_vectors = S3VectorsClient(config)
    s3_client = S3Client(config)
    index_manager = IndexManager(bedrock, s3_vectors, config, metadata_store)
    
    # Get all valid video IDs
    valid_video_ids = set()
    indexes = await index_manager.list_indexes()
    
    print(f"Checking {len(indexes)} indexes...")
    for index in indexes:
        videos = await index_manager.list_videos_in_index(index.id)
        print(f"  {index.name}: {len(videos)} videos")
        for video in videos:
            valid_video_ids.add(video.id)
    
    print(f"\nTotal valid videos: {len(valid_video_ids)}")
    
    # Scan transcription files
    transcription_video_ids = set()
    file_count = 0
    
    print("\nScanning transcription files in S3...")
    paginator = s3_client.client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=s3_client.bucket_name, Prefix='transcriptions/')
    
    for page in pages:
        if 'Contents' not in page:
            continue
        
        for obj in page['Contents']:
            key = obj['Key']
            file_count += 1
            
            if key.startswith('transcriptions/segments/'):
                video_id = key.split('/')[-1].replace('.json', '')
                transcription_video_ids.add(video_id)
            elif key.startswith('transcriptions/transcription-'):
                filename = key.split('/')[-1]
                video_id = filename.replace('transcription-', '').split('.')[0]
                transcription_video_ids.add(video_id)
    
    print(f"Total transcription files: {file_count}")
    print(f"Unique videos with transcriptions: {len(transcription_video_ids)}")
    
    # Find orphans
    orphaned = transcription_video_ids - valid_video_ids
    
    print("\n" + "=" * 60)
    if orphaned:
        print(f"⚠️  Found {len(orphaned)} orphaned video IDs:")
        for vid in sorted(orphaned):
            print(f"  - {vid}")
        print(f"\nRun cleanup_orphaned_transcriptions.py to remove them")
    else:
        print("✅ No orphaned transcription files found!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
