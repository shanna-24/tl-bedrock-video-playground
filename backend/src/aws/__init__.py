"""AWS clients module."""

from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from aws.s3_vectors_client import S3VectorsClient

__all__ = ["BedrockClient", "S3Client", "S3VectorsClient"]
