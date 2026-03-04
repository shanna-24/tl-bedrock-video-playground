"""Backend Stack - ECS Fargate, ALB, and IAM roles"""

from aws_cdk import (
    Stack,
    Duration,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_logs as logs,
    aws_ecr as ecr,
    aws_secretsmanager as secretsmanager,
    aws_s3 as s3,
)
from constructs import Construct


class BackendStack(Stack):
    """
    Backend infrastructure stack for TL-Video-Playground.
    
    Creates:
    - VPC with public and private subnets
    - ECS Fargate cluster
    - Application Load Balancer
    - ECS service with auto-scaling
    - IAM roles for Bedrock, S3, and S3 Vectors access
    - CloudWatch log groups
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        project_name: str,
        environment: str,
        video_bucket: s3.Bucket,
        metadata_bucket: s3.Bucket,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.project_name = project_name
        self.environment = environment
        self.video_bucket = video_bucket
        self.metadata_bucket = metadata_bucket

        # Create VPC
        self.vpc = self._create_vpc()

        # Create ECR repository
        self.ecr_repository = self._create_ecr_repository()

        # Create ECS cluster
        self.cluster = self._create_ecs_cluster()

        # Create secrets for configuration
        self.secrets = self._create_secrets()

        # Create IAM role for ECS tasks
        self.task_role = self._create_task_role()

        # Create Fargate service with ALB
        self.fargate_service = self._create_fargate_service()

        # Store ALB URL for frontend
        self.alb_url = f"http://{self.fargate_service.load_balancer.load_balancer_dns_name}"

        # Add outputs
        self._add_outputs()

    def _create_vpc(self) -> ec2.Vpc:
        """Create VPC with public and private subnets"""
        return ec2.Vpc(
            self,
            "VPC",
            vpc_name=f"{self.project_name}-vpc-{self.environment}",
            max_azs=2,  # Use 2 availability zones
            nat_gateways=1,  # Single NAT gateway for cost optimization
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ]
        )

    def _create_ecr_repository(self) -> ecr.Repository:
        """Create ECR repository for Docker images"""
        return ecr.Repository(
            self,
            "BackendRepository",
            repository_name=f"{self.project_name}-backend-{self.environment}",
            image_scan_on_push=True,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Keep only last 10 images",
                    max_image_count=10
                )
            ]
        )

    def _create_ecs_cluster(self) -> ecs.Cluster:
        """Create ECS cluster"""
        return ecs.Cluster(
            self,
            "Cluster",
            cluster_name=f"{self.project_name}-cluster-{self.environment}",
            vpc=self.vpc,
            container_insights=True
        )

    def _create_secrets(self) -> dict:
        """Create Secrets Manager secrets for sensitive configuration"""
        auth_password_secret = secretsmanager.Secret(
            self,
            "AuthPasswordSecret",
            secret_name=f"{self.project_name}/{self.environment}/auth-password-hash",
            description="Bcrypt hash of the authentication password",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"password_hash":""}',
                generate_string_key="password_hash",
                exclude_punctuation=True,
                password_length=60
            )
        )

        return {
            "auth_password": auth_password_secret
        }

    def _create_task_role(self) -> iam.Role:
        """Create IAM role for ECS tasks with necessary permissions"""
        role = iam.Role(
            self,
            "TaskRole",
            role_name=f"{self.project_name}-task-role-{self.environment}",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description="IAM role for TL-Video-Playground ECS tasks"
        )

        # Grant S3 permissions
        self.video_bucket.grant_read_write(role)
        self.metadata_bucket.grant_read_write(role)

        # Grant Bedrock permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:ListFoundationModels",
                    "bedrock:GetFoundationModel"
                ],
                resources=["*"]  # Bedrock models don't have specific ARNs
            )
        )

        # Grant Bedrock S3 Vectors permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:CreateKnowledgeBase",
                    "bedrock:GetKnowledgeBase",
                    "bedrock:DeleteKnowledgeBase",
                    "bedrock:ListKnowledgeBases",
                    "bedrock:CreateDataSource",
                    "bedrock:GetDataSource",
                    "bedrock:DeleteDataSource",
                    "bedrock:StartIngestionJob",
                    "bedrock:GetIngestionJob"
                ],
                resources=["*"]
            )
        )

        # Grant Secrets Manager permissions
        self.secrets["auth_password"].grant_read(role)

        # Grant CloudWatch Logs permissions
        role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=["*"]
            )
        )

        return role

    def _create_fargate_service(self) -> ecs_patterns.ApplicationLoadBalancedFargateService:
        """Create Fargate service with Application Load Balancer"""
        
        # Create log group
        log_group = logs.LogGroup(
            self,
            "BackendLogGroup",
            log_group_name=f"/ecs/{self.project_name}-backend-{self.environment}",
            retention=logs.RetentionDays.ONE_WEEK
        )

        # Create Fargate service
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "FargateService",
            cluster=self.cluster,
            service_name=f"{self.project_name}-backend-{self.environment}",
            cpu=512,  # 0.5 vCPU
            memory_limit_mib=1024,  # 1 GB
            desired_count=2,  # Run 2 tasks for high availability
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(self.ecr_repository, "latest"),
                container_name="backend",
                container_port=8000,
                task_role=self.task_role,
                environment={
                    "AWS_DEFAULT_REGION": self.region,
                    "S3_BUCKET_NAME": self.video_bucket.bucket_name,
                    "METADATA_BUCKET_NAME": self.metadata_bucket.bucket_name,
                    "ENVIRONMENT": self.environment
                },
                secrets={
                    "AUTH_PASSWORD_HASH": ecs.Secret.from_secrets_manager(
                        self.secrets["auth_password"],
                        "password_hash"
                    )
                },
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="backend",
                    log_group=log_group
                )
            ),
            public_load_balancer=True,
            assign_public_ip=False  # Tasks in private subnets
        )

        # Configure health check
        fargate_service.target_group.configure_health_check(
            path="/health",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(5),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3
        )

        # Configure auto-scaling
        scaling = fargate_service.service.auto_scale_task_count(
            min_capacity=2,
            max_capacity=10
        )

        # Scale based on CPU utilization
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60)
        )

        # Scale based on memory utilization
        scaling.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60)
        )

        return fargate_service

    def _add_outputs(self):
        """Add CloudFormation outputs"""
        from aws_cdk import CfnOutput

        CfnOutput(
            self,
            "LoadBalancerDNS",
            value=self.fargate_service.load_balancer.load_balancer_dns_name,
            description="Application Load Balancer DNS name",
            export_name=f"{self.stack_name}-alb-dns"
        )

        CfnOutput(
            self,
            "BackendURL",
            value=self.alb_url,
            description="Backend API URL",
            export_name=f"{self.stack_name}-backend-url"
        )

        CfnOutput(
            self,
            "ECRRepositoryURI",
            value=self.ecr_repository.repository_uri,
            description="ECR repository URI for backend Docker images",
            export_name=f"{self.stack_name}-ecr-uri"
        )

        CfnOutput(
            self,
            "ClusterName",
            value=self.cluster.cluster_name,
            description="ECS cluster name",
            export_name=f"{self.stack_name}-cluster-name"
        )
