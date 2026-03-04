"""Unit tests for EDL parsing in AnalysisService."""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.analysis_service import AnalysisService
from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from config import Config


class TestAnalysisEDLParsing:
    """Test suite for EDL parsing and video generation triggering."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_bedrock = Mock(spec=BedrockClient)
        self.mock_s3 = Mock(spec=S3Client)
        self.mock_config = Mock(spec=Config)
        self.mock_config.jockey = Mock(enabled=False)
        
        # Mock video generation service
        self.mock_video_gen = Mock()
        self.mock_video_gen.generate_video_from_edl = AsyncMock(
            return_value={
                "s3_uri": "s3://bucket/videos-generated/generated-20260215_143022.mp4",
                "s3_key": "videos-generated/generated-20260215_143022.mp4",
                "duration": 30.5,
                "segment_count": 2
            }
        )
        
        self.analysis_service = AnalysisService(
            bedrock_client=self.mock_bedrock,
            s3_client=self.mock_s3,
            config=self.mock_config,
            video_generation_service=self.mock_video_gen
        )
    
    @pytest.mark.asyncio
    async def test_parse_edl_from_json_block(self):
        """Test parsing EDL from JSON code block in Pegasus response."""
        pegasus_response = """
Here's a highlight reel from the video:

```json
{
  "action": "generate_video",
  "edl": [
    {
      "source_s3_uri": "s3://bucket/video.mp4",
      "start_time": "00:00:10.000",
      "end_time": "00:00:20.000"
    }
  ],
  "output_filename": "highlights"
}
```

The video has been generated with the best moments.
"""
        
        result = await self.analysis_service._check_and_execute_video_generation(
            pegasus_response
        )
        
        assert result is not None
        assert result["s3_uri"] == "s3://bucket/videos-generated/generated-20260215_143022.mp4"
        assert result["segment_count"] == 2
        
        # Verify video generation was called
        self.mock_video_gen.generate_video_from_edl.assert_called_once()
        call_args = self.mock_video_gen.generate_video_from_edl.call_args
        assert len(call_args[1]["edl"]) == 1
        assert call_args[1]["output_filename"] == "highlights"
    
    @pytest.mark.asyncio
    async def test_no_edl_in_response(self):
        """Test that normal responses without EDL don't trigger video generation."""
        pegasus_response = """
The video shows a person walking in a park. The scene is peaceful
and the weather appears to be sunny. There are trees in the background.
"""
        
        result = await self.analysis_service._check_and_execute_video_generation(
            pegasus_response
        )
        
        assert result is None
        self.mock_video_gen.generate_video_from_edl.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_invalid_json_ignored(self):
        """Test that invalid JSON is ignored gracefully."""
        pegasus_response = """
Here's the result:

```json
{
  "action": "generate_video",
  "edl": [
    invalid json here
  ]
}
```
"""
        
        result = await self.analysis_service._check_and_execute_video_generation(
            pegasus_response
        )
        
        assert result is None
        self.mock_video_gen.generate_video_from_edl.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_empty_edl_ignored(self):
        """Test that empty EDL is ignored."""
        pegasus_response = """
```json
{
  "action": "generate_video",
  "edl": []
}
```
"""
        
        result = await self.analysis_service._check_and_execute_video_generation(
            pegasus_response
        )
        
        assert result is None
        self.mock_video_gen.generate_video_from_edl.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_video_generation_failure_doesnt_break_analysis(self):
        """Test that video generation failure doesn't break the analysis."""
        # Mock video generation to fail
        self.mock_video_gen.generate_video_from_edl = AsyncMock(
            side_effect=Exception("Video generation failed")
        )
        
        pegasus_response = """
```json
{
  "action": "generate_video",
  "edl": [
    {
      "source_s3_uri": "s3://bucket/video.mp4",
      "start_time": "00:00:10.000",
      "end_time": "00:00:20.000"
    }
  ]
}
```
"""
        
        # Should not raise exception
        result = await self.analysis_service._check_and_execute_video_generation(
            pegasus_response
        )
        
        # Should return None on failure
        assert result is None
    
    @pytest.mark.asyncio
    async def test_analyze_video_with_edl_response(self):
        """Test full analyze_video flow with EDL in response."""
        # Mock Pegasus to return response with EDL
        self.mock_bedrock.invoke_pegasus_analysis = Mock(
            return_value={
                "message": """
I'll create a highlight reel:

```json
{
  "action": "generate_video",
  "edl": [
    {
      "source_s3_uri": "s3://bucket/videos/test.mp4",
      "start_time": "00:00:10.000",
      "end_time": "00:00:20.000"
    }
  ],
  "output_filename": "highlights"
}
```

The video has been generated.
""",
                "finishReason": "stop"
            }
        )
        
        result = await self.analysis_service.analyze_video(
            video_id="video-123",
            query="Create a highlight reel",
            video_s3_uri="s3://bucket/videos/test.mp4"
        )
        
        # Verify analysis result
        assert result.query == "Create a highlight reel"
        assert result.scope == "video"
        assert result.scope_id == "video-123"
        
        # Verify video generation was triggered
        assert "generated_video" in result.metadata
        assert result.metadata["generated_video"]["s3_uri"] == "s3://bucket/videos-generated/generated-20260215_143022.mp4"
        
        # Verify video generation service was called
        self.mock_video_gen.generate_video_from_edl.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_no_video_generation_service_available(self):
        """Test that EDL parsing is skipped when video generation service is not available."""
        # Create service without video generation
        service = AnalysisService(
            bedrock_client=self.mock_bedrock,
            s3_client=self.mock_s3,
            config=self.mock_config
        )
        
        pegasus_response = """
```json
{
  "action": "generate_video",
  "edl": [
    {
      "source_s3_uri": "s3://bucket/video.mp4",
      "start_time": "00:00:10.000",
      "end_time": "00:00:20.000"
    }
  ]
}
```
"""
        
        result = await service._check_and_execute_video_generation(
            pegasus_response
        )
        
        # Should return None when service not available
        assert result is None
    
    @pytest.mark.asyncio
    async def test_multiple_segments_in_edl(self):
        """Test parsing EDL with multiple segments."""
        pegasus_response = """
```json
{
  "action": "generate_video",
  "edl": [
    {
      "source_s3_uri": "s3://bucket/video1.mp4",
      "start_time": "00:00:10.000",
      "end_time": "00:00:20.000"
    },
    {
      "source_s3_uri": "s3://bucket/video2.mp4",
      "start_time": "00:00:05.000",
      "end_time": "00:00:15.000"
    },
    {
      "source_s3_uri": "s3://bucket/video3.mp4",
      "start_time": "00:01:00.000",
      "end_time": "00:01:10.000"
    }
  ]
}
```
"""
        
        result = await self.analysis_service._check_and_execute_video_generation(
            pegasus_response
        )
        
        assert result is not None
        
        # Verify all segments were passed
        call_args = self.mock_video_gen.generate_video_from_edl.call_args
        assert len(call_args[1]["edl"]) == 3
