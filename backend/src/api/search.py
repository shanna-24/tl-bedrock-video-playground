"""Search API endpoints for TL-Video-Playground.

This module implements endpoints for natural language video search.

Validates: Requirements 3.1, 3.2, 3.3
"""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import verify_token
from services.search_service import SearchService
from models.search import SearchResults, VideoClip
from utils.image_validator import ImageValidator
from exceptions import (
    ResourceNotFoundError,
    ValidationError,
    AWSServiceError,
    BedrockError
)


# Request/Response models
class SearchRequest(BaseModel):
    """Request model for video search.
    
    Supports three search modes:
    - Text-only: Provide only query field
    - Image-only: Provide only image and image_format fields
    - Multimodal: Provide query, image, and image_format fields
    
    Attributes:
        index_id: ID of the index to search
        query: Optional natural language search query
        image: Optional base64-encoded image data
        image_format: Optional image format (jpeg, jpg, png, webp)
        top_k: Number of results to return (default: 10)
        modalities: List of modalities to search (visual, audio, transcription)
        video_id: Optional video ID to limit search to a single video
        generate_screenshots: Whether to generate screenshots (default: True)
    """
    index_id: str = Field(
        ...,
        min_length=1,
        description="ID of the index to search"
    )
    query: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Natural language search query"
    )
    image: Optional[str] = Field(
        default=None,
        description="Base64-encoded image data"
    )
    image_format: Optional[str] = Field(
        default=None,
        pattern="^(jpeg|jpg|png|webp)$",
        description="Image format (jpeg, jpg, png, webp)"
    )
    top_k: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Number of results to return (1-100)"
    )
    modalities: Optional[list[str]] = Field(
        default=None,
        description="List of modalities to search: visual, audio, transcription. Defaults to all."
    )
    transcription_mode: Optional[str] = Field(
        default="both",
        pattern="^(semantic|lexical|both)$",
        description="Transcription search mode: semantic (embedding-based), lexical (exact text match), or both. Defaults to both."
    )
    video_id: Optional[str] = Field(
        default=None,
        description="Optional video ID to limit search to a single video"
    )
    generate_screenshots: bool = Field(
        default=True,
        description="Whether to generate screenshots for clips"
    )


