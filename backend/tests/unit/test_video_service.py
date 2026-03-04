"""Unit tests for VideoService.

Tests specific examples and edge cases for video service operations.
"""

import sys
import io
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.video_service import VideoService
from aws.s3_client import S3Client
from config import Config
from exceptions import AWSServiceError


class TestVideoServiceUpload:
    """Tests for video upload functionality."""
    
    def test_upload_video_success(self):
        """Test successful video upload."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        mock_s3.upload = Mock(return_value="s3://test-bucket/videos/index-123/test.mp4")
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Upload video
        video_file = io.BytesIO(b"fake video content")
        s3_uri = video_service.upload_video(
            file=video_file,
            index_id="index-123",
            filename="test.mp4",
            content_type="video/mp4"
        )
        
        # Verify result
        assert s3_uri == "s3://test-bucket/videos/index-123/test.mp4"
        
        # Verify S3 client was called correctly
        mock_s3.upload.assert_called_once()
        call_args = mock_s3.upload.call_args
        assert call_args[1]['key'] == "videos/index-123/test.mp4"
        assert call_args[1]['content_type'] == "video/mp4"
        assert call_args[1]['metadata']['index_id'] == "index-123"
        assert call_args[1]['metadata']['original_filename'] == "test.mp4"
    
    def test_upload_video_default_content_type(self):
        """Test video upload with default content type."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        mock_s3.upload = Mock(return_value="s3://test-bucket/videos/index-123/test.mp4")
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Upload video without content type
        video_file = io.BytesIO(b"fake video content")
        s3_uri = video_service.upload_video(
            file=video_file,
            index_id="index-123",
            filename="test.mp4"
        )
        
        # Verify default content type was used
        call_args = mock_s3.upload.call_args
        assert call_args[1]['content_type'] == "video/mp4"
    
    def test_upload_video_sanitizes_filename(self):
        """Test that upload sanitizes filenames with path separators."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        mock_s3.upload = Mock(return_value="s3://test-bucket/videos/index-123/test.mp4")
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Upload video with path separators in filename
        video_file = io.BytesIO(b"fake video content")
        s3_uri = video_service.upload_video(
            file=video_file,
            index_id="index-123",
            filename="../../../etc/passwd.mp4"
        )
        
        # Verify filename was sanitized (slashes replaced with underscores)
        call_args = mock_s3.upload.call_args
        key = call_args[1]['key']
        # The key should have slashes replaced with underscores
        assert key == "videos/index-123/.._.._.._etc_passwd.mp4"
        # Verify no slashes in the filename part (after index-123/)
        filename_part = key.split("index-123/")[1]
        assert "/" not in filename_part
    
    def test_upload_video_s3_error(self):
        """Test video upload when S3 fails."""
        # Create mock S3 client that raises error
        mock_s3 = Mock(spec=S3Client)
        mock_s3.upload = Mock(side_effect=AWSServiceError("S3 upload failed"))
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Attempt to upload video
        video_file = io.BytesIO(b"fake video content")
        with pytest.raises(AWSServiceError) as exc_info:
            video_service.upload_video(
                file=video_file,
                index_id="index-123",
                filename="test.mp4"
            )
        
        assert "S3 upload failed" in str(exc_info.value)


class TestVideoServiceStreamURL:
    """Tests for video stream URL generation."""
    
    def test_get_stream_url_without_timecode(self):
        """Test generating stream URL without timecode."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/videos/index-123/test.mp4?signature=abc"
        )
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL
        url = video_service.get_video_stream_url(
            video_id="video-123",
            s3_key="videos/index-123/test.mp4"
        )
        
        # Verify URL
        assert url == "https://test-bucket.s3.amazonaws.com/videos/index-123/test.mp4?signature=abc"
        assert "#t=" not in url
        
        # Verify S3 client was called correctly
        mock_s3.generate_presigned_url.assert_called_once_with(
            key="videos/index-123/test.mp4",
            expiration=3600,
            http_method="GET"
        )
    
    def test_get_stream_url_with_timecode(self):
        """Test generating stream URL with start timecode."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/videos/index-123/test.mp4?signature=abc"
        )
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL with timecode
        url = video_service.get_video_stream_url(
            video_id="video-123",
            s3_key="videos/index-123/test.mp4",
            start_timecode=45.5
        )
        
        # Verify URL includes timecode
        assert "https://test-bucket.s3.amazonaws.com/videos/index-123/test.mp4?signature=abc#t=45.5" == url
        assert "#t=45.5" in url
    
    def test_get_stream_url_with_zero_timecode(self):
        """Test generating stream URL with zero timecode."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/videos/index-123/test.mp4?signature=abc"
        )
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL with zero timecode
        url = video_service.get_video_stream_url(
            video_id="video-123",
            s3_key="videos/index-123/test.mp4",
            start_timecode=0.0
        )
        
        # Verify URL includes zero timecode
        assert "#t=0" in url or "#t=0.0" in url
    
    def test_get_stream_url_with_custom_expiration(self):
        """Test generating stream URL with custom expiration."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/videos/index-123/test.mp4?signature=abc"
        )
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL with custom expiration
        url = video_service.get_video_stream_url(
            video_id="video-123",
            s3_key="videos/index-123/test.mp4",
            expiration=7200
        )
        
        # Verify S3 client was called with custom expiration
        mock_s3.generate_presigned_url.assert_called_once_with(
            key="videos/index-123/test.mp4",
            expiration=7200,
            http_method="GET"
        )
    
    def test_get_stream_url_negative_timecode_raises_error(self):
        """Test that negative timecode raises ValueError."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/videos/index-123/test.mp4?signature=abc"
        )
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Attempt to generate stream URL with negative timecode
        with pytest.raises(ValueError) as exc_info:
            video_service.get_video_stream_url(
                video_id="video-123",
                s3_key="videos/index-123/test.mp4",
                start_timecode=-10.0
            )
        
        assert "non-negative" in str(exc_info.value).lower()
    
    def test_get_stream_url_s3_error(self):
        """Test stream URL generation when S3 fails."""
        # Create mock S3 client that raises error
        mock_s3 = Mock(spec=S3Client)
        mock_s3.generate_presigned_url = Mock(
            side_effect=AWSServiceError("Failed to generate presigned URL")
        )
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Attempt to generate stream URL
        with pytest.raises(AWSServiceError) as exc_info:
            video_service.get_video_stream_url(
                video_id="video-123",
                s3_key="videos/index-123/test.mp4"
            )
        
        assert "Failed to generate presigned URL" in str(exc_info.value)


