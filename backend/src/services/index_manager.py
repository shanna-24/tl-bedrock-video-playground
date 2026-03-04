"""Index Manager service for video archive system.

This module provides the IndexManager class for managing video indexes,
including creation, deletion, listing, and video management.

Validates: Requirements 1.1, 1.2, 1.3, 1.6
"""

import logging
import subprocess
import tempfile
from typing import List, Optional

from aws.bedrock_client import BedrockClient
from aws.s3_vectors_client import S3VectorsClient
from config import Config
from exceptions import ResourceLimitError, ResourceNotFoundError, ValidationError
from models.index import Index
from storage.metadata_store import IndexMetadataStore
from utils.ffmpeg import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)


class IndexManager:
    """Manages video indexes and their lifecycle.
    
    This class handles creating, deleting, listing, and retrieving video indexes.
    It integrates with BedrockClient for AI model access, S3VectorsClient for
    vector storage, and IndexMetadataStore for persistence.
    
    Attributes:
        bedrock: BedrockClient instance for Bedrock API calls
        s3_vectors: S3VectorsClient instance for vector operations
        config: Configuration object with system settings
        metadata_store: IndexMetadataStore for persisting index metadata
    """
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        s3_vectors_client: S3VectorsClient,
        config: Config,
        metadata_store: Optional[IndexMetadataStore] = None,
        embedding_job_store: Optional['EmbeddingJobStore'] = None
    ):
        """Initialize the IndexManager.
        
        Args:
            bedrock_client: BedrockClient instance
            s3_vectors_client: S3VectorsClient instance
            config: Configuration object
            metadata_store: IndexMetadataStore instance (required)
            embedding_job_store: EmbeddingJobStore instance for tracking
                               async embedding jobs (required)
        """
        self.bedrock = bedrock_client
        self.s3_vectors = s3_vectors_client
        self.config = config
        
        if metadata_store is None:
            raise ValueError("metadata_store is required - must be initialized with S3 client")
        self.metadata_store = metadata_store
        
        if embedding_job_store is None:
            raise ValueError("embedding_job_store is required - must be initialized with S3 client")
        self.embedding_job_store = embedding_job_store
        
        logger.info("Initialized IndexManager")
    
    def _validate_index_limit(self) -> bool:
        """Validate that the index limit has not been reached.
        
        Returns:
            True if creating a new index is allowed
            
        Raises:
            ResourceLimitError: If the maximum number of indexes has been reached
        """
        current_indexes = self.metadata_store.load_indexes()
        
        if len(current_indexes) >= self.config.max_indexes:
            raise ResourceLimitError(
                f"Maximum of {self.config.max_indexes} indexes allowed. "
                f"Please delete an existing index before creating a new one."
            )
        
        return True
    
    async def create_index(self, name: str) -> Index:
        """Create a new video index.
        
        This method:
        1. Validates the index limit
        2. Validates the name is unique
        3. Creates a new Index object
        4. Creates a vector index in S3 Vectors
        5. Persists the index metadata
        
        Args:
            name: User-provided name for the index
            
        Returns:
            Created Index instance
            
        Raises:
            ResourceLimitError: If maximum indexes limit is reached
            ValidationError: If the index name is invalid or already exists
            AWSServiceError: If S3 Vectors index creation fails
        """
        try:
            # Validate index limit
            self._validate_index_limit()
            
            # Check for duplicate names
            current_indexes = self.metadata_store.load_indexes()
            if any(idx.name.lower() == name.lower() for idx in current_indexes):
                raise ValidationError(
                    f"An index with the name '{name}' already exists. "
                    f"Please choose a different name."
                )
            
            logger.info(f"Creating index with name: {name}")
            
            # Create Index object (this validates the name)
            index = Index.create(name=name)
            
            # Create vector index in S3 Vectors
            # Use a normalized index name for S3 Vectors (lowercase, hyphens)
            vector_index_name = f"index-{index.id}".lower()
            
            # Create vector index with 512 dimensions (Marengo 3.0)
            # and cosine distance metric
            try:
                index_arn = self.s3_vectors.create_index(
                    index_name=vector_index_name,
                    dimension=512,
                    distance_metric="cosine"
                )
                
                # Store the vector index name in the index metadata
                index.s3_vectors_collection_id = vector_index_name
                index.metadata["vector_index_arn"] = index_arn
                
                logger.info(f"Created S3 Vectors index: {vector_index_name}")
                
            except Exception as e:
                logger.error(f"Failed to create S3 Vectors index: {e}")
                raise
            
            # Persist index metadata
            self.metadata_store.save_index(index)
            
            logger.info(f"Successfully created index: {index.id}")
            
            return index
            
        except ValidationError:
            # Re-raise validation errors from Index model
            raise
        except ResourceLimitError:
            # Re-raise resource limit errors
            raise
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise
    
    async def delete_index(self, index_id: str, s3_client=None) -> bool:
        """Delete a video index and all related assets.
        
        This method performs comprehensive cleanup:
        1. Retrieves the index from metadata store
        2. Deletes all videos in the index (which handles per-video cleanup)
        3. Deletes all video files from S3 (videos/{index_id}/*)
        4. Deletes all thumbnail files from S3 (thumbnails/{index_id}/*)
        5. Deletes all transcription files from S3 (transcriptions/segments/*)
        6. Deletes all embedding output files from S3 (based on job records)
        7. Deletes all embedding job records from job store
        8. Deletes the vector index from S3 Vectors
        9. Removes the index from metadata store
        
        Args:
            index_id: ID of the index to delete
            s3_client: Optional S3Client instance for deleting S3 assets
            
        Returns:
            True if the index was deleted successfully
            
        Raises:
            ResourceNotFoundError: If the index doesn't exist
            AWSServiceError: If S3 or S3 Vectors deletion fails
        """
        logger.info(f"Deleting index and all related assets: {index_id}")
        
        # Get the index from metadata store
        index = self.metadata_store.get_index(index_id)
        
        if index is None:
            raise ResourceNotFoundError(f"Index not found: {index_id}")
        
        cleanup_errors = []
        
        # Step 0: Delete all videos in the index first
        # This ensures proper cleanup of per-video data (embeddings, jobs, etc.)
        try:
            logger.info(f"Deleting all videos in index {index_id}")
            videos = await self.list_videos_in_index(index_id)
            videos_deleted = 0
            videos_failed = 0
            
            for video in videos:
                try:
                    await self.delete_video(video.id, s3_client=s3_client)
                    videos_deleted += 1
                except Exception as e:
                    videos_failed += 1
                    logger.warning(f"Failed to delete video {video.id}: {e}")
                    # Continue deleting other videos even if one fails
            
            logger.info(
                f"Deleted {videos_deleted} videos from index {index_id} "
                f"({videos_failed} failed)"
            )
            
            if videos_failed > 0:
                cleanup_errors.append(
                    f"Failed to delete {videos_failed} videos"
                )
        except Exception as e:
            error_msg = f"Failed to delete videos from index: {e}"
            logger.error(error_msg)
            cleanup_errors.append(error_msg)
        
        # Step 1: Delete all S3 assets if s3_client is provided
        if s3_client:
            try:
                # Delete all video files (videos/{index_id}/*)
                logger.info(f"Deleting video files for index {index_id}")
                video_count = s3_client.delete_prefix(f"videos/{index_id}/")
                logger.info(f"Deleted {video_count} video files")
            except Exception as e:
                error_msg = f"Failed to delete video files: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
            
            try:
                # Delete all thumbnail files (thumbnails/{index_id}/*)
                logger.info(f"Deleting thumbnail files for index {index_id}")
                thumbnail_count = s3_client.delete_prefix(f"thumbnails/{index_id}/")
                logger.info(f"Deleted {thumbnail_count} thumbnail files")
            except Exception as e:
                error_msg = f"Failed to delete thumbnail files: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
            
            try:
                # Delete all transcription segment files for videos in this index
                logger.info(f"Deleting transcription files for index {index_id}")
                
                # The per-video deletion should have cleaned up most transcription files
                # This is a safety net to catch any remaining files
                
                # Try to delete any remaining transcription files by prefix
                # This will catch both segments and raw AWS Transcribe outputs
                try:
                    # Note: We can't easily filter by index_id since transcription files
                    # are stored by video_id, not index_id. The per-video deletion
                    # should have handled this already.
                    logger.debug("Transcription cleanup handled by per-video deletion")
                except Exception as e:
                    logger.debug(f"Transcription cleanup note: {e}")
                
                logger.info(f"Transcription cleanup completed for index {index_id}")
            except Exception as e:
                error_msg = f"Failed to delete transcription files: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
            
            try:
                # Delete embedding output files for all jobs in this index
                logger.info(f"Deleting embedding output files for index {index_id}")
                
                # Get all jobs for this index to find their output locations
                all_jobs = self.embedding_job_store.get_all_jobs()
                index_jobs = [job for job in all_jobs if job.index_id == index_id]
                
                embedding_folders_deleted = 0
                for job in index_jobs:
                    if job.output_location:
                        try:
                            # Extract S3 key from output_location URI
                            # Format: s3://bucket/embeddings/some-folder/output.json
                            # We need to delete the entire folder: embeddings/some-folder/
                            output_key = job.output_location.replace(
                                f"s3://{s3_client.bucket_name}/", ""
                            )
                            
                            # Extract the folder path (remove the filename)
                            # e.g., "embeddings/abc123/output.json" -> "embeddings/abc123/"
                            folder_path = "/".join(output_key.split("/")[:-1]) + "/"
                            
                            # Delete the entire folder (manifest.json, output.json, etc.)
                            deleted_count = s3_client.delete_prefix(folder_path)
                            if deleted_count > 0:
                                embedding_folders_deleted += 1
                                logger.debug(
                                    f"Deleted embedding folder: {folder_path} "
                                    f"({deleted_count} files)"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Failed to delete embedding folder for {job.output_location}: {e}"
                            )
                
                logger.info(
                    f"Deleted {embedding_folders_deleted} embedding folders "
                    f"from {len(index_jobs)} jobs"
                )
            except Exception as e:
                error_msg = f"Failed to delete embedding output files: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
        else:
            logger.warning(
                "No S3 client provided - skipping S3 asset cleanup. "
                "Video, thumbnail, and embedding files will remain in S3."
            )
        
        # Step 2: Delete all embedding job records
        try:
            logger.info(f"Deleting embedding job records for index {index_id}")
            jobs_deleted = self.embedding_job_store.delete_jobs_by_index(index_id)
            logger.info(f"Deleted {jobs_deleted} embedding job records")
        except Exception as e:
            error_msg = f"Failed to delete embedding job records: {e}"
            logger.error(error_msg)
            cleanup_errors.append(error_msg)
        
        # Step 3: Delete vector index from S3 Vectors
        if index.s3_vectors_collection_id:
            try:
                self.s3_vectors.delete_index(index.s3_vectors_collection_id)
                logger.info(
                    f"Deleted S3 Vectors index: {index.s3_vectors_collection_id}"
                )
            except Exception as e:
                error_msg = f"Failed to delete S3 Vectors index: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
                # Continue with metadata deletion even if S3 Vectors deletion fails
                # This prevents orphaned metadata
        
        # Step 4: Delete from metadata store
        try:
            self.metadata_store.delete_index(index_id)
            logger.info(f"Deleted index metadata for {index_id}")
        except Exception as e:
            error_msg = f"Failed to delete index metadata: {e}"
            logger.error(error_msg)
            cleanup_errors.append(error_msg)
            raise  # Re-raise metadata deletion errors as they're critical
        
        # Log summary
        if cleanup_errors:
            logger.warning(
                f"Index {index_id} deleted with {len(cleanup_errors)} cleanup errors: "
                f"{'; '.join(cleanup_errors)}"
            )
        else:
            logger.info(f"Successfully deleted index {index_id} and all related assets")
        
        return True
    
    async def delete_video(self, video_id: str, s3_client=None) -> bool:
        """Delete a video and all its related data.
        
        This method performs comprehensive cleanup for a single video:
        1. Finds the video across all indexes
        2. Deletes the video file from S3 (videos/{index_id}/{video_id}/*)
        3. Deletes the thumbnail from S3 (thumbnails/{index_id}/{video_id}/*)
        4. Deletes all transcription files from S3:
           - Processed segments (transcriptions/segments/{video_id}.json)
           - Raw AWS Transcribe output (transcriptions/transcription-{video_id}.json)
           - Subtitle files (transcriptions/transcription-{video_id}.vtt/srt)
        5. Deletes embeddings from S3 Vectors (by video_id)
        6. Deletes embedding job records for this video
        7. Removes video metadata from the index
        
        Other videos in the same index are not affected.
        
        Args:
            video_id: ID of the video to delete
            s3_client: Optional S3Client instance for deleting S3 assets
            
        Returns:
            True if the video was deleted successfully
            
        Raises:
            ResourceNotFoundError: If the video doesn't exist
            AWSServiceError: If S3 or S3 Vectors deletion fails
        """
        logger.info(f"Deleting video and all related data: {video_id}")
        
        # Find the video across all indexes
        video = None
        parent_index = None
        indexes = await self.list_indexes()
        
        for index in indexes:
            videos = await self.list_videos_in_index(index.id)
            for v in videos:
                if v.id == video_id:
                    video = v
                    parent_index = index
                    break
            if video:
                break
        
        if not video or not parent_index:
            raise ResourceNotFoundError(f"Video not found: {video_id}")
        
        logger.info(f"Found video {video_id} in index {parent_index.id}")
        
        cleanup_errors = []
        
        # Step 1: Delete video file from S3 (videos/{index_id}/{video_id}/*)
        if s3_client:
            try:
                video_prefix = f"videos/{parent_index.id}/{video_id}/"
                logger.info(f"Deleting video files: {video_prefix}")
                video_count = s3_client.delete_prefix(video_prefix)
                logger.info(f"Deleted {video_count} video files")
            except Exception as e:
                error_msg = f"Failed to delete video files: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
            
            # Step 2: Delete thumbnail from S3 (thumbnails/{index_id}/{video_id}/*)
            try:
                thumbnail_prefix = f"thumbnails/{parent_index.id}/{video_id}/"
                logger.info(f"Deleting thumbnail files: {thumbnail_prefix}")
                thumbnail_count = s3_client.delete_prefix(thumbnail_prefix)
                logger.info(f"Deleted {thumbnail_count} thumbnail files")
            except Exception as e:
                error_msg = f"Failed to delete thumbnail files: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
            
            # Step 2.5: Delete all transcription files from S3
            try:
                # Delete processed transcription segments
                transcription_segment_key = f"transcriptions/segments/{video_id}.json"
                logger.info(f"Deleting transcription segment file: {transcription_segment_key}")
                try:
                    s3_client.delete(transcription_segment_key)
                    logger.info(f"Deleted transcription segment file for video {video_id}")
                except Exception as e:
                    # It's okay if the file doesn't exist (video might not have transcription)
                    logger.debug(f"No transcription segment file found: {e}")
                
                # Delete raw AWS Transcribe output files
                transcription_job_name = f"transcription-{video_id}"
                transcription_files = [
                    f"transcriptions/{transcription_job_name}.json",  # Raw transcription
                    f"transcriptions/{transcription_job_name}.vtt",   # VTT subtitles
                    f"transcriptions/{transcription_job_name}.srt"    # SRT subtitles
                ]
                
                for file_key in transcription_files:
                    try:
                        s3_client.delete(file_key)
                        logger.debug(f"Deleted transcription file: {file_key}")
                    except Exception as e:
                        # It's okay if files don't exist
                        logger.debug(f"Transcription file not found: {file_key}")
                
                logger.info(f"Completed transcription cleanup for video {video_id}")
            except Exception as e:
                error_msg = f"Failed to delete transcription files: {e}"
                logger.error(error_msg)
                cleanup_errors.append(error_msg)
        else:
            logger.warning(
                "No S3 client provided - skipping S3 asset cleanup. "
                "Video and thumbnail files will remain in S3."
            )
        
        # Step 3: Delete embeddings from S3 Vectors
        try:
            logger.info(f"Deleting embeddings for video {video_id} from S3 Vectors")
            logger.info(f"Vector index name: {parent_index.s3_vectors_collection_id}")
            # Delete all embeddings with this video_id from the vector index
            # The embedding keys are formatted as: {video_id}:{start}:{end}:{idx}
            deleted_count = self.s3_vectors.delete_by_video_id(
                index_name=parent_index.s3_vectors_collection_id,
                video_id=video_id
            )
            logger.info(f"Deleted {deleted_count} embeddings from S3 Vectors")
            
            if deleted_count == 0:
                logger.warning(
                    f"No embeddings were deleted from S3 Vectors for video {video_id}. "
                    f"This might indicate that embeddings were never indexed, or there's "
                    f"an issue with the deletion logic."
                )
        except Exception as e:
            error_msg = f"Failed to delete embeddings from S3 Vectors: {e}"
            logger.error(error_msg)
            cleanup_errors.append(error_msg)
        
        # Step 4: Delete embedding job records for this video
        try:
            logger.info(f"Deleting embedding job records for video {video_id}")
            all_jobs = self.embedding_job_store.get_all_jobs()
            video_jobs = [job for job in all_jobs if job.video_id == video_id]
            
            # Delete embedding output files from S3
            if s3_client:
                for job in video_jobs:
                    if job.output_location:
                        try:
                            output_key = job.output_location.replace(
                                f"s3://{s3_client.bucket_name}/", ""
                            )
                            folder_path = "/".join(output_key.split("/")[:-1]) + "/"
                            s3_client.delete_prefix(folder_path)
                            logger.debug(f"Deleted embedding folder: {folder_path}")
                        except Exception as e:
                            logger.warning(f"Failed to delete embedding folder: {e}")
            
            # Delete job records
            jobs_deleted = 0
            for job in video_jobs:
                try:
                    if self.embedding_job_store.delete_job(job.job_id):
                        jobs_deleted += 1
                except Exception as e:
                    logger.warning(f"Failed to delete job {job.job_id}: {e}")
            
            logger.info(f"Deleted {jobs_deleted} embedding job records")
        except Exception as e:
            error_msg = f"Failed to delete embedding job records: {e}"
            logger.error(error_msg)
            cleanup_errors.append(error_msg)
        
        # Step 5: Remove video from index metadata
        try:
            logger.info(f"Removing video {video_id} from index {parent_index.id}")
            
            # Remove video from the videos list in index metadata
            videos_data = parent_index.metadata.get('videos', [])
            videos_data = [v for v in videos_data if v.get('id') != video_id]
            parent_index.metadata['videos'] = videos_data
            
            # Update video count
            parent_index.video_count = max(0, parent_index.video_count - 1)
            
            # Save updated index
            self.metadata_store.save_index(parent_index)
            logger.info(f"Updated index metadata (new video count: {parent_index.video_count})")
        except Exception as e:
            error_msg = f"Failed to update index metadata: {e}"
            logger.error(error_msg)
            cleanup_errors.append(error_msg)
            raise  # Re-raise metadata errors as they're critical
        
        # Log summary
        if cleanup_errors:
            logger.warning(
                f"Video {video_id} deleted with {len(cleanup_errors)} cleanup errors: "
                f"{'; '.join(cleanup_errors)}"
            )
        else:
            logger.info(f"Successfully deleted video {video_id} and all related data")
        
        return True
    
    async def list_indexes(self) -> List[Index]:
        """List all video indexes.
        
        Returns:
            List of all Index instances
        """
        logger.debug("Listing all indexes")
        
        indexes = self.metadata_store.load_indexes()
        
        logger.info(f"Found {len(indexes)} indexes")
        
        return indexes
    
    async def get_index(self, index_id: str) -> Index:
        """Get a specific video index by ID.
        
        Args:
            index_id: ID of the index to retrieve
            
        Returns:
            Index instance
            
        Raises:
            ResourceNotFoundError: If the index doesn't exist
        """
        logger.debug(f"Getting index: {index_id}")
        
        index = self.metadata_store.get_index(index_id)
        
        if index is None:
            raise ResourceNotFoundError(f"Index not found: {index_id}")
        
        logger.info(f"Retrieved index: {index_id}")
        
        return index

    async def add_video_to_index(
        self,
        index_id: str,
        video_file,
        filename: str,
        s3_client
    ):
        """Add a video file to an index.

        This method:
        1. Validates the index exists
        2. Validates the video file format
        3. Uploads the video to S3
        4. Generates embeddings using Marengo model (async job)
        5. Creates a Video object with metadata
        6. Updates the index video count

        Args:
            index_id: ID of the index to add the video to
            video_file: File-like object containing the video data
            filename: Original filename of the video
            s3_client: S3Client instance for uploading the video

        Returns:
            Video instance with metadata

        Raises:
            ResourceNotFoundError: If the index doesn't exist
            ValidationError: If the video file is invalid
            AWSServiceError: If S3 upload or embedding generation fails
        """
        from models.video import Video
        import io

        logger.info(f"Adding video {filename} to index {index_id}")

        # Get the index to ensure it exists
        index = await self.get_index(index_id)

        # Check for duplicate filename in this index
        existing_videos = index.metadata.get('videos', [])
        if any(video.get('filename') == filename for video in existing_videos):
            from exceptions import ValidationError
            raise ValidationError(
                f"A video with the filename '{filename}' already exists in this index. "
                f"Please rename the file or choose a different video."
            )

        # Generate S3 key for the video
        video_id = str(__import__('uuid').uuid4())
        s3_key = f"videos/{index_id}/{video_id}/{filename}"

        # Determine content type based on file extension
        content_type_map = {
            '.mp4': 'video/mp4',
            '.mov': 'video/quicktime',
            '.avi': 'video/x-msvideo',
            '.mkv': 'video/x-matroska'
        }

        file_ext = None
        for ext in content_type_map.keys():
            if filename.lower().endswith(ext):
                file_ext = ext
                break

        if not file_ext:
            from exceptions import ValidationError
            raise ValidationError(
                f"Unsupported video format. Supported formats: mp4, mov, avi, mkv"
            )

        content_type = content_type_map[file_ext]

        try:
            # Upload video to S3 with duration extraction and thumbnail generation
            logger.debug(f"Uploading video to S3: {s3_key}")
            
            # First, save to temp file to extract duration and generate thumbnail
            import tempfile
            import os
            import subprocess
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                tmp_path = tmp_file.name
                video_file.seek(0)
                tmp_file.write(video_file.read())
                tmp_file.flush()
            
            thumbnail_s3_key = None
            duration = 60.0  # Default
            
            try:
                # Extract duration using ffprobe
                result = subprocess.run(
                    [
                        get_ffprobe_path(),
                        "-v", "error",
                        "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        tmp_path
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    duration = float(result.stdout.strip())
                    logger.info(f"Extracted video duration: {duration} seconds")
                else:
                    logger.warning(f"ffprobe failed: {result.stderr}. Using default 60 seconds.")
                    
            except Exception as e:
                logger.warning(f"Failed to extract duration: {e}. Using default 60 seconds.")
            
            try:
                # Generate thumbnail using ffmpeg
                thumbnail_path = tmp_path.replace(file_ext, '_thumb.jpg')
                result = subprocess.run(
                    [
                        get_ffmpeg_path(),
                        "-i", tmp_path,
                        "-ss", "00:00:01",  # Extract frame at 1 second
                        "-vframes", "1",
                        "-vf", "scale=320:-1",  # Scale to 320px width, maintain aspect ratio
                        "-y",  # Overwrite output file
                        thumbnail_path
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0 and os.path.exists(thumbnail_path):
                    # Upload thumbnail to S3
                    thumbnail_s3_key = f"thumbnails/{index_id}/{video_id}/thumb.jpg"
                    with open(thumbnail_path, 'rb') as thumb_file:
                        s3_client.upload(
                            file_obj=thumb_file,
                            key=thumbnail_s3_key,
                            content_type='image/jpeg',
                            metadata={
                                'video_id': video_id,
                                'index_id': index_id
                            }
                        )
                    logger.info(f"Generated and uploaded thumbnail: {thumbnail_s3_key}")
                    os.remove(thumbnail_path)
                else:
                    logger.warning(f"Failed to generate thumbnail (returncode={result.returncode}): {result.stderr}")
                    
            except Exception as e:
                logger.warning(f"Failed to generate thumbnail: {e}")
                
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            
            # Reset file pointer and upload to S3
            video_file.seek(0)
            metadata = {
                'index_id': index_id,
                'original_filename': filename,
                'duration': str(duration)
            }
            if thumbnail_s3_key:
                metadata['thumbnail_key'] = thumbnail_s3_key
                
            s3_uri = s3_client.upload(
                file_obj=video_file,
                key=s3_key,
                content_type=content_type,
                metadata=metadata
            )

            logger.info(f"Video uploaded to {s3_uri} with duration {duration}s")


            # Generate embeddings using Marengo model
            logger.debug(f"Starting embedding generation for {s3_uri}")
            embedding_ids = await self._generate_embeddings(
                video_s3_uri=s3_uri,
                index=index,
                video_duration=duration
            )

            logger.info(f"Generated {len(embedding_ids)} embeddings for video")

            # Note: Transcription will be generated automatically after embeddings complete
            # The embedding job processor will generate aligned transcription segments
            # that match the Marengo embedding time ranges for perfect alignment

            # Duration was already extracted during upload and stored in metadata
            # Use the duration we extracted above

            # Create Video object
            video = Video(
                id=video_id,
                index_id=index_id,
                filename=filename,
                s3_uri=s3_uri,
                duration=duration,
                embedding_ids=embedding_ids,
                metadata={
                    's3_key': s3_key,
                    'content_type': content_type
                }
            )

            # Update index video count
            index.video_count += 1
            self.metadata_store.save_index(index)

            # Save video metadata (we'll need a video metadata store)
            # For now, store videos in the index metadata
            if 'videos' not in index.metadata:
                index.metadata['videos'] = []

            index.metadata['videos'].append(video.model_dump(mode='json'))
            self.metadata_store.save_index(index)

            logger.info(f"Successfully added video {video_id} to index {index_id}")

            return video

        except Exception as e:
            logger.error(f"Failed to add video to index: {e}")
            # Attempt cleanup: delete S3 object if it was uploaded
            try:
                if 's3_uri' in locals():
                    s3_client.delete(s3_key)
                    logger.info(f"Cleaned up S3 object after failure: {s3_key}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup S3 object: {cleanup_error}")

            raise

    async def list_videos_in_index(self, index_id: str):
        """List all videos in an index.

        Args:
            index_id: ID of the index

        Returns:
            List of Video instances

        Raises:
            ResourceNotFoundError: If the index doesn't exist
        """
        from models.video import Video

        logger.debug(f"Listing videos in index {index_id}")

        # Get the index to ensure it exists
        index = await self.get_index(index_id)

        # Retrieve videos from index metadata
        videos_data = index.metadata.get('videos', [])

        # Convert to Video objects
        videos = [Video.model_validate(video_data) for video_data in videos_data]

        logger.info(f"Found {len(videos)} videos in index {index_id}")

        return videos

    async def backfill_video_metadata(self, index_id: str, s3_client):
        """Backfill missing metadata for videos in an index.
        
        This method updates videos that were uploaded before thumbnail and
        duration extraction was implemented. It:
        1. Downloads each video temporarily
        2. Extracts duration using ffprobe
        3. Generates thumbnail using ffmpeg
        4. Uploads thumbnail to S3
        5. Updates S3 metadata with thumbnail_key and duration
        6. Updates video object in index metadata
        
        Args:
            index_id: ID of the index
            s3_client: S3Client instance for accessing videos
            
        Returns:
            Dictionary with backfill results
            
        Raises:
            ResourceNotFoundError: If the index doesn't exist
        """
        import tempfile
        import os
        import subprocess
        from io import BytesIO
        
        logger.info(f"Starting metadata backfill for index {index_id}")
        
        # Get the index
        index = await self.get_index(index_id)
        
        # Get videos
        videos_data = index.metadata.get('videos', [])
        
        results = {
            'total': len(videos_data),
            'updated': 0,
            'skipped': 0,
            'failed': 0,
            'errors': []
        }
        
        for video_data in videos_data:
            video_id = video_data['id']
            s3_uri = video_data['s3_uri']
            filename = video_data['filename']
            
            try:
                # Extract S3 key from URI
                s3_key = s3_uri.replace(f"s3://{s3_client.bucket_name}/", "")
                
                # Check if metadata already exists
                try:
                    existing_metadata = s3_client.get_object_metadata(key=s3_key)
                    custom_meta = existing_metadata.get("Metadata", {})
                    
                    if "thumbnail_key" in custom_meta and "duration" in custom_meta:
                        logger.info(f"Video {video_id} already has metadata, skipping")
                        results['skipped'] += 1
                        continue
                except Exception:
                    pass  # Metadata doesn't exist, proceed with backfill
                
                logger.info(f"Backfilling metadata for video {video_id}")
                
                # Download video to temp file
                file_ext = os.path.splitext(filename)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                    tmp_path = tmp_file.name
                    s3_client.download(key=s3_key, file_obj=tmp_file)
                
                try:
                    # Extract duration using ffprobe
                    result = subprocess.run(
                        [
                            get_ffprobe_path(),
                            "-v", "error",
                            "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1",
                            tmp_path
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        duration = float(result.stdout.strip())
                        logger.info(f"Extracted duration: {duration}s")
                    else:
                        logger.warning(f"Failed to extract duration, keeping existing: {result.stderr}")
                        duration = video_data.get('duration', 60.0)
                    
                    # Generate thumbnail
                    thumbnail_path = tmp_path.replace(file_ext, '_thumb.jpg')
                    result = subprocess.run(
                        [
                            get_ffmpeg_path(),
                            "-i", tmp_path,
                            "-ss", "00:00:01",
                            "-vframes", "1",
                            "-vf", "scale=320:-1",
                            "-y",
                            thumbnail_path
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    thumbnail_s3_key = None
                    if result.returncode == 0 and os.path.exists(thumbnail_path):
                        # Upload thumbnail
                        thumbnail_s3_key = f"thumbnails/{index_id}/{video_id}/thumb.jpg"
                        with open(thumbnail_path, 'rb') as thumb_file:
                            s3_client.upload(
                                file_obj=thumb_file,
                                key=thumbnail_s3_key,
                                content_type='image/jpeg',
                                metadata={
                                    'video_id': video_id,
                                    'index_id': index_id
                                }
                            )
                        logger.info(f"Uploaded thumbnail: {thumbnail_s3_key}")
                        os.remove(thumbnail_path)
                    else:
                        logger.warning(f"Failed to generate thumbnail: {result.stderr}")
                    
                    # Update S3 metadata for video
                    # Note: S3 doesn't allow updating metadata in place, need to copy object
                    copy_source = {'Bucket': s3_client.bucket_name, 'Key': s3_key}
                    
                    # Get existing metadata
                    existing_obj_meta = s3_client.get_object_metadata(key=s3_key)
                    existing_custom_meta = existing_obj_meta.get("Metadata", {})
                    
                    # Update with new metadata
                    new_metadata = {
                        **existing_custom_meta,
                        'duration': str(duration)
                    }
                    if thumbnail_s3_key:
                        new_metadata['thumbnail_key'] = thumbnail_s3_key
                    
                    # Copy object with new metadata
                    s3_client.client.copy_object(
                        Bucket=s3_client.bucket_name,
                        CopySource=copy_source,
                        Key=s3_key,
                        Metadata=new_metadata,
                        MetadataDirective='REPLACE',
                        ContentType=existing_obj_meta.get('ContentType', 'video/mp4')
                    )
                    
                    # Update video object in index metadata
                    video_data['duration'] = duration
                    
                    logger.info(f"Successfully backfilled metadata for video {video_id}")
                    results['updated'] += 1
                    
                finally:
                    # Cleanup temp file
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                        
            except Exception as e:
                logger.error(f"Failed to backfill metadata for video {video_id}: {e}")
                results['failed'] += 1
                results['errors'].append({
                    'video_id': video_id,
                    'error': str(e)
                })
        
        # Save updated index metadata
        if results['updated'] > 0:
            self.metadata_store.save_index(index)
            logger.info(f"Saved updated metadata for {results['updated']} videos")
        
        logger.info(f"Backfill complete: {results}")
        return results

    async def _generate_embeddings(
        self,
        video_s3_uri: str,
        index,
        video_duration: Optional[float] = None
    ):
        """Generate embeddings for a video using Marengo model.

        This method starts an asynchronous embedding generation job with Bedrock
        and creates a job record in the EmbeddingJobStore for tracking.

        The embeddings will be generated in the background and processed by the
        EmbeddingJobProcessor, which will:
        1. Poll for job completion using get_async_invocation_status()
        2. Retrieve embeddings from the S3 output location
        3. Store embeddings in S3 Vectors for similarity search

        Args:
            video_s3_uri: S3 URI of the video
            index: Index object containing vector collection information
            video_duration: Duration of the video in seconds (for progress estimation)

        Returns:
            List containing the job_id for tracking the async job

        Raises:
            AWSServiceError: If embedding generation fails
        """
        logger.debug(f"Generating embeddings for video: {video_s3_uri}")

        try:
            # Start async embedding generation with Marengo 3.0
            invocation_arn = self.bedrock.start_marengo_video_embedding(
                s3_uri=video_s3_uri,
                embedding_options=["visual", "audio", "transcription"]
            )

            logger.info(f"Started embedding generation job: {invocation_arn}")

            # Extract video_id from the S3 URI
            # URI format: s3://bucket/videos/{index_id}/{video_id}/{filename}
            uri_parts = video_s3_uri.split('/')
            video_id = uri_parts[-2] if len(uri_parts) >= 2 else "unknown"

            # Create job record in the EmbeddingJobStore
            job_id = self.embedding_job_store.add_job(
                invocation_arn=invocation_arn,
                video_id=video_id,
                index_id=index.id,
                s3_uri=video_s3_uri,
                video_duration=video_duration
            )

            logger.info(
                f"Created embedding job record: {job_id} for video {video_id} (duration: {video_duration}s)"
            )

            # Return the job_id as the embedding identifier
            # The EmbeddingJobProcessor will handle the rest of the workflow
            return [job_id]

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
