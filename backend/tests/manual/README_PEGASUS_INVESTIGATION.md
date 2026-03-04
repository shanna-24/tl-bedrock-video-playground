# Pegasus Single Video Analysis Investigation

This directory contains manual tests to investigate why single video analysis produces limited results and to validate whether the Jockey orchestration approach provides better coverage.

## Background

**Observation**: Single video analysis appears to produce limited results and focus on the start of the video, while "Entire Index" analysis (even for a single video) works much better.

**Hypothesis**: The issue could be due to:
1. Pegasus output token limits (max 4096 tokens)
2. Model behavior with longer videos
3. Prompt design not encouraging comprehensive analysis
4. Lack of semantic search to find relevant segments throughout the video

## Test Scripts

### 1. `test_pegasus_single_video_analysis.py`

Investigates Pegasus behavior with different prompts and video lengths.

**What it tests:**
- Simple summarization queries
- Queries about the end of the video
- Comprehensive analysis with max tokens
- Specific timestamp queries
- Impact of video duration on analysis quality

**Run:**
```bash
# Option 1: Run directly (auto-detects config.local.yaml)
python backend/tests/manual/test_pegasus_single_video_analysis.py

# Option 2: Specify config path explicitly
CONFIG_PATH=config.local.yaml python backend/tests/manual/test_pegasus_single_video_analysis.py

# Option 3: From backend directory
cd backend
python tests/manual/test_pegasus_single_video_analysis.py
```

**What to look for:**
- Does `finishReason` show 'length' (truncation)?
- Do queries about the end of the video provide accurate information?
- Does comprehensive analysis cover the entire video?
- Is there evidence of focusing on beginning vs. end?

### 2. `test_jockey_vs_direct_comparison.py`

Compares direct Pegasus invocation vs Jockey orchestration for the same video and query.

**What it tests:**
- Side-by-side comparison of both approaches
- Output length and quality differences
- Coverage of video content (beginning, middle, end)
- Multiple query types to test consistency

**Run:**
```bash
# Option 1: Run directly (auto-detects config.local.yaml)
python backend/tests/manual/test_jockey_vs_direct_comparison.py

# Option 2: Specify config path explicitly
CONFIG_PATH=config.local.yaml python backend/tests/manual/test_jockey_vs_direct_comparison.py

# Option 3: From backend directory
cd backend
python tests/manual/test_jockey_vs_direct_comparison.py
```

**What to look for:**
- Does Jockey provide more comprehensive coverage?
- Does Jockey mention content from throughout the video?
- Is the Jockey output more detailed and relevant?
- Did Direct Pegasus hit the token limit?

## Prerequisites

1. **Configuration**: Ensure `config.local.yaml` is properly configured with:
   - AWS credentials
   - S3 bucket name
   - Bedrock model IDs
   - Jockey enabled: `jockey.enabled: true`

2. **Test Video**: You'll need:
   - A video uploaded to S3
   - The video's S3 URI
   - The video indexed with embeddings (for Jockey test)
   - The video's ID and parent index ID

3. **Dependencies**: Install required packages:
   ```bash
   pip install boto3 pydantic pyyaml
   ```

## Running the Tests

### Quick Start

1. Upload a test video and note its details:
   ```
   Video ID: abc-123
   S3 URI: s3://your-bucket/videos/index-id/video-id/video.mp4
   Index ID: index-456
   ```

2. Run the investigation test:
   ```bash
   python backend/tests/manual/test_pegasus_single_video_analysis.py
   ```

3. Run the comparison test:
   ```bash
   python backend/tests/manual/test_jockey_vs_direct_comparison.py
   ```

### Interpreting Results

#### Evidence of Token Limit Issues
- `finishReason: 'length'` in Pegasus responses
- Abrupt ending in analysis text
- Incomplete coverage of video content

#### Evidence of Model Behavior Issues
- Vague or generic responses about end of video
- Detailed beginning but shallow end coverage
- Inability to answer specific timestamp queries

#### Evidence of Prompt Design Issues
- Inconsistent results with different prompt phrasings
- Better results with more explicit instructions
- Improved coverage with structured prompts

#### Evidence Jockey Helps
- More comprehensive coverage in Jockey results
- Mentions of content from throughout the video
- Better answers to specific queries
- No truncation issues

## Expected Outcomes

### If Token Limit is the Issue
- Direct Pegasus will show `finishReason: 'length'`
- Jockey will provide longer, more complete analysis
- Longer videos will be more affected

### If Model Behavior is the Issue
- Queries about end of video will be vague/generic
- Jockey will show better coverage through multi-segment analysis
- Specific timestamp queries will work better with Jockey

### If Prompt Design is the Issue
- Different prompt phrasings will show significant variation
- Both approaches may improve with better prompts
- Structured prompts will help both approaches

### If Semantic Search is Key
- Jockey will find relevant segments throughout video
- Direct Pegasus will miss relevant content not at beginning
- Query-specific results will be better with Jockey

## Documenting Results

After running tests, document your findings:

1. **Video Details**:
   - Duration
   - Content type
   - File size

2. **Test Results**:
   - Which queries hit token limits?
   - Which approach provided better coverage?
   - Were there accuracy differences?

3. **Conclusions**:
   - What is the root cause of limited results?
   - Does Jockey solve the problem?
   - Are there other improvements needed?

## Next Steps

Based on test results:

1. **If token limit is the issue**: Jockey approach is validated
2. **If model behavior is the issue**: Consider additional prompt engineering
3. **If prompt design is the issue**: Improve prompts for both approaches
4. **If semantic search is key**: Validate Jockey is the right solution

## Troubleshooting

### "No module named 'config'"
- Ensure you're running from the `backend` directory
- Check that `CONFIG_PATH` environment variable is set

### "Video not found" or "Index not found"
- Verify the video is uploaded and indexed
- Check that embeddings have been generated
- Confirm the IDs are correct

### "Jockey is disabled"
- Set `jockey.enabled: true` in `config.local.yaml`
- Restart the application if running

### "Search service not available"
- Ensure embeddings are indexed for the video
- Check S3 Vectors configuration
- Verify the index exists

## References

- [Pegasus Model Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-pegasus.html)
- Pegasus Limits:
  - Max video: 1 hour, < 2GB
  - Max input prompt: 2000 tokens
  - Max output: 4096 tokens
