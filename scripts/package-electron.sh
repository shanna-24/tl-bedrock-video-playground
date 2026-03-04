#!/bin/bash
# Package the Electron app with Python backend
# This script builds both frontend and backend, then packages everything

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "Packaging Electron App"
echo "=========================================="

# Step 1: Build Python bundle
echo ""
echo "Step 1: Building Python bundle..."
bash "$SCRIPT_DIR/build-python-bundle.sh"

# Step 2: Download ffmpeg
echo ""
echo "Step 2: Downloading ffmpeg..."
bash "$SCRIPT_DIR/download-ffmpeg.sh"

# Step 3: Build frontend
echo ""
echo "Step 3: Building frontend..."
cd "$PROJECT_ROOT/frontend"
npm run build

# Step 4: Package with electron-builder
echo ""
echo "Step 4: Packaging Electron app..."
npm run electron:build

echo ""
echo "=========================================="
echo "Packaging complete!"
echo "=========================================="
echo ""
echo "Output location: $PROJECT_ROOT/frontend/dist-electron"
