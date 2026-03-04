"""Unit tests for MarengoWorker component.

Tests the MarengoWorker's ability to search for video segments, deduplicate,
rank by relevance, and select top N segments.

Validates: Requirements 1.3, 2.2, 2.3, 2.4
"""

import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from orchestration.marengo_worker import MarengoWorker
from models.orchestration import VideoSegment
from models.search import SearchResults, VideoClip


@pytest.fixture
def mock_search_service():
    """Create a mock SearchService for testing."""
    mock_service = Mock()
    mock_service.search_videos = AsyncMock()
    return mock_service


@pytest.fixture
def marengo_worker(mock_search_service):
    """Create a MarengoWorker instance with mocked dependencies."""
    return MarengoWorker(search_service=mock_search_service, max_results_per_query=100)


class TestMarengoWorkerInitialization:
    """Tests for MarengoWorker initialization."""
    
    def test_worker_initialization(self, mock_search_service):
        """Test that MarengoWorker initializes correctly."""
        worker = MarengoWorker(search_service=mock_search_service, max_results_per_query=100)
        
        assert worker.search == mock_search_service


class TestSearchSegments:
    """Tests for search_segments functionality."""
    
    @pytest.mark.asyncio
    async def test_search_segments_single_query(self, marengo_worker, mock_search_service):
        """Test searching with a single query."""
        # Mock search results
        mock_clips = [
            VideoClip(
                video_id="video1",
                start_timecode=10.0,
                end_timecode=20.0,
                relevance_score=0.9,
                screenshot_url="http://example.com/screenshot1.jpg",
                video_stream_url="http://example.com/video1.mp4",
                metadata={"s3_uri": "s3://bucket/video1.mp4"}
            ),
            VideoClip(
                video_id="video2",
                start_timecode=30.0,
                end_timecode=40.0,
                relevance_score=0.8,
                screenshot_url="http://example.com/screenshot2.jpg",
                video_stream_url="http://example.com/video2.mp4",
                metadata={"s3_uri": "s3://bucket/video2.mp4"}
            )
        ]
        
        mock_search_service.search_videos.return_value = SearchResults(
            query="test query",
            clips=mock_clips,
            total_results=2,
            search_time=0.5
        )
        
        # Test
        segments = await marengo_worker.search_segments(
            index_id="test-index",
            search_queries=["test query"],
            max_segments=10
        )
        
        # Verify
        assert len(segments) == 2
        assert all(isinstance(seg, VideoSegment) for seg in segments)
        
        # Verify segments are sorted by relevance (descending)
        assert segments[0].relevance_score == 0.9
        assert segments[1].relevance_score == 0.8
        
        # Verify segment data
        assert segments[0].video_id == "video1"
        assert segments[0].s3_uri == "s3://bucket/video1.mp4"
        assert segments[0].start_time == 10.0
        assert segments[0].end_time == 20.0
        
        # Verify search was called correctly
        mock_search_service.search_videos.assert_called_once()
        call_args = mock_search_service.search_videos.call_args
        assert call_args[1]["index_id"] == "test-index"
        assert call_args[1]["query"] == "test query"
        assert call_args[1]["generate_screenshots"] is False
    
    @pytest.mark.asyncio
    async def test_search_segments_multiple_queries(self, marengo_worker, mock_search_service):
        """Test searching with multiple queries."""
        # Mock search results for two queries
        mock_clips_1 = [
            VideoClip(
                video_id="video1",
                start_timecode=10.0,
                end_timecode=20.0,
                relevance_score=0.9,
                screenshot_url="http://example.com/screenshot1.jpg",
                video_stream_url="http://example.com/video1.mp4",
                metadata={"s3_uri": "s3://bucket/video1.mp4"}
            )
        ]
        
        mock_clips_2 = [
            VideoClip(
                video_id="video2",
                start_timecode=30.0,
                end_timecode=40.0,
                relevance_score=0.85,
                screenshot_url="http://example.com/screenshot2.jpg",
                video_stream_url="http://example.com/video2.mp4",
                metadata={"s3_uri": "s3://bucket/video2.mp4"}
            )
        ]
        
        # Configure mock to return different results for each query
        mock_search_service.search_videos.side_effect = [
            SearchResults(query="query1", clips=mock_clips_1, total_results=1, search_time=0.5),
            SearchResults(query="query2", clips=mock_clips_2, total_results=1, search_time=0.5)
        ]
        
        # Test
        segments = await marengo_worker.search_segments(
            index_id="test-index",
            search_queries=["query1", "query2"],
            max_segments=10
        )
        
        # Verify
        assert len(segments) == 2
        assert mock_search_service.search_videos.call_count == 2
        
        # Verify segments are sorted by relevance
        assert segments[0].relevance_score == 0.9
        assert segments[1].relevance_score == 0.85
    
    @pytest.mark.asyncio
    async def test_search_segments_respects_max_segments(self, marengo_worker, mock_search_service):
        """Test that max_segments limit is respected."""
        # Mock search results with many clips
        mock_clips = [
            VideoClip(
                video_id=f"video{i}",
                start_timecode=float(i * 10),
                end_timecode=float(i * 10 + 10),
                relevance_score=max(0.1, 1.0 - (i * 0.05)),  # Ensure scores stay >= 0.1
                screenshot_url=f"http://example.com/screenshot{i}.jpg",
                video_stream_url=f"http://example.com/video{i}.mp4",
                metadata={"s3_uri": f"s3://bucket/video{i}.mp4"}
            )
            for i in range(15)  # Reduced from 20 to keep scores positive
        ]
        
        mock_search_service.search_videos.return_value = SearchResults(
            query="test query",
            clips=mock_clips,
            total_results=15,
            search_time=0.5
        )
        
        # Test with max_segments=5
        segments = await marengo_worker.search_segments(
            index_id="test-index",
            search_queries=["test query"],
            max_segments=5
        )
        
        # Verify only 5 segments returned
        assert len(segments) == 5
        
        # Verify they are the top 5 by relevance
        assert segments[0].relevance_score == 1.0
        assert segments[4].relevance_score >= 0.75
    
    @pytest.mark.asyncio
    async def test_search_segments_deduplicates_overlapping(self, marengo_worker, mock_search_service):
        """Test that overlapping segments are deduplicated."""
        # Mock search results with overlapping segments
        mock_clips = [
            VideoClip(
                video_id="video1",
                start_timecode=10.0,
                end_timecode=20.0,
                relevance_score=0.9,
                screenshot_url="http://example.com/screenshot1.jpg",
                video_stream_url="http://example.com/video1.mp4",
                metadata={"s3_uri": "s3://bucket/video1.mp4"}
            ),
            VideoClip(
                video_id="video1",
                start_timecode=15.0,  # Overlaps with first segment
                end_timecode=25.0,
                relevance_score=0.8,  # Lower score, should be removed
                screenshot_url="http://example.com/screenshot2.jpg",
                video_stream_url="http://example.com/video1.mp4",
                metadata={"s3_uri": "s3://bucket/video1.mp4"}
            ),
            VideoClip(
                video_id="video2",
                start_timecode=30.0,
                end_timecode=40.0,
                relevance_score=0.85,
                screenshot_url="http://example.com/screenshot3.jpg",
                video_stream_url="http://example.com/video2.mp4",
                metadata={"s3_uri": "s3://bucket/video2.mp4"}
            )
        ]
        
        mock_search_service.search_videos.return_value = SearchResults(
            query="test query",
            clips=mock_clips,
            total_results=3,
            search_time=0.5
        )
        
        # Test
        segments = await marengo_worker.search_segments(
            index_id="test-index",
            search_queries=["test query"],
            max_segments=10
        )
        
        # Verify only 2 segments (overlapping one removed)
        assert len(segments) == 2
        
        # Verify the higher-scoring segment was kept
        video1_segments = [s for s in segments if s.video_id == "video1"]
        assert len(video1_segments) == 1
        assert video1_segments[0].start_time == 10.0
        assert video1_segments[0].relevance_score == 0.9
    
    @pytest.mark.asyncio
    async def test_search_segments_empty_results(self, marengo_worker, mock_search_service):
        """Test handling of empty search results."""
        mock_search_service.search_videos.return_value = SearchResults(
            query="test query",
            clips=[],
            total_results=0,
            search_time=0.5
        )
        
        # Test
        segments = await marengo_worker.search_segments(
            index_id="test-index",
            search_queries=["test query"],
            max_segments=10
        )
        
        # Verify empty list returned
        assert len(segments) == 0
    
    @pytest.mark.asyncio
    async def test_search_segments_handles_search_failure(self, marengo_worker, mock_search_service):
        """Test that search failures for individual queries don't stop the process."""
        # First query succeeds, second fails
        mock_clips = [
            VideoClip(
                video_id="video1",
                start_timecode=10.0,
                end_timecode=20.0,
                relevance_score=0.9,
                screenshot_url="http://example.com/screenshot1.jpg",
                video_stream_url="http://example.com/video1.mp4",
                metadata={"s3_uri": "s3://bucket/video1.mp4"}
            )
        ]
        
        mock_search_service.search_videos.side_effect = [
            SearchResults(query="query1", clips=mock_clips, total_results=1, search_time=0.5),
            Exception("Search failed")
        ]
        
        # Test - should not raise exception
        segments = await marengo_worker.search_segments(
            index_id="test-index",
            search_queries=["query1", "query2"],
            max_segments=10
        )
        
        # Verify we got results from the successful query
        assert len(segments) == 1
        assert segments[0].video_id == "video1"


