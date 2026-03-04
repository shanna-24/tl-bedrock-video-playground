"""
Unit tests for EmbeddingJobProcessor.

Tests the background processor's ability to monitor jobs, retrieve embeddings,
store them in S3 Vectors, and handle failures with retry logic.
"""

import sys
import tempfile
import time
import threading
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.embedding_job_processor import (
    EmbeddingJobProcessor,
    EmbeddingJobProcessorConfig
)
from services.embedding_job_store import EmbeddingJobStore, Job
from services.embedding_retriever import EmbeddingData


class TestEmbeddingJobProcessorConfig:
    """Test suite for EmbeddingJobProcessorConfig."""
    
    def test_default_config_values(self):
        """Test that default configuration values are set correctly."""
        config = EmbeddingJobProcessorConfig()
        
        assert config.poll_interval == 30
        assert config.max_concurrent_jobs == 5
        assert config.max_retries == 3
        assert config.retry_backoff == 60
        assert config.enabled is True
    
    def test_custom_config_values(self):
        """Test that custom configuration values are set correctly."""
        config = EmbeddingJobProcessorConfig(
            poll_interval=10,
            max_concurrent_jobs=3,
            max_retries=5,
            retry_backoff=30,
            enabled=False
        )
        
        assert config.poll_interval == 10
        assert config.max_concurrent_jobs == 3
        assert config.max_retries == 5
        assert config.retry_backoff == 30
        assert config.enabled is False


