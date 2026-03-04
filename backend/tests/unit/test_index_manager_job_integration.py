"""Unit tests for IndexManager integration with EmbeddingJobStore.

Tests that the IndexManager correctly creates job records when adding videos.

Validates: Embedding Job Processor Requirements 1.1
"""

import sys
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient
from config import Config
from models.index import Index
from services.embedding_job_store import EmbeddingJobStore
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
        return_value="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-123"
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
        return_value="s3://test-bucket/videos/test-index-id/video-123/test.mp4"
    )
    client.bucket_name = "test-bucket"
    return client


@pytest.fixture
def mock_metadata_store():
    """Create a mock IndexMetadataStore."""
    store = Mock(spec=IndexMetadataStore)
    store.save_index = Mock()
    return store


@pytest.fixture
def mock_embedding_job_store():
    """Create a mock EmbeddingJobStore."""
    store = Mock(spec=EmbeddingJobStore)
    # Mock add_job to return a job ID
    store.add_job = Mock(return_value="job-456")
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
def index_manager(
    mock_bedrock_client,
    mock_s3_vectors_client,
    mock_config,
    mock_metadata_store,
    mock_embedding_job_store
):
    """Create an IndexManager instance with mocked dependencies."""
    return IndexManager(
        bedrock_client=mock_bedrock_client,
        s3_vectors_client=mock_s3_vectors_client,
        config=mock_config,
        metadata_store=mock_metadata_store,
        embedding_job_store=mock_embedding_job_store
    )


