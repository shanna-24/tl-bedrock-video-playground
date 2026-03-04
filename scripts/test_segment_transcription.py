#!/usr/bin/env python3
"""Test segment-by-segment transcription."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

from config import Config
from services.pegasus_transcription_service import PegasusTranscriptionService
from aws.bedrock_client import BedrockClient
import boto3
import json

config = Config.load_from_file('config.local.yaml')
bedrock = BedrockClient(config)
service = PegasusTranscriptionService(config, bedrock)
s3 = boto3.client('s3', region_name=config.aws_region)

# Test with one video
video_id = '289fd932-6445-425a-8817-33b22ea1641e'
video_key = 'videos/1fb93fdd-b74b-4769-ab67-0414e6a4c1cd/289fd932-6445-425a-8817-33b22ea1641e/In-N-Out.mp4'
s3_uri = f's3://{config.s3_bucket_name}/{video_key}'

# Get embedding segments
emb_key = 'embeddings/2j46rxntaure/output.json'
response = s3.get_object(Bucket=config.s3_bucket_name, Key=emb_key)
emb_data = json.loads(response['Body'].read().decode('utf-8'))

embedding_segments = []
for item in emb_data['data']:
    embedding_segments.append({
        'start_sec': item['startSec'],
        'end_sec': item['endSec']
    })

print(f'Testing segment-by-segment transcription...')
print(f'Video: {video_id}')
print(f'Segments: {len(embedding_segments)}')
print()

service.start_transcription(
    video_id=video_id,
    s3_uri=s3_uri,
    embedding_segments=embedding_segments
)

print()
print('✓ Transcription completed!')
print()
print('Checking results...')

# Load and display results
response = s3.get_object(
    Bucket=config.s3_bucket_name,
    Key=f'transcriptions/segments/{video_id}.json'
)
data = json.loads(response['Body'].read().decode('utf-8'))

print(f'Total segments: {len(data["segments"])}')
print()
for i, seg in enumerate(data['segments']):
    duration = seg['end_time'] - seg['start_time']
    print(f'{i+1}. [{seg["start_time"]:.1f}s - {seg["end_time"]:.1f}s] ({duration:.1f}s)')
    text_preview = seg["text"][:80] + '...' if len(seg["text"]) > 80 else seg["text"]
    print(f'   "{text_preview}"')
    print()
