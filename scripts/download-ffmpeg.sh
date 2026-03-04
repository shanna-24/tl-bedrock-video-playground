#!/bin/bash
# Download ffmpeg binary for local development/testing
# This script is useful if you don't have ffmpeg installed system-wide

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FFMPEG_DIR="$PROJECT_ROOT/build/ffmpeg"

echo "Downloading ffmpeg for local development..."

# Detect platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    PLATFORM="windows"
else
    echo "Unsupported platform: $OSTYPE"
    exit 1
fi

echo "Platform: $PLATFORM"

# Create directory
mkdir -p "$FFMPEG_DIR"

# Download ffmpeg
if [[ "$PLATFORM" == "macos" ]]; then
    echo "Downloading ffmpeg for macOS..."
    FFMPEG_URL="https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
    curl -L "$FFMPEG_URL" -o "$FFMPEG_DIR/ffmpeg.zip"
    unzip -o "$FFMPEG_DIR/ffmpeg.zip" -d "$FFMPEG_DIR"
    chmod +x "$FFMPEG_DIR/ffmpeg"
    rm "$FFMPEG_DIR/ffmpeg.zip"
    
    echo "Downloading ffprobe for macOS..."
    FFPROBE_URL="https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"
    curl -L "$FFPROBE_URL" -o "$FFMPEG_DIR/ffprobe.zip"
    unzip -o "$FFMPEG_DIR/ffprobe.zip" -d "$FFMPEG_DIR"
    chmod +x "$FFMPEG_DIR/ffprobe"
    rm "$FFMPEG_DIR/ffprobe.zip"
elif [[ "$PLATFORM" == "linux" ]]; then
    echo "Downloading ffmpeg for Linux..."
    FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    curl -L "$FFMPEG_URL" -o "$FFMPEG_DIR/ffmpeg.tar.xz"
    tar -xf "$FFMPEG_DIR/ffmpeg.tar.xz" -C "$FFMPEG_DIR" --strip-components=1
    chmod +x "$FFMPEG_DIR/ffmpeg"
    rm "$FFMPEG_DIR/ffmpeg.tar.xz"
elif [[ "$PLATFORM" == "windows" ]]; then
    echo "Downloading ffmpeg for Windows..."
    FFMPEG_URL="https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    curl -L "$FFMPEG_URL" -o "$FFMPEG_DIR/ffmpeg.zip"
    unzip -o "$FFMPEG_DIR/ffmpeg.zip" -d "$FFMPEG_DIR"
    mv "$FFMPEG_DIR"/ffmpeg-*-essentials_build/bin/ffmpeg.exe "$FFMPEG_DIR/"
    rm -rf "$FFMPEG_DIR"/ffmpeg-*-essentials_build "$FFMPEG_DIR/ffmpeg.zip"
fi

echo ""
echo "ffmpeg downloaded to: $FFMPEG_DIR/ffmpeg"
echo ""
echo "To use this ffmpeg, set the environment variable:"
echo "  export FFMPEG_PATH=$FFMPEG_DIR/ffmpeg"
echo ""
echo "Or install system-wide:"
echo "  macOS: brew install ffmpeg"
echo "  Linux: apt-get install ffmpeg"
echo "  Windows: Download from https://ffmpeg.org/download.html"
