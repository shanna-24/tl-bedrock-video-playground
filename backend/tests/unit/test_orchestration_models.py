"""Unit tests for orchestration data models.

Validates: Requirements 1.1, 1.4
"""

import pytest
from datetime import datetime
from src.models.orchestration import (
    AnalysisIntent,
    ExecutionPlan,
    VideoSegment,
    SegmentAnalysis,
)


class TestAnalysisIntent:
    """Tests for AnalysisIntent data model."""
    
    def test_create_valid_intent_with_search(self):
        """Test creating a valid AnalysisIntent that needs search."""
        intent = AnalysisIntent(
            needs_search=True,
            analysis_type="specific",
            reasoning="Query asks about specific events"
        )
        
        assert intent.needs_search is True
        assert intent.analysis_type == "specific"
        assert intent.reasoning == "Query asks about specific events"
    
    def test_create_valid_intent_without_search(self):
        """Test creating a valid AnalysisIntent that doesn't need search."""
        intent = AnalysisIntent(
            needs_search=False,
            analysis_type="general",
            reasoning="Query asks for general overview"
        )
        
        assert intent.needs_search is False
        assert intent.analysis_type == "general"
        assert intent.reasoning == "Query asks for general overview"


class TestExecutionPlan:
    """Tests for ExecutionPlan data model."""
    
    def test_create_valid_execution_plan(self):
        """Test creating a valid ExecutionPlan."""
        plan = ExecutionPlan(
            search_queries=["action scenes", "car chase"],
            analysis_prompts=["Describe the action", "Analyze the chase"],
            max_segments=10,
            parallel_execution=True
        )
        
        assert len(plan.search_queries) == 2
        assert plan.search_queries[0] == "action scenes"
        assert len(plan.analysis_prompts) == 2
        assert plan.max_segments == 10
        assert plan.parallel_execution is True
    
    def test_create_execution_plan_with_empty_lists(self):
        """Test creating an ExecutionPlan with empty lists."""
        plan = ExecutionPlan(
            search_queries=[],
            analysis_prompts=[],
            max_segments=5,
            parallel_execution=False
        )
        
        assert len(plan.search_queries) == 0
        assert len(plan.analysis_prompts) == 0
        assert plan.max_segments == 5
        assert plan.parallel_execution is False


class TestVideoSegment:
    """Tests for VideoSegment data model."""
    
    def test_create_valid_video_segment(self):
        """Test creating a valid VideoSegment."""
        segment = VideoSegment(
            video_id="video123",
            s3_uri="s3://bucket/video.mp4",
            start_time=10.5,
            end_time=25.3,
            relevance_score=0.85
        )
        
        assert segment.video_id == "video123"
        assert segment.s3_uri == "s3://bucket/video.mp4"
        assert segment.start_time == 10.5
        assert segment.end_time == 25.3
        assert segment.relevance_score == 0.85
    
    def test_create_video_segment_with_zero_times(self):
        """Test creating a VideoSegment with zero start time."""
        segment = VideoSegment(
            video_id="video456",
            s3_uri="s3://bucket/video2.mp4",
            start_time=0.0,
            end_time=5.0,
            relevance_score=0.95
        )
        
        assert segment.start_time == 0.0
        assert segment.end_time == 5.0
    
    def test_create_video_segment_with_low_relevance(self):
        """Test creating a VideoSegment with low relevance score."""
        segment = VideoSegment(
            video_id="video789",
            s3_uri="s3://bucket/video3.mp4",
            start_time=100.0,
            end_time=120.0,
            relevance_score=0.1
        )
        
        assert segment.relevance_score == 0.1


class TestSegmentAnalysis:
    """Tests for SegmentAnalysis data model."""
    
    def test_create_valid_segment_analysis(self):
        """Test creating a valid SegmentAnalysis."""
        segment = VideoSegment(
            video_id="video123",
            s3_uri="s3://bucket/video.mp4",
            start_time=10.0,
            end_time=20.0,
            relevance_score=0.9
        )
        
        now = datetime.now()
        analysis = SegmentAnalysis(
            segment=segment,
            insights="This segment shows an action scene with cars.",
            analyzed_at=now
        )
        
        assert analysis.segment == segment
        assert analysis.insights == "This segment shows an action scene with cars."
        assert analysis.analyzed_at == now
    
    def test_segment_analysis_preserves_segment_data(self):
        """Test that SegmentAnalysis preserves all segment data."""
        segment = VideoSegment(
            video_id="video456",
            s3_uri="s3://bucket/video2.mp4",
            start_time=5.5,
            end_time=15.5,
            relevance_score=0.75
        )
        
        analysis = SegmentAnalysis(
            segment=segment,
            insights="Analysis results here",
            analyzed_at=datetime.now()
        )
        
        # Verify all segment data is preserved
        assert analysis.segment.video_id == "video456"
        assert analysis.segment.s3_uri == "s3://bucket/video2.mp4"
        assert analysis.segment.start_time == 5.5
        assert analysis.segment.end_time == 15.5
        assert analysis.segment.relevance_score == 0.75