class TestEmbeddingJobStoreIntegration:
    """Tests for IndexManager integration with EmbeddingJobStore."""
    
    @pytest.mark.asyncio
    async def test_add_video_creates_job_record(
        self,
        index_manager,
        mock_s3_client,
        mock_metadata_store,
        mock_embedding_job_store,
        mock_bedrock_client,
        sample_index
    ):
        """Test that adding a video creates a job record in the EmbeddingJobStore.
        
        This test verifies that:
        1. The Bedrock embedding job is started
        2. A job record is created in the EmbeddingJobStore
        3. The job record contains the correct invocation ARN, video_id, index_id, and s3_uri
        4. The video's embedding_ids contains the job_id
        """
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
        
        # Verify Bedrock was called
        mock_bedrock_client.start_marengo_video_embedding.assert_called_once()
        bedrock_call_args = mock_bedrock_client.start_marengo_video_embedding.call_args
        assert bedrock_call_args.kwargs['s3_uri'].startswith('s3://')
        
        # Verify job store was called
        mock_embedding_job_store.add_job.assert_called_once()
        job_call_args = mock_embedding_job_store.add_job.call_args
        
        # Verify job record parameters
        assert job_call_args.kwargs['invocation_arn'] == "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-123"
        assert job_call_args.kwargs['index_id'] == sample_index.id
        assert job_call_args.kwargs['s3_uri'].startswith('s3://')
        assert 'video_id' in job_call_args.kwargs
        
        # Verify the video has the job_id as embedding_id
        assert len(video.embedding_ids) == 1
        assert video.embedding_ids[0] == "job-456"
    
    @pytest.mark.asyncio
    async def test_job_record_contains_video_id_from_s3_uri(
        self,
        index_manager,
        mock_s3_client,
        mock_metadata_store,
        mock_embedding_job_store,
        sample_index
    ):
        """Test that the job record extracts video_id from the S3 URI.
        
        The S3 URI format is: s3://bucket/videos/{index_id}/{video_id}/{filename}
        The job record should extract the video_id from this URI.
        """
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        # Set up S3 client to return a specific URI with a known video_id
        mock_s3_client.upload = Mock(
            return_value="s3://test-bucket/videos/test-index-id/video-abc-123/test.mp4"
        )
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute
        await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify job store was called with correct video_id
        job_call_args = mock_embedding_job_store.add_job.call_args
        assert job_call_args.kwargs['video_id'] == "video-abc-123"
    
    @pytest.mark.asyncio
    async def test_job_not_created_if_bedrock_fails(
        self,
        index_manager,
        mock_s3_client,
        mock_metadata_store,
        mock_embedding_job_store,
        mock_bedrock_client,
        sample_index
    ):
        """Test that no job record is created if Bedrock embedding generation fails.
        
        This ensures that we don't create orphaned job records for failed operations.
        """
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        mock_bedrock_client.start_marengo_video_embedding = Mock(
            side_effect=Exception("Bedrock API error")
        )
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute and verify exception is raised
        with pytest.raises(Exception) as exc_info:
            await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
        
        assert "Bedrock API error" in str(exc_info.value)
        
        # Verify job store was NOT called
        mock_embedding_job_store.add_job.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_multiple_videos_create_separate_jobs(
        self,
        index_manager,
        mock_s3_client,
        mock_metadata_store,
        mock_embedding_job_store,
        sample_index
    ):
        """Test that adding multiple videos creates separate job records.
        
        This verifies that each video upload creates its own job record.
        """
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        # Mock job store to return different job IDs
        job_ids = ["job-1", "job-2", "job-3"]
        mock_embedding_job_store.add_job = Mock(side_effect=job_ids)
        
        # Add three videos
        for i in range(3):
            video_file = BytesIO(b"fake video data")
            filename = f"test_video_{i}.mp4"
            
            video = await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
            
            # Verify each video has its own job_id
            assert video.embedding_ids[0] == job_ids[i]
        
        # Verify job store was called three times
        assert mock_embedding_job_store.add_job.call_count == 3
    
    @pytest.mark.asyncio
    async def test_job_record_has_all_required_fields(
        self,
        index_manager,
        mock_s3_client,
        mock_metadata_store,
        mock_embedding_job_store,
        mock_bedrock_client,
        sample_index
    ):
        """Test that the job record contains all required fields.
        
        This test verifies that the job record created by add_job includes:
        - invocation_arn: The ARN returned by Bedrock
        - video_id: Extracted from the S3 URI
        - index_id: The index the video belongs to
        - s3_uri: The S3 location of the video
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup
        mock_metadata_store.get_index = Mock(return_value=sample_index)
        
        expected_arn = "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-123"
        expected_s3_uri = "s3://test-bucket/videos/test-index-id/video-xyz-789/test.mp4"
        
        mock_bedrock_client.start_marengo_video_embedding = Mock(
            return_value=expected_arn
        )
        mock_s3_client.upload = Mock(return_value=expected_s3_uri)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute
        await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify job store was called with all required fields
        mock_embedding_job_store.add_job.assert_called_once()
        job_call_args = mock_embedding_job_store.add_job.call_args
        
        # Verify all required fields are present
        assert 'invocation_arn' in job_call_args.kwargs
        assert 'video_id' in job_call_args.kwargs
        assert 'index_id' in job_call_args.kwargs
        assert 's3_uri' in job_call_args.kwargs
        
        # Verify field values are correct
        assert job_call_args.kwargs['invocation_arn'] == expected_arn
        assert job_call_args.kwargs['video_id'] == "video-xyz-789"
        assert job_call_args.kwargs['index_id'] == sample_index.id
        assert job_call_args.kwargs['s3_uri'] == expected_s3_uri


class TestEmbeddingJobStoreEndToEnd:
    """End-to-end tests for job storage and retrieval."""
    
    @pytest.mark.asyncio
    async def test_job_stored_with_invocation_arn_can_be_retrieved(
        self,
        mock_bedrock_client,
        mock_s3_vectors_client,
        mock_config,
        mock_metadata_store,
        mock_s3_client,
        sample_index
    ):
        """Test that a job stored with invocation ARN can be retrieved with all fields.
        
        This is an end-to-end test that verifies:
        1. IndexManager creates a job record when adding a video
        2. The job record is stored in the EmbeddingJobStore
        3. The job can be retrieved with all fields intact
        4. The invocation ARN is correctly stored and retrieved
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Create a real EmbeddingJobStore with a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Create real job store
            job_store = EmbeddingJobStore(store_path=tmp_path)
            
            # Create IndexManager with real job store
            index_manager = IndexManager(
                bedrock_client=mock_bedrock_client,
                s3_vectors_client=mock_s3_vectors_client,
                config=mock_config,
                metadata_store=mock_metadata_store,
                embedding_job_store=job_store
            )
            
            # Setup mocks
            mock_metadata_store.get_index = Mock(return_value=sample_index)
            
            expected_arn = "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-abc"
            expected_s3_uri = "s3://test-bucket/videos/test-index-id/video-123/test.mp4"
            
            mock_bedrock_client.start_marengo_video_embedding = Mock(
                return_value=expected_arn
            )
            mock_s3_client.upload = Mock(return_value=expected_s3_uri)
            
            # Add video
            video_file = BytesIO(b"fake video data")
            filename = "test_video.mp4"
            
            video = await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
            
            # Get the job_id from the video
            job_id = video.embedding_ids[0]
            
            # Retrieve the job from the store
            job = job_store.get_job(job_id)
            
            # Verify the job exists and has all required fields
            assert job is not None
            assert job.job_id == job_id
            assert job.invocation_arn == expected_arn
            assert job.video_id == "video-123"
            assert job.index_id == sample_index.id
            assert job.s3_uri == expected_s3_uri
            assert job.status == "pending"
            assert job.retry_count == 0
            assert job.error_message is None
            assert job.output_location is None
            assert job.created_at is not None
            assert job.updated_at is not None
            
        finally:
            # Cleanup
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
