#!/usr/bin/env python3
"""
TL-Video-Playground AWS CDK Application

This CDK app defines the infrastructure for deploying the TL-Video-Playground
system to AWS, including:
- Frontend: S3 + CloudFront
- Backend: ECS Fargate + ALB
- Storage: S3 buckets for videos and metadata
- AI: Amazon Bedrock integration
"""

import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.backend_stack import BackendStack
from stacks.frontend_stack import FrontendStack

app = cdk.App()

# Get environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1"
)

# Stack naming prefix
project_name = app.node.try_get_context("project_name") or "tl-video-playground"
environment_name = app.node.try_get_context("environment") or "prod"

# Storage Stack - S3 buckets for videos and metadata
storage_stack = StorageStack(
    app,
    f"{project_name}-storage-{environment_name}",
    project_name=project_name,
    environment=environment_name,
    env=env,
    description="Storage infrastructure for TL-Video-Playground (S3 buckets)"
)

# Backend Stack - ECS Fargate, ALB, IAM roles
backend_stack = BackendStack(
    app,
    f"{project_name}-backend-{environment_name}",
    project_name=project_name,
    environment=environment_name,
    video_bucket=storage_stack.video_bucket,
    metadata_bucket=storage_stack.metadata_bucket,
    env=env,
    description="Backend infrastructure for TL-Video-Playground (ECS Fargate + ALB)"
)

# Frontend Stack - S3 + CloudFront
frontend_stack = FrontendStack(
    app,
    f"{project_name}-frontend-{environment_name}",
    project_name=project_name,
    environment=environment_name,
    backend_url=backend_stack.alb_url,
    env=env,
    description="Frontend infrastructure for TL-Video-Playground (S3 + CloudFront)"
)

# Add dependencies
backend_stack.add_dependency(storage_stack)
frontend_stack.add_dependency(backend_stack)

# Add tags to all resources
cdk.Tags.of(app).add("Project", project_name)
cdk.Tags.of(app).add("Environment", environment_name)
cdk.Tags.of(app).add("ManagedBy", "CDK")

app.synth()
