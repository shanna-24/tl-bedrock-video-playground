#!/bin/bash
# Start the backend server
# This script must be run from the backend directory

cd src
CONFIG_PATH=../../config.local.yaml python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
