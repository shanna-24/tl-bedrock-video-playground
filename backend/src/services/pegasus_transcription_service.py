"""Pegasus Transcription Service - Manages video transcriptions using Pegasus.

This module handles transcription using AWS Bedrock's Pegasus model instead of
AWS Transcribe. It provides the same interface as TranscriptionService but uses
Pegasus for generating transcriptions.

Uses ffmpeg to split videos into segments for accurate per-segment transcription.
"""

import json
import logging
import re
import tempfile
import os
import subprocess
from typing import List, Dict, Any, Optional
import boto3
from botocore.exceptions import ClientError

from config import Config
from aws.bedrock_client import BedrockClient
from aws.transcribe_client import TranscriptionSegment
from exceptions import AWSServiceError
from utils.ffmpeg import get_ffmpeg_path

logger = logging.getLogger(__name__)


class PegasusTranscriptionService:
    """Service for managing video transcriptions using Pegasus.
    
    Uses Pegasus model to generate transcriptions with timestamps.
    Stores transcription data in S3 for efficient access during search.
    """
    
    def __init__(self, config: Config, bedrock_client: Optional[BedrockClient] = None):
        """Initialize the Pegasus transcription service.
        
        Args:
            config: Configuration object
            bedrock_client: Optional BedrockClient instance (creates new if not provided)
        """
        self.config = config
        self.bedrock_client = bedrock_client or BedrockClient(config)
        self.s3_client = boto3.client("s3", region_name=config.aws_region)
        
        logger.info("Initialized PegasusTranscriptionService")
    
    def start_transcription(
        self,
        video_id: str,
        s3_uri: str,
        language_code: str = "en-US",
        embedding_segments: Optional[List[Dict[str, float]]] = None
    ) -> str:
        """Start transcription for a video using Pegasus.
        
        This method immediately generates the transcription using Pegasus
        and stores it, rather than starting an async job.
        
        If embedding_segments are provided, transcription will be aligned
        with those segments. Otherwise, Pegasus will determine its own segments.
        
        Args:
            video_id: ID of the video
            s3_uri: S3 URI of the video file
            language_code: Language code (default: en-US, currently ignored)
            embedding_segments: Optional list of time segments from Marengo embeddings
                               Each dict should have 'start_sec' and 'end_sec' keys
        
        Returns:
            Job identifier (video_id for compatibility)
        
        Raises:
            AWSServiceError: If transcription fails
        """
        logger.info(f"Starting Pegasus transcription for video {video_id}")
        
        if embedding_segments:
            logger.info(
                f"Aligning transcription with {len(embedding_segments)} "
                f"Marengo embedding segments"
            )
        
        try:
            # Generate transcription using Pegasus
            segments = self._generate_transcription(
                video_id, 
                s3_uri,
                embedding_segments=embedding_segments
            )
            
            # Store segments immediately
            self._store_segments(video_id, segments)
            
            logger.info(
                f"Completed Pegasus transcription for {video_id}: "
                f"{len(segments)} segments"
            )
            
            # Return video_id as job identifier for compatibility
            return f"pegasus-{video_id}"
            
        except Exception as e:
            logger.error(f"Failed to generate transcription for {video_id}: {e}")
            raise AWSServiceError(f"Failed to generate transcription: {e}") from e
    
    def get_transcription_status(self, video_id: str) -> Dict[str, Any]:
        """Get transcription status for a video.
        
        Since Pegasus transcription is synchronous, this checks if
        the segments file exists in S3.
        
        Args:
            video_id: ID of the video
        
        Returns:
            Dictionary with status information
        """
        key = f"transcriptions/segments/{video_id}.json"
        
        try:
            self.s3_client.head_object(
                Bucket=self.config.s3_bucket_name,
                Key=key
            )
            return {
                "status": "COMPLETED",
                "job_name": f"pegasus-{video_id}"
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "404" or error_code == "NoSuchKey":
                return {
                    "status": "NOT_FOUND",
                    "job_name": f"pegasus-{video_id}"
                }
            raise
    
    def retrieve_and_store_transcription(self, video_id: str) -> List[TranscriptionSegment]:
        """Retrieve transcription segments from S3.
        
        For Pegasus, transcription is generated synchronously during start_transcription,
        so this method just loads the existing segments.
        
        Args:
            video_id: ID of the video
        
        Returns:
            List of transcription segments
        
        Raises:
            AWSServiceError: If retrieval fails
        """
        logger.info(f"Retrieving transcription for video {video_id}")
        
        segments = self._load_segments(video_id)
        
        if segments is None:
            raise AWSServiceError(
                f"No transcription found for video {video_id}. "
                "Transcription may not have been generated yet."
            )
        
        return segments
    
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
            # Skip segments longer than 15 seconds (these are likely full-video segments)
            matching_segments = []
            for segment in segments:
                # Skip empty segments
                if not segment.text or not segment.text.strip():
                    continue
                
                # Skip segments that are too long (likely full-video segments)
                segment_duration = segment.end_time - segment.start_time
                if segment_duration > 15.0:
                    continue
                
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
    
    def _generate_transcription(
            self,
            video_id: str,
            s3_uri: str,
            embedding_segments: Optional[List[Dict[str, float]]] = None
        ) -> List[TranscriptionSegment]:
            """Generate transcription using Pegasus model.

            Uses segment-by-segment approach for accurate timestamps:
            - Extracts each video segment with ffmpeg
            - Transcribes each segment individually with Pegasus
            - Uses known segment boundaries as timestamps (no fabrication)

            Args:
                video_id: ID of the video
                s3_uri: S3 URI of the video file
                embedding_segments: Optional list of time segments from Marengo

            Returns:
                List of transcription segments with timestamps
            """
            if embedding_segments:
                # Filter and prepare segments
                filtered_segments = self._filter_duplicate_segments(embedding_segments)

                logger.info(
                    f"Using segment-by-segment transcription for {len(filtered_segments)} segments"
                )

                # Always use segment-by-segment approach for accurate timestamps
                return self._generate_aligned_transcription(
                    video_id,
                    s3_uri,
                    filtered_segments
                )
            else:
                # Generate transcription with Pegasus-determined segments
                return self._generate_unaligned_transcription(video_id, s3_uri)
    
    def _generate_aligned_transcription(
        self,
        video_id: str,
        s3_uri: str,
        embedding_segments: List[Dict[str, float]]
    ) -> List[TranscriptionSegment]:
        """Generate transcription aligned with Marengo embedding segments.
        
        Uses ffmpeg to split the video into segments, then transcribes each
        segment individually with Pegasus for perfect alignment.
        
        Args:
            video_id: ID of the video
            s3_uri: S3 URI of the video file
            embedding_segments: List of time segments from Marengo (already filtered)
        
        Returns:
            List of transcription segments aligned with embeddings
        """
        logger.info(
            f"Generating segment-by-segment transcription for {len(embedding_segments)} segments"
        )
        
        # Download full video to temp file
        temp_video_path = None
        temp_dir = None
        
        try:
            # Create temp directory for video processing
            temp_dir = tempfile.mkdtemp(prefix='pegasus_transcription_')
            temp_video_path = os.path.join(temp_dir, 'video.mp4')
            
            logger.info(f"Downloading video from {s3_uri}")
            self._download_video_from_s3(s3_uri, temp_video_path)
            
            # Process each segment
            all_segments = []
            
            for i, seg in enumerate(embedding_segments):
                start_time = seg['start_sec']
                end_time = seg['end_sec']
                duration = end_time - start_time
                
                logger.info(
                    f"Processing segment {i+1}/{len(embedding_segments)}: "
                    f"{start_time:.1f}s - {end_time:.1f}s"
                )
                
                try:
                    # Extract segment using ffmpeg
                    segment_path = os.path.join(temp_dir, f'segment_{i}.mp4')
                    self._extract_video_segment(
                        temp_video_path,
                        segment_path,
                        start_time,
                        duration
                    )
                    
                    # Upload segment to S3 temporarily
                    segment_s3_key = f"temp/transcription/{video_id}/segment_{i}.mp4"
                    segment_s3_uri = self._upload_segment_to_s3(segment_path, segment_s3_key)
                    
                    # Transcribe segment with Pegasus
                    transcription_text = self._transcribe_segment(segment_s3_uri)
                    
                    # Clean up temp segment from S3
                    self._delete_temp_segment(segment_s3_key)
                    
                    # Clean up local segment file
                    if os.path.exists(segment_path):
                        os.remove(segment_path)
                    
                    # Create transcription segment
                    all_segments.append(TranscriptionSegment(
                        start_time=start_time,
                        end_time=end_time,
                        text=transcription_text,
                        confidence=0.95  # High confidence since we transcribed exact segment
                    ))
                    
                    logger.info(f"  Transcribed: {transcription_text[:60]}...")
                    
                except Exception as e:
                    logger.error(f"Failed to transcribe segment {i}: {e}")
                    # Add empty segment on failure
                    all_segments.append(TranscriptionSegment(
                        start_time=start_time,
                        end_time=end_time,
                        text="[Transcription failed]",
                        confidence=0.0
                    ))
            
            logger.info(f"Completed transcription of {len(all_segments)} segments")
            return all_segments
            
        except Exception as e:
            logger.error(f"Failed to generate segment-by-segment transcription: {e}")
            # Return empty segments on failure
            return [
                TranscriptionSegment(
                    start_time=seg['start_sec'],
                    end_time=seg['end_sec'],
                    text="[Transcription failed]",
                    confidence=0.0
                )
                for seg in embedding_segments
            ]
        finally:
            # Clean up temp directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    logger.debug(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp directory: {e}")
    
    def _filter_duplicate_segments(
        self,
        embedding_segments: List[Dict[str, float]]
    ) -> List[Dict[str, float]]:
        """Filter duplicate segments and keep only finest-grained ones.
        
        Args:
            embedding_segments: List of time segments from Marengo
        
        Returns:
            Filtered list of unique segments
        """
        segments_by_start = {}
        for seg in embedding_segments:
            start = seg.get('start_sec', seg.get('startSec', 0))
            end = seg.get('end_sec', seg.get('endSec', 0))
            duration = end - start
            
            if start not in segments_by_start or duration < (segments_by_start[start]['end_sec'] - start):
                segments_by_start[start] = {'start_sec': start, 'end_sec': end}
        
        filtered_segments = sorted(segments_by_start.values(), key=lambda x: x['start_sec'])
        
        logger.info(
            f"Filtered to {len(filtered_segments)} unique segments "
            f"(removed {len(embedding_segments) - len(filtered_segments)} duplicates)"
        )
        
        return filtered_segments
    
    
    
    
    
    
    def _download_video_from_s3(self, s3_uri: str, local_path: str) -> None:
        """Download video from S3 to local file.
        
        Args:
            s3_uri: S3 URI (s3://bucket/key)
            local_path: Local file path to save to
        """
        # Parse S3 URI
        if not s3_uri.startswith('s3://'):
            raise ValueError(f"Invalid S3 URI: {s3_uri}")
        
        parts = s3_uri[5:].split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        
        # Check if file exists
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == '404':
                raise FileNotFoundError(f"Video not found in S3: {s3_uri}")
            raise
        
        # Download file
        self.s3_client.download_file(bucket, key, local_path)
        logger.debug(f"Downloaded {s3_uri} to {local_path}")
    
    def _extract_video_segment(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        duration: float
    ) -> None:
        """Extract a segment from video using ffmpeg.
        
        Args:
            input_path: Path to input video
            output_path: Path to output segment
            start_time: Start time in seconds
            duration: Duration in seconds
        """
        cmd = [
            get_ffmpeg_path(),
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(duration),
            '-c', 'copy',  # Copy codec for speed
            '-y',  # Overwrite output
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        logger.debug(f"Extracted segment: {start_time}s + {duration}s")
    
    def _upload_segment_to_s3(self, local_path: str, s3_key: str) -> str:
        """Upload video segment to S3.
        
        Args:
            local_path: Local file path
            s3_key: S3 key to upload to
        
        Returns:
            S3 URI of uploaded file
        """
        with open(local_path, 'rb') as f:
            self.s3_client.put_object(
                Bucket=self.config.s3_bucket_name,
                Key=s3_key,
                Body=f,
                ContentType='video/mp4'
            )
        
        s3_uri = f"s3://{self.config.s3_bucket_name}/{s3_key}"
        logger.debug(f"Uploaded segment to {s3_uri}")
        return s3_uri
    
    def _delete_temp_segment(self, s3_key: str) -> None:
        """Delete temporary segment from S3.
        
        Args:
            s3_key: S3 key to delete
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.config.s3_bucket_name,
                Key=s3_key
            )
            logger.debug(f"Deleted temp segment: {s3_key}")
        except Exception as e:
            logger.warning(f"Failed to delete temp segment {s3_key}: {e}")
    
    def _transcribe_segment(self, segment_s3_uri: str) -> str:
        """Transcribe a video segment using Pegasus.
        
        Args:
            segment_s3_uri: S3 URI of the video segment
        
        Returns:
            Transcription text
        """
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
    
    def _generate_unaligned_transcription(
        self,
        video_id: str,
        s3_uri: str
    ) -> List[TranscriptionSegment]:
        """Generate transcription with Pegasus-determined segments.
        
        Used when embedding segments are not available.
        
        Args:
            video_id: ID of the video
            s3_uri: S3 URI of the video file
        
        Returns:
            List of transcription segments
        """
        # Craft prompt for transcription
        prompt = """Transcribe all spoken words in this video with precise timestamps.

Format your response as a JSON array of segments, where each segment has:
- start_time: start time in seconds (float)
- end_time: end time in seconds (float)
- text: the spoken text in that time range
- confidence: confidence score 0-1 (use 1.0 if uncertain)

Example format:
[
  {"start_time": 0.0, "end_time": 5.2, "text": "Hello and welcome to this video.", "confidence": 1.0},
  {"start_time": 5.2, "end_time": 10.5, "text": "Today we'll be discussing...", "confidence": 1.0}
]

Provide ONLY the JSON array, no other text."""

        try:
            logger.info(f"Invoking Pegasus for transcription: {video_id}")
            
            # Invoke Pegasus with structured output
            response = self.bedrock_client.invoke_pegasus_analysis(
                s3_uri=s3_uri,
                prompt=prompt,
                temperature=0.1,  # Low temperature for more deterministic output
                max_output_tokens=4096
            )
            
            message = response.get("message", "")
            
            if not message:
                raise AWSServiceError("Pegasus returned empty response")
            
            # Parse the response
            segments = self._parse_pegasus_response(message)
            
            logger.info(f"Parsed {len(segments)} segments from Pegasus response")
            
            return segments
            
        except Exception as e:
            logger.error(f"Failed to generate transcription with Pegasus: {e}")
            raise
    
    def _parse_pegasus_response(self, response_text: str) -> List[TranscriptionSegment]:
        """Parse Pegasus response into transcription segments.
        
        Args:
            response_text: Raw text response from Pegasus
        
        Returns:
            List of TranscriptionSegment objects
        """
        segments = []
        
        try:
            # Try to extract JSON array from response
            # Pegasus might include some text before/after the JSON
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            segment = TranscriptionSegment(
                                start_time=float(item.get("start_time", 0)),
                                end_time=float(item.get("end_time", 0)),
                                text=str(item.get("text", "")),
                                confidence=float(item.get("confidence", 1.0))
                            )
                            segments.append(segment)
                else:
                    raise ValueError("Response is not a JSON array")
            else:
                # Fallback: try to parse as plain text with timestamps
                logger.warning("Could not find JSON in Pegasus response, attempting text parsing")
                segments = self._parse_text_response(response_text)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from Pegasus: {e}")
            # Fallback to text parsing
            segments = self._parse_text_response(response_text)
        except Exception as e:
            logger.error(f"Error parsing Pegasus response: {e}")
            raise AWSServiceError(f"Failed to parse transcription: {e}") from e
        
        if not segments:
            # Create a single segment with all text if parsing failed
            logger.warning("Creating fallback segment with full text")
            segments = [
                TranscriptionSegment(
                    start_time=0.0,
                    end_time=60.0,  # Default duration
                    text=response_text.strip(),
                    confidence=0.5
                )
            ]
        
        return segments
    
    def _parse_text_response(self, text: str) -> List[TranscriptionSegment]:
        """Parse plain text response with timestamps.
        
        Attempts to extract timestamps and text from formats like:
        - [0:00-0:05] Hello world
        - 0:00 - 0:05: Hello world
        - (0.0s - 5.0s) Hello world
        
        Args:
            text: Plain text with timestamps
        
        Returns:
            List of TranscriptionSegment objects
        """
        segments = []
        
        # Pattern to match various timestamp formats
        patterns = [
            r'\[(\d+):(\d+)-(\d+):(\d+)\]\s*(.+?)(?=\[|$)',  # [MM:SS-MM:SS] text
            r'(\d+):(\d+)\s*-\s*(\d+):(\d+):\s*(.+?)(?=\d+:|$)',  # MM:SS - MM:SS: text
            r'\((\d+\.?\d*)\s*s?\s*-\s*(\d+\.?\d*)\s*s?\)\s*(.+?)(?=\(|$)',  # (X.Xs - Y.Ys) text
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)
            
            for match in matches:
                try:
                    if len(match.groups()) == 5:
                        # Format: [MM:SS-MM:SS] text
                        start_min, start_sec, end_min, end_sec, segment_text = match.groups()
                        start_time = int(start_min) * 60 + int(start_sec)
                        end_time = int(end_min) * 60 + int(end_sec)
                    elif len(match.groups()) == 3:
                        # Format: (X.Xs - Y.Ys) text
                        start_time = float(match.group(1))
                        end_time = float(match.group(2))
                        segment_text = match.group(3)
                    else:
                        continue
                    
                    segment = TranscriptionSegment(
                        start_time=start_time,
                        end_time=end_time,
                        text=segment_text.strip(),
                        confidence=0.8
                    )
                    segments.append(segment)
                    
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse segment: {e}")
                    continue
            
            if segments:
                break  # Found matches with this pattern
        
        return segments
    
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
            "source": "pegasus",
            "segments": [seg.to_dict() for seg in segments]
        }
        
        try:
            self.s3_client.put_object(
                Bucket=self.config.s3_bucket_name,
                Key=key,
                Body=json.dumps(data, indent=2),
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
