"""Compliance configuration loader utility.

This module handles automatic uploading of compliance configuration files
to S3 if they don't already exist. This ensures the compliance feature
works out-of-the-box for new deployments.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# S3 prefix for compliance configuration files
COMPLIANCE_CONFIG_S3_PREFIX = "compliance/configuration/"

# Required compliance config files
REQUIRED_CONFIG_FILES = [
    "compliance_params.json",
    "moral_standards_check.json",
    "video_content_check.json",
]

# Optional compliance config files
OPTIONAL_CONFIG_FILES = [
    "content_relevance_check.json",
]


def get_bundled_config_dir() -> Optional[Path]:
    """Get the path to bundled compliance config files.
    
    Checks multiple locations to support different deployment scenarios:
    1. Development: backend/compliance_config/
    2. Docker/Production: /app/compliance_config/ or relative to src/
    3. Electron: Resources path
    
    Returns:
        Path to config directory or None if not found
    """
    # Try relative to this file (development and most deployments)
    src_dir = Path(__file__).parent.parent  # backend/src/
    backend_dir = src_dir.parent  # backend/
    
    possible_paths = [
        backend_dir / "compliance_config",  # backend/compliance_config/
        Path("/app/compliance_config"),  # Docker absolute path
        src_dir / "compliance_config",  # If copied to src/
    ]
    
    for path in possible_paths:
        if path.exists() and path.is_dir():
            logger.debug(f"Found compliance config directory at: {path}")
            return path
    
    logger.warning(f"Compliance config directory not found. Searched: {possible_paths}")
    return None


def check_config_exists_in_s3(s3_client, bucket_name: str, filename: str) -> bool:
    """Check if a compliance config file exists in S3.
    
    Args:
        s3_client: boto3 S3 client
        bucket_name: S3 bucket name
        filename: Config filename (e.g., 'compliance_params.json')
        
    Returns:
        True if file exists, False otherwise
    """
    s3_key = f"{COMPLIANCE_CONFIG_S3_PREFIX}{filename}"
    try:
        s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        return True
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        # Re-raise other errors
        raise


def upload_config_to_s3(s3_client, bucket_name: str, local_path: Path, filename: str) -> bool:
    """Upload a compliance config file to S3.
    
    Args:
        s3_client: boto3 S3 client
        bucket_name: S3 bucket name
        local_path: Path to local config file
        filename: Config filename for S3 key
        
    Returns:
        True if upload successful, False otherwise
    """
    s3_key = f"{COMPLIANCE_CONFIG_S3_PREFIX}{filename}"
    try:
        with open(local_path, 'r') as f:
            content = f.read()
            # Validate JSON
            json.loads(content)
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=content.encode('utf-8'),
            ContentType='application/json'
        )
        logger.info(f"Uploaded compliance config: s3://{bucket_name}/{s3_key}")
        return True
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {local_path}: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to upload {filename} to S3: {e}")
        return False


def ensure_compliance_config_in_s3(s3_client, bucket_name: str) -> dict:
    """Ensure compliance configuration files exist in S3.
    
    If config files don't exist in S3, upload them from the bundled
    config directory. This enables out-of-the-box compliance functionality.
    
    Args:
        s3_client: boto3 S3 client (the raw client, not S3Client wrapper)
        bucket_name: S3 bucket name
        
    Returns:
        dict with status information:
        {
            'checked': int,  # Number of files checked
            'uploaded': int,  # Number of files uploaded
            'skipped': int,  # Number of files already in S3
            'failed': int,   # Number of files that failed to upload
            'missing_local': int,  # Number of files not found locally
        }
    """
    result = {
        'checked': 0,
        'uploaded': 0,
        'skipped': 0,
        'failed': 0,
        'missing_local': 0,
    }
    
    config_dir = get_bundled_config_dir()
    if config_dir is None:
        logger.warning(
            "Compliance config directory not found. "
            "Compliance feature may not work until config files are uploaded to S3."
        )
        return result
    
    all_files = REQUIRED_CONFIG_FILES + OPTIONAL_CONFIG_FILES
    
    for filename in all_files:
        result['checked'] += 1
        local_path = config_dir / filename
        
        # Check if file exists locally
        if not local_path.exists():
            if filename in REQUIRED_CONFIG_FILES:
                logger.warning(f"Required compliance config file not found locally: {local_path}")
                result['missing_local'] += 1
            else:
                logger.debug(f"Optional compliance config file not found locally: {local_path}")
            continue
        
        # Check if file already exists in S3
        try:
            if check_config_exists_in_s3(s3_client, bucket_name, filename):
                logger.debug(f"Compliance config already in S3: {filename}")
                result['skipped'] += 1
                continue
        except Exception as e:
            logger.error(f"Error checking S3 for {filename}: {e}")
            result['failed'] += 1
            continue
        
        # Upload file to S3
        if upload_config_to_s3(s3_client, bucket_name, local_path, filename):
            result['uploaded'] += 1
        else:
            result['failed'] += 1
    
    # Log summary
    if result['uploaded'] > 0:
        logger.info(
            f"Compliance config sync complete: "
            f"{result['uploaded']} uploaded, {result['skipped']} already existed"
        )
    elif result['skipped'] > 0:
        logger.info(f"Compliance config already in S3 ({result['skipped']} files)")
    
    if result['failed'] > 0:
        logger.warning(f"Failed to upload {result['failed']} compliance config files")
    
    return result
