"""Unit tests for analysis API endpoints.

This module tests the analysis API endpoints for index and video analysis.

Validates: Requirements 4.1, 4.2, 4.3, 4.4
"""

import sys
from pathlib import Path
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api.analysis import (
    router,
    set_analysis_service,
    set_index_manager,
    analyze_index,
    analyze_video,
    cancel_analysis,
    AnalyzeIndexRequest,
    AnalyzeVideoRequest,
    CancelAnalysisRequest,
    _result_to_response
)
from models.analysis import AnalysisResult
from models.index import Index
from models.video import Video
from exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BedrockError,
    AWSServiceError
)


@pytest.fixture
def mock_analysis_service():
    """Create a mock AnalysisService."""
    service = MagicMock()
    service.analyze_index = AsyncMock()
    service.analyze_video = AsyncMock()
    return service


@pytest.fixture
def mock_index_manager():
    """Create a mock IndexManager."""
    manager = MagicMock()
    manager.get_index = AsyncMock()
    manager.list_indexes = AsyncMock()
    manager.list_videos_in_index = AsyncMock()
    return manager


@pytest.fixture
def sample_index():
    """Create a sample index."""
    return Index(
        id="index-123",
        name="Test Index",
        video_count=2,
        s3_vectors_collection_id="collection-123"
    )


@pytest.fixture
def sample_videos():
    """Create sample videos."""
    return [
        Video(
            id="video-1",
            index_id="index-123",
            filename="video1.mp4",
            s3_uri="s3://bucket/videos/video1.mp4",
            duration=120.0
        ),
        Video(
            id="video-2",
            index_id="index-123",
            filename="video2.mp4",
            s3_uri="s3://bucket/videos/video2.mp4",
            duration=180.0
        )
    ]


@pytest.fixture
def sample_analysis_result():
    """Create a sample analysis result."""
    return AnalysisResult(
        query="What happens in the videos?",
        scope="index",
        scope_id="index-123",
        insights="The videos show various activities including...",
        analyzed_at=datetime(2024, 1, 1, 12, 0, 0),
        metadata={"video_count": 2}
    )


