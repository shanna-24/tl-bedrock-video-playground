#!/usr/bin/env python3
"""Test script to verify transcription retrieval in search results."""

import sys
sys.path.insert(0, 'backend/src')

from config import Config
from services.pegasus_transcription_service import PegasusTranscriptionService
import boto3

config = Config()
service = PegasusTranscriptionService(config)

# List transcription files
s3 = boto3.client('s3', region_name=config.aws_region)
response = s3.list_objects_v2(
    Bucket=config.s3_bucket_name,
    Prefix='transcriptions/segments/',
    MaxKeys=5
)

if 'Contents' in response:
    print(f"Found {len(response['Contents'])} transcription files\n")
    
    for obj in response['Contents']:
        print(f'File: {obj["Key"]}')
        
        # Extract video_id from key
        video_id = obj['Key'].split('/')[-1].replace('.json', '')
        print(f'Video ID: {video_id}')
        
        # Test get_segments_for_clip with different time ranges
        for start, end in [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0)]:
            text = service.get_segments_for_clip(video_id, start, end)
            if text:
                print(f'  [{start}-{end}s]: {text[:80]}...')
            else:
                print(f'  [{start}-{end}s]: No transcription')
        
        print('---\n')
        break
else:
    print('No transcription files found in S3')
