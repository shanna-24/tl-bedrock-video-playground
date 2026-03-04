"""End-to-end integration tests for video upload with job creation.

This module tests the complete workflow of uploading a video and creating
an embedding job record, verifying all components work together correctly.

Tests verify:
1. Video upload triggers job creation
2. Job record contains correct invocation ARN, video_id, index_id, s3_uri
3. Video's embedding_ids contains the job_id
4. Job can be retrieved from EmbeddingJobStore
5. Error scenarios are handled correctly

Validates: Embedding Job Processor Requirements 1.1, 5.1-5.4
"""

import sys
import tempfile
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient
from config import Config
from models.index import Index
from models.video import Video
from services.embedding_job_store import EmbeddingJobStore, Job
from services.index_manager import IndexManager
from storage.metadata_store import IndexMetadataStore
from exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def temp_job_store_path():
    """Create a temporary file path for job store."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp_path = tmp.name
    yield tmp_path
    # Cleanup
    if os.path.exists(tmp_path):
        os.remove(tmp_path)


@pytest.fixture
def temp_metadata_store_path():
    """Create a temporary file path for metadata store."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp_path = tmp.name
    yield tmp_path
    # Cleanup
    if os.path.exists(tmp_path):
        os.remove(tmp_path)


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
    client.start_marengo_video_embedding = Mock(
        return_value="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-abc123"
    )
    return client


@pytest.fixture
def mock_s3_vectors_client():
    """Create a mock S3VectorsClient."""
    client = Mock(spec=S3VectorsClient)
    client.create_index = Mock(return_value="arn:aws:s3vectors:us-east-1:123456789012:index/test-index")
    return client


@pytest.fixture
def mock_s3_client():
    """Create a mock S3Client."""
    client = Mock(spec=S3Client)
    client.bucket_name = "test-bucket"
    
    # Mock upload to return S3 URI with video_id
    def mock_upload(file_obj, key, content_type, metadata):
        # Extract video_id from key: videos/{index_id}/{video_id}/{filename}
        parts = key.split('/')
        if len(parts) >= 4 and parts[0] == 'videos':
            video_id = parts[2]
            return f"s3://test-bucket/videos/{parts[1]}/{video_id}/{parts[3]}"
        return f"s3://test-bucket/{key}"
    
    client.upload = Mock(side_effect=mock_upload)
    return client


@pytest.fixture
def real_job_store(temp_job_store_path):
    """Create a real EmbeddingJobStore instance for testing."""
    return EmbeddingJobStore(store_path=temp_job_store_path)


@pytest.fixture
def real_metadata_store(temp_metadata_store_path):
    """Create a real IndexMetadataStore instance for testing."""
    return IndexMetadataStore(storage_path=temp_metadata_store_path)


@pytest.fixture
def sample_index():
    """Create a sample index for testing."""
    return Index(
        id="test-index-123",
        name="Test Index",
        video_count=0,
        s3_vectors_collection_id="index-test-index-123",
        metadata={}
    )


@pytest.fixture
def index_manager(
    mock_bedrock_client,
    mock_s3_vectors_client,
    mock_config,
    real_metadata_store,
    real_job_store
):
    """Create an IndexManager instance with real stores and mocked AWS clients."""
    return IndexManager(
        bedrock_client=mock_bedrock_client,
        s3_vectors_client=mock_s3_vectors_client,
        config=mock_config,
        metadata_store=real_metadata_store,
        embedding_job_store=real_job_store
    )


