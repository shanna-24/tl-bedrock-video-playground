"""Unit tests for JockeyOrchestrator.

Tests the main orchestration component including:
- Full workflow coordination
- Fallback strategies
- Error handling
- Correlation ID propagation

Validates: Requirements 1.4, 7.1, 7.2, 7.3, 7.5
"""

import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from orchestration.orchestrator import JockeyOrchestrator
from models.orchestration import (
    AnalysisIntent,
    ExecutionPlan,
    VideoSegment,
    SegmentAnalysis
)
from models.analysis import AnalysisResult
from exceptions import AWSServiceError


@pytest.fixture
def mock_bedrock_client():
    """Create a mock BedrockClient."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_search_service():
    """Create a mock SearchService."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_config():
    """Create a mock Config with Jockey settings."""
    config = MagicMock()
    config.jockey.claude_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    config.jockey.parallel_analysis_limit = 3
    config.jockey.max_segments_per_query = 10
    return config


@pytest.fixture
def orchestrator(mock_bedrock_client, mock_search_service, mock_config):
    """Create a JockeyOrchestrator instance with mocked dependencies."""
    return JockeyOrchestrator(
        bedrock_client=mock_bedrock_client,
        search_service=mock_search_service,
        config=mock_config
    )


@pytest.fixture
def sample_video_uris():
    """Sample video S3 URIs."""
    return [
        "s3://bucket/videos/video1.mp4",
        "s3://bucket/videos/video2.mp4",
        "s3://bucket/videos/video3.mp4"
    ]


@pytest.fixture
def sample_intent_search():
    """Sample AnalysisIntent that requires search."""
    return AnalysisIntent(
        needs_search=True,
        analysis_type="specific",
        reasoning="Query asks about specific content"
    )


@pytest.fixture
def sample_intent_no_search():
    """Sample AnalysisIntent that doesn't require search."""
    return AnalysisIntent(
        needs_search=False,
        analysis_type="general",
        reasoning="Query asks for general summary"
    )


@pytest.fixture
def sample_execution_plan():
    """Sample ExecutionPlan with search queries."""
    return ExecutionPlan(
        search_queries=["dogs", "canine animals"],
        analysis_prompts=["Describe the dogs in this video"],
        max_segments=10,
        parallel_execution=True
    )


@pytest.fixture
def sample_segments():
    """Sample VideoSegment objects."""
    return [
        VideoSegment(
            video_id="video1",
            s3_uri="s3://bucket/videos/video1.mp4",
            start_time=10.0,
            end_time=20.0,
            relevance_score=0.95
        ),
        VideoSegment(
            video_id="video2",
            s3_uri="s3://bucket/videos/video2.mp4",
            start_time=30.0,
            end_time=40.0,
            relevance_score=0.85
        )
    ]


@pytest.fixture
def sample_analyses(sample_segments):
    """Sample SegmentAnalysis objects."""
    return [
        SegmentAnalysis(
            segment=sample_segments[0],
            insights="Found a golden retriever playing in the park",
            analyzed_at=datetime.now()
        ),
        SegmentAnalysis(
            segment=sample_segments[1],
            insights="Spotted a husky running on the beach",
            analyzed_at=datetime.now()
        )
    ]


class TestOrchestratorInitialization:
    """Tests for JockeyOrchestrator initialization."""
    
    def test_initialization_success(self, orchestrator):
        """Test successful orchestrator initialization."""
        assert orchestrator.supervisor is not None
        assert orchestrator.planner is not None
        assert orchestrator.marengo_worker is not None
        assert orchestrator.pegasus_worker is not None
        assert orchestrator.aggregator is not None
    
    def test_initialization_with_custom_config(
        self,
        mock_bedrock_client,
        mock_search_service
    ):
        """Test initialization with custom configuration."""
        config = MagicMock()
        config.jockey.claude_model_id = "custom-model-id"
        config.jockey.parallel_analysis_limit = 5
        
        orchestrator = JockeyOrchestrator(
            bedrock_client=mock_bedrock_client,
            search_service=mock_search_service,
            config=config
        )
        
        assert orchestrator.config.jockey.claude_model_id == "custom-model-id"
        assert orchestrator.config.jockey.parallel_analysis_limit == 5


