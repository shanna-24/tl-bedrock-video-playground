"""Unit tests for comprehensive index deletion with S3 cleanup.

This module tests that deleting an index properly cleans up all related assets:
- Video files from S3
- Thumbnail files from S3
- Embedding job records
- Vector index from S3 Vectors
- Index metadata
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock, patch

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.index_manager import IndexManager
from services.embedding_job_store import EmbeddingJobStore
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient
from aws.bedrock_client import BedrockClient
from storage.metadata_store import IndexMetadataStore
from models.index import Index
from config import Config


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Mock(spec=Config)
    config.max_indexes = 10
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-bucket"
    config.use_localstack = False
    return config


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    s3_client = Mock(spec=S3Client)
    s3_client.bucket_name = "test-bucket"
    s3_client.delete_prefix = Mock(return_value=5)  # Returns count of deleted objects
    s3_client.delete = Mock(return_value=True)
    return s3_client


@pytest.fixture
def mock_s3_vectors_client():
    """Create a mock S3 Vectors client."""
    s3_vectors = Mock(spec=S3VectorsClient)
    s3_vectors.delete_index = Mock(return_value=True)
    return s3_vectors


@pytest.fixture
def mock_bedrock_client():
    """Create a mock Bedrock client."""
    return Mock(spec=BedrockClient)


@pytest.fixture
def mock_metadata_store():
    """Create a mock metadata store."""
    store = Mock(spec=IndexMetadataStore)
    return store


@pytest.fixture
def mock_embedding_job_store():
    """Create a mock embedding job store."""
    job_store = Mock(spec=EmbeddingJobStore)
    job_store.delete_jobs_by_index = Mock(return_value=3)  # Returns count of deleted jobs
    return job_store


@pytest.fixture
def sample_index():
    """Create a sample index for testing."""
    index = Index.create("Test Index")
    index.s3_vectors_collection_id = "test-collection-id"
    index.video_count = 5
    return index


@pytest.mark.asyncio
class TestIndexDeletionCleanup:
    """Test comprehensive index deletion with S3 cleanup."""
    
    async def test_delete_index_cleans_up_all_assets(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_vectors_client,
        mock_metadata_store,
        mock_embedding_job_store,
        mock_s3_client,
        sample_index
    ):
        """Test that deleting an index cleans up all related assets."""
        # Set up metadata store to return the sample index
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        mock_metadata_store.delete_index = Mock()
        
        # Set up job store to return jobs with output locations
        from services.embedding_job_store import Job
        from datetime import datetime
        
        mock_jobs = [
            Job(
                job_id="job1",
                invocation_arn="arn1",
                video_id="video1",
                index_id=sample_index.id,
                s3_uri="s3://bucket/videos/video1.mp4",
                status="completed",
                output_location="s3://test-bucket/embeddings/folder1/output.json",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            ),
            Job(
                job_id="job2",
                invocation_arn="arn2",
                video_id="video2",
                index_id=sample_index.id,
                s3_uri="s3://bucket/videos/video2.mp4",
                status="completed",
                output_location="s3://test-bucket/embeddings/folder2/output.json",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        ]
        mock_embedding_job_store.get_all_jobs = Mock(return_value=mock_jobs)
        
        # Create index manager
        index_manager = IndexManager(
            bedrock_client=mock_bedrock_client,
            s3_vectors_client=mock_s3_vectors_client,
            config=mock_config,
            metadata_store=mock_metadata_store,
            embedding_job_store=mock_embedding_job_store
        )
        
        # Delete the index with s3_client
        result = await index_manager.delete_index(sample_index.id, s3_client=mock_s3_client)
        
        # Verify result
        assert result is True
        
        # Verify S3 video files were deleted
        # delete_prefix is called for: videos, thumbnails, and 2 embedding folders
        assert mock_s3_client.delete_prefix.call_count == 4
        
        # Check video prefix
        video_prefix_call = mock_s3_client.delete_prefix.call_args_list[0]
        assert video_prefix_call[0][0] == f"videos/{sample_index.id}/"
        
        # Check thumbnail prefix
        thumbnail_prefix_call = mock_s3_client.delete_prefix.call_args_list[1]
        assert thumbnail_prefix_call[0][0] == f"thumbnails/{sample_index.id}/"
        
        # Check embedding folder prefixes
        embedding_prefix_calls = [
            call[0][0] for call in mock_s3_client.delete_prefix.call_args_list[2:]
        ]
        assert "embeddings/folder1/" in embedding_prefix_calls
        assert "embeddings/folder2/" in embedding_prefix_calls
        
        # Verify embedding jobs were deleted
        mock_embedding_job_store.delete_jobs_by_index.assert_called_once_with(sample_index.id)
        
        # Verify S3 Vectors index was deleted
        mock_s3_vectors_client.delete_index.assert_called_once_with(
            sample_index.s3_vectors_collection_id
        )
        
        # Verify metadata was deleted
        mock_metadata_store.delete_index.assert_called_once_with(sample_index.id)
    
    async def test_delete_index_without_s3_client(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_vectors_client,
        mock_metadata_store,
        mock_embedding_job_store,
        sample_index
    ):
        """Test that deleting an index without s3_client still works but skips S3 cleanup."""
        # Set up metadata store
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        mock_metadata_store.delete_index = Mock()
        
        # Create index manager
        index_manager = IndexManager(
            bedrock_client=mock_bedrock_client,
            s3_vectors_client=mock_s3_vectors_client,
            config=mock_config,
            metadata_store=mock_metadata_store,
            embedding_job_store=mock_embedding_job_store
        )
        
        # Delete the index without s3_client
        result = await index_manager.delete_index(sample_index.id, s3_client=None)
        
        # Verify result
        assert result is True
        
        # Verify embedding jobs were still deleted
        mock_embedding_job_store.delete_jobs_by_index.assert_called_once_with(sample_index.id)
        
        # Verify S3 Vectors index was deleted
        mock_s3_vectors_client.delete_index.assert_called_once_with(
            sample_index.s3_vectors_collection_id
        )
        
        # Verify metadata was deleted
        mock_metadata_store.delete_index.assert_called_once_with(sample_index.id)
    
    async def test_delete_index_handles_s3_cleanup_errors(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_vectors_client,
        mock_metadata_store,
        mock_embedding_job_store,
        mock_s3_client,
        sample_index
    ):
        """Test that S3 cleanup errors don't prevent metadata deletion."""
        # Set up metadata store
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        mock_metadata_store.delete_index = Mock()
        
        # Make S3 delete_prefix raise an error
        mock_s3_client.delete_prefix = Mock(side_effect=Exception("S3 error"))
        
        # Create index manager
        index_manager = IndexManager(
            bedrock_client=mock_bedrock_client,
            s3_vectors_client=mock_s3_vectors_client,
            config=mock_config,
            metadata_store=mock_metadata_store,
            embedding_job_store=mock_embedding_job_store
        )
        
        # Delete the index - should succeed despite S3 errors
        result = await index_manager.delete_index(sample_index.id, s3_client=mock_s3_client)
        
        # Verify result is still True
        assert result is True
        
        # Verify metadata was still deleted
        mock_metadata_store.delete_index.assert_called_once_with(sample_index.id)
    
    async def test_delete_index_handles_job_store_errors(
        self,
        mock_config,
        mock_bedrock_client,
        mock_s3_vectors_client,
        mock_metadata_store,
        mock_embedding_job_store,
        mock_s3_client,
        sample_index
    ):
        """Test that job store errors don't prevent metadata deletion."""
        # Set up metadata store
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        mock_metadata_store.delete_index = Mock()
        
        # Make job store raise an error
        mock_embedding_job_store.delete_jobs_by_index = Mock(
            side_effect=Exception("Job store error")
        )
        
        # Create index manager
        index_manager = IndexManager(
            bedrock_client=mock_bedrock_client,
            s3_vectors_client=mock_s3_vectors_client,
            config=mock_config,
            metadata_store=mock_metadata_store,
            embedding_job_store=mock_embedding_job_store
        )
        
        # Delete the index - should succeed despite job store error
        result = await index_manager.delete_index(sample_index.id, s3_client=mock_s3_client)
        
        # Verify result is still True
        assert result is True
        
        # Verify metadata was still deleted
        mock_metadata_store.delete_index.assert_called_once_with(sample_index.id)


