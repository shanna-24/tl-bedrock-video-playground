"""Unit tests for S3 Vectors client wrapper.

Tests the S3VectorsClient class methods for creating indexes, storing embeddings,
and performing similarity searches.
Validates: Requirements 7.2, 7.5
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from aws.s3_vectors_client import S3VectorsClient
from config import Config
from exceptions import AWSServiceError


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=Config)
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-vector-bucket"
    config.use_localstack = False
    return config


@pytest.fixture
def mock_config_localstack():
    """Create a mock configuration with LocalStack enabled."""
    config = Mock(spec=Config)
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-vector-bucket"
    config.use_localstack = True
    return config


class TestS3VectorsClientInitialization:
    """Test suite for S3VectorsClient initialization."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_init_without_localstack(self, mock_boto_client, mock_config):
        """Test initialization without LocalStack."""
        client = S3VectorsClient(mock_config)
        
        assert client.config == mock_config
        assert client.vector_bucket_name == "test-vector-bucket"
        mock_boto_client.assert_called_once_with(
            "s3vectors",
            region_name="us-east-1"
        )
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_init_with_localstack(self, mock_boto_client, mock_config_localstack):
        """Test initialization with LocalStack."""
        client = S3VectorsClient(mock_config_localstack)
        
        assert client.config == mock_config_localstack
        assert client.vector_bucket_name == "test-vector-bucket"
        mock_boto_client.assert_called_once_with(
            "s3vectors",
            region_name="us-east-1",
            endpoint_url="http://localhost:4566"
        )


