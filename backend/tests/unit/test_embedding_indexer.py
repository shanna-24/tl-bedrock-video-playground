"""
Unit tests for EmbeddingIndexer.

Tests the indexer's ability to store embeddings in S3 Vectors with proper
metadata, batch processing, error handling, and retry logic.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, MagicMock, patch

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.embedding_indexer import EmbeddingIndexer, ValidationError, StorageError
from services.embedding_retriever import EmbeddingData
from exceptions import AWSServiceError


class TestEmbeddingIndexer:
    """Test suite for EmbeddingIndexer."""
    
    @pytest.fixture
    def mock_s3_vectors_client(self):
        """Create a mock S3VectorsClient."""
        return Mock()
    
    @pytest.fixture
    def indexer(self, mock_s3_vectors_client):
        """Create an EmbeddingIndexer instance with mock client."""
        return EmbeddingIndexer(
            s3_vectors_client=mock_s3_vectors_client,
            batch_size=100,
            max_retries=3,
            retry_delay=1
        )
    
    @pytest.fixture
    def sample_embeddings(self):
        """Create sample embedding data for testing."""
        return [
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual", "audio"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            ),
            EmbeddingData(
                embedding=[0.4, 0.5, 0.6],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=6.0,
                end_sec=12.0
            )
        ]
    
    # Initialization Tests
    
    def test_initialization_with_defaults(self, mock_s3_vectors_client):
        """Test that indexer initializes with default parameters."""
        indexer = EmbeddingIndexer(s3_vectors_client=mock_s3_vectors_client)
        
        assert indexer.s3_vectors == mock_s3_vectors_client
        assert indexer.batch_size == 100
        assert indexer.max_retries == 3
        assert indexer.retry_delay == 1
    
    def test_initialization_with_custom_params(self, mock_s3_vectors_client):
        """Test that indexer initializes with custom parameters."""
        indexer = EmbeddingIndexer(
            s3_vectors_client=mock_s3_vectors_client,
            batch_size=50,
            max_retries=5,
            retry_delay=2
        )
        
        assert indexer.batch_size == 50
        assert indexer.max_retries == 5
        assert indexer.retry_delay == 2
    
    # S3 Key Extraction Tests
    
    def test_extract_s3_key_valid_uri(self, indexer):
        """Test extracting S3 key from valid URI."""
        s3_uri = "s3://my-bucket/videos/index-123/video-456/file.mp4"
        
        key = indexer._extract_s3_key(s3_uri)
        
        assert key == "videos/index-123/video-456/file.mp4"
    
    def test_extract_s3_key_nested_path(self, indexer):
        """Test extracting S3 key with deeply nested path."""
        s3_uri = "s3://bucket/a/b/c/d/e/file.mp4"
        
        key = indexer._extract_s3_key(s3_uri)
        
        assert key == "a/b/c/d/e/file.mp4"
    
    def test_extract_s3_key_invalid_prefix(self, indexer):
        """Test that invalid URI prefix raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid S3 URI format"):
            indexer._extract_s3_key("http://bucket/key")
    
    def test_extract_s3_key_missing_key(self, indexer):
        """Test that URI without key raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid S3 URI format"):
            indexer._extract_s3_key("s3://bucket")
    
    # Embedding Formatting Tests
    
    def test_format_embeddings_for_storage(self, indexer, sample_embeddings):
        """Test formatting embeddings for S3 Vectors storage."""
        video_id = "video-123"
        s3_key = "videos/index-1/video-123/file.mp4"
        
        vectors = indexer._format_embeddings_for_storage(
            embeddings=sample_embeddings,
            video_id=video_id,
            s3_key=s3_key
        )
        
        assert len(vectors) == 2
        
        # Check first vector
        assert vectors[0]["key"] == "video-123:0.00:6.00:0"
        assert vectors[0]["data"]["float32"] == [0.1, 0.2, 0.3]
        assert vectors[0]["metadata"]["video_id"] == "video-123"
        assert vectors[0]["metadata"]["start_timecode"] == "0.0"
        assert vectors[0]["metadata"]["end_timecode"] == "6.0"
        assert vectors[0]["metadata"]["s3_key"] == s3_key
        assert vectors[0]["metadata"]["embedding_option"] == "visual,audio"
        assert vectors[0]["metadata"]["embedding_scope"] == "clip"
        
        # Check second vector
        assert vectors[1]["key"] == "video-123:6.00:12.00:1"
        assert vectors[1]["data"]["float32"] == [0.4, 0.5, 0.6]
        assert vectors[1]["metadata"]["start_timecode"] == "6.0"
        assert vectors[1]["metadata"]["end_timecode"] == "12.0"
    
    def test_format_embeddings_unique_keys(self, indexer):
        """Test that embeddings with same timecodes get unique keys."""
        embeddings = [
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            ),
            EmbeddingData(
                embedding=[0.4, 0.5, 0.6],
                embedding_option=["audio"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ]
        
        vectors = indexer._format_embeddings_for_storage(
            embeddings=embeddings,
            video_id="video-123",
            s3_key="key"
        )
        
        # Keys should be different due to index suffix
        assert vectors[0]["key"] == "video-123:0.00:6.00:0"
        assert vectors[1]["key"] == "video-123:0.00:6.00:1"
    
    def test_format_embeddings_with_multiple_options(self, indexer):
        """Test formatting embeddings with multiple embedding options."""
        embeddings = [
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual", "audio", "transcription"],
                embedding_scope="asset",
                start_sec=10.5,
                end_sec=20.5
            )
        ]
        
        vectors = indexer._format_embeddings_for_storage(
            embeddings=embeddings,
            video_id="video-123",
            s3_key="key"
        )
        
        assert vectors[0]["metadata"]["embedding_option"] == "visual,audio,transcription"
        assert vectors[0]["metadata"]["embedding_scope"] == "asset"
    
    # Batch Storage Tests
    
    def test_store_in_batches_single_batch(self, indexer, mock_s3_vectors_client):
        """Test storing embeddings in a single batch."""
        vectors = [{"key": f"key-{i}", "data": {"float32": [0.1, 0.2, 0.3]}} for i in range(50)]
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 50,
            "failureCount": 0
        }
        
        stats = indexer._store_in_batches(vectors=vectors, index_id="index-123")
        
        assert stats["total"] == 50
        assert stats["stored"] == 50
        assert stats["failed"] == 0
        assert stats["batches"] == 1
        mock_s3_vectors_client.put_vectors.assert_called_once()
    
    def test_store_in_batches_multiple_batches(self, indexer, mock_s3_vectors_client):
        """Test storing embeddings in multiple batches."""
        # Create 250 vectors (should be 3 batches with batch_size=100)
        vectors = [{"key": f"key-{i}", "data": {"float32": [0.1, 0.2, 0.3]}} for i in range(250)]
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 100,
            "failureCount": 0
        }
        
        stats = indexer._store_in_batches(vectors=vectors, index_id="index-123")
        
        assert stats["total"] == 250
        assert stats["stored"] == 300  # 3 batches * 100 success each
        assert stats["failed"] == 0
        assert stats["batches"] == 3
        assert mock_s3_vectors_client.put_vectors.call_count == 3
    
    def test_store_in_batches_with_failures(self, indexer, mock_s3_vectors_client):
        """Test storing embeddings with some failures."""
        vectors = [{"key": f"key-{i}", "data": {"float32": [0.1, 0.2, 0.3]}} for i in range(100)]
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 95,
            "failureCount": 5
        }
        
        stats = indexer._store_in_batches(vectors=vectors, index_id="index-123")
        
        assert stats["total"] == 100
        assert stats["stored"] == 95
        assert stats["failed"] == 5
        assert stats["batches"] == 1
    
    def test_store_in_batches_normalizes_index_name(self, indexer, mock_s3_vectors_client):
        """Test that index name is normalized for S3 Vectors."""
        vectors = [{"key": "key-1", "data": {"float32": [0.1, 0.2, 0.3]}}]
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 1,
            "failureCount": 0
        }
        
        indexer._store_in_batches(vectors=vectors, index_id="INDEX-ABC-123")
        
        # Should be called with lowercase normalized name
        mock_s3_vectors_client.put_vectors.assert_called_once()
        call_args = mock_s3_vectors_client.put_vectors.call_args
        assert call_args[1]["index_name"] == "index-index-abc-123"
    
    # Retry Logic Tests
    
    def test_store_batch_with_retry_success_first_attempt(self, indexer, mock_s3_vectors_client):
        """Test successful storage on first attempt."""
        vectors = [{"key": "key-1", "data": {"float32": [0.1, 0.2, 0.3]}}]
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 1,
            "failureCount": 0
        }
        
        result = indexer._store_batch_with_retry(
            vectors=vectors,
            index_name="index-123",
            batch_num=1
        )
        
        assert result["successCount"] == 1
        assert result["failureCount"] == 0
        assert mock_s3_vectors_client.put_vectors.call_count == 1
    
    @patch('time.sleep')
    def test_store_batch_with_retry_success_after_retry(
        self, mock_sleep, indexer, mock_s3_vectors_client
    ):
        """Test successful storage after retry."""
        vectors = [{"key": "key-1", "data": {"float32": [0.1, 0.2, 0.3]}}]
        
        # Fail first attempt, succeed on second
        mock_s3_vectors_client.put_vectors.side_effect = [
            Exception("Temporary error"),
            {"successCount": 1, "failureCount": 0}
        ]
        
        result = indexer._store_batch_with_retry(
            vectors=vectors,
            index_name="index-123",
            batch_num=1
        )
        
        assert result["successCount"] == 1
        assert result["failureCount"] == 0
        assert mock_s3_vectors_client.put_vectors.call_count == 2
        # Check that sleep was called with exponential backoff + jitter (1s base + up to 20% jitter)
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 1.0 <= delay <= 1.2  # 1 * 2^0 + jitter
    
    @patch('time.sleep')
    def test_store_batch_with_retry_exponential_backoff(
        self, mock_sleep, indexer, mock_s3_vectors_client
    ):
        """Test exponential backoff on retries."""
        vectors = [{"key": "key-1", "data": {"float32": [0.1, 0.2, 0.3]}}]
        
        # Fail twice, succeed on third
        mock_s3_vectors_client.put_vectors.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            {"successCount": 1, "failureCount": 0}
        ]
        
        result = indexer._store_batch_with_retry(
            vectors=vectors,
            index_name="index-123",
            batch_num=1
        )
        
        assert result["successCount"] == 1
        assert mock_s3_vectors_client.put_vectors.call_count == 3
        
        # Check exponential backoff with jitter
        assert mock_sleep.call_count == 2
        
        # First retry: 1 * 2^0 = 1s (+ up to 20% jitter)
        delay1 = mock_sleep.call_args_list[0][0][0]
        assert 1.0 <= delay1 <= 1.2
        
        # Second retry: 1 * 2^1 = 2s (+ up to 20% jitter)
        delay2 = mock_sleep.call_args_list[1][0][0]
        assert 2.0 <= delay2 <= 2.4
    
    @patch('time.sleep')
    def test_store_batch_with_retry_max_retries_exceeded(
        self, mock_sleep, indexer, mock_s3_vectors_client
    ):
        """Test that max retries are respected."""
        vectors = [{"key": "key-1", "data": {"float32": [0.1, 0.2, 0.3]}}]
        
        # Always fail
        mock_s3_vectors_client.put_vectors.side_effect = Exception("Persistent error")
        
        result = indexer._store_batch_with_retry(
            vectors=vectors,
            index_name="index-123",
            batch_num=1
        )
        
        assert result["successCount"] == 0
        assert result["failureCount"] == 1
        assert mock_s3_vectors_client.put_vectors.call_count == 3  # max_retries
    
    # Enhanced Error Handling Tests
    
    def test_is_retryable_error_throttling(self, indexer):
        """Test that throttling errors are identified as retryable."""
        assert indexer._is_retryable_error('ThrottlingException') is True
        assert indexer._is_retryable_error('Throttling') is True
        assert indexer._is_retryable_error('TooManyRequestsException') is True
    
    def test_is_retryable_error_service_errors(self, indexer):
        """Test that service errors are identified as retryable."""
        assert indexer._is_retryable_error('ServiceUnavailable') is True
        assert indexer._is_retryable_error('InternalError') is True
        assert indexer._is_retryable_error('InternalServerError') is True
    
    def test_is_retryable_error_timeout(self, indexer):
        """Test that timeout errors are identified as retryable."""
        assert indexer._is_retryable_error('RequestTimeout') is True
        assert indexer._is_retryable_error('RequestTimeoutException') is True
    
    def test_is_retryable_error_non_retryable(self, indexer):
        """Test that non-retryable errors are identified correctly."""
        assert indexer._is_retryable_error('AccessDenied') is False
        assert indexer._is_retryable_error('InvalidParameter') is False
        assert indexer._is_retryable_error('ResourceNotFound') is False
    
    def test_calculate_backoff_delay_exponential(self, indexer):
        """Test that backoff delay increases exponentially."""
        # First attempt (attempt=0): 1 * 2^0 = 1s (+ jitter)
        delay0 = indexer._calculate_backoff_delay(0)
        assert 1.0 <= delay0 <= 1.2  # 1s + up to 20% jitter
        
        # Second attempt (attempt=1): 1 * 2^1 = 2s (+ jitter)
        delay1 = indexer._calculate_backoff_delay(1)
        assert 2.0 <= delay1 <= 2.4  # 2s + up to 20% jitter
        
        # Third attempt (attempt=2): 1 * 2^2 = 4s (+ jitter)
        delay2 = indexer._calculate_backoff_delay(2)
        assert 4.0 <= delay2 <= 4.8  # 4s + up to 20% jitter
    
    @patch('time.sleep')
    def test_store_batch_with_retry_client_error_retryable(
        self, mock_sleep, indexer, mock_s3_vectors_client
    ):
        """Test retry behavior with retryable ClientError."""
        from botocore.exceptions import ClientError
        
        vectors = [{"key": "key-1", "data": {"float32": [0.1, 0.2, 0.3]}}]
        
        # Fail with throttling error, then succeed
        error_response = {'Error': {'Code': 'ThrottlingException', 'Message': 'Rate exceeded'}}
        mock_s3_vectors_client.put_vectors.side_effect = [
            ClientError(error_response, 'PutVectors'),
            {"successCount": 1, "failureCount": 0}
        ]
        
        result = indexer._store_batch_with_retry(
            vectors=vectors,
            index_name="index-123",
            batch_num=1
        )
        
        assert result["successCount"] == 1
        assert result["failureCount"] == 0
        assert mock_s3_vectors_client.put_vectors.call_count == 2
        assert mock_sleep.call_count == 1
    
    @patch('time.sleep')
    def test_store_batch_with_retry_client_error_non_retryable(
        self, mock_sleep, indexer, mock_s3_vectors_client
    ):
        """Test that non-retryable ClientError doesn't retry."""
        from botocore.exceptions import ClientError
        
        vectors = [{"key": "key-1", "data": {"float32": [0.1, 0.2, 0.3]}}]
        
        # Fail with non-retryable error
        error_response = {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}}
        mock_s3_vectors_client.put_vectors.side_effect = ClientError(error_response, 'PutVectors')
        
        result = indexer._store_batch_with_retry(
            vectors=vectors,
            index_name="index-123",
            batch_num=1
        )
        
        assert result["successCount"] == 0
        assert result["failureCount"] == 1
        # Should not retry non-retryable errors
        assert mock_s3_vectors_client.put_vectors.call_count == 1
        assert mock_sleep.call_count == 0
    
    @patch('time.sleep')
    def test_store_batch_with_retry_botocore_error(
        self, mock_sleep, indexer, mock_s3_vectors_client
    ):
        """Test retry behavior with BotoCoreError."""
        from botocore.exceptions import BotoCoreError
        
        vectors = [{"key": "key-1", "data": {"float32": [0.1, 0.2, 0.3]}}]
        
        # Fail with BotoCoreError, then succeed
        mock_s3_vectors_client.put_vectors.side_effect = [
            BotoCoreError(),
            {"successCount": 1, "failureCount": 0}
        ]
        
        result = indexer._store_batch_with_retry(
            vectors=vectors,
            index_name="index-123",
            batch_num=1
        )
        
        assert result["successCount"] == 1
        assert result["failureCount"] == 0
        assert mock_s3_vectors_client.put_vectors.call_count == 2
        assert mock_sleep.call_count == 1
    
    @patch('time.sleep')
    def test_store_batch_with_retry_mixed_errors(
        self, mock_sleep, indexer, mock_s3_vectors_client
    ):
        """Test retry behavior with different error types."""
        from botocore.exceptions import ClientError, BotoCoreError
        
        vectors = [{"key": "key-1", "data": {"float32": [0.1, 0.2, 0.3]}}]
        
        # Fail with different errors, then succeed
        error_response = {'Error': {'Code': 'ServiceUnavailable', 'Message': 'Service unavailable'}}
        mock_s3_vectors_client.put_vectors.side_effect = [
            ClientError(error_response, 'PutVectors'),
            BotoCoreError(),
            {"successCount": 1, "failureCount": 0}
        ]
        
        result = indexer._store_batch_with_retry(
            vectors=vectors,
            index_name="index-123",
            batch_num=1
        )
        
        assert result["successCount"] == 1
        assert result["failureCount"] == 0
        assert mock_s3_vectors_client.put_vectors.call_count == 3
        assert mock_sleep.call_count == 2
    
    # Store Embeddings Integration Tests
    
    def test_store_embeddings_success(self, indexer, mock_s3_vectors_client, sample_embeddings):
        """Test successful end-to-end embedding storage."""
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 2,
            "failureCount": 0
        }
        
        stats = indexer.store_embeddings(
            embeddings=sample_embeddings,
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/videos/file.mp4"
        )
        
        assert stats["total"] == 2
        assert stats["stored"] == 2
        assert stats["failed"] == 0
        assert stats["batches"] == 1
        
        # Verify put_vectors was called with correct parameters
        mock_s3_vectors_client.put_vectors.assert_called_once()
        call_args = mock_s3_vectors_client.put_vectors.call_args
        assert call_args[1]["index_name"] == "index-index-456"
        assert len(call_args[1]["vectors"]) == 2
    
    def test_store_embeddings_empty_list(self, indexer):
        """Test that empty embeddings list raises ValidationError."""
        with pytest.raises(ValidationError, match="Embeddings list cannot be empty"):
            indexer.store_embeddings(
                embeddings=[],
                video_id="video-123",
                index_id="index-456",
                s3_uri="s3://bucket/file.mp4"
            )
    
    def test_store_embeddings_missing_video_id(self, indexer, sample_embeddings):
        """Test that missing video_id raises ValidationError."""
        with pytest.raises(ValidationError, match="video_id, index_id, and s3_uri are required"):
            indexer.store_embeddings(
                embeddings=sample_embeddings,
                video_id="",
                index_id="index-456",
                s3_uri="s3://bucket/file.mp4"
            )
    
    def test_store_embeddings_missing_index_id(self, indexer, sample_embeddings):
        """Test that missing index_id raises ValidationError."""
        with pytest.raises(ValidationError, match="video_id, index_id, and s3_uri are required"):
            indexer.store_embeddings(
                embeddings=sample_embeddings,
                video_id="video-123",
                index_id="",
                s3_uri="s3://bucket/file.mp4"
            )
    
    def test_store_embeddings_missing_s3_uri(self, indexer, sample_embeddings):
        """Test that missing s3_uri raises ValidationError."""
        with pytest.raises(ValidationError, match="video_id, index_id, and s3_uri are required"):
            indexer.store_embeddings(
                embeddings=sample_embeddings,
                video_id="video-123",
                index_id="index-456",
                s3_uri=""
            )
    
    def test_store_embeddings_large_batch(self, indexer, mock_s3_vectors_client):
        """Test storing large number of embeddings in multiple batches."""
        # Create 250 embeddings
        embeddings = [
            EmbeddingData(
                embedding=[0.1 * i, 0.2 * i, 0.3 * i],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=float(i * 6),
                end_sec=float((i + 1) * 6)
            )
            for i in range(250)
        ]
        
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 100,
            "failureCount": 0
        }
        
        stats = indexer.store_embeddings(
            embeddings=embeddings,
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/videos/file.mp4"
        )
        
        assert stats["total"] == 250
        assert stats["stored"] == 300  # 3 batches * 100 success each
        assert stats["batches"] == 3
        assert mock_s3_vectors_client.put_vectors.call_count == 3
    
    def test_store_embeddings_with_partial_failures(
        self, indexer, mock_s3_vectors_client, sample_embeddings
    ):
        """Test storing embeddings with partial failures."""
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 1,
            "failureCount": 1
        }
        
        stats = indexer.store_embeddings(
            embeddings=sample_embeddings,
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/videos/file.mp4"
        )
        
        assert stats["total"] == 2
        assert stats["stored"] == 1
        assert stats["failed"] == 1
    
    def test_store_embeddings_idempotent(self, indexer, mock_s3_vectors_client, sample_embeddings):
        """Test that storing same embeddings twice is idempotent."""
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 2,
            "failureCount": 0
        }
        
        # Store embeddings twice
        stats1 = indexer.store_embeddings(
            embeddings=sample_embeddings,
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/videos/file.mp4"
        )
        
        stats2 = indexer.store_embeddings(
            embeddings=sample_embeddings,
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/videos/file.mp4"
        )
        
        # Both should succeed with same stats
        assert stats1 == stats2
        assert mock_s3_vectors_client.put_vectors.call_count == 2
        
        # Verify same keys are used (idempotent)
        call1_vectors = mock_s3_vectors_client.put_vectors.call_args_list[0][1]["vectors"]
        call2_vectors = mock_s3_vectors_client.put_vectors.call_args_list[1][1]["vectors"]
        
        assert call1_vectors[0]["key"] == call2_vectors[0]["key"]
        assert call1_vectors[1]["key"] == call2_vectors[1]["key"]
    
    def test_store_embeddings_duplicate_handling(self, indexer, mock_s3_vectors_client):
        """Test that duplicate embeddings with same key overwrite previous ones."""
        # First set of embeddings
        embeddings1 = [
            EmbeddingData(
                embedding=[0.1, 0.2, 0.3],
                embedding_option=["visual"],
                embedding_scope="clip",
                start_sec=0.0,
                end_sec=6.0
            )
        ]
        
        # Second set with same timecodes but different embedding values
        embeddings2 = [
            EmbeddingData(
                embedding=[0.9, 0.8, 0.7],  # Different values
                embedding_option=["audio"],  # Different option
                embedding_scope="clip",
                start_sec=0.0,  # Same timecodes
                end_sec=6.0
            )
        ]
        
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 1,
            "failureCount": 0
        }
        
        # Store first embeddings
        indexer.store_embeddings(
            embeddings=embeddings1,
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/videos/file.mp4"
        )
        
        # Store second embeddings (should use same key)
        indexer.store_embeddings(
            embeddings=embeddings2,
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/videos/file.mp4"
        )
        
        # Verify both calls used the same key
        call1_vectors = mock_s3_vectors_client.put_vectors.call_args_list[0][1]["vectors"]
        call2_vectors = mock_s3_vectors_client.put_vectors.call_args_list[1][1]["vectors"]
        
        assert call1_vectors[0]["key"] == call2_vectors[0]["key"]
        assert call1_vectors[0]["key"] == "video-123:0.00:6.00:0"
        
        # But the data should be different
        assert call1_vectors[0]["data"]["float32"] == [0.1, 0.2, 0.3]
        assert call2_vectors[0]["data"]["float32"] == [0.9, 0.8, 0.7]
        
        # And metadata should be different
        assert call1_vectors[0]["metadata"]["embedding_option"] == "visual"
        assert call2_vectors[0]["metadata"]["embedding_option"] == "audio"
    
    def test_store_embeddings_prevents_duplicate_processing(self, indexer, mock_s3_vectors_client, sample_embeddings):
        """Test that reprocessing same job doesn't create duplicate vectors."""
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 2,
            "failureCount": 0
        }
        
        # Simulate processing the same job twice (e.g., after retry)
        for _ in range(3):
            stats = indexer.store_embeddings(
                embeddings=sample_embeddings,
                video_id="video-123",
                index_id="index-456",
                s3_uri="s3://bucket/videos/file.mp4"
            )
            
            # Each call should succeed
            assert stats["stored"] == 2
            assert stats["failed"] == 0
        
        # Verify all calls used identical keys
        all_calls = mock_s3_vectors_client.put_vectors.call_args_list
        assert len(all_calls) == 3
        
        first_keys = [v["key"] for v in all_calls[0][1]["vectors"]]
        for call in all_calls[1:]:
            call_keys = [v["key"] for v in call[1]["vectors"]]
            assert call_keys == first_keys
    
    def test_store_embeddings_metadata_preserved(
        self, indexer, mock_s3_vectors_client, sample_embeddings
    ):
        """Test that all metadata is preserved in storage."""
        mock_s3_vectors_client.put_vectors.return_value = {
            "successCount": 2,
            "failureCount": 0
        }
        
        indexer.store_embeddings(
            embeddings=sample_embeddings,
            video_id="video-123",
            index_id="index-456",
            s3_uri="s3://bucket/videos/index-456/video-123/file.mp4"
        )
        
        # Get the vectors that were stored
        call_args = mock_s3_vectors_client.put_vectors.call_args
        vectors = call_args[1]["vectors"]
        
        # Check first embedding metadata
        assert vectors[0]["metadata"]["video_id"] == "video-123"
        assert vectors[0]["metadata"]["s3_key"] == "videos/index-456/video-123/file.mp4"
        assert vectors[0]["metadata"]["start_timecode"] == "0.0"
        assert vectors[0]["metadata"]["end_timecode"] == "6.0"
        assert vectors[0]["metadata"]["embedding_option"] == "visual,audio"
        assert vectors[0]["metadata"]["embedding_scope"] == "clip"
        
        # Check second embedding metadata
        assert vectors[1]["metadata"]["start_timecode"] == "6.0"
        assert vectors[1]["metadata"]["end_timecode"] == "12.0"
        assert vectors[1]["metadata"]["embedding_option"] == "visual"