class TestS3ClientDeletePrefix:
    """Test S3Client delete_prefix method."""
    
    @patch("aws.s3_client.boto3.client")
    def test_delete_prefix_single_page(self, mock_boto_client, mock_config):
        """Test deleting objects with a single page of results."""
        # Set up mock S3 client
        mock_client_instance = Mock()
        mock_boto_client.return_value = mock_client_instance
        
        # Mock paginator
        mock_paginator = Mock()
        mock_client_instance.get_paginator.return_value = mock_paginator
        
        # Mock single page of results
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {'Key': 'videos/index-123/video-1/file.mp4'},
                    {'Key': 'videos/index-123/video-2/file.mp4'},
                ]
            }
        ]
        
        # Mock delete_objects response
        mock_client_instance.delete_objects.return_value = {
            'Deleted': [
                {'Key': 'videos/index-123/video-1/file.mp4'},
                {'Key': 'videos/index-123/video-2/file.mp4'},
            ]
        }
        
        # Create S3 client and delete prefix
        s3_client = S3Client(mock_config)
        count = s3_client.delete_prefix("videos/index-123/")
        
        # Verify
        assert count == 2
        mock_client_instance.delete_objects.assert_called_once()
    
    @patch("aws.s3_client.boto3.client")
    def test_delete_prefix_empty_results(self, mock_boto_client, mock_config):
        """Test deleting objects when no objects match the prefix."""
        # Set up mock S3 client
        mock_client_instance = Mock()
        mock_boto_client.return_value = mock_client_instance
        
        # Mock paginator with empty results
        mock_paginator = Mock()
        mock_client_instance.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]  # No 'Contents' key
        
        # Create S3 client and delete prefix
        s3_client = S3Client(mock_config)
        count = s3_client.delete_prefix("videos/nonexistent/")
        
        # Verify
        assert count == 0
        mock_client_instance.delete_objects.assert_not_called()


