"""
Embedding Indexer - Stores embeddings in S3 Vectors.

This module provides functionality to store embeddings retrieved from Bedrock
output into S3 Vectors with proper metadata for video search functionality.
"""

import logging
from typing import List, Dict, Any, Optional
import time
from botocore.exceptions import ClientError, BotoCoreError
from aws.s3_vectors_client import S3VectorsClient
from services.embedding_retriever import EmbeddingData

logger = logging.getLogger(__name__)


class EmbeddingIndexerError(Exception):
    """Base exception for EmbeddingIndexer errors."""

    pass


class StorageError(EmbeddingIndexerError):
    """Exception raised when storage operation fails."""

    pass


class ValidationError(EmbeddingIndexerError):
    """Exception raised when input validation fails."""

    pass


class EmbeddingIndexer:
    """
    Stores embeddings in S3 Vectors with metadata.

    This class handles storing embeddings retrieved from Bedrock async jobs
    into S3 Vectors for similarity search. It includes batch processing,
    idempotent storage, and error handling with retries.
    """

    def __init__(
        self,
        s3_vectors_client: S3VectorsClient,
        batch_size: int = 100,
        max_retries: int = 3,
        retry_delay: int = 1,
        enable_batch_optimization: bool = True,
    ):
        """
        Initialize the embedding indexer.

        Args:
            s3_vectors_client: S3VectorsClient instance for vector operations
            batch_size: Number of embeddings to store in each batch (default: 100)
            max_retries: Maximum number of retry attempts for failed operations (default: 3)
            retry_delay: Initial delay in seconds between retries (default: 1)
            enable_batch_optimization: Enable optimized batch storage (default: True)
        """
        self.s3_vectors = s3_vectors_client
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_batch_optimization = enable_batch_optimization
        
        # Performance metrics
        self._metrics = {
            "total_api_calls": 0,
            "total_vectors_stored": 0,
            "total_batches_processed": 0,
            "api_call_time_ms": 0.0,
        }

    def store_embeddings(
        self, embeddings: List[EmbeddingData], video_id: str, index_id: str, s3_uri: str
    ) -> Dict[str, Any]:
        """
        Store embeddings in S3 Vectors with metadata.

        This method:
        1. Formats embeddings with metadata for S3 Vectors
        2. Processes embeddings in batches for efficiency
        3. Handles errors with retry logic
        4. Returns statistics about the storage operation

        The storage is idempotent - storing the same embedding multiple times
        will overwrite the previous version (based on the unique key).

        Args:
            embeddings: List of EmbeddingData objects to store
            video_id: ID of the video these embeddings belong to
            index_id: ID of the index to store embeddings in
            s3_uri: S3 URI of the video file for playback

        Returns:
            Dictionary containing storage statistics:
                - total: Total number of embeddings processed
                - stored: Number of embeddings successfully stored
                - failed: Number of embeddings that failed to store
                - batches: Number of batches processed

        Raises:
            ValidationError: If embeddings list is empty or parameters are invalid
        """
        if not embeddings:
            raise ValidationError("Embeddings list cannot be empty")

        if not video_id or not index_id or not s3_uri:
            raise ValidationError("video_id, index_id, and s3_uri are required")

        logger.info(
            f"Storing {len(embeddings)} embeddings for video {video_id} "
            f"in index {index_id}"
        )

        # Extract S3 key from URI for metadata
        s3_key = self._extract_s3_key(s3_uri)

        # Format embeddings for S3 Vectors
        vectors = self._format_embeddings_for_storage(
            embeddings=embeddings, video_id=video_id, s3_key=s3_key
        )

        # Store embeddings in batches
        stats = self._store_in_batches(vectors=vectors, index_id=index_id)
        
        # Update batch metrics
        self._metrics["total_batches_processed"] += stats["batches"]

        # Calculate performance metrics
        avg_api_time = (
            self._metrics["api_call_time_ms"] / self._metrics["total_api_calls"]
            if self._metrics["total_api_calls"] > 0
            else 0
        )
        
        logger.info(
            f"Stored {stats['stored']}/{stats['total']} embeddings "
            f"in {stats['batches']} batches "
            f"({stats['failed']} failed) | "
            f"avg_api_time={avg_api_time:.2f}ms "
            f"total_api_calls={self._metrics['total_api_calls']}"
        )

        return stats

    def _extract_s3_key(self, s3_uri: str) -> str:
        """
        Extract S3 key from S3 URI.

        Args:
            s3_uri: S3 URI in format s3://bucket/key

        Returns:
            S3 key (path after bucket name)

        Raises:
            ValidationError: If URI format is invalid
        """
        if not s3_uri.startswith("s3://"):
            raise ValidationError(f"Invalid S3 URI format: {s3_uri}")

        # Remove s3:// prefix
        path = s3_uri[5:]

        # Split into bucket and key
        parts = path.split("/", 1)
        if len(parts) != 2:
            raise ValidationError(f"Invalid S3 URI format: {s3_uri}")

        return parts[1]

    def _format_embeddings_for_storage(
        self, embeddings: List[EmbeddingData], video_id: str, s3_key: str
    ) -> List[Dict[str, Any]]:
        """
        Format embeddings for S3 Vectors storage.

        Each embedding is formatted as a dictionary with:
        - key: Unique identifier for the embedding
        - data: Embedding vector in float32 format
        - metadata: Video metadata for search and playback

        Args:
            embeddings: List of EmbeddingData objects
            video_id: ID of the video
            s3_key: S3 key of the video file

        Returns:
            List of formatted vector dictionaries
        """
        vectors = []

        for idx, emb in enumerate(embeddings):
            # Generate unique key for this embedding
            # Format: video_id:start_sec:end_sec:index
            # This ensures idempotent storage - same embedding overwrites previous
            embedding_key = (
                f"{video_id}:" f"{emb.start_sec:.2f}:" f"{emb.end_sec:.2f}:" f"{idx}"
            )

            # Format metadata for search
            # Handle embedding_option - ensure it's a list before joining
            emb_option = emb.embedding_option
            if isinstance(emb_option, str):
                # Already a string (e.g., "transcription"), use as-is
                embedding_option_str = emb_option
            elif isinstance(emb_option, list):
                # List of modalities, join them
                embedding_option_str = ",".join(emb_option)
            else:
                embedding_option_str = str(emb_option)
            
            metadata = {
                "video_id": video_id,
                "start_timecode": emb.start_sec,
                "end_timecode": emb.end_sec,
                "s3_key": s3_key,
                "embedding_option": embedding_option_str,
                "embedding_scope": emb.embedding_scope,
            }

            # Format vector for S3 Vectors API
            vector = {
                "key": embedding_key,
                "data": {"float32": emb.embedding},
                "metadata": metadata,
            }

            vectors.append(vector)

        return vectors

    def _store_in_batches(
        self, vectors: List[Dict[str, Any]], index_id: str
    ) -> Dict[str, Any]:
        """
        Store vectors in batches with retry logic.

        Processes vectors in batches to handle large numbers of embeddings
        efficiently. Each batch is retried on failure with exponential backoff.

        Args:
            vectors: List of formatted vector dictionaries
            index_id: ID of the index to store vectors in

        Returns:
            Dictionary with storage statistics
        """
        # Normalize index name for S3 Vectors (lowercase, hyphens)
        vector_index_name = f"index-{index_id}".lower()

        total = len(vectors)
        stored = 0
        failed = 0
        batch_count = 0

        # Process in batches
        for i in range(0, total, self.batch_size):
            batch = vectors[i : i + self.batch_size]
            batch_count += 1

            logger.debug(
                f"Processing batch {batch_count} " f"({len(batch)} vectors, offset {i})"
            )

            # Store batch with retry logic
            result = self._store_batch_with_retry(
                vectors=batch, index_name=vector_index_name, batch_num=batch_count
            )

            stored += result["successCount"]
            failed += result["failureCount"]

        return {
            "total": total,
            "stored": stored,
            "failed": failed,
            "batches": batch_count,
        }

    def _store_batch_with_retry(
        self, vectors: List[Dict[str, Any]], index_name: str, batch_num: int
    ) -> Dict[str, int]:
        """
        Store a batch of vectors with retry logic.

        Retries failed operations with exponential backoff up to max_retries.
        Distinguishes between transient errors (retryable) and permanent errors.

        Args:
            vectors: List of vector dictionaries to store
            index_name: Name of the vector index
            batch_num: Batch number for logging

        Returns:
            Dictionary with successCount and failureCount

        Raises:
            StorageError: If all retries are exhausted for a non-transient error
        """
        last_error = None
        last_error_type = None

        for attempt in range(self.max_retries):
            try:
                # Track API call metrics
                start_time = time.time()
                
                result = self.s3_vectors.put_vectors(
                    index_name=index_name, vectors=vectors
                )
                
                # Update metrics
                api_time_ms = (time.time() - start_time) * 1000
                self._metrics["total_api_calls"] += 1
                self._metrics["api_call_time_ms"] += api_time_ms
                self._metrics["total_vectors_stored"] += result.get("successCount", 0)
                
                logger.debug(
                    f"Batch {batch_num} API call took {api_time_ms:.2f}ms, "
                    f"stored {result.get('successCount', 0)} vectors"
                )

                if result["failureCount"] > 0:
                    logger.warning(
                        f"Batch {batch_num} had {result['failureCount']} failures "
                        f"out of {len(vectors)} vectors"
                    )

                return result

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                last_error = e
                last_error_type = "ClientError"

                # Check if error is retryable
                is_retryable = self._is_retryable_error(error_code)

                if not is_retryable:
                    logger.error(
                        f"Batch {batch_num} failed with non-retryable error "
                        f"{error_code}: {str(e)}"
                    )
                    # Don't retry non-retryable errors
                    return {"successCount": 0, "failureCount": len(vectors)}

                if attempt < self.max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.warning(
                        f"Batch {batch_num} failed with {error_code} "
                        f"(attempt {attempt + 1}/{self.max_retries}): {str(e)}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Batch {batch_num} failed after {self.max_retries} "
                        f"attempts with {error_code}: {str(e)}"
                    )

            except BotoCoreError as e:
                last_error = e
                last_error_type = "BotoCoreError"

                if attempt < self.max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.warning(
                        f"Batch {batch_num} failed with BotoCoreError "
                        f"(attempt {attempt + 1}/{self.max_retries}): {str(e)}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Batch {batch_num} failed after {self.max_retries} "
                        f"attempts with BotoCoreError: {str(e)}"
                    )

            except Exception as e:
                last_error = e
                last_error_type = type(e).__name__

                if attempt < self.max_retries - 1:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.warning(
                        f"Batch {batch_num} failed with {last_error_type} "
                        f"(attempt {attempt + 1}/{self.max_retries}): {str(e)}. "
                        f"Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Batch {batch_num} failed after {self.max_retries} "
                        f"attempts with {last_error_type}: {str(e)}"
                    )

        # All retries failed
        logger.error(
            f"Batch {batch_num} permanently failed after {self.max_retries} attempts. "
            f"Last error type: {last_error_type}, Last error: {str(last_error)}"
        )

        return {"successCount": 0, "failureCount": len(vectors)}

    def _is_retryable_error(self, error_code: str) -> bool:
        """
        Determine if an AWS error code is retryable.

        Args:
            error_code: AWS error code from ClientError

        Returns:
            True if error is transient and should be retried
        """
        # Transient errors that should be retried
        retryable_errors = {
            "ThrottlingException",
            "Throttling",
            "TooManyRequestsException",
            "ProvisionedThroughputExceededException",
            "RequestTimeout",
            "RequestTimeoutException",
            "ServiceUnavailable",
            "InternalError",
            "InternalServerError",
            "SlowDown",
        }

        return error_code in retryable_errors

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: retry_delay * 2^attempt
        base_delay = self.retry_delay * (2**attempt)

        # Add jitter (up to 20% of base delay) to avoid thundering herd
        import random

        jitter = random.uniform(0, base_delay * 0.2)

        return base_delay + jitter

    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the indexer.
        
        Returns:
            Dictionary containing performance metrics:
                - total_api_calls: Total number of S3 Vectors API calls made
                - total_vectors_stored: Total number of vectors successfully stored
                - total_batches_processed: Total number of batches processed
                - avg_api_call_time_ms: Average API call time in milliseconds
                - total_api_call_time_ms: Total time spent in API calls
        """
        avg_api_time = (
            self._metrics["api_call_time_ms"] / self._metrics["total_api_calls"]
            if self._metrics["total_api_calls"] > 0
            else 0
        )
        
        return {
            "total_api_calls": self._metrics["total_api_calls"],
            "total_vectors_stored": self._metrics["total_vectors_stored"],
            "total_batches_processed": self._metrics["total_batches_processed"],
            "avg_api_call_time_ms": round(avg_api_time, 2),
            "total_api_call_time_ms": round(self._metrics["api_call_time_ms"], 2),
        }
    
    def reset_metrics(self) -> None:
        """Reset performance metrics to zero."""
        self._metrics = {
            "total_api_calls": 0,
            "total_vectors_stored": 0,
            "total_batches_processed": 0,
            "api_call_time_ms": 0.0,
        }
