"""
Manual test to investigate Pegasus single video analysis behavior.

This test helps determine why single video analysis produces limited results.

Run with:
    python -m pytest backend/tests/manual/test_pegasus_single_video_analysis.py -v -s

Or run directly:
    cd backend/tests/manual
    python test_pegasus_single_video_analysis.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend/src to path
backend_src = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(backend_src))

# Set config path if not already set
config_path_env = os.environ.get("CONFIG_PATH")
if not config_path_env:
    config_path = Path(__file__).parent.parent.parent.parent / "config.local.yaml"
    if config_path.exists():
        os.environ["CONFIG_PATH"] = str(config_path)
        print(f"Using config: {config_path}")
    else:
        print(f"Error: config.local.yaml not found at {config_path}")
        print("Please create config.local.yaml or set CONFIG_PATH environment variable")
        sys.exit(1)
else:
    print(f"Using config from CONFIG_PATH: {config_path_env}")

from aws.bedrock_client import BedrockClient
from config import Config


async def test_pegasus_analysis_variations():
    """Test different approaches to single video analysis with Pegasus."""
    
    print("\n" + "="*80)
    print("PEGASUS SINGLE VIDEO ANALYSIS INVESTIGATION")
    print("="*80)
    
    # Initialize clients - use load_from_file method
    config_path = os.environ.get("CONFIG_PATH", "config.local.yaml")
    config = Config.load_from_file(config_path)
    bedrock = BedrockClient(config)
    
    # You'll need to provide a test video S3 URI
    # Replace this with an actual video from your system
    test_video_uri = input("\nEnter S3 URI of test video (or press Enter to skip): ").strip()
    
    if not test_video_uri:
        print("\nNo video URI provided. Skipping tests.")
        print("\nTo run this test:")
        print("1. Upload a test video to your S3 bucket")
        print("2. Run this script and provide the S3 URI")
        return
    
    print(f"\nTest video: {test_video_uri}")
    print("\n" + "-"*80)
    
    # Test 1: Simple query
    print("\nTEST 1: Simple query - 'Summarize this video'")
    print("-"*80)
    
    try:
        result1 = bedrock.invoke_pegasus_analysis(
            s3_uri=test_video_uri,
            prompt="Summarize this video. Describe what happens from beginning to end.",
            temperature=0.2
        )
        
        print(f"\nFinish Reason: {result1['finishReason']}")
        print(f"Message Length: {len(result1['message'])} characters")
        print(f"\nMessage:\n{result1['message']}")
        
        if result1['finishReason'] == 'length':
            print("\n⚠️  WARNING: Output was truncated due to token limit!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "-"*80)
    
    # Test 2: Query about end of video
    print("\nTEST 2: Query about end of video - 'What happens at the end?'")
    print("-"*80)
    
    try:
        result2 = bedrock.invoke_pegasus_analysis(
            s3_uri=test_video_uri,
            prompt="What happens at the end of this video? Describe the final scenes in detail.",
            temperature=0.2
        )
        
        print(f"\nFinish Reason: {result2['finishReason']}")
        print(f"Message Length: {len(result2['message'])} characters")
        print(f"\nMessage:\n{result2['message']}")
        
        if result2['finishReason'] == 'length':
            print("\n⚠️  WARNING: Output was truncated due to token limit!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "-"*80)
    
    # Test 3: Comprehensive analysis with max tokens
    print("\nTEST 3: Comprehensive analysis with max output tokens")
    print("-"*80)
    
    try:
        result3 = bedrock.invoke_pegasus_analysis(
            s3_uri=test_video_uri,
            prompt=(
                "Provide a comprehensive analysis of this video. Include:\n"
                "1. What happens at the beginning\n"
                "2. What happens in the middle\n"
                "3. What happens at the end\n"
                "4. Key themes and topics throughout\n"
                "5. Any notable moments or transitions"
            ),
            temperature=0.2,
            max_output_tokens=4096  # Maximum allowed
        )
        
        print(f"\nFinish Reason: {result3['finishReason']}")
        print(f"Message Length: {len(result3['message'])} characters")
        print(f"\nMessage:\n{result3['message']}")
        
        if result3['finishReason'] == 'length':
            print("\n⚠️  WARNING: Output was truncated even with max tokens!")
            print("This suggests the video content exceeds what can be described in 4096 tokens.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("\n" + "-"*80)
    
    # Test 4: Specific timestamp query
    print("\nTEST 4: Query about specific timestamp")
    print("-"*80)
    
    timestamp = input("\nEnter a timestamp to query (e.g., '2:30' or press Enter to skip): ").strip()
    
    if timestamp:
        try:
            result4 = bedrock.invoke_pegasus_analysis(
                s3_uri=test_video_uri,
                prompt=f"What is happening at timestamp {timestamp} in this video? Describe in detail.",
                temperature=0.2
            )
            
            print(f"\nFinish Reason: {result4['finishReason']}")
            print(f"Message Length: {len(result4['message'])} characters")
            print(f"\nMessage:\n{result4['message']}")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
    else:
        print("Skipped timestamp test")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    
    print("\n📊 OBSERVATIONS TO NOTE:")
    print("1. Did any queries hit the token limit (finishReason='length')?")
    print("2. Did queries about the end of the video provide accurate information?")
    print("3. Did the comprehensive analysis cover the entire video?")
    print("4. Was there any indication of focusing on the beginning vs. end?")
    print("\n💡 RECOMMENDATIONS:")
    print("- If outputs are truncated: Token limit is the issue")
    print("- If end-of-video queries are vague: Model may not process entire video equally")
    print("- If comprehensive analysis is shallow: Single-pass limitation")
    print("- If all queries work well: Issue may be in prompt design or application logic")


async def test_video_duration_impact():
    """Test how video duration affects analysis quality."""
    
    print("\n" + "="*80)
    print("VIDEO DURATION IMPACT TEST")
    print("="*80)
    
    config_path = os.environ.get("CONFIG_PATH", "config.local.yaml")
    config = Config.load_from_file(config_path)
    bedrock = BedrockClient(config)
    
    print("\nThis test compares analysis quality for videos of different lengths.")
    print("You'll need to provide S3 URIs for videos of different durations.")
    
    videos = []
    for i in range(3):
        uri = input(f"\nEnter S3 URI for video {i+1} (or press Enter to finish): ").strip()
        if not uri:
            break
        duration = input(f"Enter approximate duration for video {i+1} (e.g., '30s', '5m', '30m'): ").strip()
        videos.append({"uri": uri, "duration": duration})
    
    if not videos:
        print("\nNo videos provided. Skipping duration test.")
        return
    
    query = "Provide a detailed summary of this video, covering beginning, middle, and end."
    
    for i, video in enumerate(videos, 1):
        print(f"\n{'-'*80}")
        print(f"VIDEO {i}: Duration ~{video['duration']}")
        print(f"URI: {video['uri']}")
        print(f"{'-'*80}")
        
        try:
            result = bedrock.invoke_pegasus_analysis(
                s3_uri=video['uri'],
                prompt=query,
                temperature=0.2,
                max_output_tokens=4096
            )
            
            print(f"\nFinish Reason: {result['finishReason']}")
            print(f"Message Length: {len(result['message'])} characters")
            print(f"Tokens Used: ~{len(result['message']) // 4} (approximate)")
            
            if result['finishReason'] == 'length':
                print("⚠️  Output truncated!")
            
            print(f"\nSummary Preview (first 500 chars):")
            print(result['message'][:500] + "...")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    print("\n" + "="*80)
    print("DURATION TEST COMPLETE")
    print("="*80)
    print("\n📊 Compare the results:")
    print("- Do longer videos hit the token limit more often?")
    print("- Is the analysis quality consistent across durations?")
    print("- Do longer videos get less detailed coverage?")


def main():
    """Run the investigation tests."""
    
    print("\n🔍 PEGASUS SINGLE VIDEO ANALYSIS INVESTIGATION")
    print("\nThis script tests different aspects of Pegasus video analysis")
    print("to determine why single video analysis may produce limited results.")
    
    print("\n📋 Available Tests:")
    print("1. Analysis variations (different prompts and queries)")
    print("2. Video duration impact (compare short vs long videos)")
    print("3. Both tests")
    
    choice = input("\nSelect test (1, 2, or 3): ").strip()
    
    if choice == "1":
        asyncio.run(test_pegasus_analysis_variations())
    elif choice == "2":
        asyncio.run(test_video_duration_impact())
    elif choice == "3":
        asyncio.run(test_pegasus_analysis_variations())
        asyncio.run(test_video_duration_impact())
    else:
        print("\nInvalid choice. Exiting.")


if __name__ == "__main__":
    main()
