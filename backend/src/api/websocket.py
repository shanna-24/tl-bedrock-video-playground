"""WebSocket API endpoints for real-time job notifications.

This module implements WebSocket endpoints for receiving real-time
notifications about embedding job completions.

Validates: Requirements 13.5
"""

import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Dependency injection placeholder (will be set by main.py)
_websocket_manager: Optional[WebSocketManager] = None


def set_websocket_manager(manager: WebSocketManager):
    """Set the WebSocket manager for dependency injection.
    
    This function should be called by main.py during startup to inject
    the initialized instance.
    
    Args:
        manager: Initialized WebSocketManager instance
    """
    global _websocket_manager
    _websocket_manager = manager


def get_websocket_manager() -> WebSocketManager:
    """Get the WebSocket manager instance.
    
    Returns:
        WebSocketManager instance
        
    Raises:
        RuntimeError: If WebSocket manager is not initialized
    """
    if _websocket_manager is None:
        raise RuntimeError("WebSocket manager not initialized")
    return _websocket_manager


@router.websocket("/notifications")
async def websocket_notifications(websocket: WebSocket):
    """
    WebSocket endpoint for real-time embedding job notifications.
    
    This endpoint allows clients to connect via WebSocket and receive
    real-time notifications when embedding jobs complete or fail.
    
    Message Format:
        Connection message:
        {
            "type": "connected",
            "message": "Connected to embedding job notifications",
            "timestamp": "2024-01-01T12:00:00.000000"
        }
        
        Job completion notification:
        {
            "type": "job_completion",
            "job_id": "abc-123",
            "video_id": "video-456",
            "index_id": "index-789",
            "status": "completed",  # or "failed"
            "embeddings_count": 150,  # number of embeddings stored (0 for failed)
            "error_message": null,  # error message for failed jobs
            "timestamp": "2024-01-01T12:05:00.000000"
        }
    
    Usage:
        Connect to ws://localhost:8000/ws/notifications
        
        Example JavaScript client:
        ```javascript
        const ws = new WebSocket('ws://localhost:8000/ws/notifications');
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'job_completion') {
                console.log(`Job ${data.job_id} ${data.status}`);
                if (data.status === 'completed') {
                    console.log(`Stored ${data.embeddings_count} embeddings`);
                }
            }
        };
        ```
    
    Args:
        websocket: WebSocket connection
        
    Validates: Requirements 13.5
    """
    manager = get_websocket_manager()
    
    try:
        # Accept and register the connection
        await manager.connect(websocket)
        
        # Keep connection alive and handle incoming messages
        # (we don't expect clients to send messages, but we need to keep the connection open)
        while True:
            try:
                # Wait for any message from client (mostly for keepalive)
                data = await websocket.receive_text()
                
                # Log received message (for debugging)
                logger.debug(f"Received message from WebSocket client: {data}")
                
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected normally")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket connection: {str(e)}")
                break
    
    except Exception as e:
        logger.error(f"Error handling WebSocket connection: {str(e) or type(e).__name__}")
    
    finally:
        # Unregister the connection
        manager.disconnect(websocket)
