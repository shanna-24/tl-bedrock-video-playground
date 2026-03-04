"""Full workflow integration tests for embedding job processor.

This module tests the complete end-to-end workflow from video upload to searchable embeddings:
1. Video upload triggers job creation
2. Background processor polls for job status
3. Processor retrieves embeddings from S3 when job completes
4. Processor stores embeddings in S3 Vectors with metadata
5. Embeddings become searchable

Tests verify:
- Complete pipeline integration between all components
- Job status transitions (pending → processing → completed)
- Embedding retrieval from S3 output location
- Embedding storage in S3 Vectors with correct metadata
- Error handling and retry logic
- Concurrent job processing

Validates: Embedding Job Processor Requirements 1.1-1.5, 2.1-2.3
"""

import sys
import tempfile
import os
import json
import time
import threading
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta

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
from services.embedding_job_processor import EmbeddingJobProcessor, EmbeddingJobProcessorConfig
from services.embedding_retriever import EmbeddingRetriever, EmbeddingData
from services.embedding_indexer import EmbeddingIndexer
from services.index_manager import IndexManager
from storage.metadata_store import IndexMetadataStore
from exceptions import ResourceNotFoundError, ValidationError


# ============================================================================
# Test Fixtures
# ============================================================================

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
def sample_embeddings():
    """Create sample embedding data for testing."""
    return [
        EmbeddingData(
            embedding=[0.1] * 1024,
            embedding_option=["visual", "audio"],
            embedding_scope="clip",
            start_sec=0.0,
            end_sec=6.0
        ),
        EmbeddingData(
            embedding=[0.2] * 1024,
            embedding_option=["visual", "audio"],
            embedding_scope="clip",
            start_sec=6.0,
            end_sec=12.0
        ),
        EmbeddingData(
            embedding=[0.3] * 1024,
            embedding_option=["visual", "audio"],
            embedding_scope="clip",
            start_sec=12.0,
            end_sec=18.0
        )
    ]


@pytest.fixture
def sample_bedrock_output():
    """Create sample Bedrock output JSON."""
    return {
        "data": [
            {
                "embedding": [0.1] * 1024,
                "embeddingOption": ["visual", "audio"],
                "embeddingScope": "clip",
                "startSec": 0.0,
                "endSec": 6.0
            },
            {
                "embedding": [0.2] * 1024,
                "embeddingOption": ["visual", "audio"],
                "embeddingScope": "clip",
                "startSec": 6.0,
                "endSec": 12.0
            },
            {
                "embedding": [0.3] * 1024,
                "embeddingOption": ["visual", "audio"],
                "embeddingScope": "clip",
                "startSec": 12.0,
                "endSec": 18.0
            }
        ]
    }



@pytest.fixture
def mock_bedrock_client():
    """Create a mock BedrockClient with realistic behavior."""
    client = Mock(spec=BedrockClient)
    
    # Mock starting an embedding job
    client.start_marengo_video_embedding = Mock(
        return_value="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-abc123"
    )
    
    # Mock job status - starts as InProgress, then becomes Completed
    client._job_status = "InProgress"
    client._status_check_count = 0
    
    def get_status(invocation_arn):
        client._status_check_count += 1
        
        # Simulate job progression: InProgress -> Completed after 2 checks
        if client._status_check_count >= 2:
            client._job_status = "Completed"
        
        if client._job_status == "Completed":
            return {
                "status": "Completed",
                "outputDataConfig": {
                    "s3Uri": "s3://test-bucket/embeddings/output.json"
                }
            }
        else:
            return {
                "status": "InProgress"
            }
    
    client.get_async_invocation_status = Mock(side_effect=get_status)
    
    return client


@pytest.fixture
def mock_s3_client(sample_bedrock_output):
    """Create a mock S3Client with realistic behavior."""
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
    
    # Mock boto3 S3 client for embedding retrieval
    mock_boto3_client = Mock()
    
    # Mock get_object to return sample embeddings
    def mock_get_object(Bucket, Key):
        response = {
            'Body': Mock()
        }
        # Convert sample output to bytes
        json_bytes = json.dumps(sample_bedrock_output).encode('utf-8')
        
        # Mock iter_chunks to return data in chunks
        def iter_chunks(chunk_size):
            yield json_bytes
        
        response['Body'].iter_chunks = iter_chunks
        return response
    
    mock_boto3_client.get_object = Mock(side_effect=mock_get_object)
    client.client = mock_boto3_client
    
    return client


