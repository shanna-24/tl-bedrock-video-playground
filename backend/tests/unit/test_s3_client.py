"""Unit tests for S3 client wrapper.

Tests the S3Client class methods for upload, download, delete, and presigned URL generation.
Validates: Requirements 7.3, 7.5
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from aws.s3_client import S3Client
from config import Config
from exceptions import AWSServiceError


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=Config)
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-video-bucket"
    config.use_localstack = False
    return config


@pytest.fixture
def mock_config_localstack():
    """Create a mock configuration with LocalStack enabled."""
    config = Mock(spec=Config)
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-video-bucket"
    config.use_localstack = True
    return config


class TestS3ClientInitialization:
    """Test suite for S3Client initialization."""
    
    @patch("aws.s3_client.boto3.client")
    def test_init_without_localstack(self, mock_boto_client, mock_config):
        """Test initialization without LocalStack."""
        client = S3Client(mock_config)
        
        assert client.config == mock_config
        assert client.bucket_name == "test-video-bucket"
        
        # Verify boto3.client was called with config parameter
        mock_boto_client.assert_called_once()
        call_args = mock_boto_client.call_args
        assert call_args[0][0] == "s3"
        assert "config" in call_args[1]
        # Verify no endpoint_url for non-localstack
        assert "endpoint_url" not in call_args[1]
    
    @patch("aws.s3_client.boto3.client")
    def test_init_with_localstack(self, mock_boto_client, mock_config_localstack):
        """Test initialization with LocalStack."""
        client = S3Client(mock_config_localstack)
        
        assert client.config == mock_config_localstack
        assert client.bucket_name == "test-video-bucket"
        
        # Verify boto3.client was called with endpoint_url and config
        mock_boto_client.assert_called_once()
        call_args = mock_boto_client.call_args
        assert call_args[0][0] == "s3"
        assert call_args[1]["endpoint_url"] == "http://localhost:4566"
        assert "config" in call_args[1]


class TestS3Upload:
    """Test suite for S3 upload operations."""
    
    @patch("aws.s3_client.boto3.client")
    def test_upload_success(self, mock_boto_client, mock_config):
        """Test successful file upload."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3Client(mock_config)
        
        # Create a mock file object
        file_obj = io.BytesIO(b"test video content")
        
        s3_uri = client.upload(
            file_obj=file_obj,
            key="videos/test-video.mp4"
        )
        
        assert s3_uri == "s3://test-video-bucket/videos/test-video.mp4"
        mock_client_instance.upload_fileobj.assert_called_once_with(
            file_obj,
            "test-video-bucket",
            "videos/test-video.mp4",
            ExtraArgs=None
        )
    
    @patch("aws.s3_client.boto3.client")
    def test_upload_with_content_type(self, mock_boto_client, mock_config):
        """Test upload with content type."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3Client(mock_config)
        file_obj = io.BytesIO(b"test video content")
        
        s3_uri = client.upload(
            file_obj=file_obj,
            key="videos/test-video.mp4",
            content_type="video/mp4"
        )
        
        assert s3_uri == "s3://test-video-bucket/videos/test-video.mp4"
        
        # Check that ContentType was passed
        call_args = mock_client_instance.upload_fileobj.call_args
        assert call_args[1]["ExtraArgs"]["ContentType"] == "video/mp4"
    
    @patch("aws.s3_client.boto3.client")
    def test_upload_with_metadata(self, mock_boto_client, mock_config):
        """Test upload with custom metadata."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3Client(mock_config)
        file_obj = io.BytesIO(b"test video content")
        
        metadata = {
            "index-id": "index-123",
            "duration": "120"
        }
        
        s3_uri = client.upload(
            file_obj=file_obj,
            key="videos/test-video.mp4",
            metadata=metadata
        )
        
        assert s3_uri == "s3://test-video-bucket/videos/test-video.mp4"
        
        # Check that Metadata was passed
        call_args = mock_client_instance.upload_fileobj.call_args
        assert call_args[1]["ExtraArgs"]["Metadata"] == metadata
    
    @patch("aws.s3_client.boto3.client")
    def test_upload_with_content_type_and_metadata(self, mock_boto_client, mock_config):
        """Test upload with both content type and metadata."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3Client(mock_config)
        file_obj = io.BytesIO(b"test video content")
        
        metadata = {"index-id": "index-123"}
        
        s3_uri = client.upload(
            file_obj=file_obj,
            key="videos/test-video.mp4",
            content_type="video/mp4",
            metadata=metadata
        )
        
        assert s3_uri == "s3://test-video-bucket/videos/test-video.mp4"
        
        # Check that both were passed
        call_args = mock_client_instance.upload_fileobj.call_args
        assert call_args[1]["ExtraArgs"]["ContentType"] == "video/mp4"
        assert call_args[1]["ExtraArgs"]["Metadata"] == metadata
    
    @patch("aws.s3_client.boto3.client")
    def test_upload_client_error(self, mock_boto_client, mock_config):
        """Test handling of ClientError during upload."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "NoSuchBucket",
                "Message": "The specified bucket does not exist"
            }
        }
        mock_client_instance.upload_fileobj.side_effect = ClientError(
            error_response, "PutObject"
        )
        
        client = S3Client(mock_config)
        file_obj = io.BytesIO(b"test video content")
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.upload(file_obj=file_obj, key="videos/test-video.mp4")
        
        assert "Failed to upload file to S3" in str(exc_info.value)
        assert "The specified bucket does not exist" in str(exc_info.value)
    
    @patch("aws.s3_client.boto3.client")
    def test_upload_unexpected_error(self, mock_boto_client, mock_config):
        """Test handling of unexpected errors during upload."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_client_instance.upload_fileobj.side_effect = ValueError("Unexpected error")
        
        client = S3Client(mock_config)
        file_obj = io.BytesIO(b"test video content")
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.upload(file_obj=file_obj, key="videos/test-video.mp4")
        
        assert "Failed to upload file to S3" in str(exc_info.value)


class TestS3Download:
    """Test suite for S3 download operations."""
    
    @patch("aws.s3_client.boto3.client")
    def test_download_success(self, mock_boto_client, mock_config):
        """Test successful file download."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3Client(mock_config)
        file_obj = io.BytesIO()
        
        client.download(
            key="videos/test-video.mp4",
            file_obj=file_obj
        )
        
        mock_client_instance.download_fileobj.assert_called_once_with(
            "test-video-bucket",
            "videos/test-video.mp4",
            file_obj
        )
    
    @patch("aws.s3_client.boto3.client")
    def test_download_not_found(self, mock_boto_client, mock_config):
        """Test download when file doesn't exist."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist"
            }
        }
        mock_client_instance.download_fileobj.side_effect = ClientError(
            error_response, "GetObject"
        )
        
        client = S3Client(mock_config)
        file_obj = io.BytesIO()
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.download(key="videos/nonexistent.mp4", file_obj=file_obj)
        
        assert "File not found in S3" in str(exc_info.value)
    
    @patch("aws.s3_client.boto3.client")
    def test_download_client_error(self, mock_boto_client, mock_config):
        """Test handling of ClientError during download."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied"
            }
        }
        mock_client_instance.download_fileobj.side_effect = ClientError(
            error_response, "GetObject"
        )
        
        client = S3Client(mock_config)
        file_obj = io.BytesIO()
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.download(key="videos/test-video.mp4", file_obj=file_obj)
        
        assert "Failed to download file from S3" in str(exc_info.value)
        assert "Access Denied" in str(exc_info.value)


