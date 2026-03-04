#!/bin/bash
# Upload compliance configuration files to S3
#
# Usage:
#   ./scripts/upload-compliance-config.sh <bucket-name> [region]
#
# Example:
#   ./scripts/upload-compliance-config.sh tl-video-playground-local us-east-1

set -e

BUCKET_NAME=$1
REGION=${2:-us-east-1}
CONFIG_DIR="backend/compliance_config"
S3_PREFIX="compliance/configuration"

if [ -z "$BUCKET_NAME" ]; then
    echo "Error: Bucket name is required"
    echo ""
    echo "Usage: $0 <bucket-name> [region]"
    echo ""
    echo "Example:"
    echo "  $0 tl-video-playground-local us-east-1"
    exit 1
fi

# Check if config directory exists
if [ ! -d "$CONFIG_DIR" ]; then
    echo "Error: Config directory not found: $CONFIG_DIR"
    echo "Run this script from the project root directory."
    exit 1
fi

echo "Uploading compliance configuration to s3://$BUCKET_NAME/$S3_PREFIX/"
echo ""

# Required files
REQUIRED_FILES=(
    "compliance_params.json"
    "moral_standards_check.json"
    "video_content_check.json"
)

# Optional files
OPTIONAL_FILES=(
    "content_relevance_check.json"
)

# Upload required files
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$CONFIG_DIR/$file" ]; then
        echo "Uploading $file..."
        aws s3 cp "$CONFIG_DIR/$file" "s3://$BUCKET_NAME/$S3_PREFIX/$file" --region "$REGION"
    else
        echo "Error: Required file not found: $CONFIG_DIR/$file"
        exit 1
    fi
done

# Upload optional files
for file in "${OPTIONAL_FILES[@]}"; do
    if [ -f "$CONFIG_DIR/$file" ]; then
        echo "Uploading $file (optional)..."
        aws s3 cp "$CONFIG_DIR/$file" "s3://$BUCKET_NAME/$S3_PREFIX/$file" --region "$REGION"
    else
        echo "Skipping optional file: $file (not found)"
    fi
done

echo ""
echo "✓ Compliance configuration uploaded successfully!"
echo ""
echo "Files uploaded to:"
aws s3 ls "s3://$BUCKET_NAME/$S3_PREFIX/" --region "$REGION"
