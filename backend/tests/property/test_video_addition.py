"""Property-based tests for video addition.

Feature: tl-video-playground
Property 3: Video Addition Creates Storage and Embeddings

**Validates: Requirements 1.4**

For any valid video file and existing index, adding the video to the index 
should result in the video being stored in S3, embeddings being generated and 
stored in S3 Vectors, and the video appearing in the index's video list.
"""

import sys
import tempfile
import io
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

import pytest
from hypothesis import given, strategies as st, settings, assume

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from storage.metadata_store import IndexMetadataStore
from models.index import Index
from models.video import Video
from services.index_manager import IndexManager
from aws.s3_vectors_client import S3VectorsClient
from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from config import Config


# Custom strategies for generating test data
@st.composite
def valid_index_name(draw):
    """Generate valid index names (alphanumeric, 3-50 chars)."""
    length = draw(st.integers(min_value=3, max_value=50))
    chars = st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters=' -_'
    )
    name = draw(st.text(alphabet=chars, min_size=length, max_size=length))
    
    # Strip and check if still valid length
    stripped = name.strip()
    if len(stripped) >= 3:
        return stripped
    else:
        # Generate a new name that's guaranteed to be valid after stripping
        # Use only alphanumeric characters (no spaces) to avoid stripping issues
        return draw(st.text(
            alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
            min_size=3,
            max_size=50
        ))


@st.composite
def valid_collection_id(draw):
    """Generate valid S3 Vectors collection IDs."""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'),
        min_size=5,
        max_size=100
    ))


@st.composite
def valid_index(draw):
    """Generate a valid Index instance."""
    name = draw(valid_index_name())
    collection_id = draw(valid_collection_id())
    
    index = Index.create(name=name, s3_vectors_collection_id=collection_id)
    
    return index


@st.composite
def valid_video_filename(draw):
    """Generate valid video filenames with supported extensions."""
    # Generate base filename (alphanumeric with spaces, hyphens, underscores)
    base_length = draw(st.integers(min_value=1, max_value=50))
    chars = st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),
        whitelist_characters=' -_'
    )
    base_name = draw(st.text(alphabet=chars, min_size=base_length, max_size=base_length))
    
    # Ensure base name is not empty after stripping
    if not base_name.strip():
        base_name = "video"
    else:
        base_name = base_name.strip()
    
    # Choose a random supported extension
    extension = draw(st.sampled_from(['.mp4', '.mov', '.avi', '.mkv']))
    
    return f"{base_name}{extension}"


@st.composite
def valid_video_content(draw):
    """Generate valid video file content (mock binary data)."""
    # Generate random binary data to simulate video content
    # Size between 1KB and 100KB for testing
    size = draw(st.integers(min_value=1024, max_value=102400))
    content = draw(st.binary(min_size=size, max_size=size))
    return content