class TestEmbeddingJobStoreDeleteByIndex:
    """Test EmbeddingJobStore delete_jobs_by_index method."""
    
    def test_delete_jobs_by_index(self, tmp_path):
        """Test deleting all jobs for a specific index."""
        # Create job store with temp file
        store_path = tmp_path / "jobs.json"
        job_store = EmbeddingJobStore(store_path=str(store_path))
        
        # Add jobs for different indexes
        job_id_1 = job_store.add_job("arn1", "video1", "index-123", "s3://bucket/video1")
        job_id_2 = job_store.add_job("arn2", "video2", "index-123", "s3://bucket/video2")
        job_id_3 = job_store.add_job("arn3", "video3", "index-456", "s3://bucket/video3")
        
        # Delete jobs for index-123
        deleted_count = job_store.delete_jobs_by_index("index-123")
        
        # Verify
        assert deleted_count == 2
        
        # Verify jobs are deleted
        assert job_store.get_job(job_id_1) is None
        assert job_store.get_job(job_id_2) is None
        
        # Verify job for other index still exists
        assert job_store.get_job(job_id_3) is not None
    
    def test_delete_jobs_by_index_nonexistent(self, tmp_path):
        """Test deleting jobs for a nonexistent index."""
        # Create job store with temp file
        store_path = tmp_path / "jobs.json"
        job_store = EmbeddingJobStore(store_path=str(store_path))
        
        # Add a job
        job_store.add_job("arn1", "video1", "index-123", "s3://bucket/video1")
        
        # Delete jobs for nonexistent index
        deleted_count = job_store.delete_jobs_by_index("nonexistent")
        
        # Verify
        assert deleted_count == 0