class TestVideoServiceDelete:
    """Tests for video deletion functionality."""
    
    def test_delete_video_success(self):
        """Test successful video deletion."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        mock_s3.delete = Mock(return_value=True)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Delete video
        result = video_service.delete_video(s3_key="videos/index-123/test.mp4")
        
        # Verify result
        assert result is True
        
        # Verify S3 client was called correctly
        mock_s3.delete.assert_called_once_with("videos/index-123/test.mp4")
    
    def test_delete_video_s3_error(self):
        """Test video deletion when S3 fails."""
        # Create mock S3 client that raises error
        mock_s3 = Mock(spec=S3Client)
        mock_s3.delete = Mock(side_effect=AWSServiceError("S3 delete failed"))
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Attempt to delete video
        with pytest.raises(AWSServiceError) as exc_info:
            video_service.delete_video(s3_key="videos/index-123/test.mp4")
        
        assert "S3 delete failed" in str(exc_info.value)


class TestVideoServiceKeyGeneration:
    """Tests for S3 key generation."""
    
    def test_generate_video_key_basic(self):
        """Test basic S3 key generation."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate key
        key = video_service._generate_video_key("index-123", "test.mp4")
        
        # Verify key format
        assert key == "videos/index-123/test.mp4"
    
    def test_generate_video_key_sanitizes_slashes(self):
        """Test that key generation sanitizes forward slashes."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate key with slashes in filename
        key = video_service._generate_video_key("index-123", "path/to/test.mp4")
        
        # Verify slashes are replaced
        assert key == "videos/index-123/path_to_test.mp4"
        assert key.count("/") == 2  # Only the two expected slashes
    
    def test_generate_video_key_sanitizes_backslashes(self):
        """Test that key generation sanitizes backslashes."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate key with backslashes in filename
        key = video_service._generate_video_key("index-123", "path\\to\\test.mp4")
        
        # Verify backslashes are replaced
        assert key == "videos/index-123/path_to_test.mp4"
        assert "\\" not in key
    
    def test_generate_video_key_with_special_characters(self):
        """Test key generation with special characters in filename."""
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate key with special characters
        key = video_service._generate_video_key("index-123", "test video (2024).mp4")
        
        # Verify key is generated (special chars are allowed in S3 keys)
        assert key == "videos/index-123/test video (2024).mp4"
        assert key.startswith("videos/index-123/")