class TestAnalyzeIndexFullWorkflow:
    """Tests for the full analyze_index workflow."""
    
    @pytest.mark.asyncio
    async def test_full_workflow_with_search(
        self,
        orchestrator,
        sample_video_uris,
        sample_intent_search,
        sample_execution_plan,
        sample_segments,
        sample_analyses
    ):
        """Test full workflow with search-based analysis."""
        # Mock all component methods
        orchestrator.supervisor.determine_intent = AsyncMock(
            return_value=sample_intent_search
        )
        orchestrator.planner.create_execution_plan = AsyncMock(
            return_value=sample_execution_plan
        )
        orchestrator.marengo_worker.search_segments = AsyncMock(
            return_value=sample_segments
        )
        orchestrator.pegasus_worker.analyze_segments_parallel = AsyncMock(
            return_value=sample_analyses
        )
        orchestrator.aggregator.aggregate_insights = AsyncMock(
            return_value="Aggregated insights about dogs"
        )
        
        # Execute
        result = await orchestrator.analyze_index(
            index_id="test-index",
            query="Find all dogs",
            video_s3_uris=sample_video_uris,
            temperature=0.2
        )
        
        # Verify result
        assert isinstance(result, AnalysisResult)
        assert result.query == "Find all dogs"
        assert result.scope == "index"
        assert result.scope_id == "test-index"
        assert result.insights == "Aggregated insights about dogs"
        assert result.metadata["video_count"] == 3
        assert result.metadata["segments_analyzed"] == 2
        assert result.metadata["videos_analyzed"] == 2
        assert "correlation_id" in result.metadata
        
        # Verify all components were called
        orchestrator.supervisor.determine_intent.assert_called_once_with("Find all dogs")
        orchestrator.planner.create_execution_plan.assert_called_once()
        orchestrator.marengo_worker.search_segments.assert_called_once()
        orchestrator.pegasus_worker.analyze_segments_parallel.assert_called_once()
        orchestrator.aggregator.aggregate_insights.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_full_workflow_without_search(
        self,
        orchestrator,
        sample_video_uris,
        sample_intent_no_search,
        sample_analyses
    ):
        """Test full workflow with direct analysis (no search)."""
        # Create execution plan without search queries
        plan = ExecutionPlan(
            search_queries=[],
            analysis_prompts=["Summarize the video"],
            max_segments=5,
            parallel_execution=True
        )
        
        # Mock component methods
        orchestrator.supervisor.determine_intent = AsyncMock(
            return_value=sample_intent_no_search
        )
        orchestrator.planner.create_execution_plan = AsyncMock(
            return_value=plan
        )
        orchestrator.pegasus_worker.analyze_segments_parallel = AsyncMock(
            return_value=sample_analyses
        )
        orchestrator.aggregator.aggregate_insights = AsyncMock(
            return_value="General summary of videos"
        )
        
        # Execute
        result = await orchestrator.analyze_index(
            index_id="test-index",
            query="Summarize these videos",
            video_s3_uris=sample_video_uris
        )
        
        # Verify result
        assert isinstance(result, AnalysisResult)
        assert result.insights == "General summary of videos"
        assert result.metadata["intent_needs_search"] is False
        
        # Verify search was not called
        orchestrator.marengo_worker.search_segments = AsyncMock()
        assert not orchestrator.marengo_worker.search_segments.called


