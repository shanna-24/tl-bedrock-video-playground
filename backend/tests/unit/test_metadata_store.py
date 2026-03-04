"""Unit tests for IndexMetadataStore.

Tests metadata persistence, CRUD operations, and file handling.
Validates: Requirements 1.6
"""

import os
import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime

import pytest

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from storage.metadata_store import IndexMetadataStore
from models.index import Index


class TestIndexMetadataStore:
    """Test suite for IndexMetadataStore class."""
    
    @pytest.fixture
    def temp_storage_path(self):
        """Create a temporary storage path for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_indexes.json"
    
    @pytest.fixture
    def store(self, temp_storage_path):
        """Create an IndexMetadataStore instance with temporary storage."""
        return IndexMetadataStore(storage_path=str(temp_storage_path))
    
    @pytest.fixture
    def sample_index(self):
        """Create a sample index for testing."""
        return Index.create(
            name="Test Index",
            s3_vectors_collection_id="test-collection-123"
        )
    
    def test_initialization_creates_directory(self, temp_storage_path):
        """Test that initialization creates the storage directory."""
        # Ensure parent directory doesn't exist
        if temp_storage_path.parent.exists():
            import shutil
            shutil.rmtree(temp_storage_path.parent)
        
        store = IndexMetadataStore(storage_path=str(temp_storage_path))
        
        assert temp_storage_path.parent.exists()
        assert temp_storage_path.exists()
    
    def test_initialization_creates_empty_file(self, temp_storage_path):
        """Test that initialization creates an empty JSON file."""
        store = IndexMetadataStore(storage_path=str(temp_storage_path))
        
        with open(temp_storage_path, 'r') as f:
            data = json.load(f)
        
        assert data == []
    
    def test_save_index_new(self, store, sample_index):
        """Test saving a new index."""
        store.save_index(sample_index)
        
        # Verify the index was saved
        loaded_indexes = store.load_indexes()
        assert len(loaded_indexes) == 1
        assert loaded_indexes[0].id == sample_index.id
        assert loaded_indexes[0].name == sample_index.name
        assert loaded_indexes[0].s3_vectors_collection_id == sample_index.s3_vectors_collection_id
    
    def test_save_index_update_existing(self, store, sample_index):
        """Test updating an existing index."""
        # Save initial index
        store.save_index(sample_index)
        
        # Update the index
        sample_index.name = "Updated Name"
        sample_index.video_count = 5
        store.save_index(sample_index)
        
        # Verify only one index exists with updated data
        loaded_indexes = store.load_indexes()
        assert len(loaded_indexes) == 1
        assert loaded_indexes[0].id == sample_index.id
        assert loaded_indexes[0].name == "Updated Name"
        assert loaded_indexes[0].video_count == 5
    
    def test_save_multiple_indexes(self, store):
        """Test saving multiple indexes."""
        index1 = Index.create("Index 1", "collection-1")
        index2 = Index.create("Index 2", "collection-2")
        index3 = Index.create("Index 3", "collection-3")
        
        store.save_index(index1)
        store.save_index(index2)
        store.save_index(index3)
        
        loaded_indexes = store.load_indexes()
        assert len(loaded_indexes) == 3
        
        # Verify all indexes are present
        loaded_ids = {idx.id for idx in loaded_indexes}
        assert index1.id in loaded_ids
        assert index2.id in loaded_ids
        assert index3.id in loaded_ids
    
    def test_load_indexes_empty(self, store):
        """Test loading indexes when store is empty."""
        indexes = store.load_indexes()
        assert indexes == []
    
    def test_load_indexes_preserves_datetime(self, store, sample_index):
        """Test that datetime is preserved during save/load cycle."""
        original_time = sample_index.created_at
        store.save_index(sample_index)
        
        loaded_indexes = store.load_indexes()
        loaded_time = loaded_indexes[0].created_at
        
        # Compare timestamps (allow small difference due to serialization)
        assert abs((loaded_time - original_time).total_seconds()) < 1
    
    def test_load_indexes_preserves_metadata(self, store, sample_index):
        """Test that metadata dictionary is preserved."""
        sample_index.metadata = {
            "key1": "value1",
            "key2": 123,
            "key3": {"nested": "data"}
        }
        store.save_index(sample_index)
        
        loaded_indexes = store.load_indexes()
        assert loaded_indexes[0].metadata == sample_index.metadata
    
    def test_delete_index(self, store, sample_index):
        """Test deleting an index."""
        store.save_index(sample_index)
        
        # Verify index exists
        assert len(store.load_indexes()) == 1
        
        # Delete the index
        store.delete_index(sample_index.id)
        
        # Verify index is gone
        assert len(store.load_indexes()) == 0
    
    def test_delete_index_nonexistent(self, store):
        """Test deleting a non-existent index doesn't raise error."""
        # Should not raise any exception
        store.delete_index("nonexistent-id")
        assert len(store.load_indexes()) == 0
    
    def test_delete_index_from_multiple(self, store):
        """Test deleting one index from multiple."""
        index1 = Index.create("Index 1", "collection-1")
        index2 = Index.create("Index 2", "collection-2")
        index3 = Index.create("Index 3", "collection-3")
        
        store.save_index(index1)
        store.save_index(index2)
        store.save_index(index3)
        
        # Delete middle index
        store.delete_index(index2.id)
        
        loaded_indexes = store.load_indexes()
        assert len(loaded_indexes) == 2
        
        loaded_ids = {idx.id for idx in loaded_indexes}
        assert index1.id in loaded_ids
        assert index2.id not in loaded_ids
        assert index3.id in loaded_ids
    
    def test_get_index_existing(self, store, sample_index):
        """Test retrieving an existing index by ID."""
        store.save_index(sample_index)
        
        retrieved = store.get_index(sample_index.id)
        
        assert retrieved is not None
        assert retrieved.id == sample_index.id
        assert retrieved.name == sample_index.name
    
    def test_get_index_nonexistent(self, store):
        """Test retrieving a non-existent index returns None."""
        retrieved = store.get_index("nonexistent-id")
        assert retrieved is None
    
    def test_get_index_from_multiple(self, store):
        """Test retrieving specific index from multiple."""
        index1 = Index.create("Index 1", "collection-1")
        index2 = Index.create("Index 2", "collection-2")
        index3 = Index.create("Index 3", "collection-3")
        
        store.save_index(index1)
        store.save_index(index2)
        store.save_index(index3)
        
        retrieved = store.get_index(index2.id)
        
        assert retrieved is not None
        assert retrieved.id == index2.id
        assert retrieved.name == "Index 2"
    
    def test_corrupted_json_file(self, temp_storage_path):
        """Test that corrupted JSON file is handled gracefully."""
        # Create corrupted JSON file
        temp_storage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_storage_path, 'w') as f:
            f.write("{ invalid json [")
        
        store = IndexMetadataStore(storage_path=str(temp_storage_path))
        
        # Should return empty list instead of crashing
        indexes = store.load_indexes()
        assert indexes == []
    
    def test_persistence_across_instances(self, temp_storage_path, sample_index):
        """Test that data persists across different store instances."""
        # Save with first instance
        store1 = IndexMetadataStore(storage_path=str(temp_storage_path))
        store1.save_index(sample_index)
        
        # Load with second instance
        store2 = IndexMetadataStore(storage_path=str(temp_storage_path))
        loaded_indexes = store2.load_indexes()
        
        assert len(loaded_indexes) == 1
        assert loaded_indexes[0].id == sample_index.id
    
    def test_save_index_with_all_fields(self, store):
        """Test saving an index with all fields populated."""
        index = Index(
            id="test-id-123",
            name="Full Index",
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            video_count=10,
            s3_vectors_collection_id="collection-xyz",
            metadata={"custom": "data", "count": 42}
        )
        
        store.save_index(index)
        loaded = store.get_index("test-id-123")
        
        assert loaded is not None
        assert loaded.id == "test-id-123"
        assert loaded.name == "Full Index"
        assert loaded.video_count == 10
        assert loaded.s3_vectors_collection_id == "collection-xyz"
        assert loaded.metadata == {"custom": "data", "count": 42}
    
    def test_empty_metadata_dict(self, store):
        """Test that empty metadata dictionary is handled correctly."""
        index = Index.create("Test", "collection")
        index.metadata = {}
        
        store.save_index(index)
        loaded = store.get_index(index.id)
        
        assert loaded.metadata == {}
    
    def test_special_characters_in_name(self, store):
        """Test that valid special characters in index name are preserved."""
        index = Index.create("Test Index-Name_123", "collection")
        
        store.save_index(index)
        loaded = store.get_index(index.id)
        
        assert loaded.name == "Test Index-Name_123"
