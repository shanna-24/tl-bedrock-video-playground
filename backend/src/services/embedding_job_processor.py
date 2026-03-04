"""
Embedding Job Processor - Background worker for processing embedding jobs.

This module provides a background processor that monitors async video embedding jobs,
retrieves completed embeddings, and stores them in S3 Vectors to enable video search.

The processor runs in a separate thread and polls for job completion at regular intervals.
It handles job status checking, embedding retrieval, storage, and retry logic.
"""

import json
import logging
import threading
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient
from services.embedding_job_store import EmbeddingJobStore, Job
from services.embedding_retriever import EmbeddingRetriever
from services.embedding_indexer import EmbeddingIndexer
from services.segment_processor_service import SegmentProcessorService
from config import Config

# Import WebSocketManager with TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


def log_structured(level: str, message: str, event_type: str, **context: Any) -> None:
    """
    Log a structured message with consistent fields for monitoring and debugging.

    This function provides structured logging with key-value pairs that can be
    easily parsed by log aggregation systems. All job events should use this
    function to ensure consistent log format.

    Args:
        level: Log level (info, debug, warning, error)
        message: Human-readable log message
        event_type: Type of event (e.g., job_started, job_completed, state_transition)
        **context: Additional context fields (job_id, video_id, status, etc.)

    Example:
        log_structured(
            "info",
            "Job processing started",
            "job_started",
            job_id="abc-123",
            video_id="video-456",
            status="pending"
        )
    """
    # Build structured context
    structured_context = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        **context,
    }

    # Format message with structured fields for easy parsing
    # Format: MESSAGE | field1=value1 field2=value2 ...
    fields_str = " ".join(f"{k}={v}" for k, v in structured_context.items())
    formatted_message = f"{message} | {fields_str}"

    # Log at appropriate level
    log_func = getattr(logger, level.lower())
    log_func(formatted_message, extra=structured_context)


class EmbeddingJobProcessorConfig:
    """Configuration for the embedding job processor.

    Attributes:
        poll_interval: Seconds between polling cycles (default: 30)
        max_concurrent_jobs: Maximum number of jobs to process concurrently (default: 5)
        max_retries: Maximum number of retry attempts for failed jobs (default: 3)
        retry_backoff: Base delay in seconds for exponential backoff (default: 60)
        enabled: Whether the processor is enabled (default: True)
    """

    def __init__(
        self,
        poll_interval: int = 30,
        max_concurrent_jobs: int = 5,
        max_retries: int = 3,
        retry_backoff: int = 60,
        enabled: bool = True,
    ):
        self.poll_interval = poll_interval
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.enabled = enabled


