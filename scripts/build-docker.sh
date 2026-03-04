#!/bin/bash
# Build Docker image for TwelveLabs Video Archive
#
# Usage:
#   ./scripts/build-docker.sh [tag]
#
# Examples:
#   ./scripts/build-docker.sh                    # Build with default tag
#   ./scripts/build-docker.sh v1.0.0             # Build with specific tag
#   ./scripts/build-docker.sh latest             # Build with 'latest' tag

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default image name and tag
IMAGE_NAME="tl-video-playground"
TAG="${1:-latest}"

echo "=========================================="
echo "Building Docker Image"
echo "=========================================="
echo "Image: ${IMAGE_NAME}:${TAG}"
echo ""

cd "$PROJECT_ROOT"

# Build the image
docker build \
    -t "${IMAGE_NAME}:${TAG}" \
    -f Dockerfile \
    .

echo ""
echo "=========================================="
echo "Build Complete!"
echo "=========================================="
echo ""
echo "Image: ${IMAGE_NAME}:${TAG}"
echo ""
echo "To run the container:"
echo ""
echo "  docker run -d \\"
echo "    --name tl-video-playground \\"
echo "    -p 8000:8000 \\"
echo "    -e AWS_ACCESS_KEY_ID=\"your-key\" \\"
echo "    -e AWS_SECRET_ACCESS_KEY=\"your-secret\" \\"
echo "    -e AWS_REGION=\"us-east-1\" \\"
echo "    -v \$(pwd)/config.yaml:/app/config.yaml:ro \\"
echo "    -e CONFIG_PATH=/app/config.yaml \\"
echo "    ${IMAGE_NAME}:${TAG}"
echo ""
echo "See docs/DOCKER_QUICKSTART.md for full setup instructions."
