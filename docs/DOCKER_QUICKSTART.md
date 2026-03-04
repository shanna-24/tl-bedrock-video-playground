# Docker Quickstart Guide

This guide explains how to run the TL-Video-Playground application from a pre-built Docker container.

## Prerequisites

1. **Docker** installed and running
2. **AWS Account** with the following:
   - AWS Access Key ID and Secret Access Key
   - Bedrock model access enabled for TwelveLabs models
   - An S3 bucket for video storage
   - An S3 Vector bucket (same name as S3 bucket)

## Setup Steps

### 1. Load the Docker Image

If you received the application as a `.tar.gz` file, load it into Docker:

```bash
docker load < tl-video-playground.tar.gz
```

This will import the `tl-video-playground:latest` image into your local Docker registry.

### 2. Create AWS Resources

If you don't already have them, create the required AWS resources:

```bash
# Set your preferred region
export AWS_REGION=us-east-1

# Create S3 bucket for video storage
aws s3 mb s3://your-bucket-name --region $AWS_REGION

# Create S3 Vector bucket (required for video search)
aws s3vectors create-vector-bucket \
  --vector-bucket-name your-bucket-name \
  --region $AWS_REGION
```

### 3. Enable Bedrock Model Access

1. Go to [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Navigate to **Model access**
3. Request access to:
   - `twelvelabs.marengo-embed-3-0-v1:0` (video embeddings)
   - `twelvelabs.pegasus-1-2-v1:0` (video analysis)
4. Wait for approval (usually instant)

### 4. Create Configuration File

Create a `config.yaml` file with your settings:

```yaml
# config.yaml
marengo_model_id: "twelvelabs.marengo-embed-3-0-v1:0"
pegasus_model_id: "twelvelabs.pegasus-1-2-v1:0"
inference_profile_prefix: "us"
aws_region: "us-east-1"
s3_bucket_name: "your-bucket-name"
max_indexes: 5
auth_password_hash: "$2b$12$YOUR_BCRYPT_HASH_HERE"
environment: "production"

logging:
  file_logging_enabled: true
  level: "INFO"

theme:
  default_mode: "dark"

jockey:
  enabled: true
  claude_model_id: "anthropic.claude-sonnet-4-5-20250929-v1:0"
  max_segments_per_query: 10
  max_search_results: 15
  parallel_analysis_limit: 5
  search_cache_ttl: 300
  claude_temperature: 0.7
  claude_max_tokens: 4096
  web_search_enabled: false

embedding_processor:
  enabled: true
  polling_interval: 30
  max_concurrent_jobs: 5
  max_retries: 3
  retry_backoff_base: 2
```

### 5. Generate Password Hash

Generate a bcrypt hash for your login password:

```bash
# Using Python
python3 -c 'import bcrypt; print(bcrypt.hashpw("YOUR_PASSWORD".encode(), bcrypt.gensalt()).decode())'
```

Replace `$2b$12$YOUR_BCRYPT_HASH_HERE` in config.yaml with the generated hash.

### 6. Run the Container

Run the Docker container with your AWS credentials and config:

```bash
docker run -d \
  --name tl-video-playground \
  -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID="your-access-key" \
  -e AWS_SECRET_ACCESS_KEY="your-secret-key" \
  -e AWS_REGION="us-east-1" \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -e CONFIG_PATH=/app/config.yaml \
  tl-video-playground:latest
```

Or mount your AWS credentials file:

```bash
docker run -d \
  --name tl-video-playground \
  -p 8000:8000 \
  -v ~/.aws:/root/.aws:ro \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -e CONFIG_PATH=/app/config.yaml \
  tl-video-playground:latest
```

### 7. Access the Application

Open your browser and navigate to:

- **Application**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

Log in with the password you configured in step 5.

## What Happens on First Run

When the container starts for the first time:

1. The backend initializes and connects to AWS
2. Compliance configuration files are automatically uploaded to S3 (if not already present)
3. The embedding job processor starts monitoring for video uploads
4. The application is ready to use

## Verify Setup

Check that everything is working:

```bash
# Check container logs
docker logs tl-video-playground

# Test health endpoint
curl http://localhost:8000/health
```

Expected health response:
```json
{
  "status": "healthy",
  "environment": "production",
  "version": "1.0.0"
}
```

## Troubleshooting

### Container won't start

Check logs for errors:
```bash
docker logs tl-video-playground
```

Common issues:
- Invalid config.yaml syntax
- Missing AWS credentials
- Incorrect S3 bucket name

### AWS connection errors

Verify your credentials:
```bash
# Test AWS access
docker run --rm \
  -e AWS_ACCESS_KEY_ID="your-key" \
  -e AWS_SECRET_ACCESS_KEY="your-secret" \
  amazon/aws-cli sts get-caller-identity
```

### Bedrock model access denied

Ensure you've requested and received access to the TwelveLabs models in the Bedrock console.

### S3 Vector bucket not found

Create the S3 Vector bucket:
```bash
aws s3vectors create-vector-bucket \
  --vector-bucket-name your-bucket-name \
  --region us-east-1
```

## Stopping the Container

```bash
docker stop tl-video-playground
docker rm tl-video-playground
```

## Removing the Docker Image

To completely remove the application from your system:

```bash
docker rmi tl-video-playground:latest
```

If the container is still running, stop and remove it first, then remove the image.

## Data Persistence

By default, application data (indexes, job records) is stored in S3, so it persists across container restarts. Video files and embeddings are also stored in S3.

To persist local logs, mount a volume:

```bash
docker run -d \
  --name tl-video-playground \
  -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID="your-key" \
  -e AWS_SECRET_ACCESS_KEY="your-secret" \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -e CONFIG_PATH=/app/config.yaml \
  tl-video-playground:latest
```

## Summary Checklist

- [ ] Docker image loaded (`docker load < tl-video-playground.tar.gz`)
- [ ] AWS account with credentials
- [ ] S3 bucket created
- [ ] S3 Vector bucket created
- [ ] Bedrock model access enabled
- [ ] config.yaml created with your settings
- [ ] Password hash generated
- [ ] Docker container running
- [ ] Application accessible at http://localhost:8000
