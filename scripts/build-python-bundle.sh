#!/bin/bash
# Build a standalone Python bundle for Electron app
# This script creates a relocatable Python environment with all dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
PYTHON_BUNDLE_DIR="$BUILD_DIR/python-bundle"

echo "Building Python bundle for Electron app..."

# Clean previous build
rm -rf "$PYTHON_BUNDLE_DIR"
mkdir -p "$PYTHON_BUNDLE_DIR"

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

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv "$PYTHON_BUNDLE_DIR"

# Activate virtual environment
if [[ "$PLATFORM" == "windows" ]]; then
    source "$PYTHON_BUNDLE_DIR/Scripts/activate"
else
    source "$PYTHON_BUNDLE_DIR/bin/activate"
fi

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing Python dependencies..."
pip install -r "$PROJECT_ROOT/backend/requirements.txt"

# Install PyInstaller for creating standalone executables (optional alternative)
pip install pyinstaller

echo "Python bundle created successfully at: $PYTHON_BUNDLE_DIR"
echo ""
echo "Bundle size:"
du -sh "$PYTHON_BUNDLE_DIR"

# Download ffmpeg binary for the platform
echo "Downloading ffmpeg binary..."
FFMPEG_DIR="$BUILD_DIR/ffmpeg"
mkdir -p "$FFMPEG_DIR"

if [[ "$PLATFORM" == "macos" ]]; then
    # Check if ffmpeg is already installed via Homebrew
    if command -v ffmpeg &> /dev/null; then
        echo "Found system ffmpeg, copying to bundle..."
        SYSTEM_FFMPEG=$(which ffmpeg)
        cp "$SYSTEM_FFMPEG" "$FFMPEG_DIR/ffmpeg"
        chmod +x "$FFMPEG_DIR/ffmpeg"
    else
        echo "ERROR: ffmpeg not found. Please install it first:"
        echo "  brew install ffmpeg"
        echo ""
        echo "Alternatively, download manually from:"
        echo "  https://evermeet.cx/ffmpeg/"
        echo "  and place the binary in: $FFMPEG_DIR/ffmpeg"
        exit 1
    fi
elif [[ "$PLATFORM" == "linux" ]]; then
    # Check if ffmpeg is installed
    if command -v ffmpeg &> /dev/null; then
        echo "Found system ffmpeg, copying to bundle..."
        SYSTEM_FFMPEG=$(which ffmpeg)
        cp "$SYSTEM_FFMPEG" "$FFMPEG_DIR/ffmpeg"
        chmod +x "$FFMPEG_DIR/ffmpeg"
    else
        # Try to download static build
        echo "Downloading static ffmpeg build for Linux..."
        FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
        curl -L "$FFMPEG_URL" -o "$FFMPEG_DIR/ffmpeg.tar.xz"
        tar -xf "$FFMPEG_DIR/ffmpeg.tar.xz" -C "$FFMPEG_DIR" --strip-components=1
        chmod +x "$FFMPEG_DIR/ffmpeg"
        rm "$FFMPEG_DIR/ffmpeg.tar.xz"
    fi
elif [[ "$PLATFORM" == "windows" ]]; then
    # For Windows, try to copy system ffmpeg or provide instructions
    if command -v ffmpeg &> /dev/null; then
        echo "Found system ffmpeg, copying to bundle..."
        SYSTEM_FFMPEG=$(which ffmpeg)
        cp "$SYSTEM_FFMPEG" "$FFMPEG_DIR/ffmpeg.exe"
    else
        echo "ERROR: ffmpeg not found. Please install it first or download from:"
        echo "  https://www.gyan.dev/ffmpeg/builds/"
        echo "  and place ffmpeg.exe in: $FFMPEG_DIR/"
        exit 1
    fi
fi

echo "ffmpeg binary ready at: $FFMPEG_DIR"

# Create a marker file with build info
cat > "$PYTHON_BUNDLE_DIR/BUILD_INFO.txt" << EOF
Build Date: $(date)
Platform: $PLATFORM
Python Version: $(python --version)
Pip Version: $(pip --version)
FFmpeg: Bundled in $FFMPEG_DIR
EOF

echo ""
echo "Build complete!"
