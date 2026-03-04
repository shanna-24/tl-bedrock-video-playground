#!/usr/bin/env python3
"""Generate a comprehensive Jupyter notebook for video transcription walkthrough."""

import json
from pathlib import Path

# Define the notebook structure
notebook = {
    "cells": [],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {
                "name": "ipython",
                "version": 3
            },
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.11.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 4
}

def add_markdown(text):
    """Add a markdown cell."""
    notebook["cells"].append({
        "cell_type": "markdown",
        "metadata": {},
        "source": text.split("\n")
    })

def add_code(code):
    """Add a code cell."""
    notebook["cells"].append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": code.split("\n")
    })

# Title and Introduction
add_markdown("""# Video Transcription Implementation Walkthrough

This notebook demonstrates the complete video transcription process using AWS Bedrock's Pegasus model.

## Overview

The system uses **TwelveLabs Pegasus** model (via AWS Bedrock) to transcribe video content with precise timestamp alignment.

### Key Features
- **Segment-aligned transcription**: Transcription segments match Marengo embedding boundaries
- **High accuracy**: Per-segment transcription using ffmpeg video splitting
- **Search integration**: Transcription text included in search results
- **Automatic processing**: Triggered after embedding job completion

### Architecture
```
Video Upload → Embedding Job → Marengo Embeddings → Pegasus Transcription → S3 Storage → Search
```""")

# Setup
add_markdown("## Part 1: Setup and Configuration")

add_code("""import sys
import os
from pathlib import Path

# Add backend/src to path
backend_src = Path.cwd().parent / 'backend' / 'src'
sys.path.insert(0, str(backend_src))

import json
import boto3
from config import Config
from aws.bedrock_client import BedrockClient
from services.pegasus_transcription_service import PegasusTranscriptionService

print("✓ Imports successful")""")

add_code("""# Load configuration
config_path = Path.cwd().parent / 'config.local.yaml'
config = Config.load_from_file(str(config_path))

print(f"Configuration loaded:")
print(f"  AWS Region: {config.aws_region}")
print(f"  S3 Bucket: {config.s3_bucket_name}")
print(f"  Pegasus Model: {config.pegasus_model_id}")
print(f"  Marengo Model: {config.marengo_model_id}")""")

# Architecture
add_markdown("""## Part 2: Understanding the Architecture

### Transcription Approach

The system uses **segment-by-segment transcription** for accurate timestamps:

1. **Segment-by-Segment** (Current)
   - Splits video using ffmpeg based on Marengo embedding segments
   - Transcribes each segment individually with Pegasus
   - Uses known segment boundaries as timestamps (no fabrication)
   - Higher accuracy per segment
   - Perfect alignment with embeddings

### Why Segment-by-Segment?

**Accurate Timestamps:**
- Pegasus is a video understanding model, not speech-to-text
- Cannot generate accurate timestamps on its own
- We use known segment boundaries from Marengo embeddings
- Timestamps are accurate and reliable

**Better Accuracy:**
- Each segment transcribed with full context
- No hallucination or guessing
- Consistent with embedding boundaries

### Process Flow

1. Download full video from S3
2. For each Marengo embedding segment:
   - Extract segment using ffmpeg
   - Upload to S3 temporarily
   - Transcribe with Pegasus
   - Store with known timestamps
   - Clean up temp files
3. Store all segments in S3

**Characteristics:**
- Multiple API calls (one per segment)
- Uses ffmpeg for extraction
- Temporary files managed automatically
- 30-60s completion for typical videos
- Accurate and reliable timestamps""")

# Find Video
add_markdown("## Part 3: Finding a Video to Transcribe")

add_code("""# Initialize S3 client
s3_client = boto3.client('s3', region_name=config.aws_region)

# Find videos in S3
response = s3_client.list_objects_v2(
    Bucket=config.s3_bucket_name,
    Prefix='videos/',
    MaxKeys=5
)

if response.get('Contents'):
    print("Available videos:")
    for i, obj in enumerate(response['Contents'][:5], 1):
        key = obj['Key']
        size_mb = obj['Size'] / (1024 * 1024)
        print(f"  {i}. {key} ({size_mb:.2f} MB)")
    
    # Select first video
    video_key = response['Contents'][0]['Key']
    video_s3_uri = f"s3://{config.s3_bucket_name}/{video_key}"
    
    # Extract video_id
    parts = video_key.split('/')
    video_id = parts[2] if len(parts) >= 3 else "demo-video"
    
    print(f"\\nSelected video:")
    print(f"  Video ID: {video_id}")
    print(f"  S3 URI: {video_s3_uri}")
else:
    print("No videos found")
    video_id = None
    video_s3_uri = None""")

# Load Embeddings
add_markdown("""## Part 4: Loading Embedding Segments

Transcription is aligned with Marengo embedding segments.""")

