"""Unit tests for IndexManager video management methods.

Tests the add_video_to_index and list_videos_in_index methods.

Validates: Requirements 1.4, 1.5
"""

import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient
from config import Config
from exceptions import ResourceNotFoundError, ValidationError
from models.index import Index
from models.video import Video
from services.index_manager import IndexManager
from storage.metadata_store import IndexMetadataStore


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=Config)
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-bucket"
    config.s3_vectors_collection = "test-collection"
    config.max_indexes = 3
    config.marengo_model_id = "twelvelabs.marengo-v1"
    config.pegasus_model_id = "twelvelabs.pegasus-v1"
    config.use_localstack = False
    return config


@pytest.fixture
def mock_bedrock_client():
    """Create a mock BedrockClient."""
    client = Mock(spec=BedrockClient)
    # Mock the start_marengo_video_embedding method
    client.start_marengo_video_embedding = Mock(
        return_value="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-id"
    )
    return client


@pytest.fixture
def mock_s3_vectors_client():
    """Create a mock S3VectorsClient."""
    return Mock(spec=S3VectorsClient)


@pytest.fixture
def mock_s3_client():
    """Create a mock S3Client."""
    client = Mock(spec=S3Client)
    # Mock the upload method to return an S3 URI
    client.upload = Mock(
        return_value="s3://test-bucket/videos/test-index-id/test-video-id/test.mp4"
    )
    # Mock the delete method
    client.delete = Mock(return_value=True)
    return client


@pytest.fixture
def mock_metadata_store():
    """Create a mock IndexMetadataStore."""
    store = Mock(spec=IndexMetadataStore)
    # Mock save_index to do nothing
    store.save_index = Mock()
    return store


@pytest.fixture
def mock_embedding_job_store():
    """Create a mock EmbeddingJobStore."""
    from services.embedding_job_store import EmbeddingJobStore
    store = Mock(spec=EmbeddingJobStore)
    # Mock add_job to return a job ID
    store.add_job = Mock(return_value="test-job-id-123")
    return store


@pytest.fixture
def sample_index():
    """Create a sample index for testing."""
    return Index(
        id="test-index-id",
        name="Test Index",
        video_count=0,
        s3_vectors_collection_id="index-test-index-id",
        metadata={}
    )


@pytest.fixture
def index_manager(mock_bedrock_client, mock_s3_vectors_client, mock_config, mock_metadata_store, mock_embedding_job_store):
    """Create an IndexManager instance with mocked dependencies."""
    return IndexManager(
        bedrock_client=mock_bedrock_client,
        s3_vectors_client=mock_s3_vectors_client,
        config=mock_config,
        metadata_store=mock_metadata_store,
        embedding_job_store=mock_embedding_job_store
    )


