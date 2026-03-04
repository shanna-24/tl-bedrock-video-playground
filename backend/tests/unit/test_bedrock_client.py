"""Unit tests for Bedrock client wrapper.

Tests the BedrockClient class methods for invoking Marengo and Pegasus models.
Validates: Requirements 7.1, 7.5
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from botocore.exceptions import ClientError

# Add backend/src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from aws.bedrock_client import BedrockClient
from config import Config
from exceptions import BedrockError


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=Config)
    config.marengo_model_id = "twelvelabs.marengo-embed-2-7-v1:0"
    config.pegasus_model_id = "twelvelabs.pegasus-1-2-v1:0"
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-bucket"
    config.use_localstack = False
    config.inference_profile_prefix = "us"
    return config


@pytest.fixture
def mock_config_localstack():
    """Create a mock configuration with LocalStack enabled."""
    config = Mock(spec=Config)
    config.marengo_model_id = "twelvelabs.marengo-embed-2-7-v1:0"
    config.pegasus_model_id = "twelvelabs.pegasus-1-2-v1:0"
    config.aws_region = "us-east-1"
    config.s3_bucket_name = "test-bucket"
    config.use_localstack = True
    config.inference_profile_prefix = "us"
    return config


class TestBedrockClientInitialization:
    """Test suite for BedrockClient initialization."""
    
    @patch("aws.bedrock_client.boto3.client")
    def test_init_without_localstack(self, mock_boto_client, mock_config):
        """Test initialization without LocalStack."""
        client = BedrockClient(mock_config)
        
        assert client.config == mock_config
        mock_boto_client.assert_called_once_with(
            "bedrock-runtime",
            region_name="us-east-1"
        )
    
    @patch("aws.bedrock_client.boto3.client")
    def test_init_with_localstack(self, mock_boto_client, mock_config_localstack):
        """Test initialization with LocalStack."""
        client = BedrockClient(mock_config_localstack)
        
        assert client.config == mock_config_localstack
        mock_boto_client.assert_called_once_with(
            "bedrock-runtime",
            region_name="us-east-1",
            endpoint_url="http://localhost:4566"
        )


class TestMarengoTextEmbedding:
    """Test suite for Marengo text embedding generation."""
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_marengo_text_embedding_success(self, mock_boto_client, mock_config):
        """Test successful text embedding generation."""
        # Setup mock response
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "embedding": [0.1, 0.2, 0.3, 0.4, 0.5]
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        # Create client and invoke
        client = BedrockClient(mock_config)
        embedding = client.invoke_marengo_text_embedding("test query")
        
        # Verify
        assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_client_instance.invoke_model.assert_called_once()
        
        # Check the request body
        call_args = mock_client_instance.invoke_model.call_args
        assert call_args[1]["modelId"] == "twelvelabs.marengo-embed-2-7-v1:0"
        
        request_body = json.loads(call_args[1]["body"])
        assert request_body["inputType"] == "text"
        assert request_body["inputText"] == "test query"
        assert request_body["textTruncate"] == "end"
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_marengo_text_embedding_with_truncate_none(
        self, mock_boto_client, mock_config
    ):
        """Test text embedding with truncate=none."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "embedding": [0.1, 0.2]
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        client = BedrockClient(mock_config)
        embedding = client.invoke_marengo_text_embedding(
            "test query",
            text_truncate="none"
        )
        
        assert embedding == [0.1, 0.2]
        
        # Check the request body
        call_args = mock_client_instance.invoke_model.call_args
        request_body = json.loads(call_args[1]["body"])
        assert request_body["textTruncate"] == "none"
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_marengo_text_embedding_client_error(
        self, mock_boto_client, mock_config
    ):
        """Test handling of ClientError from Bedrock API."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Simulate ClientError
        error_response = {
            "Error": {
                "Code": "ValidationException",
                "Message": "Invalid input text"
            }
        }
        mock_client_instance.invoke_model.side_effect = ClientError(
            error_response, "InvokeModel"
        )
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            client.invoke_marengo_text_embedding("test query")
        
        assert "Failed to generate text embedding" in str(exc_info.value)
        assert "Invalid input text" in str(exc_info.value)
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_marengo_text_embedding_unexpected_error(
        self, mock_boto_client, mock_config
    ):
        """Test handling of unexpected errors."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Simulate unexpected error
        mock_client_instance.invoke_model.side_effect = ValueError("Unexpected error")
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            client.invoke_marengo_text_embedding("test query")
        
        assert "Failed to generate text embedding" in str(exc_info.value)


