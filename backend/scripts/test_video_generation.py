#!/usr/bin/env python3
"""Test script for video generation from Edit Decision List.

This script demonstrates the video generation functionality by creating
a compiled video from multiple segments of source videos.
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import Config
from aws.s3_client import S3Client
from services.video_generation_service import VideoGenerationService


async def main():
    print("=" * 70)
    print("Video Generation Test")
    print("=" * 70)
    print()
    
    # Load configuration
    print("Loading configuration...")
    try:
        config = Config.load_from_file("config.local.yaml")
        print(f"✓ Configuration loaded")
        print(f"  S3 Bucket: {config.s3_bucket_name}")
        print(f"  AWS Region: {config.aws_region}")
        print()
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return 1
    
    # Initialize S3 client
    print("Initializing S3 client...")
    try:
        s3_client = S3Client(config)
        print(f"✓ S3 client initialized")
        print()
    except Exception as e:
        print(f"✗ Failed to initialize S3 client: {e}")
        return 1
    
    # Initialize video generation service
    print("Initializing video generation service...")
    try:
        video_gen_service = VideoGenerationService(s3_client, config)
        print(f"✓ Video generation service initialized")
        print()
    except Exception as e:
        print(f"✗ Failed to initialize video generation service: {e}")
        print(f"  Make sure ffmpeg is installed: brew install ffmpeg")
        return 1
    
    # Example EDL - Replace with actual video URIs from your S3 bucket
    print("Creating example Edit Decision List...")
    print()
    print("NOTE: This is an example EDL. Replace the source_s3_uri values")
    print("      with actual video URIs from your S3 bucket.")
    print()
    
    example_edl = [
        {
            "source_s3_uri": f"s3://{config.s3_bucket_name}/videos/example_video_1.mp4",
            "start_time": "00:00:05.000",
            "end_time": "00:00:15.000"
        },
        {
            "source_s3_uri": f"s3://{config.s3_bucket_name}/videos/example_video_1.mp4",
            "start_time": "00:00:30.000",
            "end_time": "00:00:40.000"
        },
        {
            "source_s3_uri": f"s3://{config.s3_bucket_name}/videos/example_video_2.mp4",
            "start_time": "00:00:10.000",
            "end_time": "00:00:20.000"
        }
    ]
    
    print("Example EDL:")
    for i, entry in enumerate(example_edl, 1):
        print(f"  Segment {i}:")
        print(f"    Source: {entry['source_s3_uri']}")
        print(f"    Time: {entry['start_time']} - {entry['end_time']}")
    print()
    
    # Ask user if they want to proceed with actual generation
    response = input("Do you want to test with actual videos? (yes/no): ").strip().lower()
    if response != "yes":
        print()
        print("Test cancelled. To test video generation:")
        print("1. Upload test videos to your S3 bucket")
        print("2. Update the EDL in this script with actual S3 URIs")
        print("3. Run this script again")
        return 0
    
    # Generate video
    print()
    print("Generating video from EDL...")
    print("(This may take some time depending on video sizes)")
    print()
    
    try:
        result = await video_gen_service.generate_video_from_edl(
            edl=example_edl,
            output_filename="test_compilation"
        )
        
        print()
        print("=" * 70)
        print("✅ Video generation completed successfully!")
        print("=" * 70)
        print()
        print("Generated Video Details:")
        print(f"  S3 URI: {result['s3_uri']}")
        print(f"  S3 Key: {result['s3_key']}")
        print(f"  Duration: {result['duration']:.2f} seconds")
        print(f"  Segments: {result['segment_count']}")
        print()
        
        return 0
        
    except Exception as e:
        print()
        print("=" * 70)
        print("✗ Video generation failed")
        print("=" * 70)
        print()
        print(f"Error: {e}")
        print()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
