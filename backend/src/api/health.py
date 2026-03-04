"""Health check API endpoints for TL-Video-Playground.

This module implements health check endpoints for monitoring the application
and embedding job processor status.

Validates: Requirements 8.4
"""

from typing import Annotated, Dict, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from services.embedding_job_processor import EmbeddingJobProcessor
from services.embedding_job_store import EmbeddingJobStore
from services.websocket_manager import WebSocketManager


# Response models
class HealthResponse(BaseModel):
    """Basic health check response model.
    
    Attributes:
        status: Overall health status (healthy, degraded, unhealthy)
        environment: Application environment (development, production, etc.)
        version: Application version
    """
    status: str = Field(..., description="Overall health status")
    environment: str = Field(..., description="Application environment")
    version: str = Field(..., description="Application version")


class ProcessorHealthResponse(BaseModel):
    """Processor health check response model.
    
    Attributes:
        status: Overall processor health status (healthy, degraded, unhealthy)
        processor_running: Whether the processor is running
        pending_jobs: Number of pending jobs
        processing_jobs: Number of jobs currently processing
        total_pending: Total number of pending/processing jobs
        jobs_processed: Total jobs processed since start
        jobs_completed: Total jobs completed successfully
        jobs_failed: Total jobs permanently failed
        jobs_retried: Total retry attempts
        embeddings_stored: Total embeddings stored
        last_poll_time: Timestamp of last poll (ISO format)
        last_job_completion_time: Timestamp of last successful job (ISO format)
        metrics: Detailed performance metrics
    """
    status: str = Field(..., description="Overall processor health status")
    processor_running: bool = Field(..., description="Whether the processor is running")
    pending_jobs: int = Field(..., description="Number of pending jobs")
    processing_jobs: int = Field(..., description="Number of jobs currently processing")
    total_pending: int = Field(..., description="Total number of pending/processing jobs")
    jobs_processed: int = Field(..., description="Total jobs processed since start")
    jobs_completed: int = Field(..., description="Total jobs completed successfully")
    jobs_failed: int = Field(..., description="Total jobs permanently failed")
    jobs_retried: int = Field(..., description="Total retry attempts")
    embeddings_stored: int = Field(..., description="Total embeddings stored")
    last_poll_time: str | None = Field(None, description="Timestamp of last poll (ISO format)")
    last_job_completion_time: str | None = Field(None, description="Timestamp of last successful job (ISO format)")
    metrics: Dict[str, Any] = Field(..., description="Detailed performance metrics")
    websocket_stats: Dict[str, Any] | None = Field(None, description="WebSocket connection statistics")


# Create router
router = APIRouter()


# Dependency injection placeholders (will be set by main.py)
_embedding_job_processor: EmbeddingJobProcessor = None
_embedding_job_store: EmbeddingJobStore = None
_websocket_manager: WebSocketManager = None
_config = None


def set_dependencies(processor: EmbeddingJobProcessor, job_store: EmbeddingJobStore, config, websocket_manager: WebSocketManager = None):
    """Set the dependencies for dependency injection.
    
    This function should be called by main.py during startup to inject
    the initialized instances.
    
    Args:
        processor: Initialized EmbeddingJobProcessor instance
        job_store: Initialized EmbeddingJobStore instance
        config: Application configuration
        websocket_manager: Initialized WebSocketManager instance (optional)
    """
    global _embedding_job_processor, _embedding_job_store, _config, _websocket_manager
    _embedding_job_processor = processor
    _embedding_job_store = job_store
    _config = config
    _websocket_manager = websocket_manager


def get_embedding_job_processor() -> EmbeddingJobProcessor:
    """Get the embedding job processor instance.
    
    Returns:
        EmbeddingJobProcessor instance
        
    Raises:
        RuntimeError: If embedding job processor is not initialized
    """
    if _embedding_job_processor is None:
        raise RuntimeError("Embedding job processor not initialized")
    return _embedding_job_processor


def get_embedding_job_store() -> EmbeddingJobStore:
    """Get the embedding job store instance.
    
    Returns:
        EmbeddingJobStore instance
        
    Raises:
        RuntimeError: If embedding job store is not initialized
    """
    if _embedding_job_store is None:
        raise RuntimeError("Embedding job store not initialized")
    return _embedding_job_store


