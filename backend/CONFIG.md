# Configuration Guide

This document describes all configuration options for the TL-Video-Playground backend system.

## Table of Contents

- [Configuration File Format](#configuration-file-format)
- [Core Configuration](#core-configuration)
- [Embedding Job Processor Configuration](#embedding-job-processor-configuration)
- [Configuration Examples](#configuration-examples)
- [Environment-Specific Configuration](#environment-specific-configuration)
- [Validation and Error Handling](#validation-and-error-handling)

## Configuration File Format

Configuration is stored in YAML files located in the project root:
- `config.local.yaml` - Local development configuration
- `config.prod.yaml` - Production configuration

The system automatically loads the appropriate file based on the `ENVIRONMENT` environment variable (defaults to `local`).

## Core Configuration

### AWS and Model Settings

#### `marengo_model_id`
- **Type**: String (required)
- **Description**: TwelveLabs Marengo model identifier for video embedding generation
- **Default**: None (must be specified)
- **Example**: `"twelvelabs.marengo-embed-3-0-v1:0"`
- **When to adjust**: Only change if TwelveLabs releases a new Marengo model version

#### `pegasus_model_id`
- **Type**: String (required)
- **Description**: TwelveLabs Pegasus model identifier for video analysis
- **Default**: None (must be specified)
- **Example**: `"twelvelabs.pegasus-1-2-v1:0"`
- **When to adjust**: Only change if TwelveLabs releases a new Pegasus model version

#### `inference_profile_prefix`
- **Type**: String
- **Description**: Prefix for cross-region inference profiles (enables routing to different AWS regions)
- **Default**: `"us"`
- **Valid values**: `"us"`, `"eu"`, or other AWS region prefixes
- **Example**: `"eu"`
- **When to adjust**: Set based on your primary AWS region for optimal latency

#### `aws_region`
- **Type**: String (required)
- **Description**: AWS region for all services (Bedrock, S3, S3 Vectors)
- **Default**: None (must be specified)
- **Valid format**: Standard AWS region codes (e.g., `us-east-1`, `eu-west-1`)
- **Example**: `"eu-west-1"`
- **When to adjust**: Set to your preferred AWS region based on data residency and latency requirements

### Storage Configuration

#### `s3_bucket_name`
- **Type**: String (required)
- **Description**: S3 bucket name for video file storage
- **Default**: None (must be specified)
- **Example**: `"tl-video-playground-local"`
- **When to adjust**: Use different buckets for different environments (local, staging, production)

#### `s3_vectors_collection`
- **Type**: String (required)
- **Description**: Bedrock S3 Vectors collection name for storing video embeddings
- **Default**: None (must be specified)
- **Example**: `"video-embeddings-local"`
- **When to adjust**: Use different collections for different environments to isolate data

### System Limits

#### `max_indexes`
- **Type**: Integer
- **Description**: Maximum number of video indexes that can be created
- **Default**: `3`
- **Valid range**: 1-10
- **Example**: `3`
- **When to adjust**: 
  - Increase for larger deployments with more organizational needs
  - Decrease to limit resource usage in constrained environments
  - Consider cost implications (each index creates separate S3 Vectors resources)

### Authentication

#### `auth_password_hash`
- **Type**: String (required)
- **Description**: Bcrypt hash of the authentication password
- **Default**: None (must be specified)
- **Example**: `"$2b$12$Jy5OXu9k.cKJOsoEc5lx0ehg/jdDK0GGyofG68ABAt3Dbw8BGaXIq"` (hash of "test123")
- **When to adjust**: Generate a new hash when changing the password using bcrypt

### Environment Settings

#### `environment`
- **Type**: String
- **Description**: Environment name for logging and configuration selection
- **Default**: `"local"`
- **Valid values**: `"local"`, `"production"`, or custom environment names
- **Example**: `"local"`
- **When to adjust**: Set to match your deployment environment

#### `use_localstack`
- **Type**: Boolean
- **Description**: Whether to use LocalStack for AWS services (local development only)
- **Default**: `false`
- **Example**: `false`
- **When to adjust**: Set to `true` only for local development with LocalStack

## Embedding Job Processor Configuration

The embedding job processor is a background worker that monitors async video embedding jobs, retrieves completed embeddings, and stores them in S3 Vectors to enable video search functionality.

### Configuration Section

All embedding processor settings are nested under the `embedding_processor` key:

```yaml
embedding_processor:
  enabled: true
  polling_interval: 30
  max_concurrent_jobs: 5
  max_retries: 3
  retry_backoff_base: 2
```

### Configuration Options

#### `embedding_processor.enabled`
- **Type**: Boolean
- **Description**: Master switch to enable or disable the embedding job processor
- **Default**: `true`
- **Example**: `true`
- **When to adjust**:
  - Set to `false` to temporarily disable background processing (e.g., during maintenance)
  - Keep `true` in production to ensure videos become searchable
  - Disable in test environments where you don't want automatic processing

#### `embedding_processor.polling_interval`
- **Type**: Integer (seconds)
- **Description**: How often the processor checks for job status updates
- **Default**: `30` seconds
- **Valid range**: 1-3600 seconds (1 second to 1 hour)
- **Example**: `30`
- **When to adjust**:
  - **Decrease (10-20 seconds)**: For faster embedding availability in production with high video upload rates
  - **Increase (60-300 seconds)**: To reduce AWS API calls and costs in low-traffic environments
  - **Considerations**:
    - Lower values = faster search availability but more API calls
    - Higher values = reduced costs but longer wait for search functionality
    - Bedrock embedding jobs typically take 2-10 minutes, so very low values (<10s) provide minimal benefit

#### `embedding_processor.max_concurrent_jobs`
- **Type**: Integer
- **Description**: Maximum number of embedding jobs to process simultaneously
- **Default**: `5`
- **Valid range**: 1-20
- **Example**: `5`
- **When to adjust**:
  - **Increase (10-20)**: For high-volume production environments with many concurrent video uploads
  - **Decrease (1-3)**: To limit resource usage and AWS API throttling in constrained environments
  - **Considerations**:
    - Higher values enable faster processing of multiple videos
    - Each concurrent job makes S3 and Bedrock API calls
    - Consider AWS service quotas and rate limits
    - Monitor memory usage with higher concurrency

#### `embedding_processor.max_retries`
- **Type**: Integer
- **Description**: Maximum number of retry attempts for failed embedding jobs
- **Default**: `3`
- **Valid range**: 0-10
- **Example**: `3`
- **When to adjust**:
  - **Increase (5-10)**: For environments with intermittent network issues or AWS service throttling
  - **Decrease (1-2)**: To fail fast and alert on persistent issues
  - **Set to 0**: To disable retries entirely (not recommended for production)
  - **Considerations**:
    - Each retry uses exponential backoff (see `retry_backoff_base`)
    - Failed jobs after max retries are marked as permanently failed
    - Higher values increase resilience but delay failure detection

#### `embedding_processor.retry_backoff_base`
- **Type**: Integer
- **Description**: Base multiplier for exponential backoff calculation between retries
- **Default**: `2`
- **Valid range**: 1-10
- **Example**: `2`
- **Formula**: `delay = retry_backoff_base ^ retry_count` minutes
- **When to adjust**:
  - **Increase (3-5)**: For longer delays between retries to handle rate limiting
  - **Decrease (1)**: For linear backoff instead of exponential (not recommended)
  - **Considerations**:
    - With base=2: 1st retry after 2 min, 2nd after 4 min, 3rd after 8 min
    - With base=3: 1st retry after 3 min, 2nd after 9 min, 3rd after 27 min
    - Higher values reduce API pressure but increase time to recovery

### Retry Behavior Example

With default settings (`max_retries=3`, `retry_backoff_base=2`):

1. **Initial attempt**: Job fails
2. **Retry 1**: Wait 2 minutes (2^1), then retry
3. **Retry 2**: Wait 4 minutes (2^2), then retry
4. **Retry 3**: Wait 8 minutes (2^3), then retry
5. **Final state**: If still failing, mark as permanently failed

Total time before permanent failure: ~14 minutes

## Configuration Examples

### Local Development

```yaml
# config.local.yaml
marengo_model_id: "twelvelabs.marengo-embed-3-0-v1:0"
pegasus_model_id: "twelvelabs.pegasus-1-2-v1:0"
inference_profile_prefix: "us"
aws_region: "us-east-1"
s3_bucket_name: "tl-video-playground-local"
s3_vectors_collection: "video-embeddings-local"
max_indexes: 3
auth_password_hash: "$2b$12$Jy5OXu9k.cKJOsoEc5lx0ehg/jdDK0GGyofG68ABAt3Dbw8BGaXIq"
environment: "local"
use_localstack: false

embedding_processor:
  enabled: true
  polling_interval: 30
  max_concurrent_jobs: 5
  max_retries: 3
  retry_backoff_base: 2
```

### Production - High Volume

For production environments with high video upload rates:

```yaml
# config.prod.yaml
marengo_model_id: "twelvelabs.marengo-embed-3-0-v1:0"
pegasus_model_id: "twelvelabs.pegasus-1-2-v1:0"
inference_profile_prefix: "us"
aws_region: "us-east-1"
s3_bucket_name: "tl-video-playground-prod"
s3_vectors_collection: "video-embeddings-prod"
max_indexes: 10
auth_password_hash: "$2b$12$PRODUCTION_HASH_HERE"
environment: "production"
use_localstack: false

embedding_processor:
  enabled: true
  polling_interval: 15  # Check more frequently
  max_concurrent_jobs: 15  # Process more jobs simultaneously
  max_retries: 5  # More retries for reliability
  retry_backoff_base: 2
```

### Production - Cost Optimized

For production environments prioritizing cost over speed:

```yaml
# config.prod.yaml
marengo_model_id: "twelvelabs.marengo-embed-3-0-v1:0"
pegasus_model_id: "twelvelabs.pegasus-1-2-v1:0"
inference_profile_prefix: "eu"
aws_region: "eu-west-1"
s3_bucket_name: "tl-video-playground-prod"
s3_vectors_collection: "video-embeddings-prod"
max_indexes: 5
auth_password_hash: "$2b$12$PRODUCTION_HASH_HERE"
environment: "production"
use_localstack: false

embedding_processor:
  enabled: true
  polling_interval: 120  # Check every 2 minutes (fewer API calls)
  max_concurrent_jobs: 3  # Lower concurrency
  max_retries: 3
  retry_backoff_base: 3  # Longer backoff delays
```

### Testing/Staging

For testing environments where you want manual control:

```yaml
# config.staging.yaml
marengo_model_id: "twelvelabs.marengo-embed-3-0-v1:0"
pegasus_model_id: "twelvelabs.pegasus-1-2-v1:0"
inference_profile_prefix: "us"
aws_region: "us-east-1"
s3_bucket_name: "tl-video-playground-staging"
s3_vectors_collection: "video-embeddings-staging"
max_indexes: 3
auth_password_hash: "$2b$12$STAGING_HASH_HERE"
environment: "staging"
use_localstack: false

embedding_processor:
  enabled: false  # Disable automatic processing for manual testing
  polling_interval: 60
  max_concurrent_jobs: 2
  max_retries: 1
  retry_backoff_base: 2
```

## Environment-Specific Configuration

### Loading Configuration

The system automatically loads configuration based on the `ENVIRONMENT` environment variable:

```bash
# Load config.local.yaml (default)
python main.py

# Load config.prod.yaml
ENVIRONMENT=prod python main.py

# Load custom configuration file
python main.py --config config.custom.yaml
```

### Configuration Precedence

1. Command-line argument (`--config`)
2. Environment variable (`ENVIRONMENT`)
3. Default (`config.local.yaml`)

## Validation and Error Handling

### Automatic Validation

The configuration system automatically validates all settings on startup:

- **Required fields**: Must be present and non-empty
- **Type checking**: Values must match expected types (string, integer, boolean)
- **Range validation**: Numeric values must be within valid ranges
- **Format validation**: AWS regions, model IDs must follow expected formats

### Common Validation Errors

#### Missing Required Field
```
ValueError: Field required [type=missing, input_value={...}, input_type=dict]
```
**Solution**: Add the missing field to your configuration file

#### Invalid Range
```
ValueError: Input should be greater than or equal to 1 [type=greater_than_equal, input_value=0]
```
**Solution**: Adjust the value to be within the valid range

#### Invalid AWS Region
```
ValueError: AWS region must be a valid region code (e.g., us-east-1)
```
**Solution**: Use a valid AWS region code

#### Malformed YAML
```
ValueError: Invalid YAML in configuration file: ...
```
**Solution**: Check YAML syntax (indentation, colons, quotes)

### Configuration File Not Found

If the configuration file is missing:
```
FileNotFoundError: Configuration file not found: config.local.yaml
```

**Solution**: Create the configuration file or specify a different file:
```bash
cp config.prod.yaml.example config.local.yaml
# Edit config.local.yaml with your settings
```

## Monitoring and Observability

### Logging

The embedding processor logs all important events:

```python
# Job processing started
INFO: Processing job abc123 for video video_456

# Job completed successfully
INFO: Job abc123 completed, stored 150 embeddings

# Job failed with retry
WARNING: Job abc123 retry 1/3: Bedrock API throttling

# Job permanently failed
ERROR: Job abc123 permanently failed: Max retries exceeded
```

### Metrics to Monitor

When running in production, monitor these metrics:

1. **Jobs Pending**: Number of jobs waiting to be processed
2. **Jobs Processing**: Number of jobs currently being processed
3. **Jobs Completed**: Total successful completions
4. **Jobs Failed**: Total permanent failures
5. **Average Completion Time**: Time from job creation to completion
6. **Retry Rate**: Percentage of jobs requiring retries

### Health Checks

The system provides health check endpoints:

```bash
# Check if embedding processor is running
curl http://localhost:8000/health

# Response includes processor status
{
  "status": "healthy",
  "embedding_processor": {
    "enabled": true,
    "pending_jobs": 3,
    "processing_jobs": 2
  }
}
```

## Troubleshooting

### Videos Not Becoming Searchable

**Symptoms**: Videos upload successfully but search returns no results

**Possible causes**:
1. Embedding processor is disabled
2. Jobs are failing silently
3. Polling interval is too long

**Solutions**:
1. Check `embedding_processor.enabled` is `true`
2. Check logs for error messages
3. Reduce `polling_interval` for faster processing
4. Verify AWS credentials and permissions

### High AWS Costs

**Symptoms**: Unexpected AWS bills

**Possible causes**:
1. Polling interval too low (excessive API calls)
2. Too many concurrent jobs
3. Excessive retries

**Solutions**:
1. Increase `polling_interval` to 60-120 seconds
2. Reduce `max_concurrent_jobs` to 3-5
3. Review `max_retries` and `retry_backoff_base`
4. Monitor CloudWatch metrics for API call patterns

### Jobs Stuck in Pending State

**Symptoms**: Jobs never complete or fail

**Possible causes**:
1. Bedrock API issues
2. Network connectivity problems
3. Invalid job ARNs

**Solutions**:
1. Check AWS service health dashboard
2. Verify network connectivity to AWS
3. Review job logs for specific errors
4. Manually check job status in AWS console

### Memory Issues

**Symptoms**: Application crashes or slows down

**Possible causes**:
1. Too many concurrent jobs
2. Large embedding files
3. Memory leaks

**Solutions**:
1. Reduce `max_concurrent_jobs`
2. Monitor memory usage with CloudWatch
3. Restart application periodically
4. Review logs for memory-related errors

## Best Practices

### Production Deployment

1. **Use separate configurations**: Maintain distinct config files for each environment
2. **Secure sensitive data**: Store `auth_password_hash` in AWS Secrets Manager
3. **Monitor metrics**: Set up CloudWatch alarms for job failures
4. **Test configuration changes**: Validate in staging before production
5. **Document customizations**: Keep notes on why you changed default values

### Performance Tuning

1. **Start with defaults**: Use default values initially
2. **Monitor and adjust**: Change settings based on observed behavior
3. **Test incrementally**: Change one setting at a time
4. **Consider trade-offs**: Balance speed, cost, and reliability

### Security

1. **Rotate passwords**: Change `auth_password_hash` regularly
2. **Use IAM roles**: Don't store AWS credentials in config files
3. **Encrypt at rest**: Enable S3 bucket encryption
4. **Audit access**: Review CloudTrail logs regularly

## Additional Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [TwelveLabs Model Documentation](https://www.twelvelabs.io/)
- [FastAPI Configuration Guide](https://fastapi.tiangolo.com/)
- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

## Support

For configuration issues:
1. Check this documentation
2. Review application logs
3. Consult AWS documentation
4. Open an issue on GitHub

---

**Last Updated**: March 2026
**Version**: 1.0
