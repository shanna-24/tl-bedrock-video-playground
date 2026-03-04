#!/usr/bin/env python3
"""Debug script to test video deletion and identify the bug."""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.index_manager import IndexManager
from services.embedding_job_store import EmbeddingJobStore
from aws.bedrock_client import BedrockClient
from aws.s3_vectors_client import S3VectorsClient
from aws.s3_client import S3Client
from config import Config


async def main():
    """Test video deletion to identify the bug."""
    
    # Initialize services
    config = Config(_env_file='../.env', _env_file_encoding='utf-8')
    bedrock = BedrockClient(config)
    s3_vectors = S3VectorsClient(config)
    s3_client = S3Client(config)
    job_store = EmbeddingJobStore()
    
    index_manager = IndexManager(
        bedrock_client=bedrock,
        s3_vectors_client=s3_vectors,
        config=config,
        embedding_job_store=job_store
    )
    
    # List all indexes
    print("\n=== INDEXES ===")
    indexes = await index_manager.list_indexes()
    for idx in indexes:
        print(f"Index: {idx.id} - {idx.name} ({idx.video_count} videos)")
    
    if not indexes:
        print("No indexes found")
        return
    
    # List videos in first index
    first_index = indexes[0]
    print(f"\n=== VIDEOS IN INDEX {first_index.name} ===")
    videos = await index_manager.list_videos_in_index(first_index.id)
    for video in videos:
        print(f"Video: {video.id} - {video.filename}")
        print(f"  S3 URI: {video.s3_uri}")
    
    if len(videos) < 2:
        print(f"\nNeed at least 2 videos to test deletion. Found {len(videos)}")
        return
    
    # Get all embedding jobs
    print(f"\n=== EMBEDDING JOBS ===")
    all_jobs = job_store.get_all_jobs()
    print(f"Total jobs: {len(all_jobs)}")
    for job in all_jobs:
        print(f"Job: {job.job_id}")
        print(f"  Video ID: {job.video_id}")
        print(f"  Index ID: {job.index_id}")
        print(f"  Output Location: {job.output_location}")
    
    # Check S3 bucket contents BEFORE deletion
    print(f"\n=== S3 BUCKET CONTENTS BEFORE DELETION ===")
    try:
        response = s3_client.client.list_objects_v2(
            Bucket=s3_client.bucket_name,
            MaxKeys=100
        )
        if 'Contents' in response:
            print(f"Total objects: {len(response['Contents'])}")
            for obj in response['Contents'][:20]:  # Show first 20
                print(f"  {obj['Key']}")
            if len(response['Contents']) > 20:
                print(f"  ... and {len(response['Contents']) - 20} more")
        else:
            print("No objects in bucket")
    except Exception as e:
        print(f"Error listing S3 objects: {e}")
    
    # Simulate deletion of first video
    video_to_delete = videos[0]
    print(f"\n=== SIMULATING DELETION OF VIDEO {video_to_delete.id} ===")
    print(f"Video filename: {video_to_delete.filename}")
    
    # Show what would be deleted
    print(f"\nVideo prefix: videos/{first_index.id}/{video_to_delete.id}/")
    print(f"Thumbnail prefix: thumbnails/{first_index.id}/{video_to_delete.id}/")
    
    # Show embedding jobs for this video
    video_jobs = [job for job in all_jobs if job.video_id == video_to_delete.id]
    print(f"\nEmbedding jobs for this video: {len(video_jobs)}")
    for job in video_jobs:
        if job.output_location:
            output_key = job.output_location.replace(f"s3://{s3_client.bucket_name}/", "")
            folder_path = "/".join(output_key.split("/")[:-1]) + "/"
            print(f"  Would delete embedding folder: {folder_path}")
    
    # Ask user if they want to proceed
    print(f"\n=== READY TO DELETE ===")
    response = input(f"Delete video {video_to_delete.filename}? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Aborted")
        return
    
    # Perform deletion
    print(f"\nDeleting video {video_to_delete.id}...")
    try:
        await index_manager.delete_video(video_to_delete.id, s3_client=s3_client)
        print("Deletion completed")
    except Exception as e:
        print(f"Deletion failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Check S3 bucket contents AFTER deletion
    print(f"\n=== S3 BUCKET CONTENTS AFTER DELETION ===")
    try:
        response = s3_client.client.list_objects_v2(
            Bucket=s3_client.bucket_name,
            MaxKeys=100
        )
        if 'Contents' in response:
            print(f"Total objects: {len(response['Contents'])}")
            for obj in response['Contents'][:20]:  # Show first 20
                print(f"  {obj['Key']}")
            if len(response['Contents']) > 20:
                print(f"  ... and {len(response['Contents']) - 20} more")
        else:
            print("No objects in bucket")
    except Exception as e:
        print(f"Error listing S3 objects: {e}")
    
    # Check remaining videos
    print(f"\n=== REMAINING VIDEOS ===")
    remaining_videos = await index_manager.list_videos_in_index(first_index.id)
    print(f"Videos remaining: {len(remaining_videos)}")
    for video in remaining_videos:
        print(f"  {video.id} - {video.filename}")


if __name__ == "__main__":
    asyncio.run(main())
