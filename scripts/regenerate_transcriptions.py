#!/usr/bin/env python3
"""Regenerate transcriptions for all videos with improved alignment."""

import sys
import os

# Add backend/src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

import asyncio
import boto3
import json
from config import Config
from services.pegasus_transcription_service import PegasusTranscriptionService
from aws.bedrock_client import BedrockClient

async def main():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.local.yaml')
    config = Config.load_from_file(config_path)
    bedrock_client = BedrockClient(config)
    transcription_service = PegasusTranscriptionService(config, bedrock_client)
    s3_client = boto3.client('s3', region_name=config.aws_region)
    
    print("Finding videos with existing transcriptions...")
    
    # List all transcription files
    response = s3_client.list_objects_v2(
        Bucket=config.s3_bucket_name,
        Prefix='transcriptions/segments/'
    )
    
    if 'Contents' not in response:
        print("No transcription files found")
        return
    
    video_ids = []
    for obj in response['Contents']:
        key = obj['Key']
        if key.endswith('.json'):
            video_id = key.split('/')[-1].replace('.json', '')
            video_ids.append(video_id)
    
    print(f"Found {len(video_ids)} videos with transcriptions\n")
    
    # Process each video
    for i, video_id in enumerate(video_ids, 1):
        print(f"[{i}/{len(video_ids)}] Processing {video_id}...")
        
        try:
            # Find video file
            paginator = s3_client.get_paginator('list_objects_v2')
            video_key = None
            
            for page in paginator.paginate(Bucket=config.s3_bucket_name, Prefix='videos/'):
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    if video_id in obj['Key'] and obj['Key'].endswith('.mp4'):
                        video_key = obj['Key']
                        break
                if video_key:
                    break
            
            if not video_key:
                print(f"  ⚠️  Video file not found\n")
                continue
            
            s3_uri = f"s3://{config.s3_bucket_name}/{video_key}"
            
            # Find embedding file
            embedding_key = None
            for page in paginator.paginate(Bucket=config.s3_bucket_name, Prefix='embeddings/'):
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    # Look for output.json files that contain this video_id
                    if 'output.json' in obj['Key']:
                        # Check if this embedding file contains our video
                        try:
                            emb_response = s3_client.get_object(
                                Bucket=config.s3_bucket_name,
                                Key=obj['Key']
                            )
                            emb_data = json.loads(emb_response['Body'].read().decode('utf-8'))
                            if emb_data.get('videoId') == video_id:
                                embedding_key = obj['Key']
                                break
                        except:
                            continue
                if embedding_key:
                    break
            
            if not embedding_key:
                print(f"  ⚠️  Embedding file not found\n")
                continue
            
            # Load embedding segments
            response = s3_client.get_object(
                Bucket=config.s3_bucket_name,
                Key=embedding_key
            )
            embedding_data = json.loads(response['Body'].read().decode('utf-8'))
            
            embedding_segments = []
            for segment in embedding_data.get('segments', []):
                embedding_segments.append({
                    'start_sec': segment.get('startSec', segment.get('start_sec', 0)),
                    'end_sec': segment.get('endSec', segment.get('end_sec', 0))
                })
            
            if not embedding_segments:
                print(f"  ⚠️  No embedding segments found\n")
                continue
            
            print(f"  Found {len(embedding_segments)} segments, regenerating transcription...")
            
            # Regenerate transcription
            transcription_service.start_transcription(
                video_id=video_id,
                s3_uri=s3_uri,
                embedding_segments=embedding_segments
            )
            
            print(f"  ✓ Transcription regenerated\n")
            
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"✓ Completed processing {len(video_ids)} videos")

if __name__ == "__main__":
    asyncio.run(main())
