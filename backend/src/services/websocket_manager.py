"""WebSocket Manager for real-time job notifications.

This module provides a WebSocket manager that handles client connections
and broadcasts job completion notifications to connected clients.

Validates: Requirements 13.5
"""

import logging
import json
from typing import Set, Dict, Any
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manager for WebSocket connections and job notifications.
    
    This manager:
    1. Maintains a set of active WebSocket connections
    2. Handles client connection/disconnection
    3. Broadcasts job completion notifications to all connected clients
    4. Provides connection statistics
    """
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        self._connections: Set[WebSocket] = set()
        self._connection_count = 0
        self._notification_count = 0
        
        logger.info("WebSocketManager initialized")
    
    async def connect(self, websocket: WebSocket) -> None:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection to register
        """
        await websocket.accept()
        self._connections.add(websocket)
        self._connection_count += 1
        
        logger.info(
            f"WebSocket client connected | "
            f"client_id={id(websocket)} "
            f"active_connections={len(self._connections)} "
            f"total_connections={self._connection_count}"
        )
        
        # Send welcome message
        await self._send_to_client(websocket, {
            "type": "connected",
            "message": "Connected to embedding job notifications",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def disconnect(self, websocket: WebSocket) -> None:
        """
        Unregister a WebSocket connection.
        
        Args:
            websocket: WebSocket connection to unregister
        """
        self._connections.discard(websocket)
        
        logger.info(
            f"WebSocket client disconnected | "
            f"client_id={id(websocket)} "
            f"active_connections={len(self._connections)}"
        )
    
    async def broadcast_thumbnail_ready(
        self,
        video_id: str,
        timecode: float,
        thumbnail_url: str
    ) -> None:
        """
        Broadcast thumbnail ready notification to all connected clients.
        
        Args:
            video_id: ID of the video
            timecode: Timecode of the generated thumbnail
            thumbnail_url: Presigned URL of the thumbnail
        """
        if not self._connections:
            logger.debug(
                f"No WebSocket clients connected, skipping thumbnail notification | "
                f"video_id={video_id} timecode={timecode}"
            )
            return
        
        message = {
            "type": "thumbnail_ready",
            "video_id": video_id,
            "timecode": timecode,
            "thumbnail_url": thumbnail_url,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self._notification_count += 1
        
        logger.info(
            f"Broadcasting thumbnail ready notification | "
            f"video_id={video_id} timecode={timecode} "
            f"recipients={len(self._connections)}"
        )
        
        # Send to all connected clients
        disconnected = []
        for websocket in self._connections:
            try:
                await self._send_to_client(websocket, message)
            except Exception as e:
                logger.warning(
                    f"Failed to send thumbnail notification to client | "
                    f"client_id={id(websocket)} error={e}"
                )
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)
    
    async def broadcast_analysis_progress(
        self,
        correlation_id: str,
        message: str
    ) -> None:
        """
        Broadcast analysis progress notification to all connected clients.
        
        Args:
            correlation_id: Unique identifier for the analysis operation
            message: Progress message to broadcast
        """
        if not self._connections:
            logger.debug(
                f"No WebSocket clients connected, skipping progress notification | "
                f"correlation_id={correlation_id}"
            )
            return
        
        notification = {
            "type": "analysis_progress",
            "correlation_id": correlation_id,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(
            f"Broadcasting analysis progress | "
            f"correlation_id={correlation_id} "
            f"message={message} "
            f"recipients={len(self._connections)}"
        )
        
        # Send to all connected clients
        disconnected = []
        for websocket in self._connections:
            try:
                await self._send_to_client(websocket, notification)
            except Exception as e:
                logger.warning(
                    f"Failed to send progress notification to client | "
                    f"client_id={id(websocket)} error={e}"
                )
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)
        
        # Small delay to ensure message is flushed before next operation
        import asyncio
        await asyncio.sleep(0.01)
    
    async def broadcast_job_completion(
        self,
        job_id: str,
        video_id: str,
        index_id: str,
        status: str,
        embeddings_count: int = 0,
        error_message: str = None
    ) -> None:
        """
        Broadcast job completion notification to all connected clients.
        
        Args:
            job_id: Unique identifier of the completed job
            video_id: ID of the video that was processed
            index_id: ID of the index where embeddings were stored
            status: Final job status (completed or failed)
            embeddings_count: Number of embeddings stored (for completed jobs)
            error_message: Error message (for failed jobs)
        """
        if not self._connections:
            logger.debug(
                f"No WebSocket clients connected, skipping notification | "
                f"job_id={job_id}"
            )
            return
        
        notification = {
            "type": "job_completion",
            "job_id": job_id,
            "video_id": video_id,
            "index_id": index_id,
            "status": status,
            "embeddings_count": embeddings_count,
            "error_message": error_message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self._notification_count += 1
        
        logger.info(
            f"Broadcasting job completion notification | "
            f"job_id={job_id} "
            f"video_id={video_id} "
            f"status={status} "
            f"embeddings_count={embeddings_count} "
            f"active_connections={len(self._connections)} "
            f"notification_number={self._notification_count}"
        )
        
        # Broadcast to all connected clients
        disconnected_clients = []
        
        for connection in self._connections:
            try:
                await self._send_to_client(connection, notification)
            except Exception as e:
                logger.error(
                    f"Failed to send notification to client | "
                    f"client_id={id(connection)} "
                    f"error={str(e)}"
                )
                disconnected_clients.append(connection)
        
        # Remove disconnected clients
        for connection in disconnected_clients:
            self.disconnect(connection)
    
    async def _send_to_client(
        self,
        websocket: WebSocket,
        message: Dict[str, Any]
    ) -> None:
        """
        Send a message to a specific WebSocket client.
        
        Args:
            websocket: WebSocket connection
            message: Message dictionary to send
            
        Raises:
            Exception: If sending fails (client disconnected)
        """
        await websocket.send_json(message)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get WebSocket manager statistics.
        
        Returns:
            Dictionary containing:
                - active_connections: Number of currently connected clients
                - total_connections: Total number of connections since start
                - notifications_sent: Total number of notifications broadcast
        """
        return {
            "active_connections": len(self._connections),
            "total_connections": self._connection_count,
            "notifications_sent": self._notification_count
        }