class TestFallbackStrategies:
    """Tests for fallback strategies."""
    
    @pytest.mark.asyncio
    async def test_fallback_when_search_returns_no_results(
        self,
        orchestrator,
        sample_video_uris,
        sample_intent_search,
        sample_execution_plan,
        sample_analyses
    ):
        """Test fallback to representative videos when search returns no results."""
        # Mock search to return empty list
        orchestrator.supervisor.determine_intent = AsyncMock(
            return_value=sample_intent_search
        )
        orchestrator.planner.create_execution_plan = AsyncMock(
            return_value=sample_execution_plan
        )
        orchestrator.marengo_worker.search_segments = AsyncMock(
            return_value=[]  # No search results
        )
        orchestrator.pegasus_worker.analyze_segments_parallel = AsyncMock(
            return_value=sample_analyses
        )
        orchestrator.aggregator.aggregate_insights = AsyncMock(
            return_value="Analysis of representative videos"
        )
        
        # Execute
        result = await orchestrator.analyze_index(
            index_id="test-index",
            query="Find rare content",
            video_s3_uris=sample_video_uris
        )
        
        # Verify fallback was used
        assert isinstance(result, AnalysisResult)
        assert result.insights == "Analysis of representative videos"
        
        # Verify PegasusWorker was called with representative segments
        orchestrator.pegasus_worker.analyze_segments_parallel.assert_called_once()
        call_args = orchestrator.pegasus_worker.analyze_segments_parallel.call_args
        segments = call_args[1]["segments"]
        assert len(segments) > 0
        assert all(seg.relevance_score == 0.5 for seg in segments)
    
    @pytest.mark.asyncio
    async def test_fallback_when_search_fails(
        self,
        orchestrator,
        sample_video_uris,
        sample_intent_search,
        sample_execution_plan,
        sample_analyses
    ):
        """Test fallback to representative videos when search fails with exception."""
        # Mock search to raise exception
        orchestrator.supervisor.determine_intent = AsyncMock(
            return_value=sample_intent_search
        )
        orchestrator.planner.create_execution_plan = AsyncMock(
            return_value=sample_execution_plan
        )
        orchestrator.marengo_worker.search_segments = AsyncMock(
            side_effect=Exception("Search service unavailable")
        )
        orchestrator.pegasus_worker.analyze_segments_parallel = AsyncMock(
            return_value=sample_analyses
        )
        orchestrator.aggregator.aggregate_insights = AsyncMock(
            return_value="Analysis despite search failure"
        )
        
        # Execute
        result = await orchestrator.analyze_index(
            index_id="test-index",
            query="Find content",
            video_s3_uris=sample_video_uris
        )
        
        # Verify fallback was used
        assert isinstance(result, AnalysisResult)
        assert result.insights == "Analysis despite search failure"
    
    @pytest.mark.asyncio
    async def test_fallback_when_aggregation_fails(
        self,
        orchestrator,
        sample_video_uris,
        sample_intent_search,
        sample_execution_plan,
        sample_segments,
        sample_analyses
    ):
        """Test fallback to raw insights when aggregation fails."""
        # Mock aggregation to fail
        orchestrator.supervisor.determine_intent = AsyncMock(
            return_value=sample_intent_search
        )
        orchestrator.planner.create_execution_plan = AsyncMock(
            return_value=sample_execution_plan
        )
        orchestrator.marengo_worker.search_segments = AsyncMock(
            return_value=sample_segments
        )
        orchestrator.pegasus_worker.analyze_segments_parallel = AsyncMock(
            return_value=sample_analyses
        )
        orchestrator.aggregator.aggregate_insights = AsyncMock(
            side_effect=Exception("Claude API unavailable")
        )
        
        # Execute
        result = await orchestrator.analyze_index(
            index_id="test-index",
            query="Find dogs",
            video_s3_uris=sample_video_uris
        )
        
        # Verify raw insights fallback was used
        assert isinstance(result, AnalysisResult)
        assert "# Analysis Results" in result.insights
        assert "video1" in result.insights
        assert "video2" in result.insights
        assert "golden retriever" in result.insights
        assert "husky" in result.insights
    
    @pytest.mark.asyncio
    async def test_partial_failure_handling(
        self,
        orchestrator,
        sample_video_uris,
        sample_intent_search,
        sample_execution_plan,
        sample_segments
    ):
        """Test handling of partial analysis failures."""
        # Create one successful and one failed analysis
        successful_analysis = SegmentAnalysis(
            segment=sample_segments[0],
            insights="Successful analysis",
            analyzed_at=datetime.now()
        )
        
        # Mock to return only successful analysis
        orchestrator.supervisor.determine_intent = AsyncMock(
            return_value=sample_intent_search
        )
        orchestrator.planner.create_execution_plan = AsyncMock(
            return_value=sample_execution_plan
        )
        orchestrator.marengo_worker.search_segments = AsyncMock(
            return_value=sample_segments
        )
        orchestrator.pegasus_worker.analyze_segments_parallel = AsyncMock(
            return_value=[successful_analysis]  # Only one succeeded
        )
        orchestrator.aggregator.aggregate_insights = AsyncMock(
            return_value="Partial results aggregated"
        )
        
        # Execute
        result = await orchestrator.analyze_index(
            index_id="test-index",
            query="Find content",
            video_s3_uris=sample_video_uris
        )
        
        # Verify partial results were returned
        assert isinstance(result, AnalysisResult)
        assert result.insights == "Partial results aggregated"
        assert result.metadata["segments_analyzed"] == 1


class TestErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.asyncio
    async def test_empty_query_raises_error(
        self,
        orchestrator,
        sample_video_uris
    ):
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError, match="query cannot be empty"):
            await orchestrator.analyze_index(
                index_id="test-index",
                query="",
                video_s3_uris=sample_video_uris
            )
    
    @pytest.mark.asyncio
    async def test_no_videos_raises_error(
        self,
        orchestrator
    ):
        """Test that empty video list raises ValueError."""
        with pytest.raises(ValueError, match="No videos found"):
            await orchestrator.analyze_index(
                index_id="test-index",
                query="Find content",
                video_s3_uris=[]
            )
    
    @pytest.mark.asyncio
    async def test_all_analyses_fail_raises_error(
        self,
        orchestrator,
        sample_video_uris,
        sample_intent_search,
        sample_execution_plan,
        sample_segments
    ):
        """Test that error is raised when all analyses fail."""
        # Mock all analyses to fail
        orchestrator.supervisor.determine_intent = AsyncMock(
            return_value=sample_intent_search
        )
        orchestrator.planner.create_execution_plan = AsyncMock(
            return_value=sample_execution_plan
        )
        orchestrator.marengo_worker.search_segments = AsyncMock(
            return_value=sample_segments
        )
        orchestrator.pegasus_worker.analyze_segments_parallel = AsyncMock(
            return_value=[]  # All failed
        )
        
        # Execute and expect error
        with pytest.raises(AWSServiceError, match="All segment analyses failed"):
            await orchestrator.analyze_index(
                index_id="test-index",
                query="Find content",
                video_s3_uris=sample_video_uris
            )
    
    @pytest.mark.asyncio
    async def test_supervisor_failure_propagates(
        self,
        orchestrator,
        sample_video_uris
    ):
        """Test that Supervisor failures propagate as AWSServiceError."""
        # Mock supervisor to fail
        orchestrator.supervisor.determine_intent = AsyncMock(
            side_effect=Exception("Supervisor failed")
        )
        
        # Execute and expect error
        with pytest.raises(AWSServiceError, match="orchestration failed"):
            await orchestrator.analyze_index(
                index_id="test-index",
                query="Find content",
                video_s3_uris=sample_video_uris
            )


