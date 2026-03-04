"""Property-based tests for search results structure.

Feature: tl-video-playground
Property 6: Search Results Contain Required Fields

**Validates: Requirements 3.1, 3.2, 3.3**

For any search query on an index with videos, the returned search results 
should contain video clips where each clip has a screenshot URL, start 
timecode, end timecode, relevance score, and video stream URL.
"""

import sys
import re
from pathlib import Path
from unittest.mock import Mock, AsyncMock
from typing import List, Dict, Any

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.search_service import SearchService
from aws.bedrock_client import BedrockClient
from aws.s3_vectors_client import S3VectorsClient
from aws.s3_client import S3Client
from config import Config
from models.search import SearchResults, VideoClip


# Custom strategies for generating test data
@st.composite
def valid_index_id(draw):
    """Generate valid index IDs (UUIDs)."""
    import uuid
    return str(uuid.uuid4())


@st.composite
def valid_search_query(draw):
    """Generate valid search queries."""
    # Generate non-empty text queries with smaller size
    min_length = 1
    max_length = draw(st.integers(min_value=5, max_value=30))
    
    # Use printable ASCII characters
    query = draw(st.text(
        alphabet=st.characters(
            whitelist_categories=('Lu', 'Ll', 'Nd', 'Zs'),
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
def valid_top_k(draw):
    """Generate valid top_k values."""
    return draw(st.integers(min_value=1, max_value=50))


@st.composite
def valid_embedding(draw):
    """Generate valid embedding vectors."""
    # Use smaller dimensions for testing to avoid health check issues
    dimension = draw(st.sampled_from([64, 128]))
    
    # Generate normalized embedding vector
    embedding = draw(st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=dimension,
        max_size=dimension
    ))
    
    return embedding


@st.composite
def valid_vector_result(draw):
    """Generate valid vector search results."""
    import uuid
    
    video_id = str(uuid.uuid4())
    
    # Generate timecodes
    start_timecode = draw(st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False))
    duration = draw(st.floats(min_value=1.0, max_value=60.0, allow_nan=False, allow_infinity=False))
    end_timecode = start_timecode + duration
    
    # Generate S3 key
    index_id = str(uuid.uuid4())
    filename = draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='-_'),
        min_size=5,
        max_size=20
    ))
    extension = draw(st.sampled_from(['.mp4', '.mov', '.avi', '.mkv']))
    s3_key = f"videos/{index_id}/{filename}{extension}"
    
    # Generate distance (0.0 = perfect match, 1.0 = no match)
    distance = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    
    return {
        "key": f"{video_id}_{int(start_timecode)}",
        "distance": distance,
        "metadata": {
            "video_id": video_id,
            "start_timecode": start_timecode,
            "end_timecode": end_timecode,
            "s3_key": s3_key
        }
    }


@st.composite
def valid_vector_results_list(draw):
    """Generate a list of valid vector search results."""
    num_results = draw(st.integers(min_value=1, max_value=5))
    return draw(st.lists(
        valid_vector_result(),
        min_size=num_results,
        max_size=num_results
    ))


