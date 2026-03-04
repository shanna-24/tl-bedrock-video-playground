"""Index management API endpoints for TL-Video-Playground.

This module implements endpoints for managing video indexes and their videos.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5
"""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel, Field

from api.auth import verify_token
from services.index_manager import IndexManager
from services.video_service import VideoService
from models.index import Index
from models.video import Video
from exceptions import (
    ResourceLimitError,
    ResourceNotFoundError,
    ValidationError,
    AWSServiceError
)


# Request/Response models
class CreateIndexRequest(BaseModel):
    """Request model for creating a new index.
    
    Attributes:
        name: User-provided name for the index (3-50 characters, alphanumeric)
    """
    name: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Index name (3-50 characters, alphanumeric)"
    )


class IndexResponse(BaseModel):
    """Response model for index information.
    
    Attributes:
        id: Unique index identifier
        name: Index name
        created_at: Creation timestamp
        video_count: Number of videos in the index
        s3_vectors_collection_id: S3 Vectors collection identifier
    """
    id: str
    name: str
    created_at: str
    video_count: int
    s3_vectors_collection_id: str


class IndexListResponse(BaseModel):
    """Response model for listing indexes.
    
    Attributes:
        indexes: List of indexes
        total: Total number of indexes
        max_indexes: Maximum allowed indexes
    """
    indexes: List[IndexResponse]
    total: int
    max_indexes: int


class VideoResponse(BaseModel):
    """Response model for video information.
    
    Attributes:
        id: Unique video identifier
        index_id: ID of the index containing this video
        filename: Original filename
        s3_uri: S3 storage location
        duration: Video duration in seconds
        uploaded_at: Upload timestamp
        embedding_ids: List of embedding identifiers
        thumbnail_url: Presigned URL for video thumbnail
    """
    id: str
    index_id: str
    filename: str
    s3_uri: str
    duration: float
    uploaded_at: str
    embedding_ids: List[str]
    thumbnail_url: Optional[str] = None


class VideoListResponse(BaseModel):
    """Response model for listing videos in an index.
    
    Attributes:
        videos: List of videos
        total: Total number of videos
        index_id: ID of the index
        index_name: Name of the index
    """
    videos: List[VideoResponse]
    total: int
    index_id: str
    index_name: str


class VideoUploadResponse(BaseModel):
    """Response model for video upload.
    
    Attributes:
        video: Uploaded video information
        message: Success message
    """
    video: VideoResponse
    message: str = "Video uploaded successfully"


class DeleteResponse(BaseModel):
    """Response model for deletion operations.
    
    Attributes:
        message: Success message
        deleted_id: ID of the deleted resource
    """
    message: str
    deleted_id: str


class ErrorResponse(BaseModel):
    """Error response model.
    
    Attributes:
        detail: Error message
    """
    detail: str


# Create router
router = APIRouter()


# Dependency injection placeholders (will be set by main.py)
_index_manager: IndexManager = None
_video_service: VideoService = None
_s3_client = None


def set_index_manager(index_manager: IndexManager):
    """Set the index manager instance for dependency injection.
    
    Args:
        index_manager: Initialized IndexManager instance
    """
    global _index_manager
    _index_manager = index_manager


def set_video_service(video_service: VideoService):
    """Set the video service instance for dependency injection.
    
    Args:
        video_service: Initialized VideoService instance
    """
    global _video_service
    _video_service = video_service


def set_s3_client(s3_client):
    """Set the S3 client instance for dependency injection.
    
    Args:
        s3_client: Initialized S3Client instance
    """
    global _s3_client
    _s3_client = s3_client


def get_index_manager() -> IndexManager:
    """Get the index manager instance.
    
    Returns:
        IndexManager instance
        
    Raises:
        RuntimeError: If index manager is not initialized
    """
    if _index_manager is None:
        raise RuntimeError("Index manager not initialized")
    return _index_manager


def get_video_service() -> VideoService:
    """Get the video service instance.
    
    Returns:
        VideoService instance
        
    Raises:
        RuntimeError: If video service is not initialized
    """
    if _video_service is None:
        raise RuntimeError("Video service not initialized")
    return _video_service