class TestCreateIndex:
    """Test suite for creating vector indexes."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_create_index_success(self, mock_boto_client, mock_config):
        """Test successful index creation."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "indexArn": "arn:aws:s3vectors:us-east-1:123456789012:index/test-index"
        }
        mock_client_instance.create_vector_index.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        index_arn = client.create_index(
            index_name="test-index",
            dimension=1024,
            distance_metric="cosine"
        )
        
        assert index_arn == "arn:aws:s3vectors:us-east-1:123456789012:index/test-index"
        mock_client_instance.create_vector_index.assert_called_once_with(
            vectorBucketName="test-vector-bucket",
            indexName="test-index",
            dimension=1024,
            distanceMetric="Cosine"
        )
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_create_index_with_non_filterable_keys(self, mock_boto_client, mock_config):
        """Test index creation with non-filterable metadata keys."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "indexArn": "arn:aws:s3vectors:us-east-1:123456789012:index/test-index"
        }
        mock_client_instance.create_vector_index.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        index_arn = client.create_index(
            index_name="test-index",
            dimension=512,
            distance_metric="euclidean",
            non_filterable_metadata_keys=["source_text", "raw_data"]
        )
        
        assert index_arn == "arn:aws:s3vectors:us-east-1:123456789012:index/test-index"
        
        call_args = mock_client_instance.create_vector_index.call_args
        assert call_args[1]["nonFilterableMetadataKeys"] == ["source_text", "raw_data"]
        assert call_args[1]["distanceMetric"] == "Euclidean"
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_create_index_invalid_name_length(self, mock_boto_client, mock_config):
        """Test index creation with invalid name length."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config)
        
        # Name too short
        with pytest.raises(AWSServiceError) as exc_info:
            client.create_index(index_name="ab", dimension=1024)
        assert "3-63 characters" in str(exc_info.value)
        
        # Name too long
        with pytest.raises(AWSServiceError) as exc_info:
            client.create_index(index_name="a" * 64, dimension=1024)
        assert "3-63 characters" in str(exc_info.value)
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_create_index_invalid_dimension(self, mock_boto_client, mock_config):
        """Test index creation with invalid dimension."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config)
        
        # Dimension too small
        with pytest.raises(AWSServiceError) as exc_info:
            client.create_index(index_name="test-index", dimension=0)
        assert "between 1 and 4096" in str(exc_info.value)
        
        # Dimension too large
        with pytest.raises(AWSServiceError) as exc_info:
            client.create_index(index_name="test-index", dimension=5000)
        assert "between 1 and 4096" in str(exc_info.value)
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_create_index_invalid_distance_metric(self, mock_boto_client, mock_config):
        """Test index creation with invalid distance metric."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.create_index(
                index_name="test-index",
                dimension=1024,
                distance_metric="manhattan"
            )
        assert "cosine" in str(exc_info.value).lower()
        assert "euclidean" in str(exc_info.value).lower()
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_create_index_client_error(self, mock_boto_client, mock_config):
        """Test handling of ClientError during index creation."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "IndexAlreadyExists",
                "Message": "Index already exists"
            }
        }
        mock_client_instance.create_vector_index.side_effect = ClientError(
            error_response, "CreateVectorIndex"
        )
        
        client = S3VectorsClient(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.create_index(index_name="test-index", dimension=1024)
        
        assert "Failed to create vector index" in str(exc_info.value)
        assert "Index already exists" in str(exc_info.value)



class TestDeleteIndex:
    """Test suite for deleting vector indexes."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_delete_index_success(self, mock_boto_client, mock_config):
        """Test successful index deletion."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config)
        result = client.delete_index(index_name="test-index")
        
        assert result is True
        mock_client_instance.delete_vector_index.assert_called_once_with(
            vectorBucketName="test-vector-bucket",
            indexName="test-index"
        )
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_delete_index_client_error(self, mock_boto_client, mock_config):
        """Test handling of ClientError during index deletion."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "NoSuchVectorIndex",
                "Message": "Index not found"
            }
        }
        mock_client_instance.delete_vector_index.side_effect = ClientError(
            error_response, "DeleteVectorIndex"
        )
        
        client = S3VectorsClient(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.delete_index(index_name="nonexistent-index")
        
        assert "Failed to delete vector index" in str(exc_info.value)
        assert "Index not found" in str(exc_info.value)


class TestListIndexes:
    """Test suite for listing vector indexes."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_list_indexes_success(self, mock_boto_client, mock_config):
        """Test successful index listing."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "indexes": [
                {
                    "indexName": "index-1",
                    "indexArn": "arn:aws:s3vectors:us-east-1:123456789012:index/index-1",
                    "dimension": 1024,
                    "distanceMetric": "Cosine"
                },
                {
                    "indexName": "index-2",
                    "indexArn": "arn:aws:s3vectors:us-east-1:123456789012:index/index-2",
                    "dimension": 512,
                    "distanceMetric": "Euclidean"
                }
            ]
        }
        mock_client_instance.list_vector_indexes.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        indexes = client.list_indexes()
        
        assert len(indexes) == 2
        assert indexes[0]["indexName"] == "index-1"
        assert indexes[1]["indexName"] == "index-2"
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_list_indexes_empty(self, mock_boto_client, mock_config):
        """Test listing when no indexes exist."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {"indexes": []}
        mock_client_instance.list_vector_indexes.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        indexes = client.list_indexes()
        
        assert len(indexes) == 0



class TestGetIndex:
    """Test suite for getting vector index information."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_get_index_success(self, mock_boto_client, mock_config):
        """Test successful index info retrieval."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "indexName": "test-index",
            "indexArn": "arn:aws:s3vectors:us-east-1:123456789012:index/test-index",
            "dimension": 1024,
            "distanceMetric": "Cosine",
            "nonFilterableMetadataKeys": ["source_text"]
        }
        mock_client_instance.describe_vector_index.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        index_info = client.get_index(index_name="test-index")
        
        assert index_info["indexName"] == "test-index"
        assert index_info["dimension"] == 1024
        assert index_info["distanceMetric"] == "Cosine"
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_get_index_not_found(self, mock_boto_client, mock_config):
        """Test getting info for non-existent index."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "NoSuchVectorIndex",
                "Message": "Index not found"
            }
        }
        mock_client_instance.describe_vector_index.side_effect = ClientError(
            error_response, "DescribeVectorIndex"
        )
        
        client = S3VectorsClient(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.get_index(index_name="nonexistent-index")
        
        assert "Vector index not found" in str(exc_info.value)


class TestPutVectors:
    """Test suite for storing vectors."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_put_vectors_success(self, mock_boto_client, mock_config):
        """Test successful vector storage."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "successCount": 3,
            "failureCount": 0
        }
        mock_client_instance.put_vectors.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        
        vectors = [
            {
                "key": "vector-1",
                "data": {"float32": [0.1, 0.2, 0.3]},
                "metadata": {"type": "test"}
            },
            {
                "key": "vector-2",
                "data": {"float32": [0.4, 0.5, 0.6]},
                "metadata": {"type": "test"}
            },
            {
                "key": "vector-3",
                "data": {"float32": [0.7, 0.8, 0.9]},
                "metadata": {"type": "test"}
            }
        ]
        
        result = client.put_vectors(index_name="test-index", vectors=vectors)
        
        assert result["successCount"] == 3
        assert result["failureCount"] == 0
        
        mock_client_instance.put_vectors.assert_called_once_with(
            vectorBucketName="test-vector-bucket",
            indexName="test-index",
            vectors=vectors
        )
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_put_vectors_idempotent_localstack(self, mock_boto_client, mock_config_localstack):
        """Test that storing same vectors twice is idempotent in LocalStack."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config_localstack)
        
        # Create index first
        client.create_index(index_name="test-index", dimension=3)
        
        # Store vectors first time
        vectors = [
            {
                "key": "vector-1",
                "data": {"float32": [0.1, 0.2, 0.3]},
                "metadata": {"type": "test", "version": "1"}
            },
            {
                "key": "vector-2",
                "data": {"float32": [0.4, 0.5, 0.6]},
                "metadata": {"type": "test", "version": "1"}
            }
        ]
        
        result1 = client.put_vectors(index_name="test-index", vectors=vectors)
        assert result1["successCount"] == 2
        assert result1["failureCount"] == 0
        
        # Verify vectors are stored
        assert len(client._mock_vectors["test-index"]) == 2
        
        # Store same vectors again (should replace, not duplicate)
        vectors_updated = [
            {
                "key": "vector-1",
                "data": {"float32": [0.9, 0.8, 0.7]},  # Different data
                "metadata": {"type": "test", "version": "2"}  # Different metadata
            },
            {
                "key": "vector-2",
                "data": {"float32": [0.6, 0.5, 0.4]},
                "metadata": {"type": "test", "version": "2"}
            }
        ]
        
        result2 = client.put_vectors(index_name="test-index", vectors=vectors_updated)
        assert result2["successCount"] == 2
        assert result2["failureCount"] == 0
        
        # Verify still only 2 vectors (not 4)
        assert len(client._mock_vectors["test-index"]) == 2
        
        # Verify vectors were updated with new data
        stored_vectors = client._mock_vectors["test-index"]
        vector1 = next(v for v in stored_vectors if v["key"] == "vector-1")
        vector2 = next(v for v in stored_vectors if v["key"] == "vector-2")
        
        assert vector1["data"]["float32"] == [0.9, 0.8, 0.7]
        assert vector1["metadata"]["version"] == "2"
        assert vector2["data"]["float32"] == [0.6, 0.5, 0.4]
        assert vector2["metadata"]["version"] == "2"
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_put_vectors_mixed_new_and_existing_localstack(self, mock_boto_client, mock_config_localstack):
        """Test storing mix of new and existing vectors in LocalStack."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config_localstack)
        
        # Create index
        client.create_index(index_name="test-index", dimension=3)
        
        # Store initial vectors
        initial_vectors = [
            {"key": "vector-1", "data": {"float32": [0.1, 0.2, 0.3]}},
            {"key": "vector-2", "data": {"float32": [0.4, 0.5, 0.6]}}
        ]
        client.put_vectors(index_name="test-index", vectors=initial_vectors)
        
        # Store mix of existing and new vectors
        mixed_vectors = [
            {"key": "vector-1", "data": {"float32": [0.9, 0.8, 0.7]}},  # Existing - should replace
            {"key": "vector-3", "data": {"float32": [0.7, 0.8, 0.9]}}   # New - should add
        ]
        client.put_vectors(index_name="test-index", vectors=mixed_vectors)
        
        # Verify we have 3 vectors total
        assert len(client._mock_vectors["test-index"]) == 3
        
        # Verify vector-1 was updated
        stored_vectors = client._mock_vectors["test-index"]
        vector1 = next(v for v in stored_vectors if v["key"] == "vector-1")
        assert vector1["data"]["float32"] == [0.9, 0.8, 0.7]
        
        # Verify vector-2 is unchanged
        vector2 = next(v for v in stored_vectors if v["key"] == "vector-2")
        assert vector2["data"]["float32"] == [0.4, 0.5, 0.6]
        
        # Verify vector-3 was added
        vector3 = next(v for v in stored_vectors if v["key"] == "vector-3")
        assert vector3["data"]["float32"] == [0.7, 0.8, 0.9]
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_put_vectors_duplicate_prevention_localstack(self, mock_boto_client, mock_config_localstack):
        """Test that duplicate processing doesn't create duplicate vectors."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config_localstack)
        
        # Create index
        client.create_index(index_name="test-index", dimension=3)
        
        vectors = [
            {"key": "video-123:0.00:6.00:0", "data": {"float32": [0.1, 0.2, 0.3]}},
            {"key": "video-123:6.00:12.00:1", "data": {"float32": [0.4, 0.5, 0.6]}}
        ]
        
        # Simulate processing same job 3 times (e.g., retries)
        for _ in range(3):
            result = client.put_vectors(index_name="test-index", vectors=vectors)
            assert result["successCount"] == 2
        
        # Verify only 2 vectors exist (not 6)
        assert len(client._mock_vectors["test-index"]) == 2
        
        # Verify keys are correct
        stored_keys = [v["key"] for v in client._mock_vectors["test-index"]]
        assert "video-123:0.00:6.00:0" in stored_keys
        assert "video-123:6.00:12.00:1" in stored_keys
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_put_vectors_partial_failure(self, mock_boto_client, mock_config):
        """Test vector storage with partial failures."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "successCount": 2,
            "failureCount": 1
        }
        mock_client_instance.put_vectors.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        
        vectors = [
            {"key": "vector-1", "data": {"float32": [0.1, 0.2]}},
            {"key": "vector-2", "data": {"float32": [0.3, 0.4]}},
            {"key": "vector-3", "data": {"float32": [0.5, 0.6]}}
        ]
        
        result = client.put_vectors(index_name="test-index", vectors=vectors)
        
        assert result["successCount"] == 2
        assert result["failureCount"] == 1
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_put_vectors_empty_list(self, mock_boto_client, mock_config):
        """Test storing empty vector list."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.put_vectors(index_name="test-index", vectors=[])
        
        assert "cannot be empty" in str(exc_info.value)
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_put_vectors_client_error(self, mock_boto_client, mock_config):
        """Test handling of ClientError during vector storage."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "ValidationException",
                "Message": "Invalid vector dimension"
            }
        }
        mock_client_instance.put_vectors.side_effect = ClientError(
            error_response, "PutVectors"
        )
        
        client = S3VectorsClient(mock_config)
        
        vectors = [{"key": "vector-1", "data": {"float32": [0.1, 0.2]}}]
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.put_vectors(index_name="test-index", vectors=vectors)
        
        assert "Failed to store vectors" in str(exc_info.value)
        assert "Invalid vector dimension" in str(exc_info.value)