class TestSearchSegmentsValidation:
    """Tests for input validation in search_segments."""
    
    @pytest.mark.asyncio
    async def test_search_segments_empty_queries(self, marengo_worker):
        """Test error handling for empty search queries."""
        with pytest.raises(ValueError) as exc_info:
            await marengo_worker.search_segments(
                index_id="test-index",
                search_queries=[],
                max_segments=10
            )
        
        assert "search_queries cannot be empty" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_search_segments_invalid_max_segments(self, marengo_worker):
        """Test error handling for invalid max_segments."""
        with pytest.raises(ValueError) as exc_info:
            await marengo_worker.search_segments(
                index_id="test-index",
                search_queries=["test query"],
                max_segments=0
            )
        
        assert "max_segments must be at least 1" in str(exc_info.value)


class TestSegmentDeduplication:
    """Tests for segment deduplication logic."""
    
    def test_deduplicate_no_overlap(self, marengo_worker):
        """Test deduplication with no overlapping segments."""
        segments = [
            VideoSegment(
                video_id="video1",
                s3_uri="s3://bucket/video1.mp4",
                start_time=10.0,
                end_time=20.0,
                relevance_score=0.9
            ),
            VideoSegment(
                video_id="video1",
                s3_uri="s3://bucket/video1.mp4",
                start_time=30.0,
                end_time=40.0,
                relevance_score=0.8
            )
        ]
        
        result = marengo_worker._deduplicate_segments(segments)
        
        # Both segments should be kept
        assert len(result) == 2
    
    def test_deduplicate_with_overlap(self, marengo_worker):
        """Test deduplication with overlapping segments."""
        segments = [
            VideoSegment(
                video_id="video1",
                s3_uri="s3://bucket/video1.mp4",
                start_time=10.0,
                end_time=20.0,
                relevance_score=0.9
            ),
            VideoSegment(
                video_id="video1",
                s3_uri="s3://bucket/video1.mp4",
                start_time=15.0,  # 50% overlap
                end_time=25.0,
                relevance_score=0.8
            )
        ]
        
        result = marengo_worker._deduplicate_segments(segments)
        
        # Only the higher-scoring segment should be kept
        assert len(result) == 1
        assert result[0].relevance_score == 0.9
    
    def test_deduplicate_different_videos(self, marengo_worker):
        """Test that segments from different videos are not deduplicated."""
        segments = [
            VideoSegment(
                video_id="video1",
                s3_uri="s3://bucket/video1.mp4",
                start_time=10.0,
                end_time=20.0,
                relevance_score=0.9
            ),
            VideoSegment(
                video_id="video2",
                s3_uri="s3://bucket/video2.mp4",
                start_time=10.0,  # Same time but different video
                end_time=20.0,
                relevance_score=0.8
            )
        ]
        
        result = marengo_worker._deduplicate_segments(segments)
        
        # Both segments should be kept (different videos)
        assert len(result) == 2
    
    def test_deduplicate_empty_list(self, marengo_worker):
        """Test deduplication with empty list."""
        result = marengo_worker._deduplicate_segments([])
        
        assert len(result) == 0