class TestMarengoVideoEmbedding:
    """Test suite for Marengo video embedding generation."""
    
    @patch("aws.bedrock_client.boto3.client")
    def test_start_marengo_video_embedding_success(
        self, mock_boto_client, mock_config
    ):
        """Test successful async video embedding start."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "invocationArn": "arn:aws:bedrock:us-east-1:123456789012:async-invoke/abc123"
        }
        mock_client_instance.start_async_invoke.return_value = mock_response
        
        client = BedrockClient(mock_config)
        invocation_arn = client.start_marengo_video_embedding(
            s3_uri="s3://test-bucket/video.mp4"
        )
        
        assert invocation_arn == "arn:aws:bedrock:us-east-1:123456789012:async-invoke/abc123"
        mock_client_instance.start_async_invoke.assert_called_once()
        
        # Check the request
        call_args = mock_client_instance.start_async_invoke.call_args
        assert call_args[1]["modelId"] == "twelvelabs.marengo-embed-2-7-v1:0"
        
        model_input = call_args[1]["modelInput"]
        assert model_input["inputType"] == "video"
        assert model_input["mediaSource"]["s3Location"]["uri"] == "s3://test-bucket/video.mp4"
        assert model_input["embeddingOption"] == ["visual-text", "visual-image", "audio"]
        assert model_input["startSec"] == 0.0
        assert model_input["minClipSec"] == 4
    
    @patch("aws.bedrock_client.boto3.client")
    def test_start_marengo_video_embedding_with_options(
        self, mock_boto_client, mock_config
    ):
        """Test video embedding with custom options."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "invocationArn": "arn:aws:bedrock:us-east-1:123456789012:async-invoke/abc123"
        }
        mock_client_instance.start_async_invoke.return_value = mock_response
        
        client = BedrockClient(mock_config)
        invocation_arn = client.start_marengo_video_embedding(
            s3_uri="s3://test-bucket/video.mp4",
            bucket_owner="123456789012",
            embedding_options=["visual-text"],
            start_sec=10.0,
            length_sec=30.0,
            use_fixed_length_sec=5.0,
            min_clip_sec=2
        )
        
        assert invocation_arn == "arn:aws:bedrock:us-east-1:123456789012:async-invoke/abc123"
        
        # Check the request
        call_args = mock_client_instance.start_async_invoke.call_args
        model_input = call_args[1]["modelInput"]
        
        assert model_input["mediaSource"]["s3Location"]["bucketOwner"] == "123456789012"
        assert model_input["embeddingOption"] == ["visual-text"]
        assert model_input["startSec"] == 10.0
        assert model_input["lengthSec"] == 30.0
        assert model_input["useFixedLengthSec"] == 5.0
        assert model_input["minClipSec"] == 2
    
    @patch("aws.bedrock_client.boto3.client")
    def test_start_marengo_video_embedding_client_error(
        self, mock_boto_client, mock_config
    ):
        """Test handling of ClientError for video embedding."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "Video not found in S3"
            }
        }
        mock_client_instance.start_async_invoke.side_effect = ClientError(
            error_response, "StartAsyncInvoke"
        )
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            client.start_marengo_video_embedding("s3://test-bucket/video.mp4")
        
        assert "Failed to start video embedding" in str(exc_info.value)
        assert "Video not found in S3" in str(exc_info.value)


class TestPegasusAnalysis:
    """Test suite for Pegasus video analysis."""
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_pegasus_analysis_success(self, mock_boto_client, mock_config):
        """Test successful video analysis."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "message": "This video shows a person walking in a park.",
            "finishReason": "stop"
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        client = BedrockClient(mock_config)
        result = client.invoke_pegasus_analysis(
            s3_uri="s3://test-bucket/video.mp4",
            prompt="Describe this video"
        )
        
        assert result["message"] == "This video shows a person walking in a park."
        assert result["finishReason"] == "stop"
        
        # Check the request
        call_args = mock_client_instance.invoke_model.call_args
        assert call_args[1]["modelId"] == "twelvelabs.pegasus-1-2-v1:0"
        
        request_body = json.loads(call_args[1]["body"])
        assert request_body["inputPrompt"] == "Describe this video"
        assert request_body["mediaSource"]["s3Location"]["uri"] == "s3://test-bucket/video.mp4"
        assert request_body["temperature"] == 0.2
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_pegasus_analysis_with_options(
        self, mock_boto_client, mock_config
    ):
        """Test video analysis with custom options."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "body": MagicMock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "message": "Analysis result",
            "finishReason": "length"
        }).encode()
        
        mock_client_instance.invoke_model.return_value = mock_response
        
        client = BedrockClient(mock_config)
        result = client.invoke_pegasus_analysis(
            s3_uri="s3://test-bucket/video.mp4",
            prompt="Analyze this video",
            bucket_owner="123456789012",
            temperature=0.5,
            max_output_tokens=2048,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "analysis"}
            }
        )
        
        assert result["message"] == "Analysis result"
        assert result["finishReason"] == "length"
        
        # Check the request
        call_args = mock_client_instance.invoke_model.call_args
        request_body = json.loads(call_args[1]["body"])
        
        assert request_body["mediaSource"]["s3Location"]["bucketOwner"] == "123456789012"
        assert request_body["temperature"] == 0.5
        assert request_body["maxOutputTokens"] == 2048
        assert "responseFormat" in request_body
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_pegasus_analysis_client_error(
        self, mock_boto_client, mock_config
    ):
        """Test handling of ClientError for video analysis."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "ThrottlingException",
                "Message": "Rate exceeded"
            }
        }
        mock_client_instance.invoke_model.side_effect = ClientError(
            error_response, "InvokeModel"
        )
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            client.invoke_pegasus_analysis(
                s3_uri="s3://test-bucket/video.mp4",
                prompt="Analyze this"
            )
        
        assert "Failed to analyze video" in str(exc_info.value)
        assert "Rate exceeded" in str(exc_info.value)


