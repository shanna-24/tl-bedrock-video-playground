"""Property-based tests for video listing.

Feature: tl-video-playground
Property 4: Video Listing Returns All Videos

**Validates: Requirements 1.5**

For any index with videos, listing the videos should return all videos that 
were added to that index with their complete metadata.
"""

import sys
import tempfile
import io
from pathlib import Path
from unittest.mock import Mock

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

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


class TestVideoListingProperties:
    """Property-based tests for video listing."""
    
    @given(
        index=valid_index(),
        videos=st.lists(
            st.tuples(valid_video_filename(), valid_video_content()),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x[0]  # Unique filenames
        )
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_listing_returns_all_videos(
        self,
        index,
        videos
    ):
        """Property 4: Listing returns all added videos.
        
        **Validates: Requirements 1.5**
        
        For any index with videos, listing the videos should return all videos
        that were added to that index.
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
            
            # List videos in index
            listed_videos = await index_manager.list_videos_in_index(index.id)
            
            # Verify all videos are returned
            assert len(listed_videos) == len(videos), \
                f"Expected {len(videos)} videos, but got {len(listed_videos)}"
            
            # Verify video IDs match
            added_ids = {v.id for v in added_videos}
            listed_ids = {v.id for v in listed_videos}
            assert added_ids == listed_ids, \
                "Listed video IDs do not match added video IDs"
    
    @given(
        index=valid_index(),
        videos=st.lists(
            st.tuples(valid_video_filename(), valid_video_content()),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x[0]  # Unique filenames
        )
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_listing_returns_complete_metadata(
        self,
        index,
        videos
    ):
        """Property 4: Listing returns videos with complete metadata.
        
        **Validates: Requirements 1.5**
        
        For any index with videos, listing the videos should return all videos
        with their complete metadata including id, index_id, filename, s3_uri,
        duration, embedding_ids, and metadata.
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
            
            job_counter = [0]
            
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
            for filename, video_content in videos:
                video_file = io.BytesIO(video_content)
                await index_manager.add_video_to_index(
                    index_id=index.id,
                    video_file=video_file,
                    filename=filename,
                    s3_client=mock_s3
                )
            
            # List videos in index
            listed_videos = await index_manager.list_videos_in_index(index.id)
            
            # Verify all videos have complete metadata
            for video in listed_videos:
                # Verify all required fields are present and valid
                assert video.id is not None, "Video ID is missing"
                assert len(video.id) > 0, "Video ID is empty"
                
                assert video.index_id == index.id, \
                    f"Video index_id {video.index_id} does not match expected {index.id}"
                
                assert video.filename is not None, "Video filename is missing"
                assert len(video.filename) > 0, "Video filename is empty"
                
                assert video.s3_uri is not None, "Video s3_uri is missing"
                assert video.s3_uri.startswith('s3://'), \
                    f"Video s3_uri {video.s3_uri} does not start with 's3://'"
                
                assert video.duration > 0, \
                    f"Video duration {video.duration} is not positive"
                
                assert video.uploaded_at is not None, "Video uploaded_at is missing"
                
                assert len(video.embedding_ids) > 0, \
                    "Video embedding_ids list is empty"
                
                assert isinstance(video.metadata, dict), \
                    f"Video metadata is not a dict, got {type(video.metadata)}"
    
    @given(
        index=valid_index(),
        videos=st.lists(
            st.tuples(valid_video_filename(), valid_video_content()),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x[0]  # Unique filenames
        )
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_listing_preserves_video_data(
        self,
        index,
        videos
    ):
        """Property 4: Listing preserves exact video data.
        
        **Validates: Requirements 1.5**
        
        For any index with videos, the data returned by listing should exactly
        match the data from when the videos were added.
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
            
            job_counter = [0]
            
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
            
            # Add all videos and store their data
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
            
            # List videos in index
            listed_videos = await index_manager.list_videos_in_index(index.id)
            
            # Create lookup map for listed videos
            listed_by_id = {v.id: v for v in listed_videos}
            
            # Verify each added video's data is preserved in listing
            for added_video in added_videos:
                assert added_video.id in listed_by_id, \
                    f"Added video {added_video.id} not found in listing"
                
                listed_video = listed_by_id[added_video.id]
                
                # Verify all fields match
                assert listed_video.id == added_video.id
                assert listed_video.index_id == added_video.index_id
                assert listed_video.filename == added_video.filename
                assert listed_video.s3_uri == added_video.s3_uri
                assert listed_video.duration == added_video.duration
                assert listed_video.embedding_ids == added_video.embedding_ids
                assert listed_video.metadata == added_video.metadata
    
    @given(
        index=valid_index(),
        videos=st.lists(
            st.tuples(valid_video_filename(), valid_video_content()),
            min_size=1,
            max_size=10,
            unique_by=lambda x: x[0]  # Unique filenames
        )
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_listing_persists_across_restart(
        self,
        index,
        videos
    ):
        """Property 4: Video listing persists across system restart.
        
        **Validates: Requirements 1.5**
        
        For any index with videos, after adding videos and simulating a system
        restart, listing should still return all videos with complete metadata.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store1.save_index(index)
            
            # Create mock S3 client
            mock_s3 = Mock(spec=S3Client)
            
            def mock_upload(file_obj, key, content_type=None, metadata=None):
                return f"s3://test-bucket/{key}"
            
            mock_s3.upload = Mock(side_effect=mock_upload)
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            
            job_counter = [0]
            
            def mock_embedding(s3_uri, embedding_options):
                job_counter[0] += 1
                return f"arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/job-{job_counter[0]}"
            
            mock_bedrock.start_marengo_video_embedding = Mock(side_effect=mock_embedding)
            
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
            
            # Add all videos
            added_videos = []
            for filename, video_content in videos:
                video_file = io.BytesIO(video_content)
                video = await index_manager1.add_video_to_index(
                    index_id=index.id,
                    video_file=video_file,
                    filename=filename,
                    s3_client=mock_s3
                )
                added_videos.append(video)
            
            # Simulate system restart with new metadata store and index manager
            metadata_store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
            index_manager2 = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store2
            )
            
            # List videos after restart
            listed_videos = await index_manager2.list_videos_in_index(index.id)
            
            # Verify all videos are still present
            assert len(listed_videos) == len(videos), \
                f"After restart, expected {len(videos)} videos but got {len(listed_videos)}"
            
            # Verify video IDs match
            added_ids = {v.id for v in added_videos}
            listed_ids = {v.id for v in listed_videos}
            assert added_ids == listed_ids, \
                "Video IDs after restart do not match original IDs"
            
            # Verify all metadata is preserved
            listed_by_id = {v.id: v for v in listed_videos}
            for added_video in added_videos:
                listed_video = listed_by_id[added_video.id]
                assert listed_video.filename == added_video.filename
                assert listed_video.s3_uri == added_video.s3_uri
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_listing_empty_index_returns_empty_list(
        self,
        index
    ):
        """Property 4: Listing an empty index returns an empty list.
        
        **Validates: Requirements 1.5**
        
        For any index with no videos, listing should return an empty list.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Create mock clients
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            mock_bedrock = Mock(spec=BedrockClient)
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager
            index_manager = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store
            )
            
            # List videos in empty index
            listed_videos = await index_manager.list_videos_in_index(index.id)
            
            # Verify empty list is returned
            assert isinstance(listed_videos, list), \
                f"Expected list, got {type(listed_videos)}"
            assert len(listed_videos) == 0, \
                f"Expected empty list for empty index, got {len(listed_videos)} videos"
    
    @given(
        index=valid_index(),
        videos=st.lists(
            st.tuples(valid_video_filename(), valid_video_content()),
            min_size=2,
            max_size=5,  # Reduced from 10 to 5
            unique_by=lambda x: x[0]  # Unique filenames
        )
    )
    @settings(
        max_examples=100, 
        deadline=None, 
        suppress_health_check=[HealthCheck.large_base_example, HealthCheck.data_too_large]
    )
    @pytest.mark.asyncio
    async def test_property_listing_order_is_consistent(
        self,
        index,
        videos
    ):
        """Property 4: Listing returns videos in consistent order.
        
        **Validates: Requirements 1.5**
        
        For any index with videos, multiple calls to list_videos_in_index
        should return videos in the same order.
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
            
            job_counter = [0]
            
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
            for filename, video_content in videos:
                video_file = io.BytesIO(video_content)
                await index_manager.add_video_to_index(
                    index_id=index.id,
                    video_file=video_file,
                    filename=filename,
                    s3_client=mock_s3
                )
            
            # List videos multiple times
            listing1 = await index_manager.list_videos_in_index(index.id)
            listing2 = await index_manager.list_videos_in_index(index.id)
            listing3 = await index_manager.list_videos_in_index(index.id)
            
            # Verify all listings have the same order
            ids1 = [v.id for v in listing1]
            ids2 = [v.id for v in listing2]
            ids3 = [v.id for v in listing3]
            
            assert ids1 == ids2, "First and second listing have different order"
            assert ids2 == ids3, "Second and third listing have different order"
