#!/usr/bin/env python3
"""
Test Pegasus transcription on an existing video.

This script tests the new Pegasus-based transcription system.
"""

import sys
from pathlib import Path

# Add backend/src to Python path
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

import boto3
from config import load_config
from aws.bedrock_client import BedrockClient
from services.pegasus_transcription_service import PegasusTranscriptionService

def main():
    print("=" * 70)
    print("Pegasus Transcription Test")
    print("=" * 70)
    print()
    
    # Load config
    try:
        config = load_config("config.local.yaml")
        print(f"✓ Config loaded: region={config.aws_region}, bucket={config.s3_bucket_name}")
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return 1
    
    # Find a video in S3
    try:
        s3_client = boto3.client('s3', region_name=config.aws_region)
        response = s3_client.list_objects_v2(
            Bucket=config.s3_bucket_name,
            Prefix='videos/',
            MaxKeys=1
        )
        
        if not response.get('Contents'):
            print(f"✗ No videos found in S3 bucket")
            return 1
        
        video_key = response['Contents'][0]['Key']
        video_s3_uri = f"s3://{config.s3_bucket_name}/{video_key}"
        
        # Extract video_id from key (format: videos/{index_id}/{video_id}/{filename})
        parts = video_key.split('/')
        if len(parts) >= 3:
            video_id = parts[2]
        else:
            video_id = "test-video"
        
        print(f"✓ Found video: {video_key}")
        print(f"  Video ID: {video_id}")
        print(f"  S3 URI: {video_s3_uri}")
        print()
        
    except Exception as e:
        print(f"✗ Failed to find video: {e}")
        return 1
    
    # Initialize Pegasus transcription service
    try:
        bedrock_client = BedrockClient(config)
        transcription_service = PegasusTranscriptionService(config, bedrock_client)
        print(f"✓ Initialized Pegasus transcription service")
        print()
    except Exception as e:
        print(f"✗ Failed to initialize service: {e}")
        return 1
    
    # Generate transcription
    print("Generating transcription with Pegasus...")
    print("(This may take 30-60 seconds depending on video length)")
    print()
    
    try:
        job_name = transcription_service.start_transcription(
            video_id=video_id,
            s3_uri=video_s3_uri
        )
        
        print(f"✓ Transcription completed: {job_name}")
        print()
        
        # Load and display segments
        segments = transcription_service._load_segments(video_id)
        
        if segments:
            print(f"✓ Generated {len(segments)} transcription segments")
            print()
            print("First 5 segments:")
            for i, seg in enumerate(segments[:5], 1):
                print(f"  {i}. [{seg.start_time:.1f}s - {seg.end_time:.1f}s]")
                print(f"     {seg.text[:100]}...")
                print()
            
            # Test clip retrieval
            if len(segments) > 0:
                test_start = segments[0].start_time
                test_end = segments[min(2, len(segments)-1)].end_time
                
                clip_text = transcription_service.get_segments_for_clip(
                    video_id=video_id,
                    start_time=test_start,
                    end_time=test_end
                )
                
                if clip_text:
                    print(f"✓ Clip retrieval test passed")
                    print(f"  Clip [{test_start:.1f}s - {test_end:.1f}s]:")
                    print(f"  {clip_text[:200]}...")
                else:
                    print(f"⚠️  Clip retrieval returned no text")
        else:
            print(f"⚠️  No segments found")
        
        print()
        print("=" * 70)
        print("✅ Pegasus transcription test completed successfully!")
        print("=" * 70)
        
        return 0
        
    except Exception as e:
        print(f"✗ Transcription failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