def get_s3_client():
    """Get the S3 client instance.
    
    Returns:
        S3Client instance
        
    Raises:
        RuntimeError: If S3 client is not initialized
    """
    if _s3_client is None:
        raise RuntimeError("S3 client not initialized")
    return _s3_client


def _index_to_response(index: Index) -> IndexResponse:
    """Convert Index model to IndexResponse.
    
    Args:
        index: Index model instance
        
    Returns:
        IndexResponse instance
    """
    return IndexResponse(
        id=index.id,
        name=index.name,
        created_at=index.created_at.isoformat(),
        video_count=index.video_count,
        s3_vectors_collection_id=index.s3_vectors_collection_id
    )


def _video_to_response(video: Video, video_service: VideoService = None) -> VideoResponse:
    """Convert Video model to VideoResponse.
    
    Args:
        video: Video model instance
        video_service: Optional VideoService for generating thumbnail URLs
        
    Returns:
        VideoResponse instance
    """
    import logging
    logger = logging.getLogger(__name__)
    
    thumbnail_url = None
    duration = video.duration  # Default from video object
    
    if video_service:
        try:
            # Extract S3 key from s3_uri (format: s3://bucket/key)
            s3_key = video.s3_uri.replace(f"s3://{video_service.config.s3_bucket_name}/", "")
            
            # Get video metadata from S3 to check for thumbnail and duration
            metadata = video_service.s3.get_object_metadata(key=s3_key)
            custom_metadata = metadata.get("Metadata", {})
            
            logger.info(f"Video {video.id} metadata: {custom_metadata}")
            
            # Get thumbnail key from metadata
            thumbnail_key = custom_metadata.get("thumbnail_key")
            
            if thumbnail_key:
                # Generate presigned URL for thumbnail
                thumbnail_url = video_service.s3.generate_presigned_url(
                    key=thumbnail_key,
                    expiration=3600
                )
                logger.info(f"Generated thumbnail URL for {video.id}: {thumbnail_url[:100]}...")
            else:
                logger.warning(f"No thumbnail_key found in metadata for video {video.id}")
                # Fallback: generate presigned URL for video with #t=0.1
                thumbnail_url = video_service.get_video_stream_url(
                    video_id=video.id,
                    s3_key=s3_key,
                    start_timecode=0.1,
                    expiration=3600
                )
            
            # Get duration from metadata if available (overrides video object duration)
            if "duration" in custom_metadata:
                try:
                    duration = float(custom_metadata["duration"])
                except (ValueError, TypeError):
                    pass  # Keep default duration from video object
                    
        except Exception as e:
            # Log error but don't fail the request
            logger.warning(f"Failed to retrieve metadata for video {video.id}: {e}")
    
    return VideoResponse(
        id=video.id,
        index_id=video.index_id,
        filename=video.filename,
        s3_uri=video.s3_uri,
        duration=duration,
        uploaded_at=video.uploaded_at.isoformat(),
        embedding_ids=video.embedding_ids,
        thumbnail_url=thumbnail_url
    )


@router.get(
    "",
    response_model=IndexListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of indexes retrieved successfully",
            "model": IndexListResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        }
    },
    summary="List all indexes",
    description="Retrieve a list of all video indexes with their metadata"
)
async def list_indexes(
    authenticated: Annotated[bool, Depends(verify_token)],
    index_manager: Annotated[IndexManager, Depends(get_index_manager)]
) -> IndexListResponse:
    """List all video indexes.
    
    This endpoint returns all indexes with their metadata including video counts.
    Requires authentication.
    
    Args:
        authenticated: Authentication verification (injected)
        index_manager: IndexManager instance (injected)
        
    Returns:
        IndexListResponse: List of indexes with metadata
        
    Raises:
        HTTPException: 401 if not authenticated
        HTTPException: 500 if listing fails
        
    Validates: Requirements 1.1, 1.6
    """
    try:
        indexes = await index_manager.list_indexes()
        
        return IndexListResponse(
            indexes=[_index_to_response(idx) for idx in indexes],
            total=len(indexes),
            max_indexes=index_manager.config.max_indexes
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list indexes: {str(e)}"
        )


