"""S3 client wrapper for video storage.

This module provides a wrapper around AWS S3 client for uploading, downloading,
deleting videos, and generating presigned URLs.

Validates: Requirements 7.3
"""

import logging
from typing import BinaryIO, Optional

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from config import Config
from exceptions import AWSServiceError

logger = logging.getLogger(__name__)


class S3Client:
    """Wrapper for AWS S3 client.
    
    This class provides methods for managing video files in S3, including
    upload, download, delete operations, and presigned URL generation for
    secure video streaming.
    
    Attributes:
        config: Configuration object containing S3 bucket and AWS settings
        client: boto3 S3 client
        bucket_name: Name of the S3 bucket for video storage
    """
    
    def __init__(self, config: Config, max_pool_connections: int = 50):
        """Initialize the S3 client with connection pooling.
        
        Args:
            config: Configuration object with AWS region and S3 bucket name
            max_pool_connections: Maximum number of connections to keep in the pool (default: 50)
                                 Higher values improve performance for concurrent operations
        """
        self.config = config
        self.bucket_name = config.s3_bucket_name
        
        # Configure connection pooling for better performance
        # This allows reusing connections across requests, reducing overhead
        boto_config = BotoConfig(
            region_name=config.aws_region,
            max_pool_connections=max_pool_connections,
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'  # Adaptive retry mode for better handling of throttling
            },
            # Connection timeout and read timeout
            connect_timeout=10,
            read_timeout=60,
        )
        
        # Create S3 client with connection pooling
        self.client = boto3.client(
            "s3",
            config=boto_config
        )
        
        logger.info(
            f"Initialized S3Client for bucket {self.bucket_name} in region "
            f"{config.aws_region} with connection pool (max_connections={max_pool_connections})"
        )
    
    def upload(
        self,
        file_obj: BinaryIO,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """Upload a file to S3.
        
        Args:
            file_obj: File-like object to upload
            key: S3 object key (path within bucket)
            content_type: MIME type of the file (e.g., "video/mp4")
            metadata: Optional metadata to attach to the object
        
        Returns:
            S3 URI of the uploaded file (s3://bucket/key)
        
        Raises:
            AWSServiceError: If the upload fails
        """
        try:
            extra_args = {}
            
            if content_type:
                extra_args["ContentType"] = content_type
            
            if metadata:
                extra_args["Metadata"] = metadata
            
            logger.debug(f"Uploading file to s3://{self.bucket_name}/{key}")
            
            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                key,
                ExtraArgs=extra_args if extra_args else None
            )
            
            s3_uri = f"s3://{self.bucket_name}/{key}"
            logger.info(f"Successfully uploaded file to {s3_uri}")
            
            return s3_uri
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 upload error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to upload file to S3: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error uploading to S3: {e}")
            raise AWSServiceError(
                f"Failed to upload file to S3: {str(e)}"
            ) from e
    
    def download(
        self,
        key: str,
        file_obj: BinaryIO
    ) -> None:
        """Download a file from S3.
        
        Args:
            key: S3 object key (path within bucket)
            file_obj: File-like object to write downloaded data to
        
        Raises:
            AWSServiceError: If the download fails
        """
        try:
            logger.debug(f"Downloading file from s3://{self.bucket_name}/{key}")
            
            self.client.download_fileobj(
                self.bucket_name,
                key,
                file_obj
            )
            
            logger.info(f"Successfully downloaded file from s3://{self.bucket_name}/{key}")
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 download error ({error_code}): {error_message}")
            
            if error_code == "NoSuchKey":
                raise AWSServiceError(
                    f"File not found in S3: {key}"
                ) from e
            
            raise AWSServiceError(
                f"Failed to download file from S3: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error downloading from S3: {e}")
            raise AWSServiceError(
                f"Failed to download file from S3: {str(e)}"
            ) from e
    
    def delete(self, key: str) -> bool:
        """Delete a file from S3.
        
        Args:
            key: S3 object key (path within bucket)
        
        Returns:
            True if the file was deleted successfully
        
        Raises:
            AWSServiceError: If the delete operation fails
        """
        try:
            logger.debug(f"Deleting file from s3://{self.bucket_name}/{key}")
            
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            logger.info(f"Successfully deleted file from s3://{self.bucket_name}/{key}")
            
            return True
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 delete error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to delete file from S3: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error deleting from S3: {e}")
            raise AWSServiceError(
                f"Failed to delete file from S3: {str(e)}"
            ) from e
    
    def generate_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        http_method: str = "GET"
    ) -> str:
        """Generate a presigned URL for accessing an S3 object.
        
        Presigned URLs allow temporary access to S3 objects without requiring
        AWS credentials. This is used for video streaming.
        
        Args:
            key: S3 object key (path within bucket)
            expiration: URL expiration time in seconds (default: 3600 = 1 hour)
            http_method: HTTP method for the URL (default: "GET")
        
        Returns:
            Presigned URL string
        
        Raises:
            AWSServiceError: If URL generation fails
        """
        try:
            logger.debug(
                f"Generating presigned URL for s3://{self.bucket_name}/{key} "
                f"(expiration: {expiration}s)"
            )
            
            # Determine the client method based on HTTP method
            client_method = "get_object" if http_method == "GET" else "put_object"
            
            url = self.client.generate_presigned_url(
                ClientMethod=client_method,
                Params={
                    "Bucket": self.bucket_name,
                    "Key": key
                },
                ExpiresIn=expiration
            )
            
            logger.info(f"Generated presigned URL for {key}")
            
            return url
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 presigned URL error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to generate presigned URL: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {e}")
            raise AWSServiceError(
                f"Failed to generate presigned URL: {str(e)}"
            ) from e
    
    def object_exists(self, key: str) -> bool:
        """Check if an object exists in S3.
        
        Args:
            key: S3 object key (path within bucket)
        
        Returns:
            True if the object exists, False otherwise
        
        Raises:
            AWSServiceError: If the check operation fails (excluding NoSuchKey)
        """
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            
            # NoSuchKey means the object doesn't exist, which is not an error
            if error_code == "404" or error_code == "NoSuchKey":
                return False
            
            # Other errors should be raised
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 head_object error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to check if object exists: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error checking object existence: {e}")
            raise AWSServiceError(
                f"Failed to check if object exists: {str(e)}"
            ) from e
    
    def get_object_metadata(self, key: str) -> dict:
        """Get metadata for an S3 object.
        
        Args:
            key: S3 object key (path within bucket)
        
        Returns:
            Dictionary containing object metadata including:
                - ContentLength: Size in bytes
                - ContentType: MIME type
                - LastModified: Last modification timestamp
                - Metadata: Custom metadata
        
        Raises:
            AWSServiceError: If the operation fails
        """
        try:
            logger.debug(f"Getting metadata for s3://{self.bucket_name}/{key}")
            
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=key
            )
            
            metadata = {
                "ContentLength": response.get("ContentLength"),
                "ContentType": response.get("ContentType"),
                "LastModified": response.get("LastModified"),
                "Metadata": response.get("Metadata", {})
            }
            
            logger.info(f"Retrieved metadata for {key}")
            
            return metadata
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 metadata error ({error_code}): {error_message}")
            
            if error_code == "404" or error_code == "NoSuchKey":
                raise AWSServiceError(
                    f"File not found in S3: {key}"
                ) from e
            
            raise AWSServiceError(
                f"Failed to get object metadata: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error getting object metadata: {e}")
            raise AWSServiceError(
                f"Failed to get object metadata: {str(e)}"
            ) from e
    
    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects with a given prefix (folder).
        
        This method lists all objects under the prefix and deletes them in batches
        of up to 1000 objects at a time (S3 delete_objects limit).
        
        Args:
            prefix: S3 key prefix (folder path) to delete
        
        Returns:
            Number of objects deleted
        
        Raises:
            AWSServiceError: If the delete operation fails
        """
        try:
            logger.debug(f"Deleting all objects with prefix: s3://{self.bucket_name}/{prefix}")
            
            deleted_count = 0
            
            # List all objects with the prefix
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                # Prepare batch delete request (max 1000 objects per request)
                objects_to_delete = [{'Key': obj['Key']} for obj in page['Contents']]
                
                if not objects_to_delete:
                    continue
                
                # Delete batch
                response = self.client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={'Objects': objects_to_delete}
                )
                
                # Count successful deletions
                deleted = response.get('Deleted', [])
                deleted_count += len(deleted)
                
                # Log any errors
                errors = response.get('Errors', [])
                for error in errors:
                    logger.error(
                        f"Failed to delete {error['Key']}: "
                        f"{error['Code']} - {error['Message']}"
                    )
            
            logger.info(
                f"Successfully deleted {deleted_count} objects with prefix "
                f"s3://{self.bucket_name}/{prefix}"
            )
            
            return deleted_count
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"S3 batch delete error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to delete objects with prefix {prefix}: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error deleting objects with prefix: {e}")
            raise AWSServiceError(
                f"Failed to delete objects with prefix {prefix}: {str(e)}"
            ) from e
