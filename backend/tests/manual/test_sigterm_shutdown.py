#!/usr/bin/env python3
"""
Manual test script for SIGTERM handling.

This script starts the FastAPI application in a subprocess and sends SIGTERM
to verify graceful shutdown behavior.

Usage:
    python tests/manual/test_sigterm_shutdown.py
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path

# Add src to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir / "src"))


def test_sigterm_shutdown():
    """Test that the application handles SIGTERM gracefully."""
    print("=" * 70)
    print("SIGTERM Graceful Shutdown Test")
    print("=" * 70)
    
    # Set config path
    config_path = backend_dir / ".." / "config.local.yaml"
    env = os.environ.copy()
    env["CONFIG_PATH"] = str(config_path)
    
    print(f"\n1. Starting FastAPI application...")
    print(f"   Config: {config_path}")
    
    # Start the application in a subprocess
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(backend_dir / "src"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print(f"   Process PID: {process.pid}")
    
    # Wait for application to start
    print("\n2. Waiting for application to start (5 seconds)...")
    startup_output = []
    start_time = time.time()
    
    while time.time() - start_time < 5:
        line = process.stdout.readline()
        if line:
            startup_output.append(line.strip())
            print(f"   {line.strip()}")
        
        # Check if application started successfully
        if "Application startup complete" in line or "Uvicorn running" in line:
            print("\n   ✓ Application started successfully!")
            break
    
    # Give it a moment to fully initialize
    time.sleep(2)
    
    # Send SIGTERM
    print(f"\n3. Sending SIGTERM to process {process.pid}...")
    process.send_signal(signal.SIGTERM)
    
    # Capture shutdown output
    print("\n4. Capturing shutdown output...")
    shutdown_output = []
    
    try:
        # Wait for process to exit (with timeout)
        remaining_output, _ = process.communicate(timeout=15)
        shutdown_output = remaining_output.strip().split('\n')
    except subprocess.TimeoutExpired:
        print("\n   ⚠ Process did not exit within 15 seconds, forcing termination...")
        process.kill()
        remaining_output, _ = process.communicate()
        shutdown_output = remaining_output.strip().split('\n')
    
    # Print shutdown output
    for line in shutdown_output:
        if line.strip():
            print(f"   {line.strip()}")
    
    # Analyze results
    print("\n" + "=" * 70)
    print("Test Results")
    print("=" * 70)
    
    # Check for expected shutdown messages
    all_output = '\n'.join(startup_output + shutdown_output)
    
    checks = {
        "Signal received": "Received SIGTERM signal" in all_output or "Received SIGINT signal" in all_output,
        "Processor stop initiated": "Stopping embedding job processor" in all_output or "Stopping EmbeddingJobProcessor" in all_output,
        "Graceful shutdown": "Shutting down" in all_output,
        "Process exited": process.returncode is not None
    }
    
    print("\nShutdown Checks:")
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
    
    # Overall result
    all_passed = all(checks.values())
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ SIGTERM HANDLING TEST PASSED")
        print("  The application handles SIGTERM gracefully and shuts down cleanly.")
    else:
        print("✗ SIGTERM HANDLING TEST FAILED")
        print("  Some shutdown checks did not pass. Review the output above.")
    print("=" * 70)
    
    return all_passed


def test_sigint_shutdown():
    """Test that the application handles SIGINT (Ctrl+C) gracefully."""
    print("\n\n" + "=" * 70)
    print("SIGINT (Ctrl+C) Graceful Shutdown Test")
    print("=" * 70)
    
    # Set config path
    config_path = backend_dir / ".." / "config.local.yaml"
    env = os.environ.copy()
    env["CONFIG_PATH"] = str(config_path)
    
    print(f"\n1. Starting FastAPI application...")
    print(f"   Config: {config_path}")
    
    # Start the application in a subprocess
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"],
        cwd=str(backend_dir / "src"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print(f"   Process PID: {process.pid}")
    
    # Wait for application to start
    print("\n2. Waiting for application to start (5 seconds)...")
    startup_output = []
    start_time = time.time()
    
    while time.time() - start_time < 5:
        line = process.stdout.readline()
        if line:
            startup_output.append(line.strip())
            print(f"   {line.strip()}")
        
        if "Application startup complete" in line or "Uvicorn running" in line:
            print("\n   ✓ Application started successfully!")
            break
    
    time.sleep(2)
    
    # Send SIGINT
    print(f"\n3. Sending SIGINT to process {process.pid}...")
    process.send_signal(signal.SIGINT)
    
    # Capture shutdown output
    print("\n4. Capturing shutdown output...")
    shutdown_output = []
    
    try:
        remaining_output, _ = process.communicate(timeout=15)
        shutdown_output = remaining_output.strip().split('\n')
    except subprocess.TimeoutExpired:
        print("\n   ⚠ Process did not exit within 15 seconds, forcing termination...")
        process.kill()
        remaining_output, _ = process.communicate()
        shutdown_output = remaining_output.strip().split('\n')
    
    # Print shutdown output
    for line in shutdown_output:
        if line.strip():
            print(f"   {line.strip()}")
    
    # Analyze results
    print("\n" + "=" * 70)
    print("Test Results")
    print("=" * 70)
    
    all_output = '\n'.join(startup_output + shutdown_output)
    
    checks = {
        "Signal received": "Received SIGINT signal" in all_output or "Received SIGTERM signal" in all_output,
        "Processor stop initiated": "Stopping embedding job processor" in all_output or "Stopping EmbeddingJobProcessor" in all_output,
        "Graceful shutdown": "Shutting down" in all_output,
        "Process exited": process.returncode is not None
    }
    
    print("\nShutdown Checks:")
    for check_name, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check_name}")
    
    all_passed = all(checks.values())
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ SIGINT HANDLING TEST PASSED")
        print("  The application handles SIGINT gracefully and shuts down cleanly.")
    else:
        print("✗ SIGINT HANDLING TEST FAILED")
        print("  Some shutdown checks did not pass. Review the output above.")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("Manual SIGTERM/SIGINT Shutdown Tests")
    print("=" * 70)
    print("\nThis script tests graceful shutdown behavior by:")
    print("  1. Starting the FastAPI application in a subprocess")
    print("  2. Sending SIGTERM/SIGINT signals")
    print("  3. Verifying graceful shutdown messages in logs")
    print("  4. Checking that the process exits cleanly")
    print("\nNote: This test requires a valid config.local.yaml file.")
    print("=" * 70)
    
    # Check if config exists
    config_path = backend_dir / ".." / "config.local.yaml"
    if not config_path.exists():
        print(f"\n✗ ERROR: Config file not found at {config_path}")
        print("  Please create a config.local.yaml file before running this test.")
        sys.exit(1)
    
    # Run tests
    try:
        sigterm_passed = test_sigterm_shutdown()
        sigint_passed = test_sigint_shutdown()
        
        # Final summary
        print("\n\n" + "=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)
        print(f"  SIGTERM Test: {'✓ PASSED' if sigterm_passed else '✗ FAILED'}")
        print(f"  SIGINT Test:  {'✓ PASSED' if sigint_passed else '✗ FAILED'}")
        print("=" * 70)
        
        if sigterm_passed and sigint_passed:
            print("\n✓ ALL TESTS PASSED")
            print("  The application handles shutdown signals gracefully.")
            sys.exit(0)
        else:
            print("\n✗ SOME TESTS FAILED")
            print("  Review the output above for details.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n✗ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
