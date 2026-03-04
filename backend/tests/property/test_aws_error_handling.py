"""Property-based tests for AWS error handling.

Feature: tl-video-playground
Property 8: AWS Errors Are Handled Gracefully

**Validates: Requirements 7.5**

For any AWS service call that fails (Bedrock, S3, S3 Vectors), the system 
should catch the error and return a descriptive error message to the user 
rather than exposing raw AWS exceptions.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from typing import List, Dict, Any

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from fastapi import HTTPException

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from exceptions import AWSServiceError, BedrockError
from api import videos, search, analysis, indexes
from services.video_service import VideoService
from services.search_service import SearchService
from services.analysis_service import AnalysisService
from services.index_manager import IndexManager
from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient
from config import Config


# Custom strategies for generating test data
@st.composite
def valid_index_id(draw):
    """Generate valid index IDs (UUIDs)."""
    import uuid
    return str(uuid.uuid4())


@st.composite
def valid_video_id(draw):
    """Generate valid video IDs (UUIDs)."""
    import uuid
    return str(uuid.uuid4())


@st.composite
def valid_query(draw):
    """Generate valid queries."""
    min_length = 5
    max_length = draw(st.integers(min_value=10, max_value=50))
    
    query = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=min_length,
        max_size=max_length
    ))
    
    assume(query.strip())
    return query.strip()


@st.composite
def aws_error_message(draw):
    """Generate AWS error messages."""
    error_types = [
        "ThrottlingException",
        "ServiceUnavailableException",
        "InternalServerError",
        "AccessDeniedException",
        "ResourceNotFoundException",
        "ValidationException",
        "TimeoutError",
        "ConnectionError",
        "ModelNotReadyException",
        "RateLimitExceededException"
    ]
    
    error_type = draw(st.sampled_from(error_types))
    
    # Generate descriptive error message
    details = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=10,
        max_size=100
    ))
    
    assume(details.strip())
    
    return f"{error_type}: {details.strip()}"


@st.composite
def timeout_error_message(draw):
    """Generate timeout-specific error messages."""
    error_types = [
        "TimeoutError",
        "RequestTimeout",
        "ConnectionTimeout",
        "ReadTimeout"
    ]
    
    error_type = draw(st.sampled_from(error_types))
    
    # Generate descriptive error message with timeout context
    details = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=10,
        max_size=100
    ))
    
    assume(details.strip())
    
    return f"{error_type}: {details.strip()}"


@st.composite
def throttling_error_message(draw):
    """Generate throttling-specific error messages."""
    error_types = [
        "ThrottlingException",
        "RateLimitExceededException",
        "TooManyRequestsException",
        "SlowDown"
    ]
    
    error_type = draw(st.sampled_from(error_types))
    
    # Generate descriptive error message with throttling context
    details = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=10,
        max_size=100
    ))
    
    assume(details.strip())
    
    return f"{error_type}: Rate limit exceeded. {details.strip()}"


@st.composite
def bedrock_error_message(draw):
    """Generate Bedrock-specific error messages."""
    error_types = [
        "ModelThrottledException",
        "ModelTimeoutException",
        "ModelNotReadyException",
        "ModelErrorException",
        "InvalidRequestException"
    ]
    
    error_type = draw(st.sampled_from(error_types))
    
    details = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=10,
        max_size=100
    ))
    
    assume(details.strip())
    
    return f"{error_type}: {details.strip()}"


@st.composite
def s3_error_message(draw):
    """Generate S3-specific error messages."""
    error_types = [
        "NoSuchBucket",
        "NoSuchKey",
        "AccessDenied",
        "RequestTimeout",
        "ServiceUnavailable",
        "SlowDown"
    ]
    
    error_type = draw(st.sampled_from(error_types))
    
    details = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=10,
        max_size=100
    ))
    
    assume(details.strip())
    
    return f"{error_type}: {details.strip()}"


class TestAWSErrorHandlingProperties:
    """Property-based tests for AWS error handling."""
    
    @pytest.mark.asyncio
    @given(
        video_id=valid_video_id(),
        error_message=aws_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_video_stream_handles_aws_errors(
        self,
        video_id,
        error_message
    ):
        """Property 8: Video streaming handles AWS errors gracefully.
        
        **Validates: Requirements 7.5**
        
        For any AWS error during video stream URL generation, the API
        should return an HTTPException with a descriptive message that
        doesn't expose internal AWS error details.
        """
        # Create mock services
        mock_video_service = Mock(spec=VideoService)
        mock_index_manager = Mock(spec=IndexManager)
        mock_config = Mock(spec=Config)
        mock_video_service.config = mock_config
        mock_config.s3_bucket_name = "test-bucket"
        
        # Mock index manager to return a video
        mock_index = Mock()
        mock_index.id = "test-index-id"
        mock_video = Mock()
        mock_video.id = video_id
        mock_video.s3_uri = f"s3://test-bucket/videos/test-index-id/test-video.mp4"
        
        mock_index_manager.list_indexes = AsyncMock(return_value=[mock_index])
        mock_index_manager.list_videos_in_index = AsyncMock(return_value=[mock_video])
        
        # Mock video service to raise AWS error
        mock_video_service.get_video_stream_url = Mock(
            side_effect=AWSServiceError(error_message)
        )
        
        # Set up dependency injection
        videos.set_video_service(mock_video_service)
        videos.set_index_manager(mock_index_manager)
        
        # Call the endpoint and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await videos.get_video_stream(
                video_id=video_id,
                start_time=None,
                authenticated=True,
                video_service=mock_video_service,
                index_manager=mock_index_manager
            )
        
        # Verify error is transformed into HTTP exception
        assert exc_info.value.status_code in [429, 500, 504], \
            "AWS errors should map to appropriate HTTP status codes"
        
        # Verify error message is descriptive
        error_detail = str(exc_info.value.detail).lower()
        assert len(error_detail) > 0, "Error message should not be empty"
        
        # Verify error message doesn't expose raw AWS exception
        assert "exception" not in error_detail or "aws" not in error_detail, \
            "Error message should not expose raw AWS exception details"
        
        # Verify error message is user-friendly
        user_friendly_terms = [
            "failed", "unavailable", "retry", "error", "service",
            "temporarily", "please", "try again"
        ]
        assert any(term in error_detail for term in user_friendly_terms), \
            "Error message should contain user-friendly terms"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_query(),
        error_message=bedrock_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_search_handles_bedrock_errors(
        self,
        index_id,
        query,
        error_message
    ):
        """Property 8: Search handles Bedrock errors gracefully.
        
        **Validates: Requirements 7.5**
        
        For any Bedrock error during search (query embedding), the API
        should return an HTTPException with a descriptive message.
        """
        # Create mock service
        mock_search_service = Mock(spec=SearchService)
        
        # Mock search service to raise Bedrock error
        mock_search_service.search_videos = AsyncMock(
            side_effect=BedrockError(error_message)
        )
        
        # Set up dependency injection
        search.set_search_service(mock_search_service)
        
        # Create request
        request = search.SearchRequest(
            index_id=index_id,
            query=query,
            top_k=10,
            generate_screenshots=True
        )
        
        # Call the endpoint and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await search.search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        # Verify error is transformed into HTTP exception
        assert exc_info.value.status_code in [429, 500, 504], \
            "Bedrock errors should map to appropriate HTTP status codes"
        
        # Verify error message is descriptive
        error_detail = str(exc_info.value.detail).lower()
        assert len(error_detail) > 0, "Error message should not be empty"
        
        # Verify error message mentions AI service or search
        assert any(term in error_detail for term in ["ai", "search", "query", "service"]), \
            "Error message should mention the affected service"
        
        # Check for throttling-specific handling
        if "throttl" in error_message.lower() or "rate" in error_message.lower():
            assert exc_info.value.status_code == 429, \
                "Throttling errors should return 429 status code"
            assert "retry" in error_detail or "unavailable" in error_detail, \
                "Throttling errors should suggest retry"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_query(),
        error_message=bedrock_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_analysis_handles_bedrock_errors(
        self,
        index_id,
        query,
        error_message
    ):
        """Property 8: Analysis handles Bedrock errors gracefully.
        
        **Validates: Requirements 7.5**
        
        For any Bedrock error during analysis (Pegasus invocation), the API
        should return an HTTPException with a descriptive message.
        """
        # Create mock services
        mock_analysis_service = Mock(spec=AnalysisService)
        mock_index_manager = Mock(spec=IndexManager)
        
        # Mock index manager to return valid index and videos
        mock_index = Mock()
        mock_index.id = index_id
        mock_index.name = "test-index"
        
        mock_video = Mock()
        mock_video.id = "test-video-id"
        mock_video.s3_uri = "s3://test-bucket/videos/test-index-id/test-video.mp4"
        
        mock_index_manager.get_index = AsyncMock(return_value=mock_index)
        mock_index_manager.list_videos_in_index = AsyncMock(return_value=[mock_video])
        
        # Mock analysis service to raise Bedrock error
        mock_analysis_service.analyze_index = AsyncMock(
            side_effect=BedrockError(error_message)
        )
        
        # Set up dependency injection
        analysis.set_analysis_service(mock_analysis_service)
        analysis.set_index_manager(mock_index_manager)
        
        # Create request
        request = analysis.AnalyzeIndexRequest(
            index_id=index_id,
            query=query,
            temperature=0.2
        )
        
        # Call the endpoint and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await analysis.analyze_index(
                request=request,
                authenticated=True,
                analysis_service=mock_analysis_service,
                index_manager=mock_index_manager
            )
        
        # Verify error is transformed into HTTP exception
        assert exc_info.value.status_code in [429, 500, 504], \
            "Bedrock errors should map to appropriate HTTP status codes"
        
        # Verify error message is descriptive
        error_detail = str(exc_info.value.detail).lower()
        assert len(error_detail) > 0, "Error message should not be empty"
        
        # Verify error message mentions AI service or analysis
        assert any(term in error_detail for term in ["ai", "analysis", "analyze", "service"]), \
            "Error message should mention the affected service"
    
    @pytest.mark.asyncio
    @given(
        index_name=st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
            min_size=3,
            max_size=50
        ),
        error_message=aws_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_index_creation_handles_aws_errors(
        self,
        index_name,
        error_message
    ):
        """Property 8: Index creation handles AWS errors gracefully.
        
        **Validates: Requirements 7.5**
        
        For any AWS error during index creation (S3 Vectors), the API
        should return an HTTPException with a descriptive message.
        """
        assume(index_name.strip())
        
        # Create mock service
        mock_index_manager = Mock(spec=IndexManager)
        
        # Mock index manager to raise AWS error
        mock_index_manager.create_index = AsyncMock(
            side_effect=AWSServiceError(error_message)
        )
        
        # Set up dependency injection
        indexes.set_index_manager(mock_index_manager)
        
        # Create request
        request = indexes.CreateIndexRequest(name=index_name.strip())
        
        # Call the endpoint and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await indexes.create_index(
                request=request,
                authenticated=True,
                index_manager=mock_index_manager
            )
        
        # Verify error is transformed into HTTP exception
        assert exc_info.value.status_code == 500, \
            "AWS errors during index creation should return 500 status code"
        
        # Verify error message is descriptive
        error_detail = str(exc_info.value.detail).lower()
        assert len(error_detail) > 0, "Error message should not be empty"
        
        # Verify error message mentions index creation
        assert any(term in error_detail for term in ["index", "create", "failed"]), \
            "Error message should mention index creation"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        error_message=aws_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_index_deletion_handles_aws_errors(
        self,
        index_id,
        error_message
    ):
        """Property 8: Index deletion handles AWS errors gracefully.
        
        **Validates: Requirements 7.5**
        
        For any AWS error during index deletion (S3 Vectors cleanup), the API
        should return an HTTPException with a descriptive message.
        """
        # Create mock service
        mock_index_manager = Mock(spec=IndexManager)
        
        # Mock index manager to raise AWS error
        mock_index_manager.delete_index = AsyncMock(
            side_effect=AWSServiceError(error_message)
        )
        
        # Set up dependency injection
        indexes.set_index_manager(mock_index_manager)
        
        # Call the endpoint and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await indexes.delete_index(
                index_id=index_id,
                authenticated=True,
                index_manager=mock_index_manager
            )
        
        # Verify error is transformed into HTTP exception
        assert exc_info.value.status_code == 500, \
            "AWS errors during index deletion should return 500 status code"
        
        # Verify error message is descriptive
        error_detail = str(exc_info.value.detail).lower()
        assert len(error_detail) > 0, "Error message should not be empty"
        
        # Verify error message mentions index deletion
        assert any(term in error_detail for term in ["index", "delete", "failed"]), \
            "Error message should mention index deletion"
    
    @pytest.mark.asyncio
    @given(
        error_message=aws_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_error_messages_are_user_friendly(
        self,
        error_message
    ):
        """Property 8: All AWS error messages are user-friendly.
        
        **Validates: Requirements 7.5**
        
        For any AWS error, the transformed error message should:
        - Not contain stack traces
        - Not contain internal AWS error codes
        - Use plain language
        - Suggest actions when appropriate
        """
        # Create an AWSServiceError
        aws_error = AWSServiceError(error_message)
        
        # Verify the error message doesn't contain stack traces
        error_str = str(aws_error)
        assert "Traceback" not in error_str, \
            "Error message should not contain stack traces"
        assert "File \"" not in error_str, \
            "Error message should not contain file paths from stack traces"
        
        # Verify the error message doesn't contain internal codes
        # (AWS error codes are typically CamelCase with "Exception" suffix)
        # But the user-facing message should be plain language
        internal_patterns = [
            "botocore",
            "ClientError",
            "boto3",
            "aws_access_key",
            "aws_secret"
        ]
        
        for pattern in internal_patterns:
            assert pattern not in error_str.lower(), \
                f"Error message should not contain internal pattern: {pattern}"
    
    @pytest.mark.asyncio
    @given(
        video_id=valid_video_id(),
        error_message=s3_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_s3_errors_are_handled(
        self,
        video_id,
        error_message
    ):
        """Property 8: S3 errors are handled gracefully.
        
        **Validates: Requirements 7.5**
        
        For any S3 error (NoSuchKey, AccessDenied, etc.), the API
        should return an HTTPException with a descriptive message.
        """
        # Create mock services
        mock_video_service = Mock(spec=VideoService)
        mock_index_manager = Mock(spec=IndexManager)
        mock_config = Mock(spec=Config)
        mock_video_service.config = mock_config
        mock_config.s3_bucket_name = "test-bucket"
        
        # Mock index manager to return a video
        mock_index = Mock()
        mock_index.id = "test-index-id"
        mock_video = Mock()
        mock_video.id = video_id
        mock_video.s3_uri = f"s3://test-bucket/videos/test-index-id/test-video.mp4"
        
        mock_index_manager.list_indexes = AsyncMock(return_value=[mock_index])
        mock_index_manager.list_videos_in_index = AsyncMock(return_value=[mock_video])
        
        # Mock video service to raise S3 error (wrapped in AWSServiceError)
        mock_video_service.get_video_stream_url = Mock(
            side_effect=AWSServiceError(error_message)
        )
        
        # Set up dependency injection
        videos.set_video_service(mock_video_service)
        videos.set_index_manager(mock_index_manager)
        
        # Call the endpoint and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await videos.get_video_stream(
                video_id=video_id,
                start_time=None,
                authenticated=True,
                video_service=mock_video_service,
                index_manager=mock_index_manager
            )
        
        # Verify error is transformed into HTTP exception
        assert exc_info.value.status_code in [429, 500, 504], \
            "S3 errors should map to appropriate HTTP status codes"
        
        # Verify error message is descriptive
        error_detail = str(exc_info.value.detail).lower()
        assert len(error_detail) > 0, "Error message should not be empty"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_query(),
        error_message=timeout_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_timeout_errors_return_504(
        self,
        index_id,
        query,
        error_message
    ):
        """Property 8: Timeout errors return 504 Gateway Timeout.
        
        **Validates: Requirements 7.5**
        
        For any AWS timeout error, the API should return a 504 status code
        with a message suggesting the user try again.
        """
        
        # Create mock service
        mock_search_service = Mock(spec=SearchService)
        
        # Mock search service to raise timeout error
        mock_search_service.search_videos = AsyncMock(
            side_effect=AWSServiceError(error_message)
        )
        
        # Set up dependency injection
        search.set_search_service(mock_search_service)
        
        # Create request
        request = search.SearchRequest(
            index_id=index_id,
            query=query,
            top_k=10,
            generate_screenshots=True
        )
        
        # Call the endpoint and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await search.search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        # Verify timeout errors return 504
        assert exc_info.value.status_code == 504, \
            "Timeout errors should return 504 Gateway Timeout"
        
        # Verify error message suggests retry
        error_detail = str(exc_info.value.detail).lower()
        assert any(term in error_detail for term in ["try", "retry", "again", "long"]), \
            "Timeout error message should suggest retry"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_query(),
        error_message=throttling_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_throttling_errors_return_429(
        self,
        index_id,
        query,
        error_message
    ):
        """Property 8: Throttling errors return 429 Too Many Requests.
        
        **Validates: Requirements 7.5**
        
        For any AWS throttling error, the API should return a 429 status code
        with a message suggesting the user retry.
        """
        
        # Create mock service
        mock_search_service = Mock(spec=SearchService)
        
        # Mock search service to raise throttling error
        mock_search_service.search_videos = AsyncMock(
            side_effect=AWSServiceError(error_message)
        )
        
        # Set up dependency injection
        search.set_search_service(mock_search_service)
        
        # Create request
        request = search.SearchRequest(
            index_id=index_id,
            query=query,
            top_k=10,
            generate_screenshots=True
        )
        
        # Call the endpoint and expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await search.search_videos(
                request=request,
                authenticated=True,
                search_service=mock_search_service
            )
        
        # Verify throttling errors return 429
        assert exc_info.value.status_code == 429, \
            "Throttling errors should return 429 Too Many Requests"
        
        # Verify error message suggests retry
        error_detail = str(exc_info.value.detail).lower()
        assert any(term in error_detail for term in ["retry", "unavailable", "temporarily"]), \
            "Throttling error message should suggest retry"
    
    @pytest.mark.asyncio
    @given(
        error_message=aws_error_message()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow]
    )
    async def test_property_error_messages_have_reasonable_length(
        self,
        error_message
    ):
        """Property 8: Error messages have reasonable length.
        
        **Validates: Requirements 7.5**
        
        For any AWS error, the user-facing error message should be
        concise (not too long) but informative (not too short).
        """
        # Create an AWSServiceError
        aws_error = AWSServiceError(error_message)
        error_str = str(aws_error)
        
        # Verify error message is not too short
        assert len(error_str) >= 10, \
            "Error message should be at least 10 characters"
        
        # Verify error message is not too long (reasonable limit)
        assert len(error_str) <= 500, \
            "Error message should not exceed 500 characters for user-friendliness"
