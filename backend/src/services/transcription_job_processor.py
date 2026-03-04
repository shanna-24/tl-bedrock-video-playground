"""Transcription Job Processor - Background worker for processing transcription jobs.

This module provides a background processor that monitors AWS Transcribe jobs,
retrieves completed transcriptions, and stores them for search results.
"""

import logging
import threading
import time
from typing import Optional, Dict, Any

from aws.transcribe_client import TranscribeClient
from services.transcription_service import TranscriptionService
from config import Config

logger = logging.getLogger(__name__)


class TranscriptionJobProcessor:
    """Background processor for transcription jobs.
    
    Monitors AWS Transcribe jobs and processes completed transcriptions.
    """
    
    def __init__(
        self,
        config: Config,
        poll_interval: int = 60,
        enabled: bool = True
    ):
        """Initialize the transcription job processor.
        
        Args:
            config: Configuration object
            poll_interval: Seconds between polling cycles (default: 60)
            enabled: Whether the processor is enabled (default: True)
        """
        self.config = config
        self.poll_interval = poll_interval
        self.enabled = enabled
        
        self.transcription_service = TranscriptionService(config)
        self.transcribe_client = TranscribeClient(config)
        
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._pending_jobs: Dict[str, str] = {}  # job_name -> video_id
        
        logger.info(
            f"Initialized TranscriptionJobProcessor "
            f"(poll_interval={poll_interval}s, enabled={enabled})"
        )
    
    def start(self) -> None:
        """Start the background processor thread."""
        if not self.enabled:
            logger.info("Transcription processor is disabled")
            return
        
        if self._thread and self._thread.is_alive():
            logger.warning("Transcription processor already running")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._process_loop,
            name="TranscriptionJobProcessor",
            daemon=True
        )
        self._thread.start()
        
        logger.info("Started transcription job processor")
    
    def stop(self, timeout: float = 10.0) -> None:
        """Stop the background processor thread.
        
        Args:
            timeout: Maximum seconds to wait for thread to stop
        """
        if not self._thread or not self._thread.is_alive():
            logger.info("Transcription processor not running")
            return
        
        logger.info("Stopping transcription job processor...")
        self._stop_event.set()
        
        self._thread.join(timeout=timeout)
        
        if self._thread.is_alive():
            logger.warning(
                f"Transcription processor did not stop within {timeout}s"
            )
        else:
            logger.info("Transcription job processor stopped")
    
    def add_job(self, video_id: str, job_name: str) -> None:
        """Add a transcription job to monitor.
        
        Args:
            video_id: ID of the video
            job_name: AWS Transcribe job name
        """
        self._pending_jobs[job_name] = video_id
        logger.info(f"Added transcription job to monitor: {job_name} for video {video_id}")
    
    def _process_loop(self) -> None:
        """Main processing loop that runs in background thread."""
        logger.info("Transcription processor loop started")
        
        while not self._stop_event.is_set():
            try:
                # Discover any IN_PROGRESS jobs from AWS Transcribe
                # This ensures we process jobs even if they weren't registered via add_job()
                self._discover_pending_jobs()
                
                if self._pending_jobs:
                    self._process_pending_jobs()
                
                # Wait for next poll interval or stop event
                self._stop_event.wait(timeout=self.poll_interval)
                
            except Exception as e:
                logger.error(f"Error in transcription processor loop: {e}", exc_info=True)
                # Continue processing despite errors
                time.sleep(5)
        
        logger.info("Transcription processor loop stopped")
    
    def _discover_pending_jobs(self) -> None:
        """Discover IN_PROGRESS and COMPLETED transcription jobs from AWS Transcribe.
        
        This method queries AWS Transcribe for any IN_PROGRESS or COMPLETED jobs
        and adds them to the pending jobs list if they're not already being tracked.
        This ensures we process jobs even if they weren't registered via add_job()
        (e.g., jobs started manually or before the processor was running).
        """
        try:
            # Check both IN_PROGRESS and COMPLETED jobs
            for status in ['IN_PROGRESS', 'COMPLETED']:
                response = self.transcribe_client.client.list_transcription_jobs(
                    Status=status,
                    MaxResults=100
                )
                
                jobs = response.get('TranscriptionJobSummaries', [])
                
                for job in jobs:
                    job_name = job['TranscriptionJobName']
                    
                    # Only process jobs that follow our naming convention
                    if not job_name.startswith('transcription-'):
                        continue
                    
                    # Skip if already being tracked
                    if job_name in self._pending_jobs:
                        continue
                    
                    # Extract video_id from job name
                    video_id = job_name.replace('transcription-', '')
                    
                    # For COMPLETED jobs, check if we already have the segments file
                    if status == 'COMPLETED':
                        try:
                            # Check if segments file exists in S3
                            import boto3
                            s3_client = boto3.client('s3', region_name=self.config.aws_region)
                            key = f"transcriptions/segments/{video_id}.json"
                            s3_client.head_object(
                                Bucket=self.config.s3_bucket_name,
                                Key=key
                            )
                            # File exists, skip this job
                            logger.debug(
                                f"Skipping completed job {job_name} - segments already stored"
                            )
                            continue
                        except Exception:
                            # File doesn't exist, need to process this job
                            pass
                    
                    # Add to pending jobs
                    self._pending_jobs[job_name] = video_id
                    logger.info(
                        f"Discovered {status} transcription job: {job_name} "
                        f"for video {video_id}"
                    )
            
        except Exception as e:
            logger.warning(f"Failed to discover pending transcription jobs: {e}")
    
    def _process_pending_jobs(self) -> None:
        """Process all pending transcription jobs."""
        completed_jobs = []
        
        for job_name, video_id in list(self._pending_jobs.items()):
            try:
                # Check job status
                status_info = self.transcribe_client.get_transcription_job_status(job_name)
                status = status_info["status"]
                
                if status == "COMPLETED":
                    logger.info(f"Transcription job completed: {job_name}")
                    
                    # Retrieve and store transcription segments
                    try:
                        segments = self.transcription_service.retrieve_and_store_transcription(
                            video_id=video_id
                        )
                        logger.info(
                            f"Stored {len(segments)} transcription segments for video {video_id}"
                        )
                        completed_jobs.append(job_name)
                        
                    except Exception as e:
                        logger.error(
                            f"Failed to retrieve transcription for {video_id}: {e}",
                            exc_info=True
                        )
                        # Remove from pending to avoid infinite retries
                        completed_jobs.append(job_name)
                
                elif status == "FAILED":
                    failure_reason = status_info.get("failure_reason", "Unknown")
                    logger.error(
                        f"Transcription job failed: {job_name}. Reason: {failure_reason}"
                    )
                    completed_jobs.append(job_name)
                
                elif status == "IN_PROGRESS":
                    logger.debug(f"Transcription job still in progress: {job_name}")
                
                else:
                    logger.warning(f"Unknown transcription job status: {status} for {job_name}")
                
            except Exception as e:
                logger.error(
                    f"Error processing transcription job {job_name}: {e}",
                    exc_info=True
                )
        
        # Remove completed jobs from pending list
        for job_name in completed_jobs:
            del self._pending_jobs[job_name]
    
    def get_status(self) -> Dict[str, Any]:
        """Get processor status information.
        
        Returns:
            Dictionary with status information
        """
        return {
            "enabled": self.enabled,
            "running": self._thread and self._thread.is_alive(),
            "pending_jobs": len(self._pending_jobs),
            "poll_interval": self.poll_interval
        }
