"""Unit tests for video playback API endpoints.

Tests video streaming URL generation with and without start_time parameter.
Validates: Requirements 2.1, 2.2
"""

import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api import videos, auth
from services.video_service import VideoService
from services.index_manager import IndexManager
from services.auth_service import AuthService
from models.video import Video
from models.index import Index
from config import Config
from exceptions import ResourceNotFoundError, AWSServiceError


class TestVideosAPI:
    """Test suite for video playback API endpoints."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock(spec=Config)
        config.s3_bucket_name = "test-bucket"
        config.auth_password_hash = "$2b$12$nwluL4QIKcHv7t2K2BvQqugdkC0JA9lisYkXqH2o5nAdQu8.JylFe"
        return config
    
    @pytest.fixture
    def auth_service(self, mock_config):
        """Create an AuthService instance for authentication."""
        return AuthService(mock_config, secret_key="test-secret-key")
    
    @pytest.fixture
    def mock_video_service(self, mock_config):
        """Create a mock VideoService."""
        service = Mock(spec=VideoService)
        service.config = mock_config
        service.get_video_stream_url = Mock()
        return service
    
    @pytest.fixture
    def mock_index_manager(self):
        """Create a mock IndexManager."""
        manager = Mock(spec=IndexManager)
        manager.list_indexes = AsyncMock()
        manager.list_videos_in_index = AsyncMock()
        return manager
    
    @pytest.fixture
    def sample_video(self):
        """Create a sample video for testing."""
        return Video(
            id="video-123",
            index_id="index-456",
            filename="test_video.mp4",
            s3_uri="s3://test-bucket/videos/index-456/test_video.mp4",
            duration=120.5,
            uploaded_at=datetime.now(),
            embedding_ids=["emb-1", "emb-2"]
        )
    
    @pytest.fixture
    def sample_index(self):
        """Create a sample index for testing."""
        return Index(
            id="index-456",
            name="Test Index",
            created_at=datetime.now(),
            video_count=1,
            s3_vectors_collection_id="collection-789"
        )
    
    @pytest.fixture
    def app(self, auth_service, mock_video_service, mock_index_manager):
        """Create a FastAPI test application with videos router."""
        test_app = FastAPI()
        
        # Set up auth service for dependency injection
        auth.set_auth_service(auth_service)
        
        # Set up videos service and index manager for dependency injection
        videos.set_video_service(mock_video_service)
        videos.set_index_manager(mock_index_manager)
        
        # Include routers
        test_app.include_router(auth.router, prefix="/api/auth")
        test_app.include_router(videos.router, prefix="/api/videos")
        
        return test_app
    
    @pytest.fixture
    def client(self, app):
        """Create a test client for the FastAPI application."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_token(self, client):
        """Get an authentication token for testing."""
        response = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        return response.json()["token"]
    
    def test_get_video_stream_success(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test successful video stream URL generation without start_time.
        
        Validates: Requirements 2.1
        """
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        mock_video_service.get_video_stream_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/videos/index-456/test_video.mp4"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=..."
        )
        
        # Make request
        response = client.get(
            "/api/videos/video-123/stream",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "video_id" in data
        assert "stream_url" in data
        assert "start_timecode" in data
        assert "expiration" in data
        
        # Check values
        assert data["video_id"] == "video-123"
        assert data["stream_url"].startswith("https://")
        assert data["start_timecode"] is None
        assert data["expiration"] == 3600
        
        # Verify service was called correctly
        mock_video_service.get_video_stream_url.assert_called_once_with(
            video_id="video-123",
            s3_key="videos/index-456/test_video.mp4",
            start_timecode=None,
            expiration=3600
        )
    
    def test_get_video_stream_with_start_time(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test video stream URL generation with start_time parameter.
        
        Validates: Requirements 2.2
        """
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        mock_video_service.get_video_stream_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/videos/index-456/test_video.mp4"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...#t=30.5"
        )
        
        # Make request with start_time
        response = client.get(
            "/api/videos/video-123/stream?start_time=30.5",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Check values
        assert data["video_id"] == "video-123"
        assert data["stream_url"].endswith("#t=30.5")
        assert data["start_timecode"] == 30.5
        assert data["expiration"] == 3600
        
        # Verify service was called with start_timecode
        mock_video_service.get_video_stream_url.assert_called_once_with(
            video_id="video-123",
            s3_key="videos/index-456/test_video.mp4",
            start_timecode=30.5,
            expiration=3600
        )
    
    def test_get_video_stream_with_zero_start_time(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test video stream URL generation with start_time=0."""
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        mock_video_service.get_video_stream_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/videos/index-456/test_video.mp4"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...#t=0"
        )
        
        # Make request with start_time=0
        response = client.get(
            "/api/videos/video-123/stream?start_time=0",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["start_timecode"] == 0.0
    
    def test_get_video_stream_negative_start_time(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test that negative start_time is rejected."""
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        
        # Make request with negative start_time
        response = client.get(
            "/api/videos/video-123/stream?start_time=-10",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify error response
        assert response.status_code == 422  # FastAPI validation error
    
    def test_get_video_stream_video_not_found(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_index
    ):
        """Test error when video is not found.
        
        Validates: Requirements 2.1
        """
        # Set up mocks - return empty video list
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = []
        
        # Make request
        response = client.get(
            "/api/videos/nonexistent-video/stream",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify error response
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
    
    def test_get_video_stream_no_authentication(self, client):
        """Test that authentication is required."""
        # Make request without token
        response = client.get("/api/videos/video-123/stream")
        
        # Verify unauthorized response
        assert response.status_code == 403
    
    def test_get_video_stream_invalid_token(self, client):
        """Test with invalid authentication token."""
        # Make request with invalid token
        response = client.get(
            "/api/videos/video-123/stream",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        # Verify unauthorized response
        assert response.status_code == 401
    
    def test_get_video_stream_aws_error(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test handling of AWS service errors."""
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        mock_video_service.get_video_stream_url.side_effect = AWSServiceError(
            "S3 service error occurred"
        )
        
        # Make request
        response = client.get(
            "/api/videos/video-123/stream",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to generate video stream URL" in data["detail"]
    
    def test_get_video_stream_throttling_error(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test handling of AWS throttling errors."""
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        mock_video_service.get_video_stream_url.side_effect = AWSServiceError(
            "Rate exceeded"
        )
        
        # Make request
        response = client.get(
            "/api/videos/video-123/stream",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify throttling response
        assert response.status_code == 429
        data = response.json()
        assert "detail" in data
        assert "temporarily unavailable" in data["detail"].lower()
    
    def test_get_video_stream_multiple_indexes(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video
    ):
        """Test finding video across multiple indexes."""
        # Create multiple indexes
        index1 = Index(
            id="index-1",
            name="Index 1",
            created_at=datetime.now(),
            video_count=1,
            s3_vectors_collection_id="collection-1"
        )
        index2 = Index(
            id="index-2",
            name="Index 2",
            created_at=datetime.now(),
            video_count=1,
            s3_vectors_collection_id="collection-2"
        )
        
        # Video is in the second index
        mock_index_manager.list_indexes.return_value = [index1, index2]
        mock_index_manager.list_videos_in_index.side_effect = [
            [],  # First index has no videos
            [sample_video]  # Second index has our video
        ]
        mock_video_service.get_video_stream_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/videos/index-456/test_video.mp4"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=..."
        )
        
        # Make request
        response = client.get(
            "/api/videos/video-123/stream",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "video-123"
        
        # Verify we searched both indexes
        assert mock_index_manager.list_videos_in_index.call_count == 2
    
    def test_get_video_stream_response_structure(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test that response has correct structure."""
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        mock_video_service.get_video_stream_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/videos/index-456/test_video.mp4"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=..."
        )
        
        # Make request
        response = client.get(
            "/api/videos/video-123/stream",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify response structure
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields are present
        assert "video_id" in data
        assert "stream_url" in data
        assert "start_timecode" in data
        assert "expiration" in data
        
        # Check field types
        assert isinstance(data["video_id"], str)
        assert isinstance(data["stream_url"], str)
        assert data["start_timecode"] is None or isinstance(data["start_timecode"], (int, float))
        assert isinstance(data["expiration"], int)
    
    def test_get_video_stream_error_response_structure(
        self,
        client,
        auth_token,
        mock_index_manager,
        sample_index
    ):
        """Test that error responses have correct structure."""
        # Set up mocks - video not found
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = []
        
        # Make request
        response = client.get(
            "/api/videos/nonexistent-video/stream",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify error structure
        assert response.status_code == 404
        data = response.json()
        
        # Check error structure
        assert "detail" in data
        assert isinstance(data["detail"], str)
    
    def test_get_video_stream_large_start_time(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test with start_time larger than video duration."""
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        mock_video_service.get_video_stream_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/videos/index-456/test_video.mp4"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...#t=200"
        )
        
        # Make request with start_time > video duration
        # Note: We don't validate this at the API level - the video player handles it
        response = client.get(
            "/api/videos/video-123/stream?start_time=200",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify response (should succeed - player will handle invalid timecode)
        assert response.status_code == 200
        data = response.json()
        assert data["start_timecode"] == 200.0
    
    def test_get_video_stream_fractional_start_time(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test with fractional start_time values."""
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        mock_video_service.get_video_stream_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/videos/index-456/test_video.mp4"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...#t=45.678"
        )
        
        # Make request with fractional start_time
        response = client.get(
            "/api/videos/video-123/stream?start_time=45.678",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["start_timecode"] == 45.678
    
    def test_get_video_stream_s3_key_extraction(
        self,
        client,
        auth_token,
        mock_video_service,
        mock_index_manager,
        sample_video,
        sample_index
    ):
        """Test correct extraction of S3 key from S3 URI."""
        # Set up mocks
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = [sample_video]
        mock_video_service.get_video_stream_url.return_value = (
            "https://test-bucket.s3.amazonaws.com/videos/index-456/test_video.mp4"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=..."
        )
        
        # Make request
        response = client.get(
            "/api/videos/video-123/stream",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        # Verify response
        assert response.status_code == 200
        
        # Verify S3 key was extracted correctly
        mock_video_service.get_video_stream_url.assert_called_once()
        call_args = mock_video_service.get_video_stream_url.call_args
        assert call_args[1]["s3_key"] == "videos/index-456/test_video.mp4"
    
    def test_video_service_not_initialized(self):
        """Test behavior when video service is not initialized."""
        # Create a new app without setting video service
        test_app = FastAPI()
        videos._video_service = None  # Reset global state
        videos._index_manager = None  # Reset global state
        test_app.include_router(videos.router, prefix="/api/videos")
        test_client = TestClient(test_app, raise_server_exceptions=False)
        
        # Should fail with internal server error
        response = test_client.get("/api/videos/video-123/stream")
        assert response.status_code in [403, 500]  # 403 for missing auth, 500 for missing service
    
    def test_index_manager_not_initialized(self, auth_service, mock_video_service):
        """Test behavior when index manager is not initialized."""
        # Create a new app without setting index manager
        test_app = FastAPI()
        auth.set_auth_service(auth_service)
        videos.set_video_service(mock_video_service)
        videos._index_manager = None  # Reset global state
        test_app.include_router(auth.router, prefix="/api/auth")
        test_app.include_router(videos.router, prefix="/api/videos")
        test_client = TestClient(test_app, raise_server_exceptions=False)
        
        # Get auth token
        login_response = test_client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        token = login_response.json()["token"]
        
        # Should fail with internal server error
        response = test_client.get(
            "/api/videos/video-123/stream",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 500
