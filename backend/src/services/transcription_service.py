"""Transcription Service - Manages video transcriptions.

This module handles transcription job lifecycle, storage, and retrieval
of transcription segments matched to video clips.
"""

import json
import logging
from typing import List, Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

from config import Config
from aws.transcribe_client import TranscribeClient, TranscriptionSegment
from exceptions import AWSServiceError

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for managing video transcriptions.
    
    Handles transcription job creation, status tracking, and segment retrieval.
    Stores transcription data in S3 for efficient access during search.
    """
    
    def __init__(self, config: Config):
        """Initialize the transcription service.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.transcribe_client = TranscribeClient(config)
        self.s3_client = boto3.client("s3", region_name=config.aws_region)
        
        logger.info("Initialized TranscriptionService")
    
    def start_transcription(
        self,
        video_id: str,
        s3_uri: str,
        language_code: str = "en-US"
    ) -> str:
        """Start transcription for a video.
        
        Args:
            video_id: ID of the video
            s3_uri: S3 URI of the video file
            language_code: Language code (default: en-US)
        
        Returns:
            Transcription job name
        
        Raises:
            AWSServiceError: If transcription fails to start
        """
        job_name = f"transcription-{video_id}"
        
        logger.info(f"Starting transcription for video {video_id}")
        
        try:
            self.transcribe_client.start_transcription_job(
                job_name=job_name,
                s3_uri=s3_uri,
                language_code=language_code,
                output_bucket=self.config.s3_bucket_name
            )
            
            return job_name
            
        except Exception as e:
            logger.error(f"Failed to start transcription for {video_id}: {e}")
            raise
    
    def get_transcription_status(self, video_id: str) -> Dict[str, Any]:
        """Get transcription job status for a video.
        
        Args:
            video_id: ID of the video
        
        Returns:
            Dictionary with status information
        """
        job_name = f"transcription-{video_id}"
        return self.transcribe_client.get_transcription_job_status(job_name)
    
    def retrieve_and_store_transcription(self, video_id: str) -> List[TranscriptionSegment]:
        """Retrieve transcription segments and store them in S3.
        
        Args:
            video_id: ID of the video
        
        Returns:
            List of transcription segments
        
        Raises:
            AWSServiceError: If retrieval or storage fails
        """
        job_name = f"transcription-{video_id}"
        
        logger.info(f"Retrieving transcription for video {video_id}")
        
        try:
            # Get segments from Transcribe
            segments = self.transcribe_client.get_transcription_segments(job_name)
            
            # Store segments in S3 for quick access
            self._store_segments(video_id, segments)
            
            logger.info(
                f"Stored {len(segments)} transcription segments for video {video_id}"
            )
            
            return segments
            
        except Exception as e:
            logger.error(f"Failed to retrieve transcription for {video_id}: {e}")
            raise
    
    def get_segments_for_clip(
        self,
        video_id: str,
        start_time: float,
        end_time: float
    ) -> Optional[str]:
        """Get transcription text for a specific video clip.
        
        Args:
            video_id: ID of the video
            start_time: Clip start time in seconds
            end_time: Clip end time in seconds
        
        Returns:
            Transcription text for the clip, or None if not available
        """
        try:
            # Load segments from S3
            segments = self._load_segments(video_id)
            
            if not segments:
                return None
            
            # Find segments that overlap with the clip timerange
            matching_segments = []
            for segment in segments:
                # Check if segment overlaps with clip
                if (segment.start_time < end_time and 
                    segment.end_time > start_time):
                    matching_segments.append(segment)
            
            if not matching_segments:
                return None
            
            # Combine text from matching segments
            text = " ".join(seg.text for seg in matching_segments)
            return text.strip()
            
        except Exception as e:
            logger.warning(
                f"Failed to get transcription for clip {video_id} "
                f"[{start_time}-{end_time}]: {e}"
            )
            return None
    
    def _store_segments(
        self,
        video_id: str,
        segments: List[TranscriptionSegment]
    ) -> None:
        """Store transcription segments in S3.
        
        Args:
            video_id: ID of the video
            segments: List of transcription segments
        """
        key = f"transcriptions/segments/{video_id}.json"
        
        # Convert segments to JSON
        data = {
            "video_id": video_id,
            "segments": [seg.to_dict() for seg in segments]
        }
        
        try:
            self.s3_client.put_object(
                Bucket=self.config.s3_bucket_name,
                Key=key,
                Body=json.dumps(data),
                ContentType="application/json"
            )
            
            logger.debug(f"Stored transcription segments at s3://{self.config.s3_bucket_name}/{key}")
            
        except ClientError as e:
            logger.error(f"Failed to store transcription segments: {e}")
            raise AWSServiceError(f"Failed to store transcription segments: {e}") from e
    
    def _load_segments(self, video_id: str) -> Optional[List[TranscriptionSegment]]:
        """Load transcription segments from S3.
        
        Args:
            video_id: ID of the video
        
        Returns:
            List of transcription segments, or None if not found
        """
        key = f"transcriptions/segments/{video_id}.json"
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.config.s3_bucket_name,
                Key=key
            )
            
            data = json.loads(response["Body"].read().decode("utf-8"))
            segments = [
                TranscriptionSegment.from_dict(seg_data)
                for seg_data in data["segments"]
            ]
            
            return segments
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "NoSuchKey":
                logger.debug(f"No transcription found for video {video_id}")
                return None
            
            logger.error(f"Failed to load transcription segments: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse transcription segments: {e}")
            return None
