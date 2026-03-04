# Test Videos Directory

This directory is used for manual and concurrent upload testing of the embedding job processor.

## Purpose

Place test video files here for:
- Manual end-to-end testing
- Concurrent upload testing
- Performance testing
- Integration testing

## Requirements

### Video Format
- **Format**: MP4 (recommended)
- **Duration**: 10-30 seconds (for faster testing)
- **Size**: < 100MB per video
- **Codec**: H.264 video, AAC audio (standard web formats)

### Naming Convention

For automated concurrent testing, name your videos:
```
test-video-1.mp4
test-video-2.mp4
test-video-3.mp4
test-video-4.mp4
test-video-5.mp4
```

For manual testing, any name is acceptable.

## How to Add Test Videos

### Option 1: Copy Existing Videos

```bash
# Copy videos from another location
cp /path/to/your/videos/*.mp4 backend/test_videos/

# Rename for automated testing
mv backend/test_videos/video1.mp4 backend/test_videos/test-video-1.mp4
mv backend/test_videos/video2.mp4 backend/test_videos/test-video-2.mp4
mv backend/test_videos/video3.mp4 backend/test_videos/test-video-3.mp4
```

### Option 2: Download Sample Videos

You can download free sample videos from:
- [Pexels Videos](https://www.pexels.com/videos/) (free stock videos)
- [Pixabay Videos](https://pixabay.com/videos/) (free stock videos)
- [Coverr](https://coverr.co/) (free stock videos)

Example using curl:
```bash
# Download a sample video (replace URL with actual video URL)
curl -o backend/test_videos/test-video-1.mp4 "https://example.com/sample-video.mp4"
```

### Option 3: Create Test Videos

If you have ffmpeg installed, you can create simple test videos:

```bash
# Create a 10-second test video with color bars
ffmpeg -f lavfi -i testsrc=duration=10:size=1280x720:rate=30 \
  -f lavfi -i sine=frequency=1000:duration=10 \
  -c:v libx264 -c:a aac \
  backend/test_videos/test-video-1.mp4

# Create a 15-second test video with different pattern
ffmpeg -f lavfi -i testsrc2=duration=15:size=1280x720:rate=30 \
  -f lavfi -i sine=frequency=500:duration=15 \
  -c:v libx264 -c:a aac \
  backend/test_videos/test-video-2.mp4

# Create a 20-second test video with mandelbrot pattern
ffmpeg -f lavfi -i mandelbrot=duration=20:size=1280x720:rate=30 \
  -f lavfi -i sine=frequency=800:duration=20 \
  -c:v libx264 -c:a aac \
  backend/test_videos/test-video-3.mp4
```

## Usage

### Manual Testing

```bash
# Upload a single video
./scripts/manual_test_helper.sh upload test_videos/test-video-1.mp4

# Or use full path
./scripts/manual_test_helper.sh upload /path/to/your/video.mp4
```

### Concurrent Testing

```bash
# Automated concurrent upload test (requires 3-5 videos)
./scripts/concurrent_upload_test.sh

# Or use manual helper for concurrent uploads
./scripts/manual_test_helper.sh concurrent-upload 3
```

### Custom Video Paths

You can also specify custom video paths without copying to this directory:

```bash
# Using environment variable
VIDEO_FILES="/path/to/video1.mp4,/path/to/video2.mp4,/path/to/video3.mp4" \
  ./scripts/concurrent_upload_test.sh

# Or upload individually
./scripts/manual_test_helper.sh upload /path/to/video1.mp4
./scripts/manual_test_helper.sh upload /path/to/video2.mp4
```

## Recommended Test Videos

For comprehensive testing, use videos with different characteristics:

1. **Short video** (10-15 seconds): Fast processing, quick feedback
2. **Medium video** (30-60 seconds): Typical use case
3. **Different content types**:
   - Talking head / interview
   - Action / sports
   - Nature / landscape
   - Text / presentation

This variety helps test different embedding scenarios.

## Cleanup

Test videos are not tracked by git (see `.gitignore`). To clean up:

```bash
# Remove all test videos
rm backend/test_videos/*.mp4

# Or remove specific videos
rm backend/test_videos/test-video-*.mp4
```

## Notes

- Test videos are excluded from git (see `.gitignore`)
- Keep videos small (< 100MB) for faster uploads
- Use short videos (10-30s) for faster testing cycles
- For production testing, use realistic video content
- Videos are uploaded to S3, so AWS costs apply

## Troubleshooting

### Issue: No test videos found

**Solution**: Add at least 3 videos to this directory with the naming convention `test-video-1.mp4`, `test-video-2.mp4`, etc.

### Issue: Video upload fails

**Possible causes**:
- Invalid video format (use MP4 with H.264/AAC)
- Video too large (> 100MB)
- Corrupted video file

**Solution**: Try a different video or re-encode with ffmpeg:
```bash
ffmpeg -i input.mp4 -c:v libx264 -c:a aac -movflags +faststart output.mp4
```

### Issue: Concurrent test fails to find videos

**Solution**: Ensure you have at least as many videos as specified by `NUM_VIDEOS` (default: 3)

## Related Documentation

- **Concurrent Testing Guide**: `../CONCURRENT_TESTING_GUIDE.md`
- **Manual Testing Guide**: `../MANUAL_TESTING_GUIDE.md`
- **Manual Test Checklist**: `../MANUAL_TEST_CHECKLIST.md`
