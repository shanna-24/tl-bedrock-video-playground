"""Property-based tests for video streaming URLs.

Feature: tl-video-playground
Property 5: Video Streaming URLs Are Valid

**Validates: Requirements 2.1, 2.2**

For any video in an index, requesting a stream URL (with or without a start 
timecode) should return a valid presigned S3 URL that includes the correct 
video key and optional start time parameter.
"""

import sys
import re
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import urlparse, parse_qs

import pytest
from hypothesis import given, strategies as st, settings, assume

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.video_service import VideoService
from aws.s3_client import S3Client
from config import Config


# Custom strategies for generating test data
@st.composite
def valid_video_id(draw):
    """Generate valid video IDs (UUIDs)."""
    # Generate UUID-like strings
    import uuid
    return str(uuid.uuid4())


@st.composite
def valid_s3_key(draw):
    """Generate valid S3 keys for videos."""
    # Generate index ID
    index_id = str(draw(st.uuids()))
    
    # Generate filename
    base_length = draw(st.integers(min_value=1, max_value=30))
    chars = st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters='-_'
    )
    base_name = draw(st.text(alphabet=chars, min_size=base_length, max_size=base_length))
    
    if not base_name.strip():
        base_name = "video"
    else:
        base_name = base_name.strip()
    
    extension = draw(st.sampled_from(['.mp4', '.mov', '.avi', '.mkv']))
    filename = f"{base_name}{extension}"
    
    # Generate S3 key in the format: videos/{index_id}/{filename}
    return f"videos/{index_id}/{filename}"


@st.composite
def valid_timecode(draw):
    """Generate valid timecodes (non-negative floats)."""
    # Generate timecodes between 0 and 3600 seconds (1 hour)
    return draw(st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False))


@st.composite
def valid_expiration(draw):
    """Generate valid expiration times in seconds."""
    # Generate expiration between 60 seconds and 7 days
    return draw(st.integers(min_value=60, max_value=604800))