class TestQueryVectors:
    """Test suite for similarity search."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_query_vectors_success(self, mock_boto_client, mock_config):
        """Test successful similarity search."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "vectors": [
                {
                    "key": "vector-1",
                    "distance": 0.1,
                    "metadata": {"type": "test"}
                },
                {
                    "key": "vector-2",
                    "distance": 0.3,
                    "metadata": {"type": "test"}
                }
            ]
        }
        mock_client_instance.query_vectors.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        
        query_vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        results = client.query_vectors(
            index_name="test-index",
            query_vector=query_vector,
            top_k=2
        )
        
        assert len(results) == 2
        assert results[0]["key"] == "vector-1"
        assert results[0]["distance"] == 0.1
        assert results[1]["key"] == "vector-2"
        
        mock_client_instance.query_vectors.assert_called_once()
        call_args = mock_client_instance.query_vectors.call_args
        assert call_args[1]["queryVector"] == {"float32": query_vector}
        assert call_args[1]["topK"] == 2
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_query_vectors_with_metadata_filter(self, mock_boto_client, mock_config):
        """Test similarity search with metadata filter."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "vectors": [
                {
                    "key": "vector-1",
                    "distance": 0.1,
                    "metadata": {"genre": "scifi"}
                }
            ]
        }
        mock_client_instance.query_vectors.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        
        query_vector = [0.1, 0.2, 0.3]
        results = client.query_vectors(
            index_name="test-index",
            query_vector=query_vector,
            top_k=5,
            metadata_filter={"genre": "scifi"}
        )
        
        assert len(results) == 1
        assert results[0]["metadata"]["genre"] == "scifi"
        
        call_args = mock_client_instance.query_vectors.call_args
        assert call_args[1]["filter"] == {"genre": "scifi"}
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_query_vectors_without_distance_and_metadata(self, mock_boto_client, mock_config):
        """Test similarity search without returning distance and metadata."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "vectors": [
                {"key": "vector-1"},
                {"key": "vector-2"}
            ]
        }
        mock_client_instance.query_vectors.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        
        query_vector = [0.1, 0.2, 0.3]
        results = client.query_vectors(
            index_name="test-index",
            query_vector=query_vector,
            top_k=2,
            return_distance=False,
            return_metadata=False
        )
        
        assert len(results) == 2
        assert "distance" not in results[0]
        assert "metadata" not in results[0]
        
        call_args = mock_client_instance.query_vectors.call_args
        assert call_args[1]["returnDistance"] is False
        assert call_args[1]["returnMetadata"] is False
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_query_vectors_empty_query(self, mock_boto_client, mock_config):
        """Test querying with empty vector."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.query_vectors(
                index_name="test-index",
                query_vector=[],
                top_k=5
            )
        
        assert "cannot be empty" in str(exc_info.value)
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_query_vectors_invalid_top_k(self, mock_boto_client, mock_config):
        """Test querying with invalid top_k."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.query_vectors(
                index_name="test-index",
                query_vector=[0.1, 0.2],
                top_k=0
            )
        
        assert "at least 1" in str(exc_info.value)



