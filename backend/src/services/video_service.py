"""Video service for handling video storage and streaming.

This module provides the VideoService class for managing video uploads,
streaming URL generation, and video deletion operations.

Validates: Requirements 2.1, 2.2
"""

import logging
import subprocess
import tempfile
from typing import BinaryIO, Optional
from urllib.parse import urlencode

from config import Config
from aws.s3_client import S3Client
from exceptions import AWSServiceError
from utils.ffmpeg import get_ffprobe_path

logger = logging.getLogger(__name__)


class VideoService:
    """Handles video storage and streaming operations.
    
    This service manages video file operations including upload to S3,
    generating presigned URLs for streaming (with optional start timecode),
    and video deletion.
    
    Attributes:
        s3: S3Client instance for S3 operations
        config: Configuration object
    """
    
    def __init__(self, s3_client: S3Client, config: Config):
        """Initialize the VideoService.
        
        Args:
            s3_client: S3Client instance for S3 operations
            config: Configuration object with system settings
        """
        self.s3 = s3_client
        self.config = config
        logger.info("Initialized VideoService")
    
    def upload_video(
        self,
        file: BinaryIO,
        index_id: str,
        filename: str,
        content_type: Optional[str] = None
    ) -> tuple[str, float]:
        """Upload a video file to S3 and extract its duration.
        
        Args:
            file: File-like object containing video data
            index_id: ID of the index this video belongs to
            filename: Original filename of the video
            content_type: MIME type of the video (e.g., "video/mp4")
        
        Returns:
            Tuple of (S3 URI of the uploaded video, duration in seconds)
        
        Raises:
            AWSServiceError: If the upload fails
        """
        import tempfile
        import os
        
        try:
            # Save uploaded file to temporary location to extract duration
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp_file:
                tmp_path = tmp_file.name
                # Write uploaded file to temp
                file.seek(0)
                tmp_file.write(file.read())
                tmp_file.flush()
            
            try:
                # Extract video duration using ffprobe
                duration = self._extract_video_duration(tmp_path)
                logger.info(f"Extracted video duration: {duration} seconds")
            except Exception as e:
                logger.warning(f"Failed to extract video duration: {e}. Using default 60 seconds.")
                duration = 60.0
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            
            # Generate S3 key for the video
            key = self._generate_video_key(index_id, filename)
            
            logger.info(f"Uploading video {filename} to index {index_id}")
            
            # Upload to S3 with metadata including duration
            metadata = {
                "index_id": index_id,
                "original_filename": filename,
                "duration": str(duration)
            }
            
            # Reset file pointer before upload
            file.seek(0)
            
            s3_uri = self.s3.upload(
                file_obj=file,
                key=key,
                content_type=content_type or "video/mp4",
                metadata=metadata
            )
            
            logger.info(f"Successfully uploaded video to {s3_uri} with duration {duration}s")
            return s3_uri, duration
            
        except AWSServiceError:
            # Re-raise AWS service errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error uploading video: {e}")
            raise AWSServiceError(
                f"Failed to upload video: {str(e)}"
            ) from e
    
    def get_video_stream_url(
        self,
        video_id: str,
        s3_key: str,
        start_timecode: Optional[float] = None,
        expiration: int = 3600
    ) -> str:
        """Generate a presigned URL for video streaming.
        
        This method generates a presigned S3 URL that allows temporary access
        to the video file for streaming. Optionally includes a start timecode
        parameter for playback from a specific point in the video.
        
        Args:
            video_id: ID of the video
            s3_key: S3 object key for the video
            start_timecode: Optional start time in seconds for video playback
            expiration: URL expiration time in seconds (default: 3600 = 1 hour)
        
        Returns:
            Presigned URL string for video streaming
        
        Raises:
            AWSServiceError: If URL generation fails
        """
        try:
            logger.info(
                f"Generating stream URL for video {video_id} "
                f"(start_timecode: {start_timecode})"
            )
            
            # Generate base presigned URL
            url = self.s3.generate_presigned_url(
                key=s3_key,
                expiration=expiration,
                http_method="GET"
            )
            
            # Add start timecode parameter if provided
            # Note: The start_time parameter is typically handled by the video player
            # on the client side, but we include it in the URL for convenience
            if start_timecode is not None:
                # Validate start_timecode
                if start_timecode < 0:
                    raise ValueError("start_timecode must be non-negative")
                
                # Add fragment identifier for HTML5 video players
                # Format: #t=start_time
                url = f"{url}#t={start_timecode}"
            
            logger.info(f"Generated stream URL for video {video_id}")
            return url
            
        except AWSServiceError:
            # Re-raise AWS service errors
            raise
        except ValueError as e:
            logger.error(f"Invalid start_timecode: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating stream URL: {e}")
            raise AWSServiceError(
                f"Failed to generate video stream URL: {str(e)}"
            ) from e
    
    def delete_video(self, s3_key: str) -> bool:
        """Delete a video file from S3.
        
        Args:
            s3_key: S3 object key for the video
        
        Returns:
            True if the video was deleted successfully
        
        Raises:
            AWSServiceError: If the delete operation fails
        """
        try:
            logger.info(f"Deleting video with key {s3_key}")
            
            result = self.s3.delete(s3_key)
            
            logger.info(f"Successfully deleted video {s3_key}")
            return result
            
        except AWSServiceError:
            # Re-raise AWS service errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting video: {e}")
            raise AWSServiceError(
                f"Failed to delete video: {str(e)}"
            ) from e
    
    def _generate_video_key(self, index_id: str, filename: str) -> str:
        """Generate S3 key for a video file.
        
        The key format is: videos/{index_id}/{filename}
        
        Args:
            index_id: ID of the index
            filename: Original filename
        
        Returns:
            S3 object key string
        """
        # Sanitize filename to prevent path traversal
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        
        key = f"videos/{index_id}/{safe_filename}"
        logger.debug(f"Generated S3 key: {key}")
        
        return key

    def _extract_video_duration(self, video_path: str) -> float:
        """Extract video duration using ffprobe.
        
        Args:
            video_path: Path to the video file
        
        Returns:
            Duration in seconds as a float
        
        Raises:
            Exception: If duration extraction fails
        """
        import subprocess
        
        try:
            # Use ffprobe to get duration
            result = subprocess.run(
                [
                    get_ffprobe_path(),
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                return duration
            else:
                raise Exception(f"ffprobe failed: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error extracting video duration: {e}")
            raise