class TestPegasusStreamingAnalysis:
    """Test suite for Pegasus streaming video analysis."""
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_pegasus_streaming_success(self, mock_boto_client, mock_config):
        """Test successful streaming video analysis."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Mock streaming response
        mock_stream = [
            {"chunk": {"bytes": json.dumps({"message": "This "}).encode()}},
            {"chunk": {"bytes": json.dumps({"message": "is "}).encode()}},
            {"chunk": {"bytes": json.dumps({"message": "a test"}).encode()}},
        ]
        
        mock_response = {
            "body": iter(mock_stream)
        }
        mock_client_instance.invoke_model_with_response_stream.return_value = mock_response
        
        client = BedrockClient(mock_config)
        chunks = list(client.invoke_pegasus_analysis_streaming(
            s3_uri="s3://test-bucket/video.mp4",
            prompt="Describe this video"
        ))
        
        assert chunks == ["This ", "is ", "a test"]
    
    @patch("aws.bedrock_client.boto3.client")
    def test_invoke_pegasus_streaming_client_error(
        self, mock_boto_client, mock_config
    ):
        """Test handling of ClientError for streaming analysis."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "ServiceUnavailable",
                "Message": "Service temporarily unavailable"
            }
        }
        mock_client_instance.invoke_model_with_response_stream.side_effect = ClientError(
            error_response, "InvokeModelWithResponseStream"
        )
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            list(client.invoke_pegasus_analysis_streaming(
                s3_uri="s3://test-bucket/video.mp4",
                prompt="Analyze this"
            ))
        
        assert "Failed to analyze video with streaming" in str(exc_info.value)


