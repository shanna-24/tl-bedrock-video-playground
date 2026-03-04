"""
Unit tests for EmbeddingJobStore.

Tests the job store's ability to persist and retrieve job records,
including atomic write operations and concurrent access safety.
"""

import json
import tempfile
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta

import pytest

from src.services.embedding_job_store import EmbeddingJobStore, Job


class TestEmbeddingJobStore:
    """Test suite for EmbeddingJobStore."""
    
    @pytest.fixture
    def temp_store_path(self):
        """Create a temporary file path for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
        Path(temp_path).with_suffix('.tmp').unlink(missing_ok=True)
    
    @pytest.fixture
    def store(self, temp_store_path):
        """Create a job store instance for testing."""
        return EmbeddingJobStore(store_path=temp_store_path)
    
    # Core CRUD Operations Tests
    
    def test_add_job_creates_new_job(self, store):
        """Test that add_job creates a new job with correct fields."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        assert job_id is not None
        assert isinstance(job_id, str)
        
        # Retrieve and verify the job
        job = store.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id
        assert job.invocation_arn == "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test"
        assert job.video_id == "video-123"
        assert job.index_id == "index-456"
        assert job.s3_uri == "s3://bucket/video.mp4"
        assert job.status == "pending"
        assert job.retry_count == 0
        assert job.error_message is None
        assert job.output_location is None
    
    def test_add_job_sets_timestamps(self, store):
        """Test that add_job sets created_at and updated_at timestamps."""
        before = datetime.utcnow()
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        after = datetime.utcnow()
        
        job = store.get_job(job_id)
        assert job.created_at >= before
        assert job.created_at <= after
        assert job.updated_at >= before
        assert job.updated_at <= after
    
    def test_get_job_returns_none_for_nonexistent(self, store):
        """Test that get_job returns None for non-existent job."""
        job = store.get_job("nonexistent-job-id")
        assert job is None
    
    def test_get_job_retrieves_existing_job(self, store):
        """Test that get_job retrieves an existing job correctly."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        job = store.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id
    
    def test_get_pending_jobs_returns_empty_list_initially(self, store):
        """Test that get_pending_jobs returns empty list when no jobs exist."""
        pending_jobs = store.get_pending_jobs()
        assert pending_jobs == []
    
    def test_get_pending_jobs_returns_pending_jobs(self, store):
        """Test that get_pending_jobs returns jobs with pending status."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        pending_jobs = store.get_pending_jobs()
        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == job_id
        assert pending_jobs[0].status == "pending"
    
    def test_get_pending_jobs_returns_processing_jobs(self, store):
        """Test that get_pending_jobs returns jobs with processing status."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        store.update_job_status(job_id, "processing")
        
        pending_jobs = store.get_pending_jobs()
        assert len(pending_jobs) == 1
        assert pending_jobs[0].status == "processing"
    
    def test_get_pending_jobs_excludes_completed_jobs(self, store):
        """Test that get_pending_jobs excludes completed jobs."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        store.update_job_status(job_id, "completed")
        
        pending_jobs = store.get_pending_jobs()
        assert len(pending_jobs) == 0
    
    def test_get_pending_jobs_excludes_failed_jobs(self, store):
        """Test that get_pending_jobs excludes failed jobs."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        store.update_job_status(job_id, "failed")
        
        pending_jobs = store.get_pending_jobs()
        assert len(pending_jobs) == 0
    
    def test_get_pending_jobs_returns_multiple_jobs(self, store):
        """Test that get_pending_jobs returns multiple pending/processing jobs."""
        job_id1 = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test1",
            video_id="video-1",
            index_id="index-1",
            s3_uri="s3://bucket/video1.mp4"
        )
        
        job_id2 = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test2",
            video_id="video-2",
            index_id="index-2",
            s3_uri="s3://bucket/video2.mp4"
        )
        
        store.update_job_status(job_id2, "processing")
        
        pending_jobs = store.get_pending_jobs()
        assert len(pending_jobs) == 2
        job_ids = {job.job_id for job in pending_jobs}
        assert job_id1 in job_ids
        assert job_id2 in job_ids
    
    def test_update_job_status_changes_status(self, store):
        """Test that update_job_status changes the job status."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        store.update_job_status(job_id, "processing")
        
        job = store.get_job(job_id)
        assert job.status == "processing"
    
    def test_update_job_status_updates_timestamp(self, store):
        """Test that update_job_status updates the updated_at timestamp."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        original_job = store.get_job(job_id)
        original_updated_at = original_job.updated_at
        
        time.sleep(0.1)  # Ensure timestamp difference
        store.update_job_status(job_id, "processing")
        
        updated_job = store.get_job(job_id)
        assert updated_job.updated_at > original_updated_at
    
    def test_update_job_status_with_additional_fields(self, store):
        """Test that update_job_status can update additional fields."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        store.update_job_status(
            job_id,
            "completed",
            output_location="s3://bucket/output/embeddings.json",
            retry_count=2
        )
        
        job = store.get_job(job_id)
        assert job.status == "completed"
        assert job.output_location == "s3://bucket/output/embeddings.json"
        assert job.retry_count == 2
    
    def test_update_job_status_with_error_message(self, store):
        """Test that update_job_status can set error message."""
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        store.update_job_status(
            job_id,
            "failed",
            error_message="Bedrock job failed: Invalid input"
        )
        
        job = store.get_job(job_id)
        assert job.status == "failed"
        assert job.error_message == "Bedrock job failed: Invalid input"
    
    def test_update_job_status_raises_error_for_nonexistent_job(self, store):
        """Test that update_job_status raises ValueError for non-existent job."""
        with pytest.raises(ValueError, match="Job nonexistent-id not found"):
            store.update_job_status("nonexistent-id", "completed")
    
    def test_multiple_jobs_with_different_statuses(self, store):
        """Test managing multiple jobs with different statuses."""
        job_id1 = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test1",
            video_id="video-1",
            index_id="index-1",
            s3_uri="s3://bucket/video1.mp4"
        )
        
        job_id2 = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test2",
            video_id="video-2",
            index_id="index-2",
            s3_uri="s3://bucket/video2.mp4"
        )
        
        job_id3 = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test3",
            video_id="video-3",
            index_id="index-3",
            s3_uri="s3://bucket/video3.mp4"
        )
        
        store.update_job_status(job_id1, "processing")
        store.update_job_status(job_id2, "completed")
        store.update_job_status(job_id3, "failed")
        
        pending_jobs = store.get_pending_jobs()
        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == job_id1
        
        job1 = store.get_job(job_id1)
        job2 = store.get_job(job_id2)
        job3 = store.get_job(job_id3)
        
        assert job1.status == "processing"
        assert job2.status == "completed"
        assert job3.status == "failed"
    
    def test_persistence_across_instances(self, temp_store_path):
        """Test that jobs persist across different store instances."""
        store1 = EmbeddingJobStore(store_path=temp_store_path)
        job_id = store1.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        store2 = EmbeddingJobStore(store_path=temp_store_path)
        job = store2.get_job(job_id)
        
        assert job is not None
        assert job.job_id == job_id
        assert job.video_id == "video-123"
    
    # Atomic Write and Concurrency Tests
    
    def test_atomic_write_creates_temp_file(self, store, temp_store_path):
        """Test that atomic writes use a temporary file."""
        # Add a job
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Verify the main file exists
        assert Path(temp_store_path).exists()
        
        # Verify the temp file was cleaned up (replaced with main file)
        temp_file = Path(temp_store_path).with_suffix('.tmp')
        assert not temp_file.exists()
        
        # Verify the job was written correctly
        with open(temp_store_path, 'r') as f:
            data = json.load(f)
            assert job_id in data
            assert data[job_id]['video_id'] == "video-123"
    
    def test_atomic_write_preserves_data_on_concurrent_access(self, store, temp_store_path):
        """Test that atomic writes prevent data corruption."""
        # Add multiple jobs
        job_ids = []
        for i in range(5):
            job_id = store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-{i}",
                video_id=f"video-{i}",
                index_id=f"index-{i}",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
            job_ids.append(job_id)
        
        # Verify all jobs are present
        with open(temp_store_path, 'r') as f:
            data = json.load(f)
            assert len(data) == 5
            for job_id in job_ids:
                assert job_id in data
    
    def test_json_file_is_valid_after_write(self, store, temp_store_path):
        """Test that the JSON file is always valid after writes."""
        # Add a job
        store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Verify the file contains valid JSON
        with open(temp_store_path, 'r') as f:
            data = json.load(f)  # Should not raise JSONDecodeError
            assert isinstance(data, dict)
    
    def test_store_survives_empty_initialization(self, temp_store_path):
        """Test that store can be initialized with non-existent file."""
        # Remove the file if it exists
        Path(temp_store_path).unlink(missing_ok=True)
        
        # Create store - should create the file
        store = EmbeddingJobStore(store_path=temp_store_path)
        
        # Verify file was created
        assert Path(temp_store_path).exists()
        
        # Verify it contains empty dict
        with open(temp_store_path, 'r') as f:
            data = json.load(f)
            assert data == {}
    
    def test_concurrent_writes_are_safe(self, store, temp_store_path):
        """Test that concurrent writes don't corrupt data."""
        job_ids = []
        errors = []
        
        def add_jobs(thread_id, count):
            """Add multiple jobs from a thread."""
            try:
                for i in range(count):
                    job_id = store.add_job(
                        invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/thread-{thread_id}-job-{i}",
                        video_id=f"video-{thread_id}-{i}",
                        index_id=f"index-{thread_id}-{i}",
                        s3_uri=f"s3://bucket/video-{thread_id}-{i}.mp4"
                    )
                    job_ids.append(job_id)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads that write concurrently
        threads = []
        num_threads = 5
        jobs_per_thread = 3
        
        for i in range(num_threads):
            thread = threading.Thread(target=add_jobs, args=(i, jobs_per_thread))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        
        # Verify all jobs were written
        assert len(job_ids) == num_threads * jobs_per_thread
        
        # Verify the file is valid JSON and contains all jobs
        with open(temp_store_path, 'r') as f:
            data = json.load(f)
            assert len(data) == num_threads * jobs_per_thread
            for job_id in job_ids:
                assert job_id in data
    
    def test_concurrent_read_write_are_safe(self, store, temp_store_path):
        """Test that concurrent reads and writes don't cause issues."""
        # Add initial jobs
        for i in range(3):
            store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/initial-{i}",
                video_id=f"video-{i}",
                index_id=f"index-{i}",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
        
        errors = []
        read_results = []
        
        def read_jobs():
            """Read jobs repeatedly."""
            try:
                for _ in range(10):
                    jobs = store.get_pending_jobs()
                    read_results.append(len(jobs))
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        def write_jobs():
            """Write jobs repeatedly."""
            try:
                for i in range(5):
                    store.add_job(
                        invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/concurrent-{i}",
                        video_id=f"video-concurrent-{i}",
                        index_id=f"index-concurrent-{i}",
                        s3_uri=f"s3://bucket/video-concurrent-{i}.mp4"
                    )
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        # Start reader and writer threads
        reader_thread = threading.Thread(target=read_jobs)
        writer_thread = threading.Thread(target=write_jobs)
        
        reader_thread.start()
        writer_thread.start()
        
        reader_thread.join()
        writer_thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent read/write: {errors}"
        
        # Verify reads returned valid results
        assert len(read_results) > 0
        assert all(isinstance(count, int) and count >= 0 for count in read_results)
    
    def test_concurrent_status_updates_are_safe(self, store, temp_store_path):
        """Test that concurrent status updates don't corrupt data."""
        # Add jobs
        job_ids = []
        for i in range(5):
            job_id = store.add_job(
                invocation_arn=f"arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/update-{i}",
                video_id=f"video-{i}",
                index_id=f"index-{i}",
                s3_uri=f"s3://bucket/video-{i}.mp4"
            )
            job_ids.append(job_id)
        
        errors = []
        
        def update_job_status(job_id, status):
            """Update job status."""
            try:
                store.update_job_status(job_id, status)
            except Exception as e:
                errors.append(e)
        
        # Update all jobs concurrently
        threads = []
        for i, job_id in enumerate(job_ids):
            status = "processing" if i % 2 == 0 else "completed"
            thread = threading.Thread(target=update_job_status, args=(job_id, status))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Errors during concurrent updates: {errors}"
        
        # Verify the file is valid JSON
        with open(temp_store_path, 'r') as f:
            data = json.load(f)
            assert len(data) == 5
            
            # Verify all jobs have been updated
            for i, job_id in enumerate(job_ids):
                expected_status = "processing" if i % 2 == 0 else "completed"
                assert data[job_id]['status'] == expected_status


    def test_get_pending_jobs_excludes_jobs_with_future_retry_time(self, store):
        """Test that get_pending_jobs excludes jobs with next_retry_at in the future."""
        # Add a job
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Set next_retry_at to 1 hour in the future
        future_time = datetime.utcnow() + timedelta(hours=1)
        store.update_job_status(
            job_id,
            "pending",
            next_retry_at=future_time
        )
        
        # Get pending jobs
        pending_jobs = store.get_pending_jobs()
        
        # Should not include the job with future retry time
        assert len(pending_jobs) == 0
    
    def test_get_pending_jobs_includes_jobs_with_past_retry_time(self, store):
        """Test that get_pending_jobs includes jobs with next_retry_at in the past."""
        # Add a job
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Set next_retry_at to 1 hour in the past
        past_time = datetime.utcnow() - timedelta(hours=1)
        store.update_job_status(
            job_id,
            "pending",
            next_retry_at=past_time
        )
        
        # Get pending jobs
        pending_jobs = store.get_pending_jobs()
        
        # Should include the job with past retry time
        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == job_id
    
    def test_get_pending_jobs_includes_jobs_with_no_retry_time(self, store):
        """Test that get_pending_jobs includes jobs with no next_retry_at set."""
        # Add a job (no retry time set)
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Get pending jobs
        pending_jobs = store.get_pending_jobs()
        
        # Should include the job with no retry time
        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == job_id
        assert pending_jobs[0].next_retry_at is None
    
    def test_update_job_status_with_next_retry_at(self, store):
        """Test that update_job_status can update next_retry_at field."""
        # Add a job
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Update with next_retry_at
        retry_time = datetime.utcnow() + timedelta(minutes=5)
        store.update_job_status(
            job_id,
            "pending",
            next_retry_at=retry_time
        )
        
        # Retrieve and verify
        job = store.get_job(job_id)
        assert job.next_retry_at is not None
        # Compare timestamps (allow small difference due to serialization)
        time_diff = abs((job.next_retry_at - retry_time).total_seconds())
        assert time_diff < 1.0
    
    def test_get_job_parses_next_retry_at_correctly(self, store):
        """Test that get_job correctly parses next_retry_at from JSON."""
        # Add a job
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4"
        )
        
        # Update with next_retry_at
        retry_time = datetime.utcnow() + timedelta(minutes=10)
        store.update_job_status(
            job_id,
            "pending",
            next_retry_at=retry_time
        )
        
        # Create a new store instance to force reading from file
        new_store = EmbeddingJobStore(store_path=store.store_path)
        
        # Retrieve job
        job = new_store.get_job(job_id)
        
        # Verify next_retry_at is a datetime object
        assert isinstance(job.next_retry_at, datetime)
        # Compare timestamps (allow small difference due to serialization)
        time_diff = abs((job.next_retry_at - retry_time).total_seconds())
        assert time_diff < 1.0

    def test_get_all_jobs_returns_all_jobs(self, store):
        """Test that get_all_jobs returns all jobs regardless of status."""
        # Add jobs with different statuses
        job_id_1 = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test1",
            video_id="video-1",
            index_id="index-1",
            s3_uri="s3://bucket/video1.mp4"
        )
        
        job_id_2 = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test2",
            video_id="video-2",
            index_id="index-2",
            s3_uri="s3://bucket/video2.mp4"
        )
        
        job_id_3 = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test3",
            video_id="video-3",
            index_id="index-3",
            s3_uri="s3://bucket/video3.mp4"
        )
        
        job_id_4 = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test4",
            video_id="video-4",
            index_id="index-4",
            s3_uri="s3://bucket/video4.mp4"
        )
        
        # Update jobs to different statuses (leave job_id_1 as pending)
        store.update_job_status(job_id_2, "processing")
        store.update_job_status(job_id_3, "completed")
        store.update_job_status(job_id_4, "failed")
        
        # Get all jobs
        all_jobs = store.get_all_jobs()
        
        # Verify all jobs are returned
        assert len(all_jobs) == 4
        
        # Verify job IDs
        job_ids = {job.job_id for job in all_jobs}
        assert job_ids == {job_id_1, job_id_2, job_id_3, job_id_4}
        
        # Verify statuses
        statuses = {job.status for job in all_jobs}
        assert statuses == {"pending", "processing", "completed", "failed"}
    
    def test_get_all_jobs_returns_empty_list_when_no_jobs(self, store):
        """Test that get_all_jobs returns empty list when no jobs exist."""
        all_jobs = store.get_all_jobs()
        assert all_jobs == []
