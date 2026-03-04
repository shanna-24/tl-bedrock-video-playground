"""Video generation service for creating compiled videos from Edit Decision Lists.

This module provides the VideoGenerationService class for generating videos
by splicing together clips from source videos based on an Edit Decision List (EDL).
"""

import logging
import subprocess
import tempfile
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from aws.s3_client import S3Client
from config import Config
from exceptions import AWSServiceError
from utils.ffmpeg import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)


class VideoGenerationService:
    """Handles video generation from Edit Decision Lists using ffmpeg.
    
    This service accepts an Edit Decision List (EDL) that specifies source videos
    in S3 with timecodes, downloads the necessary segments, uses ffmpeg to splice
    them together, and uploads the result to S3.
    
    EDL Format:
    [
        {
            "source_s3_uri": "s3://bucket/path/to/video.mp4",
            "start_time": "00:00:10.500",  # HH:MM:SS.mmm format
            "end_time": "00:00:25.000"
        },
        ...
    ]
    
    Attributes:
        s3: S3Client for accessing and uploading video files
        config: Configuration object
    """
    
    def __init__(self, s3_client: S3Client, config: Config):
        """Initialize the VideoGenerationService.
        
        Args:
            s3_client: Client for S3 API
            config: Configuration object
        """
        self.s3 = s3_client
        self.config = config
        
        # Verify ffmpeg is available
        try:
            subprocess.run(
                [get_ffmpeg_path(), "-version"],
                capture_output=True,
                check=True
            )
            logger.info("VideoGenerationService initialized with ffmpeg available")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"ffmpeg not found or not working: {e}")
            raise RuntimeError(
                "ffmpeg is required for video generation. "
                "Please install ffmpeg: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux)"
            ) from e
    
    async def generate_video_from_edl(
        self,
        edl: List[Dict[str, str]],
        output_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a video from an Edit Decision List.
        
        Args:
            edl: List of video segments with source URIs and timecodes
            output_filename: Optional custom filename (without extension)
        
        Returns:
            Dictionary containing:
                - s3_uri: S3 URI of the generated video
                - s3_key: S3 key of the generated video
                - duration: Duration of the generated video in seconds
                - segment_count: Number of segments spliced together
        
        Raises:
            ValueError: If EDL is invalid or empty
            AWSServiceError: If S3 operations fail
            RuntimeError: If ffmpeg processing fails
        """
        if not edl or not isinstance(edl, list):
            raise ValueError("EDL must be a non-empty list")
        
        # Validate EDL entries
        for i, entry in enumerate(edl):
            if not isinstance(entry, dict):
                raise ValueError(f"EDL entry {i} must be a dictionary")
            if "source_s3_uri" not in entry:
                raise ValueError(f"EDL entry {i} missing 'source_s3_uri'")
            if "start_time" not in entry or "end_time" not in entry:
                raise ValueError(f"EDL entry {i} missing 'start_time' or 'end_time'")
        
        logger.info(f"Generating video from EDL with {len(edl)} segments")
        
        # Generate output filename with timestamp
        if output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_filename = f"generated-{output_filename}_{timestamp}.mp4"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_filename = f"generated-{timestamp}.mp4"
        
        # Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            try:
                # Group segments by source video to avoid duplicate downloads
                source_videos = {}  # Maps S3 URI to local file path
                
                # Download unique source videos
                unique_sources = set(entry["source_s3_uri"] for entry in edl)
                logger.info(f"Downloading {len(unique_sources)} unique source video(s)")
                
                for source_uri in unique_sources:
                    source_file = await self._download_source_video(
                        source_uri=source_uri,
                        temp_path=temp_path
                    )
                    source_videos[source_uri] = source_file
                
                # Process each segment using cached source videos
                segment_files = []
                for i, entry in enumerate(edl):
                    source_file = source_videos[entry["source_s3_uri"]]
                    segment_file = await self._extract_segment(
                        source_file=source_file,
                        start_time=entry["start_time"],
                        end_time=entry["end_time"],
                        segment_index=i,
                        temp_path=temp_path
                    )
                    segment_files.append(segment_file)
                
                # Concatenate segments using ffmpeg
                output_file = temp_path / final_filename
                await self._concatenate_segments(
                    segment_files=segment_files,
                    output_file=output_file
                )
                
                # Get video duration
                duration = self._get_video_duration(output_file)
                
                # Generate thumbnail from the start of the video
                thumbnail_key = await self._generate_thumbnail(
                    video_file=output_file,
                    output_filename=final_filename
                )
                
                # Upload to S3
                s3_key = f"videos-generated/{final_filename}"
                await self._upload_to_s3(
                    local_file=output_file,
                    s3_key=s3_key
                )
                
                s3_uri = f"s3://{self.config.s3_bucket_name}/{s3_key}"
                
                # Generate presigned URLs for video and thumbnail
                video_stream_url = self.s3.generate_presigned_url(
                    key=s3_key,
                    expiration=3600
                )
                
                if thumbnail_key:
                    thumbnail_url = self.s3.generate_presigned_url(
                        key=thumbnail_key,
                        expiration=3600
                    )
                    logger.info(f"Generated thumbnail presigned URL for key: {thumbnail_key}")
                    logger.info(f"Thumbnail URL (first 150 chars): {thumbnail_url[:150] if thumbnail_url else 'None'}...")
                else:
                    thumbnail_url = None
                    logger.warning("No thumbnail generated - thumbnail_url will be None")
                
                logger.info(
                    f"Successfully generated video: {s3_uri} "
                    f"({len(edl)} segments from {len(unique_sources)} source(s), {duration:.2f}s)"
                )
                
                result = {
                    "s3_uri": s3_uri,
                    "s3_key": s3_key,
                    "video_stream_url": video_stream_url,
                    "duration": duration,
                    "segment_count": len(edl),
                    "generated_at": datetime.now().isoformat(),
                    "thumbnail_url": thumbnail_url
                }
                
                logger.info(f"Returning result with thumbnail_url: {result.get('thumbnail_url') is not None}")
                
                return result
                
            except Exception as e:
                logger.error(f"Failed to generate video: {e}")
                raise
    
    async def _download_source_video(
        self,
        source_uri: str,
        temp_path: Path
    ) -> Path:
        """Download a source video from S3.
        
        Args:
            source_uri: S3 URI of the source video
            temp_path: Temporary directory path
        
        Returns:
            Path to the downloaded video file
        
        Raises:
            ValueError: If S3 URI is invalid
            AWSServiceError: If download fails
        """
        # Parse S3 URI
        if not source_uri.startswith("s3://"):
            raise ValueError(f"Invalid S3 URI: {source_uri}")
        
        s3_key = source_uri.replace(f"s3://{self.config.s3_bucket_name}/", "")
        
        logger.info(f"Downloading source video from S3: bucket={self.config.s3_bucket_name}, key={s3_key}")
        
        # Verify the object exists before attempting download
        if not self.s3.object_exists(s3_key):
            # Try to find the video with a different filename in the same directory
            logger.warning(f"Video not found at exact path: {s3_key}")
            
            # Extract directory path (everything except the filename)
            key_parts = s3_key.rsplit("/", 1)
            if len(key_parts) == 2:
                directory = key_parts[0]
                original_filename = key_parts[1]
                
                logger.info(f"Searching for video in directory: {directory}/")
                
                # List objects in the directory to find potential matches
                try:
                    import boto3
                    s3_client = boto3.client('s3')
                    response = s3_client.list_objects_v2(
                        Bucket=self.config.s3_bucket_name,
                        Prefix=directory + "/",
                        MaxKeys=100
                    )
                    
                    if 'Contents' in response:
                        # Look for video files in the directory
                        video_extensions = ['.mp4', '.mov', '.avi', '.mkv']
                        found_videos = [
                            obj['Key'] for obj in response['Contents']
                            if any(obj['Key'].lower().endswith(ext) for ext in video_extensions)
                        ]
                        
                        if found_videos:
                            if len(found_videos) == 1:
                                # Found exactly one video, use it
                                s3_key = found_videos[0]
                                logger.info(
                                    f"Found alternative video file: {s3_key} "
                                    f"(original: {original_filename})"
                                )
                            else:
                                # Multiple videos found, log them
                                logger.warning(
                                    f"Found {len(found_videos)} videos in directory: {found_videos}. "
                                    f"Cannot determine which one to use."
                                )
                                raise AWSServiceError(
                                    f"Video not found in S3: {source_uri}. "
                                    f"Found {len(found_videos)} videos in the same directory, "
                                    f"but cannot determine which one is correct. "
                                    f"The video filename in the EDL may be incorrect."
                                )
                        else:
                            raise AWSServiceError(
                                f"Video not found in S3: {source_uri}. "
                                f"No video files found in directory {directory}/. "
                                f"The video may have been deleted."
                            )
                except Exception as e:
                    if isinstance(e, AWSServiceError):
                        raise
                    logger.error(f"Failed to search for alternative video: {e}")
                    raise AWSServiceError(
                        f"Video not found in S3: {source_uri}. "
                        f"The video may have been deleted or the S3 URI may be incorrect."
                    ) from e
            else:
                raise AWSServiceError(
                    f"Video not found in S3: {source_uri}. "
                    f"The video may have been deleted or the S3 URI may be incorrect."
                )
        
        # Create a unique filename based on the S3 key hash to avoid collisions
        import hashlib
        uri_hash = hashlib.md5(s3_key.encode()).hexdigest()[:8]
        source_file = temp_path / f"source_{uri_hash}.mp4"
        
        # Download source video
        try:
            with open(source_file, 'wb') as f:
                self.s3.download(
                    key=s3_key,
                    file_obj=f
                )
        except Exception as e:
            raise AWSServiceError(
                f"Failed to download video from S3: s3://{self.config.s3_bucket_name}/{s3_key}. Error: {str(e)}"
            ) from e
        
        logger.info(f"Downloaded source video to {source_file}")
        return source_file
    
    async def _extract_segment(
        self,
        source_file: Path,
        start_time: str,
        end_time: str,
        segment_index: int,
        temp_path: Path
    ) -> Path:
        """Extract a segment from a source video using ffmpeg.
        
        Args:
            source_file: Path to the source video file
            start_time: Start time in HH:MM:SS.mmm format
            end_time: End time in HH:MM:SS.mmm format
            segment_index: Index of this segment in the EDL
            temp_path: Temporary directory path
        
        Returns:
            Path to the extracted segment file
        
        Raises:
            RuntimeError: If ffmpeg extraction fails
        """
        logger.debug(
            f"Extracting segment {segment_index}: {source_file.name} "
            f"[{start_time} - {end_time}]"
        )
        
        # Extract segment using ffmpeg
        segment_file = temp_path / f"segment_{segment_index}.mp4"
        
        try:
            # Use ffmpeg to extract the segment
            # -ss: start time, -to: end time
            # -c:v libx264: Re-encode video for accurate cuts
            # -c:a aac: Re-encode audio
            cmd = [
                get_ffmpeg_path(),
                "-i", str(source_file),
                "-ss", start_time,
                "-to", end_time,
                "-c:v", "libx264",  # Re-encode video for accurate cuts
                "-c:a", "aac",      # Re-encode audio
                "-y",               # Overwrite output file
                str(segment_file)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.debug(f"Extracted segment {segment_index} successfully")
            
            return segment_file
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg extraction failed: {e.stderr}")
            raise RuntimeError(
                f"Failed to extract segment {segment_index}: {e.stderr}"
            ) from e
    
    async def _concatenate_segments(
        self,
        segment_files: List[Path],
        output_file: Path
    ) -> None:
        """Concatenate video segments into a single output file.
        
        Args:
            segment_files: List of segment file paths
            output_file: Output file path
        
        Raises:
            RuntimeError: If ffmpeg concatenation fails
        """
        logger.debug(f"Concatenating {len(segment_files)} segments")
        
        # Create concat file for ffmpeg
        concat_file = output_file.parent / "concat_list.txt"
        with open(concat_file, "w") as f:
            for segment_file in segment_files:
                # ffmpeg concat requires relative or absolute paths with proper escaping
                f.write(f"file '{segment_file.absolute()}'\n")
        
        try:
            # Use ffmpeg concat demuxer
            cmd = [
                get_ffmpeg_path(),
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",  # Copy streams without re-encoding (fast)
                "-y",          # Overwrite output file
                str(output_file)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            logger.debug("Concatenation completed successfully")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg concatenation failed: {e.stderr}")
            raise RuntimeError(
                f"Failed to concatenate segments: {e.stderr}"
            ) from e
    
    def _get_video_duration(self, video_file: Path) -> float:
        """Get the duration of a video file in seconds.
        
        Args:
            video_file: Path to video file
        
        Returns:
            Duration in seconds
        
        Raises:
            RuntimeError: If ffprobe fails
        """
        try:
            cmd = [
                get_ffprobe_path(),
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_file)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            duration = float(result.stdout.strip())
            return duration
            
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Failed to get video duration: {e}")
            raise RuntimeError(f"Failed to get video duration: {e}") from e
    
    async def _generate_thumbnail(
        self,
        video_file: Path,
        output_filename: str
    ) -> Optional[str]:
        """Generate a thumbnail from the start of the generated video.
        
        Args:
            video_file: Path to the generated video file
            output_filename: Base filename for the thumbnail
        
        Returns:
            S3 key of the uploaded thumbnail, or None if generation fails
        """
        thumbnail_path = None
        
        try:
            logger.info(f"Starting thumbnail generation for {output_filename}")
            
            # Verify video file exists
            if not video_file.exists():
                logger.error(f"Video file does not exist: {video_file}")
                return None
            
            # Generate thumbnail at 0.5 seconds (to avoid black frames at start)
            thumbnail_path = video_file.parent / f"{output_filename.replace('.mp4', '_thumb.jpg')}"
            
            logger.debug(f"Extracting thumbnail frame to {thumbnail_path}")
            
            result = subprocess.run(
                [
                    get_ffmpeg_path(),
                    "-ss", "0.5",  # Seek to 0.5 seconds
                    "-i", str(video_file),
                    "-vframes", "1",  # Extract single frame
                    "-vf", "scale=640:-1",  # Scale to 640px width
                    "-y",  # Overwrite output file
                    str(thumbnail_path)
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            # Verify thumbnail was created
            if not thumbnail_path.exists():
                logger.error(f"Thumbnail file was not created: {thumbnail_path}")
                logger.error(f"ffmpeg stdout: {result.stdout}")
                logger.error(f"ffmpeg stderr: {result.stderr}")
                return None
            
            logger.info(f"Thumbnail extracted successfully, size: {thumbnail_path.stat().st_size} bytes")
            
            # Upload thumbnail to S3
            thumbnail_key = f"thumbnails/generated/{output_filename.replace('.mp4', '.jpg')}"
            
            logger.debug(f"Uploading thumbnail to S3: {thumbnail_key}")
            
            with open(thumbnail_path, 'rb') as thumb_file:
                self.s3.upload(
                    file_obj=thumb_file,
                    key=thumbnail_key,
                    content_type='image/jpeg'
                )
            
            logger.info(f"Successfully generated and uploaded thumbnail: {thumbnail_key}")
            return thumbnail_key
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg failed to generate thumbnail: {e.stderr}")
            logger.error(f"ffmpeg stdout: {e.stdout}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate thumbnail: {e}", exc_info=True)
            return None
        finally:
            # Clean up temp thumbnail file
            if thumbnail_path and thumbnail_path.exists():
                try:
                    thumbnail_path.unlink()
                    logger.debug(f"Cleaned up temp thumbnail file: {thumbnail_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temp thumbnail file: {e}")
    
    async def _upload_to_s3(self, local_file: Path, s3_key: str) -> None:
        """Upload generated video to S3.
        
        Args:
            local_file: Path to local video file
            s3_key: S3 key for upload
        
        Raises:
            AWSServiceError: If upload fails
        """
        try:
            logger.debug(f"Uploading generated video to s3://{self.config.s3_bucket_name}/{s3_key}")
            
            with open(local_file, 'rb') as f:
                self.s3.upload(
                    file_obj=f,
                    key=s3_key,
                    content_type="video/mp4"
                )
            
            logger.info(f"Successfully uploaded video to S3: {s3_key}")
            
        except Exception as e:
            logger.error(f"Failed to upload video to S3: {e}")
            raise AWSServiceError(f"Failed to upload video: {str(e)}") from e
