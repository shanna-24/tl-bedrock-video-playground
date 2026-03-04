"""Unit tests for data models.

Tests validation rules and model behavior for Index, Video, VideoClip,
SearchResults, and AnalysisResult models.
"""

import sys
from pathlib import Path
import pytest
from datetime import datetime
from pydantic import ValidationError

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from models.index import Index
from models.video import Video
from models.search import VideoClip, SearchResults
from models.analysis import AnalysisResult


class TestIndexModel:
    """Tests for Index model validation."""
    
    def test_create_valid_index(self):
        """Test creating a valid index."""
        index = Index.create(name="Test Index")
        
        assert index.id is not None
        assert len(index.id) > 0
        assert index.name == "Test Index"
        assert index.video_count == 0
        assert index.s3_vectors_collection_id == ""
        assert isinstance(index.created_at, datetime)
        assert isinstance(index.metadata, dict)
    
    def test_index_name_validation_empty(self):
        """Test that empty index name is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Index(name="", id="test-id")
        
        assert "Index name cannot be empty" in str(exc_info.value)
    
    def test_index_name_validation_too_short(self):
        """Test that index name shorter than 3 characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Index(name="ab", id="test-id")
        
        assert "3-50 characters" in str(exc_info.value)
    
    def test_index_name_validation_too_long(self):
        """Test that index name longer than 50 characters is rejected."""
        long_name = "a" * 51
        with pytest.raises(ValidationError) as exc_info:
            Index(name=long_name, id="test-id")
        
        assert "3-50 characters" in str(exc_info.value)
    
    def test_index_name_validation_special_chars(self):
        """Test that index name with invalid special characters is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Index(name="Test@Index!", id="test-id")
        
        assert "alphanumeric" in str(exc_info.value)
    
    def test_index_name_allows_valid_chars(self):
        """Test that index name allows alphanumeric, spaces, hyphens, underscores."""
        valid_names = [
            "Test Index",
            "test-index",
            "test_index",
            "Test-Index_123",
        ]
        
        for name in valid_names:
            index = Index(name=name, id="test-id")
            assert index.name == name
    
    def test_index_video_count_non_negative(self):
        """Test that video count must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            Index(name="Test", id="test-id", video_count=-1)
        
        assert "greater than or equal to 0" in str(exc_info.value)
    
    def test_index_json_serialization(self):
        """Test that index can be serialized to JSON."""
        index = Index.create(name="Test Index")
        data = index.model_dump(mode='json')
        
        assert data['name'] == "Test Index"
        assert 'id' in data
        assert 'created_at' in data
        assert data['video_count'] == 0


class TestVideoModel:
    """Tests for Video model validation."""
    
    def test_create_valid_video(self):
        """Test creating a valid video."""
        video = Video(
            index_id="index-123",
            filename="test.mp4",
            s3_uri="s3://bucket/test.mp4",
            duration=120.5
        )
        
        assert video.id is not None
        assert video.index_id == "index-123"
        assert video.filename == "test.mp4"
        assert video.s3_uri == "s3://bucket/test.mp4"
        assert video.duration == 120.5
        assert isinstance(video.uploaded_at, datetime)
        assert isinstance(video.embedding_ids, list)
        assert isinstance(video.metadata, dict)
    
    def test_video_filename_validation_empty(self):
        """Test that empty filename is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Video(
                index_id="index-123",
                filename="",
                s3_uri="s3://bucket/test.mp4",
                duration=120.5
            )
        
        assert "Filename cannot be empty" in str(exc_info.value)
    
    def test_video_filename_validation_invalid_extension(self):
        """Test that invalid file extension is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Video(
                index_id="index-123",
                filename="test.txt",
                s3_uri="s3://bucket/test.txt",
                duration=120.5
            )
        
        assert "Unsupported video format" in str(exc_info.value)
    
    def test_video_filename_valid_extensions(self):
        """Test that all valid video extensions are accepted."""
        valid_extensions = ['.mp4', '.mov', '.avi', '.mkv']
        
        for ext in valid_extensions:
            video = Video(
                index_id="index-123",
                filename=f"test{ext}",
                s3_uri="s3://bucket/test.mp4",
                duration=120.5
            )
            assert video.filename == f"test{ext}"
    
    def test_video_s3_uri_validation(self):
        """Test that S3 URI must start with s3://."""
        with pytest.raises(ValidationError) as exc_info:
            Video(
                index_id="index-123",
                filename="test.mp4",
                s3_uri="http://bucket/test.mp4",
                duration=120.5
            )
        
        assert "must start with 's3://'" in str(exc_info.value)
    
    def test_video_duration_positive(self):
        """Test that duration must be positive."""
        with pytest.raises(ValidationError) as exc_info:
            Video(
                index_id="index-123",
                filename="test.mp4",
                s3_uri="s3://bucket/test.mp4",
                duration=0
            )
        
        assert "greater than 0" in str(exc_info.value)


