"""Storage Stack - S3 buckets for videos and metadata"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
)
from constructs import Construct


class StorageStack(Stack):
    """
    Storage infrastructure stack for TL-Video-Playground.
    
    Creates:
    - S3 bucket for video storage with lifecycle policies
    - S3 bucket for metadata storage
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        environment: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Video storage bucket
        self.video_bucket = s3.Bucket(
            self,
            "VideoBucket",
            bucket_name=f"{project_name}-videos-{environment}-{self.account}",
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,  # Protect video data
            auto_delete_objects=False,
            lifecycle_rules=[
                # Move to Intelligent-Tiering after 30 days
                s3.LifecycleRule(
                    id="intelligent-tiering",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                            transition_after=Duration.days(30)
                        )
                    ]
                ),
                # Delete incomplete multipart uploads after 7 days
                s3.LifecycleRule(
                    id="cleanup-incomplete-uploads",
                    enabled=True,
                    abort_incomplete_multipart_upload_after=Duration.days(7)
                )
            ],
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.POST,
                        s3.HttpMethods.DELETE
                    ],
                    allowed_origins=["*"],  # Update with specific frontend domain in production
                    allowed_headers=["*"],
                    max_age=3000
                )
            ]
        )

        # Metadata storage bucket
        self.metadata_bucket = s3.Bucket(
            self,
            "MetadataBucket",
            bucket_name=f"{project_name}-metadata-{environment}-{self.account}",
            versioned=True,  # Enable versioning for metadata
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,  # Protect metadata
            auto_delete_objects=False,
            lifecycle_rules=[
                # Keep only last 10 versions
                s3.LifecycleRule(
                    id="limit-versions",
                    enabled=True,
                    noncurrent_version_expiration=Duration.days(90),
                    noncurrent_versions_to_retain=10
                )
            ]
        )

        # Output bucket names
        self._add_outputs()

    def _add_outputs(self):
        """Add CloudFormation outputs"""
        from aws_cdk import CfnOutput

        CfnOutput(
            self,
            "VideoBucketName",
            value=self.video_bucket.bucket_name,
            description="S3 bucket for video storage",
            export_name=f"{self.stack_name}-video-bucket"
        )

        CfnOutput(
            self,
            "MetadataBucketName",
            value=self.metadata_bucket.bucket_name,
            description="S3 bucket for metadata storage",
            export_name=f"{self.stack_name}-metadata-bucket"
        )
