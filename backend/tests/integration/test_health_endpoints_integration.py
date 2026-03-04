"""Integration tests for health check endpoints.

This module tests the health check endpoints in a real application context.

Validates: Requirements 8.4
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI application.
    
    Note: This test requires a valid config file to be present.
    """
    from main import app
    return TestClient(app)


class TestHealthEndpointsIntegration:
    """Integration tests for health check endpoints."""
    
    def test_basic_health_check_endpoint(self, test_client):
        """Test that the basic health check endpoint returns 200 OK."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "environment" in data
        assert "version" in data
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
    
    def test_processor_health_check_endpoint(self, test_client):
        """Test that the processor health check endpoint returns valid data."""
        response = test_client.get("/health/processor")
        
        # Should return 200 OK regardless of processor status
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields are present
        assert "status" in data
        assert "processor_running" in data
        assert "pending_jobs" in data
        assert "processing_jobs" in data
        assert "total_pending" in data
        assert "jobs_processed" in data
        assert "jobs_completed" in data
        assert "jobs_failed" in data
        assert "jobs_retried" in data
        assert "embeddings_stored" in data
        assert "metrics" in data
        
        # Verify status is one of the expected values
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        
        # Verify metrics structure
        metrics = data["metrics"]
        assert "counters" in metrics
        assert "gauges" in metrics
        assert "timings" in metrics
        assert "timestamps" in metrics
        
        # Verify counter fields
        counters = metrics["counters"]
        assert "jobs_processed" in counters
        assert "jobs_completed" in counters
        assert "jobs_failed" in counters
        assert "jobs_retried" in counters
        assert "embeddings_stored" in counters
        
        # Verify gauge fields
        gauges = metrics["gauges"]
        assert "running" in gauges
        assert "pending_jobs" in gauges
        assert "processing_jobs" in gauges
        assert "total_pending" in gauges
        assert "success_rate_percent" in gauges
        assert "retry_rate_percent" in gauges
        
        # Verify timing fields
        timings = metrics["timings"]
        assert "total_processing_time_seconds" in timings
        assert "total_retrieval_time_seconds" in timings
        assert "total_storage_time_seconds" in timings
        assert "avg_processing_time_seconds" in timings
        assert "avg_retrieval_time_seconds" in timings
        assert "avg_storage_time_seconds" in timings
    
    def test_health_endpoints_in_openapi_docs(self, test_client):
        """Test that health endpoints are documented in OpenAPI schema."""
        response = test_client.get("/openapi.json")
        
        assert response.status_code == 200
        openapi_schema = response.json()
        
        # Verify health endpoints are in the schema
        assert "/health" in openapi_schema["paths"]
        assert "/health/processor" in openapi_schema["paths"]
        
        # Verify basic health endpoint
        health_endpoint = openapi_schema["paths"]["/health"]
        assert "get" in health_endpoint
        assert health_endpoint["get"]["summary"] == "Basic health check"
        
        # Verify processor health endpoint
        processor_endpoint = openapi_schema["paths"]["/health/processor"]
        assert "get" in processor_endpoint
        assert processor_endpoint["get"]["summary"] == "Processor health check"