class TestVideoClipModel:
    """Tests for VideoClip model validation."""
    
    def test_create_valid_video_clip(self):
        """Test creating a valid video clip."""
        clip = VideoClip(
            video_id="video-123",
            start_timecode=10.5,
            end_timecode=20.5,
            relevance_score=0.85,
            screenshot_url="https://example.com/screenshot.jpg",
            video_stream_url="https://example.com/video.mp4"
        )
        
        assert clip.video_id == "video-123"
        assert clip.start_timecode == 10.5
        assert clip.end_timecode == 20.5
        assert clip.relevance_score == 0.85
        assert clip.screenshot_url == "https://example.com/screenshot.jpg"
        assert clip.video_stream_url == "https://example.com/video.mp4"
    
    def test_video_clip_timecode_validation(self):
        """Test that end_timecode must be greater than start_timecode."""
        with pytest.raises(ValidationError) as exc_info:
            VideoClip(
                video_id="video-123",
                start_timecode=20.5,
                end_timecode=10.5,
                relevance_score=0.85,
                screenshot_url="https://example.com/screenshot.jpg",
                video_stream_url="https://example.com/video.mp4"
            )
        
        assert "end_timecode must be greater than start_timecode" in str(exc_info.value)
    
    def test_video_clip_timecode_non_negative(self):
        """Test that timecodes must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            VideoClip(
                video_id="video-123",
                start_timecode=-1.0,
                end_timecode=10.5,
                relevance_score=0.85,
                screenshot_url="https://example.com/screenshot.jpg",
                video_stream_url="https://example.com/video.mp4"
            )
        
        assert "greater than or equal to 0" in str(exc_info.value)
    
    def test_video_clip_relevance_score_range(self):
        """Test that relevance score must be between 0.0 and 1.0."""
        # Test score too high
        with pytest.raises(ValidationError) as exc_info:
            VideoClip(
                video_id="video-123",
                start_timecode=10.5,
                end_timecode=20.5,
                relevance_score=1.5,
                screenshot_url="https://example.com/screenshot.jpg",
                video_stream_url="https://example.com/video.mp4"
            )
        
        assert "less than or equal to 1" in str(exc_info.value)
        
        # Test score too low
        with pytest.raises(ValidationError) as exc_info:
            VideoClip(
                video_id="video-123",
                start_timecode=10.5,
                end_timecode=20.5,
                relevance_score=-0.1,
                screenshot_url="https://example.com/screenshot.jpg",
                video_stream_url="https://example.com/video.mp4"
            )
        
        assert "greater than or equal to 0" in str(exc_info.value)
    
    def test_video_clip_url_validation(self):
        """Test that URLs cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            VideoClip(
                video_id="video-123",
                start_timecode=10.5,
                end_timecode=20.5,
                relevance_score=0.85,
                screenshot_url="",
                video_stream_url="https://example.com/video.mp4"
            )
        
        assert "URL cannot be empty" in str(exc_info.value)


