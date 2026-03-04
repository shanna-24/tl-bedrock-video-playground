"""Application state management.

This module provides a centralized location for application state
to avoid circular import issues between main.py and API modules.
"""

from typing import Optional


class AppState:
    """Container for application-wide state and services."""
    
    def __init__(self):
        self.config: Optional[object] = None
        self.bedrock_client: Optional[object] = None
        self.s3_client: Optional[object] = None
        self.s3_vectors_client: Optional[object] = None
        self.auth_service: Optional[object] = None
        self.index_manager: Optional[object] = None
        self.video_service: Optional[object] = None
        self.search_service: Optional[object] = None
        self.analysis_service: Optional[object] = None
        self.video_reel_service: Optional[object] = None
        self.metadata_store: Optional[object] = None
        self.embedding_job_store: Optional[object] = None
        self.embedding_job_processor: Optional[object] = None
        self.transcription_job_processor: Optional[object] = None
        self.websocket_manager: Optional[object] = None


# Global application state instance
app_state = AppState()
