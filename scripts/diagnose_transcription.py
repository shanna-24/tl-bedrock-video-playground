#!/usr/bin/env python3
"""
Diagnostic script to check transcription status for uploaded videos.

This script checks:
1. Which videos exist in the system
2. Which transcription jobs exist in AWS Transcribe
3. Which transcription files exist in S3
4. Provides recommendations for fixing missing transcriptions
"""

import sys
import os
from pathlib import Path

# Add backend/src to Python path
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

import boto3
import json
from config import load_config
from storage.metadata_store import IndexMetadataStore

def main():
    print("=" * 70)
    print("Transcription Diagnostic Tool")
    print("=" * 70)
    print()
    
    # Load config
    try:
        config = load_config("config.local.yaml")
        print(f"✓ Config loaded: region={config.aws_region}, bucket={config.s3_bucket_name}")
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return 1
    
    # Initialize clients
    try:
        s3_client = boto3.client('s3', region_name=config.aws_region)
        transcribe_client = boto3.client('transcribe', region_name=config.aws_region)
        metadata_store = IndexMetadataStore()
        print(f"✓ AWS clients initialized")
    except Exception as e:
        print(f"✗ Failed to initialize clients: {e}")
        return 1
    
    print()
    print("-" * 70)
    print("STEP 1: Checking videos in system")
    print("-" * 70)
    
    # Get all videos from metadata
    all_videos = []
    try:
        indexes = metadata_store.load_indexes()
        print(f"Found {len(indexes)} indexes")
        
        for index in indexes:
            videos_data = index.metadata.get('videos', [])
            for video_data in videos_data:
                all_videos.append({
                    'id': video_data['id'],
                    'filename': video_data['filename'],
                    'index_id': index.id,
                    'index_name': index.name,
                    's3_uri': video_data.get('s3_uri', '')
                })
        
        print(f"Found {len(all_videos)} total videos")
        
        if not all_videos:
            print("\n⚠️  No videos found in the system")
            print("   Upload some videos first before checking transcriptions")
            return 0
        
        print("\nVideos:")
        for i, video in enumerate(all_videos, 1):
            print(f"  {i}. {video['filename']} (ID: {video['id'][:8]}...)")
            print(f"     Index: {video['index_name']}")
        
    except Exception as e:
        print(f"✗ Failed to load videos: {e}")
        return 1
    
    print()
    print("-" * 70)
    print("STEP 2: Checking AWS Transcribe jobs")
    print("-" * 70)
    
    # Check transcription jobs in AWS
    transcription_jobs = {}
    try:
        # List all transcription jobs
        response = transcribe_client.list_transcription_jobs(MaxResults=100)
        jobs = response.get('TranscriptionJobSummaries', [])
        
        print(f"Found {len(jobs)} transcription jobs in AWS Transcribe")
        
        for job in jobs:
            job_name = job['TranscriptionJobName']
            # Extract video_id from job name (format: transcription-{video_id})
            if job_name.startswith('transcription-'):
                video_id = job_name.replace('transcription-', '')
                transcription_jobs[video_id] = {
                    'job_name': job_name,
                    'status': job['TranscriptionJobStatus'],
                    'created': job.get('CreationTime', 'Unknown')
                }
        
        print(f"Found {len(transcription_jobs)} transcription jobs for videos")
        
    except Exception as e:
        print(f"✗ Failed to list transcription jobs: {e}")
        return 1
    
    print()
    print("-" * 70)
    print("STEP 3: Checking transcription files in S3")
    print("-" * 70)
    
    # Check for transcription segment files in S3
    transcription_files = set()
    try:
        response = s3_client.list_objects_v2(
            Bucket=config.s3_bucket_name,
            Prefix='transcriptions/segments/'
        )
        
        for obj in response.get('Contents', []):
            key = obj['Key']
            # Extract video_id from key (format: transcriptions/segments/{video_id}.json)
            if key.endswith('.json'):
                video_id = key.split('/')[-1].replace('.json', '')
                transcription_files.add(video_id)
        
        print(f"Found {len(transcription_files)} transcription segment files in S3")
        
    except Exception as e:
        print(f"✗ Failed to list transcription files: {e}")
        return 1
    
    print()
    print("=" * 70)
    print("ANALYSIS RESULTS")
    print("=" * 70)
    print()
    
    # Analyze each video
    videos_with_transcription = 0
    videos_with_pending_jobs = 0
    videos_without_jobs = 0
    videos_with_failed_jobs = 0
    
    for video in all_videos:
        video_id = video['id']
        has_file = video_id in transcription_files
        has_job = video_id in transcription_jobs
        
        status_icon = "✓" if has_file else "✗"
        
        print(f"{status_icon} {video['filename']}")
        print(f"   Video ID: {video_id}")
        
        if has_file:
            print(f"   ✓ Transcription file exists in S3")
            videos_with_transcription += 1
        else:
            print(f"   ✗ No transcription file in S3")
        
        if has_job:
            job_info = transcription_jobs[video_id]
            status = job_info['status']
            print(f"   Transcription job: {status}")
            
            if status == 'COMPLETED':
                if not has_file:
                    print(f"   ⚠️  Job completed but file missing - processor may not have run")
                    videos_with_pending_jobs += 1
            elif status == 'IN_PROGRESS':
                print(f"   ⏳ Job still processing...")
                videos_with_pending_jobs += 1
            elif status == 'FAILED':
                print(f"   ❌ Job failed")
                videos_with_failed_jobs += 1
        else:
            print(f"   ✗ No transcription job found")
            videos_without_jobs += 1
        
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total videos: {len(all_videos)}")
    print(f"  ✓ With transcription: {videos_with_transcription}")
    print(f"  ⏳ With pending/completed jobs: {videos_with_pending_jobs}")
    print(f"  ❌ With failed jobs: {videos_with_failed_jobs}")
    print(f"  ✗ Without jobs: {videos_without_jobs}")
    print()
    
    # Recommendations
    if videos_without_jobs > 0:
        print("RECOMMENDATION:")
        print(f"  {videos_without_jobs} videos don't have transcription jobs.")
        print(f"  This means transcription wasn't started when they were uploaded.")
        print(f"  You can manually trigger transcription using:")
        print(f"    python scripts/trigger_transcription.py")
        print()
    
    if videos_with_pending_jobs > 0:
        print("RECOMMENDATION:")
        print(f"  {videos_with_pending_jobs} videos have jobs that need processing.")
        print(f"  Make sure the backend is running with the transcription processor enabled.")
        print(f"  The processor checks every 60 seconds for completed jobs.")
        print()
    
    if videos_with_failed_jobs > 0:
        print("RECOMMENDATION:")
        print(f"  {videos_with_failed_jobs} videos have failed transcription jobs.")
        print(f"  Check AWS Transcribe console for error details.")
        print(f"  Common issues: unsupported video format, no audio track, permissions.")
        print()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
