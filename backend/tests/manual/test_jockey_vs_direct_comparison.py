"""
Manual test to compare Jockey orchestration vs direct Pegasus analysis.

This test helps validate whether the Jockey approach actually provides better results
for single video analysis compared to direct Pegasus invocation.

Run with:
    cd backend
    CONFIG_PATH=../config.local.yaml python tests/manual/test_jockey_vs_direct_comparison.py
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

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
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient
from config import Config
from services.analysis_service import AnalysisService
from services.search_service import SearchService


async def compare_analysis_approaches():
    """Compare direct Pegasus vs Jockey orchestration for single video analysis."""
    
    print("\n" + "="*80)
    print("JOCKEY VS DIRECT PEGASUS COMPARISON")
    print("="*80)
    
    # Initialize services - use load_from_file method
    config_path = os.environ.get("CONFIG_PATH", "config.local.yaml")
    config = Config.load_from_file(config_path)
    bedrock = BedrockClient(config)
    s3 = S3Client(config)
    s3_vectors = S3VectorsClient(config)
    
    # Get test parameters
    print("\n📋 Test Setup")
    print("-"*80)
    
    video_id = input("Enter video ID: ").strip()
    if not video_id:
        print("No video ID provided. Exiting.")
        return
    
    video_s3_uri = input("Enter video S3 URI: ").strip()
    if not video_s3_uri:
        print("No S3 URI provided. Exiting.")
        return
    
    index_id = input("Enter index ID (for Jockey test): ").strip()
    if not index_id:
        print("No index ID provided. Exiting.")
        return
    
    query = input("Enter analysis query: ").strip()
    if not query:
        query = "Provide a comprehensive summary of this video, including key events from beginning to end."
        print(f"Using default query: {query}")
    
    verbosity = input("Enter verbosity (concise/extended, default: extended): ").strip() or "extended"
    
    print("\n" + "="*80)
    
    # Test 1: Direct Pegasus Analysis
    print("\n🔵 TEST 1: DIRECT PEGASUS ANALYSIS")
    print("-"*80)
    print("Using: Direct invoke_pegasus_analysis()")
    print(f"Query: {query}")
    print(f"Verbosity: {verbosity}")
    
    direct_start = datetime.now()
    
    try:
        # Add verbosity instruction
        verbosity_instruction = (
            "Provide a brief, focused response with key insights only."
            if verbosity == "concise"
            else "Provide a detailed, comprehensive analysis with thorough explanations and examples."
        )
        
        enhanced_query = f"{verbosity_instruction}\n\n{query}"
        
        direct_result = bedrock.invoke_pegasus_analysis(
            s3_uri=video_s3_uri,
            prompt=enhanced_query,
            temperature=0.2,
            max_output_tokens=4096
        )
        
        direct_duration = (datetime.now() - direct_start).total_seconds()
        
        print(f"\n✅ Direct analysis completed in {direct_duration:.2f}s")
        print(f"Finish Reason: {direct_result['finishReason']}")
        print(f"Message Length: {len(direct_result['message'])} characters")
        print(f"Estimated Tokens: ~{len(direct_result['message']) // 4}")
        
        if direct_result['finishReason'] == 'length':
            print("\n⚠️  WARNING: Output was truncated due to token limit!")
        
        print(f"\n📄 Direct Pegasus Result:")
        print("-"*80)
        print(direct_result['message'])
        print("-"*80)
        
    except Exception as e:
        print(f"\n❌ Direct analysis failed: {e}")
        direct_result = None
        direct_duration = 0
    
    # Test 2: Jockey Orchestration
    print("\n\n🟢 TEST 2: JOCKEY ORCHESTRATION")
    print("-"*80)
    print("Using: JockeyOrchestrator with semantic search + multi-segment analysis")
    print(f"Query: {query}")
    print(f"Verbosity: {verbosity}")
    
    jockey_start = datetime.now()
    
    try:
        # Initialize services for Jockey
        search_service = SearchService(
            bedrock_client=bedrock,
            s3_vectors_client=s3_vectors,
            s3_client=s3,
            config=config
        )
        
        analysis_service = AnalysisService(
            bedrock_client=bedrock,
            s3_client=s3,
            config=config,
            search_service=search_service
        )
        
        # Check if Jockey is enabled
        if not config.jockey.enabled:
            print("\n⚠️  WARNING: Jockey is disabled in config!")
            print("Enable it in config.local.yaml: jockey.enabled = true")
            jockey_result = None
        else:
            # Run Jockey analysis
            jockey_result = await analysis_service.analyze_video(
                video_id=video_id,
                query=query,
                video_s3_uri=video_s3_uri,
                index_id=index_id,
                verbosity=verbosity,
                temperature=0.2
            )
            
            jockey_duration = (datetime.now() - jockey_start).total_seconds()
            
            print(f"\n✅ Jockey analysis completed in {jockey_duration:.2f}s")
            print(f"Insights Length: {len(jockey_result.insights)} characters")
            print(f"Jockey Enabled: {jockey_result.metadata.get('jockey_enabled', False)}")
            print(f"Single Video Jockey: {jockey_result.metadata.get('single_video_jockey', False)}")
            
            print(f"\n📄 Jockey Result:")
            print("-"*80)
            print(jockey_result.insights)
            print("-"*80)
            
            # Show metadata
            if jockey_result.metadata:
                print(f"\n📊 Metadata:")
                for key, value in jockey_result.metadata.items():
                    if key not in ['video_s3_uri']:
                        print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"\n❌ Jockey analysis failed: {e}")
        import traceback
        traceback.print_exc()
        jockey_result = None
        jockey_duration = 0
    
    # Comparison
    print("\n\n" + "="*80)
    print("📊 COMPARISON SUMMARY")
    print("="*80)
    
    if direct_result and jockey_result:
        print(f"\n⏱️  Performance:")
        print(f"  Direct Pegasus: {direct_duration:.2f}s")
        print(f"  Jockey:         {jockey_duration:.2f}s")
        print(f"  Difference:     {abs(jockey_duration - direct_duration):.2f}s")
        
        print(f"\n📏 Output Length:")
        print(f"  Direct Pegasus: {len(direct_result['message'])} characters")
        print(f"  Jockey:         {len(jockey_result.insights)} characters")
        print(f"  Difference:     {len(jockey_result.insights) - len(direct_result['message'])} characters")
        
        print(f"\n🎯 Quality Indicators:")
        print(f"  Direct truncated: {'Yes' if direct_result['finishReason'] == 'length' else 'No'}")
        print(f"  Jockey used orchestration: {jockey_result.metadata.get('jockey_enabled', False)}")
        
        print("\n\n💡 EVALUATION QUESTIONS:")
        print("-"*80)
        print("1. Does Jockey provide more comprehensive coverage?")
        print("2. Does Jockey mention content from throughout the video (not just beginning)?")
        print("3. Is the Jockey output more detailed and relevant?")
        print("4. Did Direct Pegasus hit the token limit?")
        print("5. Does Jockey better answer the specific query?")
        
        print("\n📝 Manual Review:")
        print("Compare the two outputs above and assess:")
        print("- Comprehensiveness (does it cover the whole video?)")
        print("- Relevance (does it answer the query?)")
        print("- Detail level (is it thorough enough?)")
        print("- Accuracy (is the information correct?)")
        
    elif direct_result:
        print("\n⚠️  Only direct Pegasus completed successfully")
        print("Cannot perform comparison")
    elif jockey_result:
        print("\n⚠️  Only Jockey completed successfully")
        print("Cannot perform comparison")
    else:
        print("\n❌ Both approaches failed")
        print("Check error messages above")
    
    print("\n" + "="*80)


async def test_multiple_queries():
    """Test multiple different queries to see consistency."""
    
    print("\n" + "="*80)
    print("MULTIPLE QUERY COMPARISON TEST")
    print("="*80)
    
    config_path = os.environ.get("CONFIG_PATH", "config.local.yaml")
    config = Config.load_from_file(config_path)
    bedrock = BedrockClient(config)
    s3 = S3Client(config)
    s3_vectors = S3VectorsClient(config)
    
    video_id = input("\nEnter video ID: ").strip()
    video_s3_uri = input("Enter video S3 URI: ").strip()
    index_id = input("Enter index ID: ").strip()
    
    if not all([video_id, video_s3_uri, index_id]):
        print("Missing required parameters. Exiting.")
        return
    
    # Test queries
    test_queries = [
        "What happens at the beginning of this video?",
        "What happens in the middle of this video?",
        "What happens at the end of this video?",
        "Summarize the entire video from start to finish.",
        "What are the main topics or themes in this video?"
    ]
    
    print("\n📋 Testing with multiple queries:")
    for i, q in enumerate(test_queries, 1):
        print(f"{i}. {q}")
    
    # Initialize services
    search_service = SearchService(
        bedrock_client=bedrock,
        s3_vectors_client=s3_vectors,
        s3_client=s3,
        config=config
    )
    
    analysis_service = AnalysisService(
        bedrock_client=bedrock,
        s3_client=s3,
        config=config,
        search_service=search_service
    )
    
    results = []
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"QUERY {i}: {query}")
        print('='*80)
        
        # Direct Pegasus
        print("\n🔵 Direct Pegasus:")
        try:
            direct = bedrock.invoke_pegasus_analysis(
                s3_uri=video_s3_uri,
                prompt=query,
                temperature=0.2
            )
            print(f"✅ Length: {len(direct['message'])} chars, Finish: {direct['finishReason']}")
            print(f"Preview: {direct['message'][:200]}...")
        except Exception as e:
            print(f"❌ Failed: {e}")
            direct = None
        
        # Jockey
        print("\n🟢 Jockey:")
        try:
            jockey = await analysis_service.analyze_video(
                video_id=video_id,
                query=query,
                video_s3_uri=video_s3_uri,
                index_id=index_id,
                verbosity="extended"
            )
            print(f"✅ Length: {len(jockey.insights)} chars")
            print(f"Preview: {jockey.insights[:200]}...")
        except Exception as e:
            print(f"❌ Failed: {e}")
            jockey = None
        
        results.append({
            "query": query,
            "direct": direct,
            "jockey": jockey
        })
    
    print("\n\n" + "="*80)
    print("📊 MULTI-QUERY SUMMARY")
    print("="*80)
    
    for i, result in enumerate(results, 1):
        print(f"\nQuery {i}: {result['query']}")
        if result['direct']:
            print(f"  Direct: {len(result['direct']['message'])} chars, {result['direct']['finishReason']}")
        else:
            print(f"  Direct: Failed")
        
        if result['jockey']:
            print(f"  Jockey: {len(result['jockey'].insights)} chars")
        else:
            print(f"  Jockey: Failed")


def main():
    """Run comparison tests."""
    
    print("\n🔍 JOCKEY VS DIRECT PEGASUS COMPARISON")
    print("\nThis script compares the quality and coverage of:")
    print("1. Direct Pegasus analysis (single invocation)")
    print("2. Jockey orchestration (semantic search + multi-segment)")
    
    print("\n📋 Available Tests:")
    print("1. Single query comparison (detailed)")
    print("2. Multiple query comparison (coverage test)")
    print("3. Both tests")
    
    choice = input("\nSelect test (1, 2, or 3): ").strip()
    
    if choice == "1":
        asyncio.run(compare_analysis_approaches())
    elif choice == "2":
        asyncio.run(test_multiple_queries())
    elif choice == "3":
        asyncio.run(compare_analysis_approaches())
        asyncio.run(test_multiple_queries())
    else:
        print("\nInvalid choice. Exiting.")


if __name__ == "__main__":
    main()
