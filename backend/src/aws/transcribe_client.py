"""AWS Transcribe client wrapper for video transcription.

This module provides functionality to transcribe video audio using AWS Transcribe
and retrieve transcription results with timecodes.
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional
import boto3
from botocore.exceptions import ClientError

from config import Config
from exceptions import AWSServiceError

logger = logging.getLogger(__name__)


class TranscriptionSegment:
    """Represents a transcription segment with timecode and text.
    
    Attributes:
        start_time: Start time in seconds
        end_time: End time in seconds
        text: Transcribed text for this segment
        confidence: Confidence score (0.0-1.0)
    """
    
    def __init__(
        self,
        start_time: float,
        end_time: float,
        text: str,
        confidence: float = 1.0
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.text = text
        self.confidence = confidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "text": self.text,
            "confidence": self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptionSegment":
        """Create from dictionary representation."""
        return cls(
            start_time=data["start_time"],
            end_time=data["end_time"],
            text=data["text"],
            confidence=data.get("confidence", 1.0)
        )


class TranscribeClient:
    """Wrapper for AWS Transcribe client.
    
    Provides methods for starting transcription jobs, checking status,
    and retrieving transcription results with timecodes.
    """
    
    def __init__(self, config: Config):
        """Initialize the Transcribe client.
        
        Args:
            config: Configuration object with AWS region and S3 bucket
        """
        self.config = config
        self.client = boto3.client(
            "transcribe",
            region_name=config.aws_region
        )
        self.s3_client = boto3.client(
            "s3",
            region_name=config.aws_region
        )
        
        logger.info(
            f"Initialized TranscribeClient for region {config.aws_region}"
        )
    
    def start_transcription_job(
        self,
        job_name: str,
        s3_uri: str,
        language_code: str = "en-US",
        output_bucket: Optional[str] = None
    ) -> str:
        """Start a transcription job for a video file.
        
        Args:
            job_name: Unique name for the transcription job
            s3_uri: S3 URI of the video file (s3://bucket/key)
            language_code: Language code (default: en-US)
            output_bucket: S3 bucket for output (default: config bucket)
        
        Returns:
            Job name for tracking
        
        Raises:
            AWSServiceError: If the API call fails
        """
        try:
            output_bucket = output_bucket or self.config.s3_bucket_name
            
            logger.info(f"Starting transcription job: {job_name}")
            
            self.client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={"MediaFileUri": s3_uri},
                MediaFormat="mp4",  # Adjust based on your video format
                LanguageCode=language_code,
                OutputBucketName=output_bucket,
                OutputKey=f"transcriptions/{job_name}.json",
                Settings={
                    "ShowSpeakerLabels": False,
                    "MaxSpeakerLabels": 2
                },
                Subtitles={
                    "Formats": ["vtt", "srt"]
                }
            )
            
            logger.info(f"Started transcription job: {job_name}")
            return job_name
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            
            if error_code == "ConflictException":
                logger.warning(f"Transcription job already exists: {job_name}")
                return job_name
            
            logger.error(f"Transcribe API error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to start transcription job: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error starting transcription: {e}")
            raise AWSServiceError(
                f"Failed to start transcription job: {str(e)}"
            ) from e
    
    def get_transcription_job_status(self, job_name: str) -> Dict[str, Any]:
        """Get the status of a transcription job.
        
        Args:
            job_name: Name of the transcription job
        
        Returns:
            Dictionary containing:
                - status: Job status (IN_PROGRESS, COMPLETED, FAILED)
                - transcript_file_uri: S3 URI of transcript (if completed)
                - failure_reason: Error message (if failed)
        
        Raises:
            AWSServiceError: If the API call fails
        """
        try:
            response = self.client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            
            job = response["TranscriptionJob"]
            status_info = {
                "status": job["TranscriptionJobStatus"],
                "transcript_file_uri": None,
                "failure_reason": None
            }
            
            if job["TranscriptionJobStatus"] == "COMPLETED":
                status_info["transcript_file_uri"] = (
                    job["Transcript"]["TranscriptFileUri"]
                )
            elif job["TranscriptionJobStatus"] == "FAILED":
                status_info["failure_reason"] = job.get("FailureReason")
            
            return status_info
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Transcribe API error ({error_code}): {error_message}")
            raise AWSServiceError(
                f"Failed to get transcription job status: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error getting job status: {e}")
            raise AWSServiceError(
                f"Failed to get transcription job status: {str(e)}"
            ) from e
    
    def get_transcription_segments(
        self,
        job_name: str,
        max_retries: int = 3
    ) -> List[TranscriptionSegment]:
        """Retrieve transcription segments with timecodes.
        
        Args:
            job_name: Name of the completed transcription job
            max_retries: Maximum number of retries for downloading
        
        Returns:
            List of TranscriptionSegment objects
        
        Raises:
            AWSServiceError: If retrieval fails
        """
        try:
            # Get job status to get transcript URI
            status = self.get_transcription_job_status(job_name)
            
            if status["status"] != "COMPLETED":
                raise AWSServiceError(
                    f"Transcription job not completed. Status: {status['status']}"
                )
            
            transcript_uri = status["transcript_file_uri"]
            if not transcript_uri:
                raise AWSServiceError("No transcript URI found")
            
            # Download transcript from S3
            logger.info(f"Downloading transcript from: {transcript_uri}")
            transcript_data = self._download_transcript(transcript_uri, max_retries)
            
            # Parse segments
            segments = self._parse_transcript_segments(transcript_data)
            
            logger.info(f"Retrieved {len(segments)} transcription segments")
            return segments
            
        except Exception as e:
            logger.error(f"Failed to get transcription segments: {e}")
            raise AWSServiceError(
                f"Failed to get transcription segments: {str(e)}"
            ) from e
    
    def _download_transcript(
        self,
        transcript_uri: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """Download transcript JSON from S3 or HTTPS URI.
        
        Args:
            transcript_uri: URI of the transcript file
            max_retries: Maximum number of retry attempts
        
        Returns:
            Parsed transcript JSON data
        """
        for attempt in range(max_retries):
            try:
                if transcript_uri.startswith("s3://"):
                    # Parse S3 URI
                    parts = transcript_uri[5:].split("/", 1)
                    bucket = parts[0]
                    key = parts[1]
                    
                    # Download from S3
                    response = self.s3_client.get_object(Bucket=bucket, Key=key)
                    content = response["Body"].read().decode("utf-8")
                else:
                    # AWS Transcribe returns HTTPS URLs like:
                    # https://s3.{region}.amazonaws.com/{bucket}/{key}
                    # Parse and use S3 client instead of urllib to avoid SSL issues
                    import re
                    
                    # Try to parse as S3 HTTPS URL
                    s3_https_pattern = r'https://s3[.-]([^.]+)\.amazonaws\.com/([^/]+)/(.+)'
                    match = re.match(s3_https_pattern, transcript_uri)
                    
                    if match:
                        # Extract bucket and key from HTTPS URL
                        region = match.group(1)
                        bucket = match.group(2)
                        key = match.group(3)
                        
                        logger.debug(f"Parsed S3 HTTPS URL: bucket={bucket}, key={key}")
                        
                        # Use S3 client to download (avoids SSL certificate issues)
                        response = self.s3_client.get_object(Bucket=bucket, Key=key)
                        content = response["Body"].read().decode("utf-8")
                    else:
                        # Fallback to urllib with SSL context for other HTTPS URLs
                        import urllib.request
                        import ssl
                        
                        # Create SSL context that doesn't verify certificates
                        # This is needed on macOS where Python may not have proper certificates
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE
                        
                        with urllib.request.urlopen(transcript_uri, context=ssl_context) as response:
                            content = response.read().decode("utf-8")
                
                return json.loads(content)
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Failed to download transcript (attempt {attempt + 1}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    raise
    
    def _parse_transcript_segments(
        self,
        transcript_data: Dict[str, Any]
    ) -> List[TranscriptionSegment]:
        """Parse transcript JSON into segments with timecodes.
        
        Args:
            transcript_data: Parsed transcript JSON
        
        Returns:
            List of TranscriptionSegment objects
        """
        segments = []
        
        # AWS Transcribe format has items with start_time, end_time, and alternatives
        results = transcript_data.get("results", {})
        items = results.get("items", [])
        
        # Group items into segments (by sentence or fixed duration)
        current_segment_text = []
        current_start = None
        current_end = None
        
        for item in items:
            item_type = item.get("type")
            
            # Skip punctuation items without timing
            if item_type == "punctuation":
                if item.get("alternatives"):
                    current_segment_text.append(
                        item["alternatives"][0]["content"]
                    )
                continue
            
            # Get timing and content
            start_time = float(item.get("start_time", 0))
            end_time = float(item.get("end_time", 0))
            
            if not item.get("alternatives"):
                continue
            
            content = item["alternatives"][0]["content"]
            confidence = float(item["alternatives"][0].get("confidence", 1.0))
            
            # Initialize segment
            if current_start is None:
                current_start = start_time
            
            current_end = end_time
            current_segment_text.append(content)
            
            # Create segment every 10 seconds or at sentence end
            if (current_end - current_start >= 10.0 or 
                content.endswith((".", "!", "?"))):
                
                if current_segment_text:
                    segment = TranscriptionSegment(
                        start_time=current_start,
                        end_time=current_end,
                        text=" ".join(current_segment_text),
                        confidence=confidence
                    )
                    segments.append(segment)
                    
                    # Reset for next segment
                    current_segment_text = []
                    current_start = None
                    current_end = None
        
        # Add remaining text as final segment
        if current_segment_text and current_start is not None:
            segment = TranscriptionSegment(
                start_time=current_start,
                end_time=current_end or current_start,
                text=" ".join(current_segment_text),
                confidence=1.0
            )
            segments.append(segment)
        
        return segments