def get_config():
    """Get the application configuration.
    
    Returns:
        Config instance
        
    Raises:
        RuntimeError: If configuration is not initialized
    """
    if _config is None:
        raise RuntimeError("Configuration not initialized")
    return _config


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Application is healthy",
            "model": HealthResponse
        }
    },
    summary="Basic health check",
    description="Check if the application is running and responsive"
)
async def health_check() -> HealthResponse:
    """Basic health check endpoint.
    
    This endpoint provides a simple health check for the application.
    It returns the overall status, environment, and version.
    
    Returns:
        HealthResponse: Basic health status information
        
    Validates: Requirements 8.4
    """
    config = get_config()
    return HealthResponse(
        status="healthy",
        environment=config.environment if config else "unknown",
        version="1.0.0"
    )


@router.get(
    "/health/processor",
    response_model=ProcessorHealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Processor is healthy",
            "model": ProcessorHealthResponse
        },
        503: {
            "description": "Processor is unhealthy",
            "model": ProcessorHealthResponse
        }
    },
    summary="Processor health check",
    description="Check the health and status of the embedding job processor"
)
async def processor_health_check(
    processor: Annotated[EmbeddingJobProcessor, Depends(get_embedding_job_processor)],
    job_store: Annotated[EmbeddingJobStore, Depends(get_embedding_job_store)]
) -> ProcessorHealthResponse:
    """Processor health check endpoint.
    
    This endpoint provides detailed health information about the embedding job processor,
    including:
    - Whether the processor is running
    - Number of pending, processing, completed, and failed jobs
    - Performance metrics (processing times, success rates, etc.)
    - Timestamps of last activity
    
    The health status is determined based on:
    - healthy: Processor is running and no issues detected
    - degraded: Processor is running but has high failure rate or many pending jobs
    - unhealthy: Processor is not running or has critical issues
    
    Args:
        processor: EmbeddingJobProcessor instance (injected)
        job_store: EmbeddingJobStore instance (injected)
        
    Returns:
        ProcessorHealthResponse: Detailed processor health status
        
    Validates: Requirements 8.4
    """
    # Get processor stats
    stats = processor.get_stats()
    
    # Get detailed metrics
    metrics = processor.get_metrics()
    
    # Get WebSocket stats if available
    websocket_stats = None
    if _websocket_manager:
        websocket_stats = _websocket_manager.get_stats()
    
    # Determine health status
    health_status = _determine_processor_health(stats, metrics)
    
    # Build response
    response = ProcessorHealthResponse(
        status=health_status,
        processor_running=stats["running"],
        pending_jobs=stats["pending_jobs"],
        processing_jobs=stats["processing_jobs"],
        total_pending=stats["total_pending"],
        jobs_processed=stats["jobs_processed"],
        jobs_completed=stats["jobs_completed"],
        jobs_failed=stats["jobs_failed"],
        jobs_retried=stats["jobs_retried"],
        embeddings_stored=stats["embeddings_stored"],
        last_poll_time=stats["last_poll_time"],
        last_job_completion_time=stats["last_job_completion_time"],
        metrics=metrics,
        websocket_stats=websocket_stats
    )
    
    return response


def _determine_processor_health(stats: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    """Determine the health status of the processor.
    
    Health status is determined based on:
    - unhealthy: Processor is not running
    - degraded: High failure rate (>20%) or many pending jobs (>50)
    - healthy: Processor is running normally
    
    Args:
        stats: Processor statistics
        metrics: Processor metrics
        
    Returns:
        str: Health status (healthy, degraded, unhealthy)
    """
    # If processor is not running, it's unhealthy
    if not stats["running"]:
        return "unhealthy"
    
    # Check for high failure rate
    success_rate = metrics["gauges"]["success_rate_percent"]
    if success_rate < 80.0 and stats["jobs_processed"] >= 5:
        return "degraded"
    
    # Check for too many pending jobs
    if stats["total_pending"] > 50:
        return "degraded"
    
    # Check for high retry rate
    retry_rate = metrics["gauges"]["retry_rate_percent"]
    if retry_rate > 30.0 and stats["jobs_processed"] >= 5:
        return "degraded"
    
    # Otherwise, processor is healthy
    return "healthy"
