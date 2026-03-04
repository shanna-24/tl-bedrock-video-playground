#!/usr/bin/env python3
"""
Test script for modality-filtered vector search.

This script demonstrates searching video embeddings with modality filtering:
1. Lists available indexes
2. Accepts a text search term
3. Generates a Marengo embedding for the search term
4. Allows specifying search modalities (visual, audio, transcription)
5. Performs vector search with metadata filtering
6. Returns top 5 matches with video name and timecodes
"""

import sys
from pathlib import Path

# Add backend/src to Python path
backend_src = Path(__file__).parent.parent / "backend" / "src"
sys.path.insert(0, str(backend_src))

from config import load_config
from aws.bedrock_client import BedrockClient
from aws.s3_vectors_client import S3VectorsClient
from storage.metadata_store import IndexMetadataStore


def list_s3_vector_indexes(s3_vectors: S3VectorsClient) -> list:
    """List all vector indexes from S3 Vectors bucket."""
    return s3_vectors.list_indexes()


def list_metadata_indexes(metadata_store: IndexMetadataStore) -> list:
    """List all indexes from local metadata store (for video names)."""
    return metadata_store.load_indexes()


def get_video_name_by_id(metadata_indexes: list, video_id: str) -> str:
    """Look up video filename by video_id across all metadata indexes."""
    for index in metadata_indexes:
        videos = index.metadata.get('videos', [])
        for video in videos:
            if video.get('id') == video_id:
                return video.get('filename', 'Unknown')
    return f"Unknown (ID: {video_id[:8]}...)"


