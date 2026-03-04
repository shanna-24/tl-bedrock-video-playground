"""Unit tests for WebSocket Manager.

This module tests the WebSocket manager functionality including
connection management and notification broadcasting.

Validates: Requirements 13.5
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.websocket_manager import WebSocketManager


@pytest.fixture
def websocket_manager():
    """Create a WebSocket manager instance for testing."""
    return WebSocketManager()


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_websocket_manager_initialization(websocket_manager):
    """Test WebSocket manager initialization."""
    assert websocket_manager._connections == set()
    assert websocket_manager._connection_count == 0
    assert websocket_manager._notification_count == 0


@pytest.mark.asyncio
async def test_connect_websocket(websocket_manager, mock_websocket):
    """Test connecting a WebSocket client."""
    await websocket_manager.connect(mock_websocket)
    
    # Verify connection was accepted
    mock_websocket.accept.assert_called_once()
    
    # Verify connection was added to set
    assert mock_websocket in websocket_manager._connections
    assert websocket_manager._connection_count == 1
    
    # Verify welcome message was sent
    mock_websocket.send_json.assert_called_once()
    call_args = mock_websocket.send_json.call_args[0][0]
    assert call_args["type"] == "connected"
    assert "Connected to embedding job notifications" in call_args["message"]


@pytest.mark.asyncio
async def test_disconnect_websocket(websocket_manager, mock_websocket):
    """Test disconnecting a WebSocket client."""
    # First connect
    await websocket_manager.connect(mock_websocket)
    assert len(websocket_manager._connections) == 1
    
    # Then disconnect
    websocket_manager.disconnect(mock_websocket)
    
    # Verify connection was removed
    assert mock_websocket not in websocket_manager._connections
    assert len(websocket_manager._connections) == 0


@pytest.mark.asyncio
async def test_multiple_connections(websocket_manager):
    """Test managing multiple WebSocket connections."""
    # Create multiple mock websockets
    ws1 = MagicMock()
    ws1.accept = AsyncMock()
    ws1.send_json = AsyncMock()
    
    ws2 = MagicMock()
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()
    
    ws3 = MagicMock()
    ws3.accept = AsyncMock()
    ws3.send_json = AsyncMock()
    
    # Connect all three
    await websocket_manager.connect(ws1)
    await websocket_manager.connect(ws2)
    await websocket_manager.connect(ws3)
    
    # Verify all are connected
    assert len(websocket_manager._connections) == 3
    assert websocket_manager._connection_count == 3
    
    # Disconnect one
    websocket_manager.disconnect(ws2)
    
    # Verify only two remain
    assert len(websocket_manager._connections) == 2
    assert ws1 in websocket_manager._connections
    assert ws2 not in websocket_manager._connections
    assert ws3 in websocket_manager._connections


@pytest.mark.asyncio
async def test_broadcast_job_completion_success(websocket_manager, mock_websocket):
    """Test broadcasting job completion notification."""
    # Connect a client
    await websocket_manager.connect(mock_websocket)
    mock_websocket.send_json.reset_mock()  # Reset to ignore welcome message
    
    # Broadcast completion
    await websocket_manager.broadcast_job_completion(
        job_id="job-123",
        video_id="video-456",
        index_id="index-789",
        status="completed",
        embeddings_count=150
    )
    
    # Verify notification was sent
    mock_websocket.send_json.assert_called_once()
    call_args = mock_websocket.send_json.call_args[0][0]
    
    assert call_args["type"] == "job_completion"
    assert call_args["job_id"] == "job-123"
    assert call_args["video_id"] == "video-456"
    assert call_args["index_id"] == "index-789"
    assert call_args["status"] == "completed"
    assert call_args["embeddings_count"] == 150
    assert call_args["error_message"] is None
    assert "timestamp" in call_args
    
    # Verify notification count
    assert websocket_manager._notification_count == 1


@pytest.mark.asyncio
async def test_broadcast_job_completion_failure(websocket_manager, mock_websocket):
    """Test broadcasting job failure notification."""
    # Connect a client
    await websocket_manager.connect(mock_websocket)
    mock_websocket.send_json.reset_mock()
    
    # Broadcast failure
    await websocket_manager.broadcast_job_completion(
        job_id="job-123",
        video_id="video-456",
        index_id="index-789",
        status="failed",
        embeddings_count=0,
        error_message="Bedrock job failed"
    )
    
    # Verify notification was sent
    mock_websocket.send_json.assert_called_once()
    call_args = mock_websocket.send_json.call_args[0][0]
    
    assert call_args["type"] == "job_completion"
    assert call_args["status"] == "failed"
    assert call_args["embeddings_count"] == 0
    assert call_args["error_message"] == "Bedrock job failed"


@pytest.mark.asyncio
async def test_broadcast_to_multiple_clients(websocket_manager):
    """Test broadcasting to multiple connected clients."""
    # Create and connect multiple clients
    ws1 = MagicMock()
    ws1.accept = AsyncMock()
    ws1.send_json = AsyncMock()
    
    ws2 = MagicMock()
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()
    
    ws3 = MagicMock()
    ws3.accept = AsyncMock()
    ws3.send_json = AsyncMock()
    
    await websocket_manager.connect(ws1)
    await websocket_manager.connect(ws2)
    await websocket_manager.connect(ws3)
    
    # Reset mocks to ignore welcome messages
    ws1.send_json.reset_mock()
    ws2.send_json.reset_mock()
    ws3.send_json.reset_mock()
    
    # Broadcast notification
    await websocket_manager.broadcast_job_completion(
        job_id="job-123",
        video_id="video-456",
        index_id="index-789",
        status="completed",
        embeddings_count=150
    )
    
    # Verify all clients received the notification
    ws1.send_json.assert_called_once()
    ws2.send_json.assert_called_once()
    ws3.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_broadcast_with_no_connections(websocket_manager):
    """Test broadcasting when no clients are connected."""
    # Broadcast without any connections
    await websocket_manager.broadcast_job_completion(
        job_id="job-123",
        video_id="video-456",
        index_id="index-789",
        status="completed",
        embeddings_count=150
    )
    
    # Should not raise an error
    # Notification count should still be 0 since no clients
    assert websocket_manager._notification_count == 0


@pytest.mark.asyncio
async def test_broadcast_handles_disconnected_client(websocket_manager):
    """Test that broadcasting handles disconnected clients gracefully."""
    # Create two clients
    ws1 = MagicMock()
    ws1.accept = AsyncMock()
    ws1.send_json = AsyncMock()
    
    ws2 = MagicMock()
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()
    
    await websocket_manager.connect(ws1)
    await websocket_manager.connect(ws2)
    
    assert len(websocket_manager._connections) == 2
    
    # Reset mocks and make ws2 fail on next send
    ws1.send_json.reset_mock()
    ws2.send_json.reset_mock()
    ws2.send_json.side_effect = Exception("Connection closed")
    
    # Broadcast notification
    await websocket_manager.broadcast_job_completion(
        job_id="job-123",
        video_id="video-456",
        index_id="index-789",
        status="completed",
        embeddings_count=150
    )
    
    # ws1 should have received the notification
    ws1.send_json.assert_called_once()
    
    # ws2 should have been removed from connections
    assert len(websocket_manager._connections) == 1
    assert ws1 in websocket_manager._connections
    assert ws2 not in websocket_manager._connections


@pytest.mark.asyncio
async def test_get_stats(websocket_manager, mock_websocket):
    """Test getting WebSocket manager statistics."""
    # Initial stats
    stats = websocket_manager.get_stats()
    assert stats["active_connections"] == 0
    assert stats["total_connections"] == 0
    assert stats["notifications_sent"] == 0
    
    # Connect a client
    await websocket_manager.connect(mock_websocket)
    
    stats = websocket_manager.get_stats()
    assert stats["active_connections"] == 1
    assert stats["total_connections"] == 1
    assert stats["notifications_sent"] == 0
    
    # Send a notification
    await websocket_manager.broadcast_job_completion(
        job_id="job-123",
        video_id="video-456",
        index_id="index-789",
        status="completed",
        embeddings_count=150
    )
    
    stats = websocket_manager.get_stats()
    assert stats["active_connections"] == 1
    assert stats["total_connections"] == 1
    assert stats["notifications_sent"] == 1
    
    # Disconnect
    websocket_manager.disconnect(mock_websocket)
    
    stats = websocket_manager.get_stats()
    assert stats["active_connections"] == 0
    assert stats["total_connections"] == 1  # Total doesn't decrease
    assert stats["notifications_sent"] == 1


@pytest.mark.asyncio
async def test_disconnect_nonexistent_connection(websocket_manager, mock_websocket):
    """Test disconnecting a connection that doesn't exist."""
    # Should not raise an error
    websocket_manager.disconnect(mock_websocket)
    
    # Stats should remain at 0
    stats = websocket_manager.get_stats()
    assert stats["active_connections"] == 0
    assert stats["total_connections"] == 0