add_code("""def find_embedding_file(video_id):
    paginator = s3_client.get_paginator('list_objects_v2')
    
    for page in paginator.paginate(Bucket=config.s3_bucket_name, Prefix='embeddings/'):
        if 'Contents' not in page:
            continue
        
        for obj in page['Contents']:
            if 'output.json' in obj['Key']:
                try:
                    response = s3_client.get_object(
                        Bucket=config.s3_bucket_name,
                        Key=obj['Key']
                    )
                    data = json.loads(response['Body'].read().decode('utf-8'))
                    if data.get('videoId') == video_id:
                        return obj['Key'], data
                except:
                    continue
    return None, None

if video_id:
    embedding_key, embedding_data = find_embedding_file(video_id)
    
    if embedding_data:
        segments = embedding_data.get('segments', [])
        print(f"Found {len(segments)} embedding segments")
        print(f"\\nFirst 5 segments:")
        for i, seg in enumerate(segments[:5], 1):
            start = seg.get('startSec', seg.get('start_sec', 0))
            end = seg.get('endSec', seg.get('end_sec', 0))
            duration = end - start
            print(f"  {i}. [{start:.1f}s - {end:.1f}s] (duration: {duration:.1f}s)")
        
        embedding_segments = [
            {
                'start_sec': seg.get('startSec', seg.get('start_sec', 0)),
                'end_sec': seg.get('endSec', seg.get('end_sec', 0))
            }
            for seg in segments
        ]
    else:
        print("No embedding data found")
        embedding_segments = None
else:
    embedding_segments = None""")

# Initialize Service
add_markdown("## Part 5: Initialize Pegasus Transcription Service")

add_code("""bedrock_client = BedrockClient(config)
transcription_service = PegasusTranscriptionService(config, bedrock_client)

print("✓ Pegasus transcription service initialized")
print(f"  Using model: {config.pegasus_model_id}")
print(f"  AWS Region: {config.aws_region}")""")

# Process Explanation
add_markdown("""## Part 6: Understanding the Transcription Process

### Segment-by-Segment Workflow

1. **Download full video** from S3
2. **Filter segments** (remove duplicates)
3. **For each segment:**
   - Extract using ffmpeg
   - Upload to S3 temporarily
   - Invoke Pegasus
   - Parse response
   - Clean up
4. **Store all segments** in S3

### Transcription Prompt
```
Transcribe all spoken words in this video clip.

Provide only the transcription text, nothing else.
Do NOT include timestamps, labels, or formatting.
Just the spoken words.
```""")

# Generate Transcription
add_markdown("## Part 7: Generate Transcription\n\nThis may take 30-60 seconds.")

add_code("""if video_id and video_s3_uri:
    print("Starting transcription...")
    print("(This may take 30-60 seconds)\\n")
    
    try:
        job_name = transcription_service.start_transcription(
            video_id=video_id,
            s3_uri=video_s3_uri,
            embedding_segments=embedding_segments
        )
        
        print(f"✓ Transcription completed: {job_name}")
        
    except Exception as e:
        print(f"✗ Transcription failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No video selected")""")

# Inspect Results
add_markdown("## Part 8: Inspect Transcription Results")

add_code("""if video_id:
    segments = transcription_service._load_segments(video_id)
    
    if segments:
        print(f"Generated {len(segments)} transcription segments\\n")
        
        print("First 10 segments:")
        print("=" * 80)
        for i, seg in enumerate(segments[:10], 1):
            duration = seg.end_time - seg.start_time
            print(f"\\nSegment {i}:")
            print(f"  Time: [{seg.start_time:.1f}s - {seg.end_time:.1f}s] ({duration:.1f}s)")
            print(f"  Confidence: {seg.confidence:.2f}")
            print(f"  Text: {seg.text}")
        
        # Statistics
        total_duration = segments[-1].end_time if segments else 0
        total_words = sum(len(seg.text.split()) for seg in segments)
        avg_confidence = sum(seg.confidence for seg in segments) / len(segments)
        
        print("\\n" + "=" * 80)
        print("\\nStatistics:")
        print(f"  Total segments: {len(segments)}")
        print(f"  Total duration: {total_duration:.1f}s")
        print(f"  Total words: {total_words}")
        print(f"  Average confidence: {avg_confidence:.2f}")
        print(f"  Words per second: {total_words / total_duration:.2f}")
    else:
        print("No transcription segments found")""")

# Clip Retrieval
add_markdown("""## Part 9: Testing Clip Retrieval

The service retrieves transcription for specific video clips (used in search).""")

add_code("""if video_id and segments and len(segments) > 2:
    test_start = segments[0].start_time
    test_end = segments[min(2, len(segments)-1)].end_time
    
    print(f"Testing clip retrieval for [{test_start:.1f}s - {test_end:.1f}s]\\n")
    
    clip_text = transcription_service.get_segments_for_clip(
        video_id=video_id,
        start_time=test_start,
        end_time=test_end
    )
    
    if clip_text:
        print("✓ Clip retrieval successful")
        print(f"\\nTranscription for clip:")
        print("=" * 80)
        print(clip_text)
        print("=" * 80)
    else:
        print("⚠️  No text returned")
else:
    print("Not enough segments for test")""")

