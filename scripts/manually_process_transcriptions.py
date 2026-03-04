#!/usr/bin/env python3
"""
Manually process completed transcription jobs.

This script manually triggers the transcription processing that the
background processor should do automatically.
"""

import sys
from pathlib import Path

# Add backend/src to Python path
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

from config import load_config
from services.transcription_service import TranscriptionService
import boto3

def main():
    print("=" * 70)
    print("Manual Transcription Processing")
    print("=" * 70)
    print()
    
    # Load config
    config = load_config("config.local.yaml")
    transcribe_client = boto3.client('transcribe', region_name=config.aws_region)
    transcription_service = TranscriptionService(config)
    
    # Get COMPLETED jobs
    response = transcribe_client.list_transcription_jobs(
        Status='COMPLETED',
        MaxResults=100
    )
    
    jobs = response.get('TranscriptionJobSummaries', [])
    print(f"Found {len(jobs)} COMPLETED transcription jobs")
    print()
    
    # Filter for our jobs
    our_jobs = [j for j in jobs if j['TranscriptionJobName'].startswith('transcription-')]
    print(f"Found {len(our_jobs)} jobs for our videos")
    print()
    
    # Process each job
    processed = 0
    skipped = 0
    failed = 0
    
    for job in our_jobs:
        job_name = job['TranscriptionJobName']
        video_id = job_name.replace('transcription-', '')
        
        print(f"Processing: {job_name}")
        print(f"  Video ID: {video_id}")
        
        # Check if already processed
        try:
            s3_client = boto3.client('s3', region_name=config.aws_region)
            key = f"transcriptions/segments/{video_id}.json"
            s3_client.head_object(Bucket=config.s3_bucket_name, Key=key)
            print(f"  ⏭️  Already processed (segments file exists)")
            skipped += 1
            continue
        except:
            pass
        
        # Process the transcription
        try:
            segments = transcription_service.retrieve_and_store_transcription(video_id)
            print(f"  ✓ Processed {len(segments)} segments")
            processed += 1
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed += 1
        
        print()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total jobs: {len(our_jobs)}")
    print(f"  ✓ Processed: {processed}")
    print(f"  ⏭️  Skipped (already done): {skipped}")
    print(f"  ✗ Failed: {failed}")
    
    if processed > 0:
        print()
        print("✅ Transcription segments are now available in S3!")
        print("   Location: s3://{bucket}/transcriptions/segments/{video_id}.json")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