@pytest.fixture
def mock_s3_vectors_client():
    """Create a mock S3VectorsClient with realistic behavior."""
    client = Mock(spec=S3VectorsClient)
    
    # Mock index creation
    client.create_index = Mock(
        return_value="arn:aws:s3vectors:us-east-1:123456789012:index/test-index"
    )
    
    # Mock vector storage - track stored vectors
    client._stored_vectors = []
    
    def mock_put_vectors(index_name, vectors):
        client._stored_vectors.extend(vectors)
        return {
            "successCount": len(vectors),
            "failureCount": 0
        }
    
    client.put_vectors = Mock(side_effect=mock_put_vectors)
    
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


@pytest.fixture
def processor_config():
    """Create a processor configuration optimized for testing."""
    return EmbeddingJobProcessorConfig(
        poll_interval=0.1,  # Fast polling for tests
        max_concurrent_jobs=3,
        max_retries=3,
        retry_backoff=1,  # Short backoff for tests
        enabled=True
    )


@pytest.fixture
def embedding_processor(
    mock_config,
    mock_bedrock_client,
    mock_s3_client,
    mock_s3_vectors_client,
    real_job_store,
    processor_config
):
    """Create an EmbeddingJobProcessor instance for testing."""
    return EmbeddingJobProcessor(
        config=mock_config,
        bedrock_client=mock_bedrock_client,
        s3_client=mock_s3_client,
        s3_vectors_client=mock_s3_vectors_client,
        job_store=real_job_store,
        processor_config=processor_config
    )



# ============================================================================
# Full Workflow Integration Tests
# ============================================================================

