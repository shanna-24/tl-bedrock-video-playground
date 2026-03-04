"""Property-based tests for analysis results structure.

Feature: tl-video-playground
Property 7: Analysis Returns Structured Results

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

For any analysis request (whether for an entire index or a single video) 
with a natural language query, the system should return an AnalysisResult 
object with the query, scope, scope_id, insights text, and timestamp.
"""

import sys
import re
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from typing import List, Dict, Any

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from datetime import datetime

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.analysis_service import AnalysisService
from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from config import Config
from models.analysis import AnalysisResult


def create_mock_config():
    """Create a mock Config object with jockey disabled for testing."""
    mock_config = create_mock_config()
    mock_jockey_config = Mock()
    mock_jockey_config.enabled = False
    mock_config.jockey = mock_jockey_config
    return mock_config


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
def valid_analysis_query(draw):
    """Generate valid analysis queries."""
    # Generate non-empty text queries
    min_length = 5
    max_length = draw(st.integers(min_value=10, max_value=100))
    
    # Use printable ASCII characters
    query = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=min_length,
        max_size=max_length
    ))
    
    # Ensure query is not just whitespace
    assume(query.strip())
    
    return query.strip()


@st.composite
def valid_s3_uri(draw):
    """Generate valid S3 URIs."""
    import uuid
    
    bucket = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'),
        min_size=3,
        max_size=20
    ))
    
    index_id = str(uuid.uuid4())
    
    filename = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
        min_size=5,
        max_size=20
    ))
    
    extension = draw(st.sampled_from(['.mp4', '.mov', '.avi', '.mkv']))
    
    return f"s3://{bucket}/videos/{index_id}/{filename}{extension}"


@st.composite
def valid_s3_uri_list(draw):
    """Generate a list of valid S3 URIs."""
    num_videos = draw(st.integers(min_value=1, max_value=5))
    return draw(st.lists(
        valid_s3_uri(),
        min_size=num_videos,
        max_size=num_videos
    ))


@st.composite
def valid_pegasus_response(draw):
    """Generate valid Pegasus analysis responses."""
    # Generate non-empty insights text
    insights = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs', 'Po'),
            min_codepoint=32,
            max_codepoint=126
        ),
        min_size=10,
        max_size=500
    ))
    
    # Ensure insights is not just whitespace
    assume(insights.strip())
    
    finish_reason = draw(st.sampled_from(["stop", "length"]))
    
    return {
        "message": insights.strip(),
        "finishReason": finish_reason
    }


@st.composite
def valid_temperature(draw):
    """Generate valid temperature values."""
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


@st.composite
def valid_max_tokens(draw):
    """Generate valid max_output_tokens values."""
    return draw(st.integers(min_value=100, max_value=4096))


