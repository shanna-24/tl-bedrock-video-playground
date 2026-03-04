"""Frontend Stack - S3 and CloudFront for static website hosting"""

from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_iam as iam,
)
from constructs import Construct


class FrontendStack(Stack):
    """
    Frontend infrastructure stack for TL-Video-Playground.
    
    Creates:
    - S3 bucket for static website hosting
    - CloudFront distribution for global CDN
    - Origin Access Identity for secure S3 access
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        environment: str,
        backend_url: str,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.project_name = project_name
        self.environment = environment
        self.backend_url = backend_url

        # Create S3 bucket for frontend
        self.frontend_bucket = self._create_frontend_bucket()

        # Create CloudFront distribution
        self.distribution = self._create_cloudfront_distribution()

        # Add outputs
        self._add_outputs()

    def _create_frontend_bucket(self) -> s3.Bucket:
        """Create S3 bucket for hosting frontend static files"""
        bucket = s3.Bucket(
            self,
            "FrontendBucket",
            bucket_name=f"{self.project_name}-frontend-{self.environment}-{self.account}",
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,  # CloudFront will access via OAI
            removal_policy=RemovalPolicy.DESTROY,  # Frontend can be rebuilt
            auto_delete_objects=True,
            website_index_document="index.html",
            website_error_document="index.html"  # For SPA routing
        )

        return bucket

    def _create_cloudfront_distribution(self) -> cloudfront.Distribution:
        """Create CloudFront distribution for global content delivery"""
        
        # Create Origin Access Identity
        oai = cloudfront.OriginAccessIdentity(
            self,
            "OAI",
            comment=f"OAI for {self.project_name} frontend"
        )

        # Grant CloudFront read access to S3 bucket
        self.frontend_bucket.grant_read(oai)

        # Create CloudFront distribution
        distribution = cloudfront.Distribution(
            self,
            "Distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    self.frontend_bucket,
                    origin_access_identity=oai
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                compress=True
            ),
            default_root_object="index.html",
            error_responses=[
                # Handle SPA routing - return index.html for 404s
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                ),
                cloudfront.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.minutes(5)
                )
            ],
            price_class=cloudfront.PriceClass.PRICE_CLASS_100,  # Use only North America and Europe
            comment=f"{self.project_name} frontend distribution"
        )

        return distribution

    def _add_outputs(self):
        """Add CloudFormation outputs"""
        from aws_cdk import CfnOutput

        CfnOutput(
            self,
            "FrontendBucketName",
            value=self.frontend_bucket.bucket_name,
            description="S3 bucket for frontend static files",
            export_name=f"{self.stack_name}-frontend-bucket"
        )

        CfnOutput(
            self,
            "CloudFrontURL",
            value=f"https://{self.distribution.distribution_domain_name}",
            description="CloudFront distribution URL",
            export_name=f"{self.stack_name}-cloudfront-url"
        )

        CfnOutput(
            self,
            "CloudFrontDistributionId",
            value=self.distribution.distribution_id,
            description="CloudFront distribution ID",
            export_name=f"{self.stack_name}-distribution-id"
        )

        CfnOutput(
            self,
            "BackendURL",
            value=self.backend_url,
            description="Backend API URL for frontend configuration"
        )
