#!/bin/bash
# Quick start script for Electron development
# Starts both Vite dev server and Electron app

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Starting Electron development environment..."
echo ""

# Check if dependencies are installed
if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd "$PROJECT_ROOT/frontend"
    npm install
fi

# Start development
cd "$PROJECT_ROOT/frontend"
echo ""
echo "Starting Vite dev server and Electron..."
echo "Press Ctrl+C to stop"
echo ""

npm run electron:dev
