"""Unit tests for IndexManager service.

Tests the IndexManager class methods for creating, deleting, listing, and
retrieving video indexes.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from aws.bedrock_client import BedrockClient
from aws.s3_vectors_client import S3VectorsClient
from config import Config
from exceptions import ResourceLimitError, ResourceNotFoundError, ValidationError
from models.index import Index
from services.index_manager import IndexManager
from storage.metadata_store import IndexMetadataStore


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=Config)
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-bucket"
    config.s3_vectors_collection = "test-collection"
    config.max_indexes = 3
    config.marengo_model_id = "twelvelabs.marengo-v1"
    config.pegasus_model_id = "twelvelabs.pegasus-v1"
    config.use_localstack = False
    return config


@pytest.fixture
def mock_bedrock_client():
    """Create a mock BedrockClient."""
    return Mock(spec=BedrockClient)


@pytest.fixture
def mock_s3_vectors_client():
    """Create a mock S3VectorsClient."""
    return Mock(spec=S3VectorsClient)


@pytest.fixture
def mock_metadata_store():
    """Create a mock IndexMetadataStore."""
    return Mock(spec=IndexMetadataStore)


@pytest.fixture
def mock_embedding_job_store():
    """Create a mock EmbeddingJobStore."""
    from services.embedding_job_store import EmbeddingJobStore
    store = Mock(spec=EmbeddingJobStore)
    return store


@pytest.fixture
def index_manager(mock_bedrock_client, mock_s3_vectors_client, mock_config, mock_metadata_store, mock_embedding_job_store):
    """Create an IndexManager instance with mocked dependencies."""
    return IndexManager(
        bedrock_client=mock_bedrock_client,
        s3_vectors_client=mock_s3_vectors_client,
        config=mock_config,
        metadata_store=mock_metadata_store,
        embedding_job_store=mock_embedding_job_store
    )


class TestIndexLimitEdgeCase:
    """Tests for index limit enforcement.
    
    **Validates: Requirements 1.2**
    """
    
    @pytest.mark.asyncio
    async def test_create_fourth_index_rejected(
        self, index_manager, mock_metadata_store, mock_s3_vectors_client
    ):
        """Test that creating a 4th index is rejected with ResourceLimitError.
        
        This test verifies that the system enforces the maximum of 3 indexes
        as specified in Requirement 1.2.
        """
        # Setup - create 3 existing indexes
        existing_indexes = [
            Index(
                id=f"index-{i}",
                name=f"Test Index {i}",
                video_count=0,
                s3_vectors_collection_id=f"index-index-{i}",
                metadata={}
            )
            for i in range(1, 4)
        ]
        
        # Mock the metadata store to return 3 existing indexes
        mock_metadata_store.load_indexes = Mock(return_value=existing_indexes)
        
        # Execute and verify - attempt to create a 4th index
        with pytest.raises(ResourceLimitError) as exc_info:
            await index_manager.create_index("Fourth Index")
        
        # Verify the error message is appropriate
        error_message = str(exc_info.value)
        assert "Maximum of 3 indexes allowed" in error_message
        assert "delete an existing index" in error_message.lower()
        
        # Verify that S3 Vectors index creation was never called
        mock_s3_vectors_client.create_index.assert_not_called()
        
        # Verify that the index was not saved to metadata store
        mock_metadata_store.save_index.assert_not_called()