@router.post(
    "",
    response_model=IndexResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Index created successfully",
            "model": IndexResponse
        },
        400: {
            "description": "Invalid request or index limit exceeded",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Create a new index",
    description="Create a new video index with the specified name. Maximum 3 indexes allowed."
)
async def create_index(
    request: CreateIndexRequest,
    authenticated: Annotated[bool, Depends(verify_token)],
    index_manager: Annotated[IndexManager, Depends(get_index_manager)]
) -> IndexResponse:
    """Create a new video index.
    
    This endpoint creates a new index with the provided name. The system
    enforces a maximum of 3 indexes. If the limit is reached, the request
    will be rejected with a 400 error.
    
    Args:
        request: Index creation request with name
        authenticated: Authentication verification (injected)
        index_manager: IndexManager instance (injected)
        
    Returns:
        IndexResponse: Created index information
        
    Raises:
        HTTPException: 400 if index limit exceeded or invalid name
        HTTPException: 401 if not authenticated
        HTTPException: 500 if creation fails
        
    Validates: Requirements 1.1, 1.2
    """
    try:
        index = await index_manager.create_index(request.name)
        return _index_to_response(index)
        
    except ResourceLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AWSServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create index: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create index: {str(e)}"
        )


@router.delete(
    "/{index_id}",
    response_model=DeleteResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Index deleted successfully",
            "model": DeleteResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Index not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Delete an index",
    description="Delete a video index and all associated embeddings from S3 Vectors"
)
async def delete_index(
    index_id: str,
    authenticated: Annotated[bool, Depends(verify_token)],
    index_manager: Annotated[IndexManager, Depends(get_index_manager)],
    s3_client: Annotated["S3Client", Depends(get_s3_client)]
) -> DeleteResponse:
    """Delete a video index and all related assets.
    
    This endpoint deletes an index and removes all associated data:
    - All video files from S3 (videos/{index_id}/*)
    - All thumbnail files from S3 (thumbnails/{index_id}/*)
    - All embedding job records
    - Vector index from S3 Vectors
    - Index metadata
    
    The operation cannot be undone.
    
    Args:
        index_id: ID of the index to delete
        authenticated: Authentication verification (injected)
        index_manager: IndexManager instance (injected)
        s3_client: S3Client instance for deleting S3 assets (injected)
        
    Returns:
        DeleteResponse: Deletion confirmation
        
    Raises:
        HTTPException: 401 if not authenticated
        HTTPException: 404 if index not found
        HTTPException: 500 if deletion fails
        
    Validates: Requirements 1.3
    """
    try:
        await index_manager.delete_index(index_id, s3_client=s3_client)
        
        return DeleteResponse(
            message="Index and all related assets deleted successfully",
            deleted_id=index_id
        )
        
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AWSServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete index: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete index: {str(e)}"
        )


@router.get(
    "/{index_id}/videos",
    response_model=VideoListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "List of videos retrieved successfully",
            "model": VideoListResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Index not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="List videos in an index",
    description="Retrieve all videos in the specified index with their metadata"
)
async def list_videos(
    index_id: str,
    authenticated: Annotated[bool, Depends(verify_token)],
    index_manager: Annotated[IndexManager, Depends(get_index_manager)],
    video_service: Annotated[VideoService, Depends(get_video_service)]
) -> VideoListResponse:
    """List all videos in an index.
    
    This endpoint returns all videos in the specified index with their
    metadata including duration, upload time, and embedding IDs.
    
    Args:
        index_id: ID of the index
        authenticated: Authentication verification (injected)
        index_manager: IndexManager instance (injected)
        video_service: VideoService instance (injected)
        
    Returns:
        VideoListResponse: List of videos with metadata
        
    Raises:
        HTTPException: 401 if not authenticated
        HTTPException: 404 if index not found
        HTTPException: 500 if listing fails
        
    Validates: Requirements 1.5
    """
    try:
        # Get index to ensure it exists and get its name
        index = await index_manager.get_index(index_id)
        
        # List videos in the index
        videos = await index_manager.list_videos_in_index(index_id)
        
        return VideoListResponse(
            videos=[_video_to_response(video, video_service) for video in videos],
            total=len(videos),
            index_id=index_id,
            index_name=index.name
        )
        
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list videos: {str(e)}"
        )


