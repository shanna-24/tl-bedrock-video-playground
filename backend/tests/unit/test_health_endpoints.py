"""Unit tests for health check endpoints.

This module tests the health check endpoints for the application and
embedding job processor.

Validates: Requirements 8.4
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from api.health import (
    health_check,
    processor_health_check,
    _determine_processor_health
)


class TestHealthCheckEndpoint:
    """Tests for the basic health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check_returns_healthy_status(self):
        """Test that health check returns healthy status."""
        # Mock config
        with patch('api.health.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.environment = "development"
            mock_get_config.return_value = mock_config
            
            # Call health check
            response = await health_check()
            
            # Verify response
            assert response.status == "healthy"
            assert response.environment == "development"
            assert response.version == "1.0.0"
    
    @pytest.mark.asyncio
    async def test_health_check_handles_missing_config(self):
        """Test that health check handles missing config gracefully."""
        # Mock config as None
        with patch('api.health.get_config') as mock_get_config:
            mock_get_config.return_value = None
            
            # Call health check
            response = await health_check()
            
            # Verify response
            assert response.status == "healthy"
            assert response.environment == "unknown"
            assert response.version == "1.0.0"


class TestProcessorHealthCheckEndpoint:
    """Tests for the processor health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_processor_health_check_returns_healthy_status(self):
        """Test that processor health check returns healthy status when processor is running."""
        # Mock processor
        mock_processor = Mock()
        mock_processor.get_stats.return_value = {
            "running": True,
            "pending_jobs": 2,
            "processing_jobs": 1,
            "total_pending": 3,
            "jobs_processed": 10,
            "jobs_completed": 9,
            "jobs_failed": 0,
            "jobs_retried": 1,
            "embeddings_stored": 450,
            "last_poll_time": "2024-01-01T12:00:00",
            "last_job_completion_time": "2024-01-01T11:55:00",
            "total_processing_time": 120.5,
            "total_retrieval_time": 45.2,
            "total_storage_time": 30.1,
            "avg_processing_time": 12.05,
            "avg_retrieval_time": 5.02,
            "avg_storage_time": 3.34
        }
        mock_processor.get_metrics.return_value = {
            "counters": {
                "jobs_processed": 10,
                "jobs_completed": 9,
                "jobs_failed": 0,
                "jobs_retried": 1,
                "embeddings_stored": 450
            },
            "gauges": {
                "running": True,
                "pending_jobs": 2,
                "processing_jobs": 1,
                "total_pending": 3,
                "success_rate_percent": 100.0,
                "retry_rate_percent": 10.0
            },
            "timings": {
                "total_processing_time_seconds": 120.5,
                "total_retrieval_time_seconds": 45.2,
                "total_storage_time_seconds": 30.1,
                "avg_processing_time_seconds": 12.05,
                "avg_retrieval_time_seconds": 5.02,
                "avg_storage_time_seconds": 3.34
            },
            "timestamps": {
                "last_poll_time": "2024-01-01T12:00:00",
                "last_job_completion_time": "2024-01-01T11:55:00"
            }
        }
        
        mock_job_store = Mock()
        
        # Call processor health check
        response = await processor_health_check(mock_processor, mock_job_store)
        
        # Verify response
        assert response.status == "healthy"
        assert response.processor_running is True
        assert response.pending_jobs == 2
        assert response.processing_jobs == 1
        assert response.total_pending == 3
        assert response.jobs_processed == 10
        assert response.jobs_completed == 9
        assert response.jobs_failed == 0
        assert response.jobs_retried == 1
        assert response.embeddings_stored == 450
        assert response.last_poll_time == "2024-01-01T12:00:00"
        assert response.last_job_completion_time == "2024-01-01T11:55:00"
        assert response.metrics["gauges"]["success_rate_percent"] == 100.0
    
    @pytest.mark.asyncio
    async def test_processor_health_check_returns_unhealthy_when_not_running(self):
        """Test that processor health check returns unhealthy when processor is not running."""
        # Mock processor that is not running
        mock_processor = Mock()
        mock_processor.get_stats.return_value = {
            "running": False,
            "pending_jobs": 5,
            "processing_jobs": 0,
            "total_pending": 5,
            "jobs_processed": 0,
            "jobs_completed": 0,
            "jobs_failed": 0,
            "jobs_retried": 0,
            "embeddings_stored": 0,
            "last_poll_time": None,
            "last_job_completion_time": None,
            "total_processing_time": 0.0,
            "total_retrieval_time": 0.0,
            "total_storage_time": 0.0,
            "avg_processing_time": 0.0,
            "avg_retrieval_time": 0.0,
            "avg_storage_time": 0.0
        }
        mock_processor.get_metrics.return_value = {
            "counters": {
                "jobs_processed": 0,
                "jobs_completed": 0,
                "jobs_failed": 0,
                "jobs_retried": 0,
                "embeddings_stored": 0
            },
            "gauges": {
                "running": False,
                "pending_jobs": 5,
                "processing_jobs": 0,
                "total_pending": 5,
                "success_rate_percent": 0.0,
                "retry_rate_percent": 0.0
            },
            "timings": {
                "total_processing_time_seconds": 0.0,
                "total_retrieval_time_seconds": 0.0,
                "total_storage_time_seconds": 0.0,
                "avg_processing_time_seconds": 0.0,
                "avg_retrieval_time_seconds": 0.0,
                "avg_storage_time_seconds": 0.0
            },
            "timestamps": {
                "last_poll_time": None,
                "last_job_completion_time": None
            }
        }
        
        mock_job_store = Mock()
        
        # Call processor health check
        response = await processor_health_check(mock_processor, mock_job_store)
        
        # Verify response
        assert response.status == "unhealthy"
        assert response.processor_running is False
        assert response.total_pending == 5
    
    @pytest.mark.asyncio
    async def test_processor_health_check_returns_degraded_with_high_failure_rate(self):
        """Test that processor health check returns degraded with high failure rate."""
        # Mock processor with high failure rate
        mock_processor = Mock()
        mock_processor.get_stats.return_value = {
            "running": True,
            "pending_jobs": 2,
            "processing_jobs": 1,
            "total_pending": 3,
            "jobs_processed": 10,
            "jobs_completed": 6,
            "jobs_failed": 4,
            "jobs_retried": 2,
            "embeddings_stored": 300,
            "last_poll_time": "2024-01-01T12:00:00",
            "last_job_completion_time": "2024-01-01T11:55:00",
            "total_processing_time": 120.5,
            "total_retrieval_time": 45.2,
            "total_storage_time": 30.1,
            "avg_processing_time": 12.05,
            "avg_retrieval_time": 7.53,
            "avg_storage_time": 5.02
        }
        mock_processor.get_metrics.return_value = {
            "counters": {
                "jobs_processed": 10,
                "jobs_completed": 6,
                "jobs_failed": 4,
                "jobs_retried": 2,
                "embeddings_stored": 300
            },
            "gauges": {
                "running": True,
                "pending_jobs": 2,
                "processing_jobs": 1,
                "total_pending": 3,
                "success_rate_percent": 60.0,  # Low success rate
                "retry_rate_percent": 20.0
            },
            "timings": {
                "total_processing_time_seconds": 120.5,
                "total_retrieval_time_seconds": 45.2,
                "total_storage_time_seconds": 30.1,
                "avg_processing_time_seconds": 12.05,
                "avg_retrieval_time_seconds": 7.53,
                "avg_storage_time_seconds": 5.02
            },
            "timestamps": {
                "last_poll_time": "2024-01-01T12:00:00",
                "last_job_completion_time": "2024-01-01T11:55:00"
            }
        }
        
        mock_job_store = Mock()
        
        # Call processor health check
        response = await processor_health_check(mock_processor, mock_job_store)
        
        # Verify response
        assert response.status == "degraded"
        assert response.processor_running is True
        assert response.jobs_failed == 4
        assert response.metrics["gauges"]["success_rate_percent"] == 60.0
    
    @pytest.mark.asyncio
    async def test_processor_health_check_returns_degraded_with_many_pending_jobs(self):
        """Test that processor health check returns degraded with many pending jobs."""
        # Mock processor with many pending jobs
        mock_processor = Mock()
        mock_processor.get_stats.return_value = {
            "running": True,
            "pending_jobs": 60,
            "processing_jobs": 5,
            "total_pending": 65,
            "jobs_processed": 100,
            "jobs_completed": 95,
            "jobs_failed": 5,
            "jobs_retried": 10,
            "embeddings_stored": 4500,
            "last_poll_time": "2024-01-01T12:00:00",
            "last_job_completion_time": "2024-01-01T11:55:00",
            "total_processing_time": 1200.5,
            "total_retrieval_time": 450.2,
            "total_storage_time": 300.1,
            "avg_processing_time": 12.05,
            "avg_retrieval_time": 4.74,
            "avg_storage_time": 3.16
        }
        mock_processor.get_metrics.return_value = {
            "counters": {
                "jobs_processed": 100,
                "jobs_completed": 95,
                "jobs_failed": 5,
                "jobs_retried": 10,
                "embeddings_stored": 4500
            },
            "gauges": {
                "running": True,
                "pending_jobs": 60,
                "processing_jobs": 5,
                "total_pending": 65,
                "success_rate_percent": 95.0,
                "retry_rate_percent": 10.0
            },
            "timings": {
                "total_processing_time_seconds": 1200.5,
                "total_retrieval_time_seconds": 450.2,
                "total_storage_time_seconds": 300.1,
                "avg_processing_time_seconds": 12.05,
                "avg_retrieval_time_seconds": 4.74,
                "avg_storage_time_seconds": 3.16
            },
            "timestamps": {
                "last_poll_time": "2024-01-01T12:00:00",
                "last_job_completion_time": "2024-01-01T11:55:00"
            }
        }
        
        mock_job_store = Mock()
        
        # Call processor health check
        response = await processor_health_check(mock_processor, mock_job_store)
        
        # Verify response
        assert response.status == "degraded"
        assert response.processor_running is True
        assert response.total_pending == 65


class TestDetermineProcessorHealth:
    """Tests for the _determine_processor_health function."""
    
    def test_returns_unhealthy_when_not_running(self):
        """Test that function returns unhealthy when processor is not running."""
        stats = {
            "running": False,
            "total_pending": 5,
            "jobs_processed": 0
        }
        metrics = {
            "gauges": {
                "success_rate_percent": 0.0,
                "retry_rate_percent": 0.0
            }
        }
        
        result = _determine_processor_health(stats, metrics)
        
        assert result == "unhealthy"
    
    def test_returns_degraded_with_low_success_rate(self):
        """Test that function returns degraded with low success rate."""
        stats = {
            "running": True,
            "total_pending": 3,
            "jobs_processed": 10
        }
        metrics = {
            "gauges": {
                "success_rate_percent": 60.0,  # Below 80%
                "retry_rate_percent": 20.0
            }
        }
        
        result = _determine_processor_health(stats, metrics)
        
        assert result == "degraded"
    
    def test_returns_degraded_with_many_pending_jobs(self):
        """Test that function returns degraded with many pending jobs."""
        stats = {
            "running": True,
            "total_pending": 60,  # Above 50
            "jobs_processed": 100
        }
        metrics = {
            "gauges": {
                "success_rate_percent": 95.0,
                "retry_rate_percent": 10.0
            }
        }
        
        result = _determine_processor_health(stats, metrics)
        
        assert result == "degraded"
    
    def test_returns_degraded_with_high_retry_rate(self):
        """Test that function returns degraded with high retry rate."""
        stats = {
            "running": True,
            "total_pending": 3,
            "jobs_processed": 10
        }
        metrics = {
            "gauges": {
                "success_rate_percent": 90.0,
                "retry_rate_percent": 35.0  # Above 30%
            }
        }
        
        result = _determine_processor_health(stats, metrics)
        
        assert result == "degraded"
    
    def test_returns_healthy_with_normal_metrics(self):
        """Test that function returns healthy with normal metrics."""
        stats = {
            "running": True,
            "total_pending": 3,
            "jobs_processed": 10
        }
        metrics = {
            "gauges": {
                "success_rate_percent": 95.0,
                "retry_rate_percent": 10.0
            }
        }
        
        result = _determine_processor_health(stats, metrics)
        
        assert result == "healthy"
    
    def test_ignores_low_success_rate_with_few_jobs(self):
        """Test that function ignores low success rate when few jobs processed."""
        stats = {
            "running": True,
            "total_pending": 2,
            "jobs_processed": 3  # Less than 5
        }
        metrics = {
            "gauges": {
                "success_rate_percent": 50.0,  # Low but ignored
                "retry_rate_percent": 20.0
            }
        }
        
        result = _determine_processor_health(stats, metrics)
        
        assert result == "healthy"
    
    def test_ignores_high_retry_rate_with_few_jobs(self):
        """Test that function ignores high retry rate when few jobs processed."""
        stats = {
            "running": True,
            "total_pending": 2,
            "jobs_processed": 4  # Less than 5
        }
        metrics = {
            "gauges": {
                "success_rate_percent": 90.0,
                "retry_rate_percent": 40.0  # High but ignored
            }
        }
        
        result = _determine_processor_health(stats, metrics)
        
        assert result == "healthy"
