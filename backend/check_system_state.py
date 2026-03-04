#!/usr/bin/env python3
"""Check complete system state - metadata, S3, and vectors."""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.index_manager import IndexManager
from aws.bedrock_client import BedrockClient
from aws.s3_vectors_client import S3VectorsClient
from aws.s3_client import S3Client
from config import Config, load_config


async def main():
    """Check complete system state."""
    
    # Initialize services
    config = load_config("../../config.local.yaml")
    bedrock = BedrockClient(config)
    s3_vectors = S3VectorsClient(config)
    s3_client = S3Client(config)
    
    index_manager = IndexManager(
        bedrock_client=bedrock,
        s3_vectors_client=s3_vectors,
        config=config
    )
    
    print("\n=== SYSTEM STATE CHECK ===\n")
    
    # Check indexes
    indexes = await index_manager.list_indexes()
    print(f"Indexes in metadata: {len(indexes)}")
    
    for index in indexes:
        print(f"\n--- Index: {index.name} (ID: {index.id}) ---")
        print(f"Video count (metadata): {index.video_count}")
        
        # Check videos in metadata
        videos = await index_manager.list_videos_in_index(index.id)
        print(f"\nVideos in metadata: {len(videos)}")
        for video in videos:
            print(f"  - {video.id}")
            print(f"    Filename: {video.filename}")
            print(f"    S3 URI: {video.s3_uri}")
            print(f"    Duration: {video.duration}s")
        
        # Check S3 bucket for this index
        print(f"\nS3 Bucket Contents for index {index.id}:")
        
        # Check videos folder
        try:
            video_prefix = f"videos/{index.id}/"
            response = s3_client.client.list_objects_v2(
                Bucket=s3_client.bucket_name,
                Prefix=video_prefix
            )
            video_objects = response.get('Contents', [])
            print(f"  Videos folder ({video_prefix}): {len(video_objects)} objects")
            for obj in video_objects[:5]:
                print(f"    - {obj['Key']}")
            if len(video_objects) > 5:
                print(f"    ... and {len(video_objects) - 5} more")
        except Exception as e:
            print(f"  Videos folder: Error - {e}")
        
        # Check thumbnails folder
        try:
            thumbnail_prefix = f"thumbnails/{index.id}/"
            response = s3_client.client.list_objects_v2(
                Bucket=s3_client.bucket_name,
                Prefix=thumbnail_prefix
            )
            thumbnail_objects = response.get('Contents', [])
            print(f"  Thumbnails folder ({thumbnail_prefix}): {len(thumbnail_objects)} objects")
            for obj in thumbnail_objects[:5]:
                print(f"    - {obj['Key']}")
            if len(thumbnail_objects) > 5:
                print(f"    ... and {len(thumbnail_objects) - 5} more")
        except Exception as e:
            print(f"  Thumbnails folder: Error - {e}")
        
        # Check embeddings folder
        try:
            embeddings_prefix = "embeddings/"
            response = s3_client.client.list_objects_v2(
                Bucket=s3_client.bucket_name,
                Prefix=embeddings_prefix
            )
            embedding_objects = response.get('Contents', [])
            print(f"  Embeddings folder ({embeddings_prefix}): {len(embedding_objects)} objects")
            for obj in embedding_objects[:5]:
                print(f"    - {obj['Key']}")
            if len(embedding_objects) > 5:
                print(f"    ... and {len(embedding_objects) - 5} more")
        except Exception as e:
            print(f"  Embeddings folder: Error - {e}")
        
        # Check S3 Vectors
        vector_index_name = index.s3_vectors_collection_id
        if config.use_localstack:
            if vector_index_name in s3_vectors._mock_vectors:
                vector_count = len(s3_vectors._mock_vectors[vector_index_name])
            else:
                vector_count = 0
        else:
            vector_count = 0
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
                vector_count += len(response.get("vectors", []))
                next_token = response.get("nextToken")
                if not next_token:
                    break
        
        print(f"\nS3 Vectors index ({vector_index_name}): {vector_count} vectors")
    
    # Check entire S3 bucket
    print(f"\n--- Complete S3 Bucket Contents ---")
    try:
        response = s3_client.client.list_objects_v2(
            Bucket=s3_client.bucket_name,
            MaxKeys=1000
        )
        all_objects = response.get('Contents', [])
        print(f"Total objects in bucket: {len(all_objects)}")
        
        if len(all_objects) == 0:
            print("  ⚠️  BUCKET IS EMPTY!")
        else:
            print("\nAll objects:")
            for obj in all_objects:
                print(f"  - {obj['Key']}")
    except Exception as e:
        print(f"Error listing bucket: {e}")
    
    print()


if __name__ == "__main__":
    asyncio.run(main())
