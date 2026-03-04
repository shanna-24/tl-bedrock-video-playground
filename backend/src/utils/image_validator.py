"""Image validation utilities for multimodal search.

This module provides validation for image inputs in search requests,
including format, size, and dimension checks.

Validates: Requirements 1.2, 1.3, 1.4, 4.1, 4.2, 4.3, 4.4
"""

import base64
import logging
from io import BytesIO
from typing import Set

from PIL import Image

from exceptions import ValidationError

logger = logging.getLogger(__name__)


class ImageValidator:
    """Validates image inputs for search requests.
    
    This class provides static methods to validate images based on:
    - File format (JPEG, PNG, WebP)
    - File size (max 10MB)
    - Image dimensions (min 100x100, max 4096x4096 pixels)
    
    Attributes:
        MAX_SIZE_BYTES: Maximum allowed image size in bytes (10MB)
        MIN_DIMENSION: Minimum allowed dimension in pixels (100)
        MAX_DIMENSION: Maximum allowed dimension in pixels (4096)
        SUPPORTED_FORMATS: Set of supported image format strings
    """
    
    MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
    MIN_DIMENSION = 100
    MAX_DIMENSION = 4096
    SUPPORTED_FORMATS: Set[str] = {"jpeg", "jpg", "png", "webp"}
    
    @staticmethod
    def validate_image(image_base64: str, image_format: str) -> bytes:
        """Validate and decode image data.
        
        Performs comprehensive validation including:
        1. Base64 decoding
        2. Size validation (max 10MB)
        3. Format validation (JPEG, PNG, WebP)
        4. Dimension validation (100x100 to 4096x4096)
        
        Args:
            image_base64: Base64-encoded image string
            image_format: Image format (jpeg, jpg, png, webp)
            
        Returns:
            Decoded image bytes
            
        Raises:
            ValidationError: If image validation fails with specific error message
        """
        # Validate format first (before decoding)
        if not image_format or image_format.lower() not in ImageValidator.SUPPORTED_FORMATS:
            supported = ", ".join(sorted(ImageValidator.SUPPORTED_FORMATS))
            raise ValidationError(
                f"Unsupported image format: {image_format} (supported: {supported})"
            )
        
        # Decode base64
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception as e:
            logger.warning(f"Failed to decode base64 image: {e}")
            raise ValidationError("Invalid or corrupted image data")
        
        # Validate size
        size_mb = len(image_bytes) / (1024 * 1024)
        if len(image_bytes) > ImageValidator.MAX_SIZE_BYTES:
            raise ValidationError(
                f"Image size exceeds 10MB limit (received: {size_mb:.1f}MB)"
            )
        
        # Validate image can be opened and get dimensions
        try:
            image = Image.open(BytesIO(image_bytes))
            width, height = image.size
        except Exception as e:
            logger.warning(f"Failed to open image: {e}")
            raise ValidationError("Invalid or corrupted image data")
        
        # Validate dimensions (minimum)
        if width < ImageValidator.MIN_DIMENSION or height < ImageValidator.MIN_DIMENSION:
            raise ValidationError(
                f"Image dimensions too small: {width}x{height} "
                f"(minimum: {ImageValidator.MIN_DIMENSION}x{ImageValidator.MIN_DIMENSION})"
            )
        
        # Validate dimensions (maximum)
        if width > ImageValidator.MAX_DIMENSION or height > ImageValidator.MAX_DIMENSION:
            raise ValidationError(
                f"Image dimensions too large: {width}x{height} "
                f"(maximum: {ImageValidator.MAX_DIMENSION}x{ImageValidator.MAX_DIMENSION})"
            )
        
        logger.debug(f"Image validation passed: {width}x{height}, {size_mb:.2f}MB, format={image_format}")
        
        return image_bytes
