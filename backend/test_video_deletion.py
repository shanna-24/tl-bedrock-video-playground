#!/usr/bin/env python3
"""Quick test script to verify video deletion functionality."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from services.embedding_job_store import EmbeddingJobStore
from aws.s3_vectors_client import S3VectorsClient
from config import Config


def test_embedding_job_store_delete():
    """Test the new delete_job method."""
    print("Testing EmbeddingJobStore.delete_job()...")
    
    # Create a temporary store
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        store_path = f.name
    
    try:
        store = EmbeddingJobStore(store_path=store_path, enable_cache=False)
        
        # Add a job
        job_id = store.add_job(
            invocation_arn="arn:aws:bedrock:us-east-1:123456789012:invocation/test",
            video_id="test-video-123",
            index_id="test-index-456",
            s3_uri="s3://bucket/video.mp4",
            video_duration=60.0
        )
        
        print(f"  ✓ Created job: {job_id}")
        
        # Verify job exists
        job = store.get_job(job_id)
        assert job is not None, "Job should exist"
        print(f"  ✓ Job exists in store")
        
        # Delete the job
        result = store.delete_job(job_id)
        assert result is True, "Delete should return True"
        print(f"  ✓ Job deleted successfully")
        
        # Verify job is gone
        job = store.get_job(job_id)
        assert job is None, "Job should not exist after deletion"
        print(f"  ✓ Job no longer exists in store")
        
        # Try deleting non-existent job
        result = store.delete_job("non-existent-job")
        assert result is False, "Delete should return False for non-existent job"
        print(f"  ✓ Delete returns False for non-existent job")
        
        print("✅ EmbeddingJobStore.delete_job() tests passed!\n")
        
    finally:
        # Cleanup
        if os.path.exists(store_path):
            os.remove(store_path)


def test_s3_vectors_delete_by_video_id():
    """Test the new delete_by_video_id method."""
    print("Testing S3VectorsClient.delete_by_video_id()...")
    
    # Create a mock config for LocalStack
    config = Config(
        marengo_model_id="test-model",
        pegasus_model_id="test-model",
        aws_region="us-east-1",
        s3_bucket_name="test-bucket",
        s3_vectors_collection="test-collection",
        auth_password_hash="test-hash",
        use_localstack=True
    )
    
    client = S3VectorsClient(config)
    
    # Create a test index
    index_name = "test-index"
    client.create_index(index_name=index_name, dimension=512)
    print(f"  ✓ Created test index: {index_name}")
    
    # Add some test vectors
    video_id = "test-video-123"
    vectors = [
        {
            "key": f"{video_id}:0:10:0",
            "data": {"float32": [0.1] * 512},
            "metadata": {"video_id": video_id}
        },
        {
            "key": f"{video_id}:10:20:1",
            "data": {"float32": [0.2] * 512},
            "metadata": {"video_id": video_id}
        },
        {
            "key": "other-video:0:10:0",
            "data": {"float32": [0.3] * 512},
            "metadata": {"video_id": "other-video"}
        }
    ]
    
    client.put_vectors(index_name=index_name, vectors=vectors)
    print(f"  ✓ Added 3 test vectors (2 for {video_id}, 1 for other-video)")
    
    # Delete vectors for specific video
    deleted_count = client.delete_by_video_id(
        index_name=index_name,
        video_id=video_id
    )
    
    assert deleted_count == 2, f"Should delete 2 vectors, deleted {deleted_count}"
    print(f"  ✓ Deleted {deleted_count} vectors for {video_id}")
    
    # Verify only the other video's vector remains
    remaining = client._mock_vectors.get(index_name, [])
    assert len(remaining) == 1, f"Should have 1 vector remaining, found {len(remaining)}"
    assert remaining[0]["key"] == "other-video:0:10:0", "Wrong vector remaining"
    print(f"  ✓ Other video's vectors remain intact")
    
    print("✅ S3VectorsClient.delete_by_video_id() tests passed!\n")


if __name__ == "__main__":
    print("=" * 60)
    print("Video Deletion Functionality Tests")
    print("=" * 60 + "\n")
    
    try:
        test_embedding_job_store_delete()
        test_s3_vectors_delete_by_video_id()
        
        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
