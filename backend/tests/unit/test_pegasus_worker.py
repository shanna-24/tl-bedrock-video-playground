"""Unit tests for PegasusWorker component.

Tests the PegasusWorker's ability to analyze video segments using Pegasus model,
both individually and in parallel with concurrency control.

Validates: Requirements 1.3, 3.2, 7.2
"""

import sys
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from orchestration.pegasus_worker import PegasusWorker
from models.orchestration import VideoSegment, SegmentAnalysis


@pytest.fixture
def mock_bedrock_client():
    """Create a mock BedrockClient for testing."""
    mock_client = Mock()
    mock_client.invoke_pegasus_analysis = Mock()
    return mock_client


@pytest.fixture
def pegasus_worker(mock_bedrock_client):
    """Create a PegasusWorker instance with mocked dependencies."""
    return PegasusWorker(bedrock_client=mock_bedrock_client)


@pytest.fixture
def sample_segment():
    """Create a sample VideoSegment for testing."""
    return VideoSegment(
        video_id="video1",
        s3_uri="s3://bucket/video1.mp4",
        start_time=10.0,
        end_time=20.0,
        relevance_score=0.9
    )


@pytest.fixture
def sample_segments():
    """Create multiple sample VideoSegments for testing."""
    return [
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
            start_time=30.0,
            end_time=40.0,
            relevance_score=0.85
        ),
        VideoSegment(
            video_id="video3",
            s3_uri="s3://bucket/video3.mp4",
            start_time=50.0,
            end_time=60.0,
            relevance_score=0.8
        )
    ]


class TestPegasusWorkerInitialization:
    """Tests for PegasusWorker initialization."""
    
    def test_worker_initialization(self, mock_bedrock_client):
        """Test that PegasusWorker initializes correctly."""
        worker = PegasusWorker(bedrock_client=mock_bedrock_client)
        
        assert worker.bedrock == mock_bedrock_client


class TestAnalyzeSegment:
    """Tests for analyze_segment functionality."""
    
    @pytest.mark.asyncio
    async def test_analyze_segment_success(self, pegasus_worker, mock_bedrock_client, sample_segment):
        """Test successful analysis of a single segment."""
        # Mock Pegasus response
        mock_bedrock_client.invoke_pegasus_analysis.return_value = {
            "message": "This video shows a person walking in a park.",
            "finishReason": "stop"
        }
        
        # Test
        result = await pegasus_worker.analyze_segment(
            segment=sample_segment,
            prompt="Describe what you see in this video.",
            temperature=0.2
        )
        
        # Verify result structure
        assert isinstance(result, SegmentAnalysis)
        assert result.segment == sample_segment
        assert result.insights == "This video shows a person walking in a park."
        assert isinstance(result.analyzed_at, datetime)
        
        # Verify Bedrock was called correctly
        mock_bedrock_client.invoke_pegasus_analysis.assert_called_once_with(
            s3_uri="s3://bucket/video1.mp4",
            prompt="Describe what you see in this video.",
            temperature=0.2
        )
    
    @pytest.mark.asyncio
    async def test_analyze_segment_with_custom_temperature(self, pegasus_worker, mock_bedrock_client, sample_segment):
        """Test analysis with custom temperature parameter."""
        mock_bedrock_client.invoke_pegasus_analysis.return_value = {
            "message": "Analysis result",
            "finishReason": "stop"
        }
        
        # Test with custom temperature
        await pegasus_worker.analyze_segment(
            segment=sample_segment,
            prompt="Test prompt",
            temperature=0.7
        )
        
        # Verify temperature was passed correctly
        call_args = mock_bedrock_client.invoke_pegasus_analysis.call_args
        assert call_args[1]["temperature"] == 0.7
    
    @pytest.mark.asyncio
    async def test_analyze_segment_failure(self, pegasus_worker, mock_bedrock_client, sample_segment):
        """Test handling of analysis failure."""
        # Mock Pegasus failure
        mock_bedrock_client.invoke_pegasus_analysis.side_effect = Exception("Pegasus API error")
        
        # Test - should raise exception
        with pytest.raises(Exception) as exc_info:
            await pegasus_worker.analyze_segment(
                segment=sample_segment,
                prompt="Test prompt",
                temperature=0.2
            )
        
        assert "Pegasus API error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_analyze_segment_empty_response(self, pegasus_worker, mock_bedrock_client, sample_segment):
        """Test handling of empty response from Pegasus."""
        # Mock empty response
        mock_bedrock_client.invoke_pegasus_analysis.return_value = {
            "message": "",
            "finishReason": "stop"
        }
        
        # Test
        result = await pegasus_worker.analyze_segment(
            segment=sample_segment,
            prompt="Test prompt",
            temperature=0.2
        )
        
        # Should still create SegmentAnalysis with empty insights
        assert isinstance(result, SegmentAnalysis)
        assert result.insights == ""


class TestAnalyzeSegmentsParallel:
    """Tests for analyze_segments_parallel functionality."""
    
    @pytest.mark.asyncio
    async def test_analyze_segments_parallel_success(self, pegasus_worker, mock_bedrock_client, sample_segments):
        """Test successful parallel analysis of multiple segments."""
        # Mock Pegasus responses
        mock_bedrock_client.invoke_pegasus_analysis.side_effect = [
            {"message": "Analysis of video 1", "finishReason": "stop"},
            {"message": "Analysis of video 2", "finishReason": "stop"},
            {"message": "Analysis of video 3", "finishReason": "stop"}
        ]
        
        # Test
        results = await pegasus_worker.analyze_segments_parallel(
            segments=sample_segments,
            prompt="Describe the video",
            temperature=0.2,
            max_concurrent=3
        )
        
        # Verify results
        assert len(results) == 3
        assert all(isinstance(r, SegmentAnalysis) for r in results)
        
        # Verify all segments were analyzed
        analyzed_video_ids = {r.segment.video_id for r in results}
        assert analyzed_video_ids == {"video1", "video2", "video3"}
        
        # Verify Bedrock was called 3 times
        assert mock_bedrock_client.invoke_pegasus_analysis.call_count == 3
    
    @pytest.mark.asyncio
    async def test_analyze_segments_parallel_with_concurrency_limit(self, pegasus_worker, mock_bedrock_client, sample_segments):
        """Test that concurrency limit is respected."""
        # Mock Pegasus responses
        mock_bedrock_client.invoke_pegasus_analysis.side_effect = [
            {"message": f"Analysis {i}", "finishReason": "stop"}
            for i in range(3)
        ]
        
        # Test with max_concurrent=1 (sequential execution)
        results = await pegasus_worker.analyze_segments_parallel(
            segments=sample_segments,
            prompt="Describe the video",
            temperature=0.2,
            max_concurrent=1
        )
        
        # Should still get all results
        assert len(results) == 3
        
        # Verify all were called
        assert mock_bedrock_client.invoke_pegasus_analysis.call_count == 3
    
    @pytest.mark.asyncio
    async def test_analyze_segments_parallel_partial_failure(self, pegasus_worker, mock_bedrock_client, sample_segments):
        """Test graceful handling of partial failures."""
        # Mock Pegasus responses - second one fails
        mock_bedrock_client.invoke_pegasus_analysis.side_effect = [
            {"message": "Analysis of video 1", "finishReason": "stop"},
            Exception("Pegasus API error"),
            {"message": "Analysis of video 3", "finishReason": "stop"}
        ]
        
        # Test - should not raise exception
        results = await pegasus_worker.analyze_segments_parallel(
            segments=sample_segments,
            prompt="Describe the video",
            temperature=0.2,
            max_concurrent=3
        )
        
        # Should get 2 successful results (1st and 3rd)
        assert len(results) == 2
        
        # Verify successful analyses
        analyzed_video_ids = {r.segment.video_id for r in results}
        assert "video1" in analyzed_video_ids
        assert "video3" in analyzed_video_ids
        assert "video2" not in analyzed_video_ids  # Failed
    
    @pytest.mark.asyncio
    async def test_analyze_segments_parallel_all_failures(self, pegasus_worker, mock_bedrock_client, sample_segments):
        """Test handling when all analyses fail."""
        # Mock all failures
        mock_bedrock_client.invoke_pegasus_analysis.side_effect = Exception("Pegasus API error")
        
        # Test - should not raise exception
        results = await pegasus_worker.analyze_segments_parallel(
            segments=sample_segments,
            prompt="Describe the video",
            temperature=0.2,
            max_concurrent=3
        )
        
        # Should return empty list
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_segments_parallel_single_segment(self, pegasus_worker, mock_bedrock_client, sample_segment):
        """Test parallel analysis with a single segment."""
        # Mock Pegasus response
        mock_bedrock_client.invoke_pegasus_analysis.return_value = {
            "message": "Analysis result",
            "finishReason": "stop"
        }
        
        # Test with single segment
        results = await pegasus_worker.analyze_segments_parallel(
            segments=[sample_segment],
            prompt="Describe the video",
            temperature=0.2,
            max_concurrent=3
        )
        
        # Should get 1 result
        assert len(results) == 1
        assert results[0].segment == sample_segment
    
    @pytest.mark.asyncio
    async def test_analyze_segments_parallel_large_batch(self, pegasus_worker, mock_bedrock_client):
        """Test parallel analysis with many segments."""
        # Create 10 segments
        segments = [
            VideoSegment(
                video_id=f"video{i}",
                s3_uri=f"s3://bucket/video{i}.mp4",
                start_time=float(i * 10),
                end_time=float(i * 10 + 10),
                relevance_score=0.9 - (i * 0.05)
            )
            for i in range(10)
        ]
        
        # Mock Pegasus responses
        mock_bedrock_client.invoke_pegasus_analysis.side_effect = [
            {"message": f"Analysis {i}", "finishReason": "stop"}
            for i in range(10)
        ]
        
        # Test with max_concurrent=3
        results = await pegasus_worker.analyze_segments_parallel(
            segments=segments,
            prompt="Describe the video",
            temperature=0.2,
            max_concurrent=3
        )
        
        # Should get all 10 results
        assert len(results) == 10
        assert mock_bedrock_client.invoke_pegasus_analysis.call_count == 10


