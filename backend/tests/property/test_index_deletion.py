"""Property-based tests for index deletion.

Feature: tl-video-playground
Property 2: Index Deletion Removes All Data

**Validates: Requirements 1.3**

For any existing index, deleting the index should result in the index no longer 
appearing in the index list, and all associated embeddings should be removed 
from S3 Vectors.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from hypothesis import given, strategies as st, settings, assume

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from storage.metadata_store import IndexMetadataStore
from models.index import Index
from services.index_manager import IndexManager
from aws.s3_vectors_client import S3VectorsClient
from aws.bedrock_client import BedrockClient
from config import Config
from exceptions import ResourceNotFoundError


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
    # Ensure we generate at least 5 characters to meet minimum requirements
    length = draw(st.integers(min_value=5, max_value=100))
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'),
        min_size=length,
        max_size=length
    ))


@st.composite
def valid_metadata(draw):
    """Generate valid metadata dictionaries."""
    return draw(st.dictionaries(
        keys=st.text(min_size=1, max_size=50),
        values=st.one_of(
            st.text(max_size=200),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
            st.booleans(),
            st.none(),
            st.dictionaries(
                keys=st.text(min_size=1, max_size=20),
                values=st.one_of(st.text(max_size=100), st.integers()),
                max_size=5
            )
        ),
        max_size=10
    ))


@st.composite
def valid_index(draw):
    """Generate a valid Index instance."""
    name = draw(valid_index_name())
    collection_id = draw(valid_collection_id())
    video_count = draw(st.integers(min_value=0, max_value=1000))
    metadata = draw(valid_metadata())
    
    index = Index.create(name=name, s3_vectors_collection_id=collection_id)
    index.video_count = video_count
    index.metadata = metadata
    
    return index


class TestIndexDeletionProperties:
    """Property-based tests for index deletion."""
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_index_deletion_removes_from_metadata(self, index):
        """Property 2: Index deletion removes index from metadata store.
        
        **Validates: Requirements 1.3**
        
        For any valid index, after deletion, the index should no longer appear
        in the metadata store's index list or be retrievable by ID.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Verify index exists before deletion
            loaded_index = metadata_store.get_index(index.id)
            assert loaded_index is not None, "Index should exist before deletion"
            
            all_indexes = metadata_store.load_indexes()
            assert len(all_indexes) == 1, "Should have one index before deletion"
            assert all_indexes[0].id == index.id
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            mock_s3_vectors.delete_index = Mock(return_value=True)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            
            # Create mock config
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager with mocked dependencies
            index_manager = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store
            )
            
            # Delete the index
            result = await index_manager.delete_index(index.id)
            assert result is True, "Deletion should return True"
            
            # Verify index no longer exists in metadata store
            deleted_index = metadata_store.get_index(index.id)
            assert deleted_index is None, "Index should not exist after deletion"
            
            # Verify index list is empty
            remaining_indexes = metadata_store.load_indexes()
            assert len(remaining_indexes) == 0, "Index list should be empty after deletion"
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_index_deletion_removes_from_s3_vectors(self, index):
        """Property 2: Index deletion removes index from S3 Vectors.
        
        **Validates: Requirements 1.3**
        
        For any valid index, after deletion, the S3 Vectors delete_index method
        should be called with the correct collection ID.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            mock_s3_vectors.delete_index = Mock(return_value=True)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            
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
            
            # Delete the index
            await index_manager.delete_index(index.id)
            
            # Verify S3 Vectors delete_index was called with correct collection ID
            mock_s3_vectors.delete_index.assert_called_once_with(
                index.s3_vectors_collection_id
            )
    
    @given(
        indexes=st.lists(valid_index(), min_size=2, max_size=5, unique_by=lambda x: x.id)
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_index_deletion_preserves_other_indexes(self, indexes):
        """Property 2: Deleting one index preserves other indexes.
        
        **Validates: Requirements 1.3**
        
        For any list of indexes, deleting one should only remove that specific
        index while preserving all other indexes in both metadata and S3 Vectors.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save all indexes
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            for idx in indexes:
                metadata_store.save_index(idx)
            
            # Verify all indexes exist
            all_indexes = metadata_store.load_indexes()
            assert len(all_indexes) == len(indexes)
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            mock_s3_vectors.delete_index = Mock(return_value=True)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            
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
            
            # Delete the first index
            index_to_delete = indexes[0]
            await index_manager.delete_index(index_to_delete.id)
            
            # Verify deleted index is gone
            deleted_index = metadata_store.get_index(index_to_delete.id)
            assert deleted_index is None
            
            # Verify other indexes still exist
            remaining_indexes = metadata_store.load_indexes()
            assert len(remaining_indexes) == len(indexes) - 1
            
            remaining_ids = {idx.id for idx in remaining_indexes}
            expected_ids = {idx.id for idx in indexes[1:]}
            assert remaining_ids == expected_ids
            
            # Verify each remaining index has preserved data
            for original_index in indexes[1:]:
                loaded = metadata_store.get_index(original_index.id)
                assert loaded is not None
                assert loaded.name == original_index.name
                assert loaded.video_count == original_index.video_count
                assert loaded.s3_vectors_collection_id == original_index.s3_vectors_collection_id
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_index_deletion_is_idempotent_in_metadata(self, index):
        """Property 2: Deleting a non-existent index raises ResourceNotFoundError.
        
        **Validates: Requirements 1.3**
        
        For any index ID, attempting to delete an index that doesn't exist
        should raise ResourceNotFoundError without affecting other data.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store (empty)
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            
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
            
            # Attempt to delete non-existent index
            with pytest.raises(ResourceNotFoundError):
                await index_manager.delete_index(index.id)
            
            # Verify S3 Vectors delete was not called
            mock_s3_vectors.delete_index.assert_not_called()
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_index_deletion_persists_across_restart(self, index):
        """Property 2: Index deletion persists across system restart.
        
        **Validates: Requirements 1.3**
        
        For any valid index, after deletion and system restart (new metadata
        store instance), the index should remain deleted.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store1.save_index(index)
            
            # Verify index exists
            assert metadata_store1.get_index(index.id) is not None
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            mock_s3_vectors.delete_index = Mock(return_value=True)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            
            # Create mock config
            mock_config = Mock(spec=Config)
            mock_config.max_indexes = 3
            
            # Create IndexManager and delete index
            index_manager = IndexManager(
                bedrock_client=mock_bedrock,
                s3_vectors_client=mock_s3_vectors,
                config=mock_config,
                metadata_store=metadata_store1
            )
            
            await index_manager.delete_index(index.id)
            
            # Simulate system restart with new metadata store instance
            metadata_store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
            
            # Verify index is still deleted
            deleted_index = metadata_store2.get_index(index.id)
            assert deleted_index is None
            
            all_indexes = metadata_store2.load_indexes()
            assert len(all_indexes) == 0
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_index_deletion_handles_s3_vectors_failure(self, index):
        """Property 2: Index deletion continues even if S3 Vectors deletion fails.
        
        **Validates: Requirements 1.3**
        
        For any valid index, if S3 Vectors deletion fails, the metadata should
        still be removed to prevent orphaned metadata.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save index
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            metadata_store.save_index(index)
            
            # Create mock S3 Vectors client that raises an exception
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            mock_s3_vectors.delete_index = Mock(
                side_effect=Exception("S3 Vectors deletion failed")
            )
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            
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
            
            # Delete the index (should succeed despite S3 Vectors failure)
            result = await index_manager.delete_index(index.id)
            assert result is True
            
            # Verify metadata was still removed
            deleted_index = metadata_store.get_index(index.id)
            assert deleted_index is None
            
            # Verify S3 Vectors delete was attempted
            mock_s3_vectors.delete_index.assert_called_once()
    
    @given(
        indexes=st.lists(valid_index(), min_size=1, max_size=3, unique_by=lambda x: x.id)
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_property_multiple_deletions_in_sequence(self, indexes):
        """Property 2: Multiple sequential deletions work correctly.
        
        **Validates: Requirements 1.3**
        
        For any list of indexes, deleting them one by one should result in
        all indexes being removed from both metadata and S3 Vectors.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create metadata store and save all indexes
            metadata_store = IndexMetadataStore(storage_path=str(temp_storage_path))
            for idx in indexes:
                metadata_store.save_index(idx)
            
            # Create mock S3 Vectors client
            mock_s3_vectors = Mock(spec=S3VectorsClient)
            mock_s3_vectors.delete_index = Mock(return_value=True)
            
            # Create mock Bedrock client
            mock_bedrock = Mock(spec=BedrockClient)
            
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
            
            # Delete all indexes one by one
            for idx in indexes:
                await index_manager.delete_index(idx.id)
            
            # Verify all indexes are deleted from metadata
            remaining_indexes = metadata_store.load_indexes()
            assert len(remaining_indexes) == 0
            
            # Verify each index is not retrievable
            for idx in indexes:
                assert metadata_store.get_index(idx.id) is None
            
            # Verify S3 Vectors delete was called for each index
            assert mock_s3_vectors.delete_index.call_count == len(indexes)
            
            # Verify correct collection IDs were used
            called_collection_ids = [
                call[0][0] for call in mock_s3_vectors.delete_index.call_args_list
            ]
            expected_collection_ids = [idx.s3_vectors_collection_id for idx in indexes]
            assert set(called_collection_ids) == set(expected_collection_ids)
