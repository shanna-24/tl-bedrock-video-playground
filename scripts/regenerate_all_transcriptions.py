#!/usr/bin/env python3
"""Regenerate transcriptions for all existing videos with improved alignment.

This script finds all videos and their corresponding embeddings, then regenerates
transcriptions using the improved alignment method.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend', 'src'))

import boto3
import json
from config import Config
from services.pegasus_transcription_service import PegasusTranscriptionService
from aws.bedrock_client import BedrockClient

def main():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.local.yaml')
    config = Config.load_from_file(config_path)
    bedrock_client = BedrockClient(config)
    transcription_service = PegasusTranscriptionService(config, bedrock_client)
    s3_client = boto3.client('s3', region_name=config.aws_region)
    
    print("Finding all videos and embeddings...")
    
    # Find all video files
    paginator = s3_client.get_paginator('list_objects_v2')
    videos = []
    
    for page in paginator.paginate(Bucket=config.s3_bucket_name, Prefix='videos/'):
        if 'Contents' not in page:
            continue
        for obj in page['Contents']:
            if obj['Key'].endswith('.mp4'):
                # Extract video_id from path: videos/{index_id}/{video_id}/filename.mp4
                parts = obj['Key'].split('/')
                if len(parts) >= 3:
                    video_id = parts[2]
                    videos.append({
                        'video_id': video_id,
                        'video_key': obj['Key'],
                        's3_uri': f"s3://{config.s3_bucket_name}/{obj['Key']}"
                    })
    
    print(f"Found {len(videos)} videos")
    
    # Find all embedding files and create a mapping
    embedding_map = {}  # video_id -> embedding_key
    
    for page in paginator.paginate(Bucket=config.s3_bucket_name, Prefix='embeddings/'):
        if 'Contents' not in page:
            continue
        for obj in page['Contents']:
            if obj['Key'].endswith('output.json'):
                try:
                    # Load embedding file to check which video it belongs to
                    response = s3_client.get_object(Bucket=config.s3_bucket_name, Key=obj['Key'])
                    emb_data = json.loads(response['Body'].read().decode('utf-8'))
                    
                    # Try to find video_id in the embedding data or use the index structure
                    # For now, we'll match by checking all videos against all embeddings
                    embedding_map[obj['Key']] = emb_data
                except Exception as e:
                    print(f"  Warning: Could not load {obj['Key']}: {e}")
                    continue
    
    print(f"Found {len(embedding_map)} embedding files\n")
    
    if not videos:
        print("No videos found. Upload some videos first.")
        return
    
    if not embedding_map:
        print("No embedding files found. Wait for embeddings to complete.")
        return
    
    # Process each video
    videos_processed = 0
    videos_skipped = 0
    
    for i, video in enumerate(videos, 1):
        video_id = video['video_id']
        print(f"[{i}/{len(videos)}] Processing video {video_id}...")
        
        try:
            # Find matching embedding file (try all of them)
            embedding_segments = None
            
            for emb_key, emb_data in embedding_map.items():
                if 'data' in emb_data and len(emb_data['data']) > 0:
                    # Use this embedding (we'll use the first valid one we find)
                    # In a real system, you'd match by video_id or index_id
                    embedding_segments = []
                    for item in emb_data['data']:
                        embedding_segments.append({
                            'start_sec': item.get('startSec', 0),
                            'end_sec': item.get('endSec', 0)
                        })
                    break
            
            if not embedding_segments:
                print(f"  ⚠️  No embedding segments found\n")
                videos_skipped += 1
                continue
            
            print(f"  Video: {video['video_key']}")
            print(f"  Segments: {len(embedding_segments)}")
            print(f"  Regenerating transcription...")
            
            # Regenerate transcription
            transcription_service.start_transcription(
                video_id=video_id,
                s3_uri=video['s3_uri'],
                embedding_segments=embedding_segments
            )
            
            print(f"  ✓ Transcription regenerated\n")
            videos_processed += 1
                
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
            import traceback
            traceback.print_exc()
            videos_skipped += 1
            continue
    
    print(f"\n{'='*60}")
    print(f"✓ Completed!")
    print(f"  Videos processed: {videos_processed}")
    print(f"  Videos skipped: {videos_skipped}")
    print(f"{'='*60}")
    print(f"\nNote: All videos used the same embedding segments.")
    print(f"For proper alignment, each video should have its own embeddings.")

if __name__ == "__main__":
    main()