class TestSearchResultsModel:
    """Tests for SearchResults model validation."""
    
    def test_create_valid_search_results(self):
        """Test creating valid search results."""
        clip = VideoClip(
            video_id="video-123",
            start_timecode=10.5,
            end_timecode=20.5,
            relevance_score=0.85,
            screenshot_url="https://example.com/screenshot.jpg",
            video_stream_url="https://example.com/video.mp4"
        )
        
        results = SearchResults(
            query="test query",
            clips=[clip],
            total_results=1,
            search_time=0.5
        )
        
        assert results.query == "test query"
        assert len(results.clips) == 1
        assert results.total_results == 1
        assert results.search_time == 0.5
    
    def test_search_results_query_validation(self):
        """Test that query cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            SearchResults(
                query="",
                clips=[],
                total_results=0,
                search_time=0.5
            )
        
        assert "Search query cannot be empty" in str(exc_info.value)
    
    def test_search_results_total_results_validation(self):
        """Test that total_results must match clips length."""
        clip = VideoClip(
            video_id="video-123",
            start_timecode=10.5,
            end_timecode=20.5,
            relevance_score=0.85,
            screenshot_url="https://example.com/screenshot.jpg",
            video_stream_url="https://example.com/video.mp4"
        )
        
        with pytest.raises(ValidationError) as exc_info:
            SearchResults(
                query="test query",
                clips=[clip],
                total_results=5,  # Doesn't match clips length
                search_time=0.5
            )
        
        assert "must match the number of clips" in str(exc_info.value)
    
    def test_search_results_non_negative_values(self):
        """Test that total_results and search_time must be non-negative."""
        with pytest.raises(ValidationError) as exc_info:
            SearchResults(
                query="test query",
                clips=[],
                total_results=-1,
                search_time=0.5
            )
        
        assert "greater than or equal to 0" in str(exc_info.value)


class TestAnalysisResultModel:
    """Tests for AnalysisResult model validation."""
    
    def test_create_valid_analysis_result(self):
        """Test creating a valid analysis result."""
        result = AnalysisResult(
            query="What is in this video?",
            scope="video",
            scope_id="video-123",
            insights="This video contains..."
        )
        
        assert result.query == "What is in this video?"
        assert result.scope == "video"
        assert result.scope_id == "video-123"
        assert result.insights == "This video contains..."
        assert isinstance(result.analyzed_at, datetime)
        assert isinstance(result.metadata, dict)
    
    def test_analysis_result_scope_validation(self):
        """Test that scope must be 'index' or 'video'."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisResult(
                query="What is in this video?",
                scope="invalid",
                scope_id="video-123",
                insights="This video contains..."
            )
        
        assert "Input should be 'index' or 'video'" in str(exc_info.value)
    
    def test_analysis_result_query_validation(self):
        """Test that query cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisResult(
                query="",
                scope="video",
                scope_id="video-123",
                insights="This video contains..."
            )
        
        assert "Analysis query cannot be empty" in str(exc_info.value)
    
    def test_analysis_result_scope_id_validation(self):
        """Test that scope_id cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisResult(
                query="What is in this video?",
                scope="video",
                scope_id="",
                insights="This video contains..."
            )
        
        assert "Scope ID cannot be empty" in str(exc_info.value)
    
    def test_analysis_result_insights_validation(self):
        """Test that insights cannot be empty."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisResult(
                query="What is in this video?",
                scope="video",
                scope_id="video-123",
                insights=""
            )
        
        assert "Analysis insights cannot be empty" in str(exc_info.value)
    
    def test_analysis_result_both_scopes(self):
        """Test that both 'index' and 'video' scopes are valid."""
        # Test index scope
        result_index = AnalysisResult(
            query="What is in this index?",
            scope="index",
            scope_id="index-123",
            insights="This index contains..."
        )
        assert result_index.scope == "index"
        
        # Test video scope
        result_video = AnalysisResult(
            query="What is in this video?",
            scope="video",
            scope_id="video-123",
            insights="This video contains..."
        )
        assert result_video.scope == "video"
