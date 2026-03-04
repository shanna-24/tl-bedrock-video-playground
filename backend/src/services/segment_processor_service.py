"""
Segment Processor Service - Unified processing of video segments.

This module provides a unified service for processing video segments after indexing.
It handles both transcription and thumbnail generation in a single pass to minimize
video downloads and maximize efficiency.
"""

import logging
import tempfile
import os
import subprocess
import shutil
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.exceptions import ClientError

from config import Config
from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from aws.transcribe_client import TranscriptionSegment
from services.embedding_retriever import EmbeddingData
from exceptions import AWSServiceError
from utils.ffmpeg import get_ffmpeg_path

logger = logging.getLogger(__name__)


class SegmentProcessorService:
    """
    Unified service for processing video segments.
    
    This service processes all segments of a video in a single pass:
    - Downloads video once
    - For each segment:
      * Extracts segment with ffmpeg
      * Generates thumbnail from first frame
      * Transcribes segment with Pegasus
      * Uploads results to S3
    
    This approach is much more efficient than separate processing.
    """
    
    def __init__(
        self,
        config: Config,
        bedrock_client: BedrockClient,
        s3_client: S3Client,
        max_concurrent_segments: int = 3,
        thumbnail_width: int = 640
    ):
        """
        Initialize the segment processor service.
        
        Args:
            config: Configuration object
            bedrock_client: Bedrock client for Pegasus transcription
            s3_client: S3 client for uploads/downloads
            max_concurrent_segments: Maximum segments to process concurrently
            thumbnail_width: Width of generated thumbnails in pixels
        """
        self.config = config
        self.bedrock_client = bedrock_client
        self.s3_client = s3_client
        self.s3_boto_client = boto3.client("s3", region_name=config.aws_region)
        self.max_concurrent_segments = max_concurrent_segments
        self.thumbnail_width = thumbnail_width
        
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent_segments,
            thread_name_prefix="SegmentProcessor"
        )
        
        logger.info(
            f"Initialized SegmentProcessorService "
            f"(max_concurrent={max_concurrent_segments}, thumbnail_width={thumbnail_width}px)"
        )
    
    def process_video_segments(
        self,
        embeddings: List[EmbeddingData],
        video_id: str,
        index_id: str,
        s3_uri: str,
        video_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process all segments of a video in a single pass.
        
        Downloads the video once (or uses provided path), then processes each segment to:
        - Generate thumbnail
        - Generate transcription
        
        Args:
            embeddings: List of embedding data containing segment timecodes
            video_id: ID of the video
            index_id: ID of the index
            s3_uri: S3 URI of the video file
            video_path: Optional path to already-downloaded video file (optimization)
            
        Returns:
            Dictionary with processing statistics
        """
        if not embeddings:
            logger.warning(f"No embeddings provided for segment processing (video_id={video_id})")
            return {"segments_processed": 0, "thumbnails_generated": 0, "transcriptions_generated": 0}
        
        logger.info(
            f"Starting unified segment processing for {len(embeddings)} segments "
            f"(video_id={video_id}, index_id={index_id})"
        )
        
        # Filter and prepare segments
        segments = self._prepare_segments(embeddings)
        
        logger.info(
            f"Processing {len(segments)} unique segments for video {video_id}"
        )
        
        # Download video once (or use provided path)
        temp_dir = None
        local_video_path = video_path
        video_was_provided = video_path is not None
        
        try:
            if not local_video_path:
                # Create temp directory and download video
                temp_dir = tempfile.mkdtemp(prefix='segment_processor_')
                local_video_path = os.path.join(temp_dir, 'video.mp4')
                
                logger.info(f"Downloading video from {s3_uri}")
                self._download_video_from_s3(s3_uri, local_video_path)
            else:
                logger.info(f"Using provided video path: {local_video_path}")
                # Create temp directory for segment processing
                temp_dir = tempfile.mkdtemp(prefix='segment_processor_')
            
            # Process segments sequentially (could be parallelized in future)
            transcription_segments = []
            thumbnails_generated = 0
            transcriptions_generated = 0
            
            for i, segment in enumerate(segments):
                logger.info(
                    f"Processing segment {i+1}/{len(segments)}: "
                    f"{segment['start_sec']:.1f}s - {segment['end_sec']:.1f}s"
                )
                
                try:
                    result = self._process_single_segment(
                        video_path=local_video_path,
                        segment=segment,
                        segment_index=i,
                        video_id=video_id,
                        index_id=index_id,
                        temp_dir=temp_dir
                    )
                    
                    if result['thumbnail_generated']:
                        thumbnails_generated += 1
                    
                    if result['transcription']:
                        transcription_segments.append(result['transcription'])
                        transcriptions_generated += 1
                        
                except Exception as e:
                    logger.error(f"Failed to process segment {i}: {e}")
                    # Add empty transcription segment on failure
                    transcription_segments.append(TranscriptionSegment(
                        start_time=segment['start_sec'],
                        end_time=segment['end_sec'],
                        text="[Processing failed]",
                        confidence=0.0
                    ))
            
            # Store transcription segments
            if transcription_segments:
                self._store_transcription_segments(video_id, transcription_segments)
            
            logger.info(
                f"Segment processing completed for video {video_id}: "
                f"{thumbnails_generated} thumbnails, {transcriptions_generated} transcriptions"
            )
            
            return {
                "segments_processed": len(segments),
                "thumbnails_generated": thumbnails_generated,
                "transcriptions_generated": transcriptions_generated
            }
            
        except Exception as e:
            logger.error(f"Failed to process video segments: {e}")
            raise AWSServiceError(f"Segment processing failed: {e}") from e
            
        finally:
            # Clean up temp directory (but not the provided video file)
            if temp_dir and os.path.exists(temp_dir):
                try:
                    # If video was provided, don't delete it
                    if video_was_provided and local_video_path and os.path.exists(local_video_path):
                        # Move the video file out of temp dir before deleting
                        # Actually, if it was provided, it's not in our temp dir anyway
                        pass
                    
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
    
    def _prepare_segments(
        self,
        embeddings: List[EmbeddingData]
    ) -> List[Dict[str, float]]:
        """
        Prepare segments from embeddings, removing duplicates.
        
        Args:
            embeddings: List of embedding data
            
        Returns:
            List of unique segments with start_sec and end_sec
        """
        # Extract unique timecodes (rounded to nearest second for thumbnails)
        segments_by_start = {}
        
        for emb in embeddings:
            start = round(emb.start_sec)
            end = emb.end_sec
            duration = end - start
            
            # Keep the shortest segment for each start time
            if start not in segments_by_start or duration < (segments_by_start[start]['end_sec'] - start):
                segments_by_start[start] = {
                    'start_sec': start,
                    'end_sec': end
                }
        
        segments = sorted(segments_by_start.values(), key=lambda x: x['start_sec'])
        
        logger.info(
            f"Prepared {len(segments)} unique segments "
            f"(from {len(embeddings)} embeddings)"
        )
        
        return segments
    
    def _process_single_segment(
        self,
        video_path: str,
        segment: Dict[str, float],
        segment_index: int,
        video_id: str,
        index_id: str,
        temp_dir: str
    ) -> Dict[str, Any]:
        """
        Process a single segment: extract, generate thumbnail, transcribe.
        
        Args:
            video_path: Path to downloaded video file
            segment: Segment dict with start_sec and end_sec
            segment_index: Index of segment in list
            video_id: ID of the video
            index_id: ID of the index
            temp_dir: Temporary directory for processing
            
        Returns:
            Dictionary with processing results
        """
        start_time = segment['start_sec']
        end_time = segment['end_sec']
        duration = end_time - start_time
        
        # Paths for temp files
        segment_path = os.path.join(temp_dir, f'segment_{segment_index}.mp4')
        thumbnail_path = os.path.join(temp_dir, f'thumbnail_{segment_index}.jpg')
        
        result = {
            'thumbnail_generated': False,
            'transcription': None
        }
        
        try:
            # Extract segment with ffmpeg
            self._extract_video_segment(
                video_path,
                segment_path,
                start_time,
                duration
            )
            
            # Generate thumbnail from first frame of segment
            thumbnail_key = f"thumbnails/{index_id}/{video_id}/clip_{int(start_time)}.jpg"
            
            # Check if thumbnail already exists
            if not self.s3_client.object_exists(thumbnail_key):
                self._generate_thumbnail_from_segment(
                    segment_path,
                    thumbnail_path
                )
                
                # Upload thumbnail to S3
                with open(thumbnail_path, 'rb') as thumb_file:
                    self.s3_client.upload(
                        file_obj=thumb_file,
                        key=thumbnail_key,
                        content_type='image/jpeg',
                        metadata={
                            'video_id': video_id,
                            'timecode': str(int(start_time))
                        }
                    )
                
                result['thumbnail_generated'] = True
                logger.debug(f"  Generated thumbnail at {start_time}s")
            else:
                logger.debug(f"  Thumbnail already exists at {start_time}s")
            
            # Upload segment to S3 for transcription
            segment_s3_key = f"temp/transcription/{video_id}/segment_{segment_index}.mp4"
            segment_s3_uri = self._upload_segment_to_s3(segment_path, segment_s3_key)
            
            # Transcribe segment with Pegasus
            transcription_text = self._transcribe_segment(segment_s3_uri)
            
            # Clean up temp segment from S3
            self._delete_temp_segment(segment_s3_key)
            
            # Create transcription segment
            result['transcription'] = TranscriptionSegment(
                start_time=start_time,
                end_time=end_time,
                text=transcription_text,
                confidence=0.95
            )
            
            logger.debug(f"  Transcribed: {transcription_text[:60]}...")
            
        except Exception as e:
            logger.error(f"Failed to process segment at {start_time}s: {e}")
            # Return partial results
            result['transcription'] = TranscriptionSegment(
                start_time=start_time,
                end_time=end_time,
                text="[Processing failed]",
                confidence=0.0
            )
        
        finally:
            # Clean up local temp files
            for path in [segment_path, thumbnail_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception as e:
                        logger.warning(f"Failed to remove temp file {path}: {e}")
        
        return result
    
    def _download_video_from_s3(self, s3_uri: str, local_path: str) -> None:
        """Download video from S3 to local file."""
        if not s3_uri.startswith('s3://'):
            raise ValueError(f"Invalid S3 URI: {s3_uri}")
        
        parts = s3_uri[5:].split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        
        self.s3_boto_client.download_file(bucket, key, local_path)
        logger.debug(f"Downloaded {s3_uri} to {local_path}")
    
    def _extract_video_segment(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float
    ) -> None:
        """Extract a segment from video using ffmpeg."""
        cmd = [
            get_ffmpeg_path(),
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(duration),
            '-c', 'copy',
            '-y',
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg segment extraction failed: {result.stderr}")
    
    def _generate_thumbnail_from_segment(
        self,
        segment_path: str,
        thumbnail_path: str
    ) -> None:
        """Generate thumbnail from first frame of segment using ffmpeg."""
        cmd = [
            get_ffmpeg_path(),
            '-i', segment_path,
            '-vframes', '1',
            '-vf', f'scale={self.thumbnail_width}:-1',
            '-y',
            thumbnail_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg thumbnail generation failed: {result.stderr}")
    
    def _upload_segment_to_s3(self, local_path: str, s3_key: str) -> str:
        """Upload video segment to S3."""
        with open(local_path, 'rb') as f:
            self.s3_boto_client.put_object(
                Bucket=self.config.s3_bucket_name,
                Key=s3_key,
                Body=f,
                ContentType='video/mp4'
            )
        
        s3_uri = f"s3://{self.config.s3_bucket_name}/{s3_key}"
        return s3_uri
    
    def _delete_temp_segment(self, s3_key: str) -> None:
        """Delete temporary segment from S3."""
        try:
            self.s3_boto_client.delete_object(
                Bucket=self.config.s3_bucket_name,
                Key=s3_key
            )
        except Exception as e:
            logger.warning(f"Failed to delete temp segment {s3_key}: {e}")
    
    def _transcribe_segment(self, segment_s3_uri: str) -> str:
        """Transcribe a video segment using Pegasus."""
        prompt = """Transcribe all spoken words in this video clip.

Provide only the transcription text, nothing else.
Do NOT include timestamps, labels, or any other formatting.
Just the spoken words."""

        try:
            response = self.bedrock_client.invoke_pegasus_analysis(
                s3_uri=segment_s3_uri,
                prompt=prompt,
                temperature=0.1,
                max_output_tokens=1024
            )
            
            text = response.get("message", "").strip()
            return text if text else ""
            
        except Exception as e:
            logger.error(f"Failed to transcribe segment: {e}")
            return "[Transcription failed]"
    
    def _store_transcription_segments(
        self,
        video_id: str,
        segments: List[TranscriptionSegment]
    ) -> None:
        """Store transcription segments in S3."""
        import json
        
        key = f"transcriptions/segments/{video_id}.json"
        
        data = {
            "video_id": video_id,
            "source": "pegasus",
            "segments": [seg.to_dict() for seg in segments]
        }
        
        try:
            self.s3_boto_client.put_object(
                Bucket=self.config.s3_bucket_name,
                Key=key,
                Body=json.dumps(data, indent=2),
                ContentType="application/json"
            )
            
            logger.debug(f"Stored transcription segments at s3://{self.config.s3_bucket_name}/{key}")
            
        except ClientError as e:
            logger.error(f"Failed to store transcription segments: {e}")
            raise AWSServiceError(f"Failed to store transcription segments: {e}") from e
    
    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the segment processor service."""
        logger.info("Shutting down SegmentProcessorService")
        self._executor.shutdown(wait=wait)
        logger.info("SegmentProcessorService shutdown complete")