class TestAddVideoToIndex:
    """Tests for add_video_to_index method."""
    
    @pytest.mark.asyncio
    async def test_add_video_to_index_success_mp4(
        self, index_manager, mock_s3_client, mock_metadata_store, sample_index
    ):
        """Test successfully adding an MP4 video to an index."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        # Create a mock video file
        video_data = b"fake video data"
        video_file = BytesIO(video_data)
        filename = "test_video.mp4"
        
        # Execute
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify
        assert isinstance(video, Video)
        assert video.index_id == sample_index.id
        assert video.filename == filename
        assert video.s3_uri.startswith("s3://")
        assert len(video.embedding_ids) > 0
        
        # Verify S3 upload was called
        mock_s3_client.upload.assert_called_once()
        call_args = mock_s3_client.upload.call_args
        assert call_args.kwargs['content_type'] == 'video/mp4'
        assert 'index_id' in call_args.kwargs['metadata']
        
        # Verify index was updated
        assert sample_index.video_count == 1
        assert 'videos' in sample_index.metadata
        assert len(sample_index.metadata['videos']) == 1
        
        # Verify metadata store was saved
        assert mock_metadata_store.save_index.call_count == 2  # Once for count, once for video list
    
    @pytest.mark.asyncio
    async def test_add_video_to_index_success_mov(
        self, index_manager, mock_s3_client, mock_metadata_store, sample_index
    ):
        """Test successfully adding a MOV video to an index."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mov"
        
        # Execute
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify
        assert video.filename == filename
        call_args = mock_s3_client.upload.call_args
        assert call_args.kwargs['content_type'] == 'video/quicktime'
    
    @pytest.mark.asyncio
    async def test_add_video_to_index_success_avi(
        self, index_manager, mock_s3_client, mock_metadata_store, sample_index
    ):
        """Test successfully adding an AVI video to an index."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.avi"
        
        # Execute
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify
        assert video.filename == filename
        call_args = mock_s3_client.upload.call_args
        assert call_args.kwargs['content_type'] == 'video/x-msvideo'
    
    @pytest.mark.asyncio
    async def test_add_video_to_index_success_mkv(
        self, index_manager, mock_s3_client, mock_metadata_store, sample_index
    ):
        """Test successfully adding an MKV video to an index."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mkv"
        
        # Execute
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify
        assert video.filename == filename
        call_args = mock_s3_client.upload.call_args
        assert call_args.kwargs['content_type'] == 'video/x-matroska'
    
    @pytest.mark.asyncio
    async def test_add_video_to_index_invalid_format(
        self, index_manager, mock_s3_client, mock_metadata_store, sample_index
    ):
        """Test adding a video with unsupported format raises ValidationError."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.wmv"  # Unsupported format
        
        # Execute and verify
        with pytest.raises(ValidationError) as exc_info:
            await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
        
        assert "Unsupported video format" in str(exc_info.value)
        
        # Verify S3 upload was not called
        mock_s3_client.upload.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_add_video_to_index_nonexistent_index(
        self, index_manager, mock_s3_client, mock_metadata_store
    ):
        """Test adding a video to a nonexistent index raises ResourceNotFoundError."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=None)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute and verify
        with pytest.raises(ResourceNotFoundError) as exc_info:
            await index_manager.add_video_to_index(
                index_id="nonexistent-id",
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
        
        assert "not found" in str(exc_info.value).lower()
        
        # Verify S3 upload was not called
        mock_s3_client.upload.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_add_video_to_index_s3_upload_failure(
        self, index_manager, mock_s3_client, mock_metadata_store, sample_index
    ):
        """Test that S3 upload failure is handled properly."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        mock_s3_client.upload = Mock(side_effect=Exception("S3 upload failed"))
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute and verify
        with pytest.raises(Exception) as exc_info:
            await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
        
        assert "S3 upload failed" in str(exc_info.value)
        
        # Verify index video count was not incremented
        assert sample_index.video_count == 0
    
    @pytest.mark.asyncio
    async def test_add_video_to_index_embedding_generation(
        self, index_manager, mock_s3_client, mock_metadata_store, sample_index, mock_bedrock_client, mock_embedding_job_store
    ):
        """Test that embedding generation is called with correct parameters."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify embedding generation was called
        mock_bedrock_client.start_marengo_video_embedding.assert_called_once()
        call_args = mock_bedrock_client.start_marengo_video_embedding.call_args
        
        # Verify S3 URI was passed
        assert call_args.kwargs['s3_uri'].startswith('s3://')
        
        # Verify embedding options were passed
        assert 'embedding_options' in call_args.kwargs
        assert isinstance(call_args.kwargs['embedding_options'], list)
        
        # Verify job store was called to create a job record
        mock_embedding_job_store.add_job.assert_called_once()
        job_call_args = mock_embedding_job_store.add_job.call_args
        
        # Verify job record has correct parameters
        assert job_call_args.kwargs['invocation_arn'] == "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-id"
        assert job_call_args.kwargs['index_id'] == sample_index.id
        assert job_call_args.kwargs['s3_uri'].startswith('s3://')
        assert 'video_id' in job_call_args.kwargs
        
        # Verify the video has the job_id as embedding_id
        assert len(video.embedding_ids) == 1
        assert video.embedding_ids[0] == "test-job-id-123"
    
    @pytest.mark.asyncio
    async def test_add_video_to_index_cleanup_on_failure(
        self, index_manager, mock_s3_client, mock_metadata_store, sample_index, mock_bedrock_client
    ):
        """Test that S3 cleanup happens when embedding generation fails."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        mock_bedrock_client.start_marengo_video_embedding = Mock(
            side_effect=Exception("Embedding generation failed")
        )
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute and verify
        with pytest.raises(Exception):
            await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
        
        # Verify S3 delete was called for cleanup
        mock_s3_client.delete.assert_called_once()


class TestListVideosInIndex:
    """Tests for list_videos_in_index method."""
    
    @pytest.mark.asyncio
    async def test_list_videos_in_index_empty(
        self, index_manager, mock_metadata_store, sample_index
    ):
        """Test listing videos in an empty index."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        # Execute
        videos = await index_manager.list_videos_in_index(sample_index.id)
        
        # Verify
        assert isinstance(videos, list)
        assert len(videos) == 0
    
    @pytest.mark.asyncio
    async def test_list_videos_in_index_with_videos(
        self, index_manager, mock_metadata_store, sample_index
    ):
        """Test listing videos in an index with videos."""
        # Setup - add some videos to the index metadata
        video1_data = {
            'id': 'video-1',
            'index_id': sample_index.id,
            'filename': 'video1.mp4',
            's3_uri': 's3://test-bucket/videos/test-index-id/video-1/video1.mp4',
            'duration': 60.0,
            'uploaded_at': '2024-01-01T00:00:00',
            'embedding_ids': ['embedding-1'],
            'metadata': {}
        }
        
        video2_data = {
            'id': 'video-2',
            'index_id': sample_index.id,
            'filename': 'video2.mov',
            's3_uri': 's3://test-bucket/videos/test-index-id/video-2/video2.mov',
            'duration': 120.0,
            'uploaded_at': '2024-01-02T00:00:00',
            'embedding_ids': ['embedding-2'],
            'metadata': {}
        }
        
        sample_index.metadata['videos'] = [video1_data, video2_data]
        sample_index.video_count = 2
        
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        # Execute
        videos = await index_manager.list_videos_in_index(sample_index.id)
        
        # Verify
        assert isinstance(videos, list)
        assert len(videos) == 2
        
        # Verify all videos are Video objects
        for video in videos:
            assert isinstance(video, Video)
        
        # Verify video data
        assert videos[0].id == 'video-1'
        assert videos[0].filename == 'video1.mp4'
        assert videos[1].id == 'video-2'
        assert videos[1].filename == 'video2.mov'
    
    @pytest.mark.asyncio
    async def test_list_videos_in_index_nonexistent_index(
        self, index_manager, mock_metadata_store
    ):
        """Test listing videos in a nonexistent index raises ResourceNotFoundError."""
        # Setup
        mock_metadata_store.get_index = Mock(return_value=None)
        
        # Execute and verify
        with pytest.raises(ResourceNotFoundError) as exc_info:
            await index_manager.list_videos_in_index("nonexistent-id")
        
        assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_list_videos_in_index_preserves_metadata(
        self, index_manager, mock_metadata_store, sample_index
    ):
        """Test that listing videos preserves all video metadata."""
        # Setup - add a video with custom metadata
        video_data = {
            'id': 'video-1',
            'index_id': sample_index.id,
            'filename': 'video1.mp4',
            's3_uri': 's3://test-bucket/videos/test-index-id/video-1/video1.mp4',
            'duration': 60.0,
            'uploaded_at': '2024-01-01T00:00:00',
            'embedding_ids': ['embedding-1', 'embedding-2'],
            'metadata': {
                's3_key': 'videos/test-index-id/video-1/video1.mp4',
                'content_type': 'video/mp4',
                'custom_field': 'custom_value'
            }
        }
        
        sample_index.metadata['videos'] = [video_data]
        sample_index.video_count = 1
        
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        # Execute
        videos = await index_manager.list_videos_in_index(sample_index.id)
        
        # Verify
        assert len(videos) == 1
        video = videos[0]
        
        # Verify all fields are preserved
        assert video.id == 'video-1'
        assert video.filename == 'video1.mp4'
        assert video.duration == 60.0
        assert len(video.embedding_ids) == 2
        assert video.metadata['custom_field'] == 'custom_value'
