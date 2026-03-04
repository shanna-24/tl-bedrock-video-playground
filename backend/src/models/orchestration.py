"""Data models for Jockey-inspired orchestration system.

This module defines the core data structures used throughout the orchestration
workflow for index-level video analysis.

Validates: Requirements 1.1, 1.4, 6.1, 6.2, 6.3, 6.4, 6.5
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class AnalysisIntent:
    """Represents the determined intent of an analysis query.
    
    The Supervisor component analyzes user queries to determine whether
    semantic search is needed and what type of analysis to perform.
    
    Attributes:
        needs_search: Whether Marengo search is required to find relevant segments
        analysis_type: Type of analysis - "specific" for targeted queries,
                      "general" for broad overview questions
        reasoning: Explanation of the intent classification decision
    """
    needs_search: bool
    analysis_type: str  # "specific" or "general"
    reasoning: str


@dataclass
class ExecutionPlan:
    """Structured plan for executing multi-video analysis.
    
    The Planner component creates execution plans that break down complex
    queries into actionable steps for the Workers.
    
    Attributes:
        search_queries: List of Marengo-compatible search terms for finding
                       relevant video segments
        analysis_prompts: List of prompts for Pegasus analysis of segments
        max_segments: Maximum number of segments to analyze (balances
                     thoroughness vs cost)
        parallel_execution: Whether to execute analyses in parallel
    """
    search_queries: List[str]
    analysis_prompts: List[str]
    max_segments: int
    parallel_execution: bool


@dataclass
class VideoSegment:
    """Represents a video segment for analysis.
    
    Video segments are temporal portions of videos identified by Marengo
    search as relevant to the user's query.
    
    Attributes:
        video_id: Unique identifier for the video
        s3_uri: S3 URI for the video file
        start_time: Start timestamp in seconds
        end_time: End timestamp in seconds
        relevance_score: Relevance score from Marengo search (0.0 to 1.0)
    """
    video_id: str
    s3_uri: str
    start_time: float
    end_time: float
    relevance_score: float


@dataclass
class SegmentAnalysis:
    """Results from analyzing a video segment.
    
    Contains the analysis insights from Pegasus along with metadata about
    the analyzed segment.
    
    Attributes:
        segment: The video segment that was analyzed
        insights: Analysis text from Pegasus model
        analyzed_at: Timestamp when the analysis was performed
    """
    segment: VideoSegment
    insights: str
    analyzed_at: datetime