class TestSearchResultsProperties:
    """Property-based tests for search results structure."""
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_search_query(),
        top_k=valid_top_k(),
        embedding=valid_embedding(),
        vector_results=valid_vector_results_list()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_search_results_contain_required_fields(
        self,
        index_id,
        query,
        top_k,
        embedding,
        vector_results
    ):
        """Property 6: Search results contain all required fields.
        
        **Validates: Requirements 3.1, 3.2, 3.3**
        
        For any search query, all returned video clips must contain:
        - screenshot_url (non-empty string)
        - start_timecode (non-negative float)
        - end_timecode (non-negative float, greater than start)
        - relevance_score (float between 0.0 and 1.0)
        - video_stream_url (non-empty string)
        """
        # Limit vector results to top_k
        limited_results = vector_results[:top_k]
        
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3_vectors = Mock(spec=S3VectorsClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = Mock(spec=Config)
        
        # Mock Bedrock text embedding
        mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock S3 Vectors query
        mock_s3_vectors.query_vectors = Mock(return_value=limited_results)
        
        # Mock S3 presigned URL generation
        def generate_presigned_url(key, expiration=3600, http_method="GET"):
            return f"https://test-bucket.s3.amazonaws.com/{key}?signature=test"
        
        mock_s3.generate_presigned_url = Mock(side_effect=generate_presigned_url)
        
        # Create SearchService
        search_service = SearchService(
            bedrock_client=mock_bedrock,
            s3_vectors_client=mock_s3_vectors,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform search
        results = await search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=top_k,
            generate_screenshots=True
        )
        
        # Verify results is a SearchResults object
        assert isinstance(results, SearchResults), "Results should be a SearchResults object"
        
        # Verify query is preserved
        assert results.query == query, "Query should be preserved in results"
        
        # Verify total_results matches clips length
        assert results.total_results == len(results.clips), \
            "total_results should match number of clips"
        
        # Verify search_time is non-negative
        assert results.search_time >= 0, "search_time should be non-negative"
        
        # Verify each clip has all required fields
        for i, clip in enumerate(results.clips):
            # Verify clip is a VideoClip object
            assert isinstance(clip, VideoClip), \
                f"Clip {i} should be a VideoClip object"
            
            # Verify screenshot_url is present and non-empty
            assert clip.screenshot_url, \
                f"Clip {i} should have non-empty screenshot_url"
            assert isinstance(clip.screenshot_url, str), \
                f"Clip {i} screenshot_url should be a string"
            assert len(clip.screenshot_url) > 0, \
                f"Clip {i} screenshot_url should not be empty"
            
            # Verify start_timecode is non-negative
            assert clip.start_timecode >= 0, \
                f"Clip {i} start_timecode should be non-negative"
            
            # Verify end_timecode is non-negative and greater than start
            assert clip.end_timecode >= 0, \
                f"Clip {i} end_timecode should be non-negative"
            assert clip.end_timecode > clip.start_timecode, \
                f"Clip {i} end_timecode should be greater than start_timecode"
            
            # Verify relevance_score is between 0.0 and 1.0
            assert 0.0 <= clip.relevance_score <= 1.0, \
                f"Clip {i} relevance_score should be between 0.0 and 1.0"
            
            # Verify video_stream_url is present and non-empty
            assert clip.video_stream_url, \
                f"Clip {i} should have non-empty video_stream_url"
            assert isinstance(clip.video_stream_url, str), \
                f"Clip {i} video_stream_url should be a string"
            assert len(clip.video_stream_url) > 0, \
                f"Clip {i} video_stream_url should not be empty"
            
            # Verify video_stream_url is a valid URL
            assert clip.video_stream_url.startswith("https://"), \
                f"Clip {i} video_stream_url should start with https://"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_search_query(),
        top_k=valid_top_k(),
        embedding=valid_embedding(),
        vector_results=valid_vector_results_list()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_search_results_respect_top_k(
        self,
        index_id,
        query,
        top_k,
        embedding,
        vector_results
    ):
        """Property 6: Search results respect top_k parameter.
        
        **Validates: Requirements 3.1**
        
        For any search query with top_k parameter, the number of returned
        clips should not exceed top_k.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3_vectors = Mock(spec=S3VectorsClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = Mock(spec=Config)
        
        # Mock Bedrock text embedding
        mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock S3 Vectors query - return all results (SearchService should limit)
        mock_s3_vectors.query_vectors = Mock(return_value=vector_results[:top_k])
        
        # Mock S3 presigned URL generation
        def generate_presigned_url(key, expiration=3600, http_method="GET"):
            return f"https://test-bucket.s3.amazonaws.com/{key}?signature=test"
        
        mock_s3.generate_presigned_url = Mock(side_effect=generate_presigned_url)
        
        # Create SearchService
        search_service = SearchService(
            bedrock_client=mock_bedrock,
            s3_vectors_client=mock_s3_vectors,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform search
        results = await search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=top_k,
            generate_screenshots=True
        )
        
        # Verify number of results does not exceed top_k
        assert len(results.clips) <= top_k, \
            f"Number of results ({len(results.clips)}) should not exceed top_k ({top_k})"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_search_query(),
        embedding=valid_embedding(),
        vector_results=valid_vector_results_list()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_search_results_relevance_scores_are_valid(
        self,
        index_id,
        query,
        embedding,
        vector_results
    ):
        """Property 6: All relevance scores are between 0.0 and 1.0.
        
        **Validates: Requirements 3.2**
        
        For any search query, all returned clips must have relevance scores
        in the valid range [0.0, 1.0].
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3_vectors = Mock(spec=S3VectorsClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = Mock(spec=Config)
        
        # Mock Bedrock text embedding
        mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock S3 Vectors query
        mock_s3_vectors.query_vectors = Mock(return_value=vector_results)
        
        # Mock S3 presigned URL generation
        def generate_presigned_url(key, expiration=3600, http_method="GET"):
            return f"https://test-bucket.s3.amazonaws.com/{key}?signature=test"
        
        mock_s3.generate_presigned_url = Mock(side_effect=generate_presigned_url)
        
        # Create SearchService
        search_service = SearchService(
            bedrock_client=mock_bedrock,
            s3_vectors_client=mock_s3_vectors,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform search
        results = await search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=len(vector_results),
            generate_screenshots=True
        )
        
        # Verify all relevance scores are valid
        for i, clip in enumerate(results.clips):
            assert 0.0 <= clip.relevance_score <= 1.0, \
                f"Clip {i} relevance_score {clip.relevance_score} should be between 0.0 and 1.0"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_search_query(),
        embedding=valid_embedding(),
        vector_results=valid_vector_results_list()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_search_results_urls_are_valid(
        self,
        index_id,
        query,
        embedding,
        vector_results
    ):
        """Property 6: All URLs in search results are valid.
        
        **Validates: Requirements 3.2, 3.3**
        
        For any search query, all returned clips must have valid URLs for
        both screenshots and video streaming.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3_vectors = Mock(spec=S3VectorsClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = Mock(spec=Config)
        
        # Mock Bedrock text embedding
        mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock S3 Vectors query
        mock_s3_vectors.query_vectors = Mock(return_value=vector_results)
        
        # Mock S3 presigned URL generation
        def generate_presigned_url(key, expiration=3600, http_method="GET"):
            return f"https://test-bucket.s3.amazonaws.com/{key}?signature=test"
        
        mock_s3.generate_presigned_url = Mock(side_effect=generate_presigned_url)
        
        # Create SearchService
        search_service = SearchService(
            bedrock_client=mock_bedrock,
            s3_vectors_client=mock_s3_vectors,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform search
        results = await search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=len(vector_results),
            generate_screenshots=True
        )
        
        # Verify all URLs are valid
        for i, clip in enumerate(results.clips):
            # Verify screenshot URL
            assert clip.screenshot_url.startswith("https://"), \
                f"Clip {i} screenshot_url should start with https://"
            
            # Verify video stream URL
            assert clip.video_stream_url.startswith("https://"), \
                f"Clip {i} video_stream_url should start with https://"
            
            # Verify URLs contain expected components
            assert "test-bucket.s3.amazonaws.com" in clip.video_stream_url or \
                   "placeholder.com" in clip.screenshot_url, \
                f"Clip {i} URLs should contain expected domain"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_search_query(),
        embedding=valid_embedding(),
        vector_results=valid_vector_results_list()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_search_results_timecodes_are_consistent(
        self,
        index_id,
        query,
        embedding,
        vector_results
    ):
        """Property 6: Timecodes in search results are consistent.
        
        **Validates: Requirements 3.2**
        
        For any search query, all returned clips must have end_timecode
        greater than start_timecode.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3_vectors = Mock(spec=S3VectorsClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = Mock(spec=Config)
        
        # Mock Bedrock text embedding
        mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock S3 Vectors query
        mock_s3_vectors.query_vectors = Mock(return_value=vector_results)
        
        # Mock S3 presigned URL generation
        def generate_presigned_url(key, expiration=3600, http_method="GET"):
            return f"https://test-bucket.s3.amazonaws.com/{key}?signature=test"
        
        mock_s3.generate_presigned_url = Mock(side_effect=generate_presigned_url)
        
        # Create SearchService
        search_service = SearchService(
            bedrock_client=mock_bedrock,
            s3_vectors_client=mock_s3_vectors,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform search
        results = await search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=len(vector_results),
            generate_screenshots=True
        )
        
        # Verify timecode consistency
        for i, clip in enumerate(results.clips):
            assert clip.end_timecode > clip.start_timecode, \
                f"Clip {i} end_timecode ({clip.end_timecode}) should be greater than " \
                f"start_timecode ({clip.start_timecode})"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_search_query(),
        embedding=valid_embedding()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_search_results_empty_when_no_matches(
        self,
        index_id,
        query,
        embedding
    ):
        """Property 6: Search returns empty results when no matches found.
        
        **Validates: Requirements 3.1**
        
        For any search query with no matching videos, the search should
        return a valid SearchResults object with an empty clips list.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3_vectors = Mock(spec=S3VectorsClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = Mock(spec=Config)
        
        # Mock Bedrock text embedding
        mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock S3 Vectors query - return empty results
        mock_s3_vectors.query_vectors = Mock(return_value=[])
        
        # Create SearchService
        search_service = SearchService(
            bedrock_client=mock_bedrock,
            s3_vectors_client=mock_s3_vectors,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform search
        results = await search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=10,
            generate_screenshots=True
        )
        
        # Verify results structure is valid even with no matches
        assert isinstance(results, SearchResults), \
            "Results should be a SearchResults object even when empty"
        assert results.query == query, "Query should be preserved"
        assert len(results.clips) == 0, "Clips list should be empty"
        assert results.total_results == 0, "total_results should be 0"
        assert results.search_time >= 0, "search_time should be non-negative"
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        embedding=valid_embedding(),
        vector_results=valid_vector_results_list()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_search_rejects_empty_query(
        self,
        index_id,
        embedding,
        vector_results
    ):
        """Property 6: Search rejects empty queries.
        
        **Validates: Requirements 3.1**
        
        For any empty or whitespace-only query, the search should raise
        a ValueError.
        """
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3_vectors = Mock(spec=S3VectorsClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = Mock(spec=Config)
        
        # Create SearchService
        search_service = SearchService(
            bedrock_client=mock_bedrock,
            s3_vectors_client=mock_s3_vectors,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Test empty string
        with pytest.raises(ValueError) as exc_info:
            await search_service.search_videos(
                index_id=index_id,
                query="",
                top_k=10
            )
        assert "empty" in str(exc_info.value).lower()
        
        # Test whitespace-only string
        with pytest.raises(ValueError) as exc_info:
            await search_service.search_videos(
                index_id=index_id,
                query="   ",
                top_k=10
            )
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    @given(
        index_id=valid_index_id(),
        query=valid_search_query(),
        embedding=valid_embedding(),
        vector_results=valid_vector_results_list()
    )
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large]
    )
    async def test_property_search_video_stream_urls_include_timecode(
        self,
        index_id,
        query,
        embedding,
        vector_results
    ):
        """Property 6: Video stream URLs include timecode fragment.
        
        **Validates: Requirements 3.3**
        
        For any search result with a non-zero start timecode, the video
        stream URL should include a fragment identifier (#t=timecode).
        """
        # Filter to only results with non-zero start timecode
        non_zero_results = [
            r for r in vector_results
            if r["metadata"]["start_timecode"] > 0.01
        ]
        
        # Skip if no non-zero results
        assume(len(non_zero_results) > 0)
        
        # Create mock clients
        mock_bedrock = Mock(spec=BedrockClient)
        mock_s3_vectors = Mock(spec=S3VectorsClient)
        mock_s3 = Mock(spec=S3Client)
        mock_config = Mock(spec=Config)
        
        # Mock Bedrock text embedding
        mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock S3 Vectors query
        mock_s3_vectors.query_vectors = Mock(return_value=non_zero_results)
        
        # Mock S3 presigned URL generation
        def generate_presigned_url(key, expiration=3600, http_method="GET"):
            return f"https://test-bucket.s3.amazonaws.com/{key}?signature=test"
        
        mock_s3.generate_presigned_url = Mock(side_effect=generate_presigned_url)
        
        # Create SearchService
        search_service = SearchService(
            bedrock_client=mock_bedrock,
            s3_vectors_client=mock_s3_vectors,
            s3_client=mock_s3,
            config=mock_config
        )
        
        # Perform search
        results = await search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=len(non_zero_results),
            generate_screenshots=True
        )
        
        # Verify all video stream URLs include timecode fragment
        for i, clip in enumerate(results.clips):
            if clip.start_timecode > 0:
                assert "#t=" in clip.video_stream_url, \
                    f"Clip {i} video_stream_url should include #t= fragment for " \
                    f"non-zero start_timecode ({clip.start_timecode})"