# Storage Format
add_markdown("""## Part 10: Storage Format

Segments stored at: `s3://{bucket}/transcriptions/segments/{video_id}.json`""")

add_code("""if video_id:
    key = f"transcriptions/segments/{video_id}.json"
    
    try:
        response = s3_client.get_object(
            Bucket=config.s3_bucket_name,
            Key=key
        )
        
        data = json.loads(response['Body'].read().decode('utf-8'))
        
        print(f"Storage: s3://{config.s3_bucket_name}/{key}")
        print(f"\\nJSON structure:")
        print(json.dumps({
            'video_id': data.get('video_id'),
            'source': data.get('source'),
            'segment_count': len(data.get('segments', [])),
            'sample_segment': data.get('segments', [{}])[0] if data.get('segments') else None
        }, indent=2))
        
        file_size = len(json.dumps(data))
        print(f"\\nFile size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
        
    except Exception as e:
        print(f"Failed to load: {e}")""")

# Search Integration
add_markdown("""## Part 11: Search Integration

Transcription is automatically included in search results:

```json
{
  "video_id": "abc123",
  "start_time": 10.5,
  "end_time": 15.2,
  "score": 0.85,
  "transcription": "Transcribed text for this clip"
}
```

### Filtering
- Empty segments removed
- Segments >15s filtered (likely full-video)
- Only overlapping segments included""")

# Diagnostics
add_markdown("## Part 12: Diagnostics and Troubleshooting")

add_code("""def check_transcription_status(video_id):
    key = f"transcriptions/segments/{video_id}.json"
    try:
        s3_client.head_object(Bucket=config.s3_bucket_name, Key=key)
        print(f"✓ Transcription exists for {video_id}")
        return True
    except:
        print(f"✗ No transcription for {video_id}")
        return False

def list_transcribed_videos():
    response = s3_client.list_objects_v2(
        Bucket=config.s3_bucket_name,
        Prefix='transcriptions/segments/'
    )
    
    if 'Contents' in response:
        video_ids = []
        for obj in response['Contents']:
            if obj['Key'].endswith('.json'):
                vid = obj['Key'].split('/')[-1].replace('.json', '')
                video_ids.append(vid)
        return video_ids
    return []

print("Transcription Diagnostics")
print("=" * 80)

if video_id:
    print(f"\\nChecking video: {video_id}")
    check_transcription_status(video_id)

print("\\nAll transcribed videos:")
transcribed = list_transcribed_videos()
print(f"Found {len(transcribed)} videos with transcriptions")
for vid in transcribed[:5]:
    print(f"  - {vid}")""")

# Best Practices
add_markdown("""## Part 13: Best Practices

### 1. Segment Alignment
- Always provide embedding segments
- Filter duplicates before processing
- Keep segments 2-15 seconds

### 2. Error Handling
- Don't fail embedding jobs on transcription errors
- Log all errors
- Provide fallback text
- Retry with exponential backoff

### 3. Performance
- Process segments in parallel when possible
- Cache results in S3
- Clean up temp files
- Monitor API quotas

### 4. Quality
- Use low temperature (0.1)
- Validate format before storing
- Track confidence scores
- Review failures periodically""")

# Utility Scripts
add_markdown("""## Part 14: Utility Scripts

### Available Scripts

```bash
# Test transcription on a video
python scripts/test_pegasus_transcription.py

# Regenerate all transcriptions
python scripts/regenerate_transcriptions.py

# Test search with transcription
python scripts/test_search_transcription.py
```""")

# Summary
add_markdown("""## Summary

This notebook demonstrated the complete video transcription implementation:

1. **Pegasus provides video-aware transcription** with better accuracy
2. **Segment alignment** ensures perfect matching with embeddings
3. **Automatic integration** with search
4. **Robust error handling** for reliability
5. **Flexible architecture** for different use cases

### Next Steps

- Explore utility scripts in `scripts/` directory
- Review API endpoints in `backend/src/api/videos.py`
- Test with your own videos
- Monitor performance metrics
- Consider enhancements (multi-language, speaker ID, etc.)

### Resources

- **Config Guide**: `backend/CONFIG.md`
- **Pegasus Service**: `backend/src/services/pegasus_transcription_service.py`
- **Search Integration**: `backend/src/services/search_service.py`""")

# Write the notebook
output_path = Path(__file__).parent.parent / 'notebooks' / 'video_transcription_walkthrough.ipynb'
output_path.parent.mkdir(exist_ok=True)

with open(output_path, 'w') as f:
    json.dump(notebook, f, indent=1)

print(f"✓ Notebook created: {output_path}")
print(f"  Total cells: {len(notebook['cells'])}")
print(f"  Markdown cells: {sum(1 for c in notebook['cells'] if c['cell_type'] == 'markdown')}")
print(f"  Code cells: {sum(1 for c in notebook['cells'] if c['cell_type'] == 'code')}")
