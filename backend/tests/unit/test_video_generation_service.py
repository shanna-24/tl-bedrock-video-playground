"""Unit tests for VideoGenerationService."""

import sys
from pathlib import Path
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import tempfile
import subprocess

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.video_generation_service import VideoGenerationService
from exceptions import AWSServiceError


class TestVideoGenerationService:
    """Test suite for VideoGenerationService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_s3 = Mock()
        self.mock_s3.download = AsyncMock()
        self.mock_s3.upload = AsyncMock()
        
        self.mock_config = Mock()
        self.mock_config.s3_bucket_name = "test-bucket"
        self.mock_config.aws_region = "us-east-1"
    
    @patch('subprocess.run')
    def test_init_with_ffmpeg_available(self, mock_run):
        """Test initialization when ffmpeg is available."""
        mock_run.return_value = Mock(returncode=0)
        
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        assert service.s3 == self.mock_s3
        assert service.config == self.mock_config
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_init_without_ffmpeg(self, mock_run):
        """Test initialization fails when ffmpeg is not available."""
        mock_run.side_effect = FileNotFoundError()
        
        with pytest.raises(RuntimeError, match="ffmpeg is required"):
            VideoGenerationService(self.mock_s3, self.mock_config)
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_generate_video_from_edl_invalid_edl(self, mock_run):
        """Test that invalid EDL raises ValueError."""
        mock_run.return_value = Mock(returncode=0)
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        # Empty EDL
        with pytest.raises(ValueError, match="EDL must be a non-empty list"):
            await service.generate_video_from_edl([])
        
        # Non-list EDL
        with pytest.raises(ValueError, match="EDL must be a non-empty list"):
            await service.generate_video_from_edl("not a list")
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_generate_video_from_edl_missing_fields(self, mock_run):
        """Test that EDL with missing fields raises ValueError."""
        mock_run.return_value = Mock(returncode=0)
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        # Missing source_s3_uri
        edl = [{"start_time": "00:00:10.000", "end_time": "00:00:20.000"}]
        with pytest.raises(ValueError, match="missing 'source_s3_uri'"):
            await service.generate_video_from_edl(edl)
        
        # Missing timecodes
        edl = [{"source_s3_uri": "s3://bucket/video.mp4"}]
        with pytest.raises(ValueError, match="missing 'start_time' or 'end_time'"):
            await service.generate_video_from_edl(edl)
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_generate_video_from_edl_success(self, mock_run):
        """Test successful video generation from EDL."""
        # Mock ffmpeg commands
        mock_run.return_value = Mock(returncode=0, stdout="30.5", stderr="")
        
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        edl = [
            {
                "source_s3_uri": "s3://test-bucket/videos/video1.mp4",
                "start_time": "00:00:10.000",
                "end_time": "00:00:20.000"
            },
            {
                "source_s3_uri": "s3://test-bucket/videos/video2.mp4",
                "start_time": "00:00:05.000",
                "end_time": "00:00:15.000"
            }
        ]
        
        with patch.object(service, '_process_segment', new_callable=AsyncMock) as mock_process:
            with patch.object(service, '_concatenate_segments', new_callable=AsyncMock) as mock_concat:
                with patch.object(service, '_get_video_duration', return_value=30.5) as mock_duration:
                    with patch.object(service, '_upload_to_s3', new_callable=AsyncMock) as mock_upload:
                        # Mock segment files
                        mock_process.side_effect = [
                            Path("/tmp/segment_0.mp4"),
                            Path("/tmp/segment_1.mp4")
                        ]
                        
                        result = await service.generate_video_from_edl(edl, "test_output")
                        
                        # Verify result
                        assert "s3_uri" in result
                        assert "s3_key" in result
                        assert result["duration"] == 30.5
                        assert result["segment_count"] == 2
                        assert "generated-test_output_" in result["s3_key"]
                        assert result["s3_key"].startswith("videos-generated/")
                        
                        # Verify methods were called
                        assert mock_process.call_count == 2
                        mock_concat.assert_called_once()
                        mock_duration.assert_called_once()
                        mock_upload.assert_called_once()
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_process_segment_invalid_uri(self, mock_run):
        """Test that invalid S3 URI raises ValueError."""
        mock_run.return_value = Mock(returncode=0)
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        entry = {
            "source_s3_uri": "invalid://uri",
            "start_time": "00:00:10.000",
            "end_time": "00:00:20.000"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValueError, match="Invalid S3 URI"):
                await service._process_segment(entry, 0, Path(temp_dir))
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_process_segment_ffmpeg_failure(self, mock_run):
        """Test that ffmpeg extraction failure raises RuntimeError."""
        # First call succeeds (init), subsequent calls fail (extraction)
        mock_run.side_effect = [
            Mock(returncode=0),  # init check
        ]
        
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        # Now set up the failure for extraction
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffmpeg", stderr="ffmpeg error"
        )
        
        entry = {
            "source_s3_uri": "s3://test-bucket/videos/video.mp4",
            "start_time": "00:00:10.000",
            "end_time": "00:00:20.000"
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock successful download
            self.mock_s3.download.return_value = None
            
            with pytest.raises(RuntimeError, match="Failed to extract segment"):
                await service._process_segment(entry, 0, Path(temp_dir))
    
    @patch('subprocess.run')
    def test_get_video_duration_success(self, mock_run):
        """Test successful video duration extraction."""
        mock_run.side_effect = [
            Mock(returncode=0),  # init
            Mock(returncode=0, stdout="45.5\n", stderr="")  # duration
        ]
        
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_file:
            duration = service._get_video_duration(Path(temp_file.name))
            assert duration == 45.5
    
    @patch('subprocess.run')
    def test_get_video_duration_failure(self, mock_run):
        """Test video duration extraction failure."""
        mock_run.side_effect = [
            Mock(returncode=0),  # init
            subprocess.CalledProcessError(1, "ffprobe", stderr="ffprobe error")  # duration
        ]
        
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_file:
            with pytest.raises(RuntimeError, match="Failed to get video duration"):
                service._get_video_duration(Path(temp_file.name))
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_upload_to_s3_success(self, mock_run):
        """Test successful S3 upload."""
        mock_run.return_value = Mock(returncode=0)
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_file:
            await service._upload_to_s3(Path(temp_file.name), "test-key.mp4")
            
            self.mock_s3.upload.assert_called_once()
            call_args = self.mock_s3.upload.call_args
            assert call_args[1]["key"] == "test-key.mp4"
            assert call_args[1]["content_type"] == "video/mp4"
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_upload_to_s3_failure(self, mock_run):
        """Test S3 upload failure."""
        mock_run.return_value = Mock(returncode=0)
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        # Mock upload failure
        self.mock_s3.upload.side_effect = Exception("Upload failed")
        
        with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_file:
            with pytest.raises(AWSServiceError, match="Failed to upload video"):
                await service._upload_to_s3(Path(temp_file.name), "test-key.mp4")
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_concatenate_segments_success(self, mock_run):
        """Test successful segment concatenation."""
        mock_run.side_effect = [
            Mock(returncode=0),  # init
            Mock(returncode=0, stdout="", stderr="")  # concatenation
        ]
        
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mock segment files
            segment1 = temp_path / "segment_0.mp4"
            segment2 = temp_path / "segment_1.mp4"
            segment1.touch()
            segment2.touch()
            
            output_file = temp_path / "output.mp4"
            
            await service._concatenate_segments(
                [segment1, segment2],
                output_file
            )
            
            # Verify ffmpeg was called for concatenation
            assert mock_run.call_count == 2  # init + concat
    
    @patch('subprocess.run')
    @pytest.mark.asyncio
    async def test_concatenate_segments_failure(self, mock_run):
        """Test segment concatenation failure."""
        mock_run.side_effect = [
            Mock(returncode=0),  # init
        ]
        
        service = VideoGenerationService(self.mock_s3, self.mock_config)
        
        # Now set up the failure for concatenation
        mock_run.side_effect = subprocess.CalledProcessError(
            1, "ffmpeg", stderr="concat error"
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            segment1 = temp_path / "segment_0.mp4"
            segment1.touch()
            
            output_file = temp_path / "output.mp4"
            
            with pytest.raises(RuntimeError, match="Failed to concatenate segments"):
                await service._concatenate_segments([segment1], output_file)
