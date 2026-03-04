# TL-Video-Playground Backend API Guide

Video archive search and analysis system using TwelveLabs AI models.

**Base URL:** `http://localhost:8000`  
**API Docs:** `/docs` (Swagger UI)

---

## Authentication

All endpoints (except `/health`, `/api/config/*`, and `/api/auth/login`) require a Bearer token in the Authorization header.

### POST /api/auth/login
Authenticate and receive a JWT token.

**Request:**
```json
{
  "password": "your-password"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "message": "Login successful"
}
```

### POST /api/auth/logout
Logout (requires authentication). Client should discard the token.

**Response:**
```json
{
  "message": "Logout successful"
}
```

---

## Health

### GET /health
Basic health check (public).

**Response:**
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "1.0.0"
}
```

### GET /health/processor
Detailed embedding job processor health status.

**Response:**
```json
{
  "status": "healthy",
  "processor_running": true,
  "pending_jobs": 0,
  "processing_jobs": 1,
  "total_pending": 1,
  "jobs_processed": 50,
  "jobs_completed": 48,
  "jobs_failed": 2,
  "jobs_retried": 5,
  "embeddings_stored": 1500,
  "last_poll_time": "2024-01-01T12:00:00",
  "last_job_completion_time": "2024-01-01T11:55:00",
  "metrics": {...},
  "websocket_stats": {...}
}
```

---

## Configuration

### GET /api/config/theme
Get theme configuration (public).

**Response:**
```json
{
  "default_mode": "dark"
}
```

---

## Indexes

### GET /api/indexes
List all video indexes.

**Response:**
```json
{
  "indexes": [
    {
      "id": "idx-abc123",
      "name": "My Videos",
      "created_at": "2024-01-01T12:00:00",
      "video_count": 5,
      "s3_vectors_collection_id": "collection-xyz"
    }
  ],
  "total": 1,
  "max_indexes": 3
}
```

### POST /api/indexes
Create a new index (max 3 allowed).

**Request:**
```json
{
  "name": "My New Index"
}
```

**Response:** `201 Created` with index details.

### DELETE /api/indexes/{index_id}
Delete an index and all associated data (videos, thumbnails, embeddings).

**Response:**
```json
{
  "message": "Index and all related assets deleted successfully",
  "deleted_id": "idx-abc123"
}
```

### GET /api/indexes/{index_id}/videos
List all videos in an index.

**Response:**
```json
{
  "videos": [
    {
      "id": "vid-123",
      "index_id": "idx-abc123",
      "filename": "video.mp4",
      "s3_uri": "s3://bucket/videos/...",
      "duration": 120.5,
      "uploaded_at": "2024-01-01T12:00:00",
      "embedding_ids": ["emb-1", "emb-2"],
      "thumbnail_url": "https://..."
    }
  ],
  "total": 1,
  "index_id": "idx-abc123",
  "index_name": "My Videos"
}
```

### POST /api/indexes/{index_id}/videos
Upload a video to an index.

**Request:** `multipart/form-data` with `file` field  
**Supported formats:** mp4, mov, avi, mkv  
**Max size:** 5GB

**Response:** `201 Created` with video details.

### POST /api/indexes/{index_id}/videos/backfill-metadata
Backfill missing metadata (thumbnails, duration) for existing videos.

**Response:**
```json
{
  "message": "Backfill completed: 3 updated, 2 skipped, 0 failed",
  "results": {
    "updated": 3,
    "skipped": 2,
    "failed": 0
  }
}
```

---

## Videos

### GET /api/videos/{video_id}/stream
Get a presigned URL for video streaming.

**Query Parameters:**
- `start_time` (optional): Start playback at this time in seconds

**Response:**
```json
{
  "video_id": "vid-123",
  "stream_url": "https://s3.amazonaws.com/...",
  "start_timecode": 30.5,
  "expiration": 3600
}
```

### DELETE /api/videos/{video_id}
Delete a video and all related data (S3 file, thumbnail, embeddings, job records).

**Response:**
```json
{
  "message": "Video and all related data deleted successfully",
  "deleted_video_id": "vid-123"
}
```

### GET /api/videos/{video_id}/transcription
Check if transcription is available for a video.

**Response:**
```json
{
  "video_id": "vid-123",
  "has_transcription": true,
  "status": "available"
}
```

---

## Search

### POST /api/search
Search videos using text, image, or both (multimodal).

**Request:**
```json
{
  "index_id": "idx-abc123",
  "query": "person walking on beach",
  "image": "base64-encoded-image-data",
  "image_format": "jpeg",
  "top_k": 10,
  "modalities": ["visual", "audio", "transcription"],
  "generate_screenshots": true
}
```

**Notes:**
- At least one of `query` or `image` must be provided
- `image_format` required when `image` is provided (jpeg, jpg, png, webp)
- `modalities` defaults to all if not specified

**Response:**
```json
{
  "query": "person walking on beach",
  "clips": [
    {
      "video_id": "vid-123",
      "start_timecode": 45.0,
      "end_timecode": 52.0,
      "relevance_score": 0.92,
      "screenshot_url": "https://...",
      "video_stream_url": "https://...",
      "metadata": {
        "transcription": "..."
      }
    }
  ],
  "total_results": 5,
  "search_time": 1.23
}
```

---

## Analysis

### POST /api/analyze/index
Analyze all videos in an index using natural language.

**Request:**
```json
{
  "index_id": "idx-abc123",
  "query": "What are the main themes across these videos?",
  "verbosity": "balanced",
  "temperature": 0.2,
  "max_output_tokens": 2048,
  "correlation_id": "optional-tracking-id"
}
```

**Verbosity options:** `concise`, `balanced`, `extended`

**Response:**
```json
{
  "query": "What are the main themes...",
  "scope": "index",
  "scope_id": "idx-abc123",
  "insights": "The videos primarily focus on...",
  "analyzed_at": "2024-01-01T12:00:00",
  "metadata": {...}
}
```

### POST /api/analyze/video
Analyze a single video using natural language.

**Request:**
```json
{
  "video_id": "vid-123",
  "query": "Summarize the key events in this video",
  "verbosity": "balanced",
  "use_jockey": false,
  "temperature": 0.2,
  "max_output_tokens": 2048,
  "correlation_id": "optional-tracking-id"
}
```

**Response:** Same structure as index analysis.

---

## Video Reel

### POST /api/video-reel/generate
Generate a video reel by concatenating search result clips.

**Request:**
```json
{
  "clips": [
    {
      "video_id": "vid-123",
      "start_timecode": 10.0,
      "end_timecode": 20.0,
      "relevance_score": 0.9,
      "screenshot_url": "...",
      "video_stream_url": "..."
    }
  ]
}
```

**Response:**
```json
{
  "reel_id": "reel-uuid",
  "s3_key": "videos-generated/reel-uuid.mp4",
  "stream_url": "https://...",
  "clip_count": 3
}
```

---

## Embedding Jobs

### GET /api/embedding-jobs
List all embedding jobs.

**Query Parameters:**
- `status` (optional): Filter by status (pending, processing, completed, failed)

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "job-123",
      "invocation_arn": "arn:aws:bedrock:...",
      "video_id": "vid-123",
      "index_id": "idx-abc123",
      "s3_uri": "s3://bucket/videos/...",
      "status": "processing",
      "created_at": "2024-01-01T12:00:00",
      "updated_at": "2024-01-01T12:05:00",
      "retry_count": 0,
      "error_message": null,
      "output_location": null,
      "next_retry_at": null,
      "video_duration": 120.5,
      "progress": {
        "estimated_percent": 45,
        "elapsed_seconds": 60,
        "estimated_remaining_seconds": 73
      }
    }
  ],
  "total": 1
}
```

### GET /api/embedding-jobs/{job_id}
Get details of a specific embedding job.

### POST /api/embedding-jobs/{job_id}/retry
Retry a failed embedding job.

**Response:** Updated job details with status reset to `pending`.

### POST /api/embedding-jobs/{job_id}/cancel
Cancel a running embedding job.

**Response:** Updated job details with status set to `cancelled`.

---

## WebSocket

### WS /ws/notifications
Real-time notifications for embedding job completions.

**Connection Message:**
```json
{
  "type": "connected",
  "message": "Connected to embedding job notifications",
  "timestamp": "2024-01-01T12:00:00.000000"
}
```

**Job Completion Notification:**
```json
{
  "type": "job_completion",
  "job_id": "job-123",
  "video_id": "vid-456",
  "index_id": "idx-789",
  "status": "completed",
  "embeddings_count": 150,
  "error_message": null,
  "timestamp": "2024-01-01T12:05:00.000000"
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing/invalid token)
- `404` - Not Found
- `413` - Payload Too Large (file size exceeded)
- `429` - Too Many Requests (rate limited)
- `500` - Internal Server Error
- `504` - Gateway Timeout
