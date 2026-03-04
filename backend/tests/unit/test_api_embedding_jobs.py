"""Unit tests for embedding jobs API endpoints.

Tests the API endpoints for querying and listing embedding jobs.
"""

import os
import sys
import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from main import app
from services.embedding_job_store import Job
from api import embedding_jobs


@pytest.fixture
def mock_job_store():
    """Create a mock embedding job store."""
    return Mock()


@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock client."""
    return Mock()


@pytest.fixture
def client(mock_job_store, mock_bedrock_client):
    """Create a test client with mocked dependencies."""
    # Set the mock job store and bedrock client
    embedding_jobs.set_embedding_job_store(mock_job_store)
    embedding_jobs.set_bedrock_client(mock_bedrock_client)
    
    # Create test client
    return TestClient(app)


@pytest.fixture
def sample_job():
    """Create a sample job for testing."""
    return Job(
        job_id="test-job-123",
        invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
        video_id="video-456",
        index_id="index-789",
        s3_uri="s3://test-bucket/videos/test.mp4",
        status="pending",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
        retry_count=0,
        error_message=None,
        output_location=None,
        next_retry_at=None
    )


@pytest.fixture
def sample_completed_job():
    """Create a sample completed job for testing."""
    return Job(
        job_id="test-job-456",
        invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test2",
        video_id="video-789",
        index_id="index-789",
        s3_uri="s3://test-bucket/videos/test2.mp4",
        status="completed",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 5, 0),
        retry_count=0,
        error_message=None,
        output_location="s3://test-bucket/embeddings/output.json",
        next_retry_at=None
    )


@pytest.fixture
def sample_failed_job():
    """Create a sample failed job for testing."""
    return Job(
        job_id="test-job-789",
        invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test3",
        video_id="video-999",
        index_id="index-789",
        s3_uri="s3://test-bucket/videos/test3.mp4",
        status="failed",
        created_at=datetime(2024, 1, 1, 12, 0, 0),
        updated_at=datetime(2024, 1, 1, 12, 10, 0),
        retry_count=3,
        error_message="Max retries exceeded: Bedrock job failed",
        output_location=None,
        next_retry_at=None
    )


class TestGetJob:
    """Tests for GET /api/embedding-jobs/{job_id} endpoint."""
    
    def test_get_job_success(self, client, mock_job_store, sample_job):
        """Test successfully retrieving a job by ID."""
        # Setup mock
        mock_job_store.get_job.return_value = sample_job
        
        # Make request
        response = client.get("/api/embedding-jobs/test-job-123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == "test-job-123"
        assert data["video_id"] == "video-456"
        assert data["index_id"] == "index-789"
        assert data["status"] == "pending"
        assert data["retry_count"] == 0
        assert data["error_message"] is None
        assert data["output_location"] is None
        
        # Verify mock was called correctly
        mock_job_store.get_job.assert_called_once_with("test-job-123")
    
    def test_get_job_not_found(self, client, mock_job_store):
        """Test retrieving a non-existent job."""
        # Setup mock to return None
        mock_job_store.get_job.return_value = None
        
        # Make request
        response = client.get("/api/embedding-jobs/nonexistent-job")
        
        # Verify response
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        
        # Verify mock was called correctly
        mock_job_store.get_job.assert_called_once_with("nonexistent-job")
    
    def test_get_completed_job(self, client, mock_job_store, sample_completed_job):
        """Test retrieving a completed job with output location."""
        # Setup mock
        mock_job_store.get_job.return_value = sample_completed_job
        
        # Make request
        response = client.get("/api/embedding-jobs/test-job-456")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == "test-job-456"
        assert data["status"] == "completed"
        assert data["output_location"] == "s3://test-bucket/embeddings/output.json"
        assert data["error_message"] is None
    
    def test_get_failed_job(self, client, mock_job_store, sample_failed_job):
        """Test retrieving a failed job with error message."""
        # Setup mock
        mock_job_store.get_job.return_value = sample_failed_job
        
        # Make request
        response = client.get("/api/embedding-jobs/test-job-789")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == "test-job-789"
        assert data["status"] == "failed"
        assert data["retry_count"] == 3
        assert "Max retries exceeded" in data["error_message"]
        assert data["output_location"] is None


class TestListJobs:
    """Tests for GET /api/embedding-jobs endpoint."""
    
    def test_list_all_jobs(self, client, mock_job_store, sample_job, sample_completed_job, sample_failed_job):
        """Test listing all jobs without filter."""
        # Setup mock
        mock_job_store.get_all_jobs.return_value = [
            sample_job,
            sample_completed_job,
            sample_failed_job
        ]
        
        # Make request
        response = client.get("/api/embedding-jobs")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 3
        assert len(data["jobs"]) == 3
        
        # Verify job IDs
        job_ids = [job["job_id"] for job in data["jobs"]]
        assert "test-job-123" in job_ids
        assert "test-job-456" in job_ids
        assert "test-job-789" in job_ids
        
        # Verify mock was called correctly
        mock_job_store.get_all_jobs.assert_called_once()
    
    def test_list_jobs_filter_by_pending(self, client, mock_job_store, sample_job, sample_completed_job):
        """Test listing jobs filtered by pending status."""
        # Setup mock
        mock_job_store.get_all_jobs.return_value = [
            sample_job,
            sample_completed_job
        ]
        
        # Make request with status filter
        response = client.get("/api/embedding-jobs?status=pending")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 1
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["job_id"] == "test-job-123"
        assert data["jobs"][0]["status"] == "pending"
    
    def test_list_jobs_filter_by_completed(self, client, mock_job_store, sample_job, sample_completed_job):
        """Test listing jobs filtered by completed status."""
        # Setup mock
        mock_job_store.get_all_jobs.return_value = [
            sample_job,
            sample_completed_job
        ]
        
        # Make request with status filter
        response = client.get("/api/embedding-jobs?status=completed")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 1
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["job_id"] == "test-job-456"
        assert data["jobs"][0]["status"] == "completed"
    
    def test_list_jobs_filter_by_failed(self, client, mock_job_store, sample_failed_job):
        """Test listing jobs filtered by failed status."""
        # Setup mock
        mock_job_store.get_all_jobs.return_value = [sample_failed_job]
        
        # Make request with status filter
        response = client.get("/api/embedding-jobs?status=failed")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 1
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["job_id"] == "test-job-789"
        assert data["jobs"][0]["status"] == "failed"
    
    def test_list_jobs_empty(self, client, mock_job_store):
        """Test listing jobs when no jobs exist."""
        # Setup mock to return empty list
        mock_job_store.get_all_jobs.return_value = []
        
        # Make request
        response = client.get("/api/embedding-jobs")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 0
        assert len(data["jobs"]) == 0
    
    def test_list_jobs_filter_no_matches(self, client, mock_job_store, sample_job):
        """Test listing jobs with filter that matches no jobs."""
        # Setup mock
        mock_job_store.get_all_jobs.return_value = [sample_job]
        
        # Make request with status filter that doesn't match
        response = client.get("/api/embedding-jobs?status=completed")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 0
        assert len(data["jobs"]) == 0


class TestJobResponseFormat:
    """Tests for job response format and data conversion."""
    
    def test_job_response_includes_all_fields(self, client, mock_job_store, sample_job):
        """Test that job response includes all expected fields."""
        # Setup mock
        mock_job_store.get_job.return_value = sample_job
        
        # Make request
        response = client.get("/api/embedding-jobs/test-job-123")
        
        # Verify response has all fields
        data = response.json()
        expected_fields = [
            "job_id", "invocation_arn", "video_id", "index_id", "s3_uri",
            "status", "created_at", "updated_at", "retry_count",
            "error_message", "output_location", "next_retry_at"
        ]
        
        for field in expected_fields:
            assert field in data
    
    def test_datetime_serialization(self, client, mock_job_store, sample_job):
        """Test that datetime fields are properly serialized to ISO format."""
        # Setup mock
        mock_job_store.get_job.return_value = sample_job
        
        # Make request
        response = client.get("/api/embedding-jobs/test-job-123")
        
        # Verify datetime fields are ISO formatted strings
        data = response.json()
        assert data["created_at"] == "2024-01-01T12:00:00"
        assert data["updated_at"] == "2024-01-01T12:00:00"
    
    def test_next_retry_at_serialization(self, client, mock_job_store):
        """Test that next_retry_at is properly serialized when set."""
        # Create job with next_retry_at
        job = Job(
            job_id="test-job-retry",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="pending",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 0, 0),
            retry_count=1,
            next_retry_at=datetime(2024, 1, 1, 12, 5, 0)
        )
        
        # Setup mock
        mock_job_store.get_job.return_value = job
        
        # Make request
        response = client.get("/api/embedding-jobs/test-job-retry")
        
        # Verify next_retry_at is serialized
        data = response.json()
        assert data["next_retry_at"] == "2024-01-01T12:05:00"


class TestRetryJob:
    """Tests for POST /api/embedding-jobs/{job_id}/retry endpoint."""
    
    def test_retry_failed_job_success(self, client, mock_job_store, sample_failed_job):
        """Test successfully retrying a failed job."""
        # Create updated job with reset status
        updated_job = Job(
            job_id=sample_failed_job.job_id,
            invocation_arn=sample_failed_job.invocation_arn,
            video_id=sample_failed_job.video_id,
            index_id=sample_failed_job.index_id,
            s3_uri=sample_failed_job.s3_uri,
            status="pending",
            created_at=sample_failed_job.created_at,
            updated_at=datetime(2024, 1, 1, 12, 15, 0),
            retry_count=0,
            error_message=None,
            output_location=None,
            next_retry_at=None
        )
        
        # Setup mock - first call returns failed job, second returns updated job
        mock_job_store.get_job.side_effect = [sample_failed_job, updated_job]
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-789/retry")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == "test-job-789"
        assert data["status"] == "pending"
        assert data["retry_count"] == 0
        assert data["error_message"] is None
        assert data["next_retry_at"] is None
        
        # Verify mock was called correctly
        assert mock_job_store.get_job.call_count == 2
        mock_job_store.update_job_status.assert_called_once_with(
            job_id="test-job-789",
            status="pending",
            retry_count=0,
            error_message=None,
            next_retry_at=None
        )
    
    def test_retry_job_not_found(self, client, mock_job_store):
        """Test retrying a non-existent job."""
        # Setup mock to return None
        mock_job_store.get_job.return_value = None
        
        # Make request
        response = client.post("/api/embedding-jobs/nonexistent-job/retry")
        
        # Verify response
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_retry_pending_job_fails(self, client, mock_job_store, sample_job):
        """Test that retrying a pending job fails."""
        # Setup mock
        mock_job_store.get_job.return_value = sample_job
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-123/retry")
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "cannot be retried" in data["detail"].lower()
        assert "pending" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_retry_processing_job_fails(self, client, mock_job_store):
        """Test that retrying a processing job fails."""
        # Create processing job
        processing_job = Job(
            job_id="test-job-processing",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="processing",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 2, 0),
            retry_count=0
        )
        
        # Setup mock
        mock_job_store.get_job.return_value = processing_job
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-processing/retry")
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "cannot be retried" in data["detail"].lower()
        assert "processing" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_retry_completed_job_fails(self, client, mock_job_store, sample_completed_job):
        """Test that retrying a completed job fails."""
        # Setup mock
        mock_job_store.get_job.return_value = sample_completed_job
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-456/retry")
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "cannot be retried" in data["detail"].lower()
        assert "completed" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_retry_job_with_partial_retries(self, client, mock_job_store):
        """Test retrying a failed job that had some retry attempts."""
        # Create failed job with retry attempts
        failed_job_with_retries = Job(
            job_id="test-job-retries",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-999",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="failed",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 10, 0),
            retry_count=2,
            error_message="Temporary S3 error",
            next_retry_at=datetime(2024, 1, 1, 12, 15, 0)
        )
        
        # Create updated job
        updated_job = Job(
            job_id=failed_job_with_retries.job_id,
            invocation_arn=failed_job_with_retries.invocation_arn,
            video_id=failed_job_with_retries.video_id,
            index_id=failed_job_with_retries.index_id,
            s3_uri=failed_job_with_retries.s3_uri,
            status="pending",
            created_at=failed_job_with_retries.created_at,
            updated_at=datetime(2024, 1, 1, 12, 20, 0),
            retry_count=0,
            error_message=None,
            next_retry_at=None
        )
        
        # Setup mock
        mock_job_store.get_job.side_effect = [failed_job_with_retries, updated_job]
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-retries/retry")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "pending"
        assert data["retry_count"] == 0
        assert data["error_message"] is None
        assert data["next_retry_at"] is None
        
        # Verify update was called with correct parameters
        mock_job_store.update_job_status.assert_called_once_with(
            job_id="test-job-retries",
            status="pending",
            retry_count=0,
            error_message=None,
            next_retry_at=None
        )



class TestCancelJob:
    """Tests for POST /api/embedding-jobs/{job_id}/cancel endpoint."""
    
    def test_cancel_pending_job_success(self, client, mock_job_store, mock_bedrock_client, sample_job):
        """Test successfully cancelling a pending job."""
        # Create cancelled job
        cancelled_job = Job(
            job_id=sample_job.job_id,
            invocation_arn=sample_job.invocation_arn,
            video_id=sample_job.video_id,
            index_id=sample_job.index_id,
            s3_uri=sample_job.s3_uri,
            status="cancelled",
            created_at=sample_job.created_at,
            updated_at=datetime(2024, 1, 1, 12, 5, 0),
            retry_count=0,
            error_message="Job cancelled by user",
            output_location=None,
            next_retry_at=None
        )
        
        # Setup mocks
        mock_job_store.get_job.side_effect = [sample_job, cancelled_job]
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-123/cancel")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["job_id"] == "test-job-123"
        assert data["status"] == "cancelled"
        assert data["error_message"] == "Job cancelled by user"
        
        # Verify mocks were called correctly
        assert mock_job_store.get_job.call_count == 2
        mock_bedrock_client.stop_model_invocation_job.assert_called_once()
        mock_job_store.update_job_status.assert_called_once_with(
            job_id="test-job-123",
            status="cancelled",
            error_message="Job cancelled by user"
        )
    
    def test_cancel_processing_job_success(self, client, mock_job_store, mock_bedrock_client):
        """Test successfully cancelling a processing job."""
        # Create processing job
        processing_job = Job(
            job_id="test-job-processing",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="processing",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 2, 0),
            retry_count=0
        )
        
        # Create cancelled job
        cancelled_job = Job(
            job_id=processing_job.job_id,
            invocation_arn=processing_job.invocation_arn,
            video_id=processing_job.video_id,
            index_id=processing_job.index_id,
            s3_uri=processing_job.s3_uri,
            status="cancelled",
            created_at=processing_job.created_at,
            updated_at=datetime(2024, 1, 1, 12, 5, 0),
            retry_count=0,
            error_message="Job cancelled by user"
        )
        
        # Setup mocks
        mock_job_store.get_job.side_effect = [processing_job, cancelled_job]
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-processing/cancel")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "cancelled"
        assert data["error_message"] == "Job cancelled by user"
    
    def test_cancel_job_not_found(self, client, mock_job_store):
        """Test cancelling a non-existent job."""
        # Setup mock to return None
        mock_job_store.get_job.return_value = None
        
        # Make request
        response = client.post("/api/embedding-jobs/nonexistent-job/cancel")
        
        # Verify response
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_cancel_completed_job_fails(self, client, mock_job_store, sample_completed_job):
        """Test that cancelling a completed job fails."""
        # Setup mock
        mock_job_store.get_job.return_value = sample_completed_job
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-456/cancel")
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "cannot be cancelled" in data["detail"].lower()
        assert "completed" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_cancel_failed_job_fails(self, client, mock_job_store, sample_failed_job):
        """Test that cancelling a failed job fails."""
        # Setup mock
        mock_job_store.get_job.return_value = sample_failed_job
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-789/cancel")
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "cannot be cancelled" in data["detail"].lower()
        assert "failed" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_cancel_job_already_completed_in_bedrock(self, client, mock_job_store, mock_bedrock_client, sample_job):
        """Test cancelling a job that has already completed in Bedrock."""
        # Setup mocks
        mock_job_store.get_job.return_value = sample_job
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Completed"
        }
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-123/cancel")
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "already completed" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_cancel_job_already_failed_in_bedrock(self, client, mock_job_store, mock_bedrock_client, sample_job):
        """Test cancelling a job that has already failed in Bedrock."""
        # Setup mocks
        mock_job_store.get_job.return_value = sample_job
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "Failed"
        }
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-123/cancel")
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "already failed" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_cancel_job_bedrock_conflict_error(self, client, mock_job_store, mock_bedrock_client, sample_job):
        """Test handling Bedrock conflict error when stopping job."""
        from aws.bedrock_client import BedrockError
        
        # Setup mocks
        mock_job_store.get_job.return_value = sample_job
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        mock_bedrock_client.stop_model_invocation_job.side_effect = BedrockError(
            "Job cannot be stopped (may already be completed or failed)"
        )
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-123/cancel")
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "cannot be cancelled" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_cancel_job_bedrock_other_error(self, client, mock_job_store, mock_bedrock_client, sample_job):
        """Test handling other Bedrock errors when stopping job."""
        from aws.bedrock_client import BedrockError
        
        # Setup mocks
        mock_job_store.get_job.return_value = sample_job
        mock_bedrock_client.get_async_invocation_status.return_value = {
            "status": "InProgress"
        }
        mock_bedrock_client.stop_model_invocation_job.side_effect = BedrockError(
            "Internal server error"
        )
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-123/cancel")
        
        # Verify response
        assert response.status_code == 500
        data = response.json()
        assert "failed to cancel" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()
    
    def test_cancel_already_cancelled_job_fails(self, client, mock_job_store):
        """Test that cancelling an already cancelled job fails."""
        # Create cancelled job
        cancelled_job = Job(
            job_id="test-job-cancelled",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="cancelled",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            updated_at=datetime(2024, 1, 1, 12, 5, 0),
            retry_count=0,
            error_message="Job cancelled by user"
        )
        
        # Setup mock
        mock_job_store.get_job.return_value = cancelled_job
        
        # Make request
        response = client.post("/api/embedding-jobs/test-job-cancelled/cancel")
        
        # Verify response
        assert response.status_code == 400
        data = response.json()
        assert "cannot be cancelled" in data["detail"].lower()
        assert "cancelled" in data["detail"].lower()
        
        # Verify update was not called
        mock_job_store.update_job_status.assert_not_called()


class TestJobProgressEstimationAPI:
    """Test suite for job progress estimation in API responses."""

    def test_get_job_includes_progress_estimation(self, client, mock_job_store):
        """Test that GET /api/embedding-jobs/{job_id} includes progress estimation."""
        # Create a job with video duration
        job = Job(
            job_id="test-job-123",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="processing",
            created_at=datetime.utcnow() - timedelta(seconds=50),
            updated_at=datetime.utcnow(),
            retry_count=0,
            video_duration=100.0  # 100 second video
        )
        
        mock_job_store.get_job.return_value = job
        
        # Make request
        response = client.get("/api/embedding-jobs/test-job-123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Verify progress field is present
        assert "progress" in data
        assert "video_duration" in data
        assert data["video_duration"] == 100.0
        
        # Verify progress estimation fields
        progress = data["progress"]
        assert "has_estimation" in progress
        assert "progress_percent" in progress
        assert "estimated_completion_time" in progress
        assert "elapsed_seconds" in progress
        assert "estimated_total_seconds" in progress
        
        # Verify estimation is available
        assert progress["has_estimation"] is True
        assert progress["progress_percent"] is not None
        assert progress["estimated_total_seconds"] == 150.0  # 100 * 1.5

    def test_get_job_without_duration_no_estimation(self, client, mock_job_store):
        """Test that jobs without video duration have no progress estimation."""
        # Create a job without video duration
        job = Job(
            job_id="test-job-123",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="processing",
            created_at=datetime.utcnow() - timedelta(seconds=50),
            updated_at=datetime.utcnow(),
            retry_count=0,
            video_duration=None
        )
        
        mock_job_store.get_job.return_value = job
        
        # Make request
        response = client.get("/api/embedding-jobs/test-job-123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Verify progress field is present but estimation is not available
        assert "progress" in data
        progress = data["progress"]
        assert progress["has_estimation"] is False
        assert progress["progress_percent"] is None

    def test_list_jobs_includes_progress_estimation(self, client, mock_job_store):
        """Test that GET /api/embedding-jobs includes progress estimation for all jobs."""
        # Create jobs with different durations
        jobs = [
            Job(
                job_id="test-job-1",
                invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test1",
                video_id="video-1",
                index_id="index-789",
                s3_uri="s3://test-bucket/videos/test1.mp4",
                status="processing",
                created_at=datetime.utcnow() - timedelta(seconds=30),
                updated_at=datetime.utcnow(),
                retry_count=0,
                video_duration=60.0
            ),
            Job(
                job_id="test-job-2",
                invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test2",
                video_id="video-2",
                index_id="index-789",
                s3_uri="s3://test-bucket/videos/test2.mp4",
                status="pending",
                created_at=datetime.utcnow() - timedelta(seconds=10),
                updated_at=datetime.utcnow(),
                retry_count=0,
                video_duration=120.0
            ),
            Job(
                job_id="test-job-3",
                invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test3",
                video_id="video-3",
                index_id="index-789",
                s3_uri="s3://test-bucket/videos/test3.mp4",
                status="completed",
                created_at=datetime.utcnow() - timedelta(seconds=100),
                updated_at=datetime.utcnow(),
                retry_count=0,
                video_duration=90.0
            )
        ]
        
        mock_job_store.get_all_jobs.return_value = jobs
        
        # Make request
        response = client.get("/api/embedding-jobs")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Verify all jobs have progress field
        assert "jobs" in data
        assert len(data["jobs"]) == 3
        
        for job_data in data["jobs"]:
            assert "progress" in job_data
            assert "video_duration" in job_data
            
            # Verify progress structure
            progress = job_data["progress"]
            assert "has_estimation" in progress
            assert "progress_percent" in progress
            assert "estimated_completion_time" in progress
            assert "elapsed_seconds" in progress
            assert "estimated_total_seconds" in progress

    def test_completed_job_no_progress_estimation(self, client, mock_job_store):
        """Test that completed jobs don't show progress estimation."""
        # Create a completed job
        job = Job(
            job_id="test-job-123",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="completed",
            created_at=datetime.utcnow() - timedelta(seconds=100),
            updated_at=datetime.utcnow(),
            retry_count=0,
            video_duration=100.0,
            output_location="s3://test-bucket/embeddings/output.json"
        )
        
        mock_job_store.get_job.return_value = job
        
        # Make request
        response = client.get("/api/embedding-jobs/test-job-123")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Verify no estimation for completed job
        assert "progress" in data
        progress = data["progress"]
        assert progress["has_estimation"] is False

    def test_retry_job_preserves_video_duration(self, client, mock_job_store):
        """Test that retrying a job preserves video duration for progress estimation."""
        # Create a failed job with video duration
        failed_job = Job(
            job_id="test-job-123",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="failed",
            created_at=datetime.utcnow() - timedelta(seconds=200),
            updated_at=datetime.utcnow(),
            retry_count=3,
            error_message="Max retries exceeded",
            video_duration=100.0
        )
        
        # Create the retried job (status reset to pending)
        retried_job = Job(
            job_id="test-job-123",
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation/test",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/test.mp4",
            status="pending",
            created_at=datetime.utcnow() - timedelta(seconds=200),
            updated_at=datetime.utcnow(),
            retry_count=0,
            error_message=None,
            video_duration=100.0  # Duration preserved
        )
        
        mock_job_store.get_job.side_effect = [failed_job, retried_job]
        
        # Make retry request
        response = client.post("/api/embedding-jobs/test-job-123/retry")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        # Verify video duration is preserved
        assert data["video_duration"] == 100.0
        assert data["status"] == "pending"
        
        # Verify progress estimation is available
        progress = data["progress"]
        assert progress["has_estimation"] is True
