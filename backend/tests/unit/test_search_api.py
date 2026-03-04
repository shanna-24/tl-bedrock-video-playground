"""Unit tests for search API endpoints.

Tests the search endpoint implementation including:
- Successful search with results
- Empty query validation
- Authentication requirements
- Error handling for various failure scenarios
- Response format validation

Validates: Requirements 3.1, 3.2, 3.3
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api.search import (
    router,
    set_search_service,
    get_search_service,
    search_videos,
    SearchRequest,
    _clip_to_response
)
from models.search import SearchResults, VideoClip
from exceptions import (
    ResourceNotFoundError,
    ValidationError,
    AWSServiceError,
    BedrockError
)


@pytest.fixture
def mock_search_service():
    """Create a mock SearchService."""
    service = MagicMock()
    service.search_videos = AsyncMock()
    return service


@pytest.fixture
def sample_video_clip():
    """Create a sample VideoClip for testing."""
    return VideoClip(
        video_id="video-123",
        start_timecode=10.5,
        end_timecode=25.3,
        relevance_score=0.85,
        screenshot_url="https://example.com/screenshot.jpg",
        video_stream_url="https://example.com/video.mp4#t=10.5",
        metadata={"source": "test"}
    )


@pytest.fixture
def sample_search_results(sample_video_clip):
    """Create sample SearchResults for testing."""
    return SearchResults(
        query="test query",
        clips=[sample_video_clip],
        total_results=1,
        search_time=0.5
    )


class TestSearchServiceDependency:
    """Test search service dependency injection."""
    
    def test_set_and_get_search_service(self, mock_search_service):
        """Test setting and getting search service."""
        set_search_service(mock_search_service)
        service = get_search_service()
        assert service == mock_search_service
    
    def test_get_search_service_not_initialized(self):
        """Test getting search service when not initialized."""
        # Reset to None
        set_search_service(None)
        
        with pytest.raises(RuntimeError, match="Search service not initialized"):
            get_search_service()


class TestClipToResponse:
    """Test VideoClip to response conversion."""
    
    def test_clip_to_response(self, sample_video_clip):
        """Test converting VideoClip to VideoClipResponse."""
        response = _clip_to_response(sample_video_clip)
        
        assert response.video_id == sample_video_clip.video_id
        assert response.start_timecode == sample_video_clip.start_timecode
        assert response.end_timecode == sample_video_clip.end_timecode
        assert response.relevance_score == sample_video_clip.relevance_score
        assert response.screenshot_url == sample_video_clip.screenshot_url
        assert response.video_stream_url == sample_video_clip.video_stream_url


class TestSearchVideosEndpoint:
    """Test the search_videos endpoint."""
    
    @pytest.mark.asyncio
    async def test_search_videos_success(
        self,
        mock_search_service,
        sample_search_results
    ):
        """Test successful video search."""
        # Setup
        set_search_service(mock_search_service)
        mock_search_service.search_videos.return_value = sample_search_results
        
        request = SearchRequest(
            index_id="index-123",
            query="test query",
            top_k=10,
            generate_screenshots=True
        )
        
        # Execute
        response = await search_videos(
            request=request,
            authenticated=True,
            search_service=mock_search_service
        )
        
        # Verify
        assert response.query == "test query"
        assert len(response.clips) == 1
        assert response.total_results == 1
        assert response.search_time == 0.5
        
        # Verify clip details
        clip = response.clips[0]
        assert clip.video_id == "video-123"
        assert clip.start_timecode == 10.5
        assert clip.end_timecode == 25.3
        assert clip.relevance_score == 0.85
        
        # Verify service was called correctly
        mock_search_service.search_videos.assert_called_once_with(
            index_id="index-123",
            query="test query",
            top_k=10,
            generate_screenshots=True
        )
    
    @pytest.mark.asyncio
    async def test_search_videos_empty_query(self, mock_search_service):
        """Test search with whitespace-only query."""
        set_search_service(mock_search_service)
        
        # Create a request with whitespace-only query
        # This passes Pydantic validation (min_length=1) but should be caught
        # by our endpoint logic that checks strip()
        request = SearchRequest(
            index_id="index-123",
            query=" ",  # Single space - passes Pydantic min_length=1
            top_k=10
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_search_videos_with_custom_top_k(
        self,
        mock_search_service,
        sample_search_results
    ):
        """Test search with custom top_k parameter."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.return_value = sample_search_results
        
        request = SearchRequest(
            index_id="index-123",
            query="test query",
            top_k=5,
            generate_screenshots=False
        )
        
        response = await search_videos(
            request=request,
            authenticated=True,
            search_service=mock_search_service
        )
        
        # Verify service was called with correct parameters
        mock_search_service.search_videos.assert_called_once_with(
            index_id="index-123",
            query="test query",
            top_k=5,
            generate_screenshots=False
        )
    
    @pytest.mark.asyncio
    async def test_search_videos_no_results(self, mock_search_service):
        """Test search that returns no results."""
        set_search_service(mock_search_service)
        
        empty_results = SearchResults(
            query="test query",
            clips=[],
            total_results=0,
            search_time=0.3
        )
        mock_search_service.search_videos.return_value = empty_results
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        response = await search_videos(
            request=request,
            authenticated=True,
            search_service=mock_search_service
        )
        
        assert response.query == "test query"
        assert len(response.clips) == 0
        assert response.total_results == 0
        assert response.search_time == 0.3