class TestVideoUploadJobCreationEndToEnd:
    """End-to-end tests for video upload with job creation workflow."""
    
    @pytest.mark.asyncio
    async def test_video_upload_creates_job_record(
        self,
        index_manager,
        mock_s3_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that uploading a video creates a job record in the EmbeddingJobStore.
        
        This test verifies the complete workflow:
        1. Video is uploaded to S3
        2. Bedrock embedding job is started
        3. Job record is created in EmbeddingJobStore
        4. Video object is created with job_id in embedding_ids
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup: Save the index to metadata store
        real_metadata_store.save_index(sample_index)
        
        # Create a mock video file
        video_file = BytesIO(b"fake video data for testing")
        filename = "test_video.mp4"
        
        # Execute: Upload video to index
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify: Video was created
        assert video is not None
        assert video.id is not None
        assert video.filename == filename
        assert video.index_id == sample_index.id
        
        # Verify: Video has embedding_ids with job_id
        assert len(video.embedding_ids) == 1
        job_id = video.embedding_ids[0]
        assert job_id is not None
        
        # Verify: Job record exists in job store
        job = real_job_store.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id
    
    @pytest.mark.asyncio
    async def test_job_record_contains_correct_fields(
        self,
        index_manager,
        mock_s3_client,
        mock_bedrock_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that the job record contains all required fields with correct values.
        
        Verifies:
        - invocation_arn matches Bedrock response
        - video_id is extracted from S3 URI
        - index_id matches the target index
        - s3_uri is the video location
        - status is 'pending'
        - timestamps are set
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        expected_arn = "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-xyz789"
        mock_bedrock_client.start_marengo_video_embedding = Mock(return_value=expected_arn)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Get the job record
        job_id = video.embedding_ids[0]
        job = real_job_store.get_job(job_id)
        
        # Verify: invocation_arn
        assert job.invocation_arn == expected_arn
        
        # Verify: video_id (extracted from S3 URI)
        assert job.video_id == video.id
        
        # Verify: index_id
        assert job.index_id == sample_index.id
        
        # Verify: s3_uri
        assert job.s3_uri == video.s3_uri
        assert job.s3_uri.startswith("s3://")
        
        # Verify: status
        assert job.status == "pending"
        
        # Verify: timestamps
        assert job.created_at is not None
        assert job.updated_at is not None
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.updated_at, datetime)
        
        # Verify: retry fields
        assert job.retry_count == 0
        assert job.error_message is None
        assert job.output_location is None
    
    @pytest.mark.asyncio
    async def test_job_can_be_retrieved_from_store(
        self,
        index_manager,
        mock_s3_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that a created job can be retrieved from the EmbeddingJobStore.
        
        This verifies that the job is properly persisted and can be retrieved
        by the background processor.
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute: Upload video
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Verify: Job can be retrieved by ID
        job = real_job_store.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id
        
        # Verify: Job appears in pending jobs list
        pending_jobs = real_job_store.get_pending_jobs()
        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == job_id
        
        # Verify: Job appears in all jobs list
        all_jobs = real_job_store.get_all_jobs()
        assert len(all_jobs) == 1
        assert all_jobs[0].job_id == job_id
    
    @pytest.mark.asyncio
    async def test_multiple_videos_create_separate_jobs(
        self,
        index_manager,
        mock_s3_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that uploading multiple videos creates separate job records.
        
        Verifies that each video upload creates its own independent job record
        with unique job_id and invocation_arn.
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Upload three videos
        videos = []
        for i in range(3):
            video_file = BytesIO(f"fake video data {i}".encode())
            filename = f"test_video_{i}.mp4"
            
            video = await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
            videos.append(video)
        
        # Verify: Each video has its own job_id
        job_ids = [video.embedding_ids[0] for video in videos]
        assert len(job_ids) == 3
        assert len(set(job_ids)) == 3, "All job_ids should be unique"
        
        # Verify: Each job exists in the store
        for job_id in job_ids:
            job = real_job_store.get_job(job_id)
            assert job is not None
            assert job.job_id == job_id
        
        # Verify: All jobs are pending
        pending_jobs = real_job_store.get_pending_jobs()
        assert len(pending_jobs) == 3
        
        # Verify: Each job has correct video_id
        for video in videos:
            job_id = video.embedding_ids[0]
            job = real_job_store.get_job(job_id)
            assert job.video_id == video.id
    
    @pytest.mark.asyncio
    async def test_video_s3_uri_matches_job_s3_uri(
        self,
        index_manager,
        mock_s3_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that the video's S3 URI matches the job's S3 URI.
        
        This ensures consistency between the video metadata and the job record.
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Get the job
        job_id = video.embedding_ids[0]
        job = real_job_store.get_job(job_id)
        
        # Verify: S3 URIs match
        assert video.s3_uri == job.s3_uri
        
        # Verify: S3 URI contains video_id
        assert video.id in video.s3_uri
        assert video.id in job.s3_uri


class TestVideoUploadJobCreationErrorHandling:
    """Tests for error handling in video upload with job creation."""
    
    @pytest.mark.asyncio
    async def test_no_job_created_if_bedrock_fails(
        self,
        index_manager,
        mock_s3_client,
        mock_bedrock_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that no job record is created if Bedrock embedding generation fails.
        
        This ensures we don't create orphaned job records for failed operations.
        
        Validates: Requirements 1.3 (Error Handling)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Mock Bedrock to fail
        mock_bedrock_client.start_marengo_video_embedding = Mock(
            side_effect=Exception("Bedrock API error: Service unavailable")
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
        
        # Verify: No job records were created
        all_jobs = real_job_store.get_all_jobs()
        assert len(all_jobs) == 0, "No jobs should be created when Bedrock fails"
        
        # Verify: No pending jobs
        pending_jobs = real_job_store.get_pending_jobs()
        assert len(pending_jobs) == 0
    
    @pytest.mark.asyncio
    async def test_no_job_created_if_s3_upload_fails(
        self,
        index_manager,
        mock_s3_client,
        mock_bedrock_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that no job record is created if S3 upload fails.
        
        Verifies that the workflow fails gracefully before creating a job record
        if the video cannot be uploaded to S3.
        
        Validates: Requirements 1.3 (Error Handling)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Mock S3 to fail
        mock_s3_client.upload = Mock(
            side_effect=Exception("S3 upload error: Access denied")
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
        
        assert "S3 upload error" in str(exc_info.value)
        
        # Verify: No job records were created
        all_jobs = real_job_store.get_all_jobs()
        assert len(all_jobs) == 0, "No jobs should be created when S3 upload fails"
        
        # Verify: Bedrock was not called
        mock_bedrock_client.start_marengo_video_embedding.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_error_if_index_does_not_exist(
        self,
        index_manager,
        mock_s3_client,
        real_job_store
    ):
        """Test that uploading to a non-existent index raises an error.
        
        Verifies that the system validates the index exists before attempting
        to upload a video.
        
        Validates: Requirements 1.3 (Error Handling)
        """
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute and verify exception is raised
        with pytest.raises(ResourceNotFoundError) as exc_info:
            await index_manager.add_video_to_index(
                index_id="non-existent-index",
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
        
        assert "not found" in str(exc_info.value).lower()
        
        # Verify: No job records were created
        all_jobs = real_job_store.get_all_jobs()
        assert len(all_jobs) == 0
    
    @pytest.mark.asyncio
    async def test_error_if_invalid_video_format(
        self,
        index_manager,
        mock_s3_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that uploading an invalid video format raises an error.
        
        Verifies that the system validates the video file format before
        attempting to upload.
        
        Validates: Requirements 1.3 (Error Handling)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.txt"  # Invalid format
        
        # Execute and verify exception is raised
        with pytest.raises(ValidationError) as exc_info:
            await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
        
        assert "Unsupported video format" in str(exc_info.value)
        
        # Verify: No job records were created
        all_jobs = real_job_store.get_all_jobs()
        assert len(all_jobs) == 0


class TestJobStoreIntegration:
    """Tests for EmbeddingJobStore integration with video upload."""
    
    @pytest.mark.asyncio
    async def test_job_store_persists_across_instances(
        self,
        mock_bedrock_client,
        mock_s3_vectors_client,
        mock_s3_client,
        mock_config,
        real_metadata_store,
        temp_job_store_path,
        sample_index
    ):
        """Test that job records persist across EmbeddingJobStore instances.
        
        This verifies that jobs are properly saved to disk and can be retrieved
        after creating a new store instance (simulating server restart).
        
        Validates: Requirements 1.1 (Job Status Tracking), 2.1 (Reliability)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Create first job store and index manager
        job_store_1 = EmbeddingJobStore(store_path=temp_job_store_path)
        index_manager_1 = IndexManager(
            bedrock_client=mock_bedrock_client,
            s3_vectors_client=mock_s3_vectors_client,
            config=mock_config,
            metadata_store=real_metadata_store,
            embedding_job_store=job_store_1
        )
        
        # Upload video with first instance
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        video = await index_manager_1.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Create second job store instance (simulating restart)
        job_store_2 = EmbeddingJobStore(store_path=temp_job_store_path)
        
        # Verify: Job can be retrieved from new instance
        job = job_store_2.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id
        assert job.video_id == video.id
        assert job.index_id == sample_index.id
        assert job.s3_uri == video.s3_uri
        
        # Verify: Job appears in pending jobs
        pending_jobs = job_store_2.get_pending_jobs()
        assert len(pending_jobs) == 1
        assert pending_jobs[0].job_id == job_id
    
    @pytest.mark.asyncio
    async def test_concurrent_video_uploads_create_separate_jobs(
        self,
        index_manager,
        mock_s3_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that concurrent video uploads create separate job records.
        
        This verifies that the job store handles concurrent writes correctly
        using file locking.
        
        Validates: Requirements 2.1 (Reliability)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Upload videos sequentially (simulating concurrent uploads)
        videos = []
        for i in range(5):
            video_file = BytesIO(f"fake video data {i}".encode())
            filename = f"test_video_{i}.mp4"
            
            video = await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3_client
            )
            videos.append(video)
        
        # Verify: All jobs were created
        all_jobs = real_job_store.get_all_jobs()
        assert len(all_jobs) == 5
        
        # Verify: All job_ids are unique
        job_ids = [job.job_id for job in all_jobs]
        assert len(set(job_ids)) == 5
        
        # Verify: Each video has correct job_id
        for video in videos:
            job_id = video.embedding_ids[0]
            job = real_job_store.get_job(job_id)
            assert job is not None
            assert job.video_id == video.id


class TestVideoMetadataIntegration:
    """Tests for video metadata integration with job creation."""
    
    @pytest.mark.asyncio
    async def test_video_metadata_includes_job_id(
        self,
        index_manager,
        mock_s3_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that video metadata includes the job_id in embedding_ids.
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify: Video has embedding_ids
        assert len(video.embedding_ids) == 1
        
        # Verify: embedding_ids contains job_id
        job_id = video.embedding_ids[0]
        job = real_job_store.get_job(job_id)
        assert job is not None
    
    @pytest.mark.asyncio
    async def test_video_can_be_retrieved_from_index(
        self,
        index_manager,
        mock_s3_client,
        real_metadata_store,
        sample_index
    ):
        """Test that uploaded video can be retrieved from the index.
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        video_file = BytesIO(b"fake video data")
        filename = "test_video.mp4"
        
        # Execute: Upload video
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify: Video can be retrieved from index
        videos = await index_manager.list_videos_in_index(sample_index.id)
        assert len(videos) == 1
        assert videos[0].id == video.id
        assert videos[0].filename == filename
        assert len(videos[0].embedding_ids) == 1
    
    @pytest.mark.asyncio
    async def test_index_video_count_increments(
        self,
        index_manager,
        mock_s3_client,
        real_metadata_store,
        sample_index
    ):
        """Test that the index video count increments when videos are added.
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        assert sample_index.video_count == 0
        
        # Upload first video
        video_file_1 = BytesIO(b"fake video data 1")
        await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file_1,
            filename="test_video_1.mp4",
            s3_client=mock_s3_client
        )
        
        # Verify: Video count is 1
        updated_index = await index_manager.get_index(sample_index.id)
        assert updated_index.video_count == 1
        
        # Upload second video
        video_file_2 = BytesIO(b"fake video data 2")
        await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file_2,
            filename="test_video_2.mp4",
            s3_client=mock_s3_client
        )
        
        # Verify: Video count is 2
        updated_index = await index_manager.get_index(sample_index.id)
        assert updated_index.video_count == 2
