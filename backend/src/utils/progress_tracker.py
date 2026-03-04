"""Progress tracking utilities for streaming analysis progress to clients.

This module provides utilities for tracking and streaming progress updates
during long-running analysis operations using WebSocket.
"""

import logging
from typing import Optional
from datetime import datetime

from exceptions import AnalysisCancelledError

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Tracks progress of analysis operations and streams updates via WebSocket.
    
    This class manages progress state for a single analysis operation and
    broadcasts updates through the WebSocket manager.
    
    Attributes:
        correlation_id: Unique identifier for the analysis operation
        websocket_manager: WebSocketManager instance for broadcasting
        _completed: Flag indicating if operation is complete
        _cancelled: Flag indicating if operation was cancelled
    """
    
    def __init__(self, correlation_id: str, websocket_manager):
        """Initialize the progress tracker.
        
        Args:
            correlation_id: Unique identifier for the analysis operation
            websocket_manager: WebSocketManager instance for broadcasting
        """
        self.correlation_id = correlation_id
        self.websocket_manager = websocket_manager
        self._completed = False
        self._cancelled = False
        
        logger.debug(f"[{correlation_id}] Progress tracker initialized")
    
    @property
    def is_cancelled(self) -> bool:
        """Check if the operation has been cancelled."""
        return self._cancelled
    
    def cancel(self):
        """Mark the operation as cancelled."""
        self._cancelled = True
        logger.info(f"[{self.correlation_id}] Progress tracker cancelled")
    
    async def update(self, message: str):
        """Update progress with a new message.
        
        Args:
            message: Progress message to send to clients
        """
        if self._completed:
            logger.warning(
                f"[{self.correlation_id}] Attempted to update completed tracker"
            )
            return
        
        if self._cancelled:
            logger.debug(
                f"[{self.correlation_id}] Skipping update for cancelled tracker"
            )
            return
        
        await self.websocket_manager.broadcast_analysis_progress(
            correlation_id=self.correlation_id,
            message=message
        )
        
        logger.info(f"[{self.correlation_id}] Progress: {message}")
    
    async def complete(self):
        """Mark the operation as complete."""
        self._completed = True
        logger.debug(f"[{self.correlation_id}] Progress tracker completed")


# Global registry of active progress trackers
_active_trackers: dict[str, ProgressTracker] = {}


def create_tracker(correlation_id: str, websocket_manager) -> ProgressTracker:
    """Create and register a new progress tracker.
    
    Args:
        correlation_id: Unique identifier for the analysis operation
        websocket_manager: WebSocketManager instance for broadcasting
    
    Returns:
        New ProgressTracker instance
    """
    tracker = ProgressTracker(correlation_id, websocket_manager)
    _active_trackers[correlation_id] = tracker
    
    logger.debug(f"Created progress tracker: {correlation_id}")
    
    return tracker


def get_tracker(correlation_id: str) -> Optional[ProgressTracker]:
    """Get an existing progress tracker by correlation ID.
    
    Args:
        correlation_id: Unique identifier for the analysis operation
    
    Returns:
        ProgressTracker instance if found, None otherwise
    """
    return _active_trackers.get(correlation_id)


def remove_tracker(correlation_id: str):
    """Remove a progress tracker from the registry.
    
    Args:
        correlation_id: Unique identifier for the analysis operation
    """
    if correlation_id in _active_trackers:
        del _active_trackers[correlation_id]
        logger.debug(f"Removed progress tracker: {correlation_id}")


def cancel_tracker(correlation_id: str) -> bool:
    """Cancel a progress tracker by correlation ID.
    
    Args:
        correlation_id: Unique identifier for the analysis operation
    
    Returns:
        True if tracker was found and cancelled, False otherwise
    """
    tracker = _active_trackers.get(correlation_id)
    if tracker:
        tracker.cancel()
        logger.info(f"Cancelled progress tracker: {correlation_id}")
        return True
    logger.debug(f"No tracker found to cancel: {correlation_id}")
    return False


def is_tracker_cancelled(correlation_id: str) -> bool:
    """Check if a tracker has been cancelled.
    
    Args:
        correlation_id: Unique identifier for the analysis operation
    
    Returns:
        True if tracker exists and is cancelled, False otherwise
    """
    tracker = _active_trackers.get(correlation_id)
    return tracker.is_cancelled if tracker else False


def check_cancellation(correlation_id: str) -> None:
    """Check if a tracker has been cancelled and raise exception if so.
    
    This is a convenience function for cooperative cancellation. Call this
    at checkpoints in long-running operations to allow graceful cancellation.
    
    Args:
        correlation_id: Unique identifier for the analysis operation
    
    Raises:
        AnalysisCancelledError: If the tracker has been cancelled
    """
    if is_tracker_cancelled(correlation_id):
        logger.info(f"Analysis cancelled by user: {correlation_id}")
        raise AnalysisCancelledError(f"Analysis {correlation_id} was cancelled by user")
