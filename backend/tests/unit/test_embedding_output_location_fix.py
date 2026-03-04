"""Test for embedding output location extraction fix.

This test verifies that the embedding job processor correctly extracts
the output location from Bedrock's nested response structure.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, patch
from datetime import datetime

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.embedding_job_processor import EmbeddingJobProcessor, EmbeddingJobProcessorConfig
from services.embedding_job_store import EmbeddingJobStore, Job
from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient
from config import Config


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock(spec=Config)
    config.s3_bucket_name = "test-bucket"
    config.aws_region = "us-east-1"
    return config


@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock client."""
    return Mock(spec=BedrockClient)


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    s3_client = Mock(spec=S3Client)
    s3_client.client = Mock()  # Add client attribute for EmbeddingRetriever
    return s3_client


@pytest.fixture
def mock_s3_vectors_client():
    """Create a mock S3 Vectors client."""
    return Mock(spec=S3VectorsClient)


@pytest.fixture
def job_store(tmp_path):
    """Create a real job store with temp file."""
    store_path = tmp_path / "jobs.json"
    return EmbeddingJobStore(store_path=str(store_path), enable_cache=False)


class TestEmbeddingOutputLocationFix:
    """Test that output location is correctly extracted from Bedrock response."""
    
    def test_extract_output_location_nested_structure(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_client,
        mock_s3_vectors_client,
        job_store
    ):
        """Test extraction from nested s3OutputDataConfig structure (correct format)."""
        # Create a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test123",
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://test-bucket/videos/video.mp4",
            video_duration=60.0
        )
        
        # Mock Bedrock response with nested structure (actual AWS format)
        # Note: Bedrock returns folder path without filename
        bedrock_response = {
            "status": "Completed",
            "outputDataConfig": {
                "s3OutputDataConfig": {
                    "s3Uri": "s3://test-bucket/embeddings/abc123"
                }
            }
        }
        mock_bedrock_client.get_async_invocation_status.return_value = bedrock_response
        
        # Mock retriever to return empty embeddings (we just want to test extraction)
        with patch('services.embedding_job_processor.EmbeddingRetriever') as mock_retriever_class:
            mock_retriever = Mock()
            mock_retriever.retrieve_embeddings.return_value = []
            mock_retriever_class.return_value = mock_retriever
            
            # Mock indexer
            with patch('services.embedding_job_processor.EmbeddingIndexer') as mock_indexer_class:
                mock_indexer = Mock()
                mock_indexer_class.return_value = mock_indexer
                
                # Create processor
                processor = EmbeddingJobProcessor(
                    config=mock_config,
                    bedrock_client=mock_bedrock_client,
                    s3_client=mock_s3_client,
                    s3_vectors_client=mock_s3_vectors_client,
                    job_store=job_store,
                    processor_config=EmbeddingJobProcessorConfig(enabled=False)
                )
                
                # Get the job
                job = job_store.get_job(job_id)
                
                # Process the job
                processor._process_job(job)
                
                # Verify output_location was set correctly with /output.json appended
                updated_job = job_store.get_job(job_id)
                assert updated_job.output_location == "s3://test-bucket/embeddings/abc123/output.json"
                assert updated_job.status == "completed"
                
                # Verify retriever was called with the complete path
                mock_retriever.retrieve_embeddings.assert_called_once_with(
                    "s3://test-bucket/embeddings/abc123/output.json"
                )
    
    def test_extract_output_location_direct_structure(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_client,
        mock_s3_vectors_client,
        job_store
    ):
        """Test extraction from direct s3Uri structure (fallback compatibility)."""
        # Create a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test456",
            video_id="video-456",
            index_id="index-789",
            s3_uri="s3://test-bucket/videos/video2.mp4",
            video_duration=120.0
        )
        
        # Mock Bedrock response with direct structure (fallback format)
        bedrock_response = {
            "status": "Completed",
            "outputDataConfig": {
                "s3Uri": "s3://test-bucket/embeddings/xyz789/output.json"
            }
        }
        mock_bedrock_client.get_async_invocation_status.return_value = bedrock_response
        
        # Mock retriever
        with patch('services.embedding_job_processor.EmbeddingRetriever') as mock_retriever_class:
            mock_retriever = Mock()
            mock_retriever.retrieve_embeddings.return_value = []
            mock_retriever_class.return_value = mock_retriever
            
            # Mock indexer
            with patch('services.embedding_job_processor.EmbeddingIndexer') as mock_indexer_class:
                mock_indexer = Mock()
                mock_indexer_class.return_value = mock_indexer
                
                # Create processor
                processor = EmbeddingJobProcessor(
                    config=mock_config,
                    bedrock_client=mock_bedrock_client,
                    s3_client=mock_s3_client,
                    s3_vectors_client=mock_s3_vectors_client,
                    job_store=job_store,
                    processor_config=EmbeddingJobProcessorConfig(enabled=False)
                )
                
                # Get the job
                job = job_store.get_job(job_id)
                
                # Process the job
                processor._process_job(job)
                
                # Verify output_location was set correctly
                updated_job = job_store.get_job(job_id)
                assert updated_job.output_location == "s3://test-bucket/embeddings/xyz789/output.json"
                assert updated_job.status == "completed"
    
    def test_missing_output_location_error(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_client,
        mock_s3_vectors_client,
        job_store
    ):
        """Test that missing output location provides helpful error message."""
        # Create a job
        job_id = job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:async-invoke/test789",
            video_id="video-789",
            index_id="index-012",
            s3_uri="s3://test-bucket/videos/video3.mp4"
        )
        
        # Mock Bedrock response with no s3Uri (error case)
        bedrock_response = {
            "status": "Completed",
            "outputDataConfig": {
                "someOtherField": "value"
            }
        }
        mock_bedrock_client.get_async_invocation_status.return_value = bedrock_response
        
        # Create processor with max_retries=0 to fail immediately
        processor = EmbeddingJobProcessor(
            config=mock_config,
            bedrock_client=mock_bedrock_client,
            s3_client=mock_s3_client,
            s3_vectors_client=mock_s3_vectors_client,
            job_store=job_store,
            processor_config=EmbeddingJobProcessorConfig(enabled=False, max_retries=0)
        )
        
        # Get the job
        job = job_store.get_job(job_id)
        
        # Process the job - should handle error gracefully
        processor._process_job(job)
        
        # Verify job was marked as failed with helpful error message
        updated_job = job_store.get_job(job_id)
        assert updated_job.status == "failed"
        assert "No s3Uri found in outputDataConfig" in updated_job.error_message
        assert "Structure:" in updated_job.error_message  # Should include actual structure