class TestSegmentOverlap:
    """Tests for segment overlap detection."""
    
    def test_segments_overlap_same_video_high_overlap(self, marengo_worker):
        """Test overlap detection for segments with >=50% overlap."""
        seg1 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=10.0,
            end_time=20.0,
            relevance_score=0.9
        )
        seg2 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=15.0,  # 5 second overlap out of 10 second duration = 50%
            end_time=25.0,
            relevance_score=0.8
        )
        
        # 50% overlap should be considered overlapping (>= threshold)
        assert marengo_worker._segments_overlap(seg1, seg2) is True
    
    def test_segments_overlap_same_video_low_overlap(self, marengo_worker):
        """Test overlap detection for segments with <50% overlap."""
        seg1 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=10.0,
            end_time=20.0,
            relevance_score=0.9
        )
        seg2 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=18.0,  # 2 second overlap out of 10 second duration = 20%
            end_time=28.0,
            relevance_score=0.8
        )
        
        assert marengo_worker._segments_overlap(seg1, seg2) is False
    
    def test_segments_overlap_different_videos(self, marengo_worker):
        """Test that segments from different videos don't overlap."""
        seg1 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=10.0,
            end_time=20.0,
            relevance_score=0.9
        )
        seg2 = VideoSegment(
            video_id="video2",
            s3_uri="s3://bucket/video2.mp4",
            start_time=10.0,
            end_time=20.0,
            relevance_score=0.8
        )
        
        assert marengo_worker._segments_overlap(seg1, seg2) is False
    
    def test_segments_overlap_no_temporal_overlap(self, marengo_worker):
        """Test segments with no temporal overlap."""
        seg1 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=10.0,
            end_time=20.0,
            relevance_score=0.9
        )
        seg2 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=30.0,
            end_time=40.0,
            relevance_score=0.8
        )
        
        assert marengo_worker._segments_overlap(seg1, seg2) is False
    
    def test_segments_overlap_adjacent(self, marengo_worker):
        """Test adjacent segments (end of one = start of other)."""
        seg1 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=10.0,
            end_time=20.0,
            relevance_score=0.9
        )
        seg2 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=20.0,  # Starts exactly where seg1 ends
            end_time=30.0,
            relevance_score=0.8
        )
        
        # Adjacent segments should not be considered overlapping
        assert marengo_worker._segments_overlap(seg1, seg2) is False
    
    def test_segments_overlap_one_contains_other(self, marengo_worker):
        """Test when one segment completely contains another."""
        seg1 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=10.0,
            end_time=30.0,
            relevance_score=0.9
        )
        seg2 = VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/video1.mp4",
            start_time=15.0,  # Completely inside seg1
            end_time=20.0,
            relevance_score=0.8
        )
        
        # 100% overlap of seg2 with seg1
        assert marengo_worker._segments_overlap(seg1, seg2) is True
