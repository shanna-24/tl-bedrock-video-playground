# AWS Production Deployment Guide

This guide provides step-by-step instructions for deploying TL-Video-Playground to AWS production infrastructure.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [Pre-Deployment Checklist](#pre-deployment-checklist)
4. [Deployment Steps](#deployment-steps)
5. [Post-Deployment Configuration](#post-deployment-configuration)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Cost Estimation](#cost-estimation)
9. [Security Best Practices](#security-best-practices)

## Prerequisites

### AWS Account Requirements

1. **AWS Account** with appropriate permissions:
   - IAM permissions to create and manage resources
   - Access to Amazon Bedrock with Marengo and Pegasus models
   - Service quotas sufficient for ECS, S3, CloudFront

2. **AWS CLI** installed and configured:
   ```bash
   aws --version  # Should be 2.x or higher
   aws configure  # Set up credentials
   ```

3. **AWS CDK CLI** installed:
   ```bash
   npm install -g aws-cdk
   cdk --version  # Should be 2.x or higher
   ```

4. **Docker** installed and running:
   ```bash
   docker --version
   docker ps  # Verify Docker daemon is running
   ```

5. **Python 3.11+** for CDK:
   ```bash
   python --version
   ```

6. **Node.js 20+** for frontend build:
   ```bash
   node --version
   npm --version
   ```

### AWS Service Access

Ensure you have access to the following AWS services in your target region:

- **Amazon Bedrock**: Request access to TwelveLabs Marengo and Pegasus models
- **Amazon ECS**: Fargate capacity
- **Amazon S3**: Bucket creation
- **Amazon CloudFront**: Distribution creation
- **AWS Secrets Manager**: Secret storage
- **Amazon ECR**: Container registry

To request Bedrock model access:
1. Go to AWS Console → Amazon Bedrock → Model access
2. Request access to:
   - `twelvelabs.marengo-v1`
   - `twelvelabs.pegasus-v1`
3. Wait for approval (usually instant for most models)

## Architecture Overview

The production deployment consists of three main stacks:

### 1. Storage Stack
- **Video Bucket**: S3 bucket for video storage with lifecycle policies
- **Metadata Bucket**: S3 bucket for index metadata with versioning

### 2. Backend Stack
- **VPC**: 2 AZs with public and private subnets
- **ECS Fargate**: Containerized backend with auto-scaling (2-10 tasks)
- **Application Load Balancer**: HTTPS traffic routing
- **ECR Repository**: Docker image storage
- **IAM Roles**: Permissions for Bedrock, S3, Secrets Manager

### 3. Frontend Stack
- **S3 Bucket**: Static website hosting
- **CloudFront**: Global CDN with HTTPS
- **Origin Access Identity**: Secure S3 access

## Pre-Deployment Checklist

- [ ] AWS account with appropriate permissions
- [ ] AWS CLI configured with credentials
- [ ] CDK CLI installed globally
- [ ] Docker installed and running
- [ ] Bedrock model access approved
- [ ] Target AWS region selected (e.g., us-east-1)
- [ ] Domain name (optional, for custom domain)
- [ ] SSL certificate (optional, for custom domain)
- [ ] Budget alerts configured

## Deployment Steps

### Step 1: Clone and Prepare Repository

```bash
# Clone repository
git clone <repository-url>
cd tl-video-playground

# Verify project structure
ls -la
# Should see: backend/, frontend/, infrastructure/, docs/
```

### Step 2: Configure AWS Credentials

```bash
# Configure AWS CLI
aws configure

# Verify credentials
aws sts get-caller-identity

# Set environment variables
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1  # Change to your preferred region
export PROJECT_NAME=tl-video-playground
export ENVIRONMENT=prod
```

### Step 3: Create AWS Resources

#### Create S3 Bucket

```bash
# Create a bucket for video storage
aws s3 mb s3://your-tl-video-bucket --region us-east-1

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket your-tl-video-bucket \
  --versioning-configuration Status=Enabled
```

#### Create S3 Vector Bucket

The system uses Bedrock S3 Vectors for storing video embeddings. This must be created before deploying:

```bash
# Create S3 Vector bucket (required for index creation)
aws s3vectors create-vector-bucket \
  --vector-bucket-name your-tl-video-bucket \
  --region us-east-1

# Verify it was created
aws s3vectors list-vector-buckets --region us-east-1
```

**Note:** S3 Vector buckets are separate from regular S3 buckets and are required for the video search functionality to work.

### Step 4: Bootstrap AWS CDK

Bootstrap CDK in your AWS account (one-time setup per account/region):

```bash
cdk bootstrap aws://${AWS_ACCOUNT_ID}/${AWS_REGION}
```

This creates:
- S3 bucket for CDK assets
- IAM roles for CloudFormation
- ECR repository for Docker images

### Step 5: Install CDK Dependencies

```bash
cd infrastructure/cdk

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 6: Review and Customize Configuration

Edit `infrastructure/cdk/cdk.json` if needed:

```json
{
  "context": {
    "project_name": "tl-video-playground",
    "environment": "prod",
    "region": "us-east-1"
  }
}
```

Or pass context via command line (recommended):

```bash
export CDK_CONTEXT="--context project_name=${PROJECT_NAME} --context environment=${ENVIRONMENT} --context region=${AWS_REGION}"
```

### Step 7: Synthesize CloudFormation Templates

```bash
# Generate CloudFormation templates
cdk synth ${CDK_CONTEXT}

# Review generated templates
ls cdk.out/
```

### Step 8: Deploy Storage Stack

```bash
# Deploy storage stack first
cdk deploy ${PROJECT_NAME}-storage-${ENVIRONMENT} ${CDK_CONTEXT}

# Confirm deployment when prompted
# Type 'y' and press Enter

# Wait for deployment to complete (2-3 minutes)
```

Save the output values:
- `VideoBucketName`
- `MetadataBucketName`

### Step 9: Deploy Backend Stack

```bash
# Deploy backend stack
cdk deploy ${PROJECT_NAME}-backend-${ENVIRONMENT} ${CDK_CONTEXT}

# Confirm deployment when prompted
# This will take 5-10 minutes
```

Save the output values:
- `LoadBalancerDNS`
- `BackendURL`
- `ECRRepositoryURI`
- `ClusterName`

### Step 10: Create Production Configuration

Before building the Docker image, create a production configuration file:

```bash
cd ../../backend

# Create production config from template
cat > ../config.prod.yaml << 'EOF'
# Production configuration
marengo_model_id: "twelvelabs.marengo-embed-3-0-v1:0"
pegasus_model_id: "twelvelabs.pegasus-1-2-v1:0"
inference_profile_prefix: "us"
aws_region: "us-east-1"
s3_bucket_name: "your-video-bucket-name"  # Update with your bucket
max_indexes: 5
auth_password_hash: "PLACEHOLDER"  # Will be set via Secrets Manager
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
EOF
```

See [Configuration Guide](../backend/CONFIG.md) for detailed configuration options.

### Step 11: Build and Push Backend Docker Image

```bash
# Get ECR repository URI from stack outputs
export ECR_URI=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-backend-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryURI`].OutputValue' \
  --output text)

echo "ECR URI: $ECR_URI"

# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin $ECR_URI

# Build backend Docker image
cd ../../backend
docker build -t ${PROJECT_NAME}-backend:latest -f Dockerfile .

# Tag image for ECR
docker tag ${PROJECT_NAME}-backend:latest ${ECR_URI}:latest

# Push image to ECR
docker push ${ECR_URI}:latest

# Verify image was pushed
aws ecr describe-images --repository-name ${PROJECT_NAME}-backend-${ENVIRONMENT}
```

### Step 12: Update ECS Service

After pushing the Docker image, update the ECS service to use it:

```bash
# Force new deployment to pull latest image
aws ecs update-service \
  --cluster ${PROJECT_NAME}-cluster-${ENVIRONMENT} \
  --service ${PROJECT_NAME}-backend-${ENVIRONMENT} \
  --force-new-deployment

# Wait for service to stabilize (5-10 minutes)
aws ecs wait services-stable \
  --cluster ${PROJECT_NAME}-cluster-${ENVIRONMENT} \
  --services ${PROJECT_NAME}-backend-${ENVIRONMENT}
```

### Step 13: Configure Authentication Secret

```bash
# Generate password hash
export PASSWORD="your_secure_password_here"
export PASSWORD_HASH=$(python -c "from passlib.hash import bcrypt; print(bcrypt.hash('${PASSWORD}'))")

# Update secret in Secrets Manager
aws secretsmanager update-secret \
  --secret-id ${PROJECT_NAME}/${ENVIRONMENT}/auth-password-hash \
  --secret-string "{\"password_hash\":\"${PASSWORD_HASH}\"}"

# Verify secret was updated
aws secretsmanager get-secret-value \
  --secret-id ${PROJECT_NAME}/${ENVIRONMENT}/auth-password-hash \
  --query SecretString --output text
```

**Important**: Save your password securely. You'll need it to log in to the application.

### Step 14: Verify Backend Deployment

```bash
# Get backend URL
export BACKEND_URL=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-backend-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`BackendURL`].OutputValue' \
  --output text)

echo "Backend URL: $BACKEND_URL"

# Test health endpoint
curl ${BACKEND_URL}/health

# Should return: {"status":"healthy"}

# Test API documentation
curl ${BACKEND_URL}/docs
# Should return HTML for Swagger UI
```

### Step 15: Build and Deploy Frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Create production environment file
cat > .env.production << EOF
VITE_API_URL=${BACKEND_URL}
EOF

# Build frontend
npm run build

# Verify build
ls -la dist/
# Should see: index.html, assets/, etc.
```

### Step 16: Deploy Frontend Stack

```bash
cd ../infrastructure/cdk

# Deploy frontend stack
cdk deploy ${PROJECT_NAME}-frontend-${ENVIRONMENT} ${CDK_CONTEXT}

# Confirm deployment when prompted
# This will take 5-10 minutes
```

Save the output values:
- `FrontendBucketName`
- `CloudFrontURL`
- `CloudFrontDistributionId`

### Step 17: Upload Frontend to S3

```bash
# Get S3 bucket name
export FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-frontend-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
  --output text)

echo "Frontend Bucket: $FRONTEND_BUCKET"

# Upload frontend files to S3
cd ../../frontend
aws s3 sync dist/ s3://${FRONTEND_BUCKET}/ --delete

# Verify upload
aws s3 ls s3://${FRONTEND_BUCKET}/
```

### Step 18: Invalidate CloudFront Cache

```bash
# Get CloudFront distribution ID
export DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-frontend-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
  --output text)

echo "Distribution ID: $DISTRIBUTION_ID"

# Create invalidation
aws cloudfront create-invalidation \
  --distribution-id ${DISTRIBUTION_ID} \
  --paths "/*"

# Wait for invalidation to complete (5-10 minutes)
aws cloudfront wait invalidation-completed \
  --distribution-id ${DISTRIBUTION_ID} \
  --id $(aws cloudfront list-invalidations \
    --distribution-id ${DISTRIBUTION_ID} \
    --query 'InvalidationList.Items[0].Id' \
    --output text)
```

### Step 19: Access Your Application

```bash
# Get CloudFront URL
export CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-frontend-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontURL`].OutputValue' \
  --output text)

echo "Application URL: $CLOUDFRONT_URL"
echo "Login with password: $PASSWORD"
```

Open the CloudFront URL in your browser and log in with your password.

## Post-Deployment Configuration

### Upload Compliance Configuration (Auto or Manual)

The compliance configuration files are automatically uploaded to S3 on first startup if they don't already exist. The backend checks for these files and uploads them from `backend/compliance_config/`.

If you want to customize the compliance rules, you can either:

1. **Edit before deployment**: Modify files in `backend/compliance_config/` before building/deploying
2. **Upload manually**: Use the upload script to overwrite with custom configs:

```bash
# From the project root directory
./scripts/upload-compliance-config.sh ${VIDEO_BUCKET_NAME} ${AWS_REGION}
```

Or manually:

```bash
# Get video bucket name from stack outputs
export VIDEO_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name ${PROJECT_NAME}-storage-${ENVIRONMENT} \
  --query 'Stacks[0].Outputs[?OutputKey==`VideoBucketName`].OutputValue' \
  --output text)

# Upload compliance config files
aws s3 cp backend/compliance_config/compliance_params.json \
  s3://${VIDEO_BUCKET}/compliance/configuration/
aws s3 cp backend/compliance_config/moral_standards_check.json \
  s3://${VIDEO_BUCKET}/compliance/configuration/
aws s3 cp backend/compliance_config/video_content_check.json \
  s3://${VIDEO_BUCKET}/compliance/configuration/
aws s3 cp backend/compliance_config/content_relevance_check.json \
  s3://${VIDEO_BUCKET}/compliance/configuration/
```

### Configure Custom Domain (Optional)

If you want to use a custom domain:

1. **Request SSL Certificate** in AWS Certificate Manager:
   ```bash
   aws acm request-certificate \
     --domain-name yourdomain.com \
     --validation-method DNS \
     --region us-east-1  # CloudFront requires us-east-1
   ```

2. **Validate Certificate** by adding DNS records

3. **Update CloudFront Distribution** to use custom domain and certificate

4. **Update Route53** to point to CloudFront distribution

### Configure CORS for Production

Update backend CORS settings to only allow your frontend domain:

1. Edit `backend/src/main.py`
2. Change CORS origins from `["*"]` to `["https://yourdomain.com"]`
3. Rebuild and redeploy backend Docker image

### Enable CloudWatch Alarms

Set up alarms for monitoring:

```bash
# High CPU alarm
aws cloudwatch put-metric-alarm \
  --alarm-name ${PROJECT_NAME}-high-cpu \
  --alarm-description "Alert when CPU exceeds 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# High memory alarm
aws cloudwatch put-metric-alarm \
  --alarm-name ${PROJECT_NAME}-high-memory \
  --alarm-description "Alert when memory exceeds 80%" \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2
```

### Configure Backup Strategy

Enable automated backups for S3 buckets:

```bash
# Enable versioning (already enabled for metadata bucket)
aws s3api put-bucket-versioning \
  --bucket ${FRONTEND_BUCKET} \
  --versioning-configuration Status=Enabled

# Configure lifecycle policy for old versions
# (Already configured in CDK for metadata bucket)
```

## Monitoring and Maintenance

### View Application Logs

```bash
# Backend logs
aws logs tail /ecs/${PROJECT_NAME}-backend-${ENVIRONMENT} --follow

# Filter for errors
aws logs tail /ecs/${PROJECT_NAME}-backend-${ENVIRONMENT} --follow --filter-pattern "ERROR"

# View specific time range
aws logs tail /ecs/${PROJECT_NAME}-backend-${ENVIRONMENT} \
  --since 1h \
  --format short
```

### Monitor ECS Service

```bash
# Check service status
aws ecs describe-services \
  --cluster ${PROJECT_NAME}-cluster-${ENVIRONMENT} \
  --services ${PROJECT_NAME}-backend-${ENVIRONMENT}

# List running tasks
aws ecs list-tasks \
  --cluster ${PROJECT_NAME}-cluster-${ENVIRONMENT} \
  --service-name ${PROJECT_NAME}-backend-${ENVIRONMENT}

# View task details
aws ecs describe-tasks \
  --cluster ${PROJECT_NAME}-cluster-${ENVIRONMENT} \
  --tasks <task-arn>
```

### Monitor CloudFront

```bash
# View CloudFront metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/CloudFront \
  --metric-name Requests \
  --dimensions Name=DistributionId,Value=${DISTRIBUTION_ID} \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

### Update Application

To deploy updates:

1. **Backend updates**:
   ```bash
   cd backend
   docker build -t ${ECR_URI}:latest -f Dockerfile .
   docker push ${ECR_URI}:latest
   aws ecs update-service \
     --cluster ${PROJECT_NAME}-cluster-${ENVIRONMENT} \
     --service ${PROJECT_NAME}-backend-${ENVIRONMENT} \
     --force-new-deployment
   ```

2. **Frontend updates**:
   ```bash
   cd frontend
   npm run build
   aws s3 sync dist/ s3://${FRONTEND_BUCKET}/ --delete
   aws cloudfront create-invalidation \
     --distribution-id ${DISTRIBUTION_ID} \
     --paths "/*"
   ```

3. **Infrastructure updates**:
   ```bash
   cd infrastructure/cdk
   cdk diff ${CDK_CONTEXT}  # Review changes
   cdk deploy ${CDK_CONTEXT}  # Apply changes
   ```

## Troubleshooting

### Backend Tasks Not Starting

**Symptoms**: ECS tasks fail to start or immediately stop

**Solutions**:
1. Check task logs:
   ```bash
   aws logs tail /ecs/${PROJECT_NAME}-backend-${ENVIRONMENT} --since 10m
   ```

2. Verify Docker image exists in ECR:
   ```bash
   aws ecr describe-images --repository-name ${PROJECT_NAME}-backend-${ENVIRONMENT}
   ```

3. Check IAM role permissions:
   ```bash
   aws iam get-role --role-name ${PROJECT_NAME}-task-role-${ENVIRONMENT}
   ```

4. Verify secrets are configured:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id ${PROJECT_NAME}/${ENVIRONMENT}/auth-password-hash
   ```

### Frontend Not Loading

**Symptoms**: CloudFront returns 403 or 404 errors

**Solutions**:
1. Verify files are in S3:
   ```bash
   aws s3 ls s3://${FRONTEND_BUCKET}/
   ```

2. Check CloudFront distribution status:
   ```bash
   aws cloudfront get-distribution --id ${DISTRIBUTION_ID}
   ```

3. Invalidate CloudFront cache:
   ```bash
   aws cloudfront create-invalidation \
     --distribution-id ${DISTRIBUTION_ID} \
     --paths "/*"
   ```

4. Check S3 bucket policy allows CloudFront OAI access

### API Errors

**Symptoms**: Frontend shows API connection errors

**Solutions**:
1. Verify backend is healthy:
   ```bash
   curl ${BACKEND_URL}/health
   ```

2. Check ALB target health:
   ```bash
   aws elbv2 describe-target-health \
     --target-group-arn <target-group-arn>
   ```

3. Verify security groups allow traffic

4. Check backend logs for errors

### High Costs

**Symptoms**: AWS bill is higher than expected

**Solutions**:
1. Review CloudWatch metrics for usage patterns
2. Reduce ECS task count if over-provisioned
3. Enable S3 Intelligent-Tiering (already configured)
4. Review CloudFront cache hit ratio
5. Delete unused resources:
   ```bash
   # List all stacks
   aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE
   
   # Delete unused stacks
   cdk destroy <stack-name>
   ```

## Cost Estimation

Estimated monthly costs for moderate usage:

| Service | Usage | Estimated Cost |
|---------|-------|----------------|
| ECS Fargate | 2 tasks × 0.5 vCPU × 1 GB | $30-40 |
| Application Load Balancer | 1 ALB | $20-25 |
| S3 Storage | 100 GB videos | $2-3 |
| S3 Requests | 1M requests | $0.50 |
| CloudFront | 100 GB transfer | $8-10 |
| Bedrock (Marengo) | 10 hours video indexing | $50-100 |
| Bedrock (Pegasus) | 1000 analysis requests | $20-30 |
| NAT Gateway | 1 NAT × 100 GB | $35-40 |
| CloudWatch Logs | 10 GB logs | $5 |
| **Total** | | **$170-280/month** |

**Note**: Costs vary based on:
- Number of videos indexed
- Search and analysis frequency
- Video storage size
- Geographic distribution of users
- Data transfer volumes

### Cost Optimization Tips

1. **Use S3 Lifecycle Policies**: Already configured to move videos to Intelligent-Tiering
2. **Optimize ECS Task Count**: Scale down during low-traffic periods
3. **Enable CloudFront Caching**: Reduce origin requests
4. **Use Reserved Capacity**: For predictable workloads
5. **Monitor and Alert**: Set up billing alerts

## Security Best Practices

### Network Security

- ✅ ECS tasks run in private subnets
- ✅ ALB only accepts HTTPS traffic (configure SSL certificate)
- ✅ Security groups follow least privilege
- ✅ VPC flow logs enabled (optional, add via CDK)

### Data Security

- ✅ All S3 buckets encrypted at rest
- ✅ All S3 buckets block public access
- ✅ S3 bucket versioning enabled for metadata
- ✅ CloudFront uses HTTPS only

### Access Control

- ✅ IAM roles follow least privilege
- ✅ Secrets stored in AWS Secrets Manager
- ✅ No hardcoded credentials
- ✅ CloudFront OAI for S3 access

### Application Security

- ✅ Password hashing with bcrypt
- ✅ JWT token authentication
- ✅ Input validation on all endpoints
- ✅ CORS configured (update for production domain)

### Compliance

- Enable AWS CloudTrail for audit logging
- Enable AWS Config for compliance monitoring
- Enable GuardDuty for threat detection
- Regular security assessments

## Cleanup

To completely remove all deployed resources:

```bash
# Destroy all stacks (in reverse order)
cdk destroy ${PROJECT_NAME}-frontend-${ENVIRONMENT} ${CDK_CONTEXT}
cdk destroy ${PROJECT_NAME}-backend-${ENVIRONMENT} ${CDK_CONTEXT}
cdk destroy ${PROJECT_NAME}-storage-${ENVIRONMENT} ${CDK_CONTEXT}

# Manually delete S3 buckets (if RETAIN policy)
aws s3 rb s3://${FRONTEND_BUCKET} --force
aws s3 rb s3://<video-bucket-name> --force
aws s3 rb s3://<metadata-bucket-name> --force

# Delete ECR images
aws ecr batch-delete-image \
  --repository-name ${PROJECT_NAME}-backend-${ENVIRONMENT} \
  --image-ids imageTag=latest

# Delete secrets
aws secretsmanager delete-secret \
  --secret-id ${PROJECT_NAME}/${ENVIRONMENT}/auth-password-hash \
  --force-delete-without-recovery
```

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Amazon ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [CloudFront Best Practices](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/best-practices.html)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)

## Support

For issues or questions:
- Check [GitHub Issues](https://github.com/your-repo/issues)
- Review CloudWatch logs
- Contact AWS Support for service-specific issues
