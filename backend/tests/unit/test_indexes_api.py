"""Unit tests for index management API endpoints.

Tests index creation, deletion, listing, and video management endpoints.
Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5
"""

import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api import indexes, auth
from services.index_manager import IndexManager
from services.video_service import VideoService
from services.auth_service import AuthService
from models.index import Index
from models.video import Video
from config import Config
from exceptions import ResourceLimitError, ResourceNotFoundError, ValidationError


class TestIndexesAPI:
    """Test suite for index management API endpoints."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock(spec=Config)
        config.max_indexes = 3
        config.auth_password_hash = "$2b$12$nwluL4QIKcHv7t2K2BvQqugdkC0JA9lisYkXqH2o5nAdQu8.JylFe"
        return config
    
    @pytest.fixture
    def auth_service(self, mock_config):
        """Create an AuthService instance."""
        return AuthService(mock_config, secret_key="test-secret-key")
    
    @pytest.fixture
    def mock_index_manager(self, mock_config):
        """Create a mock IndexManager."""
        manager = Mock(spec=IndexManager)
        manager.config = mock_config
        
        # Make async methods return AsyncMock
        manager.create_index = AsyncMock()
        manager.delete_index = AsyncMock()
        manager.list_indexes = AsyncMock()
        manager.get_index = AsyncMock()
        manager.add_video_to_index = AsyncMock()
        manager.list_videos_in_index = AsyncMock()
        
        return manager
    
    @pytest.fixture
    def mock_video_service(self):
        """Create a mock VideoService."""
        service = Mock(spec=VideoService)
        service.s3 = Mock()
        return service
    
    @pytest.fixture
    def app(self, auth_service, mock_index_manager, mock_video_service):
        """Create a FastAPI test application with indexes router."""
        test_app = FastAPI()
        
        # Set up auth service
        auth.set_auth_service(auth_service)
        test_app.include_router(auth.router, prefix="/api/auth")
        
        # Set up indexes router
        indexes.set_index_manager(mock_index_manager)
        indexes.set_video_service(mock_video_service)
        test_app.include_router(indexes.router, prefix="/api/indexes")
        
        return test_app
    
    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)
    
    @pytest.fixture
    def auth_token(self, client):
        """Get an authentication token."""
        response = client.post(
            "/api/auth/login",
            json={"password": "testpass"}
        )
        return response.json()["token"]
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get authentication headers."""
        return {"Authorization": f"Bearer {auth_token}"}
    
    # Test GET /api/indexes - List all indexes
    
    def test_list_indexes_success(self, client, auth_headers, mock_index_manager):
        """Test successful listing of indexes."""
        # Mock index data
        mock_indexes = [
            Index(id="idx1", name="Index 1", video_count=5),
            Index(id="idx2", name="Index 2", video_count=3),
        ]
        mock_index_manager.list_indexes.return_value = mock_indexes
        
        response = client.get("/api/indexes", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "indexes" in data
        assert "total" in data
        assert "max_indexes" in data
        
        # Check data
        assert len(data["indexes"]) == 2
        assert data["total"] == 2
        assert data["max_indexes"] == 3
        
        # Check first index
        assert data["indexes"][0]["id"] == "idx1"
        assert data["indexes"][0]["name"] == "Index 1"
        assert data["indexes"][0]["video_count"] == 5
    
    def test_list_indexes_empty(self, client, auth_headers, mock_index_manager):
        """Test listing when no indexes exist."""
        mock_index_manager.list_indexes.return_value = []
        
        response = client.get("/api/indexes", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["indexes"] == []
        assert data["total"] == 0
        assert data["max_indexes"] == 3
    
    def test_list_indexes_unauthorized(self, client):
        """Test listing without authentication."""
        response = client.get("/api/indexes")
        
        assert response.status_code == 403
    
    def test_list_indexes_invalid_token(self, client):
        """Test listing with invalid token."""
        response = client.get(
            "/api/indexes",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401
    
    # Test POST /api/indexes - Create new index
    
    def test_create_index_success(self, client, auth_headers, mock_index_manager):
        """Test successful index creation."""
        mock_index = Index(id="new-idx", name="New Index", video_count=0)
        mock_index_manager.create_index.return_value = mock_index
        
        response = client.post(
            "/api/indexes",
            headers=auth_headers,
            json={"name": "New Index"}
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check response structure
        assert data["id"] == "new-idx"
        assert data["name"] == "New Index"
        assert data["video_count"] == 0
        
        # Verify create_index was called
        mock_index_manager.create_index.assert_called_once_with("New Index")
    
    def test_create_index_limit_exceeded(self, client, auth_headers, mock_index_manager):
        """Test index creation when limit is exceeded."""
        mock_index_manager.create_index.side_effect = ResourceLimitError(
            "Maximum of 3 indexes allowed"
        )
        
        response = client.post(
            "/api/indexes",
            headers=auth_headers,
            json={"name": "Fourth Index"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Maximum of 3 indexes allowed" in data["detail"]
    
    def test_create_index_invalid_name(self, client, auth_headers, mock_index_manager):
        """Test index creation with invalid name."""
        mock_index_manager.create_index.side_effect = ValidationError(
            "Index name must be 3-50 characters"
        )
        
        response = client.post(
            "/api/indexes",
            headers=auth_headers,
            json={"name": "AB"}
        )
        
        # Can be 400 (from service) or 422 (from Pydantic validation)
        assert response.status_code in [400, 422]
        data = response.json()
        # Check that error message is present (format varies by status code)
        assert "detail" in data
    
    def test_create_index_missing_name(self, client, auth_headers):
        """Test index creation without name."""
        response = client.post(
            "/api/indexes",
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == 422
    
    def test_create_index_empty_name(self, client, auth_headers):
        """Test index creation with empty name."""
        response = client.post(
            "/api/indexes",
            headers=auth_headers,
            json={"name": ""}
        )
        
        assert response.status_code == 422
    
    def test_create_index_name_too_short(self, client, auth_headers):
        """Test index creation with name too short."""
        response = client.post(
            "/api/indexes",
            headers=auth_headers,
            json={"name": "AB"}
        )
        
        assert response.status_code in [400, 422]
    
    def test_create_index_name_too_long(self, client, auth_headers):
        """Test index creation with name too long."""
        response = client.post(
            "/api/indexes",
            headers=auth_headers,
            json={"name": "A" * 51}
        )
        
        assert response.status_code == 422
    
    def test_create_index_unauthorized(self, client):
        """Test index creation without authentication."""
        response = client.post(
            "/api/indexes",
            json={"name": "New Index"}
        )
        
        assert response.status_code == 403
    
    # Test DELETE /api/indexes/{id} - Delete index
    
    def test_delete_index_success(self, client, auth_headers, mock_index_manager):
        """Test successful index deletion."""
        mock_index_manager.delete_index.return_value = True
        
        response = client.delete(
            "/api/indexes/idx1",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["message"] == "Index deleted successfully"
        assert data["deleted_id"] == "idx1"
        
        # Verify delete_index was called
        mock_index_manager.delete_index.assert_called_once_with("idx1")
    
    def test_delete_index_not_found(self, client, auth_headers, mock_index_manager):
        """Test deleting non-existent index."""
        mock_index_manager.delete_index.side_effect = ResourceNotFoundError(
            "Index not found: idx999"
        )
        
        response = client.delete(
            "/api/indexes/idx999",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "Index not found" in data["detail"]
    
    def test_delete_index_unauthorized(self, client):
        """Test index deletion without authentication."""
        response = client.delete("/api/indexes/idx1")
        
        assert response.status_code == 403
    
    # Test GET /api/indexes/{id}/videos - List videos in index
    
    def test_list_videos_success(self, client, auth_headers, mock_index_manager):
        """Test successful listing of videos in an index."""
        # Mock index
        mock_index = Index(id="idx1", name="Test Index", video_count=2)
        mock_index_manager.get_index.return_value = mock_index
        
        # Mock videos
        mock_videos = [
            Video(
                id="vid1",
                index_id="idx1",
                filename="video1.mp4",
                s3_uri="s3://bucket/video1.mp4",
                duration=120.0
            ),
            Video(
                id="vid2",
                index_id="idx1",
                filename="video2.mp4",
                s3_uri="s3://bucket/video2.mp4",
                duration=180.0
            ),
        ]
        mock_index_manager.list_videos_in_index.return_value = mock_videos
        
        response = client.get(
            "/api/indexes/idx1/videos",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "videos" in data
        assert "total" in data
        assert "index_id" in data
        assert "index_name" in data
        
        # Check data
        assert len(data["videos"]) == 2
        assert data["total"] == 2
        assert data["index_id"] == "idx1"
        assert data["index_name"] == "Test Index"
        
        # Check first video
        assert data["videos"][0]["id"] == "vid1"
        assert data["videos"][0]["filename"] == "video1.mp4"
        assert data["videos"][0]["duration"] == 120.0
    
    def test_list_videos_empty(self, client, auth_headers, mock_index_manager):
        """Test listing videos when index is empty."""
        mock_index = Index(id="idx1", name="Empty Index", video_count=0)
        mock_index_manager.get_index.return_value = mock_index
        mock_index_manager.list_videos_in_index.return_value = []
        
        response = client.get(
            "/api/indexes/idx1/videos",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["videos"] == []
        assert data["total"] == 0
    
    def test_list_videos_index_not_found(self, client, auth_headers, mock_index_manager):
        """Test listing videos for non-existent index."""
        mock_index_manager.get_index.side_effect = ResourceNotFoundError(
            "Index not found: idx999"
        )
        
        response = client.get(
            "/api/indexes/idx999/videos",
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "Index not found" in data["detail"]
    
    def test_list_videos_unauthorized(self, client):
        """Test listing videos without authentication."""
        response = client.get("/api/indexes/idx1/videos")
        
        assert response.status_code == 403
    
    # Test POST /api/indexes/{id}/videos - Upload video
    
    def test_upload_video_success(self, client, auth_headers, mock_index_manager):
        """Test successful video upload."""
        mock_video = Video(
            id="vid1",
            index_id="idx1",
            filename="test.mp4",
            s3_uri="s3://bucket/test.mp4",
            duration=120.0
        )
        mock_index_manager.add_video_to_index.return_value = mock_video
        
        # Create a mock video file
        video_content = b"fake video content"
        files = {"file": ("test.mp4", BytesIO(video_content), "video/mp4")}
        
        response = client.post(
            "/api/indexes/idx1/videos",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Check response structure
        assert "video" in data
        assert "message" in data
        
        # Check video data
        assert data["video"]["id"] == "vid1"
        assert data["video"]["filename"] == "test.mp4"
        assert data["video"]["duration"] == 120.0
        assert data["message"] == "Video uploaded successfully"
    
    def test_upload_video_invalid_format(self, client, auth_headers):
        """Test video upload with invalid format."""
        # Create a file with invalid extension
        files = {"file": ("test.txt", BytesIO(b"not a video"), "text/plain")}
        
        response = client.post(
            "/api/indexes/idx1/videos",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported video format" in data["detail"]
    
    def test_upload_video_index_not_found(self, client, auth_headers, mock_index_manager):
        """Test video upload to non-existent index."""
        mock_index_manager.add_video_to_index.side_effect = ResourceNotFoundError(
            "Index not found: idx999"
        )
        
        files = {"file": ("test.mp4", BytesIO(b"video"), "video/mp4")}
        
        response = client.post(
            "/api/indexes/idx999/videos",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "Index not found" in data["detail"]
    
    def test_upload_video_too_large(self, client, auth_headers):
        """Test video upload exceeding size limit."""
        # Create a file larger than 5GB (simulated)
        large_content = b"x" * (5 * 1024 * 1024 * 1024 + 1)
        files = {"file": ("large.mp4", BytesIO(large_content), "video/mp4")}
        
        response = client.post(
            "/api/indexes/idx1/videos",
            headers=auth_headers,
            files=files
        )
        
        assert response.status_code == 413
        data = response.json()
        assert "Maximum video size is 5GB" in data["detail"]
    
    def test_upload_video_unauthorized(self, client):
        """Test video upload without authentication."""
        files = {"file": ("test.mp4", BytesIO(b"video"), "video/mp4")}
        
        response = client.post(
            "/api/indexes/idx1/videos",
            files=files
        )
        
        assert response.status_code == 403
    
    def test_upload_video_missing_file(self, client, auth_headers):
        """Test video upload without file."""
        response = client.post(
            "/api/indexes/idx1/videos",
            headers=auth_headers
        )
        
        assert response.status_code == 422
    
    def test_upload_video_supported_formats(self, client, auth_headers, mock_index_manager):
        """Test video upload with all supported formats."""
        mock_video = Video(
            id="vid1",
            index_id="idx1",
            filename="test.mp4",
            s3_uri="s3://bucket/test.mp4",
            duration=120.0
        )
        mock_index_manager.add_video_to_index.return_value = mock_video
        
        supported_formats = [
            ("test.mp4", "video/mp4"),
            ("test.mov", "video/quicktime"),
            ("test.avi", "video/x-msvideo"),
            ("test.mkv", "video/x-matroska"),
        ]
        
        for filename, content_type in supported_formats:
            files = {"file": (filename, BytesIO(b"video"), content_type)}
            
            response = client.post(
                "/api/indexes/idx1/videos",
                headers=auth_headers,
                files=files
            )
            
            assert response.status_code == 201, f"Failed for {filename}"
    
    # Integration tests
    
    def test_complete_index_workflow(self, client, auth_headers, mock_index_manager):
        """Test complete workflow: create index, upload video, list videos, delete index."""
        # Step 1: Create index
        mock_index = Index(id="idx1", name="Test Index", video_count=0)
        mock_index_manager.create_index.return_value = mock_index
        
        create_response = client.post(
            "/api/indexes",
            headers=auth_headers,
            json={"name": "Test Index"}
        )
        assert create_response.status_code == 201
        index_id = create_response.json()["id"]
        
        # Step 2: Upload video
        mock_video = Video(
            id="vid1",
            index_id=index_id,
            filename="test.mp4",
            s3_uri="s3://bucket/test.mp4",
            duration=120.0
        )
        mock_index_manager.add_video_to_index.return_value = mock_video
        
        files = {"file": ("test.mp4", BytesIO(b"video"), "video/mp4")}
        upload_response = client.post(
            f"/api/indexes/{index_id}/videos",
            headers=auth_headers,
            files=files
        )
        assert upload_response.status_code == 201
        
        # Step 3: List videos
        mock_index.video_count = 1
        mock_index_manager.get_index.return_value = mock_index
        mock_index_manager.list_videos_in_index.return_value = [mock_video]
        
        list_response = client.get(
            f"/api/indexes/{index_id}/videos",
            headers=auth_headers
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1
        
        # Step 4: Delete index
        mock_index_manager.delete_index.return_value = True
        
        delete_response = client.delete(
            f"/api/indexes/{index_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200
    
    def test_list_indexes_after_creating_multiple(self, client, auth_headers, mock_index_manager):
        """Test listing indexes after creating multiple."""
        # Create 3 indexes
        indexes = []
        for i in range(3):
            mock_index = Index(id=f"idx{i}", name=f"Index {i}", video_count=0)
            indexes.append(mock_index)
            mock_index_manager.create_index.return_value = mock_index
            
            response = client.post(
                "/api/indexes",
                headers=auth_headers,
                json={"name": f"Index {i}"}
            )
            assert response.status_code == 201
        
        # List all indexes
        mock_index_manager.list_indexes.return_value = indexes
        
        response = client.get("/api/indexes", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 3
        assert len(data["indexes"]) == 3
    
    def test_error_handling_consistency(self, client, auth_headers, mock_index_manager):
        """Test that error responses have consistent structure."""
        # Test 404 error
        mock_index_manager.get_index.side_effect = ResourceNotFoundError("Not found")
        response = client.get("/api/indexes/idx999/videos", headers=auth_headers)
        assert response.status_code == 404
        assert "detail" in response.json()
        
        # Test 400 error
        mock_index_manager.create_index.side_effect = ValidationError("Invalid")
        response = client.post(
            "/api/indexes",
            headers=auth_headers,
            json={"name": "Test"}
        )
        assert response.status_code == 400
        assert "detail" in response.json()
        
        # Test 401 error
        response = client.get("/api/indexes")
        assert response.status_code in [401, 403]
    
    def test_concurrent_index_operations(self, client, auth_headers, mock_index_manager):
        """Test concurrent index operations."""
        import concurrent.futures
        
        mock_index = Index(id="idx1", name="Test", video_count=0)
        mock_index_manager.create_index.return_value = mock_index
        mock_index_manager.list_indexes.return_value = [mock_index]
        
        def perform_operations():
            # List indexes
            list_resp = client.get("/api/indexes", headers=auth_headers)
            return list_resp.status_code == 200
        
        # Run concurrent operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(perform_operations) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        assert all(results)
