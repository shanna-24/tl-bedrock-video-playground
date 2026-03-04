#!/usr/bin/env python3
"""Configure CORS for S3 bucket to allow frontend to load images and videos.

This script configures the S3 bucket with CORS rules that allow the frontend
application to load thumbnails and videos from presigned URLs.
"""

import sys
import boto3
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import load_config


def configure_cors(bucket_name: str, frontend_url: str = "http://localhost:5173"):
    """Configure CORS for the S3 bucket.
    
    Args:
        bucket_name: Name of the S3 bucket
        frontend_url: URL of the frontend application
    """
    s3_client = boto3.client('s3')
    
    cors_configuration = {
        'CORSRules': [
            {
                'AllowedHeaders': ['*'],
                'AllowedMethods': ['GET', 'HEAD'],
                'AllowedOrigins': [
                    frontend_url,
                    'http://localhost:5173',  # Vite dev server
                    'http://localhost:3000',  # Alternative dev port
                ],
                'ExposeHeaders': [
                    'ETag',
                    'Content-Length',
                    'Content-Type'
                ],
                'MaxAgeSeconds': 3600
            }
        ]
    }
    
    try:
        s3_client.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration=cors_configuration
        )
        print(f"✓ CORS configuration applied to bucket: {bucket_name}")
        print(f"  Allowed origins: {', '.join(cors_configuration['CORSRules'][0]['AllowedOrigins'])}")
        return True
    except Exception as e:
        print(f"✗ Failed to configure CORS: {e}")
        return False


def main():
    """Main entry point."""
    # Load configuration
    config = load_config()
    
    print("Configuring S3 CORS...")
    print(f"Bucket: {config.s3_bucket_name}")
    
    # Configure CORS
    success = configure_cors(config.s3_bucket_name)
    
    if success:
        print("\n✓ CORS configuration complete!")
        print("\nThe frontend can now load:")
        print("  - Video thumbnails from presigned URLs")
        print("  - Video streams from presigned URLs")
    else:
        print("\n✗ CORS configuration failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
