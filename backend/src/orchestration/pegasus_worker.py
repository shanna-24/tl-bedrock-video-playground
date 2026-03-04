"""Pegasus Worker for deep video analysis.

This module implements the PegasusWorker component that performs deep video
analysis using the Pegasus model. It can analyze individual segments or multiple
segments in parallel with concurrency control.

Validates: Requirements 1.3, 3.2, 7.2
"""

import asyncio
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from models.orchestration import VideoSegment, SegmentAnalysis
from utils.ffmpeg import get_ffmpeg_path
from utils.progress_tracker import check_cancellation
from exceptions import AnalysisCancelledError

logger = logging.getLogger(__name__)


class PegasusWorker:
    """Performs deep video analysis using Pegasus model.
    
    The PegasusWorker analyzes video segments using the Pegasus model to generate
    insights, descriptions, or answers to questions about video content. It supports
    both single segment analysis and parallel analysis of multiple segments with
    concurrency control.
    
    For segment-level analysis, it downloads videos from S3, extracts segments using
    ffmpeg, uploads temporary segment videos to S3, and analyzes them with Pegasus.
    
    Videos are cached during a single analysis session to avoid redundant downloads
    when multiple segments come from the same video.
    
    Attributes:
        bedrock: BedrockClient instance for invoking Pegasus model
        s3: S3Client instance for video download/upload operations
        _video_cache: Dictionary mapping S3 URIs to local file paths (session cache)
    """
    
    def __init__(self, bedrock_client: BedrockClient, s3_client: Optional[S3Client] = None):
        """Initialize the PegasusWorker.
        
        Args:
            bedrock_client: BedrockClient instance for Pegasus analysis
            s3_client: Optional S3Client instance for segment extraction (required for segment-level analysis)
        """
        self.bedrock = bedrock_client
        self.s3 = s3_client
        self._video_cache = {}  # Cache for downloaded videos during analysis session
        logger.info("Initialized PegasusWorker")
    
    async def analyze_segment(
        self,
        segment: VideoSegment,
        prompt: str,
        temperature: float = 0.2,
        extract_segment: bool = False,
        shared_temp_path: Optional[Path] = None
    ) -> SegmentAnalysis:
        """Analyze a single video segment using Pegasus.
        
        This method invokes the Pegasus model to analyze a video segment and
        generate insights based on the provided prompt.
        
        When extract_segment is True, it downloads the full video (or uses cached version),
        extracts the specific segment using ffmpeg, uploads it to S3 temporarily, and 
        analyzes the segment video. This enables true segment-level analysis.
        
        Args:
            segment: VideoSegment object containing video metadata
            prompt: Analysis prompt for Pegasus
            temperature: Temperature for randomness (0-1, default: 0.2)
            extract_segment: Whether to extract and analyze the specific segment
                           (requires s3_client and shared_temp_path to be provided)
            shared_temp_path: Required when extract_segment=True. Temporary directory path
                            for video processing. Must be provided by caller to ensure
                            proper video caching across multiple segments.
        
        Returns:
            SegmentAnalysis object containing the segment, insights, and timestamp
        
        Raises:
            Exception: If Pegasus invocation fails
            ValueError: If extract_segment is True but s3_client or shared_temp_path not provided
        """
        logger.debug(
            f"Analyzing segment from video {segment.video_id} "
            f"[{segment.start_time:.1f}s-{segment.end_time:.1f}s] "
            f"(extract_segment={extract_segment})"
        )
        
        try:
            # Determine which S3 URI to analyze
            analysis_s3_uri = segment.s3_uri
            temp_segment_key = None
            
            # If segment extraction is requested and segment has specific timing
            if extract_segment and segment.start_time > 0 and segment.end_time > segment.start_time:
                if not self.s3:
                    raise ValueError("S3Client is required for segment extraction")
                
                if not shared_temp_path:
                    raise ValueError(
                        "shared_temp_path is required for segment extraction. "
                        "This should be provided by analyze_segments_parallel() or created "
                        "by the caller for single segment analysis."
                    )
                
                logger.info(
                    f"Extracting segment [{segment.start_time:.1f}s-{segment.end_time:.1f}s] "
                    f"from video {segment.video_id}"
                )
                
                # Extract segment and upload to S3 using the shared temp directory
                analysis_s3_uri, temp_segment_key = await self._extract_and_upload_segment(
                    segment, shared_temp_path
                )
            
            try:
                # Invoke Pegasus analysis
                # Note: BedrockClient.invoke_pegasus_analysis is synchronous,
                # but we wrap it in an async function for consistency
                result = self.bedrock.invoke_pegasus_analysis(
                    s3_uri=analysis_s3_uri,
                    prompt=prompt,
                    temperature=temperature
                )
                
                # Create SegmentAnalysis object
                analysis = SegmentAnalysis(
                    segment=segment,
                    insights=result["message"],
                    analyzed_at=datetime.now()
                )
                
                logger.info(
                    f"Successfully analyzed segment from video {segment.video_id} "
                    f"({len(analysis.insights)} characters)"
                )
                
                return analysis
                
            finally:
                # Clean up temporary segment file from S3 if created
                if temp_segment_key:
                    try:
                        self.s3.delete(temp_segment_key)
                        logger.debug(f"Cleaned up temporary segment: {temp_segment_key}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up temporary segment {temp_segment_key}: {e}")
            
        except Exception as e:
            logger.error(
                f"Failed to analyze segment from video {segment.video_id} "
                f"[{segment.start_time:.1f}s-{segment.end_time:.1f}s]: {e}"
            )
            raise
    
    async def analyze_segments_parallel(
        self,
        segments: List[VideoSegment],
        prompt: str,
        temperature: float = 0.2,
        max_concurrent: int = 3,
        extract_segments: bool = False,
        correlation_id: Optional[str] = None
    ) -> List[SegmentAnalysis]:
        """Analyze multiple video segments in parallel with concurrency control.
        
        This method analyzes multiple segments concurrently while respecting the
        maximum concurrency limit. Individual failures are handled gracefully,
        allowing successful analyses to be returned even if some fail.
        
        When extract_segments is True, downloads full videos once per unique video,
        extracts segments using ffmpeg, and analyzes each segment individually.
        
        Args:
            segments: List of VideoSegment objects to analyze
            prompt: Analysis prompt for Pegasus
            temperature: Temperature for randomness (0-1, default: 0.2)
            max_concurrent: Maximum number of concurrent analyses (default: 3)
            extract_segments: Whether to extract and analyze specific segments
            correlation_id: Optional correlation ID for cancellation tracking
        
        Returns:
            List of SegmentAnalysis objects for successful analyses.
            Failed analyses are logged but not included in the result.
        
        Raises:
            ValueError: If segments is empty or max_concurrent < 1
            AnalysisCancelledError: If the analysis is cancelled by the user
        """
        if not segments:
            raise ValueError("segments cannot be empty")
        
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        
        logger.info(
            f"Starting parallel analysis of {len(segments)} segments "
            f"(max_concurrent={max_concurrent}, extract_segments={extract_segments})"
        )
        
        # Check for cancellation before starting
        if correlation_id:
            check_cancellation(correlation_id)
        
        # Clear video cache at the start of each analysis session
        self._video_cache.clear()
        
        # Create a shared temporary directory for the entire analysis session
        # This is REQUIRED when extract_segments=True to ensure all segments use the same
        # temp directory and video caching works correctly
        temp_dir_obj = None
        shared_temp_path = None
        
        if extract_segments:
            temp_dir_obj = tempfile.TemporaryDirectory()
            shared_temp_path = Path(temp_dir_obj.name)
            logger.info(f"Created shared temp directory for {len(segments)} segments: {shared_temp_path}")
        
        try:
            # Create semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)
            # Track if cancellation was requested
            cancelled = False
            
            async def analyze_with_limit(segment: VideoSegment) -> SegmentAnalysis:
                """Analyze a segment with semaphore-based concurrency control."""
                nonlocal cancelled
                # Check for cancellation before acquiring semaphore
                if correlation_id:
                    check_cancellation(correlation_id)
                
                async with semaphore:
                    # Check again after acquiring semaphore (may have waited)
                    if correlation_id:
                        check_cancellation(correlation_id)
                    
                    return await self.analyze_segment(
                        segment, prompt, temperature, extract_segments, shared_temp_path
                    )
            
            # Create tasks for all segments
            tasks = [analyze_with_limit(seg) for seg in segments]
            
            # Execute all tasks and gather results, capturing exceptions
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and collect successful results
            successful_results = []
            failed_count = 0
            cancellation_error = None
            
            for i, result in enumerate(results):
                if isinstance(result, AnalysisCancelledError):
                    # Capture cancellation error to re-raise after cleanup
                    cancellation_error = result
                    logger.info(f"Segment {i+1}/{len(segments)} was cancelled")
                elif isinstance(result, Exception):
                    failed_count += 1
                    logger.error(
                        f"Failed to analyze segment {i+1}/{len(segments)} "
                        f"(video {segments[i].video_id}): {result}"
                    )
                else:
                    successful_results.append(result)
            
            # If cancellation was requested, raise the error
            if cancellation_error:
                raise cancellation_error
            
            logger.info(
                f"Parallel analysis completed: {len(successful_results)} successful, "
                f"{failed_count} failed"
            )
            
            return successful_results
            
        finally:
            # Clear video cache after analysis session completes
            self._video_cache.clear()
            
            # Clean up shared temporary directory
            if temp_dir_obj:
                try:
                    temp_dir_obj.cleanup()
                    logger.debug("Cleaned up shared temp directory")
                except Exception as e:
                    logger.warning(f"Failed to clean up shared temp directory: {e}")
    
    async def _extract_and_upload_segment(
        self,
        segment: VideoSegment,
        temp_dir: Path
    ) -> tuple[str, str]:
        """Extract a video segment using ffmpeg and upload to S3.
        
        Downloads the full video from S3 (or uses cached version), extracts the 
        specific segment using ffmpeg, uploads the segment to a temporary location 
        in S3, and returns the S3 URI.
        
        Videos are cached during the analysis session to avoid redundant downloads
        when multiple segments come from the same video.
        
        Args:
            segment: VideoSegment with timing information
            temp_dir: Temporary directory path for video processing
        
        Returns:
            Tuple of (segment_s3_uri, temp_segment_key) for the uploaded segment
        
        Raises:
            RuntimeError: If ffmpeg extraction fails
            AWSServiceError: If S3 operations fail
        """
        # Check if video is already cached
        if segment.s3_uri in self._video_cache:
            local_video_path = self._video_cache[segment.s3_uri]
            logger.debug(f"Using cached video from {local_video_path}")
        else:
            # Download full video from S3
            video_filename = segment.s3_uri.split('/')[-1]
            local_video_path = temp_dir / video_filename
            
            logger.info(f"Downloading video from {segment.s3_uri} (first time)")
            
            # Extract S3 key from URI
            s3_key = segment.s3_uri.replace(f"s3://{self.s3.bucket_name}/", "")
            
            with open(local_video_path, 'wb') as f:
                self.s3.download(s3_key, f)
            
            # Cache the video path for reuse
            self._video_cache[segment.s3_uri] = local_video_path
            logger.debug(f"Cached video at {local_video_path}")
        
        # Extract segment using ffmpeg
        segment_filename = f"segment_{segment.video_id}_{segment.start_time:.1f}_{segment.end_time:.1f}.mp4"
        segment_path = temp_dir / segment_filename
        
        duration = segment.end_time - segment.start_time
        
        logger.debug(
            f"Extracting segment: start={segment.start_time:.1f}s, duration={duration:.1f}s"
        )
        
        cmd = [
            get_ffmpeg_path(),
            '-y',  # Overwrite output file
            '-ss', str(segment.start_time),
            '-i', str(local_video_path),
            '-t', str(duration),
            '-c', 'copy',  # Copy codec for faster extraction
            '-avoid_negative_ts', '1',
            str(segment_path)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        # Upload segment to S3 temporary location
        temp_segment_key = f"temp/segments/{segment_filename}"
        
        logger.debug(f"Uploading segment to s3://{self.s3.bucket_name}/{temp_segment_key}")
        
        with open(segment_path, 'rb') as f:
            segment_s3_uri = self.s3.upload(
                file_obj=f,
                key=temp_segment_key,
                content_type="video/mp4"
            )
        
        logger.info(f"Segment extracted and uploaded: {segment_s3_uri}")
        
        return segment_s3_uri, temp_segment_key
