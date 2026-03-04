#!/usr/bin/env python3
"""
Test script to verify AWS Transcribe is working correctly.

This script tests the transcription functionality to help diagnose issues.
"""

import sys
import os
from pathlib import Path

# Add backend/src to Python path
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

import boto3
from config import load_config

def test_transcribe_permissions():
    """Test if we have permissions to use AWS Transcribe."""
    print("Testing AWS Transcribe permissions...")
    
    try:
        config = load_config("config.local.yaml")
        print(f"✓ Config loaded: region={config.aws_region}, bucket={config.s3_bucket_name}")
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return False
    
    try:
        transcribe_client = boto3.client('transcribe', region_name=config.aws_region)
        print(f"✓ Transcribe client created")
    except Exception as e:
        print(f"✗ Failed to create Transcribe client: {e}")
        return False
    
    # Test listing transcription jobs (requires transcribe:ListTranscriptionJobs)
    try:
        response = transcribe_client.list_transcription_jobs(MaxResults=1)
        print(f"✓ Can list transcription jobs")
        print(f"  Status: {response.get('Status', 'N/A')}")
    except Exception as e:
        print(f"✗ Cannot list transcription jobs: {e}")
        print(f"  This might indicate missing IAM permissions")
        return False
    
    # Check if we can access S3
    try:
        s3_client = boto3.client('s3', region_name=config.aws_region)
        response = s3_client.list_objects_v2(
            Bucket=config.s3_bucket_name,
            Prefix='videos/',
            MaxKeys=1
        )
        print(f"✓ Can access S3 bucket: {config.s3_bucket_name}")
        
        # Check if there are any videos
        if response.get('Contents'):
            print(f"  Found videos in bucket")
        else:
            print(f"  No videos found in bucket")
    except Exception as e:
        print(f"✗ Cannot access S3 bucket: {e}")
        return False
    
    return True


def test_transcribe_job_creation():
    """Test creating a transcription job with a sample video."""
    print("\nTesting transcription job creation...")
    
    try:
        config = load_config("config.local.yaml")
        transcribe_client = boto3.client('transcribe', region_name=config.aws_region)
        s3_client = boto3.client('s3', region_name=config.aws_region)
    except Exception as e:
        print(f"✗ Failed to initialize clients: {e}")
        return False
    
    # Find a video in S3
    try:
        response = s3_client.list_objects_v2(
            Bucket=config.s3_bucket_name,
            Prefix='videos/',
            MaxKeys=1
        )
        
        if not response.get('Contents'):
            print(f"✗ No videos found in S3 bucket")
            print(f"  Upload a video first before testing transcription")
            return False
        
        video_key = response['Contents'][0]['Key']
        video_s3_uri = f"s3://{config.s3_bucket_name}/{video_key}"
        print(f"✓ Found video: {video_key}")
        
        # Extract video_id from key (format: videos/{index_id}/{video_id}/{filename})
        parts = video_key.split('/')
        if len(parts) >= 3:
            video_id = parts[2]
        else:
            video_id = "test-video"
        
        job_name = f"test-transcription-{video_id}"
        
        # Try to start a transcription job
        print(f"  Attempting to start transcription job: {job_name}")
        print(f"  Video URI: {video_s3_uri}")
        
        try:
            transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={"MediaFileUri": video_s3_uri},
                MediaFormat="mp4",
                LanguageCode="en-US",
                OutputBucketName=config.s3_bucket_name,
                OutputKey=f"transcriptions/{job_name}.json"
            )
            print(f"✓ Successfully started transcription job: {job_name}")
            print(f"  Job will process in the background")
            print(f"  Check status with: aws transcribe get-transcription-job --transcription-job-name {job_name}")
            return True
            
        except Exception as e:
            error_str = str(e)
            if "ConflictException" in error_str:
                print(f"✓ Job already exists: {job_name}")
                print(f"  This is OK - checking status...")
                
                # Get job status
                try:
                    response = transcribe_client.get_transcription_job(
                        TranscriptionJobName=job_name
                    )
                    status = response['TranscriptionJob']['TranscriptionJobStatus']
                    print(f"  Job status: {status}")
                    return True
                except Exception as status_error:
                    print(f"✗ Failed to get job status: {status_error}")
                    return False
            else:
                print(f"✗ Failed to start transcription job: {e}")
                
                # Check for common errors
                if "AccessDenied" in error_str or "not authorized" in error_str:
                    print(f"\n  DIAGNOSIS: Missing IAM permissions")
                    print(f"  Your IAM role/user needs these permissions:")
                    print(f"    - transcribe:StartTranscriptionJob")
                    print(f"    - transcribe:GetTranscriptionJob")
                    print(f"    - s3:GetObject (for the video file)")
                    print(f"    - s3:PutObject (for transcription output)")
                elif "InvalidRequest" in error_str:
                    print(f"\n  DIAGNOSIS: Invalid request parameters")
                    print(f"  Check that the video file format is supported")
                return False
        
    except Exception as e:
        print(f"✗ Error during test: {e}")
        return False


def main():
    print("=" * 60)
    print("AWS Transcribe Test Script")
    print("=" * 60)
    print()
    
    # Test 1: Permissions
    if not test_transcribe_permissions():
        print("\n❌ Permission test failed")
        print("Please check your AWS credentials and IAM permissions")
        return 1
    
    # Test 2: Job creation
    if not test_transcribe_job_creation():
        print("\n❌ Job creation test failed")
        print("Transcription jobs cannot be created")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    print("\nTranscription should be working correctly.")
    print("If you still don't see transcriptions, check:")
    print("  1. Backend logs for errors")
    print("  2. AWS Transcribe console for job status")
    print("  3. S3 bucket for transcription output files")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
