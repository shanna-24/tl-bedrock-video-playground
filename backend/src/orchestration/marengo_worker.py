"""Marengo Worker for semantic video search.

This module implements the MarengoWorker component that executes semantic search
using Marengo embeddings to find relevant video segments across the index.

Validates: Requirements 1.3, 2.2, 2.3, 2.4
"""

import logging
from typing import List

from services.search_service import SearchService
from models.orchestration import VideoSegment

logger = logging.getLogger(__name__)


class MarengoWorker:
    """Executes semantic search using Marengo embeddings.
    
    The MarengoWorker retrieves relevant video segments from the index using
    semantic search, deduplicates overlapping segments, ranks them by relevance,
    and selects the top N segments for analysis.
    
    Attributes:
        search: SearchService instance for performing semantic search
        max_results_per_query: Maximum number of search results to retrieve per query
    """
    
    def __init__(self, search_service: SearchService, max_results_per_query: int = 15):
        """Initialize the MarengoWorker.
        
        Args:
            search_service: SearchService instance for semantic search
            max_results_per_query: Maximum number of search results per query (from config)
        """
        self.search = search_service
        self.max_results_per_query = max_results_per_query
        logger.info(f"Initialized MarengoWorker with max_results_per_query: {max_results_per_query}")
    
    async def search_segments(
        self,
        index_id: str,
        search_queries: List[str],
        max_segments: int
    ) -> List[VideoSegment]:
        """Search for relevant video segments using semantic search.
        
        This method:
        1. Executes each search query using the SearchService
        2. Converts search results to VideoSegment objects
        3. Deduplicates overlapping segments
        4. Ranks segments by relevance score
        5. Returns the top N segments
        
        Args:
            index_id: ID of the index to search
            search_queries: List of search query strings
            max_segments: Maximum number of segments to return
        
        Returns:
            List of VideoSegment objects, ranked by relevance score,
            limited to max_segments
        
        Raises:
            ValueError: If search_queries is empty or max_segments < 1
        """
        if not search_queries:
            raise ValueError("search_queries cannot be empty")
        
        if max_segments < 1:
            raise ValueError("max_segments must be at least 1")
        
        logger.info(
            f"Searching index {index_id} with {len(search_queries)} queries, "
            f"max_segments={max_segments}"
        )
        
        all_segments = []
        
        # Execute each search query
        for i, query in enumerate(search_queries):
            logger.debug(f"Executing search query {i+1}/{len(search_queries)}: {query[:50]}...")
            
            try:
                # Search using SearchService
                # Use configured max_results_per_query, but don't exceed what's needed
                top_k = min(self.max_results_per_query, max_segments * 2)
                
                results = await self.search.search_videos(
                    index_id=index_id,
                    query=query,
                    top_k=top_k,
                    generate_screenshots=False  # Don't need screenshots for analysis
                )
                
                # Convert search results to VideoSegment objects
                for clip in results.clips:
                    # Filter out clips longer than 10 seconds
                    clip_duration = clip.end_timecode - clip.start_timecode
                    if clip_duration > 10.0:
                        logger.debug(
                            f"Skipping clip from video {clip.video_id} "
                            f"[{clip.start_timecode:.1f}s-{clip.end_timecode:.1f}s] "
                            f"(duration: {clip_duration:.1f}s > 10s limit)"
                        )
                        continue
                    
                    # Get S3 key from metadata (stored during embedding creation)
                    s3_key = clip.metadata.get("s3_key", "")
                    
                    if not s3_key:
                        logger.error(
                            f"s3_key not found in metadata for video {clip.video_id}, "
                            "skipping segment"
                        )
                        continue
                    
                    # Construct S3 URI from bucket and key
                    s3_uri = f"s3://{self.search.config.s3_bucket_name}/{s3_key}"
                    
                    segment = VideoSegment(
                        video_id=clip.video_id,
                        s3_uri=s3_uri,
                        start_time=clip.start_timecode,
                        end_time=clip.end_timecode,
                        relevance_score=clip.relevance_score
                    )
                    all_segments.append(segment)
                
                logger.debug(f"Query {i+1} returned {len(results.clips)} segments")
                
            except Exception as e:
                logger.error(f"Failed to execute search query {i+1}: {e}")
                # Continue with other queries even if one fails
                continue
        
        if not all_segments:
            logger.warning("No segments found for any search query")
            return []
        
        logger.info(f"Total segments before deduplication: {len(all_segments)}")
        
        # Deduplicate overlapping segments
        unique_segments = self._deduplicate_segments(all_segments)
        logger.info(f"Segments after deduplication: {len(unique_segments)}")
        
        # Rank by relevance score (descending)
        ranked_segments = sorted(
            unique_segments,
            key=lambda s: s.relevance_score,
            reverse=True
        )
        
        # Select top N segments
        top_segments = ranked_segments[:max_segments]
        
        logger.info(
            f"Returning {len(top_segments)} segments "
            f"(scores: {top_segments[0].relevance_score:.3f} to "
            f"{top_segments[-1].relevance_score:.3f})"
        )
        
        return top_segments
    
    def _deduplicate_segments(self, segments: List[VideoSegment]) -> List[VideoSegment]:
        """Deduplicate overlapping video segments.
        
        This method removes duplicate segments by keeping the one with the highest
        relevance score when segments overlap significantly. Two segments are
        considered overlapping if they:
        1. Are from the same video
        2. Have temporal overlap > 50% of the shorter segment's duration
        
        Args:
            segments: List of VideoSegment objects to deduplicate
        
        Returns:
            List of unique VideoSegment objects
        """
        if not segments:
            return []
        
        # Sort by relevance score (descending) to prioritize higher-scoring segments
        sorted_segments = sorted(
            segments,
            key=lambda s: s.relevance_score,
            reverse=True
        )
        
        unique_segments = []
        
        for segment in sorted_segments:
            # Check if this segment overlaps significantly with any already selected segment
            is_duplicate = False
            
            for unique_segment in unique_segments:
                if self._segments_overlap(segment, unique_segment):
                    is_duplicate = True
                    logger.debug(
                        f"Segment {segment.video_id} "
                        f"[{segment.start_time:.1f}-{segment.end_time:.1f}] "
                        f"overlaps with existing segment "
                        f"[{unique_segment.start_time:.1f}-{unique_segment.end_time:.1f}], "
                        f"skipping (score: {segment.relevance_score:.3f} vs "
                        f"{unique_segment.relevance_score:.3f})"
                    )
                    break
            
            if not is_duplicate:
                unique_segments.append(segment)
        
        return unique_segments
    
    def _segments_overlap(self, seg1: VideoSegment, seg2: VideoSegment) -> bool:
        """Check if two segments overlap significantly.
        
        Two segments are considered overlapping if:
        1. They are from the same video
        2. Their temporal overlap is >= 50% of the shorter segment's duration
        
        Args:
            seg1: First VideoSegment
            seg2: Second VideoSegment
        
        Returns:
            True if segments overlap significantly, False otherwise
        """
        # Must be from the same video
        if seg1.video_id != seg2.video_id:
            return False
        
        # Calculate overlap
        overlap_start = max(seg1.start_time, seg2.start_time)
        overlap_end = min(seg1.end_time, seg2.end_time)
        
        # No overlap if end comes before start
        if overlap_end <= overlap_start:
            return False
        
        overlap_duration = overlap_end - overlap_start
        
        # Calculate durations
        seg1_duration = seg1.end_time - seg1.start_time
        seg2_duration = seg2.end_time - seg2.start_time
        
        # Avoid division by zero
        if seg1_duration <= 0 or seg2_duration <= 0:
            return False
        
        # Check if overlap is >= 50% of the shorter segment
        shorter_duration = min(seg1_duration, seg2_duration)
        overlap_ratio = overlap_duration / shorter_duration
        
        return overlap_ratio >= 0.5