class TestAnalyzeIndexEndpoint:
    """Tests for POST /analyze/index endpoint."""
    
    @pytest.mark.asyncio
    async def test_analyze_index_success(
        self,
        mock_analysis_service,
        mock_index_manager,
        sample_index,
        sample_videos,
        sample_analysis_result
    ):
        """Test successful index analysis."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        mock_index_manager.get_index.return_value = sample_index
        mock_index_manager.list_videos_in_index.return_value = sample_videos
        mock_analysis_service.analyze_index.return_value = sample_analysis_result
        
        request = AnalyzeIndexRequest(
            index_id="index-123",
            query="What happens in the videos?",
            temperature=0.2
        )
        
        # Execute
        response = await analyze_index(
            request=request,
            authenticated=True,
            analysis_service=mock_analysis_service,
            index_manager=mock_index_manager
        )
        
        # Verify
        assert response.query == "What happens in the videos?"
        assert response.scope == "index"
        assert response.scope_id == "index-123"
        assert response.insights == "The videos show various activities including..."
        assert "2024-01-01T12:00:00" in response.analyzed_at
        assert response.metadata["video_count"] == 2
        
        # Verify service calls
        mock_index_manager.get_index.assert_called_once_with("index-123")
        mock_index_manager.list_videos_in_index.assert_called_once_with("index-123")
        mock_analysis_service.analyze_index.assert_called_once()
        
        call_args = mock_analysis_service.analyze_index.call_args
        assert call_args.kwargs["index_id"] == "index-123"
        assert call_args.kwargs["query"] == "What happens in the videos?"
        assert call_args.kwargs["temperature"] == 0.2
        assert len(call_args.kwargs["video_s3_uris"]) == 2
    
    @pytest.mark.asyncio
    async def test_analyze_index_with_max_tokens(
        self,
        mock_analysis_service,
        mock_index_manager,
        sample_index,
        sample_videos
    ):
        """Test index analysis with max_output_tokens parameter."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        # Create a different result for this test
        result = AnalysisResult(
            query="Summarize the content",
            scope="index",
            scope_id="index-123",
            insights="Summary of content...",
            analyzed_at=datetime(2024, 1, 1, 12, 0, 0),
            metadata={"video_count": 2}
        )
        
        mock_index_manager.get_index.return_value = sample_index
        mock_index_manager.list_videos_in_index.return_value = sample_videos
        mock_analysis_service.analyze_index.return_value = result
        
        request = AnalyzeIndexRequest(
            index_id="index-123",
            query="Summarize the content",
            temperature=0.5,
            max_output_tokens=2048
        )
        
        # Execute
        response = await analyze_index(
            request=request,
            authenticated=True,
            analysis_service=mock_analysis_service,
            index_manager=mock_index_manager
        )
        
        # Verify
        assert response.query == "Summarize the content"
        
        call_args = mock_analysis_service.analyze_index.call_args
        assert call_args.kwargs["max_output_tokens"] == 2048
        assert call_args.kwargs["temperature"] == 0.5
    
    @pytest.mark.asyncio
    async def test_analyze_index_empty_query(
        self,
        mock_analysis_service,
        mock_index_manager
    ):
        """Test index analysis with empty query."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        request = AnalyzeIndexRequest(
            index_id="index-123",
            query=" ",  # Whitespace query
            temperature=0.2
        )
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await analyze_index(
                request=request,
                authenticated=True,
                analysis_service=mock_analysis_service,
                index_manager=mock_index_manager
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "query cannot be empty" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_index_not_found(
        self,
        mock_analysis_service,
        mock_index_manager
    ):
        """Test index analysis with non-existent index."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        mock_index_manager.get_index.side_effect = ResourceNotFoundError(
            "Index index-999 not found"
        )
        
        request = AnalyzeIndexRequest(
            index_id="index-999",
            query="What happens?",
            temperature=0.2
        )
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await analyze_index(
                request=request,
                authenticated=True,
                analysis_service=mock_analysis_service,
                index_manager=mock_index_manager
            )
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_index_no_videos(
        self,
        mock_analysis_service,
        mock_index_manager,
        sample_index
    ):
        """Test index analysis with no videos in index."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        mock_index_manager.get_index.return_value = sample_index
        mock_index_manager.list_videos_in_index.return_value = []  # No videos
        
        request = AnalyzeIndexRequest(
            index_id="index-123",
            query="What happens?",
            temperature=0.2
        )
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await analyze_index(
                request=request,
                authenticated=True,
                analysis_service=mock_analysis_service,
                index_manager=mock_index_manager
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "no videos" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_index_bedrock_throttling(
        self,
        mock_analysis_service,
        mock_index_manager,
        sample_index,
        sample_videos
    ):
        """Test index analysis with Bedrock throttling error."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        mock_index_manager.get_index.return_value = sample_index
        mock_index_manager.list_videos_in_index.return_value = sample_videos
        mock_analysis_service.analyze_index.side_effect = BedrockError(
            "Rate limit exceeded - throttling"
        )
        
        request = AnalyzeIndexRequest(
            index_id="index-123",
            query="What happens?",
            temperature=0.2
        )
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await analyze_index(
                request=request,
                authenticated=True,
                analysis_service=mock_analysis_service,
                index_manager=mock_index_manager
            )
        
        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "temporarily unavailable" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_index_timeout(
        self,
        mock_analysis_service,
        mock_index_manager,
        sample_index,
        sample_videos
    ):
        """Test index analysis with timeout error."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        mock_index_manager.get_index.return_value = sample_index
        mock_index_manager.list_videos_in_index.return_value = sample_videos
        mock_analysis_service.analyze_index.side_effect = AWSServiceError(
            "Request timeout"
        )
        
        request = AnalyzeIndexRequest(
            index_id="index-123",
            query="What happens?",
            temperature=0.2
        )
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await analyze_index(
                request=request,
                authenticated=True,
                analysis_service=mock_analysis_service,
                index_manager=mock_index_manager
            )
        
        assert exc_info.value.status_code == status.HTTP_504_GATEWAY_TIMEOUT
        assert "took too long" in exc_info.value.detail.lower()


class TestAnalyzeVideoEndpoint:
    """Tests for POST /analyze/video endpoint."""
    
    @pytest.mark.asyncio
    async def test_analyze_video_success(
        self,
        mock_analysis_service,
        mock_index_manager,
        sample_index,
        sample_videos
    ):
        """Test successful video analysis."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        video_result = AnalysisResult(
            query="What happens in this video?",
            scope="video",
            scope_id="video-1",
            insights="This video shows...",
            analyzed_at=datetime(2024, 1, 1, 12, 0, 0),
            metadata={"video_s3_uri": "s3://bucket/videos/video1.mp4"}
        )
        
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = sample_videos
        mock_analysis_service.analyze_video.return_value = video_result
        
        request = AnalyzeVideoRequest(
            video_id="video-1",
            query="What happens in this video?",
            temperature=0.2
        )
        
        # Execute
        response = await analyze_video(
            request=request,
            authenticated=True,
            analysis_service=mock_analysis_service,
            index_manager=mock_index_manager
        )
        
        # Verify
        assert response.query == "What happens in this video?"
        assert response.scope == "video"
        assert response.scope_id == "video-1"
        assert response.insights == "This video shows..."
        
        # Verify service calls
        mock_analysis_service.analyze_video.assert_called_once()
        call_args = mock_analysis_service.analyze_video.call_args
        assert call_args.kwargs["video_id"] == "video-1"
        assert call_args.kwargs["query"] == "What happens in this video?"
        assert call_args.kwargs["video_s3_uri"] == "s3://bucket/videos/video1.mp4"
    
    @pytest.mark.asyncio
    async def test_analyze_video_with_max_tokens(
        self,
        mock_analysis_service,
        mock_index_manager,
        sample_index,
        sample_videos
    ):
        """Test video analysis with max_output_tokens parameter."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        video_result = AnalysisResult(
            query="Summarize",
            scope="video",
            scope_id="video-1",
            insights="Summary...",
            analyzed_at=datetime.now(),
            metadata={}
        )
        
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = sample_videos
        mock_analysis_service.analyze_video.return_value = video_result
        
        request = AnalyzeVideoRequest(
            video_id="video-1",
            query="Summarize",
            temperature=0.7,
            max_output_tokens=1024
        )
        
        # Execute
        response = await analyze_video(
            request=request,
            authenticated=True,
            analysis_service=mock_analysis_service,
            index_manager=mock_index_manager
        )
        
        # Verify
        assert response.query == "Summarize"
        
        call_args = mock_analysis_service.analyze_video.call_args
        assert call_args.kwargs["max_output_tokens"] == 1024
        assert call_args.kwargs["temperature"] == 0.7
    
    @pytest.mark.asyncio
    async def test_analyze_video_empty_query(
        self,
        mock_analysis_service,
        mock_index_manager
    ):
        """Test video analysis with empty query."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        request = AnalyzeVideoRequest(
            video_id="video-1",
            query=" ",  # Whitespace query
            temperature=0.2
        )
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await analyze_video(
                request=request,
                authenticated=True,
                analysis_service=mock_analysis_service,
                index_manager=mock_index_manager
            )
        
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "query cannot be empty" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_video_not_found(
        self,
        mock_analysis_service,
        mock_index_manager,
        sample_index,
        sample_videos
    ):
        """Test video analysis with non-existent video."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = sample_videos
        
        request = AnalyzeVideoRequest(
            video_id="video-999",  # Non-existent video
            query="What happens?",
            temperature=0.2
        )
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await analyze_video(
                request=request,
                authenticated=True,
                analysis_service=mock_analysis_service,
                index_manager=mock_index_manager
            )
        
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_analyze_video_bedrock_error(
        self,
        mock_analysis_service,
        mock_index_manager,
        sample_index,
        sample_videos
    ):
        """Test video analysis with Bedrock error."""
        # Setup
        set_analysis_service(mock_analysis_service)
        set_index_manager(mock_index_manager)
        
        mock_index_manager.list_indexes.return_value = [sample_index]
        mock_index_manager.list_videos_in_index.return_value = sample_videos
        mock_analysis_service.analyze_video.side_effect = BedrockError(
            "Model invocation failed"
        )
        
        request = AnalyzeVideoRequest(
            video_id="video-1",
            query="What happens?",
            temperature=0.2
        )
        
        # Execute & Verify
        with pytest.raises(HTTPException) as exc_info:
            await analyze_video(
                request=request,
                authenticated=True,
                analysis_service=mock_analysis_service,
                index_manager=mock_index_manager
            )
        
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "failed to analyze" in exc_info.value.detail.lower()


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_result_to_response(self):
        """Test converting AnalysisResult to AnalysisResponse."""
        # Setup
        result = AnalysisResult(
            query="Test query",
            scope="index",
            scope_id="index-123",
            insights="Test insights",
            analyzed_at=datetime(2024, 1, 1, 12, 0, 0),
            metadata={"key": "value"}
        )
        
        # Execute
        response = _result_to_response(result)
        
        # Verify
        assert response.query == "Test query"
        assert response.scope == "index"
        assert response.scope_id == "index-123"
        assert response.insights == "Test insights"
        assert response.analyzed_at == "2024-01-01T12:00:00"
        assert response.metadata == {"key": "value"}


class TestRequestValidation:
    """Tests for request model validation."""
    
    def test_analyze_index_request_valid(self):
        """Test valid AnalyzeIndexRequest."""
        request = AnalyzeIndexRequest(
            index_id="index-123",
            query="What happens?",
            temperature=0.5,
            max_output_tokens=2048
        )
        
        assert request.index_id == "index-123"
        assert request.query == "What happens?"
        assert request.temperature == 0.5
        assert request.max_output_tokens == 2048
    
    def test_analyze_index_request_defaults(self):
        """Test AnalyzeIndexRequest with default values."""
        request = AnalyzeIndexRequest(
            index_id="index-123",
            query="What happens?"
        )
        
        assert request.temperature == 0.2
        assert request.max_output_tokens is None
    
    def test_analyze_video_request_valid(self):
        """Test valid AnalyzeVideoRequest."""
        request = AnalyzeVideoRequest(
            video_id="video-123",
            query="What happens?",
            temperature=0.3,
            max_output_tokens=1024
        )
        
        assert request.video_id == "video-123"
        assert request.query == "What happens?"
        assert request.temperature == 0.3
        assert request.max_output_tokens == 1024
    
    def test_analyze_video_request_defaults(self):
        """Test AnalyzeVideoRequest with default values."""
        request = AnalyzeVideoRequest(
            video_id="video-123",
            query="What happens?"
        )
        
        assert request.temperature == 0.2
        assert request.max_output_tokens is None


class TestCancelAnalysisEndpoint:
    """Tests for POST /analyze/cancel endpoint."""
    
    @pytest.mark.asyncio
    async def test_cancel_analysis_success(self):
        """Test successful analysis cancellation."""
        # Setup - create a tracker first
        from utils.progress_tracker import create_tracker, _active_trackers
        
        mock_websocket_manager = MagicMock()
        correlation_id = "test-correlation-123"
        
        # Create a tracker
        tracker = create_tracker(correlation_id, mock_websocket_manager)
        assert correlation_id in _active_trackers
        
        request = CancelAnalysisRequest(correlation_id=correlation_id)
        
        # Execute
        response = await cancel_analysis(request=request, authenticated=True)
        
        # Verify
        assert response.cancelled is True
        assert response.correlation_id == correlation_id
        assert tracker.is_cancelled is True
        
        # Cleanup
        from utils.progress_tracker import remove_tracker
        remove_tracker(correlation_id)
    
    @pytest.mark.asyncio
    async def test_cancel_analysis_not_found(self):
        """Test cancellation of non-existent analysis."""
        request = CancelAnalysisRequest(correlation_id="non-existent-id")
        
        # Execute
        response = await cancel_analysis(request=request, authenticated=True)
        
        # Verify - should return cancelled=False for non-existent tracker
        assert response.cancelled is False
        assert response.correlation_id == "non-existent-id"
    
    def test_cancel_analysis_request_validation(self):
        """Test CancelAnalysisRequest validation."""
        # Valid request
        request = CancelAnalysisRequest(correlation_id="valid-id")
        assert request.correlation_id == "valid-id"
        
        # Empty correlation_id should fail validation
        with pytest.raises(Exception):  # Pydantic validation error
            CancelAnalysisRequest(correlation_id="")


class TestProgressTrackerCancellation:
    """Tests for progress tracker cancellation functionality."""
    
    @pytest.mark.asyncio
    async def test_tracker_cancel_flag(self):
        """Test that cancelled tracker has is_cancelled flag set."""
        from utils.progress_tracker import ProgressTracker
        
        mock_websocket_manager = MagicMock()
        tracker = ProgressTracker("test-id", mock_websocket_manager)
        
        assert tracker.is_cancelled is False
        tracker.cancel()
        assert tracker.is_cancelled is True
    
    @pytest.mark.asyncio
    async def test_cancelled_tracker_skips_updates(self):
        """Test that cancelled tracker skips progress updates."""
        from utils.progress_tracker import ProgressTracker
        
        mock_websocket_manager = MagicMock()
        mock_websocket_manager.broadcast_analysis_progress = AsyncMock()
        
        tracker = ProgressTracker("test-id", mock_websocket_manager)
        
        # Update before cancellation should work
        await tracker.update("Progress 1")
        mock_websocket_manager.broadcast_analysis_progress.assert_called_once()
        
        # Cancel the tracker
        tracker.cancel()
        
        # Update after cancellation should be skipped
        await tracker.update("Progress 2")
        # Should still only have been called once
        assert mock_websocket_manager.broadcast_analysis_progress.call_count == 1
    
    def test_cancel_tracker_function(self):
        """Test cancel_tracker function."""
        from utils.progress_tracker import (
            create_tracker, 
            cancel_tracker, 
            is_tracker_cancelled,
            remove_tracker
        )
        
        mock_websocket_manager = MagicMock()
        correlation_id = "test-cancel-123"
        
        # Create tracker
        tracker = create_tracker(correlation_id, mock_websocket_manager)
        
        # Cancel it
        result = cancel_tracker(correlation_id)
        assert result is True
        assert is_tracker_cancelled(correlation_id) is True
        
        # Try to cancel non-existent tracker
        result = cancel_tracker("non-existent")
        assert result is False
        
        # Cleanup
        remove_tracker(correlation_id)
    
    def test_is_tracker_cancelled_function(self):
        """Test is_tracker_cancelled function."""
        from utils.progress_tracker import (
            create_tracker,
            is_tracker_cancelled,
            cancel_tracker,
            remove_tracker
        )
        
        mock_websocket_manager = MagicMock()
        correlation_id = "test-is-cancelled-123"
        
        # Non-existent tracker
        assert is_tracker_cancelled("non-existent") is False
        
        # Create tracker - not cancelled
        create_tracker(correlation_id, mock_websocket_manager)
        assert is_tracker_cancelled(correlation_id) is False
        
        # Cancel it
        cancel_tracker(correlation_id)
        assert is_tracker_cancelled(correlation_id) is True
        
        # Cleanup
        remove_tracker(correlation_id)
