"""Unit tests for AnalysisService.

These tests cover specific examples and edge cases for the analysis service.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
import pytest
from datetime import datetime

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.analysis_service import AnalysisService
from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from config import Config
from models.analysis import AnalysisResult
from exceptions import BedrockError, AWSServiceError


class TestAnalysisService:
    """Unit tests for AnalysisService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_bedrock = Mock(spec=BedrockClient)
        self.mock_s3 = Mock(spec=S3Client)
        self.mock_config = Mock(spec=Config)
        
        # Mock jockey config with enabled=False to use legacy implementation
        mock_jockey_config = Mock()
        mock_jockey_config.enabled = False
        self.mock_config.jockey = mock_jockey_config
        
        self.analysis_service = AnalysisService(
            bedrock_client=self.mock_bedrock,
            s3_client=self.mock_s3,
            config=self.mock_config
        )
    
    @pytest.mark.asyncio
    async def test_analyze_index_with_valid_query(self):
        """Test analyzing an index with a valid query returns results."""
        # Arrange
        index_id = "test-index-123"
        query = "What are the main topics discussed in these videos?"
        video_s3_uris = [
            "s3://test-bucket/videos/index1/video1.mp4",
            "s3://test-bucket/videos/index1/video2.mp4"
        ]
        
        # Mock Pegasus response
        pegasus_response = {
            "message": "The videos discuss various topics including technology, nature, and education.",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act
        result = await self.analysis_service.analyze_index(
            index_id=index_id,
            query=query,
            video_s3_uris=video_s3_uris
        )
        
        # Assert
        assert isinstance(result, AnalysisResult)
        assert result.query == query
        assert result.scope == "index"
        assert result.scope_id == index_id
        assert result.insights == pegasus_response["message"]
        assert isinstance(result.analyzed_at, datetime)
        assert result.metadata["video_count"] == 2
        
        # Verify Pegasus was called
        self.mock_bedrock.invoke_pegasus_analysis.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_video_with_valid_query(self):
        """Test analyzing a single video with a valid query returns results."""
        # Arrange
        video_id = "video-123"
        query = "Describe the main events in this video"
        video_s3_uri = "s3://test-bucket/videos/index1/video1.mp4"
        
        # Mock Pegasus response
        pegasus_response = {
            "message": "The video shows a person walking through a park on a sunny day.",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act
        result = await self.analysis_service.analyze_video(
            video_id=video_id,
            query=query,
            video_s3_uri=video_s3_uri
        )
        
        # Assert
        assert isinstance(result, AnalysisResult)
        assert result.query == query
        assert result.scope == "video"
        assert result.scope_id == video_id
        assert result.insights == pegasus_response["message"]
        assert isinstance(result.analyzed_at, datetime)
        assert result.metadata["video_s3_uri"] == video_s3_uri
        
        # Verify Pegasus was called
        self.mock_bedrock.invoke_pegasus_analysis.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_index_empty_query_raises_error(self):
        """Test that empty query raises ValueError for index analysis."""
        video_s3_uris = ["s3://test-bucket/videos/video1.mp4"]
        
        with pytest.raises(ValueError) as exc_info:
            await self.analysis_service.analyze_index(
                index_id="test-index",
                query="",
                video_s3_uris=video_s3_uris
            )
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_analyze_index_whitespace_query_raises_error(self):
        """Test that whitespace-only query raises ValueError for index analysis."""
        video_s3_uris = ["s3://test-bucket/videos/video1.mp4"]
        
        with pytest.raises(ValueError) as exc_info:
            await self.analysis_service.analyze_index(
                index_id="test-index",
                query="   ",
                video_s3_uris=video_s3_uris
            )
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_analyze_index_no_videos_raises_error(self):
        """Test that analyzing index with no videos raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await self.analysis_service.analyze_index(
                index_id="test-index",
                query="What is in these videos?",
                video_s3_uris=[]
            )
        assert "no videos" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_analyze_video_empty_query_raises_error(self):
        """Test that empty query raises ValueError for video analysis."""
        with pytest.raises(ValueError) as exc_info:
            await self.analysis_service.analyze_video(
                video_id="video-123",
                query="",
                video_s3_uri="s3://test-bucket/videos/video1.mp4"
            )
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_analyze_video_invalid_s3_uri_raises_error(self):
        """Test that invalid S3 URI raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await self.analysis_service.analyze_video(
                video_id="video-123",
                query="Describe this video",
                video_s3_uri="http://example.com/video.mp4"
            )
        assert "invalid" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_analyze_index_bedrock_error_propagates(self):
        """Test that BedrockError from Pegasus is propagated."""
        # Arrange
        video_s3_uris = ["s3://test-bucket/videos/video1.mp4"]
        self.mock_bedrock.invoke_pegasus_analysis = Mock(
            side_effect=BedrockError("Model invocation failed")
        )
        
        # Act & Assert
        with pytest.raises(BedrockError):
            await self.analysis_service.analyze_index(
                index_id="test-index",
                query="What is in these videos?",
                video_s3_uris=video_s3_uris
            )
    
    @pytest.mark.asyncio
    async def test_analyze_video_bedrock_error_propagates(self):
        """Test that BedrockError from Pegasus is propagated."""
        # Arrange
        self.mock_bedrock.invoke_pegasus_analysis = Mock(
            side_effect=BedrockError("Model invocation failed")
        )
        
        # Act & Assert
        with pytest.raises(BedrockError):
            await self.analysis_service.analyze_video(
                video_id="video-123",
                query="Describe this video",
                video_s3_uri="s3://test-bucket/videos/video1.mp4"
            )
    
    @pytest.mark.asyncio
    async def test_analyze_index_with_temperature_parameter(self):
        """Test that temperature parameter is passed to Pegasus."""
        # Arrange
        video_s3_uris = ["s3://test-bucket/videos/video1.mp4"]
        temperature = 0.5
        
        pegasus_response = {
            "message": "Analysis result",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act
        await self.analysis_service.analyze_index(
            index_id="test-index",
            query="Analyze this",
            video_s3_uris=video_s3_uris,
            temperature=temperature
        )
        
        # Assert
        call_args = self.mock_bedrock.invoke_pegasus_analysis.call_args
        assert call_args[1]["temperature"] == temperature
    
    @pytest.mark.asyncio
    async def test_analyze_video_with_max_output_tokens(self):
        """Test that max_output_tokens parameter is passed to Pegasus."""
        # Arrange
        max_tokens = 2048
        
        pegasus_response = {
            "message": "Analysis result",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act
        await self.analysis_service.analyze_video(
            video_id="video-123",
            query="Analyze this",
            video_s3_uri="s3://test-bucket/videos/video1.mp4",
            max_output_tokens=max_tokens
        )
        
        # Assert
        call_args = self.mock_bedrock.invoke_pegasus_analysis.call_args
        assert call_args[1]["max_output_tokens"] == max_tokens
    
    @pytest.mark.asyncio
    async def test_analyze_index_empty_pegasus_response_raises_error(self):
        """Test that empty Pegasus response raises BedrockError."""
        # Arrange
        video_s3_uris = ["s3://test-bucket/videos/video1.mp4"]
        
        # Mock empty response
        pegasus_response = {
            "message": "",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act & Assert
        with pytest.raises(BedrockError) as exc_info:
            await self.analysis_service.analyze_index(
                index_id="test-index",
                query="Analyze this",
                video_s3_uris=video_s3_uris
            )
        assert "empty" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_analyze_index_multiple_videos(self):
        """Test analyzing index with multiple videos."""
        # Arrange
        index_id = "test-index-123"
        query = "What are the common themes?"
        video_s3_uris = [
            "s3://test-bucket/videos/video1.mp4",
            "s3://test-bucket/videos/video2.mp4",
            "s3://test-bucket/videos/video3.mp4"
        ]
        
        pegasus_response = {
            "message": "Common themes include nature and technology.",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act
        result = await self.analysis_service.analyze_index(
            index_id=index_id,
            query=query,
            video_s3_uris=video_s3_uris
        )
        
        # Assert
        assert result.metadata["video_count"] == 3
        assert result.scope == "index"
        assert result.scope_id == index_id
    
    @pytest.mark.asyncio
    async def test_analyze_video_result_structure(self):
        """Test that video analysis result has correct structure."""
        # Arrange
        video_id = "video-123"
        query = "What happens in this video?"
        video_s3_uri = "s3://test-bucket/videos/video1.mp4"
        
        pegasus_response = {
            "message": "A detailed description of the video content.",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act
        result = await self.analysis_service.analyze_video(
            video_id=video_id,
            query=query,
            video_s3_uri=video_s3_uri
        )
        
        # Assert
        assert result.query == query
        assert result.scope == "video"
        assert result.scope_id == video_id
        assert result.insights
        assert isinstance(result.analyzed_at, datetime)
        assert "video_s3_uri" in result.metadata
        assert result.metadata["video_s3_uri"] == video_s3_uri

    @pytest.mark.asyncio
    async def test_analyze_index_with_jockey_enabled(self):
        """Test that JockeyOrchestrator is used when enabled."""
        # Arrange
        from unittest.mock import AsyncMock
        
        # Create a new config with Jockey enabled
        mock_config = Mock(spec=Config)
        mock_jockey_config = Mock()
        mock_jockey_config.enabled = True
        mock_jockey_config.claude_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        mock_jockey_config.parallel_analysis_limit = 3
        mock_config.jockey = mock_jockey_config
        
        # Create mock search service
        mock_search_service = Mock()
        
        # Create analysis service with Jockey enabled
        analysis_service = AnalysisService(
            bedrock_client=self.mock_bedrock,
            s3_client=self.mock_s3,
            config=mock_config,
            search_service=mock_search_service
        )
        
        # Verify orchestrator was initialized
        assert analysis_service.orchestrator is not None
        
        # Mock the orchestrator's analyze_index method
        expected_result = AnalysisResult(
            query="Test query",
            scope="index",
            scope_id="test-index",
            insights="Orchestrator insights",
            analyzed_at=datetime.now(),
            metadata={"jockey_enabled": True}
        )
        analysis_service.orchestrator.analyze_index = AsyncMock(return_value=expected_result)
        
        # Act
        result = await analysis_service.analyze_index(
            index_id="test-index",
            query="Test query",
            video_s3_uris=["s3://bucket/video1.mp4", "s3://bucket/video2.mp4"]
        )
        
        # Assert
        assert result == expected_result
        analysis_service.orchestrator.analyze_index.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_index_jockey_disabled_uses_legacy(self):
        """Test that legacy implementation is used when Jockey is disabled."""
        # Arrange
        index_id = "test-index-123"
        query = "What are the main topics?"
        video_s3_uris = ["s3://bucket/video1.mp4"]
        
        # Mock Pegasus response
        pegasus_response = {
            "message": "Legacy implementation result",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act
        result = await self.analysis_service.analyze_index(
            index_id=index_id,
            query=query,
            video_s3_uris=video_s3_uris
        )
        
        # Assert
        assert result.insights == pegasus_response["message"]
        assert result.metadata.get("jockey_enabled") == False
        self.mock_bedrock.invoke_pegasus_analysis.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_index_jockey_fallback_on_error(self):
        """Test that legacy implementation is used as fallback when orchestrator fails."""
        # Arrange
        from unittest.mock import AsyncMock
        
        # Create a new config with Jockey enabled
        mock_config = Mock(spec=Config)
        mock_jockey_config = Mock()
        mock_jockey_config.enabled = True
        mock_jockey_config.claude_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        mock_jockey_config.parallel_analysis_limit = 3
        mock_config.jockey = mock_jockey_config
        
        # Create mock search service
        mock_search_service = Mock()
        
        # Create analysis service with Jockey enabled
        analysis_service = AnalysisService(
            bedrock_client=self.mock_bedrock,
            s3_client=self.mock_s3,
            config=mock_config,
            search_service=mock_search_service
        )
        
        # Mock orchestrator to raise an error
        analysis_service.orchestrator.analyze_index = AsyncMock(
            side_effect=Exception("Orchestrator failed")
        )
        
        # Mock Pegasus for fallback
        pegasus_response = {
            "message": "Fallback result",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act
        result = await analysis_service.analyze_index(
            index_id="test-index",
            query="Test query",
            video_s3_uris=["s3://bucket/video1.mp4"]
        )
        
        # Assert - should fall back to legacy implementation
        assert result.insights == pegasus_response["message"]
        assert result.metadata.get("jockey_enabled") == False
        self.mock_bedrock.invoke_pegasus_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_video_with_jockey_uses_single_video_optimization(self):
        """Test that single video analysis with Jockey uses optimized workflow."""
        # Arrange
        from unittest.mock import AsyncMock
        
        # Create a new config with Jockey enabled
        mock_config = Mock(spec=Config)
        mock_jockey_config = Mock()
        mock_jockey_config.enabled = True
        mock_jockey_config.claude_model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        mock_jockey_config.parallel_analysis_limit = 3
        mock_jockey_config.web_search_enabled = False
        mock_jockey_config.brave_api_key = None
        mock_config.jockey = mock_jockey_config
        
        # Create mock search service
        mock_search_service = Mock()
        
        # Create analysis service with Jockey enabled
        analysis_service = AnalysisService(
            bedrock_client=self.mock_bedrock,
            s3_client=self.mock_s3,
            config=mock_config,
            search_service=mock_search_service
        )
        
        # Verify orchestrator was initialized
        assert analysis_service.orchestrator is not None
        
        # Mock the orchestrator's analyze_single_video method
        expected_result = AnalysisResult(
            query="Test query",
            scope="video",
            scope_id="video-123",
            insights="Enhanced insights from Jockey",
            analyzed_at=datetime.now(),
            metadata={
                "jockey_enabled": True,
                "single_video_mode": True,
                "bypassed_segment_search": True
            }
        )
        analysis_service.orchestrator.analyze_single_video = AsyncMock(return_value=expected_result)
        
        # Act
        result = await analysis_service.analyze_video(
            video_id="video-123",
            query="Test query",
            video_s3_uri="s3://bucket/video1.mp4",
            use_jockey=True
        )
        
        # Assert
        assert result == expected_result
        assert result.metadata.get("single_video_mode") == True
        assert result.metadata.get("bypassed_segment_search") == True
        analysis_service.orchestrator.analyze_single_video.assert_called_once()
        
        # Verify analyze_single_video was called with correct parameters
        call_args = analysis_service.orchestrator.analyze_single_video.call_args
        assert call_args.kwargs["video_id"] == "video-123"
        assert call_args.kwargs["query"] == "Test query"
        assert call_args.kwargs["video_s3_uri"] == "s3://bucket/video1.mp4"
    
    @pytest.mark.asyncio
    async def test_analyze_video_without_jockey_uses_direct_pegasus(self):
        """Test that single video analysis without Jockey uses direct Pegasus."""
        # Arrange
        video_id = "video-123"
        query = "Test query"
        video_s3_uri = "s3://bucket/video1.mp4"
        
        # Mock Pegasus response
        pegasus_response = {
            "message": "Direct Pegasus result",
            "finishReason": "stop"
        }
        self.mock_bedrock.invoke_pegasus_analysis = Mock(return_value=pegasus_response)
        
        # Act
        result = await self.analysis_service.analyze_video(
            video_id=video_id,
            query=query,
            video_s3_uri=video_s3_uri,
            use_jockey=False
        )
        
        # Assert
        assert result.insights == pegasus_response["message"]
        assert result.metadata.get("jockey_enabled") == False
        assert result.metadata.get("use_jockey_requested") == False
        self.mock_bedrock.invoke_pegasus_analysis.assert_called_once()
