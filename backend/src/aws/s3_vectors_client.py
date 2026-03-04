"""S3 Vectors client wrapper for vector embeddings storage.

This module provides a wrapper around AWS S3 Vectors client for creating
vector indexes, storing embeddings, and performing similarity searches.

Uses Amazon Bedrock S3 Vectors with S3 backend for vector storage.

Validates: Requirements 7.2
"""

import logging
import json
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from config import Config
from exceptions import AWSServiceError

logger = logging.getLogger(__name__)


class S3VectorsClient:
    """Wrapper for AWS S3 Vectors client.
    
    This class provides methods for managing vector indexes and embeddings
    in Amazon S3 Vectors, including creating indexes, storing embeddings,
    and performing similarity searches.
    
    Attributes:
        config: Configuration object containing S3 Vectors settings
        client: boto3 s3vectors client
        vector_bucket_name: Name of the S3 vector bucket
    """
    
    def __init__(self, config: Config):
        """Initialize the S3 Vectors client.
        
        Args:
            config: Configuration object with AWS region and vector bucket name
        """
        self.config = config
        self.vector_bucket_name = config.s3_bucket_name
        
        # Create S3 Vectors client
        self.client = boto3.client(
            "s3vectors",
            region_name=config.aws_region
        )
        
        logger.info(
            f"Initialized S3VectorsClient for bucket {self.vector_bucket_name} "
            f"in region {config.aws_region}"
        )
    
    def create_index(
        self,
        index_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        non_filterable_metadata_keys: Optional[List[str]] = None
    ) -> str:
        """Create a vector index in the vector bucket.
        
        Args:
            index_name: Name of the vector index (3-63 chars, lowercase, numbers, hyphens, dots)
            dimension: Number of dimensions for vectors (1-4096)
            distance_metric: Distance metric for similarity ("cosine" or "euclidean")
            non_filterable_metadata_keys: Optional list of metadata keys that won't be filterable
        
        Returns:
            ARN of the created vector index
        
        Raises:
            AWSServiceError: If index creation fails
        """
        try:
            # Validate inputs
            if not 3 <= len(index_name) <= 63:
                raise ValueError("Index name must be 3-63 characters")
            
            if not 1 <= dimension <= 4096:
                raise ValueError("Dimension must be between 1 and 4096")
            
            if distance_metric.lower() not in ["cosine", "euclidean"]:
                raise ValueError("Distance metric must be 'cosine' or 'euclidean'")
            
            logger.debug(
                f"Creating vector index '{index_name}' with dimension={dimension}, "
                f"metric={distance_metric}"
            )
            
            # AWS S3 Vectors implementation
            params: Dict[str, Any] = {
                "vectorBucketName": self.vector_bucket_name,
                "indexName": index_name,
                "dimension": dimension,
                "distanceMetric": distance_metric.lower(),  # API expects lowercase
                "dataType": "float32"  # Required parameter
            }
            
            # Add metadata configuration if provided
            if non_filterable_metadata_keys:
                params["metadataConfiguration"] = {
                    "nonFilterableMetadataKeys": non_filterable_metadata_keys
                }
            
            # Create the index using AWS S3 Vectors API
            response = self.client.create_index(**params)
            
            index_arn = response.get("indexArn", "")
            
            logger.info(f"Successfully created AWS S3 vector index: {index_arn}")
            
            return index_arn
            
        except ValueError as e:
            logger.error(f"Validation error creating index: {e}")
            raise AWSServiceError(f"Invalid parameters for index creation: {str(e)}") from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 Vectors create index error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to create vector index: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error creating vector index: {e}")
            raise AWSServiceError(
                f"Failed to create vector index: {str(e)}"
            ) from e
    
    def delete_index(self, index_name: str) -> bool:
        """Delete a vector index from the vector bucket.
        
        Args:
            index_name: Name of the vector index to delete
        
        Returns:
            True if the index was deleted successfully
        
        Raises:
            AWSServiceError: If index deletion fails
        """
        try:
            logger.debug(f"Deleting vector index '{index_name}'")
            
            # AWS S3 Vectors implementation
            self.client.delete_index(
                vectorBucketName=self.vector_bucket_name,
                indexName=index_name
            )
            
            logger.info(f"Successfully deleted AWS S3 vector index: {index_name}")
            return True
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 Vectors delete index error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to delete vector index: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error deleting vector index: {e}")
            raise AWSServiceError(
                f"Failed to delete vector index: {str(e)}"
            ) from e
    
    def list_indexes(self) -> List[Dict[str, Any]]:
        """List all vector indexes in the vector bucket.
        
        Returns:
            List of dictionaries containing index information:
                - indexName: Name of the index
                - indexArn: ARN of the index
                - dimension: Number of dimensions
                - distanceMetric: Distance metric used
        
        Raises:
            AWSServiceError: If listing indexes fails
        """
        try:
            logger.debug(f"Listing vector indexes in bucket '{self.vector_bucket_name}'")
            
            # AWS S3 Vectors implementation
            response = self.client.list_indexes(
                vectorBucketName=self.vector_bucket_name
            )
            
            indexes = response.get("indexes", [])
            
            logger.info(f"Found {len(indexes)} AWS S3 vector indexes")
            
            return indexes
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 Vectors list indexes error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to list vector indexes: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error listing vector indexes: {e}")
            raise AWSServiceError(
                f"Failed to list vector indexes: {str(e)}"
            ) from e
    
    def get_index(self, index_name: str) -> Dict[str, Any]:
        """Get information about a specific vector index.
        
        Args:
            index_name: Name of the vector index
        
        Returns:
            Dictionary containing index information:
                - indexName: Name of the index
                - indexArn: ARN of the index
                - dimension: Number of dimensions
                - distanceMetric: Distance metric used
                - nonFilterableMetadataKeys: List of non-filterable metadata keys
        
        Raises:
            AWSServiceError: If getting index info fails
        """
        try:
            logger.debug(f"Getting info for vector index '{index_name}'")
            
            # AWS S3 Vectors implementation
            response = self.client.get_index(
                vectorBucketName=self.vector_bucket_name,
                indexName=index_name
            )
            
            logger.info(f"Retrieved info for AWS S3 vector index: {index_name}")
            return response
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 Vectors get index error ({error_code}): {error_message}")
            
            if error_code == "NoSuchVectorIndex":
                raise AWSServiceError(
                    f"Vector index not found: {index_name}"
                ) from e
            
            raise AWSServiceError(
                f"Failed to get vector index info: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error getting vector index info: {e}")
            raise AWSServiceError(
                f"Failed to get vector index info: {str(e)}"
            ) from e
    
    def put_vectors(
        self,
        index_name: str,
        vectors: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Store vectors in a vector index.
        
        Each vector should be a dictionary with:
            - key: Unique identifier for the vector (up to 1024 chars)
            - data: Dictionary with "float32" key containing list of floats
            - metadata: Optional dictionary of metadata key-value pairs
        
        Args:
            index_name: Name of the vector index
            vectors: List of vector dictionaries to store
        
        Returns:
            Dictionary containing:
                - successCount: Number of vectors successfully stored
                - failureCount: Number of vectors that failed to store
        
        Raises:
            AWSServiceError: If storing vectors fails
        """
        try:
            if not vectors:
                raise ValueError("Vectors list cannot be empty")
            
            logger.debug(
                f"Storing {len(vectors)} vectors in index '{index_name}'"
            )
            
            # AWS S3 Vectors implementation
            response = self.client.put_vectors(
                vectorBucketName=self.vector_bucket_name,
                indexName=index_name,
                vectors=vectors
            )
            
            success_count = response.get("successCount", 0)
            failure_count = response.get("failureCount", 0)
            
            logger.info(
                f"Stored vectors in AWS S3: {success_count} succeeded, {failure_count} failed"
            )
            
            return {
                "successCount": success_count,
                "failureCount": failure_count
            }
            
        except ValueError as e:
            logger.error(f"Validation error storing vectors: {e}")
            raise AWSServiceError(f"Invalid parameters for storing vectors: {str(e)}") from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 Vectors put vectors error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to store vectors: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error storing vectors: {e}")
            raise AWSServiceError(
                f"Failed to store vectors: {str(e)}"
            ) from e
    
    def query_vectors(
        self,
        index_name: str,
        query_vector: List[float],
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
        return_distance: bool = True,
        return_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """Perform similarity search on a vector index.
        
        Args:
            index_name: Name of the vector index
            query_vector: Query vector as list of floats
            top_k: Number of results to return (default: 10)
            metadata_filter: Optional metadata filter dictionary
            return_distance: Whether to return distance scores (default: True)
            return_metadata: Whether to return metadata (default: True)
        
        Returns:
            List of dictionaries containing:
                - key: Vector key
                - distance: Distance score (if return_distance=True)
                - metadata: Vector metadata (if return_metadata=True)
        
        Raises:
            AWSServiceError: If similarity search fails
        """
        try:
            if not query_vector:
                raise ValueError("Query vector cannot be empty")
            
            if top_k < 1:
                raise ValueError("top_k must be at least 1")
            
            logger.debug(
                f"Querying vector index '{index_name}' with top_k={top_k}"
            )
            
            # AWS S3 Vectors implementation
            params: Dict[str, Any] = {
                "vectorBucketName": self.vector_bucket_name,
                "indexName": index_name,
                "queryVector": {"float32": query_vector},
                "topK": top_k,
                "returnDistance": return_distance,
                "returnMetadata": return_metadata
            }
            
            # Add metadata filter if provided
            if metadata_filter:
                params["filter"] = metadata_filter
            
            response = self.client.query_vectors(**params)
            
            vectors = response.get("vectors", [])
            
            logger.info(f"AWS S3 query returned {len(vectors)} results")
            
            return vectors
            
        except ValueError as e:
            logger.error(f"Validation error querying vectors: {e}")
            raise AWSServiceError(f"Invalid parameters for querying vectors: {str(e)}") from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 Vectors query error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to query vectors: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error querying vectors: {e}")
            raise AWSServiceError(
                f"Failed to query vectors: {str(e)}"
            ) from e
    
    def delete_vectors(
        self,
        index_name: str,
        vector_keys: List[str]
    ) -> Dict[str, Any]:
        """Delete vectors from a vector index.
        
        Args:
            index_name: Name of the vector index
            vector_keys: List of vector keys to delete
        
        Returns:
            Dictionary containing:
                - successCount: Number of vectors successfully deleted
                - failureCount: Number of vectors that failed to delete
        
        Raises:
            AWSServiceError: If deleting vectors fails
        """
        try:
            if not vector_keys:
                raise ValueError("Vector keys list cannot be empty")
            
            logger.debug(
                f"Deleting {len(vector_keys)} vectors from index '{index_name}'"
            )
            
            # AWS S3 Vectors implementation
            response = self.client.delete_vectors(
                vectorBucketName=self.vector_bucket_name,
                indexName=index_name,
                keys=vector_keys
            )
            
            success_count = response.get("successCount", 0)
            failure_count = response.get("failureCount", 0)
            
            logger.info(
                f"Deleted vectors from AWS S3: {success_count} succeeded, {failure_count} failed"
            )
            
            return {
                "successCount": success_count,
                "failureCount": failure_count
            }
            
        except ValueError as e:
            logger.error(f"Validation error deleting vectors: {e}")
            raise AWSServiceError(f"Invalid parameters for deleting vectors: {str(e)}") from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 Vectors delete vectors error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to delete vectors: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error deleting vectors: {e}")
            raise AWSServiceError(
                f"Failed to delete vectors: {str(e)}"
            ) from e
    
    def list_vectors(
        self,
        index_name: str,
        max_results: int = 100,
        next_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """List vectors in a vector index.
        
        Args:
            index_name: Name of the vector index
            max_results: Maximum number of results to return (default: 100)
            next_token: Token for pagination (optional)
        
        Returns:
            Dictionary containing:
                - vectors: List of vector keys
                - nextToken: Token for next page (if more results available)
        
        Raises:
            AWSServiceError: If listing vectors fails
        """
        try:
            logger.debug(f"Listing vectors in index '{index_name}'")
            
            # AWS S3 Vectors implementation
            params: Dict[str, Any] = {
                "vectorBucketName": self.vector_bucket_name,
                "indexName": index_name,
                "maxResults": max_results
            }
            
            if next_token:
                params["nextToken"] = next_token
            
            response = self.client.list_vectors(**params)
            
            vectors = response.get("vectors", [])
            next_token = response.get("nextToken")
            
            logger.info(f"Listed {len(vectors)} vectors from AWS S3 index")
            
            return {
                "vectors": vectors,
                "nextToken": next_token
            }
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 Vectors list vectors error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to list vectors: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error listing vectors: {e}")
            raise AWSServiceError(
                f"Failed to list vectors: {str(e)}"
            ) from e
    def delete_by_video_id(
        self,
        index_name: str,
        video_id: str
    ) -> int:
        """Delete all vectors associated with a specific video.

        This method queries for all vectors with the given video_id in their
        metadata and deletes them. Vector keys are formatted as:
        {video_id}:{start}:{end}:{idx}

        Args:
            index_name: Name of the vector index
            video_id: ID of the video whose embeddings should be deleted

        Returns:
            Number of vectors deleted

        Raises:
            AWSServiceError: If deletion fails
        """
        try:
            logger.info(f"Deleting all vectors for video {video_id} from index '{index_name}'")

            # AWS S3 Vectors implementation
            # List all vectors with this video_id prefix
            deleted_count = 0
            next_token = None
            total_vectors_checked = 0

            while True:
                # List vectors in batches
                params = {
                    "vectorBucketName": self.vector_bucket_name,
                    "indexName": index_name,
                    "maxResults": 100
                }

                if next_token:
                    params["nextToken"] = next_token

                response = self.client.list_vectors(**params)
                vectors = response.get("vectors", [])
                total_vectors_checked += len(vectors)
                
                # Extract keys from response (AWS returns dicts or strings)
                vector_keys = []
                for item in vectors:
                    if isinstance(item, dict):
                        vector_keys.append(item.get("key", ""))
                    else:
                        vector_keys.append(item)
                
                # Log sample keys for debugging
                if len(vector_keys) > 0 and deleted_count == 0:
                    sample_keys = vector_keys[:5]
                    logger.debug(f"Sample vector keys in index: {sample_keys}")
                    logger.debug(f"Looking for keys starting with: {video_id}:")

                # Filter vectors that belong to this video
                video_keys = [
                    key for key in vector_keys
                    if key.startswith(f"{video_id}:")
                ]
                
                if len(video_keys) > 0:
                    logger.debug(f"Found {len(video_keys)} matching vectors in this batch")

                # Delete matching vectors in batches
                if video_keys:
                    delete_response = self.client.delete_vectors(
                        vectorBucketName=self.vector_bucket_name,
                        indexName=index_name,
                        keys=video_keys
                    )
                    batch_deleted = delete_response.get("successCount", 0)
                    batch_failed = delete_response.get("failureCount", 0)
                    deleted_count += batch_deleted
                    
                    if batch_failed > 0:
                        logger.warning(f"Failed to delete {batch_failed} vectors in this batch")

                # Check if there are more vectors to process
                next_token = response.get("nextToken")
                if not next_token:
                    break

            logger.info(
                f"Deleted {deleted_count} vectors for video {video_id} from AWS S3 index "
                f"(checked {total_vectors_checked} total vectors)"
            )
            
            if deleted_count == 0 and total_vectors_checked > 0:
                logger.warning(
                    f"No vectors found with prefix '{video_id}:' in index '{index_name}'. "
                    f"Checked {total_vectors_checked} vectors total."
                )
            
            return deleted_count

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 Vectors delete by video_id error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to delete vectors for video: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error deleting vectors by video_id: {e}")
            raise AWSServiceError(
                f"Failed to delete vectors for video: {str(e)}"
            ) from e

