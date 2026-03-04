"""Video reel generation service for concatenating search result clips.

This module provides functionality to generate video reels from search results
by concatenating video clips with fade transitions using ffmpeg.
"""

import logging
import tempfile
import subprocess
import os
from typing import List

from models.search import VideoClip
from aws.s3_client import S3Client
from config import Config
from utils.ffmpeg import get_ffmpeg_path

logger = logging.getLogger(__name__)


class VideoReelService:
    """Service for generating video reels from search clips.
    
    This service downloads video clips, concatenates them with fade transitions
    using ffmpeg, and uploads the result to S3.
    
    Attributes:
        s3_client: S3Client for downloading and uploading videos
        config: Configuration object
    """
    
    def __init__(self, s3_client: S3Client, config: Config):
        """Initialize the VideoReelService.
        
        Args:
            s3_client: Client for S3 operations
            config: Configuration object
        """
        self.s3 = s3_client
        self.config = config
        logger.info("Initialized VideoReelService")
    
    async def generate_reel(
        self,
        clips: List[VideoClip],
        reel_id: str
    ) -> str:
        """Generate a video reel from search result clips with optimized caching.
        
        This method:
        1. Groups clips by source video to minimize downloads
        2. Downloads each unique source video only once (cached)
        3. Extracts time segments and applies 1-second fade in/out transitions
        4. Concatenates all processed clips into a single video
        5. Uploads the result to S3 in the videos-generated folder
        6. Cleans up all temporary files
        
        Args:
            clips: List of VideoClip objects to concatenate
            reel_id: Unique identifier for the generated reel
        
        Returns:
            S3 key of the generated video reel
        
        Raises:
            ValueError: If clips list is empty
            RuntimeError: If ffmpeg processing fails
        """
        if not clips:
            raise ValueError("Cannot generate reel from empty clips list")
        
        logger.info(f"Generating video reel {reel_id} from {len(clips)} clips")
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Step 1: Group clips by source video and download each unique video once
                video_cache = await self._download_source_videos(clips, temp_dir)
                logger.info(f"Downloaded {len(video_cache)} unique source videos")
                
                # Step 2: Process each clip (extract segment + apply fades)
                processed_clips = []
                for i, clip in enumerate(clips):
                    logger.info(f"Processing clip {i+1}/{len(clips)}: video_id={clip.video_id}, "
                               f"start={clip.start_timecode}s, end={clip.end_timecode}s")
                    clip_path = await self._process_clip_with_cache(
                        clip=clip,
                        clip_index=i,
                        video_cache=video_cache,
                        temp_dir=temp_dir
                    )
                    processed_clips.append(clip_path)
                    logger.info(f"Clip {i+1}/{len(clips)} processed successfully")
                
                logger.info(f"Processed {len(processed_clips)} clips with fade transitions")
                
                # Step 3: Create concat file for ffmpeg
                concat_file = os.path.join(temp_dir, "concat.txt")
                with open(concat_file, 'w') as f:
                    for clip_path in processed_clips:
                        # Verify clip exists before adding to concat file
                        if not os.path.exists(clip_path):
                            raise RuntimeError(f"Processed clip not found: {clip_path}")
                        f.write(f"file '{clip_path}'\n")
                
                logger.info(f"Created concat file with {len(processed_clips)} clips")
                
                # Log concat file contents for debugging
                with open(concat_file, 'r') as f:
                    logger.debug(f"Concat file contents:\n{f.read()}")
                
                # Step 4: Concatenate all clips
                output_path = os.path.join(temp_dir, "reel.mp4")
                self._concatenate_clips(concat_file, output_path)
                
                # Step 5: Upload to S3
                s3_key = f"videos-generated/{reel_id}.mp4"
                with open(output_path, 'rb') as f:
                    self.s3.upload(
                        file_obj=f,
                        key=s3_key,
                        content_type="video/mp4",
                        metadata={"reel_id": reel_id, "clip_count": str(len(clips))}
                    )
                
                logger.info(f"Successfully generated video reel: {s3_key}")
                return s3_key
                
            except Exception as e:
                logger.error(f"Failed to generate video reel: {e}")
                raise
            # Temporary directory and all files are automatically cleaned up here
    
    async def _download_source_videos(
        self,
        clips: List[VideoClip],
        temp_dir: str
    ) -> dict:
        """Download unique source videos and cache them.
        
        Args:
            clips: List of VideoClip objects
            temp_dir: Temporary directory for caching
        
        Returns:
            Dictionary mapping s3_key to local file path
        """
        video_cache = {}
        unique_s3_keys = set()
        
        # Identify unique source videos
        for clip in clips:
            s3_key = clip.metadata.get('s3_key', '')
            if not s3_key:
                raise ValueError(f"No S3 key found in metadata for clip from video {clip.video_id}")
            unique_s3_keys.add(s3_key)
        
        # Download each unique video once
        for s3_key in unique_s3_keys:
            # Create a safe filename from the S3 key
            safe_filename = s3_key.replace('/', '_').replace('\\', '_')
            local_path = os.path.join(temp_dir, f"source_{safe_filename}")
            
            logger.debug(f"Downloading source video from {s3_key}")
            with open(local_path, 'wb') as f:
                self.s3.download(s3_key, f)
            
            video_cache[s3_key] = local_path
            logger.debug(f"Cached source video: {s3_key} -> {local_path}")
        
        return video_cache
    
    async def _process_clip_with_cache(
        self,
        clip: VideoClip,
        clip_index: int,
        video_cache: dict,
        temp_dir: str
    ) -> str:
        """Process a single clip using cached source video with fade transitions.
        
        Uses a two-pass seeking approach for accurate extraction:
        1. Fast seek to approximately 1 second before the target
        2. Accurate seek to the exact timecode
        
        Args:
            clip: VideoClip object
            clip_index: Index of the clip in the sequence
            video_cache: Dictionary mapping s3_key to local file path
            temp_dir: Temporary directory for processing
        
        Returns:
            Path to the processed clip file
        """
        # Get S3 key from metadata
        s3_key = clip.metadata.get('s3_key', '')
        if not s3_key:
            raise ValueError(f"No S3 key found in metadata for clip {clip_index}")
        
        # Get cached source video path
        input_path = video_cache.get(s3_key)
        if not input_path:
            raise RuntimeError(f"Source video not found in cache for clip {clip_index}")
        
        # Process clip: extract segment and add fade transitions
        output_path = os.path.join(temp_dir, f"clip_{clip_index:04d}.mp4")
        
        duration = clip.end_timecode - clip.start_timecode
        fade_duration = min(1.0, duration / 4)  # Fade duration, max 1 second or 25% of duration
        
        # Two-pass seeking for accuracy:
        # 1. Fast seek to ~1 second before target (before -i)
        # 2. Accurate seek to exact position (after -i with -ss)
        fast_seek = max(0, clip.start_timecode - 1.0)  # Seek to 1 second before
        accurate_seek = clip.start_timecode - fast_seek  # Remaining offset
        
        # ffmpeg command to extract segment with fade in/out
        cmd = [
            get_ffmpeg_path(),
            '-ss', str(fast_seek),      # Fast seek (before input)
            '-i', input_path,
            '-ss', str(accurate_seek),  # Accurate seek (after input)
            '-t', str(duration),
            '-vf', f'fade=t=in:st=0:d={fade_duration},fade=t=out:st={duration - fade_duration}:d={fade_duration}',
            '-af', f'afade=t=in:st=0:d={fade_duration},afade=t=out:st={duration - fade_duration}:d={fade_duration}',
            '-c:v', 'libx264',
            '-preset', 'medium',        # Balance speed and quality
            '-crf', '23',               # Quality setting
            '-pix_fmt', 'yuv420p',      # Ensure compatibility
            '-c:a', 'aac',
            '-b:a', '192k',             # Audio bitrate
            '-movflags', '+faststart',  # Enable streaming
            '-y',                       # Overwrite output file
            output_path
        ]
        
        logger.debug(f"Processing clip {clip_index} from cached source: {s3_key}")
        logger.debug(f"Extracting from {clip.start_timecode}s to {clip.end_timecode}s (duration: {duration}s)")
        logger.debug(f"Using two-pass seek: fast={fast_seek}s, accurate={accurate_seek}s")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"ffmpeg error for clip {clip_index}: {result.stderr}")
            raise RuntimeError(f"Failed to process clip {clip_index}: {result.stderr}")
        
        # Verify the output file was created and has content
        if not os.path.exists(output_path):
            raise RuntimeError(f"Output file not created for clip {clip_index}")
        
        file_size = os.path.getsize(output_path)
        if file_size == 0:
            raise RuntimeError(f"Output file is empty for clip {clip_index}")
        
        logger.debug(f"Successfully processed clip {clip_index} (size: {file_size} bytes)")
        return output_path
    
    def _concatenate_clips(self, concat_file: str, output_path: str):
        """Concatenate multiple video clips using ffmpeg with re-encoding.
        
        This method re-encodes the clips during concatenation to ensure
        compatibility and avoid black frames that can occur with stream copying
        when clips have different encoding parameters.
        
        Args:
            concat_file: Path to the concat file listing all clips
            output_path: Path for the output video
        """
        cmd = [
            get_ffmpeg_path(),
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:v', 'libx264',  # Re-encode video
            '-c:a', 'aac',      # Re-encode audio
            '-preset', 'medium', # Balance between speed and quality
            '-crf', '23',       # Constant Rate Factor (quality: 0-51, lower is better)
            '-y',               # Overwrite output file
            output_path
        ]
        
        logger.debug("Concatenating clips with ffmpeg (re-encoding)")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"ffmpeg concatenation error: {result.stderr}")
            raise RuntimeError(f"Failed to concatenate clips: {result.stderr}")
        
        logger.info("Successfully concatenated clips")
    
    def get_reel_url(self, s3_key: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for the video reel.
        
        Args:
            s3_key: S3 key of the video reel
            expiration: URL expiration time in seconds (default: 1 hour)
        
        Returns:
            Presigned URL for streaming the video reel
        """
        return self.s3.generate_presigned_url(s3_key, expiration)
