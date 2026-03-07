"""Search service for natural language video search.

This module provides the SearchService class for performing natural language
searches across video indexes using TwelveLabs Marengo model embeddings.

Validates: Requirements 3.1, 3.2, 3.3
"""

import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union
from io import BytesIO

from aws.bedrock_client import BedrockClient
from aws.s3_vectors_client import S3VectorsClient
from aws.s3_client import S3Client
from config import Config
from models.search import SearchResults, VideoClip
from exceptions import AWSServiceError, BedrockError
from services.pegasus_transcription_service import PegasusTranscriptionService
from utils.ffmpeg import get_ffmpeg_path

if TYPE_CHECKING:
    from services.index_manager import IndexManager

logger = logging.getLogger(__name__)


class SearchService:
    """Handles natural language video search.
    
    This service uses the Marengo model to embed search queries and performs
    similarity search against video embeddings stored in S3 Vectors. It also
    generates screenshots for video clips and presigned URLs for streaming.
    
    Attributes:
        bedrock: BedrockClient for query embedding
        s3_vectors: S3VectorsClient for similarity search
        s3: S3Client for presigned URLs and screenshots
        config: Configuration object
    """
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        s3_vectors_client: S3VectorsClient,
        s3_client: S3Client,
        config: Config,
        index_manager: Optional["IndexManager"] = None
    ):
        """Initialize the SearchService.
        
        Args:
            bedrock_client: Client for Bedrock API (Marengo model)
            s3_vectors_client: Client for S3 Vectors API
            s3_client: Client for S3 API
            config: Configuration object
            index_manager: Optional IndexManager for lexical search (lazy-loaded if not provided)
        """
        self.bedrock = bedrock_client
        self.s3_vectors = s3_vectors_client
        self.s3 = s3_client
        self.config = config
        self._index_manager = index_manager
        self.transcription_service = PegasusTranscriptionService(config, bedrock_client)
        
        logger.info("Initialized SearchService")
    
    def _get_index_manager(self) -> "IndexManager":
        """Get the index manager instance.
        
        Returns:
            IndexManager instance
            
        Raises:
            RuntimeError: If index_manager was not provided during initialization
        """
        if self._index_manager is None:
            raise RuntimeError("IndexManager not provided to SearchService. Pass index_manager during initialization.")
        return self._index_manager
    
    async def search_videos(
        self,
        index_id: str,
        query: Optional[Union[str, List[str]]] = None,
        image_bytes: Optional[bytes] = None,
        top_k: int = 10,
        modalities: Optional[List[str]] = None,
        transcription_mode: str = "both",
        video_id: Optional[str] = None,
        generate_screenshots: bool = True
    ) -> SearchResults:
        """Search for videos using text, image, or both.
        
        This method:
        1. Embeds the query using Marengo model (text, image, or multimodal)
        2. Performs similarity search in S3 Vectors with optional modality filtering
        3. Optionally performs lexical search on transcription text
        4. Generates screenshots for matching clips (optional)
        5. Generates presigned URLs for video streaming
        
        Args:
            index_id: ID of the index to search
            query: Optional natural language search query. Can be:
                   - A single string: "term"
                   - A list of alternative terms: ["term1", "term2", "term3"]
                   For lexical search, multiple terms use OR logic (any match counts)
            image_bytes: Optional image bytes for visual search
            top_k: Number of results to return (default: 10)
            modalities: Optional list of modalities to search (visual, audio, transcription).
                       Defaults to all modalities if not specified.
            transcription_mode: How to search transcriptions when transcription modality is selected.
                              "semantic" = embedding-based only, "lexical" = exact text match only,
                              "both" = combine both approaches (default).
            video_id: Optional video ID to limit search to a single video.
            generate_screenshots: Whether to generate screenshots (default: True)
        
        Returns:
            SearchResults object containing matching video clips
        
        Raises:
            BedrockError: If query embedding fails
            AWSServiceError: If similarity search or URL generation fails
            ValueError: If neither query nor image is provided
            
        Validates: Requirements 2.1, 2.3, 3.1, 3.2, 3.3, 5.3, 5.4, 5.5, 5.6
        """
        if not query and not image_bytes:
            raise ValueError("At least one of query or image must be provided")
        
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        
        # Normalize query for logging and semantic search
        # For semantic search, if query is a list, join with OR
        query_for_semantic = None
        if query:
            if isinstance(query, list):
                query_for_semantic = " OR ".join(query)
                query_display = f"{query[0][:50]}... ({len(query)} terms)"
            else:
                query_for_semantic = query
                query_display = query[:50]
        
        # Determine search mode for logging
        if query and image_bytes:
            search_mode = "multimodal"
        elif image_bytes:
            search_mode = "image-only"
        else:
            search_mode = "text-only"
        
        # Log modality filter
        modality_desc = ", ".join(modalities) if modalities else "all"
        logger.info(f"Performing {search_mode} search on index {index_id} (modalities: {modality_desc}, transcription_mode: {transcription_mode})")
        if query:
            logger.info(f"Query: {query_display}...")
        
        start_time = time.time()
        
        try:
            # Determine if transcription search is requested
            search_transcription = modalities is None or 'transcription' in modalities
            logger.info(f"search_transcription={search_transcription}, modalities={modalities}")
            
            # Determine which search methods to use
            do_semantic_search = True
            do_lexical_search = False
            
            if search_transcription and query:
                if transcription_mode == "lexical":
                    # Lexical only - exclude transcription from semantic search
                    do_lexical_search = True
                    # If only transcription modality is requested, skip semantic search entirely
                    if modalities == ["transcription"]:
                        do_semantic_search = False
                elif transcription_mode == "both":
                    # Both semantic and lexical
                    do_lexical_search = True
                # For "semantic", just use the default semantic search
            
            logger.info(f"do_semantic_search={do_semantic_search}, do_lexical_search={do_lexical_search}")
            
            all_results = []
            
            # Step 1: Semantic search (embedding-based)
            if do_semantic_search:
                # For lexical-only mode, exclude transcription from semantic modalities
                semantic_modalities = modalities
                if transcription_mode == "lexical" and search_transcription:
                    if modalities:
                        semantic_modalities = [m for m in modalities if m != 'transcription']
                    else:
                        semantic_modalities = ['visual', 'audio']
                
                # Only do semantic search if there are modalities to search or we have an image
                if semantic_modalities or image_bytes:
                    # Embed the query using Marengo (text, image, or multimodal)
                    query_embedding = await self._embed_query_multimodal(query_for_semantic, image_bytes)
                    
                    # Request more results than needed to account for filtering
                    search_top_k = top_k * 3
                    semantic_results = await self._similarity_search(
                        query_embedding=query_embedding,
                        index_id=index_id,
                        top_k=search_top_k,
                        modalities=semantic_modalities if semantic_modalities else None,
                        video_id=video_id
                    )
                    
                    # Mark results as semantic
                    for result in semantic_results:
                        result['match_type'] = 'semantic'
                    all_results.extend(semantic_results)
            
            # Step 2: Lexical transcription search (exact text match)
            if do_lexical_search and query:
                lexical_results = await self._lexical_transcription_search(
                    query=query,
                    index_id=index_id,
                    top_k=top_k * 2,  # Get extra for merging
                    video_id=video_id
                )
                all_results.extend(lexical_results)
            
            # Step 3: Merge and deduplicate results
            merged_results = self._merge_search_results(all_results, top_k * 3)
            
            # Step 4: Convert vector results to VideoClip objects
            clip_metadata_list = []
            for vector_result in merged_results:
                # Extract metadata from vector result
                metadata = vector_result.get("metadata", {})
                result_video_id = metadata.get("video_id", "")
                
                # Handle timecodes - they might be strings (old data) or floats (new data)
                start_timecode_raw = metadata.get("start_timecode", 0.0)
                end_timecode_raw = metadata.get("end_timecode", 0.0)
                
                # Convert to float if they're strings
                try:
                    start_timecode = float(start_timecode_raw) if start_timecode_raw else 0.0
                    end_timecode = float(end_timecode_raw) if end_timecode_raw else 0.0
                except (ValueError, TypeError):
                    logger.warning(f"Invalid timecode format: start={start_timecode_raw}, end={end_timecode_raw}")
                    start_timecode = 0.0
                    end_timecode = 0.0
                
                # Filter out clips longer than 10 seconds
                clip_duration = end_timecode - start_timecode
                if clip_duration > 10.0:
                    logger.debug(
                        f"Skipping clip from video {result_video_id} "
                        f"[{start_timecode:.1f}s-{end_timecode:.1f}s] "
                        f"(duration: {clip_duration:.1f}s > 10s limit)"
                    )
                    continue
                
                s3_key = metadata.get("s3_key", "")
                
                # Get relevance score (distance converted to similarity score)
                # For cosine distance: similarity = 1 - distance
                distance = vector_result.get("distance", 0.0)
                relevance_score = max(0.0, min(1.0, 1.0 - distance))
                
                # Store clip metadata for later processing
                clip_metadata_list.append({
                    "video_id": result_video_id,
                    "start_timecode": start_timecode,
                    "end_timecode": end_timecode,
                    "relevance_score": relevance_score,
                    "s3_key": s3_key,
                    "metadata": metadata
                })
            
            # Limit to requested top_k BEFORE generating thumbnails
            clip_metadata_list = clip_metadata_list[:top_k]
            
            # Second pass: generate thumbnails and create VideoClip objects only for top_k results
            clips = []
            for clip_meta in clip_metadata_list:
                # Generate presigned URL for video streaming with time range restriction
                video_stream_url = self._generate_presigned_url(
                    s3_key=clip_meta["s3_key"],
                    start_timecode=clip_meta["start_timecode"],
                    end_timecode=clip_meta["end_timecode"]
                )
                
                # Generate thumbnail URL (only for clips that will be returned)
                screenshot_url = await self._generate_screenshot(
                    s3_key=clip_meta["s3_key"],
                    timecode=clip_meta["start_timecode"],
                    video_id=clip_meta["video_id"],
                    index_id=index_id,
                    generate=generate_screenshots
                )
                
                # Get transcription text for this clip
                transcription_text = self.transcription_service.get_segments_for_clip(
                    video_id=clip_meta["video_id"],
                    start_time=clip_meta["start_timecode"],
                    end_time=clip_meta["end_timecode"]
                )
                
                # Add transcription to metadata if available
                metadata = clip_meta["metadata"].copy()
                if transcription_text:
                    metadata["transcription"] = transcription_text
                
                # Create VideoClip object
                clip = VideoClip(
                    video_id=clip_meta["video_id"],
                    start_timecode=clip_meta["start_timecode"],
                    end_timecode=clip_meta["end_timecode"],
                    relevance_score=clip_meta["relevance_score"],
                    screenshot_url=screenshot_url,
                    video_stream_url=video_stream_url,
                    metadata=metadata
                )
                
                clips.append(clip)
            
            # Calculate search time
            search_time = time.time() - start_time
            
            # Format query for display (convert list to string if needed)
            query_display = query_for_semantic if query_for_semantic else (query if isinstance(query, str) else " OR ".join(query) if query else "[image search]")
            
            # Create SearchResults object
            results = SearchResults(
                query=query_display,
                clips=clips,
                total_results=len(clips),
                search_time=search_time
            )
            
            logger.info(
                f"Search completed in {search_time:.2f}s, found {len(clips)} results"
            )
            
            return results
            
        except BedrockError as e:
            logger.error(f"Failed to embed query: {e}")
            raise
        except AWSServiceError as e:
            logger.error(f"Failed to search vectors: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            raise AWSServiceError(f"Search failed: {str(e)}") from e
    
    async def _embed_query(self, query: str) -> List[float]:
        """Embed a text query using Marengo model.
        
        Args:
            query: Text query to embed
        
        Returns:
            List of floats representing the query embedding
        
        Raises:
            BedrockError: If embedding generation fails
        """
        try:
            logger.debug(f"Embedding query: {query[:50]}...")
            
            # Use Marengo text embedding
            embedding = self.bedrock.invoke_marengo_text_embedding(
                text=query,
                text_truncate="end"
            )
            
            logger.debug(f"Generated query embedding with {len(embedding)} dimensions")
            
            return embedding
            
        except BedrockError as e:
            logger.error(f"Failed to embed query: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error embedding query: {e}")
            raise BedrockError(f"Failed to embed query: {str(e)}") from e
    async def _embed_query_multimodal(
            self,
            query: Optional[str] = None,
            image_bytes: Optional[bytes] = None
        ) -> List[float]:
            """Embed a query using text, image, or both.

            This method uses the Marengo model's multimodal embedding capability
            to generate embeddings from text, images, or both inputs combined.

            Args:
                query: Optional text query
                image_bytes: Optional image bytes

            Returns:
                List of floats representing the query embedding

            Raises:
                BedrockError: If embedding generation fails

            Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
            """
            try:
                # Determine input description for logging
                if query and image_bytes:
                    input_desc = f"multimodal query (text + image): {query[:50]}..."
                elif image_bytes:
                    input_desc = "image-only query"
                else:
                    input_desc = f"text query: {query[:50]}..."

                logger.debug(f"Embedding {input_desc}")

                # Use multimodal embedding method
                embedding = self.bedrock.invoke_marengo_multimodal_embedding(
                    text=query,
                    image_bytes=image_bytes
                )

                logger.debug(f"Generated embedding with {len(embedding)} dimensions")

                return embedding

            except BedrockError as e:
                logger.error(f"Failed to embed query: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error embedding query: {e}")
                raise BedrockError(f"Failed to embed query: {str(e)}") from e

    
    async def _similarity_search(
        self,
        query_embedding: List[float],
        index_id: str,
        top_k: int,
        modalities: Optional[List[str]] = None,
        video_id: Optional[str] = None
    ) -> List[dict]:
        """Perform similarity search in S3 Vectors with optional modality filtering.
        
        Args:
            query_embedding: Query embedding vector
            index_id: ID of the vector index to search
            top_k: Number of results to return
            modalities: Optional list of modalities to filter by (visual, audio, transcription).
                       If None or contains all three, no modality filter is applied.
            video_id: Optional video ID to limit search to a single video.
        
        Returns:
            List of dictionaries containing vector results with metadata
        
        Raises:
            AWSServiceError: If similarity search fails
        """
        try:
            logger.debug(f"Performing similarity search in index {index_id}")
            
            # S3 Vectors index name uses "index-{uuid}" format
            vector_index_name = f"index-{index_id}".lower()
            
            # Build metadata filter
            metadata_filter = self._build_modality_filter(modalities, video_id)
            
            # Query vectors in S3 Vectors
            results = self.s3_vectors.query_vectors(
                index_name=vector_index_name,
                query_vector=query_embedding,
                top_k=top_k,
                metadata_filter=metadata_filter,
                return_distance=True,
                return_metadata=True
            )
            
            logger.debug(f"Similarity search returned {len(results)} results")
            
            return results
            
        except AWSServiceError as e:
            logger.error(f"Failed to perform similarity search: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during similarity search: {e}")
            raise AWSServiceError(f"Similarity search failed: {str(e)}") from e
    
    def _build_modality_filter(self, modalities: Optional[List[str]], video_id: Optional[str] = None) -> Optional[dict]:
        """Build S3 Vectors metadata filter for modality and video filtering.
        
        Args:
            modalities: List of modalities to filter by (visual, audio, transcription).
                       If None or contains all three, returns filter for clips only.
            video_id: Optional video ID to limit search to a single video.
        
        Returns:
            Metadata filter dictionary for S3 Vectors query, or None if no filter needed.
        """
        filters = []
        
        # Always filter to clips only (exclude full video/asset embeddings)
        filters.append({"embedding_scope": {"$eq": "clip"}})
        
        # Add video_id filter if specified
        if video_id:
            filters.append({"video_id": {"$eq": video_id}})
        
        # If no modalities specified or all three are selected, only filter by scope (and video_id if present)
        all_modalities = {'visual', 'audio', 'transcription'}
        if modalities and set(modalities) != all_modalities:
            # Use $in to match any of the selected modalities
            filters.append({"embedding_option": {"$in": modalities}})
        
        # Combine all filters with AND
        if len(filters) == 1:
            return filters[0]
        return {"$and": filters}
    
    async def _lexical_transcription_search(
        self,
        query: Union[str, List[str]],
        index_id: str,
        top_k: int,
        video_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Perform lexical search across transcription text.
        
        Searches for exact substring matches (case-insensitive) in stored
        transcription JSON files. Supports multiple alternative search terms
        with OR logic.
        
        Args:
            query: Search text to find in transcriptions. Can be:
                   - A single string: "term"
                   - A list of alternative terms: ["term1", "term2", "term3"]
                   All terms are matched with OR logic (any match counts)
            index_id: ID of the index to search
            top_k: Maximum number of results to return
            video_id: Optional video ID to limit search to a single video
        
        Returns:
            List of matching clips with metadata in the same format as similarity search
        """
        import boto3
        from botocore.exceptions import ClientError
        
        # Normalize query to list of terms
        if isinstance(query, str):
            search_terms = [query.lower().strip()]
        else:
            search_terms = [term.lower().strip() for term in query if term.strip()]
        
        if not search_terms:
            return []
        
        logger.info(f"Performing lexical transcription search for: {search_terms[0][:50]}... ({len(search_terms)} term(s))")
        
        matching_clips = []
        
        try:
            # Get all videos in the index (or just the specified video)
            index_manager = self._get_index_manager()
            videos = await index_manager.list_videos_in_index(index_id)
            
            logger.info(f"Found {len(videos)} videos in index {index_id}")
            
            # Filter to single video if video_id is specified
            if video_id:
                videos = [v for v in videos if v.id == video_id]
                logger.info(f"Filtered to {len(videos)} videos for video_id={video_id}")
            
            logger.debug(f"Searching transcriptions for {len(videos)} videos")
            
            # Use boto3 directly for S3 access (consistent with transcription service)
            s3_client = boto3.client("s3", region_name=self.config.aws_region)
            
            for video in videos:
                vid = video.id
                
                # Load transcription from S3
                transcription_key = f"transcriptions/segments/{vid}.json"
                try:
                    response = s3_client.get_object(
                        Bucket=self.config.s3_bucket_name,
                        Key=transcription_key
                    )
                    transcription_data = json.loads(response["Body"].read().decode("utf-8"))
                    segments = transcription_data.get("segments", [])
                    logger.debug(f"Loaded {len(segments)} segments for video {vid}")
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code", "Unknown")
                    if error_code == "NoSuchKey":
                        logger.debug(f"No transcription found for video {vid}")
                    else:
                        logger.warning(f"Error loading transcription for {vid}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Error parsing transcription for video {vid}: {e}")
                    continue
                
                # Search each segment for any of the query terms
                for segment in segments:
                    text = segment.get("text", "")
                    if not text:
                        continue
                    
                    text_lower = text.lower()
                    
                    # Check if any search term matches (OR logic)
                    matched_term = None
                    for term in search_terms:
                        if term in text_lower:
                            matched_term = term
                            break
                    
                    if matched_term:
                        # Calculate relevance based on match quality
                        relevance = self._calculate_lexical_relevance(matched_term, text_lower)
                        
                        start_time = float(segment.get("start_time", 0))
                        end_time = float(segment.get("end_time", 0))
                        
                        # Skip segments longer than 10 seconds (consistent with semantic search)
                        if end_time - start_time > 10.0:
                            logger.debug(f"Skipping segment longer than 10s: {start_time}-{end_time}")
                            continue
                        
                        # Get video S3 key from video metadata
                        # s3_uri format: s3://bucket/path/to/video.mp4
                        s3_key = video.s3_uri.replace(f"s3://{self.config.s3_bucket_name}/", "") if video.s3_uri else f"videos/{index_id}/{vid}"
                        
                        logger.debug(f"Found lexical match in video {vid} at {start_time}-{end_time}: {text[:50]}...")
                        
                        # Format result to match similarity search output
                        matching_clips.append({
                            "metadata": {
                                "video_id": vid,
                                "start_timecode": start_time,
                                "end_timecode": end_time,
                                "s3_key": s3_key,
                                "embedding_option": "transcription",
                                "embedding_scope": "clip"
                            },
                            "distance": 1.0 - relevance,  # Convert relevance to distance
                            "match_type": "lexical",
                            "transcription_match": text,
                            "matched_term": matched_term  # Track which term matched
                        })
            
            # Sort by relevance (lower distance = higher relevance)
            matching_clips.sort(key=lambda x: x["distance"])
            
            logger.info(f"Lexical search found {len(matching_clips)} matches")
            
            return matching_clips[:top_k]
            
        except Exception as e:
            logger.error(f"Error in lexical transcription search: {e}")
            return []
    
    def _calculate_lexical_relevance(self, query: str, text: str) -> float:
        """Calculate relevance score for lexical match.
        
        Scoring factors:
        - Exact match (full text equals query): 1.0
        - Query is significant portion of text: 0.7-0.9
        - Query is small portion of text: 0.5-0.7
        
        Args:
            query: The search query (lowercase)
            text: The transcription text (lowercase)
        
        Returns:
            Relevance score between 0.5 and 1.0
        """
        query_len = len(query)
        text_len = len(text)
        
        if text == query:
            return 1.0
        
        if text_len == 0:
            return 0.5
        
        # Ratio of query length to text length
        ratio = query_len / text_len
        
        # Base score + bonus for higher coverage
        return min(0.5 + (ratio * 0.5), 0.95)
    
    def _merge_search_results(
        self,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Merge and deduplicate semantic and lexical results.
        
        Deduplication key: (video_id, start_timecode rounded to nearest second)
        
        When duplicates exist:
        - Keep the higher relevance score (lower distance)
        - Track match types from both sources
        
        Args:
            results: Combined list of semantic and lexical results
            top_k: Maximum number of results to return
        
        Returns:
            Deduplicated and sorted list of results
        """
        seen: Dict[tuple, Dict[str, Any]] = {}
        
        for result in results:
            metadata = result.get("metadata", {})
            video_id = metadata.get("video_id", "")
            start_time = metadata.get("start_timecode", 0)
            
            # Create deduplication key
            key = (video_id, round(float(start_time)))
            
            if key not in seen:
                # First occurrence
                result["match_types"] = [result.get("match_type", "semantic")]
                seen[key] = result
            else:
                # Duplicate found - merge
                existing = seen[key]
                existing_distance = existing.get("distance", 1.0)
                new_distance = result.get("distance", 1.0)
                
                # Track match types
                existing_types = existing.get("match_types", ["semantic"])
                new_type = result.get("match_type", "semantic")
                if new_type not in existing_types:
                    existing_types.append(new_type)
                    existing["match_types"] = existing_types
                
                # Keep the one with lower distance (higher relevance)
                if new_distance < existing_distance:
                    result["match_types"] = existing_types
                    seen[key] = result
        
        # Sort by distance (lower = more relevant)
        merged = list(seen.values())
        merged.sort(key=lambda x: x.get("distance", 1.0))
        
        return merged[:top_k]
    
    async def _generate_screenshot(
        self,
        s3_key: str,
        timecode: float,
        video_id: str,
        index_id: str,
        generate: bool = True
    ) -> str:
        """Generate a screenshot URL for a video clip at a specific timecode.
        
        Prioritizes clip-specific thumbnails over video thumbnails. Returns immediately
        with a cached clip thumbnail if available, otherwise falls back to the video's
        main thumbnail only if clip thumbnail generation hasn't completed yet.
        
        Args:
            s3_key: S3 key of the video
            timecode: Timecode in seconds for frame extraction
            video_id: ID of the video
            index_id: ID of the index
            generate: Whether to generate thumbnail (default: True)
        
        Returns:
            Presigned S3 URL for thumbnail (prioritizes clip-specific, falls back to video)
        """
        if not generate:
            return f"https://placeholder.com/screenshot?video={s3_key}&t={timecode}"
        
        try:
            # Round timecode to nearest second for caching
            rounded_timecode = round(timecode)
            
            # PRIORITY 1: Check if clip-specific thumbnail exists in S3 within 3 seconds window
            # Look for thumbnails at exact time or up to 3 seconds after
            best_thumbnail_key = None
            best_timecode_diff = float('inf')
            
            for offset in range(4):  # Check 0, 1, 2, 3 seconds after
                candidate_timecode = rounded_timecode + offset
                candidate_key = f"thumbnails/{index_id}/{video_id}/clip_{candidate_timecode}.jpg"
                
                # Check if this thumbnail actually exists in S3
                if self.s3.object_exists(candidate_key):
                    # Check if this is closer than previous best
                    if offset < best_timecode_diff:
                        best_thumbnail_key = candidate_key
                        best_timecode_diff = offset
                        # If exact match, use it immediately
                        if offset == 0:
                            thumbnail_url = self.s3.generate_presigned_url(
                                key=candidate_key,
                                expiration=3600,
                                http_method="GET"
                            )
                            logger.debug(f"Using exact clip thumbnail for {video_id} at {rounded_timecode}s")
                            return thumbnail_url
            
            # If we found a clip thumbnail within 3 seconds, use it
            if best_thumbnail_key:
                thumbnail_url = self.s3.generate_presigned_url(
                    key=best_thumbnail_key,
                    expiration=3600,
                    http_method="GET"
                )
                logger.debug(f"Using clip thumbnail for {video_id} at {rounded_timecode}s (found at +{best_timecode_diff}s)")
                return thumbnail_url
            
            # PRIORITY 2: No clip thumbnail found - trigger async generation and fall back to video thumbnail
            thumbnail_key = f"thumbnails/{index_id}/{video_id}/clip_{rounded_timecode}.jpg"
            
            # Start async thumbnail generation (fire and forget)
            import asyncio
            asyncio.create_task(
                self._generate_clip_thumbnail_async(
                    s3_key=s3_key,
                    timecode=rounded_timecode,
                    thumbnail_key=thumbnail_key,
                    video_id=video_id
                )
            )
            
            # Fall back to video's main thumbnail while clip thumbnail is being generated
            logger.debug(f"No clip thumbnail for {video_id} at {rounded_timecode}s, falling back to video thumbnail while generating")
            return await self._get_video_thumbnail(index_id, video_id)
            
        except Exception as e:
            logger.warning(f"Failed to get thumbnail for {video_id} at {timecode}s: {e}")
            # Fall back to video thumbnail
            try:
                return await self._get_video_thumbnail(index_id, video_id)
            except Exception:
                return f"https://placeholder.com/screenshot?video={s3_key}&t={timecode}"
    
    async def _generate_clip_thumbnail_async(
        self,
        s3_key: str,
        timecode: float,
        thumbnail_key: str,
        video_id: str
    ) -> None:
        """Generate a clip-specific thumbnail asynchronously.
        
        This runs in the background and doesn't block the search response.
        Broadcasts a WebSocket notification when complete.
        
        Args:
            s3_key: S3 key of the video
            timecode: Timecode in seconds for frame extraction
            thumbnail_key: S3 key where thumbnail should be stored
            video_id: ID of the video
        """
        try:
            import tempfile
            import os
            import subprocess
            
            logger.info(f"Starting async thumbnail generation for {video_id} at {timecode}s")
            
            # Download video to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_video:
                video_path = tmp_video.name
                self.s3.download(s3_key, tmp_video)
            
            try:
                # Generate thumbnail at specific timecode using ffmpeg
                thumbnail_path = video_path.replace('.mp4', f'_thumb_{timecode}.jpg')
                
                result = subprocess.run(
                    [
                        get_ffmpeg_path(),
                        "-ss", str(timecode),  # Seek to timecode
                        "-i", video_path,
                        "-vframes", "1",  # Extract single frame
                        "-vf", "scale=640:-1",  # Scale to 640px width, maintain aspect ratio
                        "-y",  # Overwrite output file
                        thumbnail_path
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and os.path.exists(thumbnail_path):
                    # Upload thumbnail to S3
                    with open(thumbnail_path, 'rb') as thumb_file:
                        self.s3.upload(
                            file_obj=thumb_file,
                            key=thumbnail_key,
                            content_type='image/jpeg',
                            metadata={
                                'video_id': video_id,
                                'timecode': str(timecode)
                            }
                        )
                    
                    logger.info(f"Successfully generated clip thumbnail for {video_id} at {timecode}s")
                    os.remove(thumbnail_path)
                    
                    # Generate presigned URL for the new thumbnail
                    thumbnail_url = self.s3.generate_presigned_url(
                        key=thumbnail_key,
                        expiration=3600,
                        http_method="GET"
                    )
                    
                    # Broadcast thumbnail ready notification via WebSocket
                    await self._broadcast_thumbnail_ready(video_id, timecode, thumbnail_url)
                else:
                    logger.warning(f"Failed to generate thumbnail at {timecode}s: {result.stderr}")
                    
            finally:
                # Clean up temp video file
                if os.path.exists(video_path):
                    os.remove(video_path)
                    
        except Exception as e:
            logger.error(f"Error in async thumbnail generation for {video_id} at {timecode}s: {e}")
    
    async def _broadcast_thumbnail_ready(
        self,
        video_id: str,
        timecode: float,
        thumbnail_url: str
    ) -> None:
        """Broadcast thumbnail ready notification via WebSocket.
        
        Args:
            video_id: ID of the video
            timecode: Timecode of the thumbnail
            thumbnail_url: Presigned URL of the generated thumbnail
        """
        try:
            # Import WebSocket API module to get the manager
            from api.websocket import get_websocket_manager
            import asyncio
            
            # Add small delay to ensure WebSocket connections are fully established
            await asyncio.sleep(0.1)
            
            try:
                websocket_manager = get_websocket_manager()
                await websocket_manager.broadcast_thumbnail_ready(
                    video_id=video_id,
                    timecode=timecode,
                    thumbnail_url=thumbnail_url
                )
            except RuntimeError:
                # WebSocket manager not initialized, skip notification
                logger.debug("WebSocket manager not initialized, skipping thumbnail notification")
        except Exception as e:
            logger.warning(f"Failed to broadcast thumbnail ready notification: {e}")
    
    async def _get_video_thumbnail(self, index_id: str, video_id: str) -> str:
        """Get the main video thumbnail (generated at upload time).
        
        Args:
            index_id: ID of the index
            video_id: ID of the video
            
        Returns:
            Presigned S3 URL for the video thumbnail
        """
        thumbnail_key = f"thumbnails/{index_id}/{video_id}/thumb.jpg"
        return self.s3.generate_presigned_url(
            key=thumbnail_key,
            expiration=3600,
            http_method="GET"
        )
    
    def _generate_presigned_url(
        self,
        s3_key: str,
        start_timecode: Optional[float] = None,
        end_timecode: Optional[float] = None,
        expiration: int = 3600
    ) -> str:
        """Generate a presigned URL for video streaming with timecode restrictions.
        
        Uses Media Fragments URI specification (https://www.w3.org/TR/media-frags/)
        to restrict playback to a specific time range. The fragment identifier #t=start,end
        is supported by HTML5 video players.
        
        Args:
            s3_key: S3 key of the video
            start_timecode: Optional start timecode in seconds
            end_timecode: Optional end timecode in seconds
            expiration: URL expiration time in seconds (default: 3600)
        
        Returns:
            Presigned S3 URL for video streaming with time fragment
        
        Raises:
            AWSServiceError: If URL generation fails
        """
        try:
            # Generate presigned URL
            url = self.s3.generate_presigned_url(
                key=s3_key,
                expiration=expiration,
                http_method="GET"
            )
            
            # Add Media Fragments URI time range if specified
            # Format: #t=start,end (both in seconds)
            if start_timecode is not None and start_timecode > 0:
                if end_timecode is not None and end_timecode > start_timecode:
                    # Restrict playback to the clip range
                    url = f"{url}#t={start_timecode},{end_timecode}"
                else:
                    # Only start time specified
                    url = f"{url}#t={start_timecode}"
            
            logger.debug(f"Generated presigned URL for {s3_key}")
            
            return url
            
        except AWSServiceError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating presigned URL: {e}")
            raise AWSServiceError(f"Failed to generate presigned URL: {str(e)}") from e