class VideoClipResponse(BaseModel):
    """Response model for video clip information.
    
    Attributes:
        video_id: ID of the video
        start_timecode: Start time in seconds
        end_timecode: End time in seconds
        relevance_score: Relevance score (0.0-1.0)
        screenshot_url: URL to screenshot
        video_stream_url: Presigned URL for streaming
        metadata: Optional metadata including transcription
    """
    video_id: str
    start_timecode: float
    end_timecode: float
    relevance_score: float
    screenshot_url: str
    video_stream_url: str
    metadata: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Response model for search results.
    
    Attributes:
        query: The search query
        clips: List of matching video clips
        total_results: Total number of results
        search_time: Time taken to search in seconds
    """
    query: str
    clips: list[VideoClipResponse]
    total_results: int
    search_time: float


class ErrorResponse(BaseModel):
    """Error response model.
    
    Attributes:
        detail: Error message
    """
    detail: str


# Create router
router = APIRouter()


# Dependency injection placeholder (will be set by main.py)
_search_service: SearchService = None


def set_search_service(search_service: SearchService):
    """Set the search service instance for dependency injection.
    
    Args:
        search_service: Initialized SearchService instance
    """
    global _search_service
    _search_service = search_service


def get_search_service() -> SearchService:
    """Get the search service instance.
    
    Returns:
        SearchService instance
        
    Raises:
        RuntimeError: If search service is not initialized
    """
    if _search_service is None:
        raise RuntimeError("Search service not initialized")
    return _search_service


def _clip_to_response(clip: VideoClip) -> VideoClipResponse:
    """Convert VideoClip model to VideoClipResponse.
    
    Args:
        clip: VideoClip model instance
        
    Returns:
        VideoClipResponse instance
    """
    return VideoClipResponse(
        video_id=clip.video_id,
        start_timecode=clip.start_timecode,
        end_timecode=clip.end_timecode,
        relevance_score=clip.relevance_score,
        screenshot_url=clip.screenshot_url,
        video_stream_url=clip.video_stream_url,
        metadata=clip.metadata
    )


@router.post(
    "",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Search completed successfully",
            "model": SearchResponse
        },
        400: {
            "description": "Invalid request (empty query, invalid index_id, etc.)",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Index not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        },
        504: {
            "description": "Search timeout",
            "model": ErrorResponse
        }
    },
    summary="Search videos with natural language",
    description=(
        "Search for video content using natural language queries. "
        "Returns matching video clips with screenshots, timecodes, and relevance scores."
    )
)
async def search_videos(
    request: SearchRequest,
    authenticated: Annotated[bool, Depends(verify_token)],
    search_service: Annotated[SearchService, Depends(get_search_service)]
) -> SearchResponse:
    """Search for videos using text, image, or both.
    
    This endpoint performs semantic search across video embeddings in the
    specified index. It supports three search modes:
    - Text-only: Provide query field
    - Image-only: Provide image and image_format fields
    - Multimodal: Provide query, image, and image_format fields
    
    Returns matching video clips with:
    - Screenshots at the relevant timecode
    - Start and end timecodes for the clip
    - Relevance scores indicating match quality
    - Presigned URLs for video streaming
    
    The search uses the TwelveLabs Marengo model to embed the query and
    performs similarity search against video embeddings stored in S3 Vectors.
    
    Args:
        request: Search request with index_id, optional query, optional image, and options
        authenticated: Authentication verification (injected)
        search_service: SearchService instance (injected)
        
    Returns:
        SearchResponse: Search results with matching video clips
        
    Raises:
        HTTPException: 400 if neither query nor image provided, or validation fails
        HTTPException: 401 if not authenticated
        HTTPException: 404 if index not found
        HTTPException: 500 if search fails
        HTTPException: 504 if search times out
        
    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 5.3, 6.1, 6.4
    """
    try:
        # Validate that at least one input is provided
        if not request.query and not request.image:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one of query or image must be provided"
            )
        
        # Validate query is not empty if provided
        if request.query and not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query cannot be empty"
            )
        
        # Validate and decode image if provided
        image_bytes = None
        if request.image:
            # Validate image_format is provided
            if not request.image_format:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="image_format is required when image is provided"
                )
            
            # Validate and decode image
            try:
                image_bytes = ImageValidator.validate_image(
                    request.image,
                    request.image_format
                )
            except ValidationError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid image: {str(e)}"
                )
        
        # Validate modalities if provided
        valid_modalities = {'visual', 'audio', 'transcription'}
        modalities = request.modalities
        if modalities:
            invalid = set(modalities) - valid_modalities
            if invalid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid modalities: {invalid}. Valid options: visual, audio, transcription"
                )
            if not modalities:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least one modality must be selected"
                )
        
        # Validate transcription_mode
        transcription_mode = request.transcription_mode or "both"
        if transcription_mode not in ("semantic", "lexical", "both"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid transcription_mode. Valid options: semantic, lexical, both"
            )
        
        # Perform search
        results = await search_service.search_videos(
            index_id=request.index_id,
            query=request.query,
            image_bytes=image_bytes,
            top_k=request.top_k,
            modalities=modalities,
            transcription_mode=transcription_mode,
            video_id=request.video_id,
            generate_screenshots=request.generate_screenshots
        )
        
        # Convert to response model
        return SearchResponse(
            query=results.query,
            clips=[_clip_to_response(clip) for clip in results.clips],
            total_results=results.total_results,
            search_time=results.search_time
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise
    except ValueError as e:
        # Handle validation errors from search service
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
        # Handle index not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except BedrockError as e:
        # Handle Bedrock errors (query embedding failures)
        error_msg = str(e).lower()
        if "throttl" in error_msg or "rate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI service temporarily unavailable, please retry"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process search query: {str(e)}"
            )
    except AWSServiceError as e:
        # Handle AWS service errors
        error_msg = str(e).lower()
        if "timeout" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Search took too long, please try a more specific query"
            )
        elif "throttl" in error_msg or "rate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Service temporarily unavailable, please retry"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Search failed: {str(e)}"
            )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )
