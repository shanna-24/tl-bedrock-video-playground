"""Media validator for video and audio files.

This module provides validation for video and audio files used in search queries.
"""

import base64
import logging
from typing import Tuple

from exceptions import ValidationError

logger = logging.getLogger(__name__)


class MediaValidator:
    """Validator for video and audio media files."""
    
    # Supported video formats
    SUPPORTED_VIDEO_FORMATS = {
        'mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', 'm4v'
    }
    
    # Supported audio formats
    SUPPORTED_AUDIO_FORMATS = {
        'mp3', 'wav', 'aac', 'm4a', 'flac', 'ogg', 'wma'
    }
    
    # Maximum file size: 25MB (Bedrock limit for InvokeModel)
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB in bytes
    
    # Maximum duration: 10 seconds
    MAX_DURATION_SEC = 10.0
    
    @staticmethod
    def validate_video(
        video_base64: str,
        video_format: str
    ) -> bytes:
        """Validate and decode a base64-encoded video file.
        
        Args:
            video_base64: Base64-encoded video data
            video_format: Video format (e.g., 'mp4', 'mov')
        
        Returns:
            Decoded video bytes
        
        Raises:
            ValidationError: If validation fails
        """
        # Validate format
        video_format = video_format.lower().strip()
        if video_format not in MediaValidator.SUPPORTED_VIDEO_FORMATS:
            raise ValidationError(
                f"Unsupported video format: {video_format}. "
                f"Supported formats: {', '.join(sorted(MediaValidator.SUPPORTED_VIDEO_FORMATS))}"
            )
        
        # Validate base64 string
        if not video_base64 or not isinstance(video_base64, str):
            raise ValidationError("Video data must be a non-empty base64 string")
        
        # Decode base64
        try:
            video_bytes = base64.b64decode(video_base64)
        except Exception as e:
            logger.error(f"Failed to decode video base64: {e}")
            raise ValidationError(f"Invalid base64 encoding: {str(e)}")
        
        # Validate size
        video_size = len(video_bytes)
        if video_size == 0:
            raise ValidationError("Video file is empty")
        
        if video_size > MediaValidator.MAX_FILE_SIZE:
            size_mb = video_size / (1024 * 1024)
            max_mb = MediaValidator.MAX_FILE_SIZE / (1024 * 1024)
            raise ValidationError(
                f"Video file too large: {size_mb:.2f}MB. "
                f"Maximum allowed: {max_mb:.0f}MB"
            )
        
        logger.info(
            f"Validated video: format={video_format}, "
            f"size={video_size / 1024:.2f}KB"
        )
        
        return video_bytes
    
    @staticmethod
    def validate_audio(
        audio_base64: str,
        audio_format: str
    ) -> bytes:
        """Validate and decode a base64-encoded audio file.
        
        Args:
            audio_base64: Base64-encoded audio data
            audio_format: Audio format (e.g., 'mp3', 'wav')
        
        Returns:
            Decoded audio bytes
        
        Raises:
            ValidationError: If validation fails
        """
        # Validate format
        audio_format = audio_format.lower().strip()
        if audio_format not in MediaValidator.SUPPORTED_AUDIO_FORMATS:
            raise ValidationError(
                f"Unsupported audio format: {audio_format}. "
                f"Supported formats: {', '.join(sorted(MediaValidator.SUPPORTED_AUDIO_FORMATS))}"
            )
        
        # Validate base64 string
        if not audio_base64 or not isinstance(audio_base64, str):
            raise ValidationError("Audio data must be a non-empty base64 string")
        
        # Decode base64
        try:
            audio_bytes = base64.b64decode(audio_base64)
        except Exception as e:
            logger.error(f"Failed to decode audio base64: {e}")
            raise ValidationError(f"Invalid base64 encoding: {str(e)}")
        
        # Validate size
        audio_size = len(audio_bytes)
        if audio_size == 0:
            raise ValidationError("Audio file is empty")
        
        if audio_size > MediaValidator.MAX_FILE_SIZE:
            size_mb = audio_size / (1024 * 1024)
            max_mb = MediaValidator.MAX_FILE_SIZE / (1024 * 1024)
            raise ValidationError(
                f"Audio file too large: {size_mb:.2f}MB. "
                f"Maximum allowed: {max_mb:.0f}MB"
            )
        
        logger.info(
            f"Validated audio: format={audio_format}, "
            f"size={audio_size / 1024:.2f}KB"
        )
        
        return audio_bytes
