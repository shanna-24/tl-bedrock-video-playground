"""Embedding Jobs API endpoints for TL-Video-Playground.

This module implements API endpoints for querying embedding job status
and managing embedding jobs.

Validates: Requirements 13.1
"""

from typing import Annotated, List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from services.embedding_job_store import EmbeddingJobStore, Job


# Response models
class JobResponse(BaseModel):
    """Embedding job response model.
    
    Attributes:
        job_id: Unique identifier for the job
        invocation_arn: ARN of the Bedrock async invocation
        video_id: ID of the video being processed
        index_id: ID of the index to store embeddings in
        s3_uri: S3 URI of the video file
        status: Current job status (pending, processing, completed, failed)
        created_at: Timestamp when the job was created (ISO format)
        updated_at: Timestamp when the job was last updated (ISO format)
        retry_count: Number of retry attempts
        error_message: Error message if job failed
        output_location: S3 location of the embedding output
        next_retry_at: Timestamp when the job should be retried (ISO format)
        video_duration: Duration of the video in seconds
        progress: Progress estimation information
    """
    job_id: str = Field(..., description="Unique identifier for the job")
    invocation_arn: str = Field(..., description="ARN of the Bedrock async invocation")
    video_id: str = Field(..., description="ID of the video being processed")
    index_id: str = Field(..., description="ID of the index to store embeddings in")
    s3_uri: str = Field(..., description="S3 URI of the video file")
    status: str = Field(..., description="Current job status")
    created_at: str = Field(..., description="Timestamp when the job was created")
    updated_at: str = Field(..., description="Timestamp when the job was last updated")
    retry_count: int = Field(..., description="Number of retry attempts")
    error_message: Optional[str] = Field(None, description="Error message if job failed")
    output_location: Optional[str] = Field(None, description="S3 location of the embedding output")
    next_retry_at: Optional[str] = Field(None, description="Timestamp when the job should be retried")
    video_duration: Optional[float] = Field(None, description="Duration of the video in seconds")
    progress: Dict[str, Any] = Field(..., description="Progress estimation information")


class JobListResponse(BaseModel):
    """List of embedding jobs response model.
    
    Attributes:
        jobs: List of embedding jobs
        total: Total number of jobs matching the query
    """
    jobs: List[JobResponse] = Field(..., description="List of embedding jobs")
    total: int = Field(..., description="Total number of jobs")


# Create router
router = APIRouter()


# Dependency injection placeholder (will be set by main.py)
_embedding_job_store: EmbeddingJobStore = None
_bedrock_client = None


def set_embedding_job_store(job_store: EmbeddingJobStore):
    """Set the embedding job store for dependency injection.
    
    This function should be called by main.py during startup to inject
    the initialized instance.
    
    Args:
        job_store: Initialized EmbeddingJobStore instance
    """
    global _embedding_job_store
    _embedding_job_store = job_store


def set_bedrock_client(bedrock_client):
    """Set the Bedrock client for dependency injection.
    
    This function should be called by main.py during startup to inject
    the initialized instance.
    
    Args:
        bedrock_client: Initialized BedrockClient instance
    """
    global _bedrock_client
    _bedrock_client = bedrock_client


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


def get_bedrock_client():
    """Get the Bedrock client instance.
    
    Returns:
        BedrockClient instance
        
    Raises:
        RuntimeError: If Bedrock client is not initialized
    """
    if _bedrock_client is None:
        raise RuntimeError("Bedrock client not initialized")
    return _bedrock_client


def _job_to_response(job: Job) -> JobResponse:
    """Convert a Job model to a JobResponse.
    
    Args:
        job: Job model instance
        
    Returns:
        JobResponse: API response model with progress estimation
    """
    return JobResponse(
        job_id=job.job_id,
        invocation_arn=job.invocation_arn,
        video_id=job.video_id,
        index_id=job.index_id,
        s3_uri=job.s3_uri,
        status=job.status,
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        retry_count=job.retry_count,
        error_message=job.error_message,
        output_location=job.output_location,
        next_retry_at=job.next_retry_at.isoformat() if job.next_retry_at else None,
        video_duration=job.video_duration,
        progress=job.estimate_progress()
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Job found",
            "model": JobResponse
        },
        404: {
            "description": "Job not found"
        }
    },
    summary="Get embedding job by ID",
    description="Retrieve detailed information about a specific embedding job"
)
async def get_job(
    job_id: str,
    job_store: Annotated[EmbeddingJobStore, Depends(get_embedding_job_store)]
) -> JobResponse:
    """Get a specific embedding job by ID.
    
    This endpoint retrieves detailed information about a specific embedding job,
    including its current status, retry count, error messages, and timestamps.
    
    Args:
        job_id: Unique identifier of the job
        job_store: EmbeddingJobStore instance (injected)
        
    Returns:
        JobResponse: Detailed job information
        
    Raises:
        HTTPException: 404 if job is not found
        
    Validates: Requirements 13.1
    """
    job = job_store.get_job(job_id)
    
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    return _job_to_response(job)


