"""Unit tests for SearchService.

These tests cover specific examples and edge cases for the search service.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.search_service import SearchService
from aws.bedrock_client import BedrockClient
from aws.s3_vectors_client import S3VectorsClient
from aws.s3_client import S3Client
from config import Config
from models.search import SearchResults, VideoClip
from exceptions import BedrockError, AWSServiceError


class TestSearchService:
    """Unit tests for SearchService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_bedrock = Mock(spec=BedrockClient)
        self.mock_s3_vectors = Mock(spec=S3VectorsClient)
        self.mock_s3 = Mock(spec=S3Client)
        self.mock_config = Mock(spec=Config)
        
        self.search_service = SearchService(
            bedrock_client=self.mock_bedrock,
            s3_vectors_client=self.mock_s3_vectors,
            s3_client=self.mock_s3,
            config=self.mock_config
        )
    
    @pytest.mark.asyncio
    async def test_search_videos_with_valid_query(self):
        """Test searching videos with a valid query returns results."""
        # Arrange
        index_id = "test-index-123"
        query = "person walking in park"
        
        # Mock embedding
        embedding = [0.1] * 128
        self.mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock vector search results
        vector_results = [
            {
                "key": "video1_0",
                "distance": 0.2,
                "metadata": {
                    "video_id": "video1",
                    "start_timecode": 0.0,
                    "end_timecode": 5.0,
                    "s3_key": "videos/index1/video1.mp4"
                }
            }
        ]
        self.mock_s3_vectors.query_vectors = Mock(return_value=vector_results)
        
        # Mock presigned URL
        self.mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/videos/index1/video1.mp4?signature=test"
        )
        
        # Act
        results = await self.search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=10
        )
        
        # Assert
        assert isinstance(results, SearchResults)
        assert results.query == query
        assert len(results.clips) == 1
        assert results.total_results == 1
        assert results.search_time >= 0
        
        # Verify clip structure
        clip = results.clips[0]
        assert clip.video_id == "video1"
        assert clip.start_timecode == 0.0
        assert clip.end_timecode == 5.0
        assert 0.0 <= clip.relevance_score <= 1.0
        assert clip.screenshot_url
        assert clip.video_stream_url
    
    @pytest.mark.asyncio
    async def test_search_videos_empty_query_raises_error(self):
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await self.search_service.search_videos(
                index_id="test-index",
                query="",
                top_k=10
            )
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_search_videos_whitespace_query_raises_error(self):
        """Test that whitespace-only query raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await self.search_service.search_videos(
                index_id="test-index",
                query="   ",
                top_k=10
            )
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_search_videos_invalid_top_k_raises_error(self):
        """Test that invalid top_k raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await self.search_service.search_videos(
                index_id="test-index",
                query="test query",
                top_k=0
            )
        assert "top_k" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_search_videos_no_results(self):
        """Test searching with no matching results."""
        # Arrange
        index_id = "test-index-123"
        query = "nonexistent content"
        
        # Mock embedding
        embedding = [0.1] * 128
        self.mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock empty vector search results
        self.mock_s3_vectors.query_vectors = Mock(return_value=[])
        
        # Act
        results = await self.search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=10
        )
        
        # Assert
        assert isinstance(results, SearchResults)
        assert results.query == query
        assert len(results.clips) == 0
        assert results.total_results == 0
        assert results.search_time >= 0
    
    @pytest.mark.asyncio
    async def test_search_videos_bedrock_error_propagates(self):
        """Test that Bedrock errors are propagated."""
        # Arrange
        self.mock_bedrock.invoke_marengo_text_embedding = Mock(
            side_effect=BedrockError("Bedrock service unavailable")
        )
        
        # Act & Assert
        with pytest.raises(BedrockError) as exc_info:
            await self.search_service.search_videos(
                index_id="test-index",
                query="test query",
                top_k=10
            )
        assert "Bedrock" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_search_videos_s3_vectors_error_propagates(self):
        """Test that S3 Vectors errors are propagated."""
        # Arrange
        embedding = [0.1] * 128
        self.mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        self.mock_s3_vectors.query_vectors = Mock(
            side_effect=AWSServiceError("S3 Vectors service unavailable")
        )
        
        # Act & Assert
        with pytest.raises(AWSServiceError) as exc_info:
            await self.search_service.search_videos(
                index_id="test-index",
                query="test query",
                top_k=10
            )
        assert "S3 Vectors" in str(exc_info.value) or "service" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_search_videos_relevance_score_calculation(self):
        """Test that relevance scores are correctly calculated from distances."""
        # Arrange
        index_id = "test-index-123"
        query = "test query"
        
        # Mock embedding
        embedding = [0.1] * 128
        self.mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock vector search results with different distances
        vector_results = [
            {
                "key": "video1_0",
                "distance": 0.0,  # Perfect match -> score 1.0
                "metadata": {
                    "video_id": "video1",
                    "start_timecode": 0.0,
                    "end_timecode": 5.0,
                    "s3_key": "videos/index1/video1.mp4"
                }
            },
            {
                "key": "video2_0",
                "distance": 0.5,  # Medium match -> score 0.5
                "metadata": {
                    "video_id": "video2",
                    "start_timecode": 0.0,
                    "end_timecode": 5.0,
                    "s3_key": "videos/index1/video2.mp4"
                }
            },
            {
                "key": "video3_0",
                "distance": 1.0,  # No match -> score 0.0
                "metadata": {
                    "video_id": "video3",
                    "start_timecode": 0.0,
                    "end_timecode": 5.0,
                    "s3_key": "videos/index1/video3.mp4"
                }
            }
        ]
        self.mock_s3_vectors.query_vectors = Mock(return_value=vector_results)
        
        # Mock presigned URL
        self.mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/test.mp4"
        )
        
        # Act
        results = await self.search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=10
        )
        
        # Assert
        assert len(results.clips) == 3
        assert results.clips[0].relevance_score == 1.0
        assert results.clips[1].relevance_score == 0.5
        assert results.clips[2].relevance_score == 0.0
    
    @pytest.mark.asyncio
    async def test_search_videos_presigned_url_includes_timecode(self):
        """Test that presigned URLs include timecode fragment for non-zero start times."""
        # Arrange
        index_id = "test-index-123"
        query = "test query"
        
        # Mock embedding
        embedding = [0.1] * 128
        self.mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock vector search results with non-zero start timecode
        vector_results = [
            {
                "key": "video1_10",
                "distance": 0.2,
                "metadata": {
                    "video_id": "video1",
                    "start_timecode": 10.5,
                    "end_timecode": 15.5,
                    "s3_key": "videos/index1/video1.mp4"
                }
            }
        ]
        self.mock_s3_vectors.query_vectors = Mock(return_value=vector_results)
        
        # Mock presigned URL
        self.mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/videos/index1/video1.mp4?signature=test"
        )
        
        # Act
        results = await self.search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=10
        )
        
        # Assert
        assert len(results.clips) == 1
        clip = results.clips[0]
        assert "#t=10.5" in clip.video_stream_url
    
    @pytest.mark.asyncio
    async def test_search_videos_presigned_url_no_timecode_for_zero_start(self):
        """Test that presigned URLs don't include timecode fragment for zero start time."""
        # Arrange
        index_id = "test-index-123"
        query = "test query"
        
        # Mock embedding
        embedding = [0.1] * 128
        self.mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock vector search results with zero start timecode
        vector_results = [
            {
                "key": "video1_0",
                "distance": 0.2,
                "metadata": {
                    "video_id": "video1",
                    "start_timecode": 0.0,
                    "end_timecode": 5.0,
                    "s3_key": "videos/index1/video1.mp4"
                }
            }
        ]
        self.mock_s3_vectors.query_vectors = Mock(return_value=vector_results)
        
        # Mock presigned URL
        self.mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/videos/index1/video1.mp4?signature=test"
        )
        
        # Act
        results = await self.search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=10
        )
        
        # Assert
        assert len(results.clips) == 1
        clip = results.clips[0]
        assert "#t=" not in clip.video_stream_url
    
    @pytest.mark.asyncio
    async def test_search_videos_screenshot_generation_disabled(self):
        """Test that screenshot generation can be disabled."""
        # Arrange
        index_id = "test-index-123"
        query = "test query"
        
        # Mock embedding
        embedding = [0.1] * 128
        self.mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock vector search results
        vector_results = [
            {
                "key": "video1_0",
                "distance": 0.2,
                "metadata": {
                    "video_id": "video1",
                    "start_timecode": 0.0,
                    "end_timecode": 5.0,
                    "s3_key": "videos/index1/video1.mp4"
                }
            }
        ]
        self.mock_s3_vectors.query_vectors = Mock(return_value=vector_results)
        
        # Mock presigned URL
        self.mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/videos/index1/video1.mp4?signature=test"
        )
        
        # Act
        results = await self.search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=10,
            generate_screenshots=False
        )
        
        # Assert
        assert len(results.clips) == 1
        clip = results.clips[0]
        # Screenshot URL should still exist (placeholder)
        assert clip.screenshot_url
        assert "placeholder" in clip.screenshot_url.lower()
    
    @pytest.mark.asyncio
    async def test_search_videos_respects_top_k(self):
        """Test that search respects the top_k parameter."""
        # Arrange
        index_id = "test-index-123"
        query = "test query"
        top_k = 2
        
        # Mock embedding
        embedding = [0.1] * 128
        self.mock_bedrock.invoke_marengo_text_embedding = Mock(return_value=embedding)
        
        # Mock vector search results (more than top_k)
        vector_results = [
            {
                "key": f"video{i}_0",
                "distance": 0.1 * i,
                "metadata": {
                    "video_id": f"video{i}",
                    "start_timecode": 0.0,
                    "end_timecode": 5.0,
                    "s3_key": f"videos/index1/video{i}.mp4"
                }
            }
            for i in range(5)
        ]
        
        # S3 Vectors should only return top_k results
        self.mock_s3_vectors.query_vectors = Mock(return_value=vector_results[:top_k])
        
        # Mock presigned URL
        self.mock_s3.generate_presigned_url = Mock(
            return_value="https://test-bucket.s3.amazonaws.com/test.mp4"
        )
        
        # Act
        results = await self.search_service.search_videos(
            index_id=index_id,
            query=query,
            top_k=top_k
        )
        
        # Assert
        assert len(results.clips) == top_k
        assert results.total_results == top_k
        
        # Verify S3 Vectors was called with correct top_k
        self.mock_s3_vectors.query_vectors.assert_called_once()
        call_args = self.mock_s3_vectors.query_vectors.call_args
        assert call_args[1]['top_k'] == top_k
