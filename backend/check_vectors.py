#!/usr/bin/env python3
"""Check S3 Vectors index for unique video IDs."""

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
    """Check S3 Vectors index for unique video IDs."""
    
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
    print("\n=== CHECKING S3 VECTORS INDEXES ===\n")
    indexes = await index_manager.list_indexes()
    
    if not indexes:
        print("No indexes found")
        return
    
    for index in indexes:
        print(f"Index: {index.name} (ID: {index.id})")
        print(f"  S3 Vectors Collection: {index.s3_vectors_collection_id}")
        print(f"  Video Count (metadata): {index.video_count}")
        
        # List all vectors in this index
        try:
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
                    
                    # AWS returns list of dicts with 'key' field, or just strings
                    for item in batch:
                        if isinstance(item, dict):
                            vector_keys.append(item.get("key", ""))
                        else:
                            vector_keys.append(item)
                    
                    next_token = response.get("nextToken")
                    if not next_token:
                        break
            
            print(f"  Total vectors in index: {len(vector_keys)}")
            
            if len(vector_keys) > 0:
                # Parse video IDs from keys (format: video_id:start:end:idx)
                video_ids = set()
                video_vector_counts = defaultdict(int)
                
                for key in vector_keys:
                    # Extract video_id (first part before colon)
                    parts = key.split(":")
                    if len(parts) >= 4:
                        video_id = parts[0]
                        video_ids.add(video_id)
                        video_vector_counts[video_id] += 1
                
                print(f"  Unique video IDs: {len(video_ids)}")
                print(f"\n  Video ID breakdown:")
                for video_id, count in sorted(video_vector_counts.items(), key=lambda x: x[1], reverse=True):
                    print(f"    {video_id}: {count} vectors")
                
                # Show sample keys
                print(f"\n  Sample vector keys:")
                for key in vector_keys[:5]:
                    print(f"    {key}")
                
                if len(vector_keys) > 5:
                    print(f"    ... and {len(vector_keys) - 5} more")
            
            print()
            
        except Exception as e:
            print(f"  Error listing vectors: {e}")
            import traceback
            traceback.print_exc()
            print()


if __name__ == "__main__":
    asyncio.run(main())
