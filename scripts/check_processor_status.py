#!/usr/bin/env python3
"""
Check if the transcription processor is running and working correctly.
"""

import sys
import time
from pathlib import Path

# Add backend/src to Python path
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

import boto3
from config import load_config

def main():
    print("=" * 70)
    print("Transcription Processor Status Check")
    print("=" * 70)
    print()
    
    config = load_config("config.local.yaml")
    s3 = boto3.client('s3', region_name=config.aws_region)
    transcribe = boto3.client('transcribe', region_name=config.aws_region)
    
    # Check completed jobs
    response = transcribe.list_transcription_jobs(Status='COMPLETED', MaxResults=20)
    completed_jobs = response.get('TranscriptionJobSummaries', [])
    
    print(f"COMPLETED transcription jobs: {len(completed_jobs)}")
    
    # Check segment files
    response = s3.list_objects_v2(
        Bucket=config.s3_bucket_name,
        Prefix='transcriptions/segments/'
    )
    segment_files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.json')]
    
    print(f"Transcription segment files in S3: {len(segment_files)}")
    print()
    
    if len(completed_jobs) > len(segment_files):
        print(f"⚠️  {len(completed_jobs) - len(segment_files)} completed jobs haven't been processed yet")
        print(f"   The processor should pick them up within 60 seconds")
        print()
        print("Waiting 70 seconds for processor to run...")
        
        for i in range(7):
            time.sleep(10)
            print(f"  {(i+1)*10}s elapsed...")
        
        print()
        print("Checking again...")
        
        # Check again
        response = s3.list_objects_v2(
            Bucket=config.s3_bucket_name,
            Prefix='transcriptions/segments/'
        )
        new_segment_files = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].endswith('.json')]
        
        print(f"Transcription segment files in S3: {len(new_segment_files)}")
        
        if len(new_segment_files) > len(segment_files):
            print(f"✅ Processor is working! Added {len(new_segment_files) - len(segment_files)} new files")
        else:
            print(f"❌ Processor may not be running or encountering errors")
            print(f"   Check backend logs for errors")
    else:
        print("✅ All completed jobs have been processed!")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