@router.post(
    "/{index_id}/videos",
    response_model=VideoUploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Video uploaded successfully",
            "model": VideoUploadResponse
        },
        400: {
            "description": "Invalid video file or format",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Index not found",
            "model": ErrorResponse
        },
        413: {
            "description": "File too large",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Upload video to index",
    description="Upload a video file to the specified index. Supported formats: mp4, mov, avi, mkv. Maximum size: 5GB."
)
async def upload_video(
    index_id: str,
    file: Annotated[UploadFile, File(description="Video file to upload")],
    authenticated: Annotated[bool, Depends(verify_token)],
    index_manager: Annotated[IndexManager, Depends(get_index_manager)],
    video_service: Annotated[VideoService, Depends(get_video_service)]
) -> VideoUploadResponse:
    """Upload a video file to an index.
    
    This endpoint uploads a video file to S3, generates embeddings using
    the Marengo model, and adds the video to the specified index.
    
    Supported formats: mp4, mov, avi, mkv
    Maximum file size: 5GB
    
    Args:
        index_id: ID of the index to add the video to
        file: Video file to upload
        authenticated: Authentication verification (injected)
        index_manager: IndexManager instance (injected)
        video_service: VideoService instance (injected)
        
    Returns:
        VideoUploadResponse: Uploaded video information
        
    Raises:
        HTTPException: 400 if file format is invalid
        HTTPException: 401 if not authenticated
        HTTPException: 404 if index not found
        HTTPException: 413 if file is too large
        HTTPException: 500 if upload fails
        
    Validates: Requirements 1.4
    """
    try:
        # Validate file format
        valid_extensions = ['.mp4', '.mov', '.avi', '.mkv']
        filename = file.filename
        
        if not any(filename.lower().endswith(ext) for ext in valid_extensions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported video format. Supported formats: {', '.join(valid_extensions)}"
            )
        
        # Check file size (5GB limit)
        # Note: This is a basic check. In production, you might want to
        # stream the file and check size during upload
        max_size = 5 * 1024 * 1024 * 1024  # 5GB in bytes
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Maximum video size is 5GB"
            )
        
        # Reset file pointer for reading
        await file.seek(0)
        
        # Add video to index
        # Pass the file object and S3 client to index manager
        from io import BytesIO
        file_obj = BytesIO(file_content)
        
        video = await index_manager.add_video_to_index(
            index_id=index_id,
            video_file=file_obj,
            filename=filename,
            s3_client=video_service.s3
        )
        
        return VideoUploadResponse(
            video=_video_to_response(video, video_service),
            message="Video uploaded successfully"
        )
        
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except AWSServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload video: {str(e)}"
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like 413)
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload video: {str(e)}"
        )


class BackfillResponse(BaseModel):
    """Response model for metadata backfill operation.
    
    Attributes:
        message: Success message
        results: Backfill results with counts
    """
    message: str
    results: dict


@router.post(
    "/{index_id}/videos/backfill-metadata",
    response_model=BackfillResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Metadata backfill completed",
            "model": BackfillResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Index not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    },
    summary="Backfill video metadata",
    description="Update metadata for videos that were uploaded before thumbnail and duration extraction was implemented"
)
async def backfill_video_metadata(
    index_id: str,
    authenticated: Annotated[bool, Depends(verify_token)],
    index_manager: Annotated[IndexManager, Depends(get_index_manager)],
    video_service: Annotated[VideoService, Depends(get_video_service)]
) -> BackfillResponse:
    """Backfill missing metadata for videos in an index.
    
    This endpoint updates videos that were uploaded before thumbnail and
    duration extraction was implemented. It extracts duration and generates
    thumbnails for all videos missing this metadata.
    
    Args:
        index_id: ID of the index
        authenticated: Authentication verification (injected)
        index_manager: IndexManager instance (injected)
        video_service: VideoService instance (injected)
        
    Returns:
        BackfillResponse: Backfill results
        
    Raises:
        HTTPException: 401 if not authenticated
        HTTPException: 404 if index not found
        HTTPException: 500 if backfill fails
    """
    try:
        results = await index_manager.backfill_video_metadata(
            index_id=index_id,
            s3_client=video_service.s3
        )
        
        return BackfillResponse(
            message=f"Backfill completed: {results['updated']} updated, {results['skipped']} skipped, {results['failed']} failed",
            results=results
        )
        
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to backfill metadata: {str(e)}"
        )