class TestAnalysisResultsProperties:
    """Property-based tests for analysis results structure."""
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_analysis_query(),
        video_s3_uris=valid_s3_uri_list(),
        pegasus_response=valid_pegasus_response()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_index_analysis_returns_structured_result(
        self,
        index_id,
        query,
        video_s3_uris,
        pegasus_response
    ):
        """Property 7: Index analysis returns properly structured results.
        
        **Validates: Requirements 4.1, 4.3, 4.4**
        
        For any index analysis request with a natural language query,
        the system must return an AnalysisResult with:
        - query (matches input query)
        - scope (equals "index")
        - scope_id (matches input index_id)
        - insights (non-empty string)
        - analyzed_at (valid datetime)
        - metadata (dict with video_count)
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = create_mock_config()
        
        # Mock Pegasus response
        mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Create AnalysisService
        analysis_service = AnalysisService(
            bedrock_client=mock_bedrock,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform index analysis
        result = await analysis_service.analyze_index(
            index_id=index_id,
            query=query,
            video_s3_uris=video_s3_uris
        )
        
        # Verify result is an AnalysisResult object
        assert isinstance(result, AnalysisResult), \
            "Result should be an AnalysisResult object"
        
        # Verify query is preserved
        assert result.query == query, \
            "Query should be preserved in result"
        
        # Verify scope is "index"
        assert result.scope == "index", \
            "Scope should be 'index' for index analysis"
        
        # Verify scope_id matches input
        assert result.scope_id == index_id, \
            "Scope ID should match input index_id"
        
        # Verify insights is non-empty
        assert result.insights, \
            "Insights should be non-empty"
        assert isinstance(result.insights, str), \
            "Insights should be a string"
        assert len(result.insights) > 0, \
            "Insights should not be empty"
        
        # Verify analyzed_at is a valid datetime
        assert isinstance(result.analyzed_at, datetime), \
            "analyzed_at should be a datetime object"
        
        # Verify metadata contains video_count
        assert "video_count" in result.metadata, \
            "Metadata should contain video_count"
        assert result.metadata["video_count"] == len(video_s3_uris), \
            "video_count should match number of videos"
    
    @pytest.mark.asyncio
    @given(
        video_id=valid_video_id(),
        query=valid_analysis_query(),
        video_s3_uri=valid_s3_uri(),
        pegasus_response=valid_pegasus_response()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_video_analysis_returns_structured_result(
        self,
        video_id,
        query,
        video_s3_uri,
        pegasus_response
    ):
        """Property 7: Video analysis returns properly structured results.
        
        **Validates: Requirements 4.2, 4.3, 4.4**
        
        For any video analysis request with a natural language query,
        the system must return an AnalysisResult with:
        - query (matches input query)
        - scope (equals "video")
        - scope_id (matches input video_id)
        - insights (non-empty string)
        - analyzed_at (valid datetime)
        - metadata (dict with video_s3_uri)
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = create_mock_config()
        
        # Mock Pegasus response
        mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Create AnalysisService
        analysis_service = AnalysisService(
            bedrock_client=mock_bedrock,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform video analysis
        result = await analysis_service.analyze_video(
            video_id=video_id,
            query=query,
            video_s3_uri=video_s3_uri
        )
        
        # Verify result is an AnalysisResult object
        assert isinstance(result, AnalysisResult), \
            "Result should be an AnalysisResult object"
        
        # Verify query is preserved
        assert result.query == query, \
            "Query should be preserved in result"
        
        # Verify scope is "video"
        assert result.scope == "video", \
            "Scope should be 'video' for video analysis"
        
        # Verify scope_id matches input
        assert result.scope_id == video_id, \
            "Scope ID should match input video_id"
        
        # Verify insights is non-empty
        assert result.insights, \
            "Insights should be non-empty"
        assert isinstance(result.insights, str), \
            "Insights should be a string"
        assert len(result.insights) > 0, \
            "Insights should not be empty"
        
        # Verify analyzed_at is a valid datetime
        assert isinstance(result.analyzed_at, datetime), \
            "analyzed_at should be a datetime object"
        
        # Verify metadata contains video_s3_uri
        assert "video_s3_uri" in result.metadata, \
            "Metadata should contain video_s3_uri"
        assert result.metadata["video_s3_uri"] == video_s3_uri, \
            "video_s3_uri should match input"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_analysis_query(),
        video_s3_uris=valid_s3_uri_list(),
        pegasus_response=valid_pegasus_response(),
        temperature=valid_temperature()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_analysis_respects_temperature_parameter(
        self,
        index_id,
        query,
        video_s3_uris,
        pegasus_response,
        temperature
    ):
        """Property 7: Analysis respects temperature parameter.
        
        **Validates: Requirements 4.3**
        
        For any analysis request with a temperature parameter,
        the temperature should be passed to the Pegasus model.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = create_mock_config()
        
        # Mock Pegasus response
        mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Create AnalysisService
        analysis_service = AnalysisService(
            bedrock_client=mock_bedrock,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform analysis with temperature
        result = await analysis_service.analyze_index(
            index_id=index_id,
            query=query,
            video_s3_uris=video_s3_uris,
            temperature=temperature
        )
        
        # Verify Pegasus was called with correct temperature
        call_args = mock_bedrock.invoke_pegasus_analysis.call_args
        assert call_args is not None, "Pegasus should have been called"
        assert call_args[1]["temperature"] == temperature, \
            f"Temperature should be {temperature}"
        
        # Verify result is still valid
        assert isinstance(result, AnalysisResult)
    
    @pytest.mark.asyncio
    @given(
        video_id=valid_video_id(),
        query=valid_analysis_query(),
        video_s3_uri=valid_s3_uri(),
        pegasus_response=valid_pegasus_response(),
        max_tokens=valid_max_tokens()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_analysis_respects_max_tokens_parameter(
        self,
        video_id,
        query,
        video_s3_uri,
        pegasus_response,
        max_tokens
    ):
        """Property 7: Analysis respects max_output_tokens parameter.
        
        **Validates: Requirements 4.3**
        
        For any analysis request with a max_output_tokens parameter,
        the value should be passed to the Pegasus model.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = create_mock_config()
        
        # Mock Pegasus response
        mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Create AnalysisService
        analysis_service = AnalysisService(
            bedrock_client=mock_bedrock,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform analysis with max_tokens
        result = await analysis_service.analyze_video(
            video_id=video_id,
            query=query,
            video_s3_uri=video_s3_uri,
            max_output_tokens=max_tokens
        )
        
        # Verify Pegasus was called with correct max_output_tokens
        call_args = mock_bedrock.invoke_pegasus_analysis.call_args
        assert call_args is not None, "Pegasus should have been called"
        assert call_args[1]["max_output_tokens"] == max_tokens, \
            f"max_output_tokens should be {max_tokens}"
        
        # Verify result is still valid
        assert isinstance(result, AnalysisResult)
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_analysis_query(),
        video_s3_uris=valid_s3_uri_list(),
        pegasus_response=valid_pegasus_response()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_analysis_timestamp_is_recent(
        self,
        index_id,
        query,
        video_s3_uris,
        pegasus_response
    ):
        """Property 7: Analysis timestamp is recent.
        
        **Validates: Requirements 4.4**
        
        For any analysis request, the analyzed_at timestamp should be
        close to the current time (within a few seconds).
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = create_mock_config()
        
        # Mock Pegasus response
        mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Create AnalysisService
        analysis_service = AnalysisService(
            bedrock_client=mock_bedrock,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Record time before analysis
        before_time = datetime.now()
        
        # Perform analysis
        result = await analysis_service.analyze_index(
            index_id=index_id,
            query=query,
            video_s3_uris=video_s3_uris
        )
        
        # Record time after analysis
        after_time = datetime.now()
        
        # Verify timestamp is between before and after
        assert before_time <= result.analyzed_at <= after_time, \
            "analyzed_at should be between before and after times"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        video_s3_uris=valid_s3_uri_list(),
        pegasus_response=valid_pegasus_response()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_analysis_rejects_empty_query(
        self,
        index_id,
        video_s3_uris,
        pegasus_response
    ):
        """Property 7: Analysis rejects empty queries.
        
        **Validates: Requirements 4.3**
        
        For any empty or whitespace-only query, the analysis should
        raise a ValueError.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = create_mock_config()
        
        # Create AnalysisService
        analysis_service = AnalysisService(
            bedrock_client=mock_bedrock,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Test empty string
        with pytest.raises(ValueError) as exc_info:
            await analysis_service.analyze_index(
                index_id=index_id,
                query="",
                video_s3_uris=video_s3_uris
            )
        assert "empty" in str(exc_info.value).lower()
        
        # Test whitespace-only string
        with pytest.raises(ValueError) as exc_info:
            await analysis_service.analyze_index(
                index_id=index_id,
                query="   ",
                video_s3_uris=video_s3_uris
            )
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @given(
        video_id=valid_video_id(),
        query=valid_analysis_query(),
        pegasus_response=valid_pegasus_response()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_video_analysis_rejects_invalid_s3_uri(
        self,
        video_id,
        query,
        pegasus_response
    ):
        """Property 7: Video analysis rejects invalid S3 URIs.
        
        **Validates: Requirements 4.2**
        
        For any invalid S3 URI (not starting with s3://), the video
        analysis should raise a ValueError.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = create_mock_config()
        
        # Create AnalysisService
        analysis_service = AnalysisService(
            bedrock_client=mock_bedrock,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Test invalid URI
        invalid_uris = [
            "http://example.com/video.mp4",
            "https://example.com/video.mp4",
            "/local/path/video.mp4",
            "video.mp4"
        ]
        
        for invalid_uri in invalid_uris:
            with pytest.raises(ValueError) as exc_info:
                await analysis_service.analyze_video(
                    video_id=video_id,
                    query=query,
                    video_s3_uri=invalid_uri
                )
            assert "invalid" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_analysis_query(),
        pegasus_response=valid_pegasus_response()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_index_analysis_rejects_empty_video_list(
        self,
        index_id,
        query,
        pegasus_response
    ):
        """Property 7: Index analysis rejects empty video list.
        
        **Validates: Requirements 4.1**
        
        For any index with no videos, the analysis should raise a
        ValueError.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = create_mock_config()
        
        # Create AnalysisService
        analysis_service = AnalysisService(
            bedrock_client=mock_bedrock,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Test empty video list
        with pytest.raises(ValueError) as exc_info:
            await analysis_service.analyze_index(
                index_id=index_id,
                query=query,
                video_s3_uris=[]
            )
        assert "no videos" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_analysis_query(),
        video_s3_uris=valid_s3_uri_list(),
        pegasus_response=valid_pegasus_response()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_analysis_metadata_is_dict(
        self,
        index_id,
        query,
        video_s3_uris,
        pegasus_response
    ):
        """Property 7: Analysis metadata is always a dictionary.
        
        **Validates: Requirements 4.4**
        
        For any analysis request, the metadata field should always be
        a dictionary with relevant information.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = create_mock_config()
        
        # Mock Pegasus response
        mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Create AnalysisService
        analysis_service = AnalysisService(
            bedrock_client=mock_bedrock,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform analysis
        result = await analysis_service.analyze_index(
            index_id=index_id,
            query=query,
            video_s3_uris=video_s3_uris
        )
        
        # Verify metadata is a dictionary
        assert isinstance(result.metadata, dict), \
            "Metadata should be a dictionary"
        
        # Verify metadata is not empty
        assert len(result.metadata) > 0, \
            "Metadata should not be empty"
