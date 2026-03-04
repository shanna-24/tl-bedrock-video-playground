"""Analysis API endpoints for TL-Video-Playground.

This module implements endpoints for video content analysis using natural language queries.

Validates: Requirements 4.1, 4.2, 4.3, 4.4
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth import verify_token, get_auth_service
from services.analysis_service import AnalysisService
from services.index_manager import IndexManager
from services.websocket_manager import WebSocketManager
from models.analysis import AnalysisResult
from utils.progress_tracker import create_tracker, remove_tracker, cancel_tracker, check_cancellation
from exceptions import (
    ResourceNotFoundError,
    ValidationError,
    AWSServiceError,
    BedrockError,
    AnalysisCancelledError
)

logger = logging.getLogger(__name__)


# Request/Response models
class AnalyzeIndexRequest(BaseModel):
    """Request model for index analysis.
    
    Attributes:
        index_id: ID of the index to analyze
        query: Natural language analysis query
        verbosity: Response verbosity level ('concise' or 'extended')
        temperature: Temperature for randomness (0-1, default: 0.2)
        max_output_tokens: Maximum tokens to generate (optional)
        correlation_id: Optional correlation ID for progress tracking
    """
    index_id: str = Field(
        ...,
        min_length=1,
        description="ID of the index to analyze"
    )
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language analysis query"
    )
    verbosity: str = Field(
        default="balanced",
        pattern="^(concise|balanced|extended)$",
        description="Response verbosity level ('concise', 'balanced', or 'extended')"
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Temperature for randomness (0-1)"
    )
    max_output_tokens: int | None = Field(
        default=None,
        ge=1,
        le=4096,
        description="Maximum tokens to generate (1-4096)"
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for progress tracking"
    )


class AnalyzeVideoRequest(BaseModel):
    """Request model for video analysis.
    
    Attributes:
        video_id: ID of the video to analyze
        query: Natural language analysis query
        verbosity: Response verbosity level ('concise' or 'extended')
        use_jockey: Whether to use Jockey orchestration for enhanced analysis
        temperature: Temperature for randomness (0-1, default: 0.2)
        max_output_tokens: Maximum tokens to generate (optional)
        correlation_id: Optional correlation ID for progress tracking
    """
    video_id: str = Field(
        ...,
        min_length=1,
        description="ID of the video to analyze"
    )
    query: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Natural language analysis query"
    )
    verbosity: str = Field(
        default="balanced",
        pattern="^(concise|balanced|extended)$",
        description="Response verbosity level ('concise', 'balanced', or 'extended')"
    )
    use_jockey: bool = Field(
        default=False,
        description="Whether to use Jockey orchestration for enhanced analysis"
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Temperature for randomness (0-1)"
    )
    max_output_tokens: int | None = Field(
        default=None,
        ge=1,
        le=4096,
        description="Maximum tokens to generate (1-4096)"
    )
    correlation_id: str | None = Field(
        default=None,
        description="Optional correlation ID for progress tracking"
    )


class AnalysisResponse(BaseModel):
    """Response model for analysis results.
    
    Attributes:
        query: The analysis query
        scope: Analysis scope ("index" or "video")
        scope_id: ID of the index or video
        insights: Formatted analysis insights
        analyzed_at: ISO timestamp of when analysis was performed
        metadata: Additional metadata
    """
    query: str
    scope: str
    scope_id: str
    insights: str
    analyzed_at: str
    metadata: dict


class ErrorResponse(BaseModel):
    """Error response model.
    
    Attributes:
        detail: Error message
    """
    detail: str


class CancelAnalysisRequest(BaseModel):
    """Request model for cancelling an analysis.
    
    Attributes:
        correlation_id: Correlation ID of the analysis to cancel
    """
    correlation_id: str = Field(
        ...,
        min_length=1,
        description="Correlation ID of the analysis to cancel"
    )


class CancelAnalysisResponse(BaseModel):
    """Response model for cancel analysis.
    
    Attributes:
        cancelled: Whether the analysis was successfully cancelled
        correlation_id: The correlation ID that was cancelled
    """
    cancelled: bool
    correlation_id: str


# Create router
router = APIRouter()


# Dependency injection placeholders (will be set by main.py)
_analysis_service: AnalysisService = None
_index_manager: IndexManager = None
_websocket_manager: WebSocketManager = None


def set_analysis_service(analysis_service: AnalysisService):
    """Set the analysis service instance for dependency injection.
    
    Args:
        analysis_service: Initialized AnalysisService instance
    """
    global _analysis_service
    _analysis_service = analysis_service


def set_index_manager(index_manager: IndexManager):
    """Set the index manager instance for dependency injection.
    
    Args:
        index_manager: Initialized IndexManager instance
    """
    global _index_manager
    _index_manager = index_manager


def set_websocket_manager(websocket_manager: WebSocketManager):
    """Set the WebSocket manager instance for dependency injection.
    
    Args:
        websocket_manager: Initialized WebSocketManager instance
    """
    global _websocket_manager
    _websocket_manager = websocket_manager


def get_analysis_service() -> AnalysisService:
    """Get the analysis service instance.
    
    Returns:
        AnalysisService instance
        
    Raises:
        RuntimeError: If analysis service is not initialized
    """
    if _analysis_service is None:
        raise RuntimeError("Analysis service not initialized")
    return _analysis_service


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


def get_websocket_manager() -> WebSocketManager:
    """Get the WebSocket manager instance.
    
    Returns:
        WebSocketManager instance
        
    Raises:
        RuntimeError: If WebSocket manager is not initialized
    """
    if _websocket_manager is None:
        raise RuntimeError("WebSocket manager not initialized")
    return _websocket_manager


def _result_to_response(result: AnalysisResult) -> AnalysisResponse:
    """Convert AnalysisResult model to AnalysisResponse.
    
    Args:
        result: AnalysisResult model instance
        
    Returns:
        AnalysisResponse instance
    """
    return AnalysisResponse(
        query=result.query,
        scope=result.scope,
        scope_id=result.scope_id,
        insights=result.insights,
        analyzed_at=result.analyzed_at.isoformat(),
        metadata=result.metadata
    )


@router.post(
    "/index",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Analysis completed successfully",
            "model": AnalysisResponse
        },
        400: {
            "description": "Invalid request (empty query, invalid index_id, no videos in index)",
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
        429: {
            "description": "AI service temporarily unavailable",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        },
        504: {
            "description": "Analysis timeout",
            "model": ErrorResponse
        }
    },
    summary="Analyze entire index",
    description=(
        "Analyze all videos in an index using a natural language query. "
        "Returns structured insights based on the query and video content."
    )
)
async def analyze_index(
    request: AnalyzeIndexRequest,
    authenticated: Annotated[bool, Depends(verify_token)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
    index_manager: Annotated[IndexManager, Depends(get_index_manager)]
) -> AnalysisResponse:
    """Analyze all videos in an index using natural language query.
    
    This endpoint analyzes all videos in the specified index using the
    TwelveLabs Pegasus model. It returns structured insights based on
    the provided query.
    
    The analysis considers all videos in the index and provides insights
    that span the entire collection.
    
    Args:
        request: Analysis request with index_id, query, and options
        authenticated: Authentication verification (injected)
        analysis_service: AnalysisService instance (injected)
        index_manager: IndexManager instance (injected)
        
    Returns:
        AnalysisResponse: Analysis results with insights
        
    Raises:
        HTTPException: 400 if query is empty or no videos in index
        HTTPException: 401 if not authenticated
        HTTPException: 404 if index not found
        HTTPException: 429 if AI service is throttled
        HTTPException: 500 if analysis fails
        HTTPException: 504 if analysis times out
        
    Validates: Requirements 4.1, 4.3, 4.4
    """
    logger.info(f"=" * 80)
    logger.info(f"ENDPOINT CALLED: /api/analyze/index")
    logger.info(f"  index_id: {request.index_id}")
    logger.info(f"  query: {request.query[:100]}")
    logger.info(f"  verbosity: {request.verbosity}")
    logger.info(f"=" * 80)
    
    try:
        # Validate query is not empty
        if not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis query cannot be empty"
            )
        
        # Get the index to verify it exists
        index = await index_manager.get_index(request.index_id)
        
        # Get all videos in the index
        videos = await index_manager.list_videos_in_index(request.index_id)
        
        # Check if index has videos
        if not videos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No videos found in index for analysis"
            )
        
        # Extract S3 URIs from videos
        video_s3_uris = [video.s3_uri for video in videos]
        
        # Create progress tracker if correlation_id provided
        progress_callback = None
        correlation_id = request.correlation_id
        if correlation_id:
            websocket_manager = get_websocket_manager()
            tracker = create_tracker(correlation_id, websocket_manager)
            progress_callback = tracker.update
        
        # Perform analysis
        try:
            result = await analysis_service.analyze_index(
                index_id=request.index_id,
                query=request.query,
                video_s3_uris=video_s3_uris,
                verbosity=request.verbosity,
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                progress_callback=progress_callback,
                correlation_id=correlation_id
            )
        finally:
            # Mark progress as complete and cleanup
            if correlation_id:
                await tracker.complete()
                remove_tracker(correlation_id)
        
        # Convert to response model
        return _result_to_response(result)
        
    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise
    except AnalysisCancelledError:
        # Analysis was cancelled by user - return 499 (Client Closed Request)
        # This is a non-standard but commonly used status code for client cancellation
        logger.info(f"Analysis cancelled for index {request.index_id}")
        raise HTTPException(
            status_code=499,
            detail="Analysis cancelled by user"
        )
    except ValueError as e:
        # Handle validation errors from analysis service
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
        # Handle Bedrock errors (Pegasus model failures)
        error_msg = str(e).lower()
        if "throttl" in error_msg or "rate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI service temporarily unavailable, please retry"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to analyze index: {str(e)}"
            )
    except AWSServiceError as e:
        # Handle AWS service errors
        error_msg = str(e).lower()
        if "timeout" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Analysis took too long, please try again"
            )
        elif "throttl" in error_msg or "rate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Service temporarily unavailable, please retry"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis failed: {str(e)}"
            )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post(
    "/video",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Analysis completed successfully",
            "model": AnalysisResponse
        },
        400: {
            "description": "Invalid request (empty query, invalid video_id)",
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
        429: {
            "description": "AI service temporarily unavailable",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        },
        504: {
            "description": "Analysis timeout",
            "model": ErrorResponse
        }
    },
    summary="Analyze single video",
    description=(
        "Analyze a single video using a natural language query. "
        "Returns structured insights based on the query and video content."
    )
)
async def analyze_video(
    request: AnalyzeVideoRequest,
    authenticated: Annotated[bool, Depends(verify_token)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
    index_manager: Annotated[IndexManager, Depends(get_index_manager)]
) -> AnalysisResponse:
    """Analyze a single video using natural language query.
    
    This endpoint analyzes a specific video using the TwelveLabs Pegasus model.
    It returns structured insights based on the provided query and the video content.
    
    Args:
        request: Analysis request with video_id, query, and options
        authenticated: Authentication verification (injected)
        analysis_service: AnalysisService instance (injected)
        index_manager: IndexManager instance (injected)
        
    Returns:
        AnalysisResponse: Analysis results with insights
        
    Raises:
        HTTPException: 400 if query is empty or video_id is invalid
        HTTPException: 401 if not authenticated
        HTTPException: 404 if video not found
        HTTPException: 429 if AI service is throttled
        HTTPException: 500 if analysis fails
        HTTPException: 504 if analysis times out
        
    Validates: Requirements 4.2, 4.3, 4.4
    """
    try:
        # Validate query is not empty
        if not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis query cannot be empty"
            )
        
        # Find the video across all indexes
        # We need to search through all indexes to find the video
        indexes = await index_manager.list_indexes()
        
        video = None
        for index in indexes:
            videos = await index_manager.list_videos_in_index(index.id)
            for v in videos:
                if v.id == request.video_id:
                    video = v
                    break
            if video:
                break
        
        # Check if video was found
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {request.video_id} not found"
            )
        
        # Create progress tracker if correlation_id provided
        progress_callback = None
        correlation_id = request.correlation_id
        if correlation_id:
            websocket_manager = get_websocket_manager()
            tracker = create_tracker(correlation_id, websocket_manager)
            progress_callback = tracker.update
        
        # Perform analysis
        try:
            result = await analysis_service.analyze_video(
                video_id=request.video_id,
                query=request.query,
                video_s3_uri=video.s3_uri,
                verbosity=request.verbosity,
                use_jockey=request.use_jockey,
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                progress_callback=progress_callback,
                correlation_id=correlation_id
            )
        finally:
            # Mark progress as complete and cleanup
            if correlation_id:
                await tracker.complete()
                remove_tracker(correlation_id)
        
        # Convert to response model
        return _result_to_response(result)
        
    except HTTPException:
        # Re-raise HTTP exceptions without wrapping
        raise
    except AnalysisCancelledError:
        # Analysis was cancelled by user - return 499 (Client Closed Request)
        logger.info(f"Analysis cancelled for video {request.video_id}")
        raise HTTPException(
            status_code=499,
            detail="Analysis cancelled by user"
        )
    except ValueError as e:
        # Handle validation errors from analysis service
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
        # Handle resource not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except BedrockError as e:
        # Handle Bedrock errors (Pegasus model failures)
        error_msg = str(e).lower()
        if "throttl" in error_msg or "rate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI service temporarily unavailable, please retry"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to analyze video: {str(e)}"
            )
    except AWSServiceError as e:
        # Handle AWS service errors
        error_msg = str(e).lower()
        if "timeout" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Analysis took too long, please try again"
            )
        elif "throttl" in error_msg or "rate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Service temporarily unavailable, please retry"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Analysis failed: {str(e)}"
            )
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )





@router.post(
    "/cancel",
    response_model=CancelAnalysisResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Cancellation request processed",
            "model": CancelAnalysisResponse
        },
        400: {
            "description": "Invalid request",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        }
    },
    summary="Cancel ongoing analysis",
    description=(
        "Cancel an ongoing analysis operation by its correlation ID. "
        "This signals the analysis to stop at the next safe checkpoint."
    )
)
async def cancel_analysis(
    request: CancelAnalysisRequest,
    authenticated: Annotated[bool, Depends(verify_token)]
) -> CancelAnalysisResponse:
    """Cancel an ongoing analysis operation.
    
    This endpoint cancels an analysis operation identified by its correlation ID.
    The cancellation is cooperative - the analysis will stop at the next safe
    checkpoint rather than being forcefully terminated.
    
    Args:
        request: Cancel request with correlation_id
        authenticated: Authentication verification (injected)
        
    Returns:
        CancelAnalysisResponse: Whether the cancellation was successful
    """
    logger.info(f"Cancellation requested for correlation_id: {request.correlation_id}")
    
    cancelled = cancel_tracker(request.correlation_id)
    
    return CancelAnalysisResponse(
        cancelled=cancelled,
        correlation_id=request.correlation_id
    )