class TestCorrelationID:
    """Tests for correlation ID generation and propagation."""
    
    @pytest.mark.asyncio
    async def test_correlation_id_in_result(
        self,
        orchestrator,
        sample_video_uris,
        sample_intent_search,
        sample_execution_plan,
        sample_segments,
        sample_analyses
    ):
        """Test that correlation ID is included in result metadata."""
        # Mock all components
        orchestrator.supervisor.determine_intent = AsyncMock(
            return_value=sample_intent_search
        )
        orchestrator.planner.create_execution_plan = AsyncMock(
            return_value=sample_execution_plan
        )
        orchestrator.marengo_worker.search_segments = AsyncMock(
            return_value=sample_segments
        )
        orchestrator.pegasus_worker.analyze_segments_parallel = AsyncMock(
            return_value=sample_analyses
        )
        orchestrator.aggregator.aggregate_insights = AsyncMock(
            return_value="Aggregated insights"
        )
        
        # Execute
        result = await orchestrator.analyze_index(
            index_id="test-index",
            query="Find content",
            video_s3_uris=sample_video_uris
        )
        
        # Verify correlation ID is present and is a valid UUID
        assert "correlation_id" in result.metadata
        correlation_id = result.metadata["correlation_id"]
        assert isinstance(correlation_id, str)
        assert len(correlation_id) == 36  # UUID format
        assert correlation_id.count('-') == 4  # UUID has 4 hyphens


class TestRepresentativeSegments:
    """Tests for representative segment creation."""
    
    def test_create_representative_segments_all_videos(
        self,
        orchestrator,
        sample_video_uris
    ):
        """Test creating representative segments when max_segments >= video count."""
        segments = orchestrator._create_representative_segments(
            video_s3_uris=sample_video_uris,
            max_segments=10
        )
        
        # Should return all videos
        assert len(segments) == len(sample_video_uris)
        assert all(seg.relevance_score == 0.5 for seg in segments)
        assert all(seg.start_time == 0.0 for seg in segments)
        assert all(seg.end_time == 0.0 for seg in segments)
    
    def test_create_representative_segments_subset(
        self,
        orchestrator,
        sample_video_uris
    ):
        """Test creating representative segments when max_segments < video count."""
        segments = orchestrator._create_representative_segments(
            video_s3_uris=sample_video_uris,
            max_segments=2
        )
        
        # Should return evenly distributed subset
        assert len(segments) == 2
        assert all(seg.relevance_score == 0.5 for seg in segments)
    
    def test_create_representative_segments_single_video(
        self,
        orchestrator
    ):
        """Test creating representative segments with single video."""
        segments = orchestrator._create_representative_segments(
            video_s3_uris=["s3://bucket/video.mp4"],
            max_segments=5
        )
        
        assert len(segments) == 1
        assert segments[0].s3_uri == "s3://bucket/video.mp4"


class TestRawInsightsFormatting:
    """Tests for raw insights formatting."""
    
    def test_format_raw_insights(
        self,
        orchestrator,
        sample_analyses
    ):
        """Test formatting raw insights as fallback."""
        formatted = orchestrator._format_raw_insights(sample_analyses)
        
        # Verify structure
        assert "# Analysis Results" in formatted
        assert "Analyzed 2 video segments" in formatted
        assert "## Video 1: video1" in formatted
        assert "## Video 2: video2" in formatted
        assert "golden retriever" in formatted
        assert "husky" in formatted
        assert "10.0s - 20.0s" in formatted
        assert "30.0s - 40.0s" in formatted
        assert "0.950" in formatted  # Relevance score
        assert "0.850" in formatted
    
    def test_format_raw_insights_single_analysis(
        self,
        orchestrator,
        sample_segments
    ):
        """Test formatting raw insights with single analysis."""
        analysis = SegmentAnalysis(
            segment=sample_segments[0],
            insights="Single insight",
            analyzed_at=datetime.now()
        )
        
        formatted = orchestrator._format_raw_insights([analysis])
        
        assert "Analyzed 1 video segments" in formatted
        assert "## Video 1: video1" in formatted
        assert "Single insight" in formatted