def select_index(s3_indexes: list, metadata_indexes: list) -> tuple:
    """Interactive index selection. Returns (index_name, display_name)."""
    print("\n" + "=" * 60)
    print("AVAILABLE S3 VECTOR INDEXES")
    print("=" * 60)
    
    if not s3_indexes:
        print("No vector indexes found in S3 Vectors bucket.")
        print("Please create an index and upload videos first.")
        return None, None
    
    # Build a mapping from S3 index name to metadata for display
    metadata_map = {}
    for meta_idx in metadata_indexes:
        s3_name = f"index-{meta_idx.id}".lower()
        metadata_map[s3_name] = meta_idx
    
    for i, s3_idx in enumerate(s3_indexes, 1):
        index_name = s3_idx.get('indexName', 'Unknown')
        dimension = s3_idx.get('dimension', '?')
        
        # Try to get friendly name from metadata
        meta = metadata_map.get(index_name)
        if meta:
            display_name = meta.name
            video_count = len(meta.metadata.get('videos', []))
            print(f"  {i}. {display_name} ({video_count} videos)")
            print(f"     S3 Index: {index_name}, Dimensions: {dimension}")
        else:
            print(f"  {i}. {index_name}")
            print(f"     Dimensions: {dimension}")
    
    print()
    while True:
        try:
            choice = input("Select an index (number): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(s3_indexes):
                selected = s3_indexes[idx]
                index_name = selected.get('indexName')
                meta = metadata_map.get(index_name)
                display_name = meta.name if meta else index_name
                return index_name, display_name
            print(f"Please enter a number between 1 and {len(s3_indexes)}")
        except ValueError:
            print("Please enter a valid number")


def get_search_query() -> str:
    """Get search query from user."""
    print("\n" + "=" * 60)
    print("SEARCH QUERY")
    print("=" * 60)
    query = input("Enter your search term: ").strip()
    if not query:
        print("Search term cannot be empty")
        return None
    return query


def select_modalities() -> list:
    """Interactive modality selection. Returns list of selected modalities."""
    print("\n" + "=" * 60)
    print("SELECT SEARCH MODALITIES")
    print("=" * 60)
    print("  1. Visual (video frames, scenes, objects)")
    print("  2. Audio (sounds, music, audio events)")
    print("  3. Transcription (spoken words, dialogue)")
    print("  4. All modalities (default)")
    print()
    print("Enter numbers separated by commas (e.g., '1,3' for visual+transcription)")
    print("Or press Enter for all modalities")
    
    choice = input("Your selection: ").strip()
    
    modality_map = {
        '1': 'visual',
        '2': 'audio',
        '3': 'transcription'
    }
    
    if not choice or choice == '4':
        return ['visual', 'audio', 'transcription']
    
    selected = []
    for c in choice.split(','):
        c = c.strip()
        if c in modality_map:
            selected.append(modality_map[c])
    
    if not selected:
        print("Invalid selection, using all modalities")
        return ['visual', 'audio', 'transcription']
    
    return selected


def build_modality_filter(modalities: list) -> dict:
    """
    Build S3 Vectors metadata filter for modality filtering.
    
    The embedding_option is stored as a single modality string like "visual", "audio", 
    or "transcription".
    
    Also filter to only include clip-level embeddings (exclude asset/full-video embeddings).
    
    S3 Vectors filter syntax supports: $eq, $ne, $in, $nin, $and, $or, etc.
    """
    # Filter to clips only (exclude full video embeddings)
    scope_filter = {"embedding_scope": {"$eq": "clip"}}
    
    if set(modalities) == {'visual', 'audio', 'transcription'}:
        # Only scope filter needed if all modalities selected
        return scope_filter
    
    # Use $in to match any of the selected modalities
    modality_filter = {"embedding_option": {"$in": modalities}}
    
    # Combine scope and modality filters with AND
    return {"$and": [scope_filter, modality_filter]}


def perform_search(
    s3_vectors: S3VectorsClient,
    bedrock: BedrockClient,
    index_name: str,
    query: str,
    modalities: list,
    top_k: int = 5
) -> list:
    """
    Perform modality-filtered vector search.
    
    1. Generate embedding for query text using Marengo
    2. Build metadata filter for selected modalities
    3. Query S3 Vectors with filter
    4. Return results
    """
    print("\n" + "-" * 60)
    print("Generating query embedding...")
    
    # Generate embedding for search query
    query_embedding = bedrock.invoke_marengo_text_embedding(query)
    print(f"✓ Generated embedding with {len(query_embedding)} dimensions")
    
    # Build modality filter (always includes clip-only filter)
    metadata_filter = build_modality_filter(modalities)
    
    modality_desc = ', '.join(modalities)
    if set(modalities) == {'visual', 'audio', 'transcription'}:
        print(f"✓ Searching all modalities (clips only)")
    else:
        print(f"✓ Filtering to modalities: {modality_desc} (clips only)")
    
    print(f"Searching index '{index_name}'...")
    
    # Perform vector search
    results = s3_vectors.query_vectors(
        index_name=index_name,
        query_vector=query_embedding,
        top_k=top_k,
        metadata_filter=metadata_filter,
        return_distance=True,
        return_metadata=True
    )
    
    print(f"✓ Found {len(results)} results")
    
    return results


def display_results(results: list, metadata_indexes: list):
    """Display search results with video names and timecodes."""
    print("\n" + "=" * 60)
    print("SEARCH RESULTS")
    print("=" * 60)
    
    if not results:
        print("No results found.")
        return
    
    display_count = 0
    for result in results:
        metadata = result.get('metadata', {})
        
        # Skip full video embeddings (asset scope) - only show clips
        embedding_scope = metadata.get('embedding_scope', 'clip')
        if isinstance(embedding_scope, list):
            embedding_scope = ''.join(embedding_scope)
        if embedding_scope == 'asset':
            continue
        
        display_count += 1
        if display_count > 5:
            break
        
        video_id = metadata.get('video_id', 'Unknown')
        if isinstance(video_id, list):
            video_id = ''.join(video_id)
        video_name = get_video_name_by_id(metadata_indexes, video_id)
        
        start_time = metadata.get('start_timecode', 0)
        end_time = metadata.get('end_timecode', 0)
        
        # Handle string timecodes (legacy data)
        try:
            start_time = float(start_time)
            end_time = float(end_time)
        except (ValueError, TypeError):
            start_time = 0
            end_time = 0
        
        # Handle embedding_option - fix any corrupted data
        embedding_option = metadata.get('embedding_option', 'unknown')
        if isinstance(embedding_option, str) and len(embedding_option) > 20:
            # Likely corrupted - remove all commas to reconstruct
            embedding_option = embedding_option.replace(',', '')
        
        distance = result.get('distance', 0)
        similarity = max(0, min(1, 1 - distance))  # Convert distance to similarity
        
        print(f"\n  {display_count}. {video_name}")
        print(f"     Timecode: {start_time:.1f}s - {end_time:.1f}s")
        print(f"     Modality: {embedding_option}")
        print(f"     Similarity: {similarity:.2%}")


def main():
    print("=" * 60)
    print("MODALITY-FILTERED VIDEO SEARCH TEST")
    print("=" * 60)
    
    # Load configuration
    try:
        config = load_config("config.local.yaml")
        print(f"✓ Config loaded: region={config.aws_region}, bucket={config.s3_bucket_name}")
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        return 1
    
    # Initialize clients
    try:
        bedrock = BedrockClient(config)
        s3_vectors = S3VectorsClient(config)
        metadata_store = IndexMetadataStore(storage_path="backend/data/indexes.json")
        print("✓ Clients initialized")
    except Exception as e:
        print(f"✗ Failed to initialize clients: {e}")
        return 1
    
    # Step 1: List indexes from S3 Vectors and metadata store
    try:
        s3_indexes = list_s3_vector_indexes(s3_vectors)
        metadata_indexes = list_metadata_indexes(metadata_store)
        print(f"✓ Found {len(s3_indexes)} S3 Vector indexes")
    except Exception as e:
        print(f"✗ Failed to list indexes: {e}")
        return 1
    
    # Select index
    index_name, display_name = select_index(s3_indexes, metadata_indexes)
    if not index_name:
        return 1
    
    print(f"\n✓ Selected: {display_name} ({index_name})")
    
    # Step 2: Get search query
    query = get_search_query()
    if not query:
        return 1
    
    # Step 3: Select modalities
    modalities = select_modalities()
    print(f"\n✓ Selected modalities: {', '.join(modalities)}")
    
    # Step 4: Perform search
    try:
        results = perform_search(
            s3_vectors=s3_vectors,
            bedrock=bedrock,
            index_name=index_name,
            query=query,
            modalities=modalities,
            top_k=5
        )
    except Exception as e:
        print(f"\n✗ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Step 5: Display results
    display_results(results, metadata_indexes)
    
    print("\n" + "=" * 60)
    print("Search complete!")
    print("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