class TestSearchErrorHandling:
    """Test error handling in search endpoint."""
    
    @pytest.mark.asyncio
    async def test_search_validation_error(self, mock_search_service):
        """Test handling of validation errors."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.side_effect = ValidationError(
            "Invalid search parameters"
        )
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 400
        assert "Invalid search parameters" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_search_value_error(self, mock_search_service):
        """Test handling of ValueError from service."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.side_effect = ValueError(
            "top_k must be at least 1"
        )
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 400
        assert "top_k must be at least 1" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_search_index_not_found(self, mock_search_service):
        """Test handling of index not found error."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.side_effect = ResourceNotFoundError(
            "Index index-123 not found"
        )
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 404
        assert "Index index-123 not found" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_search_bedrock_error(self, mock_search_service):
        """Test handling of Bedrock errors."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.side_effect = BedrockError(
            "Failed to embed query"
        )
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 500
        assert "Failed to process search query" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_search_bedrock_throttling(self, mock_search_service):
        """Test handling of Bedrock throttling errors."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.side_effect = BedrockError(
            "ThrottlingException: Rate exceeded"
        )
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 429
        assert "temporarily unavailable" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_search_aws_service_error(self, mock_search_service):
        """Test handling of AWS service errors."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.side_effect = AWSServiceError(
            "S3 Vectors connection failed"
        )
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 500
        assert "Search failed" in exc_info.value.detail
    
    @pytest.mark.asyncio
    async def test_search_timeout_error(self, mock_search_service):
        """Test handling of search timeout errors."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.side_effect = AWSServiceError(
            "Search timeout exceeded"
        )
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 504
        assert "took too long" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_search_aws_throttling(self, mock_search_service):
        """Test handling of AWS throttling errors."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.side_effect = AWSServiceError(
            "Rate limit exceeded"
        )
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 429
        assert "temporarily unavailable" in exc_info.value.detail.lower()
    
    @pytest.mark.asyncio
    async def test_search_unexpected_error(self, mock_search_service):
        """Test handling of unexpected errors."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.side_effect = Exception(
            "Unexpected error"
        )
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        assert exc_info.value.status_code == 500
        assert "Search failed" in exc_info.value.detail


class TestSearchRequestValidation:
    """Test SearchRequest model validation."""
    
    def test_valid_search_request(self):
        """Test creating a valid search request."""
        request = SearchRequest(
            index_id="index-123",
            query="test query",
            top_k=10,
            generate_screenshots=True
        )
        
        assert request.index_id == "index-123"
        assert request.query == "test query"
        assert request.top_k == 10
        assert request.generate_screenshots is True
    
    def test_search_request_defaults(self):
        """Test search request with default values."""
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        assert request.top_k == 10
        assert request.generate_screenshots is True
    
    def test_search_request_empty_index_id(self):
        """Test search request with empty index_id."""
        with pytest.raises(ValueError):
            SearchRequest(
                index_id="",
                query="test query"
            )
    
    def test_search_request_empty_query(self):
        """Test search request with empty query."""
        with pytest.raises(ValueError):
            SearchRequest(
                index_id="index-123",
                query=""
            )
    
    def test_search_request_query_too_long(self):
        """Test search request with query exceeding max length."""
        with pytest.raises(ValueError):
            SearchRequest(
                index_id="index-123",
                query="a" * 1001  # Max is 1000
            )
    
    def test_search_request_top_k_too_small(self):
        """Test search request with top_k less than 1."""
        with pytest.raises(ValueError):
            SearchRequest(
                index_id="index-123",
                query="test query",
                top_k=0
            )
    
    def test_search_request_top_k_too_large(self):
        """Test search request with top_k greater than 100."""
        with pytest.raises(ValueError):
            SearchRequest(
                index_id="index-123",
                query="test query",
                top_k=101
            )


class TestSearchResponseFormat:
    """Test search response format and structure."""
    
    @pytest.mark.asyncio
    async def test_response_contains_all_required_fields(
        self,
        mock_search_service,
        sample_search_results
    ):
        """Test that response contains all required fields."""
        set_search_service(mock_search_service)
        mock_search_service.search_videos.return_value = sample_search_results
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        response = await search_videos(
            request=request,
            authenticated=True,
            search_service=mock_search_service
        )
        
        # Check top-level fields
        assert hasattr(response, 'query')
        assert hasattr(response, 'clips')
        assert hasattr(response, 'total_results')
        assert hasattr(response, 'search_time')
        
        # Check clip fields
        if response.clips:
            clip = response.clips[0]
            assert hasattr(clip, 'video_id')
            assert hasattr(clip, 'start_timecode')
            assert hasattr(clip, 'end_timecode')
            assert hasattr(clip, 'relevance_score')
            assert hasattr(clip, 'screenshot_url')
            assert hasattr(clip, 'video_stream_url')
    
    @pytest.mark.asyncio
    async def test_response_with_multiple_clips(self, mock_search_service):
        """Test response with multiple video clips."""
        set_search_service(mock_search_service)
        
        # Create multiple clips
        clips = [
            VideoClip(
                video_id=f"video-{i}",
                start_timecode=float(i * 10),
                end_timecode=float(i * 10 + 5),
                relevance_score=0.9 - (i * 0.1),
                screenshot_url=f"https://example.com/screenshot-{i}.jpg",
                video_stream_url=f"https://example.com/video-{i}.mp4",
                metadata={}
            )
            for i in range(5)
        ]
        
        results = SearchResults(
            query="test query",
            clips=clips,
            total_results=5,
            search_time=1.2
        )
        
        mock_search_service.search_videos.return_value = results
        
        request = SearchRequest(
            index_id="index-123",
            query="test query"
        )
        
        response = await search_videos(
            request=request,
            authenticated=True,
            search_service=mock_search_service
        )
        
        assert len(response.clips) == 5
        assert response.total_results == 5
        
        # Verify clips are in order
        for i, clip in enumerate(response.clips):
            assert clip.video_id == f"video-{i}"
            assert clip.relevance_score == pytest.approx(0.9 - (i * 0.1))