class TestVideoAdditionProperties:
    """Property-based tests for video addition."""
    
    @given(
        index=valid_index(),
        filename=valid_video_filename(),
        video_content=valid_video_content()
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_video_addition_creates_s3_object(
        self,
        index,
        filename,
        video_content
    ):
        """Property 3: Video addition creates S3 object.
        
        **Validates: Requirements 1.4**
        
        For any valid video file and existing index, adding the video should
        result in the video being uploaded to S3 with the correct key and metadata.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Create mock S3 client
            mock_s3 = Mock(spec=S3Client)
            mock_s3.upload = Mock(return_value=f"s3://test-bucket/videos/{index.id}/test-video-id/{filename}")
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            mock_bedrock.start_marengo_video_embedding = Mock(
                return_value="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-id"
            )
            
            # Create mock config
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager
            index_manager = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store
            )
            
            # Create file-like object from video content
            video_file = io.BytesIO(video_content)
            
            # Add video to index
            video = await index_manager.add_video_to_index(
                index_id=index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3
            )
            
            # Verify S3 upload was called
            mock_s3.upload.assert_called_once()
            
            # Verify upload was called with correct parameters
            call_args = mock_s3.upload.call_args
            assert call_args is not None
            
            # Check file object was passed
            assert isinstance(call_args[1]['file_obj'], io.BytesIO)
            
            # Check S3 key format
            s3_key = call_args[1]['key']
            assert s3_key.startswith(f"videos/{index.id}/")
            assert s3_key.endswith(f"/{filename}")
            
            # Check content type is set correctly
            content_type = call_args[1]['content_type']
            if filename.endswith('.mp4'):
                assert content_type == 'video/mp4'
            elif filename.endswith('.mov'):
                assert content_type == 'video/quicktime'
            elif filename.endswith('.avi'):
                assert content_type == 'video/x-msvideo'
            elif filename.endswith('.mkv'):
                assert content_type == 'video/x-matroska'
            
            # Check metadata includes index_id and filename
            metadata = call_args[1]['metadata']
            assert metadata['index_id'] == index.id
            assert metadata['original_filename'] == filename
    
    @given(
        index=valid_index(),
        filename=valid_video_filename(),
        video_content=valid_video_content()
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_video_addition_generates_embeddings(
        self,
        index,
        filename,
        video_content
    ):
        """Property 3: Video addition generates embeddings.
        
        **Validates: Requirements 1.4**
        
        For any valid video file and existing index, adding the video should
        trigger embedding generation using the Marengo model.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Create mock S3 client
            mock_s3 = Mock(spec=S3Client)
            s3_uri = f"s3://test-bucket/videos/{index.id}/test-video-id/{filename}"
            mock_s3.upload = Mock(return_value=s3_uri)
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            job_arn = "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-id"
            mock_bedrock.start_marengo_video_embedding = Mock(return_value=job_arn)
            
            # Create mock config
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager
            index_manager = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store
            )
            
            # Create file-like object from video content
            video_file = io.BytesIO(video_content)
            
            # Add video to index
            video = await index_manager.add_video_to_index(
                index_id=index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3
            )
            
            # Verify Bedrock embedding generation was called
            mock_bedrock.start_marengo_video_embedding.assert_called_once()
            
            # Verify it was called with the correct S3 URI
            call_args = mock_bedrock.start_marengo_video_embedding.call_args
            assert call_args[1]['s3_uri'] == s3_uri
            
            # Verify embedding options are specified
            assert 's3_uri' in call_args[1]
            assert 'embedding_options' in call_args[1]
            
            # Verify video has embedding IDs
            assert len(video.embedding_ids) > 0
            assert video.embedding_ids[0].startswith('embedding-')
    
    @given(
        index=valid_index(),
        filename=valid_video_filename(),
        video_content=valid_video_content()
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_video_addition_appears_in_index(
        self,
        index,
        filename,
        video_content
    ):
        """Property 3: Video addition makes video appear in index's video list.
        
        **Validates: Requirements 1.4**
        
        For any valid video file and existing index, adding the video should
        result in the video appearing in the index's video list with correct metadata.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Create mock S3 client
            mock_s3 = Mock(spec=S3Client)
            s3_uri = f"s3://test-bucket/videos/{index.id}/test-video-id/{filename}"
            mock_s3.upload = Mock(return_value=s3_uri)
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            mock_bedrock.start_marengo_video_embedding = Mock(
                return_value="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-id"
            )
            
            # Create mock config
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager
            index_manager = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store
            )
            
            # Create file-like object from video content
            video_file = io.BytesIO(video_content)
            
            # Add video to index
            video = await index_manager.add_video_to_index(
                index_id=index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3
            )
            
            # List videos in index
            videos = await index_manager.list_videos_in_index(index.id)
            
            # Verify video appears in list
            assert len(videos) == 1
            
            # Verify video data is correct
            listed_video = videos[0]
            assert listed_video.id == video.id
            assert listed_video.index_id == index.id
            assert listed_video.filename == filename
            assert listed_video.s3_uri == s3_uri
            assert listed_video.duration > 0
            assert len(listed_video.embedding_ids) > 0
    
    @given(
        index=valid_index(),
        filename=valid_video_filename(),
        video_content=valid_video_content()
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_video_addition_updates_index_count(
        self,
        index,
        filename,
        video_content
    ):
        """Property 3: Video addition updates index video count.
        
        **Validates: Requirements 1.4**
        
        For any valid video file and existing index, adding the video should
        increment the index's video count by 1.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Record initial video count
            initial_count = index.video_count
            
            # Create mock S3 client
            mock_s3 = Mock(spec=S3Client)
            mock_s3.upload = Mock(
                return_value=f"s3://test-bucket/videos/{index.id}/test-video-id/{filename}"
            )
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            mock_bedrock.start_marengo_video_embedding = Mock(
                return_value="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-id"
            )
            
            # Create mock config
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager
            index_manager = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store
            )
            
            # Create file-like object from video content
            video_file = io.BytesIO(video_content)
            
            # Add video to index
            await index_manager.add_video_to_index(
                index_id=index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3
            )
            
            # Retrieve updated index
            updated_index = await index_manager.get_index(index.id)
            
            # Verify video count was incremented
            assert updated_index.video_count == initial_count + 1
    
    @given(
        index=valid_index(),
        videos=st.lists(
            st.tuples(valid_video_filename(), valid_video_content()),
            min_size=1,
            max_size=5,
            unique_by=lambda x: x[0]  # Unique filenames
        )
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_multiple_video_additions(
        self,
        index,
        videos
    ):
        """Property 3: Multiple video additions work correctly.
        
        **Validates: Requirements 1.4**
        
        For any list of valid videos and an existing index, adding multiple
        videos should result in all videos being stored, having embeddings,
        and appearing in the index's video list.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Create mock S3 client
            mock_s3 = Mock(spec=S3Client)
            
            def mock_upload(file_obj, key, content_type=None, metadata=None):
                return f"s3://test-bucket/{key}"
            
            mock_s3.upload = Mock(side_effect=mock_upload)
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            
            job_counter = [0]  # Use list to allow modification in nested function
            
            def mock_embedding(s3_uri, embedding_options):
                job_counter[0] += 1
                return f"arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/job-{job_counter[0]}"
            
            mock_bedrock.start_marengo_video_embedding = Mock(side_effect=mock_embedding)
            
            # Create mock config
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager
            index_manager = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store
            )
            
            # Add all videos
            added_videos = []
            for filename, video_content in videos:
                video_file = io.BytesIO(video_content)
                video = await index_manager.add_video_to_index(
                    index_id=index.id,
                    video_file=video_file,
                    filename=filename,
                    s3_client=mock_s3
                )
                added_videos.append(video)
            
            # Verify all videos were uploaded to S3
            assert mock_s3.upload.call_count == len(videos)
            
            # Verify all videos had embeddings generated
            assert mock_bedrock.start_marengo_video_embedding.call_count == len(videos)
            
            # List videos in index
            listed_videos = await index_manager.list_videos_in_index(index.id)
            
            # Verify all videos appear in list
            assert len(listed_videos) == len(videos)
            
            # Verify video IDs match
            added_ids = {v.id for v in added_videos}
            listed_ids = {v.id for v in listed_videos}
            assert added_ids == listed_ids
            
            # Verify index video count is correct
            updated_index = await index_manager.get_index(index.id)
            assert updated_index.video_count == len(videos)
    
    @given(
        index=valid_index(),
        filename=valid_video_filename(),
        video_content=valid_video_content()
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_video_addition_returns_video_object(
        self,
        index,
        filename,
        video_content
    ):
        """Property 3: Video addition returns valid Video object.
        
        **Validates: Requirements 1.4**
        
        For any valid video file and existing index, adding the video should
        return a Video object with all required fields populated correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Create mock S3 client
            mock_s3 = Mock(spec=S3Client)
            s3_uri = f"s3://test-bucket/videos/{index.id}/test-video-id/{filename}"
            mock_s3.upload = Mock(return_value=s3_uri)
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            mock_bedrock.start_marengo_video_embedding = Mock(
                return_value="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-id"
            )
            
            # Create mock config
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager
            index_manager = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store
            )
            
            # Create file-like object from video content
            video_file = io.BytesIO(video_content)
            
            # Add video to index
            video = await index_manager.add_video_to_index(
                index_id=index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3
            )
            
            # Verify Video object is returned
            assert isinstance(video, Video)
            
            # Verify all required fields are present
            assert video.id is not None
            assert len(video.id) > 0
            assert video.index_id == index.id
            assert video.filename == filename
            assert video.s3_uri == s3_uri
            assert video.duration > 0
            assert video.uploaded_at is not None
            assert len(video.embedding_ids) > 0
            assert isinstance(video.metadata, dict)
            
            # Verify metadata contains expected keys
            assert 's3_key' in video.metadata
            assert 'content_type' in video.metadata
    
    @given(
        index=valid_index(),
        filename=valid_video_filename(),
        video_content=valid_video_content()
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_video_addition_persists_across_restart(
        self,
        index,
        filename,
        video_content
    ):
        """Property 3: Video addition persists across system restart.
        
        **Validates: Requirements 1.4**
        
        For any valid video file and existing index, after adding the video
        and simulating a system restart, the video should still appear in
        the index's video list.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store1.save_index(index)
            
            # Create mock S3 client
            mock_s3 = Mock(spec=S3Client)
            s3_uri = f"s3://test-bucket/videos/{index.id}/test-video-id/{filename}"
            mock_s3.upload = Mock(return_value=s3_uri)
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            mock_bedrock.start_marengo_video_embedding = Mock(
                return_value="arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-id"
            )
            
            # Create mock config
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager
            index_manager1 = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store1
            )
            
            # Create file-like object from video content
            video_file = io.BytesIO(video_content)
            
            # Add video to index
            video = await index_manager1.add_video_to_index(
                index_id=index.id,
                video_file=video_file,
                filename=filename,
                s3_client=mock_s3
            )
            
            # Simulate system restart with new metadata store and index manager
            metadata_store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
            index_manager2 = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store2
            )
            
            # List videos after restart
            videos = await index_manager2.list_videos_in_index(index.id)
            
            # Verify video still appears
            assert len(videos) == 1
            assert videos[0].id == video.id
            assert videos[0].filename == filename
            assert videos[0].s3_uri == s3_uri
