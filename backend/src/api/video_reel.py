"""Video reel generation API endpoints.

This module implements endpoints for generating video reels from search results.
"""

from typing import Annotated, List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field

from api.auth import verify_token
from services.video_reel_service import VideoReelService
from models.search import VideoClip
from exceptions import AWSServiceError


# Request/Response models
class VideoReelRequest(BaseModel):
    """Request model for video reel generation.
    
    Attributes:
        clips: List of video clips to concatenate
    """
    clips: List[VideoClip] = Field(
        ...,
        min_length=1,
        description="List of video clips to concatenate into a reel"
    )


class VideoReelResponse(BaseModel):
    """Response model for video reel generation.
    
    Attributes:
        reel_id: Unique identifier for the generated reel
        s3_key: S3 key where the reel is stored
        stream_url: Presigned URL for streaming the reel
        clip_count: Number of clips in the reel
    """
    reel_id: str = Field(..., description="Unique reel identifier")
    s3_key: str = Field(..., description="S3 key of the generated reel")
    stream_url: str = Field(..., description="Presigned URL for streaming")
    clip_count: int = Field(..., description="Number of clips in the reel")


class ErrorResponse(BaseModel):
    """Error response model.
    
    Attributes:
        detail: Error message
    """
    detail: str = Field(..., description="Error message")


# Create router
router = APIRouter()


# Dependency injection placeholders
_video_reel_service: VideoReelService = None


def set_video_reel_service(video_reel_service: VideoReelService):
    """Set the video reel service instance for dependency injection.
    
    Args:
        video_reel_service: Initialized VideoReelService instance
    """
    global _video_reel_service
    _video_reel_service = video_reel_service


def get_video_reel_service() -> VideoReelService:
    """Get the video reel service instance.
    
    Returns:
        VideoReelService instance
        
    Raises:
        RuntimeError: If service not initialized
    """
    if _video_reel_service is None:
        raise RuntimeError("VideoReelService not initialized")
    return _video_reel_service


@router.post(
    "/generate",
    response_model=VideoReelResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Video reel generated successfully",
            "model": VideoReelResponse
        },
        400: {
            "description": "Invalid request (empty clips list, etc.)",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Generate video reel from clips",
    description=(
        "Generate a video reel by concatenating search result clips. "
        "Each clip will have 1-second fade in/out transitions. "
        "The generated reel is stored in the videos-generated S3 folder."
    )
)
async def generate_video_reel(
    request: VideoReelRequest,
    authenticated: Annotated[bool, Depends(verify_token)],
    video_reel_service: Annotated[VideoReelService, Depends(get_video_reel_service)]
) -> VideoReelResponse:
    """Generate a video reel from search result clips.
    
    This endpoint:
    1. Downloads each video clip from S3
    2. Extracts the relevant time segments
    3. Applies 1-second fade in/out transitions
    4. Concatenates all clips into a single video
    5. Uploads the result to S3 in the videos-generated folder
    6. Returns a presigned URL for streaming
    
    Args:
        request: VideoReelRequest with list of clips
        authenticated: Authentication verification (injected)
        video_reel_service: VideoReelService instance (injected)
        
    Returns:
        VideoReelResponse: Generated reel information with streaming URL
        
    Raises:
        HTTPException: 400 if clips list is empty
        HTTPException: 401 if not authenticated
        HTTPException: 500 if generation fails
    """
    try:
        if not request.clips:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Clips list cannot be empty"
            )
        
        # Generate unique reel ID
        reel_id = str(uuid4())
        
        # Generate the video reel
        s3_key = await video_reel_service.generate_reel(
            clips=request.clips,
            reel_id=reel_id
        )
        
        # Generate presigned URL for streaming
        stream_url = video_reel_service.get_reel_url(s3_key)
        
        return VideoReelResponse(
            reel_id=reel_id,
            s3_key=s3_key,
            stream_url=stream_url,
            clip_count=len(request.clips)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AWSServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate video reel: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error generating video reel: {str(e)}"
        )
