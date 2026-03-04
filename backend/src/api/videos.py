"""Video playback API endpoints for TL-Video-Playground.

This module implements endpoints for video streaming and playback.

Validates: Requirements 2.1, 2.2
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.auth import verify_token
from services.video_service import VideoService
from services.index_manager import IndexManager
from exceptions import (
    ResourceNotFoundError,
    ValidationError,
    AWSServiceError
)


# Request/Response models
class VideoStreamResponse(BaseModel):
    """Response model for video stream URL.
    
    Attributes:
        video_id: ID of the video
        stream_url: Presigned URL for video streaming
        start_timecode: Optional start time in seconds
        expiration: URL expiration time in seconds
    """
    video_id: str = Field(..., description="Video identifier")
    stream_url: str = Field(..., description="Presigned URL for streaming")
    start_timecode: Optional[float] = Field(
        None,
        description="Start time in seconds (if specified)"
    )
    expiration: int = Field(
        default=3600,
        description="URL expiration time in seconds"
    )


class ErrorResponse(BaseModel):
    """Error response model.
    
    Attributes:
        detail: Error message
    """
    detail: str = Field(..., description="Error message")


# Create router
router = APIRouter()


# Dependency injection placeholders (will be set by main.py)
_video_service: VideoService = None
_index_manager: IndexManager = None
_s3_client = None


def set_video_service(video_service: VideoService):
    """Set the video service instance for dependency injection.
    
    Args:
        video_service: Initialized VideoService instance
    """
    global _video_service
    _video_service = video_service


def set_index_manager(index_manager: IndexManager):
    """Set the index manager instance for dependency injection.
    
    Args:
        index_manager: Initialized IndexManager instance
    """
    global _index_manager
    _index_manager = index_manager


def set_s3_client(s3_client):
    """Set the S3 client instance for dependency injection.
    
    Args:
        s3_client: Initialized S3Client instance
    """
    global _s3_client
    _s3_client = s3_client


def get_video_service() -> VideoService:
    """Get the video service instance.
    
    Returns:
        VideoService instance
        
    Raises:
        RuntimeError: If video service is not initialized
    """
    if _video_service is None:
        raise RuntimeError("Video service not initialized")
    return _video_service


def get_index_manager() -> IndexManager:
    """Get the index manager instance.
    
    Returns:
        IndexManager instance
        
    Raises:
        RuntimeError: If index manager is not initialized
    """
    if _index_manager is None:
        raise RuntimeError("Index manager not initialized")
    return _index_manager


def get_s3_client():
    """Get the S3 client instance.
    
    Returns:
        S3Client instance
        
    Raises:
        RuntimeError: If S3 client is not initialized
    """
    if _s3_client is None:
        raise RuntimeError("S3 client not initialized")
    return _s3_client


@router.get(
    "/{video_id}/stream",
    response_model=VideoStreamResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Video stream URL generated successfully",
            "model": VideoStreamResponse
        },
        400: {
            "description": "Invalid request (negative start_time, etc.)",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Video not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Get video stream URL",
    description=(
        "Generate a presigned URL for video streaming. "
        "Optionally specify a start_time parameter to begin playback at a specific timecode."
    )
)
async def get_video_stream(
    video_id: str,
    start_time: Annotated[
        Optional[float],
        Query(
            description="Start time in seconds for video playback",
            ge=0.0,
            example=30.5
        )
    ] = None,
    authenticated: Annotated[bool, Depends(verify_token)] = None,
    video_service: Annotated[VideoService, Depends(get_video_service)] = None,
    index_manager: Annotated[IndexManager, Depends(get_index_manager)] = None
) -> VideoStreamResponse:
    """Get a presigned URL for video streaming.
    
    This endpoint generates a presigned S3 URL that allows temporary access
    to the video file for streaming. The URL is valid for 1 hour by default.
    
    If a start_time is provided, the URL will include a fragment identifier
    (#t=start_time) that HTML5 video players can use to begin playback at
    the specified timecode.
    
    Args:
        video_id: ID of the video to stream
        start_time: Optional start time in seconds (must be non-negative)
        authenticated: Authentication verification (injected)
        video_service: VideoService instance (injected)
        index_manager: IndexManager instance (injected)
        
    Returns:
        VideoStreamResponse: Presigned URL and metadata
        
    Raises:
        HTTPException: 400 if start_time is negative
        HTTPException: 401 if not authenticated
        HTTPException: 404 if video not found
        HTTPException: 500 if URL generation fails
        
    Validates: Requirements 2.1, 2.2
    """
    try:
        # Validate start_time if provided
        if start_time is not None and start_time < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_time must be non-negative"
            )
        
        # Find the video across all indexes to get its S3 key
        # We need to search through all indexes to find the video
        video = None
        indexes = await index_manager.list_indexes()
        
        for index in indexes:
            videos = await index_manager.list_videos_in_index(index.id)
            for v in videos:
                if v.id == video_id:
                    video = v
                    break
            if video:
                break
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {video_id} not found"
            )
        
        # Extract S3 key from S3 URI (format: s3://bucket/key)
        s3_key = video.s3_uri.replace(f"s3://{video_service.config.s3_bucket_name}/", "")
        
        # Generate presigned URL
        stream_url = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=start_time,
            expiration=3600  # 1 hour
        )
        
        return VideoStreamResponse(
            video_id=video_id,
            stream_url=stream_url,
            start_timecode=start_time,
            expiration=3600
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise
    except ValueError as e:
        # Handle validation errors from video service
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValidationError as e:
        # Handle validation errors
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ResourceNotFoundError as e:
        # Handle video not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AWSServiceError as e:
        # Handle AWS service errors
        error_msg = str(e).lower()
        if "throttl" in error_msg or "rate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Service temporarily unavailable, please retry"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate video stream URL: {str(e)}"
            )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate video stream URL: {str(e)}"
        )


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Video deleted successfully"
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Video not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Delete a video",
    description=(
        "Delete a video from its index, including all related data: "
        "video file from S3, thumbnail from S3, embeddings from S3 Vectors, "
        "and embedding job records. Other videos in the index remain untouched."
    )
)
async def delete_video(
    video_id: str,
    authenticated: Annotated[bool, Depends(verify_token)] = None,
    index_manager: Annotated[IndexManager, Depends(get_index_manager)] = None,
    s3_client: Annotated["S3Client", Depends(get_s3_client)] = None
) -> dict:
    """Delete a video and all its related data.
    
    This endpoint performs comprehensive cleanup:
    1. Removes video file from S3
    2. Removes thumbnail from S3
    3. Removes embeddings from S3 Vectors
    4. Removes embedding job records
    5. Removes video metadata from index
    
    Other videos in the same index are not affected.
    
    Args:
        video_id: ID of the video to delete
        authenticated: Authentication verification (injected)
        index_manager: IndexManager instance (injected)
        s3_client: S3Client instance (injected)
        
    Returns:
        Success message with deleted video ID
        
    Raises:
        HTTPException: 401 if not authenticated
        HTTPException: 404 if video not found
        HTTPException: 500 if deletion fails
    """
    try:
        # Delete the video using index manager
        await index_manager.delete_video(video_id, s3_client=s3_client)
        
        return {
            "message": "Video and all related data deleted successfully",
            "deleted_video_id": video_id
        }
        
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AWSServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete video: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete video: {str(e)}"
        )


@router.get(
    "/{video_id}/transcription",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Transcription status retrieved"
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Transcription not found",
            "model": ErrorResponse
        }
    },
    summary="Check transcription status",
    description="Check if transcription is available for a video"
)
async def get_transcription_status(
    video_id: str,
    authenticated: Annotated[bool, Depends(verify_token)] = None,
    s3_client: Annotated["S3Client", Depends(get_s3_client)] = None
) -> dict:
    """Check if transcription exists for a video.
    
    Args:
        video_id: ID of the video
        authenticated: Authentication verification (injected)
        s3_client: S3Client instance (injected)
        
    Returns:
        Status indicating if transcription exists
        
    Raises:
        HTTPException: 401 if not authenticated
        HTTPException: 404 if transcription not found
    """
    try:
        # Check if transcription segments file exists in S3
        key = f"transcriptions/segments/{video_id}.json"
        
        try:
            s3_client.get_object_metadata(key=key)
            return {
                "video_id": video_id,
                "has_transcription": True,
                "status": "available"
            }
        except Exception:
            # File doesn't exist
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transcription not available yet"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check transcription status: {str(e)}"
        )