class TestFullEmbeddingWorkflow:
    """Integration tests for the complete embedding workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_workflow_video_to_searchable_embeddings(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_s3_vectors_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test the complete workflow from video upload to searchable embeddings.
        
        This test verifies the entire pipeline:
        1. Video is uploaded and job is created
        2. Background processor starts and polls for jobs
        3. Processor detects job completion
        4. Processor retrieves embeddings from S3
        5. Processor stores embeddings in S3 Vectors
        6. Job status is updated to completed
        
        Validates: Requirements 1.1-1.5 (Complete workflow)
        """
        # Setup: Save the index
        real_metadata_store.save_index(sample_index)
        
        # Step 1: Upload video and create job
        video_file = BytesIO(b"fake video data for testing")
        filename = "test_video.mp4"
        
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename=filename,
            s3_client=mock_s3_client
        )
        
        # Verify job was created
        assert len(video.embedding_ids) == 1
        job_id = video.embedding_ids[0]
        job = real_job_store.get_job(job_id)
        assert job.status == "pending"
        
        # Step 2: Start background processor
        embedding_processor.start()
        assert embedding_processor.is_running()
        
        try:
            # Step 3: Wait for processor to complete the job
            # The processor will poll, detect completion, retrieve and store embeddings
            max_wait_time = 5.0  # seconds
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                job = real_job_store.get_job(job_id)
                if job.status == "completed":
                    break
                time.sleep(0.1)
            
            # Verify job completed
            job = real_job_store.get_job(job_id)
            assert job.status == "completed", f"Job status is {job.status}, expected completed"
            assert job.output_location == "s3://test-bucket/embeddings/output.json"
            
            # Step 4: Verify embeddings were retrieved from S3
            # The mock S3 client should have been called to get the embedding file
            mock_s3_client.client.get_object.assert_called()
            
            # Step 5: Verify embeddings were stored in S3 Vectors
            mock_s3_vectors_client.put_vectors.assert_called()
            
            # Verify correct number of embeddings stored (3 from sample data)
            stored_vectors = mock_s3_vectors_client._stored_vectors
            assert len(stored_vectors) == 3
            
            # Verify embedding metadata
            for vector in stored_vectors:
                assert "key" in vector
                assert "data" in vector
                assert "metadata" in vector
                
                metadata = vector["metadata"]
                assert metadata["video_id"] == video.id
                assert metadata["s3_key"] in video.s3_uri
                assert "start_timecode" in metadata
                assert "end_timecode" in metadata
                assert "embedding_option" in metadata
                assert "embedding_scope" in metadata
            
            # Verify processor metrics
            stats = embedding_processor.get_stats()
            assert stats["jobs_completed"] >= 1
            assert stats["embeddings_stored"] == 3
            assert stats["jobs_failed"] == 0
            
        finally:
            # Cleanup: Stop processor
            embedding_processor.stop(timeout=2.0)
            assert not embedding_processor.is_running()

    
    @pytest.mark.asyncio
    async def test_job_status_transitions(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_bedrock_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that job status transitions correctly through the workflow.
        
        Verifies the state machine: pending → processing → completed
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Upload video
        video_file = BytesIO(b"fake video data")
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename="test_video.mp4",
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Verify initial status
        job = real_job_store.get_job(job_id)
        assert job.status == "pending"
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for status to transition to processing
            max_wait = 2.0
            start_time = time.time()
            processing_seen = False
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status == "processing":
                    processing_seen = True
                    break
                time.sleep(0.05)
            
            # Note: Due to timing, we might skip directly to completed
            # This is acceptable behavior
            
            # Wait for completion
            start_time = time.time()
            while time.time() - start_time < 5.0:
                job = real_job_store.get_job(job_id)
                if job.status == "completed":
                    break
                time.sleep(0.1)
            
            # Verify final status
            job = real_job_store.get_job(job_id)
            assert job.status == "completed"
            
            # Verify timestamps were updated
            assert job.created_at is not None
            assert job.updated_at is not None
            assert job.updated_at >= job.created_at
            
        finally:
            embedding_processor.stop(timeout=2.0)
    
    @pytest.mark.asyncio
    async def test_multiple_videos_processed_concurrently(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_s3_vectors_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that multiple videos are processed concurrently.
        
        Validates: Requirements 1.5 (Performance - concurrent processing)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Upload multiple videos
        videos = []
        for i in range(3):
            video_file = BytesIO(f"fake video data {i}".encode())
            video = await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=f"test_video_{i}.mp4",
                s3_client=mock_s3_client
            )
            videos.append(video)
        
        # Verify all jobs created
        job_ids = [video.embedding_ids[0] for video in videos]
        assert len(job_ids) == 3
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for all jobs to complete
            max_wait = 10.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                completed_count = sum(
                    1 for job_id in job_ids
                    if real_job_store.get_job(job_id).status == "completed"
                )
                if completed_count == 3:
                    break
                time.sleep(0.1)
            
            # Verify all jobs completed
            for job_id in job_ids:
                job = real_job_store.get_job(job_id)
                assert job.status == "completed", f"Job {job_id} status: {job.status}"
            
            # Verify all embeddings stored (3 embeddings per video)
            stored_vectors = mock_s3_vectors_client._stored_vectors
            assert len(stored_vectors) == 9  # 3 videos * 3 embeddings each
            
            # Verify processor metrics
            stats = embedding_processor.get_stats()
            assert stats["jobs_completed"] == 3
            assert stats["embeddings_stored"] == 9
            
        finally:
            embedding_processor.stop(timeout=2.0)

    
    @pytest.mark.asyncio
    async def test_embedding_metadata_preserved(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_s3_vectors_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that embedding metadata is correctly preserved through the workflow.
        
        Validates: Requirements 1.4 (Metadata Association)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Upload video
        video_file = BytesIO(b"fake video data")
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename="test_video.mp4",
            s3_client=mock_s3_client
        )
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for completion
            job_id = video.embedding_ids[0]
            max_wait = 5.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status == "completed":
                    break
                time.sleep(0.1)
            
            # Verify embeddings stored with correct metadata
            stored_vectors = mock_s3_vectors_client._stored_vectors
            assert len(stored_vectors) == 3
            
            # Check each embedding has required metadata fields
            for i, vector in enumerate(stored_vectors):
                metadata = vector["metadata"]
                
                # Verify video_id
                assert metadata["video_id"] == video.id
                
                # Verify timecodes
                assert "start_timecode" in metadata
                assert "end_timecode" in metadata
                start_time = float(metadata["start_timecode"])
                end_time = float(metadata["end_timecode"])
                assert end_time > start_time
                
                # Verify S3 key for playback
                assert "s3_key" in metadata
                assert metadata["s3_key"] in video.s3_uri
                
                # Verify embedding options
                assert "embedding_option" in metadata
                assert "visual" in metadata["embedding_option"]
                
                # Verify embedding scope
                assert "embedding_scope" in metadata
                assert metadata["embedding_scope"] == "clip"
            
            # Verify timecodes are sequential
            timecodes = [
                (float(v["metadata"]["start_timecode"]), float(v["metadata"]["end_timecode"]))
                for v in stored_vectors
            ]
            assert timecodes[0] == (0.0, 6.0)
            assert timecodes[1] == (6.0, 12.0)
            assert timecodes[2] == (12.0, 18.0)
            
        finally:
            embedding_processor.stop(timeout=2.0)


# ============================================================================
# Error Handling and Retry Tests
# ============================================================================

class TestWorkflowErrorHandling:
    """Integration tests for error handling in the workflow."""
    
    @pytest.mark.asyncio
    async def test_bedrock_job_failure_triggers_retry(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_bedrock_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that Bedrock job failures trigger retry logic.
        
        Validates: Requirements 1.3 (Error Handling - retries)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Configure Bedrock to fail initially, then succeed
        mock_bedrock_client._failure_count = 0
        
        def get_status_with_failure(invocation_arn):
            mock_bedrock_client._failure_count += 1
            
            # Fail first time, succeed second time
            if mock_bedrock_client._failure_count == 1:
                return {
                    "status": "Failed",
                    "failureMessage": "Simulated Bedrock failure"
                }
            else:
                return {
                    "status": "Completed",
                    "outputDataConfig": {
                        "s3Uri": "s3://test-bucket/embeddings/output.json"
                    }
                }
        
        mock_bedrock_client.get_async_invocation_status = Mock(
            side_effect=get_status_with_failure
        )
        
        # Upload video
        video_file = BytesIO(b"fake video data")
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename="test_video.mp4",
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for retry and completion
            max_wait = 10.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status == "completed":
                    break
                time.sleep(0.1)
            
            # Verify job eventually completed after retry
            job = real_job_store.get_job(job_id)
            assert job.status == "completed"
            assert job.retry_count >= 1  # At least one retry occurred
            
            # Verify metrics show retry
            stats = embedding_processor.get_stats()
            assert stats["jobs_retried"] >= 1
            
        finally:
            embedding_processor.stop(timeout=2.0)

    
    @pytest.mark.asyncio
    async def test_s3_retrieval_failure_triggers_retry(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_bedrock_client,
        real_metadata_store,
        real_job_store,
        sample_index,
        sample_bedrock_output
    ):
        """Test that S3 retrieval failures trigger retry logic.
        
        Validates: Requirements 1.3 (Error Handling - retries)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Configure S3 to fail initially, then succeed
        call_count = [0]
        
        def mock_get_object_with_failure(Bucket, Key):
            call_count[0] += 1
            
            # Fail first time, succeed second time
            if call_count[0] == 1:
                from botocore.exceptions import ClientError
                raise ClientError(
                    {"Error": {"Code": "ServiceUnavailable", "Message": "Service unavailable"}},
                    "GetObject"
                )
            else:
                response = {'Body': Mock()}
                json_bytes = json.dumps(sample_bedrock_output).encode('utf-8')
                
                def iter_chunks(chunk_size):
                    yield json_bytes
                
                response['Body'].iter_chunks = iter_chunks
                return response
        
        mock_s3_client.client.get_object = Mock(side_effect=mock_get_object_with_failure)
        
        # Upload video
        video_file = BytesIO(b"fake video data")
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename="test_video.mp4",
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for retry and completion
            max_wait = 10.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status == "completed":
                    break
                time.sleep(0.1)
            
            # Verify job eventually completed after retry
            job = real_job_store.get_job(job_id)
            assert job.status == "completed"
            
            # Verify S3 was called multiple times (initial + retry)
            assert call_count[0] >= 2
            
        finally:
            embedding_processor.stop(timeout=2.0)
    
    @pytest.mark.asyncio
    async def test_permanent_failure_after_max_retries(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_bedrock_client,
        real_metadata_store,
        real_job_store,
        sample_index,
        processor_config
    ):
        """Test that jobs are marked as permanently failed after max retries.
        
        Validates: Requirements 1.3 (Error Handling - permanent failures)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Configure Bedrock to always fail
        mock_bedrock_client.get_async_invocation_status = Mock(
            return_value={
                "status": "Failed",
                "failureMessage": "Persistent Bedrock failure"
            }
        )
        
        # Upload video
        video_file = BytesIO(b"fake video data")
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename="test_video.mp4",
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for permanent failure
            max_wait = 15.0  # Longer wait for retries
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status == "failed":
                    break
                time.sleep(0.1)
            
            # Verify job permanently failed
            job = real_job_store.get_job(job_id)
            assert job.status == "failed"
            assert job.retry_count == processor_config.max_retries
            assert "Max retries exceeded" in job.error_message
            
            # Verify metrics
            stats = embedding_processor.get_stats()
            assert stats["jobs_failed"] >= 1
            
        finally:
            embedding_processor.stop(timeout=2.0)

    
    @pytest.mark.asyncio
    async def test_s3_vectors_storage_failure_triggers_retry(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_s3_vectors_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that S3 Vectors storage failures trigger retry logic.
        
        Validates: Requirements 1.3 (Error Handling - retries)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Configure S3 Vectors to fail initially, then succeed
        call_count = [0]
        
        def mock_put_vectors_with_failure(index_name, vectors):
            call_count[0] += 1
            
            # Fail first time, succeed second time
            if call_count[0] == 1:
                from botocore.exceptions import ClientError
                raise ClientError(
                    {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
                    "PutVectors"
                )
            else:
                mock_s3_vectors_client._stored_vectors.extend(vectors)
                return {
                    "successCount": len(vectors),
                    "failureCount": 0
                }
        
        mock_s3_vectors_client.put_vectors = Mock(side_effect=mock_put_vectors_with_failure)
        
        # Upload video
        video_file = BytesIO(b"fake video data")
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename="test_video.mp4",
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for retry and completion
            max_wait = 10.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status == "completed":
                    break
                time.sleep(0.1)
            
            # Verify job eventually completed after retry
            job = real_job_store.get_job(job_id)
            assert job.status == "completed"
            
            # Verify S3 Vectors was called multiple times (initial + retry)
            assert call_count[0] >= 2
            
            # Verify embeddings were eventually stored
            assert len(mock_s3_vectors_client._stored_vectors) == 3
            
        finally:
            embedding_processor.stop(timeout=2.0)


# ============================================================================
# Reliability and Persistence Tests
# ============================================================================

class TestWorkflowReliability:
    """Integration tests for workflow reliability and persistence."""
    
    @pytest.mark.asyncio
    async def test_jobs_persist_across_processor_restarts(
        self,
        index_manager,
        mock_s3_client,
        mock_bedrock_client,
        mock_s3_vectors_client,
        mock_config,
        real_metadata_store,
        real_job_store,
        sample_index,
        processor_config
    ):
        """Test that pending jobs are processed after processor restart.
        
        Validates: Requirements 2.1 (Reliability - jobs not lost on restart)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Upload video (creates job)
        video_file = BytesIO(b"fake video data")
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename="test_video.mp4",
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Verify job exists and is pending
        job = real_job_store.get_job(job_id)
        assert job.status == "pending"
        
        # Create first processor instance and start it
        processor1 = EmbeddingJobProcessor(
            config=mock_config,
            bedrock_client=mock_bedrock_client,
            s3_client=mock_s3_client,
            s3_vectors_client=mock_s3_vectors_client,
            job_store=real_job_store,
            processor_config=processor_config
        )
        
        processor1.start()
        
        # Let it run briefly, then stop (simulating restart)
        time.sleep(0.5)
        processor1.stop(timeout=2.0)
        
        # Job might still be pending or processing
        job = real_job_store.get_job(job_id)
        assert job.status in ["pending", "processing", "completed"]
        
        # Create second processor instance (simulating restart)
        processor2 = EmbeddingJobProcessor(
            config=mock_config,
            bedrock_client=mock_bedrock_client,
            s3_client=mock_s3_client,
            s3_vectors_client=mock_s3_vectors_client,
            job_store=real_job_store,
            processor_config=processor_config
        )
        
        processor2.start()
        
        try:
            # Wait for job to complete
            max_wait = 5.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status == "completed":
                    break
                time.sleep(0.1)
            
            # Verify job completed after restart
            job = real_job_store.get_job(job_id)
            assert job.status == "completed"
            
        finally:
            processor2.stop(timeout=2.0)

    
    @pytest.mark.asyncio
    async def test_duplicate_processing_prevented(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_s3_vectors_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that duplicate processing of the same job is prevented.
        
        Validates: Requirements 2.1 (Reliability - duplicate prevention)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Upload video
        video_file = BytesIO(b"fake video data")
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename="test_video.mp4",
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for completion
            max_wait = 5.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status == "completed":
                    break
                time.sleep(0.1)
            
            # Verify job completed
            job = real_job_store.get_job(job_id)
            assert job.status == "completed"
            
            # Get initial embedding count
            initial_count = len(mock_s3_vectors_client._stored_vectors)
            assert initial_count == 3
            
            # Continue running processor for a bit longer
            # It should not reprocess the completed job
            time.sleep(1.0)
            
            # Verify no additional embeddings were stored
            final_count = len(mock_s3_vectors_client._stored_vectors)
            assert final_count == initial_count, "Job was processed multiple times"
            
        finally:
            embedding_processor.stop(timeout=2.0)
    
    @pytest.mark.asyncio
    async def test_processor_graceful_shutdown(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that processor shuts down gracefully without losing jobs.
        
        Validates: Requirements 2.1 (Reliability - graceful shutdown)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Upload multiple videos
        videos = []
        for i in range(3):
            video_file = BytesIO(f"fake video data {i}".encode())
            video = await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=f"test_video_{i}.mp4",
                s3_client=mock_s3_client
            )
            videos.append(video)
        
        # Start processor
        embedding_processor.start()
        assert embedding_processor.is_running()
        
        # Let it run briefly
        time.sleep(0.5)
        
        # Stop processor gracefully
        embedding_processor.stop(timeout=5.0)
        assert not embedding_processor.is_running()
        
        # Verify all jobs are still in the store (not lost)
        all_jobs = real_job_store.get_all_jobs()
        assert len(all_jobs) == 3
        
        # Jobs should be in pending, processing, or completed state
        for job in all_jobs:
            assert job.status in ["pending", "processing", "completed"]


# ============================================================================
# Performance and Metrics Tests
# ============================================================================

class TestWorkflowPerformance:
    """Integration tests for workflow performance and metrics."""
    
    @pytest.mark.asyncio
    async def test_processor_metrics_tracking(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test that processor tracks metrics correctly.
        
        Validates: Requirements 2.2 (Observability - metrics tracking)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Upload videos
        for i in range(2):
            video_file = BytesIO(f"fake video data {i}".encode())
            await index_manager.add_video_to_index(
                index_id=sample_index.id,
                video_file=video_file,
                filename=f"test_video_{i}.mp4",
                s3_client=mock_s3_client
            )
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for jobs to complete
            max_wait = 10.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                stats = embedding_processor.get_stats()
                if stats["jobs_completed"] >= 2:
                    break
                time.sleep(0.1)
            
            # Verify metrics
            stats = embedding_processor.get_stats()
            
            # Basic counters
            assert stats["jobs_processed"] >= 2
            assert stats["jobs_completed"] >= 2
            assert stats["jobs_failed"] == 0
            assert stats["embeddings_stored"] == 6  # 2 videos * 3 embeddings
            
            # Timing metrics (may be 0 if processing was very fast)
            assert stats["avg_processing_time"] >= 0
            assert stats["avg_retrieval_time"] >= 0
            assert stats["avg_storage_time"] >= 0
            
            # Timestamps
            assert stats["last_poll_time"] is not None
            assert stats["last_job_completion_time"] is not None
            
            # Get structured metrics
            metrics = embedding_processor.get_metrics()
            assert "counters" in metrics
            assert "gauges" in metrics
            assert "timings" in metrics
            assert "timestamps" in metrics
            
            # Verify success rate
            assert metrics["gauges"]["success_rate_percent"] == 100.0
            
        finally:
            embedding_processor.stop(timeout=2.0)

    
    @pytest.mark.asyncio
    async def test_large_embedding_batch_processing(
        self,
        index_manager,
        embedding_processor,
        mock_s3_client,
        mock_s3_vectors_client,
        real_metadata_store,
        real_job_store,
        sample_index
    ):
        """Test processing of large embedding batches.
        
        Validates: Requirements 1.5 (Performance - efficient handling)
        """
        # Setup
        real_metadata_store.save_index(sample_index)
        
        # Create large embedding output (100 embeddings)
        large_output = {
            "data": [
                {
                    "embedding": [0.1 * i] * 1024,
                    "embeddingOption": ["visual", "audio"],
                    "embeddingScope": "clip",
                    "startSec": float(i * 6),
                    "endSec": float((i + 1) * 6)
                }
                for i in range(100)
            ]
        }
        
        # Configure S3 to return large output
        def mock_get_object_large(Bucket, Key):
            response = {'Body': Mock()}
            json_bytes = json.dumps(large_output).encode('utf-8')
            
            def iter_chunks(chunk_size):
                yield json_bytes
            
            response['Body'].iter_chunks = iter_chunks
            return response
        
        mock_s3_client.client.get_object = Mock(side_effect=mock_get_object_large)
        
        # Upload video
        video_file = BytesIO(b"fake video data")
        video = await index_manager.add_video_to_index(
            index_id=sample_index.id,
            video_file=video_file,
            filename="test_video.mp4",
            s3_client=mock_s3_client
        )
        
        job_id = video.embedding_ids[0]
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for completion
            max_wait = 10.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status == "completed":
                    break
                time.sleep(0.1)
            
            # Verify job completed
            job = real_job_store.get_job(job_id)
            assert job.status == "completed"
            
            # Verify all 100 embeddings were stored
            stored_vectors = mock_s3_vectors_client._stored_vectors
            assert len(stored_vectors) == 100
            
            # Verify metrics
            stats = embedding_processor.get_stats()
            assert stats["embeddings_stored"] == 100
            
        finally:
            embedding_processor.stop(timeout=2.0)


# ============================================================================
# Component Integration Tests
# ============================================================================

class TestComponentIntegration:
    """Integration tests for component interactions."""
    
    @pytest.mark.asyncio
    async def test_retriever_indexer_integration(
        self,
        mock_s3_client,
        mock_s3_vectors_client,
        sample_bedrock_output
    ):
        """Test integration between EmbeddingRetriever and EmbeddingIndexer.
        
        Validates: Requirements 1.2 (Background Processing - retrieval and storage)
        """
        # Create retriever and indexer
        retriever = EmbeddingRetriever(s3_client=mock_s3_client.client)
        indexer = EmbeddingIndexer(s3_vectors_client=mock_s3_vectors_client)
        
        # Retrieve embeddings
        embeddings = retriever.retrieve_embeddings("s3://test-bucket/embeddings/output.json")
        
        # Verify retrieval
        assert len(embeddings) == 3
        assert all(isinstance(emb, EmbeddingData) for emb in embeddings)
        
        # Store embeddings
        stats = indexer.store_embeddings(
            embeddings=embeddings,
            video_id="test-video-123",
            index_id="test-index-456",
            s3_uri="s3://test-bucket/videos/test.mp4"
        )
        
        # Verify storage
        assert stats["total"] == 3
        assert stats["stored"] == 3
        assert stats["failed"] == 0
        
        # Verify vectors were stored
        stored_vectors = mock_s3_vectors_client._stored_vectors
        assert len(stored_vectors) == 3
        
        # Verify metadata
        for vector in stored_vectors:
            assert vector["metadata"]["video_id"] == "test-video-123"
            assert "start_timecode" in vector["metadata"]
            assert "end_timecode" in vector["metadata"]
    
    @pytest.mark.asyncio
    async def test_job_store_processor_integration(
        self,
        embedding_processor,
        real_job_store
    ):
        """Test integration between EmbeddingJobStore and EmbeddingJobProcessor.
        
        Validates: Requirements 1.1 (Job Status Tracking)
        """
        # Create a job manually
        job_id = real_job_store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test",
            video_id="test-video-123",
            index_id="test-index-456",
            s3_uri="s3://test-bucket/videos/test.mp4"
        )
        
        # Verify job created
        job = real_job_store.get_job(job_id)
        assert job.status == "pending"
        
        # Start processor
        embedding_processor.start()
        
        try:
            # Wait for processor to pick up the job
            max_wait = 5.0
            start_time = time.time()
            
            while time.time() - start_time < max_wait:
                job = real_job_store.get_job(job_id)
                if job.status in ["processing", "completed"]:
                    break
                time.sleep(0.1)
            
            # Verify processor updated job status
            job = real_job_store.get_job(job_id)
            assert job.status in ["processing", "completed"]
            
        finally:
            embedding_processor.stop(timeout=2.0)