@router.get(
    "",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of jobs",
            "model": JobListResponse
        }
    },
    summary="List embedding jobs",
    description="Retrieve a list of embedding jobs, optionally filtered by status"
)
async def list_jobs(
    job_store: Annotated[EmbeddingJobStore, Depends(get_embedding_job_store)],
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter jobs by status (pending, processing, completed, failed)"
    )
) -> JobListResponse:
    """List embedding jobs with optional status filter.
    
    This endpoint retrieves a list of all embedding jobs, optionally filtered
    by status. This is useful for monitoring job progress and identifying
    failed or stuck jobs.
    
    Args:
        job_store: EmbeddingJobStore instance (injected)
        status_filter: Optional status filter (pending, processing, completed, failed)
        
    Returns:
        JobListResponse: List of jobs and total count
        
    Validates: Requirements 13.1
    """
    # Get all jobs
    all_jobs = job_store.get_all_jobs()
    
    # Filter by status if provided
    if status_filter:
        filtered_jobs = [job for job in all_jobs if job.status == status_filter]
    else:
        filtered_jobs = all_jobs
    
    # Convert to response models
    job_responses = [_job_to_response(job) for job in filtered_jobs]
    
    return JobListResponse(
        jobs=job_responses,
        total=len(job_responses)
    )


@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Job retry initiated",
            "model": JobResponse
        },
        404: {
            "description": "Job not found"
        },
        400: {
            "description": "Job cannot be retried (invalid status)"
        }
    },
    summary="Retry a failed embedding job",
    description="Reset a failed job's status to pending and clear retry count to allow reprocessing"
)
async def retry_job(
    job_id: str,
    job_store: Annotated[EmbeddingJobStore, Depends(get_embedding_job_store)]
) -> JobResponse:
    """Manually retry a failed embedding job.
    
    This endpoint allows manual retry of failed embedding jobs by resetting
    their status to 'pending' and clearing the retry count. This is useful
    for recovering from transient failures or after fixing underlying issues.
    
    Only jobs with status 'failed' can be retried. Jobs that are pending,
    processing, or completed cannot be retried.
    
    Args:
        job_id: Unique identifier of the job to retry
        job_store: EmbeddingJobStore instance (injected)
        
    Returns:
        JobResponse: Updated job information with reset status
        
    Raises:
        HTTPException: 404 if job is not found
        HTTPException: 400 if job status is not 'failed'
        
    Validates: Requirements 13.2
    """
    # Get the job
    job = job_store.get_job(job_id)
    
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Only allow retry for failed jobs
    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} cannot be retried. Current status: {job.status}. Only failed jobs can be retried."
        )
    
    # Reset job status to pending and clear retry count
    job_store.update_job_status(
        job_id=job_id,
        status="pending",
        retry_count=0,
        error_message=None,
        next_retry_at=None
    )
    
    # Get updated job
    updated_job = job_store.get_job(job_id)
    
    return _job_to_response(updated_job)


@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Job cancellation initiated",
            "model": JobResponse
        },
        404: {
            "description": "Job not found"
        },
        400: {
            "description": "Job cannot be cancelled (invalid status)"
        }
    },
    summary="Cancel a running embedding job",
    description="Stop a Bedrock job if still running and mark it as cancelled"
)
async def cancel_job(
    job_id: str,
    job_store: Annotated[EmbeddingJobStore, Depends(get_embedding_job_store)],
    bedrock_client: Annotated[object, Depends(get_bedrock_client)]
) -> JobResponse:
    """Cancel a running embedding job.
    
    This endpoint stops a running Bedrock model invocation job and marks it
    as cancelled. Only jobs with status 'pending' or 'processing' can be
    cancelled. Completed, failed, or already cancelled jobs cannot be cancelled.
    
    If the Bedrock job is still running (InProgress), it will be stopped via
    the Bedrock API. If the job has already completed or failed, the cancellation
    will fail with a 400 error.
    
    Args:
        job_id: Unique identifier of the job to cancel
        job_store: EmbeddingJobStore instance (injected)
        bedrock_client: BedrockClient instance (injected)
        
    Returns:
        JobResponse: Updated job information with cancelled status
        
    Raises:
        HTTPException: 404 if job is not found
        HTTPException: 400 if job cannot be cancelled (invalid status)
        HTTPException: 500 if Bedrock API call fails
        
    Validates: Requirements 13.3
    """
    from aws.bedrock_client import BedrockError
    
    # Get the job
    job = job_store.get_job(job_id)
    
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Only allow cancellation for pending or processing jobs
    if job.status not in ["pending", "processing"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} cannot be cancelled. Current status: {job.status}. Only pending or processing jobs can be cancelled."
        )
    
    # Try to stop the Bedrock job if it's still running
    try:
        # Check current status with Bedrock
        status_info = bedrock_client.get_async_invocation_status(job.invocation_arn)
        bedrock_status = status_info.get("status", "Unknown")
        
        if bedrock_status == "InProgress":
            # Stop the Bedrock job
            bedrock_client.stop_model_invocation_job(job.invocation_arn)
        elif bedrock_status in ["Completed", "Failed"]:
            # Job already finished, cannot cancel
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_id} has already {bedrock_status.lower()}. Cannot cancel."
            )
        
    except BedrockError as e:
        # If we get a conflict error, the job may already be completed
        if "cannot be stopped" in str(e).lower() or "conflict" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job {job_id} cannot be cancelled: {str(e)}"
            )
        else:
            # Other Bedrock errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to cancel job: {str(e)}"
            )
    
    # Mark job as cancelled in our store
    job_store.update_job_status(
        job_id=job_id,
        status="cancelled",
        error_message="Job cancelled by user"
    )
    
    # Get updated job
    updated_job = job_store.get_job(job_id)
    
    return _job_to_response(updated_job)
