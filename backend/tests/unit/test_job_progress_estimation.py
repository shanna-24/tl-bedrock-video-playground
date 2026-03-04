"""Unit tests for job progress estimation feature.

This module tests the progress estimation functionality added to the Job model
and the API endpoints that expose progress information.

Validates: Requirements 13.4
"""

import pytest
from datetime import datetime, timedelta
from src.services.embedding_job_store import Job


class TestJobProgressEstimation:
    """Test suite for job progress estimation."""

    def test_estimate_progress_with_duration(self):
        """Test progress estimation when video duration is available."""
        # Create a job with video duration
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="processing",
            video_duration=100.0,  # 100 second video
            created_at=datetime.utcnow() - timedelta(seconds=50)  # 50 seconds ago
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify estimation is available
        assert progress["has_estimation"] is True
        assert progress["progress_percent"] is not None
        assert progress["estimated_completion_time"] is not None
        assert progress["elapsed_seconds"] is not None
        assert progress["estimated_total_seconds"] is not None

        # Verify calculations
        # Estimated total = 100 * 1.5 = 150 seconds
        assert progress["estimated_total_seconds"] == 150.0

        # Elapsed = 50 seconds
        assert progress["elapsed_seconds"] == pytest.approx(50.0, abs=1.0)

        # Progress = (50 / 150) * 100 = 33.3%
        assert progress["progress_percent"] == pytest.approx(33.3, abs=1.0)

    def test_estimate_progress_without_duration(self):
        """Test progress estimation when video duration is not available."""
        # Create a job without video duration
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="processing",
            video_duration=None
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify estimation is not available
        assert progress["has_estimation"] is False
        assert progress["progress_percent"] is None
        assert progress["estimated_completion_time"] is None
        assert progress["elapsed_seconds"] is None
        assert progress["estimated_total_seconds"] is None

    def test_estimate_progress_completed_job(self):
        """Test progress estimation for completed job returns no estimation."""
        # Create a completed job
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="completed",
            video_duration=100.0
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify no estimation for completed job
        assert progress["has_estimation"] is False

    def test_estimate_progress_failed_job(self):
        """Test progress estimation for failed job returns no estimation."""
        # Create a failed job
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="failed",
            video_duration=100.0
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify no estimation for failed job
        assert progress["has_estimation"] is False

    def test_estimate_progress_cancelled_job(self):
        """Test progress estimation for cancelled job returns no estimation."""
        # Create a cancelled job
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="cancelled",
            video_duration=100.0
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify no estimation for cancelled job
        assert progress["has_estimation"] is False

    def test_estimate_progress_capped_at_95_percent(self):
        """Test that progress is capped at 95% until job actually completes."""
        # Create a job that should be past 100% based on estimation
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="processing",
            video_duration=100.0,  # 100 second video
            created_at=datetime.utcnow() - timedelta(seconds=200)  # 200 seconds ago (past estimated 150s)
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify progress is capped at 95%
        assert progress["progress_percent"] == 95.0

    def test_estimate_progress_short_video(self):
        """Test progress estimation for short video."""
        # Create a job with short video duration
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="processing",
            video_duration=10.0,  # 10 second video
            created_at=datetime.utcnow() - timedelta(seconds=5)  # 5 seconds ago
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify estimation
        # Estimated total = 10 * 1.5 = 15 seconds
        assert progress["estimated_total_seconds"] == 15.0

        # Progress = (5 / 15) * 100 = 33.3%
        assert progress["progress_percent"] == pytest.approx(33.3, abs=1.0)

    def test_estimate_progress_long_video(self):
        """Test progress estimation for long video."""
        # Create a job with long video duration
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="processing",
            video_duration=3600.0,  # 1 hour video
            created_at=datetime.utcnow() - timedelta(seconds=1800)  # 30 minutes ago
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify estimation
        # Estimated total = 3600 * 1.5 = 5400 seconds
        assert progress["estimated_total_seconds"] == 5400.0

        # Progress = (1800 / 5400) * 100 = 33.3%
        assert progress["progress_percent"] == pytest.approx(33.3, abs=1.0)

    def test_estimate_progress_just_started(self):
        """Test progress estimation for job that just started."""
        # Create a job that just started
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="pending",
            video_duration=100.0,
            created_at=datetime.utcnow()  # Just now
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify estimation shows minimal progress
        assert progress["has_estimation"] is True
        assert progress["progress_percent"] >= 0.0
        assert progress["progress_percent"] < 5.0  # Should be very low

    def test_estimate_progress_pending_status(self):
        """Test progress estimation works for pending status."""
        # Create a pending job
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="pending",
            video_duration=100.0,
            created_at=datetime.utcnow() - timedelta(seconds=30)
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify estimation is available for pending jobs
        assert progress["has_estimation"] is True
        assert progress["progress_percent"] is not None

    def test_estimate_progress_zero_duration(self):
        """Test progress estimation with zero duration."""
        # Create a job with zero duration (edge case)
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="processing",
            video_duration=0.0,
            created_at=datetime.utcnow() - timedelta(seconds=10)
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify estimation handles zero duration gracefully
        assert progress["has_estimation"] is True
        assert progress["estimated_total_seconds"] == 0.0
        assert progress["progress_percent"] == 0.0

    def test_estimate_progress_estimated_completion_time(self):
        """Test that estimated completion time is calculated correctly."""
        # Create a job
        created_at = datetime.utcnow() - timedelta(seconds=50)
        job = Job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/video.mp4",
            status="processing",
            video_duration=100.0,  # 100 second video
            created_at=created_at
        )

        # Get progress estimation
        progress = job.estimate_progress()

        # Verify estimated completion time
        # Should be created_at + 150 seconds (100 * 1.5)
        expected_completion = created_at + timedelta(seconds=150)
        actual_completion = datetime.fromisoformat(progress["estimated_completion_time"])

        # Allow 1 second tolerance
        assert abs((actual_completion - expected_completion).total_seconds()) < 1.0
