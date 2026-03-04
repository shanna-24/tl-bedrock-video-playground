"""Integration tests for WebSocket notifications.

This module tests the WebSocket endpoint integration with the
embedding job processor.

Validates: Requirements 13.5
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from main import app
from services.websocket_manager import WebSocketManager
from api import websocket as websocket_api


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def websocket_manager():
    """Create a WebSocket manager instance."""
    manager = WebSocketManager()
    websocket_api.set_websocket_manager(manager)
    return manager


def test_websocket_endpoint_exists(test_client):
    """Test that the WebSocket endpoint is registered."""
    # Check that the WebSocket route exists in the app
    routes = [route.path for route in app.routes]
    assert "/ws/notifications" in routes


@pytest.mark.asyncio
async def test_websocket_manager_broadcast(websocket_manager):
    """Test that WebSocket manager can broadcast notifications."""
    # Create a mock WebSocket connection
    mock_ws = Mock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    
    # Connect the mock client
    await websocket_manager.connect(mock_ws)
    
    # Reset mock to ignore welcome message
    mock_ws.send_json.reset_mock()
    
    # Broadcast a job completion
    await websocket_manager.broadcast_job_completion(
        job_id="test-job-123",
        video_id="test-video-456",
        index_id="test-index-789",
        status="completed",
        embeddings_count=100
    )
    
    # Verify notification was sent
    mock_ws.send_json.assert_called_once()
    call_args = mock_ws.send_json.call_args[0][0]
    
    assert call_args["type"] == "job_completion"
    assert call_args["job_id"] == "test-job-123"
    assert call_args["video_id"] == "test-video-456"
    assert call_args["status"] == "completed"
    assert call_args["embeddings_count"] == 100


@pytest.mark.asyncio
async def test_websocket_manager_stats(websocket_manager):
    """Test that WebSocket manager tracks statistics correctly."""
    # Initial stats
    stats = websocket_manager.get_stats()
    assert stats["active_connections"] == 0
    assert stats["notifications_sent"] == 0
    
    # Connect a client
    mock_ws = Mock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    
    await websocket_manager.connect(mock_ws)
    
    # Check stats after connection
    stats = websocket_manager.get_stats()
    assert stats["active_connections"] == 1
    assert stats["total_connections"] == 1
    
    # Send a notification
    await websocket_manager.broadcast_job_completion(
        job_id="test-job",
        video_id="test-video",
        index_id="test-index",
        status="completed",
        embeddings_count=50
    )
    
    # Check stats after notification
    stats = websocket_manager.get_stats()
    assert stats["notifications_sent"] == 1
    
    # Disconnect
    websocket_manager.disconnect(mock_ws)
    
    # Check stats after disconnect
    stats = websocket_manager.get_stats()
    assert stats["active_connections"] == 0
    assert stats["total_connections"] == 1  # Total doesn't decrease