class TestAnalyzeSegmentsParallelValidation:
    """Tests for input validation in analyze_segments_parallel."""
    
    @pytest.mark.asyncio
    async def test_analyze_segments_parallel_empty_segments(self, pegasus_worker):
        """Test error handling for empty segments list."""
        with pytest.raises(ValueError) as exc_info:
            await pegasus_worker.analyze_segments_parallel(
                segments=[],
                prompt="Test prompt",
                temperature=0.2,
                max_concurrent=3
            )
        
        assert "segments cannot be empty" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_analyze_segments_parallel_invalid_max_concurrent(self, pegasus_worker, sample_segments):
        """Test error handling for invalid max_concurrent."""
        with pytest.raises(ValueError) as exc_info:
            await pegasus_worker.analyze_segments_parallel(
                segments=sample_segments,
                prompt="Test prompt",
                temperature=0.2,
                max_concurrent=0
            )
        
        assert "max_concurrent must be at least 1" in str(exc_info.value)


class TestAnalysisResultStructure:
    """Tests for SegmentAnalysis result structure."""
    
    @pytest.mark.asyncio
    async def test_segment_analysis_contains_all_fields(self, pegasus_worker, mock_bedrock_client, sample_segment):
        """Test that SegmentAnalysis contains all required fields."""
        mock_bedrock_client.invoke_pegasus_analysis.return_value = {
            "message": "Test analysis",
            "finishReason": "stop"
        }
        
        result = await pegasus_worker.analyze_segment(
            segment=sample_segment,
            prompt="Test prompt",
            temperature=0.2
        )
        
        # Verify all fields are present
        assert hasattr(result, "segment")
        assert hasattr(result, "insights")
        assert hasattr(result, "analyzed_at")
        
        # Verify field types
        assert isinstance(result.segment, VideoSegment)
        assert isinstance(result.insights, str)
        assert isinstance(result.analyzed_at, datetime)
    
    @pytest.mark.asyncio
    async def test_segment_analysis_preserves_segment_data(self, pegasus_worker, mock_bedrock_client, sample_segment):
        """Test that SegmentAnalysis preserves original segment data."""
        mock_bedrock_client.invoke_pegasus_analysis.return_value = {
            "message": "Test analysis",
            "finishReason": "stop"
        }
        
        result = await pegasus_worker.analyze_segment(
            segment=sample_segment,
            prompt="Test prompt",
            temperature=0.2
        )
        
        # Verify segment data is preserved
        assert result.segment.video_id == "video1"
        assert result.segment.s3_uri == "s3://bucket/video1.mp4"
        assert result.segment.start_time == 10.0
        assert result.segment.end_time == 20.0
        assert result.segment.relevance_score == 0.9
