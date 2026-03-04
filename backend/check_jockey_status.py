#!/usr/bin/env python3
"""
Diagnostic script to check if Jockey orchestration is properly configured.

Run this script to verify:
1. Configuration is loaded correctly
2. JockeyOrchestrator can be imported
3. All dependencies are available
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def check_config():
    """Check if configuration is loaded correctly."""
    print("=" * 60)
    print("1. Checking Configuration")
    print("=" * 60)
    
    try:
        from config import load_config
        config = load_config('config.local.yaml')
        
        print(f"✓ Configuration loaded successfully")
        print(f"  - jockey.enabled: {config.jockey.enabled}")
        print(f"  - jockey.claude_model_id: {config.jockey.claude_model_id}")
        print(f"  - jockey.web_search_enabled: {config.jockey.web_search_enabled}")
        print(f"  - jockey.parallel_analysis_limit: {config.jockey.parallel_analysis_limit}")
        
        if not config.jockey.enabled:
            print("\n⚠️  WARNING: Jockey is DISABLED in configuration!")
            print("   Set jockey.enabled: true in config.local.yaml")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return False


def check_imports():
    """Check if all required modules can be imported."""
    print("\n" + "=" * 60)
    print("2. Checking Imports")
    print("=" * 60)
    
    imports_ok = True
    
    # Check JockeyOrchestrator
    try:
        from orchestration.orchestrator import JockeyOrchestrator
        print("✓ JockeyOrchestrator imported successfully")
    except Exception as e:
        print(f"✗ Failed to import JockeyOrchestrator: {e}")
        imports_ok = False
    
    # Check Aggregator
    try:
        from orchestration.aggregator import Aggregator
        print("✓ Aggregator imported successfully")
    except Exception as e:
        print(f"✗ Failed to import Aggregator: {e}")
        imports_ok = False
    
    # Check PegasusWorker
    try:
        from orchestration.pegasus_worker import PegasusWorker
        print("✓ PegasusWorker imported successfully")
    except Exception as e:
        print(f"✗ Failed to import PegasusWorker: {e}")
        imports_ok = False
    
    # Check WebSearchClient (optional)
    try:
        from services.web_search_client import WebSearchClient
        print("✓ WebSearchClient imported successfully (web search available)")
    except Exception as e:
        print(f"⚠️  WebSearchClient not available: {e}")
        print("   (This is OK if web search is disabled)")
    
    return imports_ok


def check_initialization():
    """Check if services can be initialized."""
    print("\n" + "=" * 60)
    print("3. Checking Service Initialization")
    print("=" * 60)
    
    try:
        from config import load_config
        from aws.bedrock_client import BedrockClient
        from aws.s3_client import S3Client
        from services.search_service import SearchService
        from aws.s3_vectors_client import S3VectorsClient
        from services.analysis_service import AnalysisService
        
        config = load_config('config.local.yaml')
        
        # Initialize clients (these will fail if AWS credentials are not configured)
        print("  Initializing AWS clients...")
        try:
            bedrock = BedrockClient(config)
            s3 = S3Client(config)
            s3_vectors = S3VectorsClient(config)
            print("  ✓ AWS clients initialized")
        except Exception as e:
            print(f"  ⚠️  AWS clients failed (this is OK for local testing): {e}")
            print("     Skipping service initialization test")
            return True
        
        # Initialize SearchService
        print("  Initializing SearchService...")
        search_service = SearchService(
            bedrock_client=bedrock,
            s3_vectors_client=s3_vectors,
            s3_client=s3,
            config=config
        )
        print("  ✓ SearchService initialized")
        
        # Initialize AnalysisService
        print("  Initializing AnalysisService...")
        analysis_service = AnalysisService(
            bedrock_client=bedrock,
            s3_client=s3,
            config=config,
            search_service=search_service
        )
        
        if analysis_service.orchestrator is not None:
            print("  ✓ AnalysisService initialized with JockeyOrchestrator")
            print(f"    - Orchestrator type: {type(analysis_service.orchestrator).__name__}")
            return True
        else:
            print("  ✗ AnalysisService initialized WITHOUT JockeyOrchestrator")
            print("    - orchestrator is None")
            print("    - Check application logs for initialization errors")
            return False
        
    except Exception as e:
        print(f"  ✗ Service initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all diagnostic checks."""
    print("\n" + "=" * 60)
    print("Jockey Orchestration Diagnostic Tool")
    print("=" * 60)
    
    config_ok = check_config()
    imports_ok = check_imports()
    init_ok = check_initialization()
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if config_ok and imports_ok and init_ok:
        print("✓ All checks passed!")
        print("  Jockey orchestration should be working correctly.")
        print("\nIf you're still seeing issues:")
        print("  1. Restart the application server")
        print("  2. Check application logs for errors")
        print("  3. Verify the index has multiple videos")
        return 0
    else:
        print("✗ Some checks failed!")
        print("\nTo fix:")
        if not config_ok:
            print("  - Enable Jockey in config.local.yaml")
        if not imports_ok:
            print("  - Fix import errors (see above)")
        if not init_ok:
            print("  - Check AWS credentials and configuration")
        print("  - Restart the application after making changes")
        return 1


if __name__ == "__main__":
    sys.exit(main())