class EmbeddingJobProcessor:
    """
    Background worker that processes embedding jobs.

    This processor:
    1. Polls for pending embedding jobs at regular intervals
    2. Checks job status with Bedrock
    3. Retrieves embeddings from S3 when jobs complete
    4. Stores embeddings in S3 Vectors for search
    5. Handles failures with retry logic and exponential backoff

    The processor runs in a separate thread and can be gracefully shut down.
    """

    def __init__(
        self,
        config: Config,
        bedrock_client: BedrockClient,
        s3_client: S3Client,
        s3_vectors_client: S3VectorsClient,
        job_store: Optional[EmbeddingJobStore] = None,
        processor_config: Optional[EmbeddingJobProcessorConfig] = None,
        websocket_manager: Optional["WebSocketManager"] = None,
    ):
        """
        Initialize the embedding job processor.

        Args:
            config: Application configuration
            bedrock_client: Bedrock client for checking job status
            s3_client: S3 client for downloading embeddings
            s3_vectors_client: S3 Vectors client for storing embeddings
            job_store: Optional job store (creates default if not provided)
            processor_config: Optional processor configuration (uses defaults if not provided)
            websocket_manager: Optional WebSocket manager for real-time notifications
        """
        self.config = config
        self.bedrock_client = bedrock_client
        self.s3_client = s3_client
        self.s3_vectors_client = s3_vectors_client

        # Initialize job store
        self.job_store = job_store or EmbeddingJobStore()

        # Initialize processor configuration
        self.processor_config = processor_config or EmbeddingJobProcessorConfig()

        # Initialize retriever and indexer
        self.retriever = EmbeddingRetriever(s3_client=s3_client.client)
        self.indexer = EmbeddingIndexer(s3_vectors_client=s3_vectors_client)

        # Initialize unified segment processor (handles both transcription and thumbnails)
        self.segment_processor = SegmentProcessorService(
            config=config,
            bedrock_client=bedrock_client,
            s3_client=s3_client,
            max_concurrent_segments=3,
            thumbnail_width=640
        )

        # WebSocket manager for real-time notifications
        self.websocket_manager = websocket_manager

        # Thread control
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        # Thread pool for concurrent job processing
        self._executor: Optional[ThreadPoolExecutor] = None

        # Metrics tracking
        self._metrics = {
            "jobs_processed": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "jobs_retried": 0,
            "embeddings_stored": 0,
            "last_poll_time": None,
            "last_job_completion_time": None,
            "total_processing_time": 0.0,  # Total time spent processing jobs (seconds)
            "total_retrieval_time": 0.0,  # Total time spent retrieving embeddings (seconds)
            "total_storage_time": 0.0,  # Total time spent storing embeddings (seconds)
            "avg_processing_time": 0.0,  # Average time per job (seconds)
            "avg_retrieval_time": 0.0,  # Average time per retrieval (seconds)
            "avg_storage_time": 0.0,  # Average time per storage (seconds)
        }

        log_structured(
            "info",
            "EmbeddingJobProcessor initialized",
            "processor_initialized",
            poll_interval_seconds=self.processor_config.poll_interval,
            max_concurrent_jobs=self.processor_config.max_concurrent_jobs,
            max_retries=self.processor_config.max_retries,
            retry_backoff_seconds=self.processor_config.retry_backoff,
            enabled=self.processor_config.enabled,
        )

    def start(self) -> None:
        """
        Start the background processor thread.

        Creates and starts a daemon thread that runs the polling loop.
        Also initializes the ThreadPoolExecutor for concurrent job processing.
        If the processor is already running, this method does nothing.

        Raises:
            RuntimeError: If processor is disabled in configuration
        """
        if not self.processor_config.enabled:
            log_structured(
                "warning",
                "EmbeddingJobProcessor is disabled in configuration",
                "processor_disabled",
                enabled=False,
            )
            return

        if self._running:
            log_structured(
                "warning",
                "EmbeddingJobProcessor is already running",
                "processor_already_running",
                running=True,
            )
            return

        log_structured("info", "Starting EmbeddingJobProcessor", "processor_starting")

        self._stop_event.clear()
        self._running = True

        # Create thread pool executor for concurrent job processing
        self._executor = ThreadPoolExecutor(
            max_workers=self.processor_config.max_concurrent_jobs,
            thread_name_prefix="EmbeddingJobWorker",
        )
        log_structured(
            "debug",
            "Created ThreadPoolExecutor",
            "executor_created",
            max_workers=self.processor_config.max_concurrent_jobs,
            thread_name_prefix="EmbeddingJobWorker",
        )

        # Create and start daemon thread
        self._thread = threading.Thread(
            target=self._run_loop, name="EmbeddingJobProcessor", daemon=True
        )
        self._thread.start()

        log_structured(
            "info",
            "EmbeddingJobProcessor started successfully",
            "processor_started",
            thread_name="EmbeddingJobProcessor",
            daemon=True,
        )

    def stop(self, timeout: float = 10.0) -> None:
        """
        Stop the background processor thread gracefully.

        Signals the thread to stop, shuts down the ThreadPoolExecutor,
        and waits for all jobs to finish processing before exiting.

        Args:
            timeout: Maximum time to wait for thread to stop (seconds)
        """
        if not self._running:
            log_structured(
                "warning",
                "EmbeddingJobProcessor is not running",
                "processor_not_running",
                running=False,
            )
            return

        log_structured(
            "info",
            "Stopping EmbeddingJobProcessor",
            "processor_stopping",
            timeout_seconds=timeout,
        )

        # Signal thread to stop
        self._stop_event.set()

        # Shutdown segment processor service
        log_structured(
            "debug", "Shutting down SegmentProcessorService", "segment_processor_shutting_down"
        )
        self.segment_processor.shutdown(wait=False)

        # Shutdown thread pool executor
        if self._executor:
            log_structured(
                "debug", "Shutting down ThreadPoolExecutor", "executor_shutting_down"
            )
            self._executor.shutdown(wait=True, cancel_futures=False)
            log_structured(
                "debug",
                "ThreadPoolExecutor shut down successfully",
                "executor_shutdown_complete",
            )
            self._executor = None

        # Wait for thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

            if self._thread.is_alive():
                log_structured(
                    "warning",
                    "EmbeddingJobProcessor thread did not stop within timeout",
                    "processor_stop_timeout",
                    timeout_seconds=timeout,
                    thread_alive=True,
                )
            else:
                log_structured(
                    "info",
                    "EmbeddingJobProcessor stopped successfully",
                    "processor_stopped",
                )

        self._running = False
        self._thread = None

    def is_running(self) -> bool:
        """
        Check if the processor is currently running.

        Returns:
            True if the processor thread is running, False otherwise
        """
        return self._running and self._thread is not None and self._thread.is_alive()

    def _run_loop(self) -> None:
        """
        Main processing loop that runs in the background thread.

        This loop:
        1. Retrieves pending jobs from the job store
        2. Submits jobs to ThreadPoolExecutor for concurrent processing
        3. Waits for jobs to complete or timeout
        4. Sleeps for poll_interval between cycles
        5. Exits when stop_event is set
        """
        log_structured("info", "EmbeddingJobProcessor loop started", "loop_started")
        poll_count = 0

        try:
            while not self._stop_event.is_set():
                try:
                    poll_count += 1
                    poll_start_time = time.time()
                    self._metrics["last_poll_time"] = datetime.utcnow()

                    log_structured(
                        "info",
                        "Starting poll cycle",
                        "poll_cycle_started",
                        poll_number=poll_count,
                    )

                    # Get pending jobs
                    pending_jobs = self.job_store.get_pending_jobs()

                    if pending_jobs:
                        log_structured(
                            "info",
                            "Found pending jobs",
                            "pending_jobs_found",
                            poll_number=poll_count,
                            pending_job_count=len(pending_jobs),
                            jobs_processed_total=self._metrics["jobs_processed"],
                            jobs_completed_total=self._metrics["jobs_completed"],
                            jobs_failed_total=self._metrics["jobs_failed"],
                            jobs_retried_total=self._metrics["jobs_retried"],
                        )

                        # Log job details
                        for job in pending_jobs:
                            log_structured(
                                "debug",
                                "Pending job details",
                                "pending_job_detail",
                                job_id=job.job_id,
                                video_id=job.video_id,
                                index_id=job.index_id,
                                status=job.status,
                                retry_count=job.retry_count,
                                created_at=job.created_at.isoformat(),
                                invocation_arn=job.invocation_arn,
                            )

                        # Submit jobs to thread pool for concurrent processing
                        # The executor will automatically limit to max_concurrent_jobs
                        futures: List[Future] = []

                        for job in pending_jobs:
                            # Check if we should stop
                            if self._stop_event.is_set():
                                log_structured(
                                    "info",
                                    "Stop signal received, exiting loop",
                                    "loop_stop_signal",
                                    poll_number=poll_count,
                                )
                                break

                            # Submit job to thread pool
                            future = self._executor.submit(self._process_job, job)
                            futures.append(future)

                        # Wait for all submitted jobs to complete
                        # This ensures we don't start a new polling cycle until
                        # current jobs are done
                        if futures:
                            log_structured(
                                "debug",
                                "Waiting for jobs to complete",
                                "jobs_submitted",
                                poll_number=poll_count,
                                submitted_job_count=len(futures),
                            )

                            completed_count = 0
                            for future in as_completed(futures):
                                try:
                                    # Get result (will raise exception if job failed)
                                    future.result()
                                    completed_count += 1
                                except Exception as e:
                                    # Log error but continue processing other jobs
                                    log_structured(
                                        "error",
                                        "Error in job processing future",
                                        "job_future_error",
                                        poll_number=poll_count,
                                        error=str(e),
                                        error_type=type(e).__name__,
                                    )
                                    completed_count += 1

                            poll_duration = time.time() - poll_start_time
                            log_structured(
                                "info",
                                "Poll cycle completed",
                                "poll_cycle_completed",
                                poll_number=poll_count,
                                processed_job_count=completed_count,
                                duration_seconds=round(poll_duration, 2),
                            )
                    else:
                        log_structured(
                            "info",
                            "No pending jobs found",
                            "no_pending_jobs",
                            poll_number=poll_count,
                        )

                    # Sleep for poll_interval (with early exit on stop signal)
                    self._stop_event.wait(timeout=self.processor_config.poll_interval)

                except Exception as e:
                    log_structured(
                        "error",
                        "Error in processing loop",
                        "loop_error",
                        poll_number=poll_count,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    # Continue processing other jobs even if one fails
                    # Sleep briefly to avoid tight loop on persistent errors
                    self._stop_event.wait(timeout=5)

        except Exception as e:
            log_structured(
                "error",
                "Fatal error in processing loop",
                "loop_fatal_error",
                poll_count=poll_count,
                error=str(e),
                error_type=type(e).__name__,
            )

        finally:
            log_structured(
                "info",
                "EmbeddingJobProcessor loop stopped",
                "loop_stopped",
                poll_cycles_completed=poll_count,
                jobs_processed_total=self._metrics["jobs_processed"],
                jobs_completed_total=self._metrics["jobs_completed"],
                jobs_failed_total=self._metrics["jobs_failed"],
                jobs_retried_total=self._metrics["jobs_retried"],
                embeddings_stored_total=self._metrics["embeddings_stored"],
            )

    def _process_job(self, job: Job) -> None:
        """
        Process a single embedding job.

        This method:
        1. Checks job status with Bedrock
        2. Handles completed jobs by retrieving and storing embeddings
        3. Handles failed jobs with retry logic
        4. Updates job status in the store

        Args:
            job: Job to process
        """
        job_start_time = time.time()

        log_structured(
            "info",
            "Starting job processing",
            "job_processing_started",
            job_id=job.job_id,
            video_id=job.video_id,
            index_id=job.index_id,
            status=job.status,
            retry_count=job.retry_count,
            max_retries=self.processor_config.max_retries,
            invocation_arn=job.invocation_arn,
        )

        try:
            # Increment processed counter
            self._metrics["jobs_processed"] += 1

            # Check job status with Bedrock
            log_structured(
                "debug",
                "Checking job status with Bedrock",
                "bedrock_status_check",
                job_id=job.job_id,
                invocation_arn=job.invocation_arn,
            )
            status_info = self.bedrock_client.get_async_invocation_status(
                job.invocation_arn
            )

            status = status_info.get("status", "Unknown")
            log_structured(
                "info",
                "Bedrock status retrieved",
                "bedrock_status_retrieved",
                job_id=job.job_id,
                bedrock_status=status,
                previous_status=job.status,
            )

            # Log state transition if status changed
            if status.lower() != job.status:
                log_structured(
                    "info",
                    "Job state transition detected",
                    "state_transition",
                    job_id=job.job_id,
                    video_id=job.video_id,
                    from_status=job.status,
                    to_status=status.lower(),
                )

            # Handle based on status
            if status == "Completed":
                self._handle_completed_job(job, status_info)

            elif status == "Failed":
                failure_message = status_info.get("failureMessage", "Unknown error")
                log_structured(
                    "error",
                    "Bedrock job failed",
                    "bedrock_job_failed",
                    job_id=job.job_id,
                    video_id=job.video_id,
                    failure_message=failure_message,
                )
                self._handle_failed_job(job, failure_message)

            elif status == "InProgress":
                # Update status to processing if it was pending
                if job.status == "pending":
                    log_structured(
                        "info",
                        "Job state transition",
                        "state_transition",
                        job_id=job.job_id,
                        video_id=job.video_id,
                        from_status="pending",
                        to_status="processing",
                    )
                    self.job_store.update_job_status(job.job_id, "processing")
                    log_structured(
                        "info",
                        "Job is in progress",
                        "job_in_progress",
                        job_id=job.job_id,
                        video_id=job.video_id,
                    )
                else:
                    log_structured(
                        "debug",
                        "Job still in progress",
                        "job_still_in_progress",
                        job_id=job.job_id,
                        video_id=job.video_id,
                    )

            else:
                log_structured(
                    "warning",
                    "Unknown Bedrock status",
                    "unknown_bedrock_status",
                    job_id=job.job_id,
                    video_id=job.video_id,
                    bedrock_status=status,
                )

            job_duration = time.time() - job_start_time

            # Update processing time metrics
            self._metrics["total_processing_time"] += job_duration
            if self._metrics["jobs_processed"] > 0:
                self._metrics["avg_processing_time"] = (
                    self._metrics["total_processing_time"]
                    / self._metrics["jobs_processed"]
                )

            log_structured(
                "debug",
                "Job processing completed",
                "job_processing_completed",
                job_id=job.job_id,
                video_id=job.video_id,
                duration_seconds=round(job_duration, 2),
                avg_processing_time_seconds=round(
                    self._metrics["avg_processing_time"], 2
                ),
            )

        except Exception as e:
            job_duration = time.time() - job_start_time

            # Update processing time metrics even on error
            self._metrics["total_processing_time"] += job_duration
            if self._metrics["jobs_processed"] > 0:
                self._metrics["avg_processing_time"] = (
                    self._metrics["total_processing_time"]
                    / self._metrics["jobs_processed"]
                )

            log_structured(
                "error",
                "Error processing job",
                "job_processing_error",
                job_id=job.job_id,
                video_id=job.video_id,
                duration_seconds=round(job_duration, 2),
                error=str(e),
                error_type=type(e).__name__,
            )
            # Treat as transient error and retry
            self._handle_failed_job(job, f"Processing error: {str(e)}")

    def _handle_completed_job(self, job: Job, status_info: Dict[str, Any]) -> None:
        """
        Handle a completed job by retrieving and storing embeddings.

        Args:
            job: Completed job
            status_info: Status information from Bedrock
        """
        log_structured(
            "info",
            "Job state transition to completed",
            "state_transition",
            job_id=job.job_id,
            video_id=job.video_id,
            from_status=job.status,
            to_status="completed",
        )
        log_structured(
            "info",
            "Retrieving embeddings from S3",
            "embeddings_retrieval_started",
            job_id=job.job_id,
            video_id=job.video_id,
        )

        retrieval_start_time = time.time()

        try:
            # Extract output location from status info
            output_data_config = status_info.get("outputDataConfig")
            if not output_data_config:
                raise ValueError("No outputDataConfig in completed job status")

            # Get S3 URI from output config
            # outputDataConfig format: {"s3OutputDataConfig": {"s3Uri": "s3://bucket/path/to/folder"}}
            # Note: Bedrock returns the folder path, not the full file path
            # Try both possible structures for compatibility
            output_s3_uri = None
            
            # Try nested structure first (actual Bedrock response format)
            s3_output_config = output_data_config.get("s3OutputDataConfig")
            if s3_output_config:
                output_s3_uri = s3_output_config.get("s3Uri")
            
            # Fallback to direct s3Uri (in case structure changes)
            if not output_s3_uri:
                output_s3_uri = output_data_config.get("s3Uri")
            
            if not output_s3_uri:
                raise ValueError(
                    f"No s3Uri found in outputDataConfig. "
                    f"Structure: {json.dumps(output_data_config)}"
                )
            
            # Bedrock returns the folder path without the filename
            # Append /output.json if not already present
            if not output_s3_uri.endswith("/output.json"):
                if not output_s3_uri.endswith("/"):
                    output_s3_uri += "/"
                output_s3_uri += "output.json"

            log_structured(
                "info",
                "Output location identified",
                "output_location_found",
                job_id=job.job_id,
                video_id=job.video_id,
                output_s3_uri=output_s3_uri,
            )

            # Retrieve embeddings from S3
            embeddings = self.retriever.retrieve_embeddings(output_s3_uri)

            retrieval_duration = time.time() - retrieval_start_time

            # Update retrieval time metrics
            self._metrics["total_retrieval_time"] += retrieval_duration
            completed_count = self._metrics["jobs_completed"] + 1  # +1 for current job
            self._metrics["avg_retrieval_time"] = (
                self._metrics["total_retrieval_time"] / completed_count
            )

            if not embeddings:
                log_structured(
                    "warning",
                    "No embeddings found in output",
                    "no_embeddings_found",
                    job_id=job.job_id,
                    video_id=job.video_id,
                    output_s3_uri=output_s3_uri,
                    retrieval_duration_seconds=round(retrieval_duration, 2),
                )
                self.job_store.update_job_status(
                    job.job_id,
                    "completed",
                    output_location=output_s3_uri,
                    error_message="No embeddings found in output",
                )
                self._metrics["jobs_completed"] += 1
                return

            log_structured(
                "info",
                "Embeddings retrieved successfully",
                "embeddings_retrieved",
                job_id=job.job_id,
                video_id=job.video_id,
                embedding_count=len(embeddings),
                retrieval_duration_seconds=round(retrieval_duration, 2),
                avg_retrieval_time_seconds=round(
                    self._metrics["avg_retrieval_time"], 2
                ),
            )

            # Log embedding details
            if embeddings:
                first_emb = embeddings[0]
                log_structured(
                    "debug",
                    "First embedding details",
                    "embedding_details",
                    job_id=job.job_id,
                    video_id=job.video_id,
                    embedding_scope=first_emb.embedding_scope,
                    embedding_option=first_emb.embedding_option,
                    start_sec=first_emb.start_sec,
                    end_sec=first_emb.end_sec,
                    vector_dimension=len(first_emb.embedding),
                )

            # Store embeddings in S3 Vectors
            storage_start_time = time.time()
            log_structured(
                "info",
                "Storing embeddings in S3 Vectors",
                "embeddings_storage_started",
                job_id=job.job_id,
                video_id=job.video_id,
                index_id=job.index_id,
                embedding_count=len(embeddings),
            )

            stats = self.indexer.store_embeddings(
                embeddings=embeddings,
                video_id=job.video_id,
                index_id=job.index_id,
                s3_uri=job.s3_uri,
            )

            storage_duration = time.time() - storage_start_time

            # Update storage time metrics
            self._metrics["total_storage_time"] += storage_duration
            self._metrics["avg_storage_time"] = (
                self._metrics["total_storage_time"] / completed_count
            )

            log_structured(
                "info",
                "Embeddings stored successfully",
                "embeddings_stored",
                job_id=job.job_id,
                video_id=job.video_id,
                index_id=job.index_id,
                stored_count=stats["stored"],
                total_count=stats["total"],
                storage_duration_seconds=round(storage_duration, 2),
                avg_storage_time_seconds=round(self._metrics["avg_storage_time"], 2),
            )

            # Track metrics
            self._metrics["embeddings_stored"] += stats["stored"]

            if stats["stored"] < stats["total"]:
                log_structured(
                    "warning",
                    "Partial embeddings storage",
                    "partial_storage",
                    job_id=job.job_id,
                    video_id=job.video_id,
                    stored_count=stats["stored"],
                    total_count=stats["total"],
                    missing_count=stats["total"] - stats["stored"],
                )

            # Update job status to completed
            self.job_store.update_job_status(
                job.job_id, "completed", output_location=output_s3_uri
            )

            # Update metrics
            self._metrics["jobs_completed"] += 1
            self._metrics["last_job_completion_time"] = datetime.utcnow()

            total_duration = retrieval_duration + storage_duration
            log_structured(
                "info",
                "Job completed successfully",
                "job_completed",
                job_id=job.job_id,
                video_id=job.video_id,
                index_id=job.index_id,
                total_duration_seconds=round(total_duration, 2),
                retrieval_duration_seconds=round(retrieval_duration, 2),
                storage_duration_seconds=round(storage_duration, 2),
                embeddings_stored=stats["stored"],
            )

            # Send WebSocket notification for job completion
            if self.websocket_manager:
                try:
                    import asyncio
                    # Run async notification in a thread-safe way
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        self.websocket_manager.broadcast_job_completion(
                            job_id=job.job_id,
                            video_id=job.video_id,
                            index_id=job.index_id,
                            status="completed",
                            embeddings_count=stats["stored"]
                        )
                    )
                    loop.close()
                except Exception as e:
                    log_structured(
                        "error",
                        "Failed to send WebSocket notification",
                        "websocket_notification_error",
                        job_id=job.job_id,
                        error=str(e),
                        error_type=type(e).__name__
                    )
            
            # Process all segments: generate transcriptions and thumbnails in one pass
            try:
                log_structured(
                    "info",
                    "Starting unified segment processing (transcription + thumbnails)",
                    "segment_processing_started",
                    job_id=job.job_id,
                    video_id=job.video_id,
                    segment_count=len(embeddings)
                )
                
                # Extract S3 key from S3 URI
                # Format: s3://bucket/key
                s3_key = job.s3_uri.replace(f"s3://{self.config.s3_bucket_name}/", "")
                
                # Process all segments in one pass (downloads video once)
                processing_stats = self.segment_processor.process_video_segments(
                    embeddings=embeddings,
                    video_id=job.video_id,
                    index_id=job.index_id,
                    s3_uri=job.s3_uri
                )
                
                log_structured(
                    "info",
                    "Segment processing completed",
                    "segment_processing_completed",
                    job_id=job.job_id,
                    video_id=job.video_id,
                    segments_processed=processing_stats["segments_processed"],
                    thumbnails_generated=processing_stats["thumbnails_generated"],
                    transcriptions_generated=processing_stats["transcriptions_generated"]
                )
                
            except Exception as e:
                # Don't fail the job if segment processing fails
                log_structured(
                    "warning",
                    "Failed to process segments",
                    "segment_processing_failed",
                    job_id=job.job_id,
                    video_id=job.video_id,
                    error=str(e),
                    error_type=type(e).__name__
                )

        except Exception as e:
            duration = time.time() - retrieval_start_time
            log_structured(
                "error",
                "Error handling completed job",
                "completed_job_error",
                job_id=job.job_id,
                video_id=job.video_id,
                duration_seconds=round(duration, 2),
                error=str(e),
                error_type=type(e).__name__,
            )
            # Treat as transient error and retry
            self._handle_failed_job(job, f"Error processing completed job: {str(e)}")

    def _handle_failed_job(self, job: Job, error_message: str) -> None:
        """
        Handle a failed job with retry logic.

        If the job has not exceeded max_retries, it will be retried with
        exponential backoff. Otherwise, it will be marked as permanently failed.

        Args:
            job: Failed job
            error_message: Error message describing the failure
        """
        log_structured(
            "warning",
            "Job failed",
            "job_failed",
            job_id=job.job_id,
            video_id=job.video_id,
            error_message=error_message,
            retry_count=job.retry_count,
            max_retries=self.processor_config.max_retries,
        )

        if job.retry_count < self.processor_config.max_retries:
            # Calculate next retry time with exponential backoff
            backoff_delay = self.processor_config.retry_backoff * (2**job.retry_count)
            next_retry_at = datetime.utcnow() + timedelta(seconds=backoff_delay)

            # Update job for retry with exponential backoff
            log_structured(
                "info",
                "Job state transition to pending for retry",
                "state_transition",
                job_id=job.job_id,
                video_id=job.video_id,
                from_status=job.status,
                to_status="pending",
                reason="retry",
            )

            self.job_store.update_job_status(
                job.job_id,
                "pending",
                retry_count=job.retry_count + 1,
                error_message=error_message,
                next_retry_at=next_retry_at,
            )

            # Update metrics
            self._metrics["jobs_retried"] += 1

            log_structured(
                "info",
                "Job scheduled for retry",
                "job_retry_scheduled",
                job_id=job.job_id,
                video_id=job.video_id,
                backoff_delay_seconds=backoff_delay,
                next_retry_at=next_retry_at.isoformat(),
                retry_attempt=job.retry_count + 1,
                max_retries=self.processor_config.max_retries,
            )
        else:
            # Permanent failure
            log_structured(
                "error",
                "Job state transition to failed (permanent)",
                "state_transition",
                job_id=job.job_id,
                video_id=job.video_id,
                from_status=job.status,
                to_status="failed",
                reason="max_retries_exceeded",
            )

            self.job_store.update_job_status(
                job.job_id,
                "failed",
                error_message=f"Max retries exceeded: {error_message}",
            )

            # Update metrics
            self._metrics["jobs_failed"] += 1

            # Alert on permanent failure
            log_structured(
                "error",
                "PERMANENT JOB FAILURE",
                "job_permanent_failure",
                job_id=job.job_id,
                video_id=job.video_id,
                index_id=job.index_id,
                invocation_arn=job.invocation_arn,
                max_retries=self.processor_config.max_retries,
                error_message=error_message,
            )

            # Send WebSocket notification for permanent failure
            if self.websocket_manager:
                try:
                    import asyncio
                    # Run async notification in a thread-safe way
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(
                        self.websocket_manager.broadcast_job_completion(
                            job_id=job.job_id,
                            video_id=job.video_id,
                            index_id=job.index_id,
                            status="failed",
                            embeddings_count=0,
                            error_message=error_message
                        )
                    )
                    loop.close()
                except Exception as e:
                    log_structured(
                        "error",
                        "Failed to send WebSocket notification",
                        "websocket_notification_error",
                        job_id=job.job_id,
                        error=str(e),
                        error_type=type(e).__name__
                    )

            # Check for repeated failures and alert
            self._check_repeated_failures()

    def _check_repeated_failures(self) -> None:
        """
        Check for repeated failures and alert if failure rate is high.

        This method checks if there have been multiple permanent failures
        and logs an alert if the failure rate exceeds a threshold.
        """
        # Get all jobs to calculate failure rate
        all_jobs = self.job_store.get_all_jobs()

        if not all_jobs:
            return

        failed_jobs = [job for job in all_jobs if job.status == "failed"]
        failure_rate = len(failed_jobs) / len(all_jobs)

        # Alert if failure rate exceeds 10% and we have at least 5 jobs
        if len(all_jobs) >= 5 and failure_rate > 0.10:
            log_structured(
                "error",
                "HIGH FAILURE RATE ALERT",
                "high_failure_rate",
                failed_job_count=len(failed_jobs),
                total_job_count=len(all_jobs),
                failure_rate_percent=round(failure_rate * 100, 1),
                threshold_percent=10.0,
                alert_type="systemic_issue",
            )

        # Also alert if we have 3 or more consecutive recent failures
        recent_jobs = sorted(all_jobs, key=lambda j: j.updated_at, reverse=True)[:5]
        recent_failures = [job for job in recent_jobs if job.status == "failed"]

        if len(recent_failures) >= 3:
            failed_job_ids = [job.job_id for job in recent_failures]
            log_structured(
                "error",
                "REPEATED FAILURES ALERT",
                "repeated_failures",
                recent_failure_count=len(recent_failures),
                recent_job_count=len(recent_jobs),
                failed_job_ids=failed_job_ids,
                alert_type="consecutive_failures",
            )

    def get_stats(self) -> Dict[str, Any]:
        """
        Get processor statistics.

        Returns:
            Dictionary containing processor statistics:
                - running: Whether the processor is running
                - pending_jobs: Number of pending jobs
                - processing_jobs: Number of jobs currently processing
                - total_pending: Total number of pending/processing jobs
                - jobs_processed: Total jobs processed since start
                - jobs_completed: Total jobs completed successfully
                - jobs_failed: Total jobs permanently failed
                - jobs_retried: Total retry attempts
                - embeddings_stored: Total embeddings stored
                - last_poll_time: Timestamp of last poll
                - last_job_completion_time: Timestamp of last successful job
                - total_processing_time: Total time spent processing jobs (seconds)
                - total_retrieval_time: Total time spent retrieving embeddings (seconds)
                - total_storage_time: Total time spent storing embeddings (seconds)
                - avg_processing_time: Average time per job (seconds)
                - avg_retrieval_time: Average time per retrieval (seconds)
                - avg_storage_time: Average time per storage (seconds)
        """
        pending_jobs = self.job_store.get_pending_jobs()

        pending_count = sum(1 for job in pending_jobs if job.status == "pending")
        processing_count = sum(1 for job in pending_jobs if job.status == "processing")

        return {
            "running": self.is_running(),
            "pending_jobs": pending_count,
            "processing_jobs": processing_count,
            "total_pending": len(pending_jobs),
            "jobs_processed": self._metrics["jobs_processed"],
            "jobs_completed": self._metrics["jobs_completed"],
            "jobs_failed": self._metrics["jobs_failed"],
            "jobs_retried": self._metrics["jobs_retried"],
            "embeddings_stored": self._metrics["embeddings_stored"],
            "last_poll_time": (
                self._metrics["last_poll_time"].isoformat()
                if self._metrics["last_poll_time"]
                else None
            ),
            "last_job_completion_time": (
                self._metrics["last_job_completion_time"].isoformat()
                if self._metrics["last_job_completion_time"]
                else None
            ),
            "total_processing_time": round(self._metrics["total_processing_time"], 2),
            "total_retrieval_time": round(self._metrics["total_retrieval_time"], 2),
            "total_storage_time": round(self._metrics["total_storage_time"], 2),
            "avg_processing_time": round(self._metrics["avg_processing_time"], 2),
            "avg_retrieval_time": round(self._metrics["avg_retrieval_time"], 2),
            "avg_storage_time": round(self._metrics["avg_storage_time"], 2),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get metrics in a format suitable for monitoring and observability.

        This method provides a structured view of metrics organized by category:
        - counters: Cumulative counts of events
        - gauges: Current state values
        - timings: Performance metrics

        Returns:
            Dictionary containing categorized metrics for monitoring systems
        """
        pending_jobs = self.job_store.get_pending_jobs()
        pending_count = sum(1 for job in pending_jobs if job.status == "pending")
        processing_count = sum(1 for job in pending_jobs if job.status == "processing")

        # Calculate success rate
        total_finished = self._metrics["jobs_completed"] + self._metrics["jobs_failed"]
        success_rate = (
            (self._metrics["jobs_completed"] / total_finished * 100)
            if total_finished > 0
            else 0.0
        )

        # Calculate retry rate
        retry_rate = (
            (self._metrics["jobs_retried"] / self._metrics["jobs_processed"] * 100)
            if self._metrics["jobs_processed"] > 0
            else 0.0
        )

        return {
            "counters": {
                "jobs_processed": self._metrics["jobs_processed"],
                "jobs_completed": self._metrics["jobs_completed"],
                "jobs_failed": self._metrics["jobs_failed"],
                "jobs_retried": self._metrics["jobs_retried"],
                "embeddings_stored": self._metrics["embeddings_stored"],
            },
            "gauges": {
                "running": self.is_running(),
                "pending_jobs": pending_count,
                "processing_jobs": processing_count,
                "total_pending": len(pending_jobs),
                "success_rate_percent": round(success_rate, 2),
                "retry_rate_percent": round(retry_rate, 2),
            },
            "timings": {
                "total_processing_time_seconds": round(
                    self._metrics["total_processing_time"], 2
                ),
                "total_retrieval_time_seconds": round(
                    self._metrics["total_retrieval_time"], 2
                ),
                "total_storage_time_seconds": round(
                    self._metrics["total_storage_time"], 2
                ),
                "avg_processing_time_seconds": round(
                    self._metrics["avg_processing_time"], 2
                ),
                "avg_retrieval_time_seconds": round(
                    self._metrics["avg_retrieval_time"], 2
                ),
                "avg_storage_time_seconds": round(self._metrics["avg_storage_time"], 2),
            },
            "timestamps": {
                "last_poll_time": (
                    self._metrics["last_poll_time"].isoformat()
                    if self._metrics["last_poll_time"]
                    else None
                ),
                "last_job_completion_time": (
                    self._metrics["last_job_completion_time"].isoformat()
                    if self._metrics["last_job_completion_time"]
                    else None
                ),
            },
        }
