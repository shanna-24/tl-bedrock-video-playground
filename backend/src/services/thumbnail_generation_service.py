"""
Thumbnail Generation Service - Async thumbnail generation for video segments.

This module provides functionality to generate thumbnails for all video segments
after indexing completes. Thumbnails are generated asynchronously and cached in S3.
"""

import logging
import tempfile
import os
import subprocess
from typing import List
from concurrent.futures import ThreadPoolExecutor

from aws.s3_client import S3Client
from services.embedding_retriever import EmbeddingData
from utils.ffmpeg import get_ffmpeg_path

logger = logging.getLogger(__name__)


class ThumbnailGenerationService:
    """
    Service for generating thumbnails for video segments.
    
    This service generates thumbnails for all segments of a video after indexing
    completes. Thumbnails are generated asynchronously and cached in S3 for fast
    retrieval during search operations.
    """
    
    def __init__(
        self,
        s3_client: S3Client,
        max_concurrent_thumbnails: int = 3,
        thumbnail_width: int = 640
    ):
        """
        Initialize the thumbnail generation service.
        
        Args:
            s3_client: S3 client for uploading thumbnails
            max_concurrent_thumbnails: Maximum number of thumbnails to generate concurrently
            thumbnail_width: Width of generated thumbnails in pixels (height auto-scaled)
        """
        self.s3 = s3_client
        self.max_concurrent_thumbnails = max_concurrent_thumbnails
        self.thumbnail_width = thumbnail_width
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent_thumbnails,
            thread_name_prefix="ThumbnailGenerator"
        )
        
        logger.info(
            f"Initialized ThumbnailGenerationService "
            f"(max_concurrent={max_concurrent_thumbnails}, width={thumbnail_width}px)"
        )
    
    def generate_thumbnails_for_segments(
        self,
        embeddings: List[EmbeddingData],
        video_id: str,
        index_id: str,
        s3_key: str
    ) -> None:
        """
        Generate thumbnails for all video segments asynchronously.
        
        This method starts thumbnail generation in the background for all segments
        defined by the embeddings. It returns immediately without waiting for
        completion. Thumbnails are cached in S3 for later retrieval.
        
        Args:
            embeddings: List of embedding data containing segment timecodes
            video_id: ID of the video
            index_id: ID of the index
            s3_key: S3 key of the video file
        """
        if not embeddings:
            logger.warning(f"No embeddings provided for thumbnail generation (video_id={video_id})")
            return
        
        logger.info(
            f"Starting thumbnail generation for {len(embeddings)} segments "
            f"(video_id={video_id}, index_id={index_id})"
        )
        
        # Extract unique timecodes from embeddings (rounded to nearest second)
        timecodes = set()
        for emb in embeddings:
            # Generate thumbnail at the start of each segment
            rounded_timecode = round(emb.start_sec)
            timecodes.add(rounded_timecode)
        
        logger.info(
            f"Generating {len(timecodes)} unique thumbnails for video {video_id} "
            f"(from {len(embeddings)} segments)"
        )
        
        # Submit thumbnail generation tasks to thread pool
        futures = []
        for timecode in sorted(timecodes):
            thumbnail_key = f"thumbnails/{index_id}/{video_id}/clip_{timecode}.jpg"
            
            # Check if thumbnail already exists to avoid regeneration
            if self.s3.object_exists(thumbnail_key):
                logger.debug(f"Thumbnail already exists for {video_id} at {timecode}s, skipping")
                continue
            
            # Submit generation task
            future = self._executor.submit(
                self._generate_single_thumbnail,
                s3_key=s3_key,
                timecode=timecode,
                thumbnail_key=thumbnail_key,
                video_id=video_id
            )
            futures.append((future, timecode))
        
        if not futures:
            logger.info(f"All thumbnails already exist for video {video_id}, skipping generation")
            return
        
        logger.info(f"Submitted {len(futures)} thumbnail generation tasks for video {video_id}")
        
        # Monitor completion in background (don't block)
        def monitor_completion():
            """Monitor thumbnail generation completion and log results."""
            completed = 0
            failed = 0
            
            for future, timecode in futures:
                try:
                    success = future.result(timeout=60)  # 60 second timeout per thumbnail
                    if success:
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(
                        f"Thumbnail generation failed for {video_id} at {timecode}s: {e}"
                    )
                    failed += 1
            
            logger.info(
                f"Thumbnail generation completed for video {video_id}: "
                f"{completed} succeeded, {failed} failed out of {len(futures)} total"
            )
        
        # Start monitoring in a separate thread (non-blocking)
        import threading
        monitor_thread = threading.Thread(
            target=monitor_completion,
            name=f"ThumbnailMonitor-{video_id}",
            daemon=True
        )
        monitor_thread.start()
    
    def _generate_single_thumbnail(
        self,
        s3_key: str,
        timecode: float,
        thumbnail_key: str,
        video_id: str
    ) -> bool:
        """
        Generate a single thumbnail for a video segment.
        
        This method downloads the video, extracts a frame at the specified timecode,
        and uploads the thumbnail to S3.
        
        Args:
            s3_key: S3 key of the video
            timecode: Timecode in seconds for frame extraction
            thumbnail_key: S3 key where thumbnail should be stored
            video_id: ID of the video
            
        Returns:
            True if thumbnail was generated successfully, False otherwise
        """
        video_path = None
        thumbnail_path = None
        
        try:
            logger.debug(f"Generating thumbnail for {video_id} at {timecode}s")
            
            # Download video to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_video:
                video_path = tmp_video.name
                self.s3.download(s3_key, tmp_video)
            
            # Generate thumbnail at specific timecode using ffmpeg
            thumbnail_path = video_path.replace('.mp4', f'_thumb_{timecode}.jpg')
            
            result = subprocess.run(
                [
                    get_ffmpeg_path(),
                    "-ss", str(timecode),  # Seek to timecode
                    "-i", video_path,
                    "-vframes", "1",  # Extract single frame
                    "-vf", f"scale={self.thumbnail_width}:-1",  # Scale to specified width
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
                
                logger.debug(f"Successfully generated thumbnail for {video_id} at {timecode}s")
                return True
            else:
                logger.warning(
                    f"ffmpeg failed to generate thumbnail for {video_id} at {timecode}s: "
                    f"{result.stderr}"
                )
                return False
                
        except Exception as e:
            logger.error(
                f"Error generating thumbnail for {video_id} at {timecode}s: {e}"
            )
            return False
            
        finally:
            # Clean up temp files
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp video file {video_path}: {e}")
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                try:
                    os.remove(thumbnail_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp thumbnail file {thumbnail_path}: {e}")
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0) -> None:
        """
        Shutdown the thumbnail generation service.
        
        Args:
            wait: Whether to wait for pending tasks to complete
            timeout: Maximum time to wait for shutdown (seconds)
        """
        logger.info("Shutting down ThumbnailGenerationService")
        self._executor.shutdown(wait=wait)
        logger.info("ThumbnailGenerationService shutdown complete")