class TestAsyncInvocationStatus:
    """Test suite for async invocation status checking."""
    
    @patch("aws.bedrock_client.boto3.client")
    def test_get_async_invocation_status_success(
        self, mock_boto_client, mock_config
    ):
        """Test successful status retrieval."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "status": "Completed",
            "outputDataConfig": {
                "s3OutputDataConfig": {
                    "s3Uri": "s3://test-bucket/embeddings/output.json"
                }
            }
        }
        mock_client_instance.get_async_invoke.return_value = mock_response
        
        client = BedrockClient(mock_config)
        status = client.get_async_invocation_status(
            "arn:aws:bedrock:us-east-1:123456789012:async-invoke/abc123"
        )
        
        assert status["status"] == "Completed"
        assert status["outputDataConfig"] is not None
        assert status["failureMessage"] is None
    
    @patch("aws.bedrock_client.boto3.client")
    def test_get_async_invocation_status_failed(
        self, mock_boto_client, mock_config
    ):
        """Test status retrieval for failed invocation."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        mock_response = {
            "status": "Failed",
            "failureMessage": "Video processing failed"
        }
        mock_client_instance.get_async_invoke.return_value = mock_response
        
        client = BedrockClient(mock_config)
        status = client.get_async_invocation_status(
            "arn:aws:bedrock:us-east-1:123456789012:async-invoke/abc123"
        )
        
        assert status["status"] == "Failed"
        assert status["failureMessage"] == "Video processing failed"
    
    @patch("aws.bedrock_client.boto3.client")
    def test_get_async_invocation_status_client_error(
        self, mock_boto_client, mock_config
    ):
        """Test handling of ClientError for status check."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        error_response = {
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "Invocation not found"
            }
        }
        mock_client_instance.get_async_invoke.side_effect = ClientError(
            error_response, "GetAsyncInvoke"
        )
        
        client = BedrockClient(mock_config)
        
        with pytest.raises(BedrockError) as exc_info:
            client.get_async_invocation_status(
                "arn:aws:bedrock:us-east-1:123456789012:async-invoke/abc123"
            )
        
        assert "Failed to get async invocation status" in str(exc_info.value)
        assert "Invocation not found" in str(exc_info.value)


class TestErrorHandling:
    """Test suite for AWS error handling (Requirement 7.5)."""
    
    @patch("aws.bedrock_client.boto3.client")
    def test_descriptive_error_messages(self, mock_boto_client, mock_config):
        """Test that AWS errors are transformed into descriptive messages."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Test various AWS error codes
        error_cases = [
            ("ValidationException", "Invalid input parameters"),
            ("ThrottlingException", "Request rate exceeded"),
            ("ResourceNotFoundException", "Resource not found"),
            ("ServiceUnavailableException", "Service temporarily unavailable"),
        ]
        
        client = BedrockClient(mock_config)
        
        for error_code, error_message in error_cases:
            error_response = {
                "Error": {
                    "Code": error_code,
                    "Message": error_message
                }
            }
            mock_client_instance.invoke_model.side_effect = ClientError(
                error_response, "InvokeModel"
            )
            
            with pytest.raises(BedrockError) as exc_info:
                client.invoke_marengo_text_embedding("test")
            
            # Verify the error message is descriptive and includes the AWS message
            assert error_message in str(exc_info.value)
            assert "Failed to generate text embedding" in str(exc_info.value)



