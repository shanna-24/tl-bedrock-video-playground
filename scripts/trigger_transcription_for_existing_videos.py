#!/usr/bin/env python3
"""
Manually trigger transcription for existing videos in S3.

This script is useful when:
- Videos were uploaded before transcription was implemented
- Transcription failed during upload
- You want to re-transcribe videos

It will:
1. Find all videos in S3
2. Check if they already have transcription jobs
3. Start transcription jobs for videos without them
"""

import sys
import os
from pathlib import Path

# Add backend/src to Python path
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

import boto3
from config import load_config

def main():
    print("=" * 70)
    print("Trigger Transcription for Existing Videos")
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
        print(f"✓ AWS clients initialized")
    except Exception as e:
        print(f"✗ Failed to initialize clients: {e}")
        return 1
    
    print()
    print("-" * 70)
    print("Finding videos in S3...")
    print("-" * 70)
    
    # Find all videos in S3
    videos = []
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=config.s3_bucket_name, Prefix='videos/')
        
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj['Key']
                # Skip directories
                if key.endswith('/'):
                    continue
                
                # Extract video_id from key: videos/{index_id}/{video_id}/{filename}
                parts = key.split('/')
                if len(parts) >= 4:
                    index_id = parts[1]
                    video_id = parts[2]
                    filename = parts[3]
                    
                    s3_uri = f"s3://{config.s3_bucket_name}/{key}"
                    
                    videos.append({
                        'video_id': video_id,
                        'index_id': index_id,
                        'filename': filename,
                        's3_uri': s3_uri,
                        'key': key
                    })
        
        print(f"Found {len(videos)} videos in S3")
        
        if not videos:
            print("\n⚠️  No videos found in S3")
            return 0
        
    except Exception as e:
        print(f"✗ Failed to list videos: {e}")
        return 1
    
    print()
    print("-" * 70)
    print("Checking existing transcription jobs...")
    print("-" * 70)
    
    # Get existing transcription jobs
    existing_jobs = set()
    try:
        # List transcription jobs (max 100 at a time)
        response = transcribe_client.list_transcription_jobs(MaxResults=100)
        
        for job in response.get('TranscriptionJobSummaries', []):
            job_name = job['TranscriptionJobName']
            # Extract video_id from job name: transcription-{video_id}
            if job_name.startswith('transcription-'):
                video_id = job_name.replace('transcription-', '')
                existing_jobs.add(video_id)
        
        print(f"Found {len(existing_jobs)} existing transcription jobs")
        
    except Exception as e:
        print(f"✗ Failed to list transcription jobs: {e}")
        return 1
    
    print()
    print("-" * 70)
    print("Starting transcription jobs...")
    print("-" * 70)
    
    # Start transcription for videos without jobs
    started = 0
    skipped = 0
    failed = 0
    
    for video in videos:
        video_id = video['video_id']
        filename = video['filename']
        s3_uri = video['s3_uri']
        
        # Check if job already exists
        if video_id in existing_jobs:
            print(f"⏭️  Skipping {filename} (job already exists)")
            skipped += 1
            continue
        
        # Determine media format from filename
        ext = filename.lower().split('.')[-1]
        media_format_map = {
            'mp4': 'mp4',
            'mov': 'mov',
            'avi': 'avi',
            'mkv': 'mkv',
            'webm': 'webm',
            'flv': 'flv'
        }
        media_format = media_format_map.get(ext, 'mp4')
        
        # Start transcription job
        job_name = f"transcription-{video_id}"
        
        try:
            print(f"🚀 Starting transcription for {filename}...")
            print(f"   Video ID: {video_id}")
            print(f"   S3 URI: {s3_uri}")
            
            transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={"MediaFileUri": s3_uri},
                MediaFormat=media_format,
                LanguageCode="en-US",
                OutputBucketName=config.s3_bucket_name,
                OutputKey=f"transcriptions/{job_name}.json"
            )
            
            print(f"   ✓ Job started: {job_name}")
            started += 1
            
        except Exception as e:
            error_str = str(e)
            if "ConflictException" in error_str:
                print(f"   ⏭️  Job already exists")
                skipped += 1
            else:
                print(f"   ✗ Failed: {e}")
                failed += 1
        
        print()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total videos: {len(videos)}")
    print(f"  ✓ Jobs started: {started}")
    print(f"  ⏭️  Skipped (already exists): {skipped}")
    print(f"  ✗ Failed: {failed}")
    print()
    
    if started > 0:
        print("NEXT STEPS:")
        print("  1. Transcription jobs are now processing in AWS Transcribe")
        print("  2. Make sure your backend is running with transcription processor enabled")
        print("  3. The processor will automatically retrieve completed transcriptions")
        print("  4. Check progress with: python scripts/diagnose_transcription.py")
        print()
        print("  Note: Transcription typically takes 1-2x the video duration")
        print("        (e.g., a 10-minute video takes 10-20 minutes to transcribe)")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