class TestS3Delete:
    """Test suite for S3 delete operations."""
    
    @patch("aws.s3_client.boto3.client")
    def test_delete_success(self, mock_boto_client, mock_config):
        """Test successful file deletion."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        client = S3Client(mock_config)
        result = client.delete(key="videos/test-video.mp4")
        
        assert result is True
        mock_client_instance.delete_object.assert_called_once_with(
            Bucket="test-video-bucket",
            Key="videos/test-video.mp4"
        )
    
    @patch("aws.s3_client.boto3.client")
    def test_delete_client_error(self, mock_boto_client, mock_config):
        """Test handling of ClientError during delete."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied"
            }
        }
        mock_client_instance.delete_object.side_effect = ClientError(
            error_response, "DeleteObject"
        )
        
        client = S3Client(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.delete(key="videos/test-video.mp4")
        
        assert "Failed to delete file from S3" in str(exc_info.value)
        assert "Access Denied" in str(exc_info.value)


class TestPresignedURL:
    """Test suite for presigned URL generation."""
    
    @patch("aws.s3_client.boto3.client")
    def test_generate_presigned_url_success(self, mock_boto_client, mock_config):
        """Test successful presigned URL generation."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        expected_url = (
            "https://test-video-bucket.s3.amazonaws.com/videos/test-video.mp4"
            "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=..."
        )
        mock_client_instance.generate_presigned_url.return_value = expected_url
        
        client = S3Client(mock_config)
        url = client.generate_presigned_url(key="videos/test-video.mp4")
        
        assert url == expected_url
        mock_client_instance.generate_presigned_url.assert_called_once_with(
            ClientMethod="get_object",
            Params={
                "Bucket": "test-video-bucket",
                "Key": "videos/test-video.mp4"
            },
            ExpiresIn=3600
        )
    
    @patch("aws.s3_client.boto3.client")
    def test_generate_presigned_url_custom_expiration(self, mock_boto_client, mock_config):
        """Test presigned URL with custom expiration."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        expected_url = "https://test-video-bucket.s3.amazonaws.com/videos/test-video.mp4?..."
        mock_client_instance.generate_presigned_url.return_value = expected_url
        
        client = S3Client(mock_config)
        url = client.generate_presigned_url(
            key="videos/test-video.mp4",
            expiration=7200
        )
        
        assert url == expected_url
        
        # Check that custom expiration was used
        call_args = mock_client_instance.generate_presigned_url.call_args
        assert call_args[1]["ExpiresIn"] == 7200
    
    @patch("aws.s3_client.boto3.client")
    def test_generate_presigned_url_put_method(self, mock_boto_client, mock_config):
        """Test presigned URL for PUT operation."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        expected_url = "https://test-video-bucket.s3.amazonaws.com/videos/test-video.mp4?..."
        mock_client_instance.generate_presigned_url.return_value = expected_url
        
        client = S3Client(mock_config)
        url = client.generate_presigned_url(
            key="videos/test-video.mp4",
            http_method="PUT"
        )
        
        assert url == expected_url
        
        # Check that PUT method was used
        call_args = mock_client_instance.generate_presigned_url.call_args
        assert call_args[1]["ClientMethod"] == "put_object"
    
    @patch("aws.s3_client.boto3.client")
    def test_generate_presigned_url_client_error(self, mock_boto_client, mock_config):
        """Test handling of ClientError during URL generation."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "InvalidRequest",
                "Message": "Invalid request parameters"
            }
        }
        mock_client_instance.generate_presigned_url.side_effect = ClientError(
            error_response, "GeneratePresignedUrl"
        )
        
        client = S3Client(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.generate_presigned_url(key="videos/test-video.mp4")
        
        assert "Failed to generate presigned URL" in str(exc_info.value)
        assert "Invalid request parameters" in str(exc_info.value)


class TestObjectExists:
    """Test suite for checking object existence."""
    
    @patch("aws.s3_client.boto3.client")
    def test_object_exists_true(self, mock_boto_client, mock_config):
        """Test when object exists."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # head_object succeeds when object exists
        mock_client_instance.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "video/mp4"
        }
        
        client = S3Client(mock_config)
        exists = client.object_exists(key="videos/test-video.mp4")
        
        assert exists is True
        mock_client_instance.head_object.assert_called_once_with(
            Bucket="test-video-bucket",
            Key="videos/test-video.mp4"
        )
    
    @patch("aws.s3_client.boto3.client")
    def test_object_exists_false_nosuchkey(self, mock_boto_client, mock_config):
        """Test when object doesn't exist (NoSuchKey error)."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist"
            }
        }
        mock_client_instance.head_object.side_effect = ClientError(
            error_response, "HeadObject"
        )
        
        client = S3Client(mock_config)
        exists = client.object_exists(key="videos/nonexistent.mp4")
        
        assert exists is False
    
    @patch("aws.s3_client.boto3.client")
    def test_object_exists_false_404(self, mock_boto_client, mock_config):
        """Test when object doesn't exist (404 error)."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "404",
                "Message": "Not Found"
            }
        }
        mock_client_instance.head_object.side_effect = ClientError(
            error_response, "HeadObject"
        )
        
        client = S3Client(mock_config)
        exists = client.object_exists(key="videos/nonexistent.mp4")
        
        assert exists is False
    
    @patch("aws.s3_client.boto3.client")
    def test_object_exists_other_error(self, mock_boto_client, mock_config):
        """Test handling of other errors during existence check."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied"
            }
        }
        mock_client_instance.head_object.side_effect = ClientError(
            error_response, "HeadObject"
        )
        
        client = S3Client(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.object_exists(key="videos/test-video.mp4")
        
        assert "Failed to check if object exists" in str(exc_info.value)
        assert "Access Denied" in str(exc_info.value)


class TestGetObjectMetadata:
    """Test suite for getting object metadata."""
    
    @patch("aws.s3_client.boto3.client")
    def test_get_object_metadata_success(self, mock_boto_client, mock_config):
        """Test successful metadata retrieval."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        from datetime import datetime
        last_modified = datetime(2024, 1, 1, 12, 0, 0)
        
        mock_client_instance.head_object.return_value = {
            "ContentLength": 1024000,
            "ContentType": "video/mp4",
            "LastModified": last_modified,
            "Metadata": {
                "index-id": "index-123",
                "duration": "120"
            }
        }
        
        client = S3Client(mock_config)
        metadata = client.get_object_metadata(key="videos/test-video.mp4")
        
        assert metadata["ContentLength"] == 1024000
        assert metadata["ContentType"] == "video/mp4"
        assert metadata["LastModified"] == last_modified
        assert metadata["Metadata"]["index-id"] == "index-123"
        assert metadata["Metadata"]["duration"] == "120"
    
    @patch("aws.s3_client.boto3.client")
    def test_get_object_metadata_no_custom_metadata(self, mock_boto_client, mock_config):
        """Test metadata retrieval when no custom metadata exists."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        from datetime import datetime
        last_modified = datetime(2024, 1, 1, 12, 0, 0)
        
        mock_client_instance.head_object.return_value = {
            "ContentLength": 1024000,
            "ContentType": "video/mp4",
            "LastModified": last_modified
        }
        
        client = S3Client(mock_config)
        metadata = client.get_object_metadata(key="videos/test-video.mp4")
        
        assert metadata["ContentLength"] == 1024000
        assert metadata["Metadata"] == {}
    
    @patch("aws.s3_client.boto3.client")
    def test_get_object_metadata_not_found(self, mock_boto_client, mock_config):
        """Test metadata retrieval when object doesn't exist."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist"
            }
        }
        mock_client_instance.head_object.side_effect = ClientError(
            error_response, "HeadObject"
        )
        
        client = S3Client(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.get_object_metadata(key="videos/nonexistent.mp4")
        
        assert "File not found in S3" in str(exc_info.value)
    
    @patch("aws.s3_client.boto3.client")
    def test_get_object_metadata_client_error(self, mock_boto_client, mock_config):
        """Test handling of ClientError during metadata retrieval."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "Access Denied"
            }
        }
        mock_client_instance.head_object.side_effect = ClientError(
            error_response, "HeadObject"
        )
        
        client = S3Client(mock_config)
        
        with pytest.raises(AWSServiceError) as exc_info:
            client.get_object_metadata(key="videos/test-video.mp4")
        
        assert "Failed to get object metadata" in str(exc_info.value)
        assert "Access Denied" in str(exc_info.value)


class TestErrorHandling:
    """Test suite for AWS error handling (Requirement 7.5)."""
    
    @patch("aws.s3_client.boto3.client")
    def test_descriptive_error_messages(self, mock_boto_client, mock_config):
        """Test that AWS errors are transformed into descriptive messages."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Test various AWS error codes
        error_cases = [
            ("NoSuchBucket", "The specified bucket does not exist"),
            ("AccessDenied", "Access Denied"),
            ("InvalidRequest", "Invalid request parameters"),
            ("ServiceUnavailable", "Service temporarily unavailable"),
        ]
        
        client = S3Client(mock_config)
        file_obj = io.BytesIO(b"test content")
        
        for error_code, error_message in error_cases:
            error_response = {
                "Error": {
                    "Code": error_code,
                    "Message": error_message
                }
            }
            mock_client_instance.upload_fileobj.side_effect = ClientError(
                error_response, "PutObject"
            )
            
            with pytest.raises(AWSServiceError) as exc_info:
                client.upload(file_obj=file_obj, key="test.mp4")
            
            # Verify the error message is descriptive and includes the AWS message
            assert error_message in str(exc_info.value)
            assert "Failed to upload file to S3" in str(exc_info.value)