class TestVideoStreamingURLProperties:
    """Property-based tests for video streaming URL generation."""
    
    @given(
        video_id=valid_video_id(),
        s3_key=valid_s3_key(),
        expiration=valid_expiration()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_stream_url_is_valid_without_timecode(
        self,
        video_id,
        s3_key,
        expiration
    ):
        """Property 5: Stream URL without timecode is a valid presigned S3 URL.
        
        **Validates: Requirements 2.1**
        
        For any video, requesting a stream URL without a start timecode should
        return a valid presigned S3 URL.
        """
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Mock presigned URL generation
        expected_url = f"https://test-bucket.s3.amazonaws.com/{s3_key}?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=test&X-Amz-Date=20240101T000000Z&X-Amz-Expires={expiration}&X-Amz-SignedHeaders=host&X-Amz-Signature=test"
        mock_s3.generate_presigned_url = Mock(return_value=expected_url)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL without timecode
        url = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=None,
            expiration=expiration
        )
        
        # Verify URL is valid
        assert url is not None, "URL should not be None"
        assert len(url) > 0, "URL should not be empty"
        assert url.startswith("https://"), "URL should start with https://"
        
        # Verify S3 client was called correctly
        mock_s3.generate_presigned_url.assert_called_once_with(
            key=s3_key,
            expiration=expiration,
            http_method="GET"
        )
        
        # Verify URL structure
        parsed = urlparse(url)
        assert parsed.scheme == "https", "URL scheme should be https"
        assert parsed.netloc, "URL should have a netloc (domain)"
        assert s3_key in parsed.path or s3_key in url, "URL should contain the S3 key"
    
    @given(
        video_id=valid_video_id(),
        s3_key=valid_s3_key(),
        start_timecode=valid_timecode(),
        expiration=valid_expiration()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_stream_url_includes_timecode(
        self,
        video_id,
        s3_key,
        start_timecode,
        expiration
    ):
        """Property 5: Stream URL with timecode includes the start time parameter.
        
        **Validates: Requirements 2.2**
        
        For any video with a start timecode, the generated URL should include
        the timecode as a fragment identifier (#t=start_time).
        """
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Mock presigned URL generation
        base_url = f"https://test-bucket.s3.amazonaws.com/{s3_key}?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=test&X-Amz-Date=20240101T000000Z&X-Amz-Expires={expiration}&X-Amz-SignedHeaders=host&X-Amz-Signature=test"
        mock_s3.generate_presigned_url = Mock(return_value=base_url)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL with timecode
        url = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=start_timecode,
            expiration=expiration
        )
        
        # Verify URL is valid
        assert url is not None, "URL should not be None"
        assert len(url) > 0, "URL should not be empty"
        assert url.startswith("https://"), "URL should start with https://"
        
        # Verify timecode is included in URL as fragment
        assert "#t=" in url, "URL should contain timecode fragment (#t=)"
        
        # Extract and verify timecode value
        fragment_match = re.search(r'#t=([0-9.eE+-]+)', url)
        assert fragment_match is not None, "URL should have valid timecode fragment"
        
        url_timecode = float(fragment_match.group(1))
        # Use relative tolerance for floating point comparison
        # Allow 0.1% relative error or 0.01 absolute error, whichever is larger
        tolerance = max(0.01, abs(start_timecode) * 0.001)
        assert abs(url_timecode - start_timecode) < tolerance, \
            f"URL timecode {url_timecode} should match requested timecode {start_timecode} (tolerance: {tolerance})"
    
    @given(
        video_id=valid_video_id(),
        s3_key=valid_s3_key(),
        expiration=valid_expiration()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_stream_url_contains_s3_key(
        self,
        video_id,
        s3_key,
        expiration
    ):
        """Property 5: Stream URL contains the correct S3 key.
        
        **Validates: Requirements 2.1**
        
        For any video, the generated stream URL should contain the S3 key
        that identifies the video file.
        """
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Mock presigned URL generation with the S3 key in the path
        expected_url = f"https://test-bucket.s3.amazonaws.com/{s3_key}?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=test&X-Amz-Date=20240101T000000Z&X-Amz-Expires={expiration}&X-Amz-SignedHeaders=host&X-Amz-Signature=test"
        mock_s3.generate_presigned_url = Mock(return_value=expected_url)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL
        url = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=None,
            expiration=expiration
        )
        
        # Verify S3 key is in the URL
        assert s3_key in url, f"URL should contain S3 key {s3_key}"
    
    @given(
        video_id=valid_video_id(),
        s3_key=valid_s3_key(),
        expiration=valid_expiration()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_stream_url_has_expiration(
        self,
        video_id,
        s3_key,
        expiration
    ):
        """Property 5: Stream URL is generated with correct expiration.
        
        **Validates: Requirements 2.1**
        
        For any video, the VideoService should request a presigned URL with
        the specified expiration time.
        """
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Mock presigned URL generation
        expected_url = f"https://test-bucket.s3.amazonaws.com/{s3_key}?X-Amz-Expires={expiration}"
        mock_s3.generate_presigned_url = Mock(return_value=expected_url)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL
        url = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=None,
            expiration=expiration
        )
        
        # Verify S3 client was called with correct expiration
        mock_s3.generate_presigned_url.assert_called_once()
        call_args = mock_s3.generate_presigned_url.call_args
        assert call_args[1]['expiration'] == expiration, \
            f"Expected expiration {expiration}, got {call_args[1]['expiration']}"
    
    @given(
        video_id=valid_video_id(),
        s3_key=valid_s3_key()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_stream_url_uses_default_expiration(
        self,
        video_id,
        s3_key
    ):
        """Property 5: Stream URL uses default expiration when not specified.
        
        **Validates: Requirements 2.1**
        
        For any video, when no expiration is specified, the VideoService
        should use the default expiration of 3600 seconds (1 hour).
        """
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Mock presigned URL generation
        expected_url = f"https://test-bucket.s3.amazonaws.com/{s3_key}?X-Amz-Expires=3600"
        mock_s3.generate_presigned_url = Mock(return_value=expected_url)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL without specifying expiration
        url = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=None
            # expiration not specified, should default to 3600
        )
        
        # Verify S3 client was called with default expiration
        mock_s3.generate_presigned_url.assert_called_once()
        call_args = mock_s3.generate_presigned_url.call_args
        assert call_args[1]['expiration'] == 3600, \
            f"Expected default expiration 3600, got {call_args[1]['expiration']}"
    
    @given(
        video_id=valid_video_id(),
        s3_key=valid_s3_key(),
        start_timecode=st.floats(min_value=-1000.0, max_value=-0.01, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_stream_url_rejects_negative_timecode(
        self,
        video_id,
        s3_key,
        start_timecode
    ):
        """Property 5: Stream URL generation rejects negative timecodes.
        
        **Validates: Requirements 2.2**
        
        For any video, requesting a stream URL with a negative start timecode
        should raise a ValueError.
        """
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Mock presigned URL generation
        expected_url = f"https://test-bucket.s3.amazonaws.com/{s3_key}"
        mock_s3.generate_presigned_url = Mock(return_value=expected_url)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Attempt to generate stream URL with negative timecode
        with pytest.raises(ValueError) as exc_info:
            video_service.get_video_stream_url(
                video_id=video_id,
                s3_key=s3_key,
                start_timecode=start_timecode
            )
        
        # Verify error message mentions non-negative requirement
        assert "non-negative" in str(exc_info.value).lower(), \
            "Error message should mention non-negative requirement"
    
    @given(
        video_id=valid_video_id(),
        s3_key=valid_s3_key(),
        start_timecode=valid_timecode()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_stream_url_timecode_is_zero_or_positive(
        self,
        video_id,
        s3_key,
        start_timecode
    ):
        """Property 5: Stream URL with valid timecode succeeds.
        
        **Validates: Requirements 2.2**
        
        For any video with a zero or positive start timecode, URL generation
        should succeed and include the timecode.
        """
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Mock presigned URL generation
        base_url = f"https://test-bucket.s3.amazonaws.com/{s3_key}"
        mock_s3.generate_presigned_url = Mock(return_value=base_url)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL with valid timecode
        url = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=start_timecode
        )
        
        # Verify URL was generated successfully
        assert url is not None
        assert len(url) > 0
        
        # Verify timecode is in URL
        if start_timecode == 0.0:
            # Zero timecode should still be included
            assert "#t=0" in url or "#t=0.0" in url
        else:
            assert "#t=" in url
    
    @given(
        video_id=valid_video_id(),
        s3_key=valid_s3_key(),
        start_timecode1=valid_timecode(),
        start_timecode2=valid_timecode()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_stream_url_different_timecodes_produce_different_urls(
        self,
        video_id,
        s3_key,
        start_timecode1,
        start_timecode2
    ):
        """Property 5: Different timecodes produce different URLs.
        
        **Validates: Requirements 2.2**
        
        For any video, requesting stream URLs with different start timecodes
        should produce different URLs (different fragment identifiers).
        """
        # Skip if timecodes are too similar (within 0.01 seconds)
        assume(abs(start_timecode1 - start_timecode2) > 0.01)
        
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Mock presigned URL generation
        base_url = f"https://test-bucket.s3.amazonaws.com/{s3_key}"
        mock_s3.generate_presigned_url = Mock(return_value=base_url)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URLs with different timecodes
        url1 = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=start_timecode1
        )
        
        url2 = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=start_timecode2
        )
        
        # Verify URLs are different
        assert url1 != url2, \
            f"URLs with different timecodes should be different: {url1} vs {url2}"
        
        # Verify both contain their respective timecodes
        assert f"#t={start_timecode1}" in url1 or f"#t={start_timecode1:.1f}" in url1
        assert f"#t={start_timecode2}" in url2 or f"#t={start_timecode2:.1f}" in url2
    
    @given(
        video_id=valid_video_id(),
        s3_key=valid_s3_key()
    )
    @settings(max_examples=100, deadline=None)
    def test_property_stream_url_without_timecode_has_no_fragment(
        self,
        video_id,
        s3_key
    ):
        """Property 5: Stream URL without timecode has no fragment identifier.
        
        **Validates: Requirements 2.1**
        
        For any video without a start timecode, the generated URL should not
        contain a fragment identifier (#t=).
        """
        # Create mock S3 client
        mock_s3 = Mock(spec=S3Client)
        
        # Mock presigned URL generation
        expected_url = f"https://test-bucket.s3.amazonaws.com/{s3_key}?X-Amz-Signature=test"
        mock_s3.generate_presigned_url = Mock(return_value=expected_url)
        
        # Create mock config
        mock_config = Mock(spec=Config)
        
        # Create VideoService
        video_service = VideoService(s3_client=mock_s3, config=mock_config)
        
        # Generate stream URL without timecode
        url = video_service.get_video_stream_url(
            video_id=video_id,
            s3_key=s3_key,
            start_timecode=None
        )
        
        # Verify URL does not contain fragment identifier
        assert "#t=" not in url, \
            "URL without timecode should not contain #t= fragment"
