"""Search-related data models for video archive system."""

from typing import List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class VideoClip(BaseModel):
    """Represents a segment of a video identified by timecodes.
    
    Attributes:
        video_id: ID of the video this clip belongs to
        start_timecode: Start time in seconds
        end_timecode: End time in seconds
        relevance_score: Relevance score from 0.0 to 1.0
        screenshot_url: URL to screenshot of the clip
        video_stream_url: Presigned URL to stream the video
        metadata: Additional metadata as key-value pairs
    """
    video_id: str
    start_timecode: float = Field(ge=0, description="Start time in seconds, must be non-negative")
    end_timecode: float = Field(ge=0, description="End time in seconds, must be non-negative")
    relevance_score: float = Field(ge=0.0, le=1.0, description="Relevance score between 0.0 and 1.0")
    screenshot_url: str
    video_stream_url: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('end_timecode')
    @classmethod
    def validate_timecodes(cls, v: float, info) -> float:
        """Validate that end_timecode is greater than start_timecode."""
        if 'start_timecode' in info.data and v <= info.data['start_timecode']:
            raise ValueError("end_timecode must be greater than start_timecode")
        return v
    
    @field_validator('screenshot_url', 'video_stream_url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL is not empty."""
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        return v


class SearchResults(BaseModel):
    """Represents search results from a natural language query.
    
    Attributes:
        query: The search query string
        clips: List of matching video clips
        total_results: Total number of results found
        search_time: Time taken to perform the search in seconds
    """
    query: str
    clips: List[VideoClip] = Field(default_factory=list)
    total_results: int = Field(ge=0, description="Total results must be non-negative")
    search_time: float = Field(ge=0, description="Search time in seconds, must be non-negative")
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query is not empty."""
        if not v or not v.strip():
            raise ValueError("Search query cannot be empty")
        return v
    
    @field_validator('total_results')
    @classmethod
    def validate_total_results(cls, v: int, info) -> int:
        """Validate total_results matches clips length."""
        if 'clips' in info.data and v != len(info.data['clips']):
            raise ValueError("total_results must match the number of clips")
        return v
