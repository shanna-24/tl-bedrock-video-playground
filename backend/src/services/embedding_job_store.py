"""
Embedding Job Store - Persistent storage for tracking embedding job state.

This module provides functionality to track async embedding jobs, their status,
and associated metadata. Jobs are persisted to S3 to survive server restarts.
Includes optional caching for frequently accessed jobs.
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

from utils.cache import TTLCache

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client as S3ClientType

logger = logging.getLogger(__name__)

# S3 key for embedding jobs metadata
EMBEDDING_JOBS_S3_KEY = "metadata/embedding_jobs.json"


class Job(BaseModel):
    """Model representing an embedding job.

    Attributes:
        job_id: Unique identifier for the job
        invocation_arn: ARN of the Bedrock async invocation
        video_id: ID of the video being processed
        index_id: ID of the index to store embeddings in
        s3_uri: S3 URI of the video file
        status: Current job status (pending, processing, completed, failed)
        created_at: Timestamp when the job was created
        updated_at: Timestamp when the job was last updated
        retry_count: Number of retry attempts
        error_message: Error message if job failed
        output_location: S3 location of the embedding output
        next_retry_at: Timestamp when the job should be retried (for exponential backoff)
        video_duration: Duration of the video in seconds (for progress estimation)
    """

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    invocation_arn: str
    video_id: str
    index_id: str
    s3_uri: str
    status: str = "pending"  # pending, processing, completed, failed, cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    retry_count: int = 0
    error_message: Optional[str] = None
    output_location: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    video_duration: Optional[float] = None

    def estimate_progress(self) -> Dict[str, Any]:
        """
        Estimate job progress based on video duration and elapsed time.
        
        This method provides progress estimation using a simple heuristic:
        - Processing time is estimated as ~1.5x video duration
        - Progress percentage is calculated based on elapsed time vs estimated total time
        - Expected completion time is calculated from creation time + estimated duration
        
        Returns:
            Dictionary containing:
                - progress_percent: Estimated progress percentage (0-100)
                - estimated_completion_time: ISO timestamp of expected completion
                - elapsed_seconds: Time elapsed since job creation
                - estimated_total_seconds: Estimated total processing time
                - has_estimation: Whether estimation is available (requires video_duration)
        """
        result = {
            "progress_percent": None,
            "estimated_completion_time": None,
            "elapsed_seconds": None,
            "estimated_total_seconds": None,
            "has_estimation": False
        }
        
        # Can only estimate if we have video duration and job is not completed/failed
        if self.video_duration is None or self.status in ["completed", "failed", "cancelled"]:
            return result
        
        # Calculate elapsed time since job creation
        now = datetime.utcnow()
        elapsed = (now - self.created_at).total_seconds()
        
        # Estimate total processing time as 1.5x video duration
        # This is a heuristic based on typical Bedrock processing times
        estimated_total = self.video_duration * 1.5
        
        # Calculate progress percentage (capped at 95% until actually completed)
        if estimated_total > 0:
            progress = min((elapsed / estimated_total) * 100, 95.0)
        else:
            progress = 0.0
        
        # Calculate estimated completion time
        estimated_completion = self.created_at + timedelta(seconds=estimated_total)
        
        result.update({
            "progress_percent": round(progress, 1),
            "estimated_completion_time": estimated_completion.isoformat(),
            "elapsed_seconds": round(elapsed, 1),
            "estimated_total_seconds": round(estimated_total, 1),
            "has_estimation": True
        })
        
        return result


class EmbeddingJobStore:
    """
    Persistent storage for embedding job tracking using S3.

    Stores job records in S3 as a JSON file.
    Provides methods to add, retrieve, and update job records.
    """

    def __init__(
        self,
        s3_client: "S3ClientType",
        bucket_name: str,
        store_path: Optional[str] = None,  # Deprecated, kept for compatibility
        enable_cache: bool = True
    ):
        """
        Initialize the job store with S3 storage and optional caching.

        Args:
            s3_client: Boto3 S3 client instance
            bucket_name: S3 bucket name for storing job data
            store_path: Deprecated parameter, ignored
            enable_cache: Enable TTL-based caching for job lookups (default: True)
        """
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.s3_key = EMBEDDING_JOBS_S3_KEY
        
        logger.info(f"EmbeddingJobStore initialized with S3: s3://{bucket_name}/{self.s3_key}")
        self._ensure_store_exists()
        
        # Initialize cache for job lookups (5 minute TTL)
        self.enable_cache = enable_cache
        if enable_cache:
            self._cache = TTLCache(default_ttl=300, max_size=500)
        else:
            self._cache = None

    def _ensure_store_exists(self) -> None:
        """Create the store file in S3 if it doesn't exist."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=self.s3_key)
        except self.s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                # File doesn't exist, create empty jobs dict
                self._write_jobs({})
                logger.info(f"Created empty jobs file at s3://{self.bucket_name}/{self.s3_key}")
            else:
                raise

    def _read_jobs(self) -> Dict[str, Dict[str, Any]]:
        """
        Read all jobs from S3.

        Returns:
            Dictionary mapping job_id to job data
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=self.s3_key
            )
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except self.s3_client.exceptions.NoSuchKey:
            return {}
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in {self.s3_key}, returning empty dict")
            return {}
        except Exception as e:
            logger.error(f"Error reading jobs from S3: {e}")
            return {}

    def _write_jobs(self, jobs: Dict[str, Dict[str, Any]]) -> None:
        """
        Write jobs to S3.

        Args:
            jobs: Dictionary mapping job_id to job data
        """
        content = json.dumps(jobs, indent=2, default=str)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=self.s3_key,
            Body=content.encode('utf-8'),
            ContentType='application/json'
        )

    def add_job(
        self, invocation_arn: str, video_id: str, index_id: str, s3_uri: str, video_duration: Optional[float] = None
    ) -> str:
        """
        Add a new embedding job to the store.

        Args:
            invocation_arn: ARN of the Bedrock async invocation
            video_id: ID of the video being processed
            index_id: ID of the index to store embeddings in
            s3_uri: S3 URI of the video file
            video_duration: Duration of the video in seconds (for progress estimation)

        Returns:
            job_id: Unique identifier for the created job
        """
        job = Job(
            invocation_arn=invocation_arn,
            video_id=video_id,
            index_id=index_id,
            s3_uri=s3_uri,
            video_duration=video_duration,
        )
        
        logger.info(f"Adding job {job.job_id} to S3 store")

        # Read current jobs, add new one, write back
        jobs = self._read_jobs()
        jobs[job.job_id] = job.model_dump()
        self._write_jobs(jobs)
        
        logger.info(f"Successfully added job {job.job_id} to S3 store")
        return job.job_id

    def get_pending_jobs(self) -> List[Job]:
        """
        Get all jobs with pending or processing status that are ready to be processed.

        For jobs with retry delays (next_retry_at set), only returns jobs where
        the retry time has been reached. This implements exponential backoff.
        
        Cancelled jobs are excluded from the results.

        Returns:
            List of Job objects that are pending or processing and ready to process
        """
        jobs = self._read_jobs()
        pending_jobs = []
        now = datetime.utcnow()

        for job_data in jobs.values():
            # Skip cancelled jobs
            if job_data.get("status") == "cancelled":
                continue
                
            if job_data.get("status") in ["pending", "processing"]:
                # Parse datetime strings back to datetime objects
                if isinstance(job_data.get("created_at"), str):
                    job_data["created_at"] = datetime.fromisoformat(
                        job_data["created_at"]
                    )
                if isinstance(job_data.get("updated_at"), str):
                    job_data["updated_at"] = datetime.fromisoformat(
                        job_data["updated_at"]
                    )
                if isinstance(job_data.get("next_retry_at"), str):
                    job_data["next_retry_at"] = datetime.fromisoformat(
                        job_data["next_retry_at"]
                    )

                job = Job(**job_data)

                # Only include jobs that are ready to be processed
                # If next_retry_at is set, check if it's time to retry
                if job.next_retry_at is None or job.next_retry_at <= now:
                    pending_jobs.append(job)

        return pending_jobs

    def update_job_status(self, job_id: str, status: str, **kwargs) -> None:
        """
        Update the status and other fields of a job.
        
        Invalidates cache entry for the updated job.

        Args:
            job_id: ID of the job to update
            status: New status value
            **kwargs: Additional fields to update (e.g., error_message, output_location)

        Raises:
            ValueError: If job_id is not found
        """
        jobs = self._read_jobs()
        
        if job_id not in jobs:
            raise ValueError(f"Job {job_id} not found")

        # Update job
        job_data = jobs[job_id]
        job_data["status"] = status
        job_data["updated_at"] = datetime.utcnow().isoformat()

        # Update additional fields
        for key, value in kwargs.items():
            if key in job_data:
                job_data[key] = value

        jobs[job_id] = job_data
        self._write_jobs(jobs)
        
        # Invalidate cache entry
        if self._cache:
            self._cache.delete(f"job:{job_id}")

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get a specific job by ID with caching.

        Args:
            job_id: ID of the job to retrieve

        Returns:
            Job object if found, None otherwise
        """
        # Try cache first if enabled
        if self._cache:
            cached_job = self._cache.get(f"job:{job_id}")
            if cached_job is not None:
                return cached_job
        
        jobs = self._read_jobs()
        job_data = jobs.get(job_id)

        if not job_data:
            return None

        # Parse datetime strings back to datetime objects
        if isinstance(job_data.get("created_at"), str):
            job_data["created_at"] = datetime.fromisoformat(job_data["created_at"])
        if isinstance(job_data.get("updated_at"), str):
            job_data["updated_at"] = datetime.fromisoformat(job_data["updated_at"])
        if isinstance(job_data.get("next_retry_at"), str):
            job_data["next_retry_at"] = datetime.fromisoformat(
                job_data["next_retry_at"]
            )

        job = Job(**job_data)
        
        # Cache the job if caching is enabled
        if self._cache:
            self._cache.set(f"job:{job_id}", job)
        
        return job

    def get_all_jobs(self) -> List[Job]:
        """
        Get all jobs from the store.

        Returns:
            List of all Job objects
        """
        jobs = self._read_jobs()
        all_jobs = []

        for job_data in jobs.values():
            # Parse datetime strings back to datetime objects
            if isinstance(job_data.get("created_at"), str):
                job_data["created_at"] = datetime.fromisoformat(job_data["created_at"])
            if isinstance(job_data.get("updated_at"), str):
                job_data["updated_at"] = datetime.fromisoformat(job_data["updated_at"])
            if isinstance(job_data.get("next_retry_at"), str):
                job_data["next_retry_at"] = datetime.fromisoformat(
                    job_data["next_retry_at"]
                )

            all_jobs.append(Job(**job_data))

        return all_jobs

    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics or None if caching is disabled
        """
        if self._cache:
            return self._cache.get_stats()
        return None
    
    def clear_cache(self) -> None:
        """Clear all cached entries."""
        if self._cache:
            self._cache.clear()
    
    def delete_jobs_by_index(self, index_id: str) -> int:
        """
        Delete all jobs associated with a specific index.
        
        This is used during index cleanup to remove all related job records.
        
        Args:
            index_id: ID of the index whose jobs should be deleted
            
        Returns:
            Number of jobs deleted
        """
        jobs = self._read_jobs()
        
        # Find jobs to delete
        jobs_to_delete = [
            job_id for job_id, job_data in jobs.items()
            if job_data.get("index_id") == index_id
        ]
        
        # Delete jobs and invalidate cache
        for job_id in jobs_to_delete:
            del jobs[job_id]
            if self._cache:
                self._cache.delete(f"job:{job_id}")
        
        self._write_jobs(jobs)
        return len(jobs_to_delete)

    def delete_job(self, job_id: str) -> bool:
        """
        Delete a single job by ID.

        This is used during video cleanup to remove the job record for a specific video.

        Args:
            job_id: ID of the job to delete

        Returns:
            True if job was deleted, False if job not found
        """
        jobs = self._read_jobs()
        
        # Check if job exists
        if job_id not in jobs:
            return False

        # Delete job and invalidate cache
        del jobs[job_id]
        if self._cache:
            self._cache.delete(f"job:{job_id}")

        self._write_jobs(jobs)
        return True