class TestDeleteVectors:
    """Test suite for deleting vectors."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_delete_vectors_success(self, mock_boto_client, mock_config):
        """Test successful vector deletion."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "successCount": 3,
            "failureCount": 0
        }
        mock_client_instance.delete_vectors.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        
        vector_keys = ["vector-1", "vector-2", "vector-3"]
        result = client.delete_vectors(index_name="test-index", vector_keys=vector_keys)
        
        assert result["successCount"] == 3
        assert result["failureCount"] == 0
        
        mock_client_instance.delete_vectors.assert_called_once_with(
            vectorBucketName="test-vector-bucket",
            indexName="test-index",
            keys=vector_keys
        )
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_delete_vectors_empty_list(self, mock_boto_client, mock_config):
        """Test deleting with empty key list."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3VectorsClient(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.delete_vectors(index_name="test-index", vector_keys=[])
        
        assert "cannot be empty" in str(exc_info.value)


class TestListVectors:
    """Test suite for listing vectors."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_list_vectors_success(self, mock_boto_client, mock_config):
        """Test successful vector listing."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "vectors": ["vector-1", "vector-2", "vector-3"],
            "nextToken": None
        }
        mock_client_instance.list_vectors.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        result = client.list_vectors(index_name="test-index")
        
        assert len(result["vectors"]) == 3
        assert result["nextToken"] is None
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_list_vectors_with_pagination(self, mock_boto_client, mock_config):
        """Test vector listing with pagination."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "vectors": ["vector-1", "vector-2"],
            "nextToken": "token-123"
        }
        mock_client_instance.list_vectors.return_value = mock_response
        
        client = S3VectorsClient(mock_config)
        result = client.list_vectors(
            index_name="test-index",
            max_results=2,
            next_token="previous-token"
        )
        
        assert len(result["vectors"]) == 2
        assert result["nextToken"] == "token-123"
        
        call_args = mock_client_instance.list_vectors.call_args
        assert call_args[1]["nextToken"] == "previous-token"
        assert call_args[1]["maxResults"] == 2


class TestErrorHandling:
    """Test suite for AWS error handling (Requirement 7.5)."""
    
    @patch("aws.s3_vectors_client.boto3.client")
    def test_descriptive_error_messages(self, mock_boto_client, mock_config):
        """Test that AWS errors are transformed into descriptive messages."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Test various AWS error codes
        error_cases = [
            ("ValidationException", "Invalid parameters"),
            ("ThrottlingException", "Request rate exceeded"),
            ("NoSuchVectorIndex", "Index not found"),
            ("ServiceUnavailableException", "Service temporarily unavailable"),
        ]
        
        client = S3VectorsClient(mock_config)
        
        for error_code, error_message in error_cases:
            error_response = {
                "Error": {
                    "Code": error_code,
                    "Message": error_message
                }
            }
            mock_client_instance.create_vector_index.side_effect = ClientError(
                error_response, "CreateVectorIndex"
            )
            
            with pytest.raises(AWSServiceError) as exc_info:
                client.create_index(index_name="test-index", dimension=1024)
            
            # Verify the error message is descriptive and includes the AWS message
            assert error_message in str(exc_info.value)
            assert "Failed to create vector index" in str(exc_info.value)
