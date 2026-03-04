"""Compliance API endpoints.

This module provides REST API endpoints for video compliance checking.
"""

import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.auth import verify_token
from services.compliance_service import ComplianceService
from services.index_manager import IndexManager
from services.websocket_manager import WebSocketManager
from utils.progress_tracker import create_tracker, remove_tracker
from exceptions import AWSServiceError, BedrockError

logger = logging.getLogger(__name__)

router = APIRouter()

# Service instances (set during startup)
_compliance_service: Optional[ComplianceService] = None
_index_manager: Optional[IndexManager] = None
_websocket_manager: Optional[WebSocketManager] = None


def set_compliance_service(service: ComplianceService) -> None:
    """Set the compliance service instance."""
    global _compliance_service
    _compliance_service = service


def set_index_manager(manager: IndexManager) -> None:
    """Set the index manager instance."""
    global _index_manager
    _index_manager = manager


def set_websocket_manager(manager: WebSocketManager) -> None:
    """Set the WebSocket manager instance."""
    global _websocket_manager
    _websocket_manager = manager


def get_compliance_service() -> ComplianceService:
    """Get the compliance service instance."""
    if _compliance_service is None:
        raise RuntimeError("Compliance service not initialized")
    return _compliance_service


def get_index_manager() -> IndexManager:
    """Get the index manager instance."""
    if _index_manager is None:
        raise RuntimeError("Index manager not initialized")
    return _index_manager


def get_websocket_manager() -> WebSocketManager:
    """Get the WebSocket manager instance."""
    if _websocket_manager is None:
        raise RuntimeError("WebSocket manager not initialized")
    return _websocket_manager


class CheckComplianceRequest(BaseModel):
    """Request model for compliance check."""
    video_id: str = Field(
        ...,
        min_length=1,
        description="ID of the video to check"
    )
    correlation_id: Optional[str] = Field(
        default=None,
        description="Optional correlation ID for progress tracking"
    )


class ComplianceIssue(BaseModel):
    """Model for a single compliance issue."""
    Timecode: Optional[str] = None
    Category: Optional[str] = None
    Subcategory: Optional[str] = None
    Severity: Optional[str] = None
    Description: Optional[str] = None


class ComplianceResult(BaseModel):
    """Model for compliance check result."""
    Filename: Optional[str] = None
    Title: Optional[str] = None
    Length: Optional[str] = None
    Summary: Optional[str] = None
    Overall_Status: Optional[str] = Field(None, alias="Overall Status")
    Identified_Issues: Optional[list[dict[str, Any]]] = Field(None, alias="Identified Issues")
    raw_response: Optional[str] = None
    
    class Config:
        populate_by_name = True


class ComplianceMetadata(BaseModel):
    """Metadata about the compliance check."""
    video_id: str
    video_filename: str
    checked_at: str
    compliance_params: dict[str, str]


class CheckComplianceResponse(BaseModel):
    """Response model for compliance check."""
    result: dict[str, Any]
    s3_key: str
    s3_uri: str


class ComplianceParamsResponse(BaseModel):
    """Response model for compliance parameters."""
    company: str
    category: str
    product_line: str
    categories: list[str]


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str


@router.post(
    "/check",
    response_model=CheckComplianceResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Compliance check completed", "model": CheckComplianceResponse},
        400: {"description": "Invalid request", "model": ErrorResponse},
        401: {"description": "Authentication required", "model": ErrorResponse},
        404: {"description": "Video not found", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Check video compliance",
    description="Perform compliance checking on a video using configured rules."
)
async def check_compliance(
    request: CheckComplianceRequest,
    authenticated: Annotated[bool, Depends(verify_token)],
    compliance_service: Annotated[ComplianceService, Depends(get_compliance_service)],
    index_manager: Annotated[IndexManager, Depends(get_index_manager)]
) -> CheckComplianceResponse:
    """Check video compliance against configured rules.
    
    Args:
        request: Compliance check request with video_id
        authenticated: Authentication verification (injected)
        compliance_service: ComplianceService instance (injected)
        index_manager: IndexManager instance (injected)
        
    Returns:
        CheckComplianceResponse: Compliance results with S3 location
    """
    try:
        # Find the video across all indexes
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
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video {request.video_id} not found"
            )
        
        # Create progress tracker if correlation_id provided
        progress_callback = None
        correlation_id = request.correlation_id
        tracker = None
        if correlation_id:
            websocket_manager = get_websocket_manager()
            tracker = create_tracker(correlation_id, websocket_manager)
            progress_callback = tracker.update
        
        try:
            # Perform compliance check
            result = await compliance_service.check_compliance(
                video_id=request.video_id,
                video_s3_uri=video.s3_uri,
                video_filename=video.filename,
                index_id=video.index_id,
                progress_callback=progress_callback,
                correlation_id=correlation_id
            )
        finally:
            # Mark progress as complete and cleanup
            if tracker:
                await tracker.complete()
                remove_tracker(correlation_id)
        
        return CheckComplianceResponse(
            result=result["result"],
            s3_key=result["s3_key"],
            s3_uri=result["s3_uri"]
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except BedrockError as e:
        error_msg = str(e).lower()
        if "throttl" in error_msg or "rate" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="AI service temporarily unavailable, please retry"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check compliance: {str(e)}"
        )
    except AWSServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance check failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during compliance check: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance check failed: {str(e)}"
        )


@router.get(
    "/params",
    response_model=ComplianceParamsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Compliance parameters", "model": ComplianceParamsResponse},
        401: {"description": "Authentication required", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    summary="Get compliance parameters",
    description="Get the current compliance checking parameters (company, category, product line, categories)."
)
async def get_compliance_params(
    authenticated: Annotated[bool, Depends(verify_token)],
    compliance_service: Annotated[ComplianceService, Depends(get_compliance_service)]
) -> ComplianceParamsResponse:
    """Get current compliance parameters.
    
    Args:
        authenticated: Authentication verification (injected)
        compliance_service: ComplianceService instance (injected)
        
    Returns:
        ComplianceParamsResponse: Current compliance parameters with categories
    """
    try:
        params = compliance_service.get_compliance_params()
        return ComplianceParamsResponse(
            company=params.get("company", ""),
            category=params.get("category", ""),
            product_line=params.get("product_line", ""),
            categories=params.get("categories", [])
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get compliance params: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get compliance parameters: {str(e)}"
        )
