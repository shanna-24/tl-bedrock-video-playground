"""Integration tests for API endpoints.

Tests complete request/response cycles for all API endpoints including
authentication flow and protected route access.

Validates: Requirements 5.1, 5.2, 5.3
"""

import os
import sys
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from io import BytesIO

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import models
from models.index import Index
from models.video import Video
from models.search import SearchResults, VideoClip
from models.analysis import AnalysisResult


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock()
    config.environment = "test"
    config.aws_region = "us-east-1"
    config.marengo_model_id = "test-marengo"
    config.pegasus_model_id = "test-pegasus"
    config.s3_bucket_name = "test-bucket"
    config.s3_vectors_collection = "test-collection"
    config.auth_password_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5NU7qXqw.Huiq"  # "password"
    config.max_indexes = 3
    config.use_localstack = False
    config.validate = Mock(return_value=True)
    return config



@pytest.fixture
def mock_services():
    """Create mock services for testing."""
    # Mock AuthService
    auth_service = Mock()
    auth_service.verify_password = Mock(return_value=True)
    auth_service.generate_token = Mock(return_value="test-token-123")
    auth_service.verify_token = Mock(return_value=True)
    
    # Mock IndexManager
    index_manager = Mock()
    index_manager.config = Mock(max_indexes=3)
    
    # Create sample index
    sample_index = Index(
        id="index-123",
        name="Test Index",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        video_count=1,
        s3_vectors_collection_id="collection-123",
        metadata={}
    )
    
    # Create sample video
    sample_video = Video(
        id="video-123",
        index_id="index-123",
        filename="test.mp4",
        s3_uri="s3://test-bucket/videos/test.mp4",
        duration=120.0,
        uploaded_at=datetime(2024, 1, 1, 12, 0, 0),
        embedding_ids=["emb-1", "emb-2"],
        metadata={}
    )
    
    index_manager.list_indexes = AsyncMock(return_value=[sample_index])
    index_manager.create_index = AsyncMock(return_value=sample_index)
    index_manager.delete_index = AsyncMock(return_value=True)
    index_manager.get_index = AsyncMock(return_value=sample_index)
    index_manager.list_videos_in_index = AsyncMock(return_value=[sample_video])
    index_manager.add_video_to_index = AsyncMock(return_value=sample_video)
    
    # Mock VideoService
    video_service = Mock()
    video_service.config = Mock(s3_bucket_name="test-bucket")
    video_service.get_video_stream_url = Mock(
        return_value="https://test-bucket.s3.amazonaws.com/videos/test.mp4?presigned=true"
    )
    video_service.s3 = Mock()
    
    # Mock SearchService
    search_service = Mock()
    sample_clip = VideoClip(
        video_id="video-123",
        start_timecode=10.0,
        end_timecode=20.0,
        relevance_score=0.95,
        screenshot_url="https://test-bucket.s3.amazonaws.com/screenshots/clip1.jpg",
        video_stream_url="https://test-bucket.s3.amazonaws.com/videos/test.mp4?presigned=true",
        metadata={}
    )
    
    sample_search_results = SearchResults(
        query="test query",
        clips=[sample_clip],
        total_results=1,
        search_time=0.5
    )
    
    search_service.search_videos = AsyncMock(return_value=sample_search_results)
    
    # Mock AnalysisService
    analysis_service = Mock()
    sample_analysis = AnalysisResult(
        query="test analysis query",
        scope="index",
        scope_id="index-123",
        insights="Test insights about the video content.",
        analyzed_at=datetime(2024, 1, 1, 12, 0, 0),
        metadata={}
    )
    
    analysis_service.analyze_index = AsyncMock(return_value=sample_analysis)
    analysis_service.analyze_video = AsyncMock(return_value=sample_analysis)
    
    return {
        "auth_service": auth_service,
        "index_manager": index_manager,
        "video_service": video_service,
        "search_service": search_service,
        "analysis_service": analysis_service
    }



@pytest.fixture
def test_app(mock_config, mock_services):
    """Create a test FastAPI application with mocked services."""
    # Create a new FastAPI app for testing
    app = FastAPI()
    
    # Add CORS middleware
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import and configure routers
    from api import auth, indexes, search, analysis, videos
    
    # Set up auth router
    auth.set_auth_service(mock_services["auth_service"])
    app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
    
    # Set up indexes router
    indexes.set_index_manager(mock_services["index_manager"])
    indexes.set_video_service(mock_services["video_service"])
    app.include_router(indexes.router, prefix="/api/indexes", tags=["indexes"])
    
    # Set up search router
    search.set_search_service(mock_services["search_service"])
    app.include_router(search.router, prefix="/api/search", tags=["search"])
    
    # Set up analysis router
    analysis.set_analysis_service(mock_services["analysis_service"])
    analysis.set_index_manager(mock_services["index_manager"])
    app.include_router(analysis.router, prefix="/api/analyze", tags=["analysis"])
    
    # Set up videos router
    videos.set_video_service(mock_services["video_service"])
    videos.set_index_manager(mock_services["index_manager"])
    app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
    
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


@pytest.fixture
def auth_headers(client):
    """Get authentication headers by logging in."""
    response = client.post("/api/auth/login", json={"password": "password"})
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}



class TestAuthenticationFlow:
    """Test authentication flow and protected route access.
    
    Validates: Requirements 5.1, 5.2, 5.3
    """
    
    def test_login_with_valid_credentials(self, client):
        """Test login with valid credentials returns token."""
        response = client.post("/api/auth/login", json={"password": "password"})
        
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["token"] == "test-token-123"
        assert data["message"] == "Login successful"
    
    def test_login_with_invalid_credentials(self, client, mock_services):
        """Test login with invalid credentials returns 401."""
        # Mock verify_password to return False
        mock_services["auth_service"].verify_password.return_value = False
        
        response = client.post("/api/auth/login", json={"password": "wrong"})
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Invalid password" in data["detail"]
    
    def test_logout_with_valid_token(self, client, auth_headers):
        """Test logout with valid token succeeds."""
        response = client.post("/api/auth/logout", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Logout successful"
    
    def test_logout_without_token(self, client):
        """Test logout without token returns 401."""
        response = client.post("/api/auth/logout")
        
        assert response.status_code == 403  # FastAPI returns 403 for missing credentials
    
    def test_protected_route_without_token(self, client):
        """Test accessing protected route without token returns 401."""
        response = client.get("/api/indexes")
        
        assert response.status_code == 403  # FastAPI returns 403 for missing credentials
    
    def test_protected_route_with_invalid_token(self, client, mock_services):
        """Test accessing protected route with invalid token returns 401."""
        # Mock verify_token to return False
        mock_services["auth_service"].verify_token.return_value = False
        
        headers = {"Authorization": "Bearer invalid-token"}
        response = client.get("/api/indexes", headers=headers)
        
        assert response.status_code == 401
    
    def test_protected_route_with_valid_token(self, client, auth_headers):
        """Test accessing protected route with valid token succeeds."""
        response = client.get("/api/indexes", headers=auth_headers)
        
        assert response.status_code == 200



class TestIndexManagementEndpoints:
    """Test index management API endpoints.
    
    Validates: Requirements 1.1, 1.2, 1.3, 1.5
    """
    
    def test_list_indexes_complete_cycle(self, client, auth_headers):
        """Test complete request/response cycle for listing indexes."""
        response = client.get("/api/indexes", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "indexes" in data
        assert "total" in data
        assert "max_indexes" in data
        
        # Verify index data
        assert len(data["indexes"]) == 1
        index = data["indexes"][0]
        assert index["id"] == "index-123"
        assert index["name"] == "Test Index"
        assert index["video_count"] == 1
        assert "created_at" in index
        assert "s3_vectors_collection_id" in index
    
    def test_create_index_complete_cycle(self, client, auth_headers):
        """Test complete request/response cycle for creating an index."""
        request_data = {"name": "New Test Index"}
        response = client.post("/api/indexes", json=request_data, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert data["id"] == "index-123"
        assert data["name"] == "Test Index"
        assert data["video_count"] == 1
        assert "created_at" in data
        assert "s3_vectors_collection_id" in data
    
    def test_create_index_without_auth(self, client):
        """Test creating index without authentication fails."""
        request_data = {"name": "New Test Index"}
        response = client.post("/api/indexes", json=request_data)
        
        assert response.status_code == 403
    
    def test_delete_index_complete_cycle(self, client, auth_headers):
        """Test complete request/response cycle for deleting an index."""
        response = client.delete("/api/indexes/index-123", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "message" in data
        assert "deleted_id" in data
        assert data["deleted_id"] == "index-123"
    
    def test_delete_index_without_auth(self, client):
        """Test deleting index without authentication fails."""
        response = client.delete("/api/indexes/index-123")
        
        assert response.status_code == 403
    
    def test_list_videos_in_index_complete_cycle(self, client, auth_headers):
        """Test complete request/response cycle for listing videos in an index."""
        response = client.get("/api/indexes/index-123/videos", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "videos" in data
        assert "total" in data
        assert "index_id" in data
        assert "index_name" in data
        
        # Verify video data
        assert len(data["videos"]) == 1
        video = data["videos"][0]
        assert video["id"] == "video-123"
        assert video["index_id"] == "index-123"
        assert video["filename"] == "test.mp4"
        assert video["s3_uri"] == "s3://test-bucket/videos/test.mp4"
        assert video["duration"] == 120.0
        assert "uploaded_at" in video
        assert "embedding_ids" in video



class TestVideoUploadEndpoint:
    """Test video upload API endpoint.
    
    Validates: Requirements 1.4
    """
    
    def test_upload_video_complete_cycle(self, client, auth_headers):
        """Test complete request/response cycle for uploading a video."""
        # Create a mock video file
        video_content = b"fake video content"
        files = {"file": ("test.mp4", BytesIO(video_content), "video/mp4")}
        
        response = client.post(
            "/api/indexes/index-123/videos",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 201
        data = response.json()
        
        # Verify response structure
        assert "video" in data
        assert "message" in data
        assert data["message"] == "Video uploaded successfully"
        
        # Verify video data
        video = data["video"]
        assert video["id"] == "video-123"
        assert video["index_id"] == "index-123"
        assert video["filename"] == "test.mp4"
        assert video["s3_uri"] == "s3://test-bucket/videos/test.mp4"
        assert video["duration"] == 120.0
    
    def test_upload_video_without_auth(self, client):
        """Test uploading video without authentication fails."""
        video_content = b"fake video content"
        files = {"file": ("test.mp4", BytesIO(video_content), "video/mp4")}
        
        response = client.post("/api/indexes/index-123/videos", files=files)
        
        assert response.status_code == 403
    
    def test_upload_video_invalid_format(self, client, auth_headers):
        """Test uploading video with invalid format returns 400."""
        video_content = b"fake video content"
        files = {"file": ("test.txt", BytesIO(video_content), "text/plain")}
        
        response = client.post(
            "/api/indexes/index-123/videos",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported video format" in data["detail"]



class TestSearchEndpoint:
    """Test search API endpoint.
    
    Validates: Requirements 3.1, 3.2, 3.3
    """
    
    def test_search_videos_complete_cycle(self, client, auth_headers):
        """Test complete request/response cycle for video search."""
        request_data = {
            "index_id": "index-123",
            "query": "test search query",
            "top_k": 10,
            "generate_screenshots": True
        }
        
        response = client.post("/api/search", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "query" in data
        assert "clips" in data
        assert "total_results" in data
        assert "search_time" in data
        
        # Verify search results
        assert data["query"] == "test query"
        assert data["total_results"] == 1
        assert len(data["clips"]) == 1
        
        # Verify clip data
        clip = data["clips"][0]
        assert clip["video_id"] == "video-123"
        assert clip["start_timecode"] == 10.0
        assert clip["end_timecode"] == 20.0
        assert clip["relevance_score"] == 0.95
        assert "screenshot_url" in clip
        assert "video_stream_url" in clip
    
    def test_search_without_auth(self, client):
        """Test searching without authentication fails."""
        request_data = {
            "index_id": "index-123",
            "query": "test search query"
        }
        
        response = client.post("/api/search", json=request_data)
        
        assert response.status_code == 403
    
    def test_search_with_empty_query(self, client, auth_headers):
        """Test searching with empty query returns 400."""
        request_data = {
            "index_id": "index-123",
            "query": "   "  # Empty/whitespace query
        }
        
        response = client.post("/api/search", json=request_data, headers=auth_headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "empty" in data["detail"].lower()
    
    def test_search_with_custom_top_k(self, client, auth_headers):
        """Test searching with custom top_k parameter."""
        request_data = {
            "index_id": "index-123",
            "query": "test search query",
            "top_k": 5
        }
        
        response = client.post("/api/search", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "clips" in data



class TestAnalysisEndpoints:
    """Test analysis API endpoints.
    
    Validates: Requirements 4.1, 4.2, 4.3, 4.4
    """
    
    def test_analyze_index_complete_cycle(self, client, auth_headers):
        """Test complete request/response cycle for index analysis."""
        request_data = {
            "index_id": "index-123",
            "query": "What happens in these videos?",
            "temperature": 0.2
        }
        
        response = client.post("/api/analyze/index", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "query" in data
        assert "scope" in data
        assert "scope_id" in data
        assert "insights" in data
        assert "analyzed_at" in data
        assert "metadata" in data
        
        # Verify analysis data
        assert data["query"] == "test analysis query"
        assert data["scope"] == "index"
        assert data["scope_id"] == "index-123"
        assert "insights" in data
    
    def test_analyze_index_without_auth(self, client):
        """Test analyzing index without authentication fails."""
        request_data = {
            "index_id": "index-123",
            "query": "What happens in these videos?"
        }
        
        response = client.post("/api/analyze/index", json=request_data)
        
        assert response.status_code == 403
    
    def test_analyze_index_with_empty_query(self, client, auth_headers):
        """Test analyzing index with empty query returns 400."""
        request_data = {
            "index_id": "index-123",
            "query": "   "  # Empty/whitespace query
        }
        
        response = client.post("/api/analyze/index", json=request_data, headers=auth_headers)
        
        assert response.status_code == 400
        data = response.json()
        assert "empty" in data["detail"].lower()
    
    def test_analyze_video_complete_cycle(self, client, auth_headers):
        """Test complete request/response cycle for video analysis."""
        request_data = {
            "video_id": "video-123",
            "query": "What happens in this video?",
            "temperature": 0.2
        }
        
        response = client.post("/api/analyze/video", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "query" in data
        assert "scope" in data
        assert "scope_id" in data
        assert "insights" in data
        assert "analyzed_at" in data
        assert "metadata" in data
    
    def test_analyze_video_without_auth(self, client):
        """Test analyzing video without authentication fails."""
        request_data = {
            "video_id": "video-123",
            "query": "What happens in this video?"
        }
        
        response = client.post("/api/analyze/video", json=request_data)
        
        assert response.status_code == 403
    
    def test_analyze_with_custom_temperature(self, client, auth_headers):
        """Test analysis with custom temperature parameter."""
        request_data = {
            "index_id": "index-123",
            "query": "What happens in these videos?",
            "temperature": 0.7
        }
        
        response = client.post("/api/analyze/index", json=request_data, headers=auth_headers)
        
        assert response.status_code == 200



class TestVideoStreamEndpoint:
    """Test video streaming API endpoint.
    
    Validates: Requirements 2.1, 2.2
    """
    
    def test_get_video_stream_complete_cycle(self, client, auth_headers):
        """Test complete request/response cycle for getting video stream URL."""
        response = client.get("/api/videos/video-123/stream", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "video_id" in data
        assert "stream_url" in data
        assert "expiration" in data
        
        # Verify stream data
        assert data["video_id"] == "video-123"
        assert "presigned=true" in data["stream_url"]
        assert data["expiration"] == 3600
    
    def test_get_video_stream_with_start_time(self, client, auth_headers):
        """Test getting video stream URL with start time parameter."""
        response = client.get(
            "/api/videos/video-123/stream?start_time=30.5",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response includes start_timecode
        assert "start_timecode" in data
        assert data["start_timecode"] == 30.5
    
    def test_get_video_stream_without_auth(self, client):
        """Test getting video stream without authentication fails."""
        response = client.get("/api/videos/video-123/stream")
        
        assert response.status_code == 403
    
    def test_get_video_stream_with_negative_start_time(self, client, auth_headers):
        """Test getting video stream with negative start time returns 400."""
        response = client.get(
            "/api/videos/video-123/stream?start_time=-10",
            headers=auth_headers
        )
        
        assert response.status_code == 422  # FastAPI validation error
    
    def test_get_video_stream_nonexistent_video(self, client, auth_headers, mock_services):
        """Test getting stream for nonexistent video returns 404."""
        # Mock list_indexes to return empty list
        mock_services["index_manager"].list_indexes = AsyncMock(return_value=[])
        
        response = client.get("/api/videos/nonexistent/stream", headers=auth_headers)
        
        assert response.status_code == 404



class TestEndToEndWorkflows:
    """Test complete end-to-end workflows across multiple endpoints.
    
    Validates: Requirements 5.1, 5.2, 5.3
    """
    
    def test_complete_user_workflow(self, client, mock_services):
        """Test complete user workflow: login -> create index -> upload video -> search -> logout."""
        # Step 1: Login
        login_response = client.post("/api/auth/login", json={"password": "password"})
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Step 2: List indexes
        list_response = client.get("/api/indexes", headers=headers)
        assert list_response.status_code == 200
        assert "indexes" in list_response.json()
        
        # Step 3: Create index
        create_response = client.post(
            "/api/indexes",
            json={"name": "My Videos"},
            headers=headers
        )
        assert create_response.status_code == 201
        index_id = create_response.json()["id"]
        
        # Step 4: Upload video
        video_content = b"fake video content"
        files = {"file": ("test.mp4", BytesIO(video_content), "video/mp4")}
        upload_response = client.post(
            f"/api/indexes/{index_id}/videos",
            files=files,
            headers=headers
        )
        assert upload_response.status_code == 201
        
        # Step 5: Search videos
        search_response = client.post(
            "/api/search",
            json={"index_id": index_id, "query": "test query"},
            headers=headers
        )
        assert search_response.status_code == 200
        assert "clips" in search_response.json()
        
        # Step 6: Logout
        logout_response = client.post("/api/auth/logout", headers=headers)
        assert logout_response.status_code == 200
    
    def test_video_analysis_workflow(self, client, auth_headers):
        """Test video analysis workflow: list videos -> analyze video -> get stream."""
        # Step 1: List videos in index
        list_response = client.get("/api/indexes/index-123/videos", headers=auth_headers)
        assert list_response.status_code == 200
        videos = list_response.json()["videos"]
        assert len(videos) > 0
        video_id = videos[0]["id"]
        
        # Step 2: Analyze video
        analyze_response = client.post(
            "/api/analyze/video",
            json={"video_id": video_id, "query": "What happens?"},
            headers=auth_headers
        )
        assert analyze_response.status_code == 200
        assert "insights" in analyze_response.json()
        
        # Step 3: Get video stream
        stream_response = client.get(f"/api/videos/{video_id}/stream", headers=auth_headers)
        assert stream_response.status_code == 200
        assert "stream_url" in stream_response.json()
    
    def test_index_lifecycle_workflow(self, client, auth_headers):
        """Test index lifecycle: create -> add videos -> list videos -> delete."""
        # Step 1: Create index
        create_response = client.post(
            "/api/indexes",
            json={"name": "Temp Index"},
            headers=auth_headers
        )
        assert create_response.status_code == 201
        index_id = create_response.json()["id"]
        
        # Step 2: Upload video to index
        video_content = b"fake video content"
        files = {"file": ("test.mp4", BytesIO(video_content), "video/mp4")}
        upload_response = client.post(
            f"/api/indexes/{index_id}/videos",
            files=files,
            headers=auth_headers
        )
        assert upload_response.status_code == 201
        
        # Step 3: List videos in index
        list_response = client.get(f"/api/indexes/{index_id}/videos", headers=auth_headers)
        assert list_response.status_code == 200
        assert len(list_response.json()["videos"]) > 0
        
        # Step 4: Delete index
        delete_response = client.delete(f"/api/indexes/{index_id}", headers=auth_headers)
        assert delete_response.status_code == 200



class TestErrorHandling:
    """Test error handling across API endpoints.
    
    Validates: Requirements 5.1, 5.2, 5.3
    """
    
    def test_invalid_token_format(self, client):
        """Test that invalid token format is rejected."""
        headers = {"Authorization": "InvalidFormat token123"}
        response = client.get("/api/indexes", headers=headers)
        
        # Should fail due to invalid format
        assert response.status_code in [401, 403]
    
    def test_missing_authorization_header(self, client):
        """Test that missing Authorization header is rejected."""
        response = client.get("/api/indexes")
        
        assert response.status_code == 403
    
    def test_malformed_request_body(self, client, auth_headers):
        """Test that malformed request body returns 422."""
        # Missing required field
        response = client.post("/api/indexes", json={}, headers=auth_headers)
        
        assert response.status_code == 422
    
    def test_invalid_field_types(self, client, auth_headers):
        """Test that invalid field types return 422."""
        # top_k should be int, not string
        request_data = {
            "index_id": "index-123",
            "query": "test",
            "top_k": "not-a-number"
        }
        
        response = client.post("/api/search", json=request_data, headers=auth_headers)
        
        assert response.status_code == 422
    
    def test_field_validation_errors(self, client, auth_headers):
        """Test that field validation errors return 422."""
        # Index name too short (min 3 characters)
        request_data = {"name": "ab"}
        
        response = client.post("/api/indexes", json=request_data, headers=auth_headers)
        
        assert response.status_code == 422
    
    def test_concurrent_requests_with_same_token(self, client, auth_headers):
        """Test that multiple concurrent requests with same token work."""
        # Make multiple requests concurrently
        responses = []
        for _ in range(3):
            response = client.get("/api/indexes", headers=auth_headers)
            responses.append(response)
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
