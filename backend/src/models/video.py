"""Video data model for video archive system."""

from datetime import datetime
from typing import Dict, Any, List
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator, ConfigDict


class Video(BaseModel):
    """Represents a video file in an index.
    
    Attributes:
        id: Unique identifier (UUID)
        index_id: ID of the index this video belongs to
        filename: Original filename of the video
        s3_uri: S3 URI where the video is stored
        duration: Video duration in seconds
        uploaded_at: Timestamp when the video was uploaded
        embedding_ids: List of embedding IDs in S3 Vectors
        metadata: Additional metadata as key-value pairs
    """
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    index_id: str
    filename: str
    s3_uri: str
    duration: float = Field(gt=0, description="Video duration in seconds, must be positive")
    uploaded_at: datetime = Field(default_factory=datetime.now)
    embedding_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename is not empty and has valid extension."""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        
        valid_extensions = ['.mp4', '.mov', '.avi', '.mkv']
        if not any(v.lower().endswith(ext) for ext in valid_extensions):
            raise ValueError(f"Unsupported video format. Supported formats: {', '.join(valid_extensions)}")
        
        return v
    
    @field_validator('s3_uri')
    @classmethod
    def validate_s3_uri(cls, v: str) -> str:
        """Validate S3 URI format."""
        if not v.startswith('s3://'):
            raise ValueError("S3 URI must start with 's3://'")
        return v
