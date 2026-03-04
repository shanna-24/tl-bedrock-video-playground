# TL-Video-Playground CDK Infrastructure

This directory contains AWS CDK infrastructure code for deploying TL-Video-Playground to AWS.

## Prerequisites

- AWS CLI configured with appropriate credentials
- AWS CDK CLI installed: `npm install -g aws-cdk`
- Python 3.11+
- Docker (for building container images)

## Project Structure

```
infrastructure/cdk/
├── app.py                 # Main CDK application
├── cdk.json              # CDK configuration
├── requirements.txt      # Python dependencies
├── stacks/
│   ├── storage_stack.py  # S3 buckets for videos and metadata
│   ├── backend_stack.py  # ECS Fargate, ALB, IAM roles
│   └── frontend_stack.py # S3 + CloudFront for static hosting
└── README.md            # This file
```

## Stacks

### 1. Storage Stack
- **Video Bucket**: S3 bucket for video storage with lifecycle policies
- **Metadata Bucket**: S3 bucket for index metadata with versioning

### 2. Backend Stack
- **VPC**: Virtual Private Cloud with public and private subnets
- **ECS Cluster**: Fargate cluster for running backend containers
- **ALB**: Application Load Balancer for routing traffic
- **ECR Repository**: Container registry for backend Docker images
- **IAM Roles**: Permissions for Bedrock, S3, and S3 Vectors
- **Auto-scaling**: CPU and memory-based scaling policies

### 3. Frontend Stack
- **S3 Bucket**: Static website hosting for React application
- **CloudFront**: CDN for global content delivery
- **OAI**: Origin Access Identity for secure S3 access

## Deployment

### 1. Install Dependencies

```bash
cd infrastructure/cdk
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Context

Edit `cdk.json` to set your configuration:

```json
{
  "context": {
    "project_name": "tl-video-playground",
    "environment": "prod",
    "region": "us-east-1",
    "account": "123456789012"
  }
}
```

Or pass context via command line:

```bash
cdk deploy --context account=123456789012 --context region=us-east-1
```

### 3. Bootstrap CDK (First Time Only)

```bash
cdk bootstrap aws://ACCOUNT-NUMBER/REGION
```

### 4. Synthesize CloudFormation Templates

```bash
cdk synth
```

This generates CloudFormation templates in the `cdk.out/` directory.

### 5. Deploy All Stacks

```bash
cdk deploy --all
```

Or deploy individual stacks:

```bash
cdk deploy tl-video-playground-storage-prod
cdk deploy tl-video-playground-backend-prod
cdk deploy tl-video-playground-frontend-prod
```

### 6. Build and Push Backend Docker Image

After deploying the backend stack, build and push the Docker image:

```bash
# Get ECR repository URI from stack outputs
ECR_URI=$(aws cloudformation describe-stacks \
  --stack-name tl-video-playground-backend-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`ECRRepositoryURI`].OutputValue' \
  --output text)

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ECR_URI

# Build and push image
cd ../../backend
docker build -t $ECR_URI:latest -f Dockerfile .
docker push $ECR_URI:latest
```

### 7. Deploy Frontend to S3

After deploying the frontend stack, build and upload the React application:

```bash
# Get S3 bucket name from stack outputs
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name tl-video-playground-frontend-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
  --output text)

# Get backend URL
BACKEND_URL=$(aws cloudformation describe-stacks \
  --stack-name tl-video-playground-backend-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`BackendURL`].OutputValue' \
  --output text)

# Build frontend with backend URL
cd ../../frontend
echo "VITE_API_URL=$BACKEND_URL" > .env.production
npm run build

# Upload to S3
aws s3 sync dist/ s3://$BUCKET_NAME/ --delete

# Get CloudFront distribution ID
DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name tl-video-playground-frontend-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDistributionId`].OutputValue' \
  --output text)

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"
```

### 8. Configure Secrets

Set the authentication password hash in Secrets Manager:

```bash
# Generate password hash
PASSWORD_HASH=$(python3 -c 'import bcrypt; print(bcrypt.hashpw("your_secure_password".encode(), bcrypt.gensalt()).decode())')

# Update secret
aws secretsmanager update-secret \
  --secret-id tl-video-playground/prod/auth-password-hash \
  --secret-string "{\"password_hash\":\"$PASSWORD_HASH\"}"
```

## Useful Commands

### View Stack Outputs

```bash
cdk deploy --outputs-file outputs.json
cat outputs.json
```

### Diff Changes

```bash
cdk diff
```

### Destroy Stacks

```bash
cdk destroy --all
```

**Warning**: This will delete all resources. Video and metadata buckets have `RETAIN` removal policy and must be deleted manually.

### View Logs

```bash
# Backend logs
aws logs tail /ecs/tl-video-playground-backend-prod --follow

# CloudWatch Insights query
aws logs start-query \
  --log-group-name /ecs/tl-video-playground-backend-prod \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, @message | sort @timestamp desc | limit 100'
```

## Cost Optimization

- **NAT Gateway**: Single NAT gateway is used. For production, consider multiple NAT gateways for high availability.
- **ECS Tasks**: Minimum 2 tasks for high availability. Adjust based on load.
- **CloudFront**: Uses PRICE_CLASS_100 (North America and Europe only). Change to PRICE_CLASS_ALL for global distribution.
- **S3 Lifecycle**: Videos automatically move to Intelligent-Tiering after 30 days.

## Security Considerations

- All S3 buckets have encryption enabled
- All S3 buckets block public access
- ECS tasks run in private subnets
- CloudFront uses HTTPS only
- IAM roles follow least privilege principle
- Secrets stored in AWS Secrets Manager

## Monitoring

- **CloudWatch Logs**: All backend logs are sent to CloudWatch
- **Container Insights**: Enabled on ECS cluster for detailed metrics
- **ALB Metrics**: Monitor request count, latency, and error rates
- **CloudFront Metrics**: Monitor cache hit ratio and viewer requests

## Troubleshooting

### Stack Deployment Fails

Check CloudFormation events:
```bash
aws cloudformation describe-stack-events \
  --stack-name tl-video-playground-backend-prod \
  --max-items 20
```

### ECS Tasks Not Starting

Check ECS task logs:
```bash
aws ecs describe-tasks \
  --cluster tl-video-playground-cluster-prod \
  --tasks $(aws ecs list-tasks --cluster tl-video-playground-cluster-prod --query 'taskArns[0]' --output text)
```

### CloudFront Not Serving Updated Content

Invalidate the cache:
```bash
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"
```

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [AWS CloudFront Documentation](https://docs.aws.amazon.com/cloudfront/)