class TestStopModelInvocationJob:
    """Test suite for stopping model invocation jobs."""
    
    @patch("aws.bedrock_client.boto3.client")
    def test_stop_model_invocation_job_success(
        self, mock_boto_client, mock_config
    ):
        """Test successfully stopping a model invocation job."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Mock successful stop response (empty response)
        mock_client_instance.stop_model_invocation_job.return_value = {}
        
        # Create client and stop job
        client = BedrockClient(mock_config)
        invocation_arn = "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-123"
        
        # Should not raise any exception
        client.stop_model_invocation_job(invocation_arn)
        
        # Verify the API was called correctly
        mock_client_instance.stop_model_invocation_job.assert_called_once_with(
            jobIdentifier=invocation_arn
        )
    
    @patch("aws.bedrock_client.boto3.client")
    def test_stop_model_invocation_job_conflict_error(
        self, mock_boto_client, mock_config
    ):
        """Test stopping a job that cannot be stopped (ConflictException)."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Mock ConflictException (job already completed/failed)
        error_response = {
            "Error": {
                "Code": "ConflictException",
                "Message": "Job is not in a state that can be stopped"
            }
        }
        mock_client_instance.stop_model_invocation_job.side_effect = ClientError(
            error_response, "StopModelInvocationJob"
        )
        
        # Create client and attempt to stop job
        client = BedrockClient(mock_config)
        invocation_arn = "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-123"
        
        # Should raise BedrockError with appropriate message
        with pytest.raises(BedrockError) as exc_info:
            client.stop_model_invocation_job(invocation_arn)
        
        assert "cannot be stopped" in str(exc_info.value).lower()
        assert "may already be completed or failed" in str(exc_info.value).lower()
    
    @patch("aws.bedrock_client.boto3.client")
    def test_stop_model_invocation_job_not_found(
        self, mock_boto_client, mock_config
    ):
        """Test stopping a job that doesn't exist (ResourceNotFoundException)."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Mock ResourceNotFoundException
        error_response = {
            "Error": {
                "Code": "ResourceNotFoundException",
                "Message": "Job not found"
            }
        }
        mock_client_instance.stop_model_invocation_job.side_effect = ClientError(
            error_response, "StopModelInvocationJob"
        )
        
        # Create client and attempt to stop job
        client = BedrockClient(mock_config)
        invocation_arn = "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/nonexistent"
        
        # Should raise BedrockError with appropriate message
        with pytest.raises(BedrockError) as exc_info:
            client.stop_model_invocation_job(invocation_arn)
        
        assert "job not found" in str(exc_info.value).lower()
    
    @patch("aws.bedrock_client.boto3.client")
    def test_stop_model_invocation_job_throttling(
        self, mock_boto_client, mock_config
    ):
        """Test handling throttling error when stopping job."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Mock ThrottlingException
        error_response = {
            "Error": {
                "Code": "ThrottlingException",
                "Message": "Rate exceeded"
            }
        }
        mock_client_instance.stop_model_invocation_job.side_effect = ClientError(
            error_response, "StopModelInvocationJob"
        )
        
        # Create client and attempt to stop job
        client = BedrockClient(mock_config)
        invocation_arn = "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-123"
        
        # Should raise BedrockError with appropriate message
        with pytest.raises(BedrockError) as exc_info:
            client.stop_model_invocation_job(invocation_arn)
        
        assert "failed to stop model invocation job" in str(exc_info.value).lower()
        assert "rate exceeded" in str(exc_info.value).lower()
    
    @patch("aws.bedrock_client.boto3.client")
    def test_stop_model_invocation_job_unexpected_error(
        self, mock_boto_client, mock_config
    ):
        """Test handling unexpected errors when stopping job."""
        mock_client_instance = MagicMock()
        mock_boto_client.return_value = mock_client_instance
        
        # Mock unexpected exception
        mock_client_instance.stop_model_invocation_job.side_effect = Exception(
            "Unexpected error"
        )
        
        # Create client and attempt to stop job
        client = BedrockClient(mock_config)
        invocation_arn = "arn:aws:bedrock:us-east-1:123456789012:model-invocation-job/test-job-123"
        
        # Should raise BedrockError with appropriate message
        with pytest.raises(BedrockError) as exc_info:
            client.stop_model_invocation_job(invocation_arn)
        
        assert "failed to stop model invocation job" in str(exc_info.value).lower()
        assert "unexpected error" in str(exc_info.value).lower()
