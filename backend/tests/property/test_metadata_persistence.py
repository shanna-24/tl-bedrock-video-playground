"""Property-based tests for metadata persistence.

Feature: tl-video-playground
Property 1: Index Creation and Persistence Round-Trip

**Validates: Requirements 1.1, 1.6**

For any valid index name, creating an index then restarting the system should 
result in the index still existing with the same metadata and being retrievable 
from both the metadata store and S3 Vectors.
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

import pytest
from hypothesis import given, strategies as st, settings

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from storage.metadata_store import IndexMetadataStore
from models.index import Index


# Custom strategies for generating test data
@st.composite
def valid_index_name(draw):
    """Generate valid index names (alphanumeric, 3-50 chars)."""
    # Generate length between 3 and 50
    length = draw(st.integers(min_value=3, max_value=50))
    
    # Generate alphanumeric string with spaces and common punctuation
    chars = st.characters(
        whitelist_categories=('Lu', 'Ll', 'Nd'),  # Uppercase, lowercase, digits
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
    # Collection IDs are typically UUID-like or alphanumeric with hyphens
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Nd'), whitelist_characters='-'),
        min_size=5,
        max_size=100
    ))


@st.composite
def valid_metadata(draw):
    """Generate valid metadata dictionaries."""
    # Generate a dictionary with string keys and various value types
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


class TestMetadataPersistenceProperties:
    """Property-based tests for metadata persistence round-trip."""
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    def test_property_single_index_persistence_round_trip(self, index):
        """Property 1: Single index creation and persistence round-trip.
        
        **Validates: Requirements 1.1, 1.6**
        
        For any valid index, creating it and then loading it from a fresh store
        instance should preserve all index data exactly.
        """
        # Create temporary storage path for this test
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create first store instance and save index
            store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            store1.save_index(index)
            
            # Simulate system restart by creating new store instance
            store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
            loaded_indexes = store2.load_indexes()
        
            # Verify index was persisted
            assert len(loaded_indexes) == 1, "Expected exactly one index after persistence"
            
            loaded_index = loaded_indexes[0]
            
            # Verify all fields are preserved
            assert loaded_index.id == index.id, "Index ID not preserved"
            assert loaded_index.name == index.name, "Index name not preserved"
            assert loaded_index.video_count == index.video_count, "Video count not preserved"
            assert loaded_index.s3_vectors_collection_id == index.s3_vectors_collection_id, \
                "S3 Vectors collection ID not preserved"
            assert loaded_index.metadata == index.metadata, "Metadata not preserved"
            
            # Verify datetime is preserved (allow small difference due to serialization)
            time_diff = abs((loaded_index.created_at - index.created_at).total_seconds())
            assert time_diff < 1, f"Created timestamp differs by {time_diff} seconds"
    
    @given(indexes=st.lists(valid_index(), min_size=1, max_size=10, unique_by=lambda x: x.id))
    @settings(max_examples=100, deadline=None)
    def test_property_multiple_indexes_persistence_round_trip(self, indexes):
        """Property 1: Multiple indexes creation and persistence round-trip.
        
        **Validates: Requirements 1.1, 1.6**
        
        For any list of valid indexes, creating them all and then loading them
        from a fresh store instance should preserve all indexes with their data.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create first store instance and save all indexes
            store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            for index in indexes:
                store1.save_index(index)
            
            # Simulate system restart by creating new store instance
            store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
            loaded_indexes = store2.load_indexes()
            
            # Verify all indexes were persisted
            assert len(loaded_indexes) == len(indexes), \
                f"Expected {len(indexes)} indexes, got {len(loaded_indexes)}"
            
            # Create lookup dictionaries for comparison
            original_by_id = {idx.id: idx for idx in indexes}
            loaded_by_id = {idx.id: idx for idx in loaded_indexes}
            
            # Verify all original indexes are present
            assert set(original_by_id.keys()) == set(loaded_by_id.keys()), \
                "Index IDs don't match after persistence"
            
            # Verify each index's data is preserved
            for index_id, original in original_by_id.items():
                loaded = loaded_by_id[index_id]
                
                assert loaded.name == original.name, \
                    f"Name not preserved for index {index_id}"
                assert loaded.video_count == original.video_count, \
                    f"Video count not preserved for index {index_id}"
                assert loaded.s3_vectors_collection_id == original.s3_vectors_collection_id, \
                    f"Collection ID not preserved for index {index_id}"
                assert loaded.metadata == original.metadata, \
                    f"Metadata not preserved for index {index_id}"
                
                # Verify datetime is preserved
                time_diff = abs((loaded.created_at - original.created_at).total_seconds())
                assert time_diff < 1, \
                    f"Created timestamp differs by {time_diff} seconds for index {index_id}"
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    def test_property_index_retrieval_by_id(self, index):
        """Property 1: Index retrieval by ID after persistence.
        
        **Validates: Requirements 1.1, 1.6**
        
        For any valid index, after saving and restarting, retrieving by ID
        should return the exact same index data.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create first store instance and save index
            store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            store1.save_index(index)
            
            # Simulate system restart by creating new store instance
            store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
            loaded_index = store2.get_index(index.id)
            
            # Verify index was retrieved
            assert loaded_index is not None, "Index not found after persistence"
            
            # Verify all fields are preserved
            assert loaded_index.id == index.id
            assert loaded_index.name == index.name
            assert loaded_index.video_count == index.video_count
            assert loaded_index.s3_vectors_collection_id == index.s3_vectors_collection_id
            assert loaded_index.metadata == index.metadata
            
            # Verify datetime is preserved
            time_diff = abs((loaded_index.created_at - index.created_at).total_seconds())
            assert time_diff < 1
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    def test_property_index_update_persistence(self, index):
        """Property 1: Index updates are persisted correctly.
        
        **Validates: Requirements 1.1, 1.6**
        
        For any valid index, updating it and restarting should preserve
        the updated data, not the original data.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create store and save initial index
            store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            store1.save_index(index)
            
            # Create updated index with modified values
            # Ensure updated name stays within 50 char limit
            original_name = index.name
            if len(index.name) > 42:  # Leave room for "Updated "
                updated_name = f"Upd {index.name[:42]}"
            else:
                updated_name = f"Updated {index.name}"
            
            updated_index = index.model_copy(update={
                'name': updated_name,
                'video_count': index.video_count + 10,
                'metadata': {**index.metadata, 'updated': True}
            })
            
            # Save updated index
            store1.save_index(updated_index)
            
            # Simulate system restart
            store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
            loaded_index = store2.get_index(index.id)
            
            # Verify updated data is persisted, not original
            assert loaded_index is not None
            assert loaded_index.name == updated_name
            assert loaded_index.name != original_name
            assert loaded_index.video_count == updated_index.video_count
            assert loaded_index.metadata.get("updated") is True
    
    @given(
        indexes=st.lists(valid_index(), min_size=2, max_size=5, unique_by=lambda x: x.id)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_index_deletion_persistence(self, indexes):
        """Property 1: Index deletion is persisted correctly.
        
        **Validates: Requirements 1.1, 1.6**
        
        For any list of indexes, deleting some and restarting should result
        in only the non-deleted indexes being present.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Create store and save all indexes
            store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            for index in indexes:
                store1.save_index(index)
            
            # Delete the first index
            deleted_index = indexes[0]
            store1.delete_index(deleted_index.id)
            
            # Simulate system restart
            store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
            loaded_indexes = store2.load_indexes()
            
            # Verify correct number of indexes
            assert len(loaded_indexes) == len(indexes) - 1
            
            # Verify deleted index is not present
            loaded_ids = {idx.id for idx in loaded_indexes}
            assert deleted_index.id not in loaded_ids
            
            # Verify remaining indexes are present
            for index in indexes[1:]:
                assert index.id in loaded_ids
    
    @given(index=valid_index())
    @settings(max_examples=100, deadline=None)
    def test_property_empty_metadata_persistence(self, index):
        """Property 1: Empty metadata is persisted correctly.
        
        **Validates: Requirements 1.1, 1.6**
        
        For any valid index with empty metadata, persistence should preserve
        the empty dictionary (not None or missing).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # Set metadata to empty dict
            index.metadata = {}
            
            # Create store and save index
            store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            store1.save_index(index)
            
            # Simulate system restart
            store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
            loaded_index = store2.get_index(index.id)
            
            # Verify empty metadata is preserved as empty dict
            assert loaded_index is not None
            assert loaded_index.metadata == {}
            assert isinstance(loaded_index.metadata, dict)
    
    @given(
        indexes=st.lists(valid_index(), min_size=1, max_size=5, unique_by=lambda x: x.id)
    )
    @settings(max_examples=100, deadline=None)
    def test_property_multiple_restarts_preserve_data(self, indexes):
        """Property 1: Multiple system restarts preserve data.
        
        **Validates: Requirements 1.1, 1.6**
        
        For any list of indexes, multiple system restarts should continue
        to preserve all index data correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_storage_path = Path(tmpdir) / "test_indexes.json"
            
            # First store: save all indexes
            store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
            for index in indexes:
                store1.save_index(index)
            
            # Simulate multiple restarts
            for restart_num in range(3):
                store = IndexMetadataStore(storage_path=str(temp_storage_path))
                loaded_indexes = store.load_indexes()
                
                # Verify all indexes are still present
                assert len(loaded_indexes) == len(indexes), \
                    f"Data lost after restart {restart_num + 1}"
                
                loaded_ids = {idx.id for idx in loaded_indexes}
                original_ids = {idx.id for idx in indexes}
                assert loaded_ids == original_ids, \
                    f"Index IDs changed after restart {restart_num + 1}"
