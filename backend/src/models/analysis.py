"""Analysis-related data models for video archive system."""

from datetime import datetime
from typing import Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


class AnalysisResult(BaseModel):
    """Represents the result of video content analysis.
    
    Attributes:
        query: The analysis query string
        scope: Scope of analysis - either "index" or "video"
        scope_id: ID of the index or video being analyzed
        insights: Formatted analysis text from the AI model
        analyzed_at: Timestamp when the analysis was performed
        metadata: Additional metadata as key-value pairs
    """
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    query: str
    scope: Literal["index", "video"] = Field(description="Analysis scope: 'index' or 'video'")
    scope_id: str
    insights: str
    analyzed_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query is not empty."""
        if not v or not v.strip():
            raise ValueError("Analysis query cannot be empty")
        return v
    
    @field_validator('scope_id')
    @classmethod
    def validate_scope_id(cls, v: str) -> str:
        """Validate scope_id is not empty."""
        if not v or not v.strip():
            raise ValueError("Scope ID cannot be empty")
        return v
    
    @field_validator('insights')
    @classmethod
    def validate_insights(cls, v: str) -> str:
        """Validate insights is not empty."""
        if not v or not v.strip():
            raise ValueError("Analysis insights cannot be empty")
        return v
