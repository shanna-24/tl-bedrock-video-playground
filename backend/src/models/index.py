"""Index data model for video archive system."""

from datetime import datetime
from typing import Dict, Any
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator, ConfigDict


class Index(BaseModel):
    """Represents a video index with metadata.
    
    Attributes:
        id: Unique identifier (UUID)
        name: User-provided name for the index
        created_at: Timestamp when the index was created
        video_count: Number of videos in the index
        s3_vectors_collection_id: ID of the S3 Vectors collection
        metadata: Additional metadata as key-value pairs
    """
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    created_at: datetime = Field(default_factory=datetime.now)
    video_count: int = Field(default=0, ge=0, description="Number of videos, must be non-negative")
    s3_vectors_collection_id: str = Field(default="")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate index name is alphanumeric and 3-50 characters."""
        if not v or not v.strip():
            raise ValueError("Index name cannot be empty")
        
        v = v.strip()
        
        # Check length
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Index name must be 3-50 characters")
        
        # Check alphanumeric (allow spaces, hyphens, underscores)
        if not all(c.isalnum() or c in ' -_' for c in v):
            raise ValueError("Index name must be alphanumeric (spaces, hyphens, and underscores allowed)")
        
        return v
    @classmethod
    def create(cls, name: str, s3_vectors_collection_id: str = "") -> "Index":
        """Create a new Index with generated ID and current timestamp.
        
        Args:
            name: User-provided name for the index
            s3_vectors_collection_id: Optional S3 Vectors collection ID
            
        Returns:
            New Index instance
        """
        return cls(
            name=name,
            s3_vectors_collection_id=s3_vectors_collection_id,
        )

