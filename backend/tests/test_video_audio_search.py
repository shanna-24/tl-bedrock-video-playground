"""Test script for video and audio clip search functionality.

This script demonstrates how to use the new video and audio clip search features.
"""

import base64
import json
from pathlib import Path


def create_sample_video_search_request():
    """Create a sample video clip search request."""
    # This is a placeholder - in real usage, you would read an actual video file
    # video_path = Path("sample_clip.mp4")
    # with open(video_path, "rb") as f:
    #     video_bytes = f.read()
    #     video_base64 = base64.b64encode(video_bytes).decode('utf-8')
    
    request = {
        "index_id": "your-index-id",
        "video": "base64-encoded-video-data-here",
        "video_format": "mp4",
        "top_k": 10,
        "generate_screenshots": True
    }
    
    return request


def create_sample_audio_search_request():
    """Create a sample audio clip search request."""
    # This is a placeholder - in real usage, you would read an actual audio file
    # audio_path = Path("sample_clip.mp3")
    # with open(audio_path, "rb") as f:
    #     audio_bytes = f.read()
    #     audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
    
    request = {
        "index_id": "your-index-id",
        "audio": "base64-encoded-audio-data-here",
        "audio_format": "mp3",
        "top_k": 10,
        "generate_screenshots": True
    }
    
    return request


def create_multimodal_search_request():
    """Create a multimodal search request combining text and video."""
    request = {
        "index_id": "your-index-id",
        "query": "basketball game winning shot",
        "video": "base64-encoded-video-data-here",
        "video_format": "mp4",
        "top_k": 10,
        "generate_screenshots": True
    }
    
    return request


if __name__ == "__main__":
    print("Video/Audio Clip Search Examples")
    print("=" * 50)
    
    print("\n1. Video Clip Search Request:")
    print(json.dumps(create_sample_video_search_request(), indent=2))
    
    print("\n2. Audio Clip Search Request:")
    print(json.dumps(create_sample_audio_search_request(), indent=2))
    
    print("\n3. Multimodal Search Request (Text + Video):")
    print(json.dumps(create_multimodal_search_request(), indent=2))
    
    print("\n" + "=" * 50)
    print("Usage Notes:")
    print("- Video/audio clips are limited to 10 seconds duration")
    print("- Maximum file size: 25MB (Bedrock InvokeModel limit)")
    print("- Supported video formats: mp4, mov, avi, mkv, webm, flv, wmv, m4v")
    print("- Supported audio formats: mp3, wav, aac, m4a, flac, ogg, wma")
    print("- Video clips use visual, audio, and transcription embeddings")
    print("- Audio clips use audio and transcription embeddings")
