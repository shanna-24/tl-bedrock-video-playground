#!/usr/bin/env python3
"""Cleanup orphaned vectors from S3 Vectors index."""

import asyncio
import sys
import os
from collections import defaultdict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.index_manager import IndexManager
from aws.bedrock_client import BedrockClient
from aws.s3_vectors_client import S3VectorsClient
from config import Config, load_config


async def main():
    """Cleanup orphaned vectors from S3 Vectors index."""
    
    # Initialize services
    config = load_config("../../config.local.yaml")
    bedrock = BedrockClient(config)
    s3_vectors = S3VectorsClient(config)
    
    index_manager = IndexManager(
        bedrock_client=bedrock,
        s3_vectors_client=s3_vectors,
        config=config
    )
    
    # List all indexes
    print("\n=== CLEANING UP ORPHANED VECTORS ===\n")
    indexes = await index_manager.list_indexes()
    
    if not indexes:
        print("No indexes found")
        return
    
    for index in indexes:
        print(f"Index: {index.name} (ID: {index.id})")
        
        # Get list of valid video IDs from index metadata
        videos = await index_manager.list_videos_in_index(index.id)
        valid_video_ids = {video.id for video in videos}
        print(f"  Valid videos in metadata: {len(valid_video_ids)}")
        for video_id in valid_video_ids:
            print(f"    - {video_id}")
        
        # Get all vectors from S3 Vectors index
        vector_index_name = index.s3_vectors_collection_id
        
        if config.use_localstack:
            # LocalStack mock
            if vector_index_name in s3_vectors._mock_vectors:
                vectors = s3_vectors._mock_vectors[vector_index_name]
                vector_keys = [v.get("key") for v in vectors]
            else:
                vector_keys = []
        else:
            # Real AWS S3 Vectors
            vector_keys = []
            next_token = None
            
            while True:
                params = {
                    "vectorBucketName": s3_vectors.vector_bucket_name,
                    "indexName": vector_index_name,
                    "maxResults": 1000
                }
                
                if next_token:
                    params["nextToken"] = next_token
                
                response = s3_vectors.client.list_vectors(**params)
                batch = response.get("vectors", [])
                
                # AWS returns list of dicts with 'key' field
                for item in batch:
                    if isinstance(item, dict):
                        vector_keys.append(item.get("key", ""))
                    else:
                        vector_keys.append(item)
                
                next_token = response.get("nextToken")
                if not next_token:
                    break
        
        print(f"  Total vectors in S3 Vectors index: {len(vector_keys)}")
        
        # Find orphaned vectors (vectors for videos not in metadata)
        orphaned_by_video = defaultdict(list)
        
        for key in vector_keys:
            # Extract video_id (first part before colon)
            parts = key.split(":")
            if len(parts) >= 4:
                video_id = parts[0]
                if video_id not in valid_video_ids:
                    orphaned_by_video[video_id].append(key)
        
        if not orphaned_by_video:
            print(f"  ✓ No orphaned vectors found\n")
            continue
        
        print(f"\n  Found orphaned vectors for {len(orphaned_by_video)} deleted videos:")
        for video_id, keys in orphaned_by_video.items():
            print(f"    {video_id}: {len(keys)} vectors")
        
        # Ask user if they want to delete orphaned vectors
        print(f"\n  Delete these orphaned vectors? (yes/no): ", end="")
        response = input()
        
        if response.lower() != 'yes':
            print("  Skipped\n")
            continue
        
        # Delete orphaned vectors for each video
        total_deleted = 0
        for video_id in orphaned_by_video.keys():
            print(f"  Deleting vectors for {video_id}...")
            try:
                deleted_count = s3_vectors.delete_by_video_id(
                    index_name=vector_index_name,
                    video_id=video_id
                )
                print(f"    Deleted {deleted_count} vectors")
                total_deleted += deleted_count
            except Exception as e:
                print(f"    Error: {e}")
        
        print(f"\n  ✓ Cleanup complete: deleted {total_deleted} orphaned vectors\n")


if __name__ == "__main__":
    asyncio.run(main())