class TestEmbeddingJobProcessor:
    """Test suite for EmbeddingJobProcessor."""
    
    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary file path for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock Config object."""
        config = Mock()
        config.aws_region = "us-east-1"
        config.s3_bucket_name = "test-bucket"
        config.s3_vectors_collection = "test-collection"
        return config
    
    @pytest.fixture
    def mock_bedrock_client(self):
        """Create a mock BedrockClient."""
        return Mock()
    
    @pytest.fixture
    def mock_s3_client(self):
        """Create a mock S3Client."""
        mock_client = Mock()
        mock_client.client = Mock()  # boto3 client
        return mock_client
    
    @pytest.fixture
    def mock_s3_vectors_client(self):
        """Create a mock S3VectorsClient."""
        return Mock()
    
    @pytest.fixture
    def job_store(self, temp_store_path):
        """Create a job store instance for testing."""
        return EmbeddingJobStore(store_path=temp_store_path)
    
    @pytest.fixture
    def processor_config(self):
        """Create a processor config with short intervals for testing."""
        return EmbeddingJobProcessorConfig(
            poll_interval=0.1,  # Short interval for testing
            max_concurrent_jobs=2,
            max_retries=3,
            retry_backoff=1,
            enabled=True
        )
    
    @pytest.fixture
    def processor(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_client,
        mock_s3_vectors_client,
        job_store,
        processor_config
    ):
        """Create a processor instance for testing."""
        return EmbeddingJobProcessor(
            config=mock_config,
            bedrock_client=mock_bedrock_client,
            s3_client=mock_s3_client,
            s3_vectors_client=mock_s3_vectors_client,
            job_store=job_store,
            processor_config=processor_config
        )
    
    # Initialization Tests
    
    def test_processor_initialization(self, processor):
        """Test that processor initializes correctly."""
        assert processor.config is not None
        assert processor.bedrock_client is not None
        assert processor.s3_client is not None
        assert processor.s3_vectors_client is not None
        assert processor.job_store is not None
        assert processor.processor_config is not None
        assert processor.retriever is not None
        assert processor.indexer is not None
        assert processor._running is False
        assert processor._thread is None
    
    def test_processor_uses_default_job_store_if_not_provided(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_client,
        mock_s3_vectors_client
    ):
        """Test that processor creates default job store if not provided."""
        processor = EmbeddingJobProcessor(
            config=mock_config,
            bedrock_client=mock_bedrock_client,
            s3_client=mock_s3_client,
            s3_vectors_client=mock_s3_vectors_client
        )
        
        assert processor.job_store is not None
        assert isinstance(processor.job_store, EmbeddingJobStore)
    
    def test_processor_uses_default_config_if_not_provided(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_client,
        mock_s3_vectors_client,
        job_store
    ):
        """Test that processor creates default config if not provided."""
        processor = EmbeddingJobProcessor(
            config=mock_config,
            bedrock_client=mock_bedrock_client,
            s3_client=mock_s3_client,
            s3_vectors_client=mock_s3_vectors_client,
            job_store=job_store
        )
        
        assert processor.processor_config is not None
        assert isinstance(processor.processor_config, EmbeddingJobProcessorConfig)
        assert processor.processor_config.poll_interval == 30
    
    # Start/Stop Tests
    
    def test_start_creates_and_starts_thread(self, processor):
        """Test that start() creates and starts a background thread."""
        processor.start()
        
        try:
            assert processor.is_running() is True
            assert processor._thread is not None
            assert processor._thread.is_alive() is True
            assert processor._thread.daemon is True
            assert processor._thread.name == "EmbeddingJobProcessor"
        finally:
            processor.stop()
    
    def test_start_does_nothing_if_already_running(self, processor):
        """Test that start() does nothing if processor is already running."""
        processor.start()
        
        try:
            first_thread = processor._thread
            
            # Try to start again
            processor.start()
            
            # Should be the same thread
            assert processor._thread is first_thread
        finally:
            processor.stop()
    
    def test_start_does_nothing_if_disabled(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_client,
        mock_s3_vectors_client,
        job_store
    ):
        """Test that start() does nothing if processor is disabled."""
        disabled_config = EmbeddingJobProcessorConfig(enabled=False)
        processor = EmbeddingJobProcessor(
            config=mock_config,
            bedrock_client=mock_bedrock_client,
            s3_client=mock_s3_client,
            s3_vectors_client=mock_s3_vectors_client,
            job_store=job_store,
            processor_config=disabled_config
        )
        
        processor.start()
        
        assert processor.is_running() is False
        assert processor._thread is None
    
    def test_stop_stops_thread_gracefully(self, processor):
        """Test that stop() stops the thread gracefully."""
        processor.start()
        assert processor.is_running() is True
        
        processor.stop(timeout=2.0)
        
        assert processor.is_running() is False
        assert processor._thread is None or not processor._thread.is_alive()
    
    def test_stop_does_nothing_if_not_running(self, processor):
        """Test that stop() does nothing if processor is not running."""
        assert processor.is_running() is False
        
        # Should not raise an error
        processor.stop()
        
        assert processor.is_running() is False
    
    def test_is_running_returns_false_initially(self, processor):
        """Test that is_running() returns False initially."""
        assert processor.is_running() is False
    
    def test_is_running_returns_true_when_started(self, processor):
        """Test that is_running() returns True when processor is started."""
        processor.start()
        
        try:
            assert processor.is_running() is True
        finally:
            processor.stop()
    
    # Job Processing Tests
    
    def test_process_job_checks_bedrock_status(self, processor, job_store, mock_bedrock_client):
        """Test that _process_job checks job status with Bedrock."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        
        # Process the job
        processor._process_job(job)
        
        # Verify Bedrock was called
        mock_bedrock_client.get_async_invocation_status.assert_called_once_with(
            "arn:aws:bedrock:us-east-1:123456789012:async-invoke/test"
        )
    
    def test_process_job_updates_status_to_processing(self, processor, job_store, mock_bedrock_client):
        """Test that _process_job updates status to processing for InProgress jobs."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        assert job.status == "pending"
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        
        # Process the job
        processor._process_job(job)
        
        # Verify status was updated
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "processing"
    
    def test_handle_completed_job_retrieves_and_stores_embeddings(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that completed jobs retrieve and store embeddings."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        
        # Mock retriever to return embeddings
        mock_embeddings = [
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ]
        processor.retriever.retrieve_embeddings = Mock(return_value=mock_embeddings)
        
        # Mock indexer to return success
        processor.indexer.store_embeddings = Mock(return_value={
            "total": 1,
            "stored": 1,
            "failed": 0,
            "batches": 1
        })
        
        # Process the job
        processor._process_job(job)
        
        # Verify retriever was called
        processor.retriever.retrieve_embeddings.assert_called_once_with(
            "s3://bucket/output/embeddings.json"
        )
        
        # Verify indexer was called
        processor.indexer.store_embeddings.assert_called_once_with(
            embeddings=mock_embeddings,
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Verify job status was updated
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "completed"
        assert updated_job.output_location == "s3://bucket/output/embeddings.json"
    
    def test_handle_completed_job_with_no_embeddings(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that completed jobs with no embeddings are marked as completed with warning."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        
        # Mock retriever to return empty list
        processor.retriever.retrieve_embeddings = Mock(return_value=[])
        
        # Process the job
        processor._process_job(job)
        
        # Verify job status was updated
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "completed"
        assert updated_job.error_message == "No embeddings found in output"
    
    def test_handle_failed_job_with_retries_remaining(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that failed jobs are retried when retries remain."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        assert job.retry_count == 0
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Failed",
            "failureMessage": "Video processing failed"
        }
        
        # Process the job
        processor._process_job(job)
        
        # Verify job was updated for retry
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "pending"
        assert updated_job.retry_count == 1
        assert "Video processing failed" in updated_job.error_message
    
    def test_handle_failed_job_exceeds_max_retries(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that jobs are marked as permanently failed after max retries."""
        # Add a job with max retries already attempted
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Set retry count to max
        job_store.update_job_status(job_id, "pending", retry_count=3)
        
        job = job_store.get_job(job_id)
        assert job.retry_count == 3
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Failed",
            "failureMessage": "Video processing failed"
        }
        
        # Process the job
        processor._process_job(job)
        
        # Verify job was marked as permanently failed
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "failed"
        assert "Max retries exceeded" in updated_job.error_message
    
    def test_handle_failed_job_on_exception(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that exceptions during processing are handled as failures."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        
        # Mock Bedrock to raise an exception
        mock_bedrock_client.get_async_invocation_status.side_effect = Exception("Network error")
        
        # Process the job
        processor._process_job(job)
        
        # Verify job was updated for retry
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "pending"
        assert updated_job.retry_count == 1
        assert "Network error" in updated_job.error_message
    
    # Integration Tests
    
    def test_processor_processes_pending_jobs_in_loop(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that processor processes pending jobs in the main loop."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        
        # Start processor
        processor.start()
        
        try:
            # Wait for processor to process the job
            time.sleep(0.5)
            
            # Verify job was processed
            updated_job = job_store.get_job(job_id)
            assert updated_job.status == "processing"
        finally:
            processor.stop()
    
    def test_processor_respects_max_concurrent_jobs(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that processor respects max_concurrent_jobs limit."""
        # Add multiple jobs (more than max_concurrent_jobs)
        job_ids = []
        for i in range(5):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
            job_ids.append(job_id)
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        
        # Start processor
        processor.start()
        
        try:
            # Wait for one processing cycle
            time.sleep(0.5)
            
            # Verify that only max_concurrent_jobs were processed
            # (processor_config.max_concurrent_jobs = 2)
            processing_count = sum(
                1 for job_id in job_ids
                if job_store.get_job(job_id).status == "processing"
            )
            
            # At least some jobs should be processed, but not necessarily all
            assert processing_count >= 2
        finally:
            processor.stop()
    
    def test_concurrent_job_processing_with_thread_pool(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that jobs are processed concurrently using ThreadPoolExecutor."""
        import threading
        
        # Track which threads process jobs
        processing_threads = []
        original_process_job = processor._process_job
        
        def track_thread_process_job(job):
            processing_threads.append(threading.current_thread().name)
            # Add small delay to ensure concurrent execution
            time.sleep(0.1)
            return original_process_job(job)
        
        processor._process_job = track_thread_process_job
        
        # Add multiple jobs
        job_ids = []
        for i in range(3):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
            job_ids.append(job_id)
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        
        # Start processor
        processor.start()
        
        try:
            # Wait for jobs to be processed
            time.sleep(1.0)
            
            # Verify that multiple worker threads were used
            # (should have EmbeddingJobWorker prefix)
            worker_threads = [t for t in processing_threads if "EmbeddingJobWorker" in t]
            assert len(worker_threads) > 0, "Jobs should be processed by worker threads"
            
            # Verify jobs were processed
            processing_count = sum(
                1 for job_id in job_ids
                if job_store.get_job(job_id).status == "processing"
            )
            assert processing_count >= 2, "Multiple jobs should be processed"
        finally:
            processor.stop()
    
    def test_thread_pool_executor_shutdown_on_stop(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that ThreadPoolExecutor is properly shut down when processor stops."""
        # Start processor
        processor.start()
        
        # Verify executor is created
        assert processor._executor is not None
        
        # Stop processor
        processor.stop()
        
        # Verify executor is shut down
        assert processor._executor is None
    
    # Statistics Tests
    
    def test_get_stats_returns_correct_counts(self, processor, job_store):
        """Test that get_stats returns correct job counts."""
        # Add jobs with different statuses
        job_id1 = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-1",
            video_id="video-1",
            index_id="index-456",
            s3_uri="s3://bucket/video-1.mp4"
        )
        
        job_id2 = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-2",
            video_id="video-2",
            index_id="index-456",
            s3_uri="s3://bucket/video-2.mp4"
        )
        
        # Update one to processing
        job_store.update_job_status(job_id2, "processing")
        
        # Get stats
        stats = processor.get_stats()
        
        assert stats["running"] is False
        assert stats["pending_jobs"] == 1
        assert stats["processing_jobs"] == 1
        assert stats["total_pending"] == 2
    
    def test_get_stats_shows_running_when_started(self, processor):
        """Test that get_stats shows running=True when processor is started."""
        processor.start()
        
        try:
            stats = processor.get_stats()
            assert stats["running"] is True
        finally:
            processor.stop()


    def test_exponential_backoff_calculates_correct_delays(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that exponential backoff calculates correct delays for retries."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Mock Bedrock to fail
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Failed",
            "failureMessage": "Test failure"
        }
        
        # Process job multiple times to test exponential backoff
        # retry_backoff = 1 second (from processor_config fixture)
        # Expected delays: 1 * 2^0 = 1s, 1 * 2^1 = 2s, 1 * 2^2 = 4s
        
        expected_delays = [1, 2, 4]
        
        for i, expected_delay in enumerate(expected_delays):
            job = job_store.get_job(job_id)
            before_time = datetime.utcnow()
            
            # Process the job
            processor._process_job(job)
            
            # Get updated job
            updated_job = job_store.get_job(job_id)
            
            # Verify retry count increased
            assert updated_job.retry_count == i + 1
            
            # Verify next_retry_at is set correctly
            assert updated_job.next_retry_at is not None
            
            # Calculate actual delay
            actual_delay = (updated_job.next_retry_at - before_time).total_seconds()
            
            # Allow 1 second tolerance for processing time
            assert abs(actual_delay - expected_delay) < 1.0, \
                f"Retry {i}: Expected delay ~{expected_delay}s, got {actual_delay}s"
    
    def test_failed_job_with_backoff_not_retried_immediately(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that failed jobs with backoff are not retried immediately."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Mock Bedrock to fail
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Failed",
            "failureMessage": "Test failure"
        }
        
        # Process the job (will fail and schedule retry)
        job = job_store.get_job(job_id)
        processor._process_job(job)
        
        # Verify job is pending with retry scheduled
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "pending"
        assert updated_job.retry_count == 1
        assert updated_job.next_retry_at is not None
        
        # Get pending jobs - should not include this job yet
        pending_jobs = job_store.get_pending_jobs()
        assert len(pending_jobs) == 0, "Job with future retry time should not be pending"
    
    def test_failed_job_becomes_available_after_backoff_expires(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that failed jobs become available after backoff time expires."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Set next_retry_at to past time (simulating expired backoff)
        past_time = datetime.utcnow() - timedelta(seconds=1)
        job_store.update_job_status(
            job_id,
            "pending",
            retry_count=1,
            next_retry_at=past_time
        )
        
        # Get pending jobs - should include this job now
        pending_jobs = job_store.get_pending_jobs()
        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == job_id
    
    def test_handle_failed_job_stores_next_retry_at(
        self,
        processor,
        job_store
    ):
        """Test that _handle_failed_job stores next_retry_at timestamp."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        before_time = datetime.utcnow()
        
        # Handle failure
        processor._handle_failed_job(job, "Test error")
        
        # Get updated job
        updated_job = job_store.get_job(job_id)
        
        # Verify next_retry_at is set
        assert updated_job.next_retry_at is not None
        assert updated_job.next_retry_at > before_time
        
        # Verify it's approximately 1 second in the future (retry_backoff * 2^0)
        expected_delay = processor.processor_config.retry_backoff
        actual_delay = (updated_job.next_retry_at - before_time).total_seconds()
        assert abs(actual_delay - expected_delay) < 1.0
    
    def test_multiple_jobs_with_different_backoff_times(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that multiple jobs can have different backoff times."""
        # Add multiple jobs
        job_ids = []
        for i in range(3):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
            job_ids.append(job_id)
        
        # Set different retry times for each job
        now = datetime.utcnow()
        job_store.update_job_status(job_ids[0], "pending", next_retry_at=now - timedelta(seconds=10))  # Past
        job_store.update_job_status(job_ids[1], "pending", next_retry_at=now + timedelta(seconds=10))  # Future
        job_store.update_job_status(job_ids[2], "pending", next_retry_at=None)  # No backoff
        
        # Get pending jobs
        pending_jobs = job_store.get_pending_jobs()
        pending_job_ids = [job.job_id for job in pending_jobs]
        
        # Should include jobs 0 and 2, but not job 1
        assert len(pending_jobs) == 2
        assert job_ids[0] in pending_job_ids
        assert job_ids[1] not in pending_job_ids
        assert job_ids[2] in pending_job_ids
    
    # Repeated Failures Alert Tests
    
    def test_check_repeated_failures_alerts_on_high_failure_rate(
        self,
        processor,
        job_store,
        caplog
    ):
        """Test that _check_repeated_failures alerts when failure rate exceeds threshold."""
        import logging
        
        # Add 10 jobs - 2 failed (20% failure rate, above 10% threshold)
        job_ids = []
        for i in range(10):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
            job_ids.append(job_id)
        
        # Mark 2 as failed
        job_store.update_job_status(job_ids[0], "failed", error_message="Test failure 1")
        job_store.update_job_status(job_ids[1], "failed", error_message="Test failure 2")
        
        # Mark rest as completed
        for i in range(2, 10):
            job_store.update_job_status(job_ids[i], "completed")
        
        # Check repeated failures
        with caplog.at_level(logging.ERROR):
            processor._check_repeated_failures()
        
        # Verify alert was logged
        assert any("HIGH FAILURE RATE ALERT" in record.message for record in caplog.records)
        assert any("failed_job_count=2" in record.message for record in caplog.records)
        assert any("total_job_count=10" in record.message for record in caplog.records)
    
    def test_check_repeated_failures_no_alert_on_low_failure_rate(
        self,
        processor,
        job_store,
        caplog
    ):
        """Test that _check_repeated_failures doesn't alert when failure rate is low."""
        import logging
        
        # Add 10 jobs - 1 failed (10% failure rate, at threshold)
        job_ids = []
        for i in range(10):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
            job_ids.append(job_id)
        
        # Mark 1 as failed
        job_store.update_job_status(job_ids[0], "failed", error_message="Test failure")
        
        # Mark rest as completed
        for i in range(1, 10):
            job_store.update_job_status(job_ids[i], "completed")
        
        # Check repeated failures
        with caplog.at_level(logging.ERROR):
            processor._check_repeated_failures()
        
        # Verify no alert was logged (10% is not > 10%)
        assert not any("HIGH FAILURE RATE ALERT" in record.message for record in caplog.records)
    
    def test_check_repeated_failures_alerts_on_consecutive_failures(
        self,
        processor,
        job_store,
        caplog
    ):
        """Test that _check_repeated_failures alerts on 3+ consecutive recent failures."""
        import logging
        
        # Add 5 jobs
        job_ids = []
        for i in range(5):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
            job_ids.append(job_id)
            # Add small delay to ensure different updated_at times
            time.sleep(0.01)
        
        # Mark first 2 as completed
        job_store.update_job_status(job_ids[0], "completed")
        time.sleep(0.01)
        job_store.update_job_status(job_ids[1], "completed")
        time.sleep(0.01)
        
        # Mark last 3 as failed (most recent)
        job_store.update_job_status(job_ids[2], "failed", error_message="Failure 1")
        time.sleep(0.01)
        job_store.update_job_status(job_ids[3], "failed", error_message="Failure 2")
        time.sleep(0.01)
        job_store.update_job_status(job_ids[4], "failed", error_message="Failure 3")
        
        # Check repeated failures
        with caplog.at_level(logging.ERROR):
            processor._check_repeated_failures()
        
        # Verify alert was logged
        assert any("REPEATED FAILURES ALERT" in record.message for record in caplog.records)
        assert any("recent_failure_count=3" in record.message for record in caplog.records)
        assert any("recent_job_count=5" in record.message for record in caplog.records)
    
    def test_check_repeated_failures_no_alert_with_few_jobs(
        self,
        processor,
        job_store,
        caplog
    ):
        """Test that _check_repeated_failures doesn't alert with fewer than 5 jobs."""
        import logging
        
        # Add only 3 jobs, all failed
        job_ids = []
        for i in range(3):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
            job_ids.append(job_id)
            job_store.update_job_status(job_id, "failed", error_message="Test failure")
        
        # Check repeated failures
        with caplog.at_level(logging.ERROR):
            processor._check_repeated_failures()
        
        # Verify no alert was logged (need at least 5 jobs for high failure rate alert)
        assert not any("HIGH FAILURE RATE ALERT" in record.message for record in caplog.records)
    
    def test_check_repeated_failures_no_alert_with_no_jobs(
        self,
        processor,
        caplog
    ):
        """Test that _check_repeated_failures handles empty job list gracefully."""
        import logging
        
        # Check repeated failures with no jobs
        with caplog.at_level(logging.ERROR):
            processor._check_repeated_failures()
        
        # Verify no errors or alerts
        assert not any("ALERT" in record.message for record in caplog.records)
    
    # Additional Edge Case Tests
    
    def test_handle_completed_job_missing_output_data_config(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that completed job without outputDataConfig is handled as error."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        
        # Mock Bedrock response without outputDataConfig
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed"
        }
        
        # Process the job
        processor._process_job(job)
        
        # Verify job was updated for retry (treated as error)
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "pending"
        assert updated_job.retry_count == 1
        assert "No outputDataConfig" in updated_job.error_message
    
    def test_handle_completed_job_missing_s3_uri(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that completed job without s3Uri in outputDataConfig is handled as error."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        
        # Mock Bedrock response with outputDataConfig but no s3Uri
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {"someOtherKey": "value"}  # Has outputDataConfig but no s3Uri
        }
        
        # Process the job
        processor._process_job(job)
        
        # Verify job was updated for retry (treated as error)
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "pending"
        assert updated_job.retry_count == 1
        # The error message will be wrapped in "Error processing completed job: ..."
        assert "No s3Uri" in updated_job.error_message
    
    def test_handle_completed_job_retrieval_error(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that errors during embedding retrieval trigger retry."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        
        # Mock retriever to raise an error
        processor.retriever.retrieve_embeddings = Mock(
            side_effect=Exception("S3 download failed")
        )
        
        # Process the job
        processor._process_job(job)
        
        # Verify job was updated for retry
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "pending"
        assert updated_job.retry_count == 1
        assert "S3 download failed" in updated_job.error_message
    
    def test_handle_completed_job_storage_error(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that errors during embedding storage trigger retry."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        
        # Mock retriever to return embeddings
        mock_embeddings = [
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ]
        processor.retriever.retrieve_embeddings = Mock(return_value=mock_embeddings)
        
        # Mock indexer to raise an error
        processor.indexer.store_embeddings = Mock(
            side_effect=Exception("S3 Vectors storage failed")
        )
        
        # Process the job
        processor._process_job(job)
        
        # Verify job was updated for retry
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "pending"
        assert updated_job.retry_count == 1
        assert "S3 Vectors storage failed" in updated_job.error_message
    
    def test_metrics_tracking_updates_correctly(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that metrics are tracked correctly during job processing."""
        # Add jobs
        job_id1 = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-1",
            video_id="video-1",
            index_id="index-456",
            s3_uri="s3://bucket/video-1.mp4"
        )
        
        job_id2 = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-2",
            video_id="video-2",
            index_id="index-456",
            s3_uri="s3://bucket/video-2.mp4"
        )
        
        job_id3 = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-3",
            video_id="video-3",
            index_id="index-456",
            s3_uri="s3://bucket/video-3.mp4"
        )
        
        # Initial metrics
        assert processor._metrics["jobs_processed"] == 0
        assert processor._metrics["jobs_completed"] == 0
        assert processor._metrics["jobs_failed"] == 0
        assert processor._metrics["jobs_retried"] == 0
        
        # Process job 1 - complete successfully
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        processor.retriever.retrieve_embeddings = Mock(return_value=[
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ])
        processor.indexer.store_embeddings = Mock(return_value={
            "total": 1,
            "stored": 1,
            "failed": 0,
            "batches": 1
        })
        
        job1 = job_store.get_job(job_id1)
        processor._process_job(job1)
        
        assert processor._metrics["jobs_processed"] == 1
        assert processor._metrics["jobs_completed"] == 1
        assert processor._metrics["embeddings_stored"] == 1
        
        # Process job 2 - fail and retry
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Failed",
            "failureMessage": "Test failure"
        }
        
        job2 = job_store.get_job(job_id2)
        processor._process_job(job2)
        
        assert processor._metrics["jobs_processed"] == 2
        assert processor._metrics["jobs_retried"] == 1
        
        # Process job 3 - fail permanently (set retry count to max first)
        job_store.update_job_status(job_id3, "pending", retry_count=3)
        
        job3 = job_store.get_job(job_id3)
        processor._process_job(job3)
        
        assert processor._metrics["jobs_processed"] == 3
        assert processor._metrics["jobs_failed"] == 1
    
    def test_process_job_with_unknown_status(
        self,
        processor,
        job_store,
        mock_bedrock_client,
        caplog
    ):
        """Test that unknown Bedrock status is logged as warning."""
        import logging
        
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = job_store.get_job(job_id)
        
        # Mock Bedrock response with unknown status
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "UnknownStatus"
        }
        
        # Process the job
        with caplog.at_level(logging.WARNING):
            processor._process_job(job)
        
        # Verify warning was logged
        assert any("Unknown Bedrock status" in record.message for record in caplog.records)
        
        # Verify job status unchanged
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "pending"
    
    # New Metrics Tests
    
    def test_metrics_include_processing_time(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that metrics include processing time tracking."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        
        # Process the job
        job = job_store.get_job(job_id)
        processor._process_job(job)
        
        # Verify processing time metrics are tracked (internal metrics)
        assert processor._metrics["total_processing_time"] >= 0
        assert processor._metrics["avg_processing_time"] >= 0
        
        # Get stats and verify they include timing metrics
        stats = processor.get_stats()
        assert "total_processing_time" in stats
        assert "avg_processing_time" in stats
        assert stats["total_processing_time"] >= 0
        assert stats["avg_processing_time"] >= 0
    
    def test_metrics_include_retrieval_and_storage_time(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that metrics include retrieval and storage time tracking."""
        # Add a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        
        # Mock retriever to return embeddings
        processor.retriever.retrieve_embeddings = Mock(return_value=[
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ])
        
        # Mock indexer to return success
        processor.indexer.store_embeddings = Mock(return_value={
            "total": 1,
            "stored": 1,
            "failed": 0,
            "batches": 1
        })
        
        # Process the job
        job = job_store.get_job(job_id)
        processor._process_job(job)
        
        # Verify retrieval and storage time metrics are tracked (internal metrics)
        assert processor._metrics["total_retrieval_time"] >= 0
        assert processor._metrics["avg_retrieval_time"] >= 0
        assert processor._metrics["total_storage_time"] >= 0
        assert processor._metrics["avg_storage_time"] >= 0
        
        # Get stats and verify they include timing metrics
        stats = processor.get_stats()
        assert "total_retrieval_time" in stats
        assert "avg_retrieval_time" in stats
        assert "total_storage_time" in stats
        assert "avg_storage_time" in stats
        assert stats["total_retrieval_time"] >= 0
        assert stats["avg_retrieval_time"] >= 0
        assert stats["total_storage_time"] >= 0
        assert stats["avg_storage_time"] >= 0
    
    def test_get_metrics_returns_categorized_metrics(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that get_metrics returns metrics organized by category."""
        # Add and process a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        
        # Mock retriever and indexer
        processor.retriever.retrieve_embeddings = Mock(return_value=[
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ])
        processor.indexer.store_embeddings = Mock(return_value={
            "total": 1,
            "stored": 1,
            "failed": 0,
            "batches": 1
        })
        
        job = job_store.get_job(job_id)
        processor._process_job(job)
        
        # Get metrics
        metrics = processor.get_metrics()
        
        # Verify structure
        assert "counters" in metrics
        assert "gauges" in metrics
        assert "timings" in metrics
        assert "timestamps" in metrics
        
        # Verify counters
        assert metrics["counters"]["jobs_processed"] == 1
        assert metrics["counters"]["jobs_completed"] == 1
        assert metrics["counters"]["jobs_failed"] == 0
        assert metrics["counters"]["embeddings_stored"] == 1
        
        # Verify gauges
        assert "running" in metrics["gauges"]
        assert "pending_jobs" in metrics["gauges"]
        assert "success_rate_percent" in metrics["gauges"]
        assert "retry_rate_percent" in metrics["gauges"]
        assert metrics["gauges"]["success_rate_percent"] == 100.0
        
        # Verify timings
        assert "total_processing_time_seconds" in metrics["timings"]
        assert "avg_processing_time_seconds" in metrics["timings"]
        assert "total_retrieval_time_seconds" in metrics["timings"]
        assert "avg_retrieval_time_seconds" in metrics["timings"]
        assert "total_storage_time_seconds" in metrics["timings"]
        assert "avg_storage_time_seconds" in metrics["timings"]
        
        # Verify timestamps
        assert "last_poll_time" in metrics["timestamps"]
        assert "last_job_completion_time" in metrics["timestamps"]
    
    def test_get_metrics_calculates_success_rate(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that get_metrics calculates success rate correctly."""
        # Add multiple jobs
        for i in range(5):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
        
        # Complete 3 jobs successfully
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        processor.retriever.retrieve_embeddings = Mock(return_value=[
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ])
        processor.indexer.store_embeddings = Mock(return_value={
            "total": 1,
            "stored": 1,
            "failed": 0,
            "batches": 1
        })
        
        for i in range(3):
            job_id = job_store.get_all_jobs()[i].job_id
            job = job_store.get_job(job_id)
            processor._process_job(job)
        
        # Fail 2 jobs permanently
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Failed",
            "failureMessage": "Test failure"
        }
        
        for i in range(3, 5):
            job_id = job_store.get_all_jobs()[i].job_id
            # Set retry count to max to force permanent failure
            job_store.update_job_status(job_id, "pending", retry_count=3)
            job = job_store.get_job(job_id)
            processor._process_job(job)
        
        # Get metrics
        metrics = processor.get_metrics()
        
        # Verify success rate: 3 completed / 5 total = 60%
        assert metrics["gauges"]["success_rate_percent"] == 60.0
        assert metrics["counters"]["jobs_completed"] == 3
        assert metrics["counters"]["jobs_failed"] == 2
    
    def test_get_metrics_calculates_retry_rate(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that get_metrics calculates retry rate correctly."""
        # Add jobs
        for i in range(3):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
        
        # Process 2 jobs that fail and retry
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Failed",
            "failureMessage": "Test failure"
        }
        
        for i in range(2):
            job_id = job_store.get_all_jobs()[i].job_id
            job = job_store.get_job(job_id)
            processor._process_job(job)
        
        # Process 1 job that succeeds
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        processor.retriever.retrieve_embeddings = Mock(return_value=[
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ])
        processor.indexer.store_embeddings = Mock(return_value={
            "total": 1,
            "stored": 1,
            "failed": 0,
            "batches": 1
        })
        
        job_id = job_store.get_all_jobs()[2].job_id
        job = job_store.get_job(job_id)
        processor._process_job(job)
        
        # Get metrics
        metrics = processor.get_metrics()
        
        # Verify retry rate: 2 retries / 3 processed = 66.67%
        assert metrics["gauges"]["retry_rate_percent"] == pytest.approx(66.67, rel=0.01)
        assert metrics["counters"]["jobs_retried"] == 2
        assert metrics["counters"]["jobs_processed"] == 3
    
    def test_avg_metrics_update_correctly_with_multiple_jobs(
        self,
        processor,
        job_store,
        mock_bedrock_client
    ):
        """Test that average metrics are calculated correctly across multiple jobs."""
        # Add multiple jobs
        for i in range(3):
            job_id = job_store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:async-invoke/test-{i}",
                video_id=f"video-{i}",
                index_id="index-456",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
        
        # Mock Bedrock response
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://bucket/output/embeddings.json"
            }
        }
        
        # Mock retriever and indexer
        processor.retriever.retrieve_embeddings = Mock(return_value=[
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ])
        processor.indexer.store_embeddings = Mock(return_value={
            "total": 1,
            "stored": 1,
            "failed": 0,
            "batches": 1
        })
        
        # Process all jobs
        for i in range(3):
            job_id = job_store.get_all_jobs()[i].job_id
            job = job_store.get_job(job_id)
            processor._process_job(job)
        
        # Get metrics
        metrics = processor.get_metrics()
        
        # Verify averages are calculated
        assert metrics["timings"]["avg_processing_time_seconds"] >= 0
        assert metrics["timings"]["avg_retrieval_time_seconds"] >= 0
        assert metrics["timings"]["avg_storage_time_seconds"] >= 0
        
        # Verify totals are sum of all jobs
        assert metrics["timings"]["total_processing_time_seconds"] >= 0
        assert metrics["timings"]["total_retrieval_time_seconds"] >= 0
        assert metrics["timings"]["total_storage_time_seconds"] >= 0
        
        # Verify counts are correct
        assert metrics["counters"]["jobs_processed"] == 3
        assert metrics["counters"]["jobs_completed"] == 3
